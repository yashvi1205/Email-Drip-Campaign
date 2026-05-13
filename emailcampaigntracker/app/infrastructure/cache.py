"""Caching layer for database query optimization

Provides Redis-backed caching with automatic invalidation.
Falls back to in-memory cache if Redis is unavailable.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import timedelta

import redis
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract cache backend interface"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in cache with TTL in seconds"""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        pass

    @abstractmethod
    def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern"""
        pass


class RedisCache(CacheBackend):
    """Redis-backed cache implementation"""

    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.client.ping()
        logger.info("Connected to Redis cache")

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning("Cache get error for %s: %s", key, str(e))
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            self.client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("Cache set error for %s: %s", key, str(e))

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception as e:
            logger.warning("Cache delete error for %s: %s", key, str(e))

    def delete_pattern(self, pattern: str) -> None:
        try:
            for key in self.client.scan_iter(match=pattern):
                self.client.delete(key)
        except Exception as e:
            logger.warning("Cache delete pattern error for %s: %s", pattern, str(e))


class InMemoryCache(CacheBackend):
    """In-memory fallback cache implementation"""

    def __init__(self, max_size: int = 1000):
        self.cache: dict[str, tuple[Any, float]] = {}
        self.max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, expiry = self.cache[key]
            if expiry > 0:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        if len(self.cache) >= self.max_size:
            self.cache.clear()
        import time
        self.cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        if key in self.cache:
            del self.cache[key]

    def delete_pattern(self, pattern: str) -> None:
        import fnmatch
        keys_to_delete = [
            k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)
        ]
        for key in keys_to_delete:
            del self.cache[key]


def get_cache() -> CacheBackend:
    """Get cache backend (Redis or in-memory fallback)"""
    settings = get_settings()

    if settings.redis_url:
        try:
            return RedisCache(settings.redis_url)
        except Exception as e:
            logger.warning("Failed to connect to Redis: %s. Using in-memory cache", str(e))
            return InMemoryCache()
    else:
        return InMemoryCache()


# Global cache instance
_cache: Optional[CacheBackend] = None


def init_cache() -> None:
    """Initialize global cache instance"""
    global _cache
    _cache = get_cache()


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache"""
    if _cache is None:
        init_cache()
    return _cache.get(key)


def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """Set value in cache"""
    if _cache is None:
        init_cache()
    _cache.set(key, value, ttl)


def cache_delete(key: str) -> None:
    """Delete key from cache"""
    if _cache is None:
        init_cache()
    _cache.delete(key)


def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching pattern"""
    if _cache is None:
        init_cache()
    _cache.delete_pattern(pattern)
