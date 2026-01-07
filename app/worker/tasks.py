import time
from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.worker.docker_executor import docker_executor
from app.core.session import session_manager
from app.core.redis_client import redis_client
from app.api.schemas import SessionStatus


@celery_app.task(bind=True, name="app.worker.tasks.start_session")
def start_session(self, session_id: str, environment: str) -> Dict[str, Any]:
    """
    Create and start a Docker container for the session
    """
    try:
        # Update status to creating
        session_manager.set_status(session_id, SessionStatus.CREATING)

        # Create container
        container_id = docker_executor.create_container(session_id, environment)

        # Update session with container ID
        session_manager.set_container_id(session_id, container_id)
        session_manager.set_status(session_id, SessionStatus.READY)

        return {
            "success": True,
            "session_id": session_id,
            "container_id": container_id,
            "status": SessionStatus.READY.value,
        }

    except Exception as e:
        session_manager.set_status(session_id, SessionStatus.ERROR)
        redis_client.update_session(session_id, error=str(e))
        return {
            "success": False,
            "session_id": session_id,
            "error": str(e),
            "status": SessionStatus.ERROR.value,
        }


@celery_app.task(bind=True, name="app.worker.tasks.execute_code")
def execute_code(
    self,
    session_id: str,
    code: str,
    filename: str = None,
    stdin_data: str = None
) -> Dict[str, Any]:
    """
    Execute code in the session's container with optional stdin input
    """
    try:
        # Get session info
        session = session_manager.get_session(session_id)
        if not session:
            return {
                "success": False,
                "session_id": session_id,
                "error": "Session not found",
                "stdout": "",
                "stderr": "Session not found",
                "exit_code": -1,
                "execution_time": 0,
            }

        container_id = session.get("container_id")
        environment = session.get("environment")

        if not container_id:
            return {
                "success": False,
                "session_id": session_id,
                "error": "Container not found for session",
                "stdout": "",
                "stderr": "Container not found",
                "exit_code": -1,
                "execution_time": 0,
            }

        # Update status to executing
        session_manager.set_status(session_id, SessionStatus.EXECUTING)

        # Execute code
        result = docker_executor.execute_code(
            container_id=container_id,
            code=code,
            environment=environment,
            filename=filename,
            stdin_data=stdin_data
        )

        # Save result and update status
        session_manager.save_execution_result(
            session_id=session_id,
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            execution_time=result["execution_time"]
        )
        session_manager.set_status(session_id, SessionStatus.READY)

        return {
            "success": True,
            "session_id": session_id,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "execution_time": result["execution_time"],
        }

    except Exception as e:
        session_manager.set_status(session_id, SessionStatus.ERROR)
        return {
            "success": False,
            "session_id": session_id,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "execution_time": 0,
        }


@celery_app.task(bind=True, name="app.worker.tasks.stop_session")
def stop_session(self, session_id: str) -> Dict[str, Any]:
    """
    Stop and cleanup a session's container
    """
    try:
        # Get container ID
        container_id = session_manager.get_container_id(session_id)

        # Update status
        session_manager.set_status(session_id, SessionStatus.STOPPING)

        # Stop container if exists
        if container_id:
            docker_executor.stop_container(container_id)

        # Update status and cleanup
        session_manager.set_status(session_id, SessionStatus.STOPPED)

        return {
            "success": True,
            "session_id": session_id,
            "status": SessionStatus.STOPPED.value,
        }

    except Exception as e:
        return {
            "success": False,
            "session_id": session_id,
            "error": str(e),
        }


@celery_app.task(name="app.worker.tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> Dict[str, Any]:
    """
    Periodic task to cleanup expired sessions and orphaned containers
    """
    cleaned_sessions = []
    cleaned_containers = []

    try:
        # Cleanup inactive sessions from Redis
        cleaned_sessions = redis_client.cleanup_inactive_sessions()

        # Get all containers with our label
        containers = docker_executor.client.containers.list(
            filters={"label": "code-executor=true"}
        )

        # Check each container
        for container in containers:
            session_id = container.labels.get("session_id")
            if session_id:
                # If session doesn't exist in Redis, remove container
                if not session_manager.session_exists(session_id):
                    try:
                        docker_executor.stop_container(container.id)
                        cleaned_containers.append(container.id)
                    except Exception:
                        pass

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "cleaned_sessions": cleaned_sessions,
            "cleaned_containers": cleaned_containers,
        }

    return {
        "success": True,
        "cleaned_sessions": cleaned_sessions,
        "cleaned_containers": cleaned_containers,
    }


@celery_app.task(name="app.worker.tasks.force_cleanup_all")
def force_cleanup_all() -> Dict[str, Any]:
    """
    Force cleanup all sessions and containers (for maintenance)
    """
    try:
        # Get all active sessions
        active_sessions = session_manager.get_active_sessions()

        # Stop all containers
        for session_id in active_sessions:
            container_id = session_manager.get_container_id(session_id)
            if container_id:
                docker_executor.stop_container(container_id)
            session_manager.delete_session(session_id)

        # Cleanup any orphaned containers
        orphaned = docker_executor.cleanup_orphaned_containers()

        return {
            "success": True,
            "cleaned_sessions": list(active_sessions),
            "orphaned_containers": orphaned,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

