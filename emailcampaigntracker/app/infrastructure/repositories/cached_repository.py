"""Cached repository mixin for query optimization

Provides transparent caching for frequently accessed data.
"""

from typing import Any, Optional, Type, TypeVar
from functools import wraps
import logging

from app.infrastructure.cache import (
    cache_get,
    cache_set,
    cache_delete,
    cache_delete_pattern,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching method results

    Args:
        ttl: Time to live in seconds (default: 1 hour)
        key_prefix: Prefix for cache keys
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            args_str = "|".join(str(arg) for arg in args[1:] if arg is not None)
            kwargs_str = "|".join(
                f"{k}={v}" for k, v in sorted(kwargs.items())
            )
            cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"
            cache_key = cache_key.rstrip(":")

            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit: %s", cache_key)
                return cached_value

            # Cache miss - call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache_set(cache_key, result, ttl)
                logger.debug("Cache set: %s", cache_key)

            return result

        return wrapper

    return decorator


class CachedRepositoryMixin:
    """Mixin for repositories with caching support"""

    model: Type[T]
    cache_prefix: str = ""

    def _cache_key(self, suffix: str) -> str:
        """Build cache key for model"""
        prefix = self.cache_prefix or self.model.__name__.lower()
        return f"cache:{prefix}:{suffix}"

    def _invalidate_cache(self, pattern: str = "*") -> None:
        """Invalidate cache entries matching pattern"""
        prefix = self.cache_prefix or self.model.__name__.lower()
        cache_delete_pattern(f"{self._cache_key(pattern)}")

    def get_by_id_cached(self, id: int, ttl: int = 3600) -> Optional[T]:
        """Get entity by ID with caching"""
        cache_key = self._cache_key(f"id:{id}")
        cached = cache_get(cache_key)
        if cached:
            return cached

        result = self.get_by_id(id)
        if result:
            cache_set(cache_key, result, ttl)
        return result

    def list_all_cached(self, ttl: int = 3600) -> list[T]:
        """List all entities with caching"""
        cache_key = self._cache_key("list:all")
        cached = cache_get(cache_key)
        if cached:
            return cached

        result = self.list_all()
        cache_set(cache_key, result, ttl)
        return result
