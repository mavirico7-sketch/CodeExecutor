import redis
import json
from typing import Optional, Any, Dict
from datetime import datetime

from app.config import settings


class RedisClient:
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )

    @property
    def client(self) -> redis.Redis:
        return self._client

    # Session Keys
    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _session_status_key(self, session_id: str) -> str:
        return f"session:{session_id}:status"

    def _session_container_key(self, session_id: str) -> str:
        return f"session:{session_id}:container"

    def _session_result_key(self, session_id: str) -> str:
        return f"session:{session_id}:result"

    def _active_sessions_key(self) -> str:
        return "active_sessions"

    # Session Operations
    def create_session(
        self,
        session_id: str,
        environment: str,
        status: str = "pending"
    ) -> None:
        session_data = {
            "session_id": session_id,
            "environment": environment,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
            "last_execution": "",
            "container_id": ""
        }
        self._client.hset(
            self._session_key(session_id),
            mapping=session_data
        )
        self._client.expire(
            self._session_key(session_id),
            settings.session_ttl
        )
        self._client.sadd(self._active_sessions_key(), session_id)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        data = self._client.hgetall(self._session_key(session_id))
        return data if data else None

    def update_session(self, session_id: str, **kwargs) -> None:
        # Filter out None values - Redis doesn't accept them
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        if filtered:
            self._client.hset(self._session_key(session_id), mapping=filtered)
            self._client.expire(
                self._session_key(session_id),
                settings.session_ttl
            )

    def delete_session(self, session_id: str) -> None:
        self._client.delete(self._session_key(session_id))
        self._client.srem(self._active_sessions_key(), session_id)

    def session_exists(self, session_id: str) -> bool:
        return self._client.exists(self._session_key(session_id)) > 0

    # Status Operations
    def set_status(self, session_id: str, status: str) -> None:
        self.update_session(session_id, status=status)

    def get_status(self, session_id: str) -> Optional[str]:
        return self._client.hget(self._session_key(session_id), "status")

    # Container Operations
    def set_container_id(self, session_id: str, container_id: str) -> None:
        self.update_session(session_id, container_id=container_id)

    def get_container_id(self, session_id: str) -> Optional[str]:
        return self._client.hget(self._session_key(session_id), "container_id")

    # Execution Result Operations
    def set_execution_result(
        self,
        session_id: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        execution_time: float
    ) -> None:
        result = {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time": execution_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._client.set(
            self._session_result_key(session_id),
            json.dumps(result),
            ex=settings.session_ttl
        )
        self.update_session(
            session_id,
            last_execution=datetime.utcnow().isoformat()
        )

    def get_execution_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        result = self._client.get(self._session_result_key(session_id))
        return json.loads(result) if result else None

    # Active Sessions
    def get_active_sessions(self) -> set:
        return self._client.smembers(self._active_sessions_key())

    def cleanup_inactive_sessions(self) -> list:
        """Remove sessions from active set if they no longer exist"""
        active = self.get_active_sessions()
        cleaned = []
        for session_id in active:
            if not self.session_exists(session_id):
                self._client.srem(self._active_sessions_key(), session_id)
                cleaned.append(session_id)
        return cleaned


redis_client = RedisClient()

