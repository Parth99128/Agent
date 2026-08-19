"""
A2A Protocol Adapter

Implements the Agent-to-Agent (A2A) protocol for inter-agent communication.
"""

from .models import A2AMessage, A2ARequest, A2AResponse, A2AError, A2AMessageType, A2AErrorCode, AgentCard, CapabilityQuery, CapabilityResponse
from .client import A2AClient
from .server import A2AServer

__all__ = [
    "A2AMessage",
    "A2ARequest",
    "A2AResponse",
    "A2AError",
    "A2AMessageType",
    "A2AErrorCode",
    "AgentCard",
    "CapabilityQuery",
    "CapabilityResponse",
    "A2AClient",
    "A2AServer",
]