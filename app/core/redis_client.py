"""
Redis client - Used by Celery for result backend.

This module provides a simple Redis client that can be used
for any future caching needs. Currently mainly used by Celery.
"""

import redis
from typing import Optional

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

    def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            return self._client.ping()
        except Exception:
            return False


redis_client = RedisClient()
