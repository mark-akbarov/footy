from redis.asyncio import Redis
from typing import Optional, Any
import json


class RedisManager:
    redis: Optional[Redis] = None

    @classmethod
    def set_client(cls, redis: Redis):
        cls.redis = redis

    @classmethod
    def get_client(cls) -> Redis:
        if cls.redis is None:
            raise RuntimeError("Redis client not initialized!")
        return cls.redis

    @classmethod
    async def set(cls, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set key to hold a value with optional expiration"""
        client = cls.get_client()
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return await client.set(key, value, ex=ex)

    @classmethod
    async def get(cls, key: str) -> Any:
        """Get value by key"""
        client = cls.get_client()
        value = await client.get(key)
        try:
            return json.loads(value) if value else None
        except (TypeError, json.JSONDecodeError):
            return value

    @classmethod
    async def delete(cls, key: str) -> int:
        """Delete key"""
        client = cls.get_client()
        return await client.delete(key)

    @classmethod
    async def close(cls):
        """Close Redis connection"""
        if cls.redis:
            await cls.redis.close()
