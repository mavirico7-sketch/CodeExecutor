from fastapi import APIRouter, HTTPException, status
from typing import List
from celery import Celery

from app.api.schemas import (
    EnvironmentResponse,
    ExecuteRequest,
    ExecuteResponse,
)
from app.config import settings


router = APIRouter(prefix="/api/v1", tags=["Code Execution"])

# Create Celery app for sending tasks (without importing tasks module)
celery_app = Celery(
    "code_executor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@router.get("/environments", response_model=List[EnvironmentResponse])
async def list_environments():
    """
    Get list of available execution environments
    """
    return settings.environments_data


@router.post("/execute", response_model=ExecuteResponse)
async def execute_code(request: ExecuteRequest):
    """
    Execute code in a temporary container.
    
    Creates a new container, executes the code, and removes the container.
    Each request is completely isolated.
    """
    # Validate environment
    if request.environment not in settings.environments_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid environment: {request.environment}. "
                   f"Available: {settings.environments_list}"
        )

    try:
        # Execute code (creates container, runs code, removes container)
        result = celery_app.send_task(
            "app.worker.tasks.execute_code",
            args=[request.environment, request.code, request.filename, request.stdin]
        ).get(timeout=settings.execution_timeout + 30)

        if not result.get("success", False):
            return ExecuteResponse(
                environment=request.environment,
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", result.get("error", "Execution failed")),
                exit_code=result.get("exit_code", -1),
                execution_time=result.get("execution_time", 0),
                status="error"
            )

        return ExecuteResponse(
            environment=request.environment,
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            exit_code=result.get("exit_code", 0),
            execution_time=result.get("execution_time", 0),
            status="completed"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "service": "code-executor"}
