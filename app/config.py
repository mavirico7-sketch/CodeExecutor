"""
Centralized configuration loader for Code Executor.

Loads configuration from:
  - Environment variables (from code-executor.conf via docker-compose env_file)
  - config/environments.yaml (execution environments, copied in Dockerfile)
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)

# Environments file paths
ENVIRONMENTS_FILE_PATHS = [
    Path("/app/config/environments.yaml"),  # Docker (copied via Dockerfile)
    Path.cwd() / "config" / "environments.yaml",  # Local development
]


def _find_environments_file() -> Optional[Path]:
    """Find environments.yaml file."""
    for path in ENVIRONMENTS_FILE_PATHS:
        if path.exists():
            logger.info(f"Found environments.yaml at: {path}")
            return path
    logger.warning(f"environments.yaml not found in: {[str(p) for p in ENVIRONMENTS_FILE_PATHS]}")
    return None


def _env(key: str, default: Any = None) -> Any:
    """Get value from environment variable."""
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in ('true', 'yes', '1', 'on')


def _env_int(key: str, default: int = 0) -> int:
    """Get int from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float = 0.0) -> float:
    """Get float from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


@dataclass
class EnvironmentConfig:
    """Configuration for a single execution environment."""
    name: str
    image: str
    default_filename: str
    file_extension: str
    run_command: str
    description: str = ""
    enabled: bool = True
    compile_command: Optional[str] = None
    
    def get_full_image_name(self, prefix: str) -> str:
        """Get full Docker image name with prefix."""
        return f"{prefix}-{self.image}"
    
    def get_run_command(self, file_path: str) -> List[str]:
        """
        Get the run command as a list, with placeholders replaced.
        
        Placeholders:
          {file_path} - Full path to the file (e.g., /workspace/main.py)
          {filename} - Just the filename (e.g., main.py)
          {output_path} - Path without extension (e.g., /workspace/main)
        """
        filename = os.path.basename(file_path)
        output_path = file_path.rsplit('.', 1)[0] if '.' in file_path else file_path
        
        cmd = self.run_command.format(
            file_path=file_path,
            filename=filename,
            output_path=output_path
        )
        
        # Parse command into list
        # If starts with "sh -c", keep the rest as single argument
        if cmd.startswith("sh -c "):
            return ["sh", "-c", cmd[6:].strip('"').strip("'")]
        
        return cmd.split()


@dataclass
class Settings:
    """Main settings class."""
    # Redis
    redis_host: str
    redis_port: int
    redis_db: int
    
    # Celery
    celery_broker_url: str
    celery_result_backend: str
    celery_worker_concurrency: int
    
    # Docker
    docker_socket: str
    docker_image_prefix: str
    
    # Execution limits
    container_memory_limit: str
    container_cpu_limit: float
    container_pids_limit: int
    execution_timeout: int
    session_ttl: int
    
    # Security
    network_disabled: bool
    read_only: bool
    no_new_privileges: bool
    tmpfs_size: str
    
    # API
    api_host: str
    api_port: int
    api_debug: bool
    
    # Environments
    environments: Dict[str, EnvironmentConfig] = field(default_factory=dict)
    default_environment: str = "python"
    workspace_dir: str = "/workspace"
    executor_user: str = "executor"
    
    @property
    def environments_list(self) -> List[str]:
        """Get list of enabled environment names."""
        return [name for name, env in self.environments.items() if env.enabled]
    
    def get_environment(self, name: str) -> Optional[EnvironmentConfig]:
        """Get environment config by name."""
        return self.environments.get(name)


def _load_environments() -> tuple[Dict[str, EnvironmentConfig], Dict[str, Any]]:
    """Load environments from YAML file."""
    environments = {}
    defaults = {}
    
    path = _find_environments_file()
    if path is None:
        logger.error("environments.yaml not found")
        return environments, defaults
    
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        env_defs = config.get("environments", {})
        defaults = config.get("defaults", {})
        
        logger.info(f"Found {len(env_defs)} environment definitions")
        
        for env_name, env_data in env_defs.items():
            if isinstance(env_data, dict):
                is_enabled = env_data.get("enabled", True)
                environments[env_name] = EnvironmentConfig(
                    name=env_name,
                    image=env_data.get("image", env_name),
                    default_filename=env_data.get("default_filename", "main.py"),
                    file_extension=env_data.get("file_extension", ".py"),
                    run_command=env_data.get("run_command", "python {file_path}"),
                    description=env_data.get("description", ""),
                    enabled=is_enabled,
                    compile_command=env_data.get("compile_command"),
                )
                logger.debug(f"Loaded environment: {env_name} (enabled={is_enabled})")
    
    except Exception as e:
        logger.error(f"Error loading environments.yaml: {e}")
    
    return environments, defaults


def load_settings() -> Settings:
    """Load all settings from environment variables and environments.yaml."""
    # Load environments from YAML
    environments, env_defaults = _load_environments()
    
    # Build settings from environment variables
    return Settings(
        # Redis
        redis_host=_env("REDIS_HOST", "redis"),
        redis_port=_env_int("REDIS_PORT", 6379),
        redis_db=_env_int("REDIS_DB", 0),
        
        # Celery
        celery_broker_url=_env("CELERY_BROKER_URL", "redis://redis:6379/0"),
        celery_result_backend=_env("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
        celery_worker_concurrency=_env_int("CELERY_WORKER_CONCURRENCY", 4),
        
        # Docker
        docker_socket=_env("DOCKER_SOCKET", "/var/run/docker.sock"),
        docker_image_prefix=_env("DOCKER_IMAGE_PREFIX", "code-executor"),
        
        # Limits
        container_memory_limit=_env("CONTAINER_MEMORY_LIMIT", "256m"),
        container_cpu_limit=_env_float("CONTAINER_CPU_LIMIT", 0.5),
        container_pids_limit=_env_int("CONTAINER_PIDS_LIMIT", 50),
        execution_timeout=_env_int("EXECUTION_TIMEOUT", 30),
        session_ttl=_env_int("SESSION_TTL", 3600),
        
        # Security
        network_disabled=_env_bool("NETWORK_DISABLED", True),
        read_only=_env_bool("READ_ONLY", False),
        no_new_privileges=_env_bool("NO_NEW_PRIVILEGES", True),
        tmpfs_size=_env("TMPFS_SIZE", "64m"),
        
        # API
        api_host=_env("API_HOST", "0.0.0.0"),
        api_port=_env_int("API_PORT", 8000),
        api_debug=_env_bool("API_DEBUG", False),
        
        # Environments
        environments=environments,
        default_environment=env_defaults.get("default_environment", "python"),
        workspace_dir=env_defaults.get("workspace_dir", "/workspace"),
        executor_user=env_defaults.get("executor_user", "executor"),
    )


# Global settings instance
settings = load_settings()

# Log loaded environments
logger.info(f"Config loaded. Enabled environments: {settings.environments_list}")
