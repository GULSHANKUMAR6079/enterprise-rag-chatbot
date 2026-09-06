"""
Sliding Window Rate Limiter.
Supports Redis with seamless in-memory fallback for offline/local environments.
Limits both IP requests and Session requests.
"""
import time
import asyncio
from collections import defaultdict
from typing import Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.exceptions import RateLimitExceededException

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class InMemorySlidingWindow:
    """Thread-safe in-memory sliding window rate limiter fallback."""
    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> Tuple[bool, int]:
        async with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            timestamps = [ts for ts in self._requests[key] if ts > cutoff]
            self._requests[key] = timestamps

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(earliest + window_seconds - now))
                return False, retry_after

            self._requests[key].append(now)
            return True, 0


class RateLimiter:
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.memory_limiter = InMemorySlidingWindow()
        self._redis_connected = False

    async def initialize(self):
        if aioredis and settings.REDIS_URL:
            try:
                self.redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await self.redis_client.ping()
                self._redis_connected = True
            except Exception:
                self._redis_connected = False
                self.redis_client = None

    async def check_rate_limit(self, identifier: str, max_requests: int, window_seconds: int = 60) -> None:
        """
        Enforces rate limiting on the identifier (e.g. 'ip:<hash>' or 'sess:<id>').
        Raises RateLimitExceededException if exceeded.
        """
        key = f"rate_limit:{identifier}"
        allowed = True
        retry_after = 0

        if self._redis_connected and self.redis_client:
            try:
                now = time.time()
                cutoff = now - window_seconds
                pipeline = self.redis_client.pipeline()
                pipeline.zremrangebyscore(key, 0, cutoff)
                pipeline.zcard(key)
                pipeline.zrange(key, 0, 0, withscores=True)
                pipeline.zadd(key, {str(now): now})
                pipeline.expire(key, window_seconds)
                results = await pipeline.execute()

                current_count = results[1]
                if current_count >= max_requests:
                    # Remove the tentatively added element
                    await self.redis_client.zrem(key, str(now))
                    allowed = False
                    earliest_items = results[2]
                    if earliest_items:
                        earliest_ts = float(earliest_items[0][1])
                        retry_after = max(1, int(earliest_ts + window_seconds - now))
                    else:
                        retry_after = window_seconds
            except Exception:
                # Fallback to in-memory on Redis error
                allowed, retry_after = await self.memory_limiter.is_allowed(key, max_requests, window_seconds)
        else:
            allowed, retry_after = await self.memory_limiter.is_allowed(key, max_requests, window_seconds)

        if not allowed:
            raise RateLimitExceededException(retry_after=retry_after)

    async def close(self):
        if self.redis_client:
            await self.redis_client.aclose()


# Singleton rate limiter instance
rate_limiter = RateLimiter()
