"""Per-client sliding-window rate limiter. In-memory, so the limit is per process."""

import time
from collections import defaultdict, deque

_MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> float:
        """Record a hit. Returns 0 if allowed, else seconds until a slot frees up."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return self.window - (now - hits[0])
        hits.append(now)
        if len(self._hits) > _MAX_TRACKED_CLIENTS:
            self._prune(now)
        return 0.0

    def _prune(self, now: float) -> None:
        stale = [
            k for k, h in self._hits.items() if not h or now - h[-1] >= self.window
        ]
        for k in stale:
            del self._hits[k]

    def reset(self) -> None:
        self._hits.clear()
