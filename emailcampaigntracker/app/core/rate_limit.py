import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class _Window:
    window_start: float
    count: int


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, _Window] = {}

    def check(self, key: str, limit_per_minute: int) -> None:
        now = time.monotonic()
        window = int(now // 60)
        window_start = float(window * 60)

        with self._lock:
            cur = self._state.get(key)
            if cur is None or cur.window_start != window_start:
                cur = _Window(window_start=window_start, count=0)
                self._state[key] = cur

            cur.count += 1
            if cur.count > limit_per_minute:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")


_limiter = FixedWindowRateLimiter()


def rate_limit(group: str, limit_per_minute: int):
    async def _dependency(request: Request) -> None:
        ip = getattr(request.client, "host", None) or "unknown"
        key = f"{group}:{ip}"
        _limiter.check(key, limit_per_minute)

    return _dependency

