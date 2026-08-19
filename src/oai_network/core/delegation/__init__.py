"""
Delegation Module

Handles how one agent hands work to another agent.
"""

from .models import DelegationRequest, DelegationResponse, DelegationTask, DelegationResult
from .manager import DelegationManager
from .policy import DelegationPolicy

__all__ = [
    "DelegationRequest",
    "DelegationResponse",
    "DelegationTask",
    "DelegationResult",
    "DelegationManager",
    "DelegationPolicy",
]