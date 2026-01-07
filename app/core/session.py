import uuid
from typing import Optional, Dict, Any

from app.core.redis_client import redis_client
from app.api.schemas import SessionStatus
from app.config import settings


class SessionManager:
    def __init__(self):
        self.redis = redis_client

    def create_session(self, environment: str) -> str:
        """Create a new session and return session_id"""
        if environment not in settings.environments_list:
            raise ValueError(
                f"Invalid environment: {environment}. "
                f"Available: {settings.environments_list}"
            )

        session_id = str(uuid.uuid4())
        self.redis.create_session(
            session_id=session_id,
            environment=environment,
            status=SessionStatus.PENDING.value
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.redis.get_session(session_id)

    def get_status(self, session_id: str) -> Optional[SessionStatus]:
        """Get session status"""
        status = self.redis.get_status(session_id)
        return SessionStatus(status) if status else None

    def set_status(self, session_id: str, status: SessionStatus) -> None:
        """Update session status"""
        self.redis.set_status(session_id, status.value)

    def set_container_id(self, session_id: str, container_id: str) -> None:
        """Associate container with session"""
        self.redis.set_container_id(session_id, container_id)

    def get_container_id(self, session_id: str) -> Optional[str]:
        """Get container ID for session"""
        return self.redis.get_container_id(session_id)

    def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        return self.redis.session_exists(session_id)

    def delete_session(self, session_id: str) -> None:
        """Delete session"""
        self.redis.delete_session(session_id)

    def save_execution_result(
        self,
        session_id: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        execution_time: float
    ) -> None:
        """Save code execution result"""
        self.redis.set_execution_result(
            session_id=session_id,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time=execution_time
        )

    def get_execution_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get last execution result"""
        return self.redis.get_execution_result(session_id)

    def get_active_sessions(self) -> set:
        """Get all active session IDs"""
        return self.redis.get_active_sessions()


session_manager = SessionManager()

