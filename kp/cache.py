import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.monotonic() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)


# Module-level singletons
gfz_cache = TTLCache(ttl_seconds=300)   # 5-min TTL for historical data
noaa_cache = TTLCache(ttl_seconds=180)  # 3-min TTL for real-time data
