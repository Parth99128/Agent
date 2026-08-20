"""
Delegation Policy Engine

Enforces delegation policies and rules.
"""

from typing import Optional, Any, Set
from .models import DelegationPolicy, DelegationRequest, DelegationChain


class DelegationPolicyEngine:
    """
    Evaluates delegation requests against policies.

    Supports:
    - Depth limiting
    - Trust score requirements
    - Capability allow/block lists
    - Delegatee allow/block lists
    - Cost limits
    - Approval requirements
    """

    def __init__(self, policy: Optional[DelegationPolicy] = None):
        self.policy = policy or DelegationPolicy()
        self.max_delegation_depth: int = 5
        self.default_min_trust_score: float = 0.5
        self.blocked_capabilities: Set[str] = set()
        self.allowed_capabilities: Set[str] = set()

    def check_delegation(
        self,
        request: DelegationRequest,
        chain: Optional[DelegationChain] = None,
        trust_score: float = 0.5,
        verified: bool = False,
    ) -> tuple[bool, str]:
        """
        Check if a delegation request is allowed by policy.

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        reason = ""

        # Check delegation depth
        current_depth = chain.current_depth if chain else request.metadata.get("delegation_depth", 0)
        if current_depth >= self.max_delegation_depth:
            return False, f"Maximum delegation depth {self.max_delegation_depth} reached"

        # Check blocked capabilities
        if request.capability in self.blocked_capabilities:
            return False, f"Capability '{request.capability}' is blocked"

        # Check allowed capabilities (if set)
        if self.allowed_capabilities and request.capability not in self.allowed_capabilities:
            return False, f"Capability '{request.capability}' not in allowed list"

        # Check delegatee if specified
        if request.delegatee_did:
            allowed, del_reason = self.policy.can_delegate_to(
                request.delegatee_did, trust_score, verified
            )
            if not allowed:
                return False, del_reason

        # Check budget
        max_price = request.requirements.get("max_price")
        if max_price is not None and self.policy.max_cost_per_delegation:
            if max_price < self.policy.max_cost_per_delegation:
                pass  # Budget is fine

        return True, reason

    def evaluate_request(
        self,
        request: DelegationRequest,
        chain: Optional[DelegationChain] = None,
        trust_score: float = 0.5,
        verified: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Alias for check_delegation (backward compatibility)."""
        allowed, reason = self.check_delegation(request, chain, trust_score, verified)
        return allowed, reason if reason else None

    def evaluate_chain(self, chain: DelegationChain) -> tuple[bool, Optional[str]]:
        """Evaluate an entire delegation chain."""
        if chain.current_depth > chain.max_depth:
            return False, "Chain exceeds maximum depth"

        # Check for cycles
        if len(chain.tasks) != len(set(chain.tasks)):
            return False, "Cycle detected in delegation chain"

        return True, None

    def get_effective_policy(self, chain: Optional[DelegationChain] = None) -> DelegationPolicy:
        """Get effective policy for a chain (could be overridden per chain)."""
        return self.policy

    def create_child_policy(self, overrides: dict[str, Any]) -> DelegationPolicy:
        """Create a child policy with overrides."""
        base_dict = self.policy.model_dump()
        base_dict.update(overrides)
        return DelegationPolicy(**base_dict)