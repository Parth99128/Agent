"""
Negotiation Module

Handles how two agents agree on how to talk - protocol, format, pricing, etc.
"""

from .models import NegotiationRequest, NegotiationResponse, NegotiationSession, Agreement
from .protocol import NegotiationProtocol
from .strategies import NegotiationStrategy, CooperativeStrategy, CompetitiveStrategy

__all__ = [
    "NegotiationRequest",
    "NegotiationResponse",
    "NegotiationSession",
    "Agreement",
    "NegotiationProtocol",
    "NegotiationStrategy",
    "CooperativeStrategy",
    "CompetitiveStrategy",
]