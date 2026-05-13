"""Performance monitoring and optimization utilities

Tracks slow queries, response times, and resource usage.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log performance metrics"""

    SLOW_QUERY_THRESHOLD_MS = 1000
    SLOW_ENDPOINT_THRESHOLD_MS = 5000

    @staticmethod
    def track_query(threshold_ms: int = SLOW_QUERY_THRESHOLD_MS):
        """Decorator to track database query performance"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                if duration_ms > threshold_ms:
                    logger.warning(
                        "Slow query: %s took %.2f ms",
                        func.__name__,
                        duration_ms,
                    )

                return result

            return wrapper

        return decorator

    @staticmethod
    def track_endpoint(threshold_ms: int = SLOW_ENDPOINT_THRESHOLD_MS):
        """Decorator to track API endpoint performance"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                if duration_ms > threshold_ms:
                    logger.warning(
                        "Slow endpoint: %s took %.2f ms",
                        func.__name__,
                        duration_ms,
                    )

                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                if duration_ms > threshold_ms:
                    logger.warning(
                        "Slow endpoint: %s took %.2f ms",
                        func.__name__,
                        duration_ms,
                    )

                return result

            # Return appropriate wrapper based on function type
            if hasattr(func, "__await__"):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator


def measure_time(operation_name: str):
    """Context manager for measuring operation time"""

    class TimerContext:
        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration_ms = (time.time() - self.start_time) * 1000
            logger.info("%s took %.2f ms", operation_name, duration_ms)

        @property
        def elapsed_ms(self) -> float:
            return (time.time() - self.start_time) * 1000

    return TimerContext()


class CacheStats:
    """Track cache hit/miss statistics"""

    def __init__(self):
        self.hits = 0
        self.misses = 0

    def hit(self):
        self.hits += 1

    def miss(self):
        self.misses += 1

    def get_hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

    def __str__(self):
        return f"Cache: {self.hits} hits, {self.misses} misses ({self.get_hit_rate():.1f}% hit rate)"


# Global cache stats
_cache_stats = CacheStats()


def record_cache_hit():
    """Record a cache hit"""
    _cache_stats.hit()


def record_cache_miss():
    """Record a cache miss"""
    _cache_stats.miss()


def get_cache_stats() -> CacheStats:
    """Get cache statistics"""
    return _cache_stats
