"""
Agent Identity Module

Handles agent identity verification using public-key cryptography.
Each agent has a unique identity that can be cryptographically verified.
"""

from .models import AgentIdentity, IdentityProof
from .verifier import IdentityVerifier
from .generator import IdentityGenerator

__all__ = [
    "AgentIdentity",
    "IdentityProof",
    "IdentityVerifier",
    "IdentityGenerator",
]