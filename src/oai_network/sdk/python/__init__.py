"""
OAI Network Python SDK

Client library for interacting with the OAI Network.
"""

from .client import OAIClient
from ...core.identity.models import AgentIdentity, IdentityDocument
from ...core.capabilities.models import AgentManifest, Capability, ServiceEndpoint
from ...core.discovery.models import DiscoveryQuery, DiscoveryResult, RegistryEntry
from ...core.delegation.models import DelegationRequest, DelegationResponse, DelegationTask, DelegationResult
from ...core.trust.models import TrustScore, TrustEvent
from ...core.negotiation.models import NegotiationSession, NegotiationRequest, NegotiationResponse

__version__ = "0.1.0"

__all__ = [
    "OAIClient",
    "AgentIdentity",
    "AgentManifest",
    "Capability",
    "DiscoveryQuery",
    "DiscoveryResult",
    "DelegationRequest",
    "DelegationResult",
    "TrustScore",
    "NegotiationSession",
]