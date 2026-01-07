from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SessionStatus(str, Enum):
    PENDING = "pending"
    CREATING = "creating"
    READY = "ready"
    EXECUTING = "executing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class CreateSessionRequest(BaseModel):
    environment: str = Field(
        ...,
        description="Execution environment (e.g., 'python', 'python-ml', 'node', 'rust')"
    )


class CreateSessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    environment: str
    message: str


class ExecuteCodeRequest(BaseModel):
    code: str = Field(..., description="Source code to execute")
    filename: Optional[str] = Field(
        None,
        description="Optional filename for the code (e.g., 'main.py')"
    )


class ExecuteCodeResponse(BaseModel):
    session_id: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    status: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: SessionStatus
    environment: str
    container_id: Optional[str] = None
    created_at: Optional[str] = None
    last_execution: Optional[str] = None


class StopSessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

