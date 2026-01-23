from pydantic import BaseModel, Field
from typing import Optional


class ExecuteRequest(BaseModel):
    """Request to execute code"""
    environment: str = Field(
        ...,
        description="Execution environment (e.g., 'python', 'python-ml', 'node', 'rust')"
    )
    code: str = Field(..., description="Source code to execute")
    stdin: Optional[str] = Field(
        None,
        description="Input data to pass to the program via stdin"
    )
    filename: Optional[str] = Field(
        None,
        description="Optional filename for the code (e.g., 'main.py')"
    )


class ExecuteResponse(BaseModel):
    """Response from code execution"""
    environment: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    status: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class EnvironmentResponse(BaseModel):
    name: str
    description: str
    file_extension: str
