from redis.asyncio import Redis
from typing import Optional


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
    async def close(cls):
        if cls.redis:
            await cls.redis.close()


redis_client = RedisManager()
