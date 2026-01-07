"""
Docker Executor - Manages code execution in Docker containers.

Uses centralized configuration from config/environments.yaml for
environment definitions (images, commands, etc.)
"""

import docker
import time
from typing import Dict, Any, Optional
from docker.errors import DockerException, NotFound, APIError

from app.config import settings


class DockerExecutor:
    """Executes code in isolated Docker containers."""
    
    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def get_image_name(self, environment: str) -> str:
        """Get Docker image name for environment from config."""
        env_config = settings.get_environment(environment)
        if env_config:
            return env_config.get_full_image_name(settings.docker_image_prefix)
        # Fallback for unknown environments
        return f"{settings.docker_image_prefix}-{environment}"

    def get_default_filename(self, environment: str) -> str:
        """Get default filename for environment from config."""
        env_config = settings.get_environment(environment)
        if env_config:
            return env_config.default_filename
        return "main.py"

    def create_container(self, session_id: str, environment: str) -> str:
        """Create a new container for the session."""
        image_name = self.get_image_name(environment)

        try:
            container = self.client.containers.create(
                image=image_name,
                name=f"session-{session_id[:8]}",
                command=["sleep", "infinity"],
                detach=True,
                mem_limit=settings.container_memory_limit,
                cpu_period=100000,
                cpu_quota=int(settings.container_cpu_limit * 100000),
                pids_limit=settings.container_pids_limit,
                network_mode="none" if settings.network_disabled else "bridge",
                security_opt=["no-new-privileges:true"] if settings.no_new_privileges else [],
                read_only=settings.read_only,
                working_dir=settings.workspace_dir,
                user=settings.executor_user,
                labels={
                    "code-executor": "true",
                    "session_id": session_id,
                    "environment": environment,
                },
                tmpfs={"/tmp": f"size={settings.tmpfs_size},noexec,nosuid,nodev"},
            )
            container.start()
            return container.id
        except docker.errors.ImageNotFound:
            raise DockerException(
                f"Image '{image_name}' not found. "
                f"Please build it first using: docker build -t {image_name} environments/{environment}/"
            )

    def stop_container(self, container_id: str) -> None:
        """Stop and remove a container."""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove(force=True)
        except NotFound:
            pass
        except APIError as e:
            print(f"Error stopping container {container_id}: {e}")

    def execute_code(
        self,
        container_id: str,
        code: str,
        environment: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute code in the container."""
        if filename is None:
            filename = self.get_default_filename(environment)

        try:
            container = self.client.containers.get(container_id)

            # Write code to container
            file_path = f"{settings.workspace_dir}/{filename}"
            write_result = container.exec_run(
                cmd=["sh", "-c", f"cat > {file_path}"],
                stdin=True,
                socket=True,
                user=settings.executor_user
            )
            sock = write_result.output
            sock._sock.sendall(code.encode("utf-8"))
            sock._sock.close()

            # Small delay to ensure file is written
            time.sleep(0.1)

            # Get run command from config
            run_cmd = self._get_run_command(environment, file_path)

            # Execute code with timeout
            start_time = time.time()
            exec_result = container.exec_run(
                cmd=["timeout", str(settings.execution_timeout)] + run_cmd,
                demux=True,
                user=settings.executor_user
            )
            execution_time = time.time() - start_time

            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            exit_code = exec_result.exit_code

            # Handle timeout exit code (124 from timeout command)
            if exit_code == 124:
                stderr = b"Execution timed out\n" + stderr

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "execution_time": round(execution_time, 3),
            }

        except NotFound:
            return {
                "stdout": "",
                "stderr": "Container not found. Session may have expired.",
                "exit_code": -1,
                "execution_time": 0,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1,
                "execution_time": 0,
            }

    def _get_run_command(self, environment: str, file_path: str) -> list:
        """
        Get the run command for the environment from config.
        
        The command is defined in config/environments.yaml and supports
        placeholders: {file_path}, {filename}, {output_path}
        """
        env_config = settings.get_environment(environment)
        if env_config:
            return env_config.get_run_command(file_path)
        
        # Fallback for unknown environments
        return ["python", file_path]

    def container_exists(self, container_id: str) -> bool:
        """Check if container exists."""
        try:
            self.client.containers.get(container_id)
            return True
        except NotFound:
            return False

    def cleanup_orphaned_containers(self) -> list:
        """Remove containers that are no longer associated with active sessions."""
        cleaned = []
        try:
            containers = self.client.containers.list(
                filters={"label": "code-executor=true"}
            )
            for container in containers:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    cleaned.append(container.id)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error during cleanup: {e}")
        return cleaned

    def get_container_stats(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container resource usage stats."""
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            return {
                "memory_usage": stats["memory_stats"].get("usage", 0),
                "memory_limit": stats["memory_stats"].get("limit", 0),
                "cpu_percent": self._calculate_cpu_percent(stats),
            }
        except Exception:
            return None

    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU usage percentage from stats."""
        try:
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            if system_delta > 0:
                cpu_count = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1]))
                return (cpu_delta / system_delta) * cpu_count * 100.0
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0


# Lazy singleton - won't connect to Docker until first use
docker_executor = DockerExecutor()
