from fastapi import APIRouter, HTTPException, status
from typing import List
from celery import Celery

from app.api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    ExecuteCodeRequest,
    ExecuteCodeResponse,
    SessionStatusResponse,
    StopSessionResponse,
    SessionStatus,
)
from app.core.session import session_manager
from app.config import settings


router = APIRouter(prefix="/api/v1", tags=["Code Execution"])

# Create Celery app for sending tasks (without importing tasks module)
celery_app = Celery(
    "code_executor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@router.get("/environments", response_model=List[str])
async def list_environments():
    """
    Get list of available execution environments
    """
    return settings.environments_list


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new code execution session
    
    Creates a session and starts a Docker container for code execution.
    The session will be ready for code execution once the container is running.
    """
    # Validate environment
    if request.environment not in settings.environments_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid environment: {request.environment}. "
                   f"Available: {settings.environments_list}"
        )

    try:
        # Create session
        session_id = session_manager.create_session(request.environment)

        # Start container asynchronously via send_task
        celery_app.send_task(
            "app.worker.tasks.start_session",
            args=[session_id, request.environment]
        )

        return CreateSessionResponse(
            session_id=session_id,
            status=SessionStatus.PENDING,
            environment=request.environment,
            message="Session created. Container is starting..."
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """
    Get the status of a session
    
    Returns current status, environment, and container information.
    """
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return SessionStatusResponse(
        session_id=session_id,
        status=SessionStatus(session.get("status", "pending")),
        environment=session.get("environment", ""),
        container_id=session.get("container_id"),
        created_at=session.get("created_at"),
        last_execution=session.get("last_execution"),
    )


@router.post("/sessions/{session_id}/execute", response_model=ExecuteCodeResponse)
async def execute_code_endpoint(session_id: str, request: ExecuteCodeRequest):
    """
    Execute code in a session
    
    Submits code for execution and waits for the result.
    The session must be in 'ready' status to execute code.
    """
    # Check session exists
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    # Check session is ready
    current_status = session.get("status")
    if current_status not in (SessionStatus.READY.value, SessionStatus.EXECUTING.value):
        if current_status == SessionStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session container is still starting. Please wait and retry."
            )
        elif current_status == SessionStatus.CREATING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session container is being created. Please wait and retry."
            )
        elif current_status in (SessionStatus.STOPPED.value, SessionStatus.STOPPING.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session has been stopped."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session is not ready for execution. Status: {current_status}"
            )

    try:
        # Execute code synchronously (wait for result)
        result = celery_app.send_task(
            "app.worker.tasks.execute_code",
            args=[session_id, request.code, request.filename, request.stdin]
        ).get(timeout=settings.execution_timeout + 10)

        if not result.get("success", False):
            return ExecuteCodeResponse(
                session_id=session_id,
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", result.get("error", "Execution failed")),
                exit_code=result.get("exit_code", -1),
                execution_time=result.get("execution_time", 0),
                status="error"
            )

        return ExecuteCodeResponse(
            session_id=session_id,
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


@router.delete("/sessions/{session_id}", response_model=StopSessionResponse)
async def delete_session(session_id: str):
    """
    Stop and delete a session
    
    Stops the container and removes the session.
    """
    # Check session exists
    if not session_manager.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    try:
        # Stop session asynchronously
        celery_app.send_task(
            "app.worker.tasks.stop_session",
            args=[session_id]
        )

        return StopSessionResponse(
            session_id=session_id,
            status=SessionStatus.STOPPING,
            message="Session is being stopped..."
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop session: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "service": "code-executor"}
