from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.settings import get_settings


@lru_cache(maxsize=1)
def get_redis_connection() -> Redis:
    settings = get_settings()
    # Connection is created lazily so importing the module doesn't require Redis to be reachable.
    return Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_scraper_queue() -> Queue:
    settings = get_settings()
    return Queue(name=settings.scraper_queue_name, connection=get_redis_connection())

