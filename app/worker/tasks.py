from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.worker.docker_executor import docker_executor


@celery_app.task(bind=True, name="app.worker.tasks.execute_code")
def execute_code(
    self,
    environment: str,
    code: str,
    filename: str = None,
    stdin_data: str = None
) -> Dict[str, Any]:
    """
    Execute code in a temporary container.
    
    Creates container -> executes code -> removes container.
    """
    container_id = None
    
    try:
        # Create container
        container_id = docker_executor.create_container(
            session_id=None,  # No session needed
            environment=environment
        )

        # Execute code
        result = docker_executor.execute_code(
            container_id=container_id,
            code=code,
            environment=environment,
            filename=filename,
            stdin_data=stdin_data
        )

        return {
            "success": True,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "execution_time": result["execution_time"],
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "execution_time": 0,
        }
    
    finally:
        # Always cleanup container
        if container_id:
            try:
                docker_executor.stop_container(container_id)
            except Exception:
                pass


@celery_app.task(name="app.worker.tasks.cleanup_orphaned_containers")
def cleanup_orphaned_containers() -> Dict[str, Any]:
    """
    Periodic task to cleanup any orphaned containers
    """
    try:
        orphaned = docker_executor.cleanup_orphaned_containers()
        return {
            "success": True,
            "cleaned_containers": orphaned,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
