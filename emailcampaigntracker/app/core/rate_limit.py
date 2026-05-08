import time
import logging
from fastapi import HTTPException, Request
from app.queue.redis_queue import get_redis_connection

logger = logging.getLogger("app.rate_limit")

class RedisRateLimiter:
    def __init__(self) -> None:
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            self._redis = get_redis_connection()
        return self._redis

    def check(self, key: str, limit_per_minute: int) -> None:
        redis = self._get_redis()
        current_minute = int(time.time() / 60)
        redis_key = f"rl:{key}:{current_minute}"
        
        try:
            # INCR returns the value after incrementing
            count = redis.incr(redis_key)
            if count == 1:
                # First request in this window, set expiry
                redis.expire(redis_key, 60)
            
            if count > limit_per_minute:
                logger.warning("Rate limit exceeded for %s: %d/%d", key, count, limit_per_minute)
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
        except HTTPException:
            raise
        except Exception as e:
            # Fail open if Redis is down, but log it
            logger.error("Rate limiter Redis failure: %s", e)

_limiter = RedisRateLimiter()

def rate_limit(group: str, limit_per_minute: int):
    async def _dependency(request: Request) -> None:
        # Prefer X-Forwarded-For if behind a proxy
        ip = request.headers.get("x-forwarded-for")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = getattr(request.client, "host", None) or "unknown"
            
        key = f"{group}:{ip}"
        _limiter.check(key, limit_per_minute)

    return _dependency

