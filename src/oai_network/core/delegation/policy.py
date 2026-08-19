"""
Delegation Policy Engine

Enforces delegation policies and rules.
"""

from typing import Optional, Any
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
    
    def evaluate_request(
        self, 
        request: DelegationRequest,
        chain: Optional[DelegationChain] = None,
        trust_score: float = 0.5,
        verified: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate a delegation request against policy.
        
        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        # Check delegation depth
        current_depth = chain.current_depth if chain else 0
        if current_depth >= self.policy.max_depth:
            return False, f"Maximum delegation depth {self.policy.max_depth} reached"
        
        # Check delegatee
        allowed, reason = self.policy.can_delegate_to(
            request.delegatee_did, trust_score, verified
        )
        if not allowed:
            return False, reason
        
        # Check capability
        allowed, reason = self.policy.can_delegate_capability(request.capability_name)
        if not allowed:
            return False, reason
        
        # Check timeout
        if request.timeout_seconds > self.policy.max_timeout_seconds:
            return False, f"Timeout {request.timeout_seconds}s exceeds maximum {self.policy.max_timeout_seconds}s"
        
        # Check cost if specified
        if self.policy.max_cost_per_delegation and request.metadata.get('estimated_cost'):
            if request.metadata['estimated_cost'] > self.policy.max_cost_per_delegation:
                return False, f"Estimated cost exceeds maximum per delegation"
        
        # Check approval requirement
        if current_depth >= self.policy.require_approval_above_cost:
            if not request.requires_approval:
                return False, f"Approval required for delegation depth > {self.policy.require_approval_above_cost}"
        
        return True, None
    
    def evaluate_chain(self, chain: DelegationChain) -> tuple[bool, Optional[str]]:
        """Evaluate an entire delegation chain."""
        if chain.current_depth > chain.max_depth:
            return False, "Chain exceeds maximum depth"
        
        # Check for cycles
        delegatees = [task.request.delegatee_did for task in chain.tasks]
        if len(delegatees) != len(set(delegatees)):
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