"""
Discovery Cache

Caching layer for discovery results to improve performance.
"""

import json
import time
from typing import Optional, List, Any
from threading import Lock
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A cached discovery result."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.expires_at <= 0:
            return False  # No expiration
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
        max_size: int = 1000,
        default_ttl_seconds: int = 300,
        cleanup_interval: int = 60
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self.cleanup_interval = cleanup_interval
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
        }
        self._last_cleanup = time.time()
    
    def _make_key(self, query: str, **filters) -> str:
        """Create a cache key from query and filters."""
        # Sort filters for consistent keys
        filter_str = json.dumps(filters, sort_keys=True)
        return f"{query}:{filter_str}"
    
    def get(self, query: str, **filters) -> Optional[Any]:
        """Get a value from cache."""
        key = self._make_key(query, **filters)
        
        with self._lock:
            self._maybe_cleanup()
            
            entry = self._cache.get(key)
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                self._stats['expirations'] += 1
                return None
            
            entry.touch()
            self._stats['hits'] += 1
            return entry.value
    
    def set(self, query: str, value: Any, ttl_seconds: Optional[int] = None, **filters):
        """Set a value in cache."""
        key = self._make_key(query, **filters)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.time() + ttl if ttl > 0 else 0
        
        with self._lock:
            self._maybe_cleanup()
            
            # Evict if at max size
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at
            )
            self._cache[key] = entry
    
    def invalidate(self, query: str, **filters) -> bool:
        """Invalidate a specific cache entry."""
        key = self._make_key(query, **filters)
        
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all entries matching a pattern."""
        import fnmatch
        
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0,
                'expirations': 0,
            }
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find entry with lowest hit_count (simple LRU approximation)
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
        del self._cache[lru_key]
        self._stats['evictions'] += 1
    
    def _maybe_cleanup(self):
        """Periodically clean up expired entries."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return
        
        self._last_cleanup = now
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
            self._stats['expirations'] += 1
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total if total > 0 else 0.0
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate,
            }
    
    def get_keys(self) -> List[str]:
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
    
    def discover(self, query) -> List[Any]:
        """Discover with caching."""
        # Create cache key from query parameters
        filters = {
            'capability_type': query.capability_type,
            'tags': tuple(query.tags),
            'min_trust_score': query.min_trust_score,
            'max_price': query.max_price,
            'max_latency_ms': query.max_latency_ms,
            'require_verified': query.require_verified,
            'sort_by': query.sort_by.value,
            'sort_order': query.sort_order.value,
            'limit': query.limit,
            'offset': query.offset,
        }
        
        # Try cache first
        cached = self.cache.get(query.query, **filters)
        if cached is not None:
            return cached
        
        # Not in cache, call service
        results = self.service.discover(query)
        
        # Cache results
        self.cache.set(query.query, results, **filters)
        
        return results
    
    def invalidate_agent(self, agent_did: str):
        """Invalidate cache entries for a specific agent."""
        # Simple approach: invalidate all (could be more targeted)
        self.cache.clear()