"""
Discovery Module

The "notice board" - a service agents can query to find other agents by capability.
"""

from .models import DiscoveryQuery, DiscoveryResult, RegistryEntry
from .service import DiscoveryService
from .cache import DiscoveryCache

__all__ = [
    "DiscoveryQuery",
    "DiscoveryResult",
    "RegistryEntry",
    "DiscoveryService",
    "DiscoveryCache",
]