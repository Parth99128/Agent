"""
Negotiation Module

Handles how two agents agree on how to talk - protocol, format, pricing, etc.
"""

from .models import NegotiationRequest, NegotiationResponse, NegotiationSession, NegotiationAgreement, NegotiationTemplate, NegotiationRound
from .protocol import NegotiationProtocol
from .strategies import NegotiationStrategy, CooperativeStrategy, CompetitiveStrategy, BalancedStrategy

__all__ = [
    "NegotiationRequest",
    "NegotiationResponse",
    "NegotiationSession",
    "NegotiationAgreement",
    "NegotiationTemplate",
    "NegotiationRound",
    "NegotiationProtocol",
    "NegotiationStrategy",
    "CooperativeStrategy",
    "CompetitiveStrategy",
    "BalancedStrategy",
]