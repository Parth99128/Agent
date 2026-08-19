"""
Policy Engine

Evaluates policies against requests to make allow/deny decisions.
"""

from typing import Optional, List, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from .models import Policy, PolicyRule, PolicyEffect, PolicyCondition, Budget, BudgetPeriod


class PolicyDecision(BaseModel):
    """Result of a policy evaluation."""
    allowed: bool
    matched_rules: List[PolicyRule] = Field(default_factory=list)
    denied_rules: List[PolicyRule] = Field(default_factory=list)
    budget_exceeded: List[Budget] = Field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEngine:
    """
    Evaluates policies for authorization decisions.
    
    Features:
    - Rule-based evaluation with priorities
    - Budget tracking and enforcement
    - Default deny/allow behavior
    - Detailed decision explanations
    """
    
    def __init__(self, policy: Policy):
        self.policy = policy
    
    def evaluate(
        self, 
        context: dict[str, Any],
        check_budgets: bool = True
    ) -> PolicyDecision:
        """
        Evaluate a request against the policy.
        
        Args:
            context: Request context with all relevant attributes
            check_budgets: Whether to check budget limits
            
        Returns:
            PolicyDecision with allow/deny and details
        """
        if not self.policy.enabled:
            return PolicyDecision(
                allowed=True,
                reason="Policy is disabled",
                metadata={"policy_enabled": False}
            )
        
        matched_rules = []
        denied_rules = []
        
        # Evaluate rules in priority order
        for rule in self.policy.rules:
            if rule.matches(context):
                matched_rules.append(rule)
                if rule.effect == PolicyEffect.DENY:
                    denied_rules.append(rule)
                    return PolicyDecision(
                        allowed=False,
                        matched_rules=matched_rules,
                        denied_rules=denied_rules,
                        reason=f"Denied by rule: {rule.name}",
                        metadata={"matched_rule_id": rule.id}
                    )
                elif rule.effect == PolicyEffect.ALLOW:
                    # Allow but continue checking for explicit denies
                    pass
        
        # Check budgets if enabled
        budget_exceeded = []
        if check_budgets:
            budget_exceeded = self._check_budgets(context)
            if budget_exceeded:
                return PolicyDecision(
                    allowed=False,
                    matched_rules=matched_rules,
                    denied_rules=denied_rules,
                    budget_exceeded=budget_exceeded,
                    reason=f"Budget exceeded: {', '.join(b.name for b in budget_exceeded)}",
                    metadata={"budget_ids": [b.id for b in budget_exceeded]}
                )
        
        # If we have explicit allows, permit
        if any(r.effect == PolicyEffect.ALLOW for r in matched_rules):
            return PolicyDecision(
                allowed=True,
                matched_rules=matched_rules,
                denied_rules=denied_rules,
                budget_exceeded=budget_exceeded,
                reason="Allowed by policy rules",
            )
        
        # Default effect
        return PolicyDecision(
            allowed=self.policy.default_effect == PolicyEffect.ALLOW,
            matched_rules=matched_rules,
            denied_rules=denied_rules,
            budget_exceeded=budget_exceeded,
            reason=f"Default effect: {self.policy.default_effect.value}",
        )
    
    def _check_budgets(self, context: dict[str, Any]) -> List[Budget]:
        """Check if any budgets are exceeded."""
        exceeded = []
        
        for budget in self.policy.budgets:
            if not budget.enabled:
                continue
            
            # Check if budget applies to this request
            if not self._budget_applies(budget, context):
                continue
            
            # Reset if period elapsed
            budget.reset_if_needed()
            
            # Check if exceeded
            is_exceeded, reasons = budget.is_exceeded()
            if is_exceeded:
                exceeded.append(budget)
        
        return exceeded
    
    def _budget_applies(self, budget: Budget, context: dict[str, Any]) -> bool:
        """Check if a budget applies to the current request."""
        if budget.agent_did and context.get('agent_did') != budget.agent_did:
            return False
        
        if budget.requester_did and context.get('requester_did') != budget.requester_did:
            return False
        
        if budget.capability_name and context.get('capability_name') != budget.capability_name:
            return False
        
        return True
    
    def consume_budget(
        self, 
        context: dict[str, Any],
        calls: int = 1,
        cost: float = 0.0,
        tokens: int = 0,
        latency_ms: int = 0
    ) -> List[Budget]:
        """Consume budget for a request."""
        consumed = []
        
        for budget in self.policy.budgets:
            if not budget.enabled:
                continue
            
            if not self._budget_applies(budget, context):
                continue
            
            budget.consume(calls, cost, tokens, latency_ms)
            consumed.append(budget)
        
        return consumed
    
    def get_applicable_budgets(self, context: dict[str, Any]) -> List[Budget]:
        """Get all budgets that apply to a context."""
        return [
            b for b in self.policy.budgets
            if b.enabled and self._budget_applies(b, context)
        ]
    
    def explain_decision(self, decision: PolicyDecision) -> str:
        """Generate human-readable explanation of a decision."""
        lines = []
        
        if decision.allowed:
            lines.append("✓ ALLOWED")
        else:
            lines.append("✗ DENIED")
        
        lines.append(f"Reason: {decision.reason}")
        
        if decision.matched_rules:
            lines.append("\nMatched Rules:")
            for rule in decision.matched_rules:
                lines.append(f"  - {rule.name} ({rule.effect.value})")
                if rule.description:
                    lines.append(f"    {rule.description}")
        
        if decision.denied_rules:
            lines.append("\nDenying Rules:")
            for rule in decision.denied_rules:
                lines.append(f"  - {rule.name}")
                for cond in rule.conditions:
                    lines.append(f"    {cond.type.value} {cond.operator.value} {cond.value}")
        
        if decision.budget_exceeded:
            lines.append("\nExceeded Budgets:")
            for budget in decision.budget_exceeded:
                lines.append(f"  - {budget.name} ({budget.period.value})")
                is_exceeded, reasons = budget.is_exceeded()
                for reason in reasons:
                    lines.append(f"    {reason}")
        
        return "\n".join(lines)


# Add PolicyDecision model
from pydantic import BaseModel, Field
from typing import List, Any

class PolicyDecision(BaseModel):
    """Result of a policy evaluation."""
    allowed: bool
    matched_rules: List[PolicyRule] = Field(default_factory=list)
    denied_rules: List[PolicyRule] = Field(default_factory=list)
    budget_exceeded: List[Budget] = Field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)