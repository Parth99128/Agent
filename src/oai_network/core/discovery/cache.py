"""
Discovery Cache

Caching layer for discovery results to improve performance.
"""

import time
from typing import Optional, Any
from threading import Lock
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class CacheEntry:
    """A cached discovery result."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.expires_at <= 0:
            return True  # Immediate expiration
        return time.time() > self.expires_at

    def touch(self):
        """Update access time and hit count."""
        self.hit_count += 1


class DiscoveryCache:
    """
    In-memory cache for discovery results.

    Features:
    - TTL-based expiration
    - LRU eviction when max size reached
    - Thread-safe operations
    - Cache statistics
    """

    def __init__(
        self,
        ttl_seconds: int = 60,
        max_size: int = 100,
    ):
        self.max_size = max_size
        self.default_ttl = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats['misses'] += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set a value in cache."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.time() + ttl if ttl > 0 else 0.0

        with self._lock:
            # Evict if at max size and key is new
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
            )
            self._cache[key] = entry
            self._cache.move_to_end(key)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats = {
                'hits': 0,
                'misses': 0,
            }

    def _evict_lru(self):
        """Evict least recently used entry (first item in OrderedDict)."""
        if self._cache:
            self._cache.popitem(last=False)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
            }

    def get_keys(self) -> list[str]:
        """Get all cache keys (for debugging)."""
        with self._lock:
            return list(self._cache.keys())


class CachedDiscoveryService:
    """
    Wrapper around DiscoveryService that adds caching.
    """

    def __init__(self, discovery_service, cache: Optional[DiscoveryCache] = None):
        self.service = discovery_service
        self.cache = cache or DiscoveryCache()

    async def discover(self, query) -> list[Any]:
        """Discover with caching."""
        import json

        # Create cache key from query parameters
        key = json.dumps(
            {
                'query': query.query,
                'capability_type': query.capability_type,
                'tags': list(query.tags),
                'min_trust_score': query.min_trust_score,
                'max_price': query.max_price,
                'max_latency_ms': query.max_latency_ms,
                'verified_only': query.verified_only,
                'sort_by': query.sort_by.value if query.sort_by else None,
                'sort_order': query.sort_order.value if query.sort_order else None,
                'max_results': query.max_results,
                'offset': query.offset,
            },
            sort_keys=True,
        )

        # Try cache first
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Not in cache, call service
        results = await self.service.discover(query)

        # Cache results
        self.cache.set(key, results)

        return results

    def invalidate_agent(self, agent_did: str):
        """Invalidate cache entries for a specific agent."""
        self.cache.clear()