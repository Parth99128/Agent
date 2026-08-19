"""
Capabilities Module

Defines the agent capability manifest schema - the "phonebook entry" for agents.
This is what agents publish to the registry so others can discover them.
"""

from .models import (
    AgentManifest,
    Capability,
    CapabilityType,
    InputSchema,
    OutputSchema,
    PricingModel,
    ServiceEndpoint,
    TrustMetrics,
)
from .matcher import CapabilityMatcher
from .validator import ManifestValidator

__all__ = [
    "AgentManifest",
    "Capability",
    "CapabilityType",
    "InputSchema",
    "OutputSchema",
    "PricingModel",
    "ServiceEndpoint",
    "TrustMetrics",
    "CapabilityMatcher",
    "ManifestValidator",
]