"""
Policy Engine

Evaluates policies against requests to make allow/deny decisions.
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field
from .models import Policy, PolicyRule, PolicyEffect, PolicyCondition, Budget, BudgetPeriod
from oai_network.core.observability import (
    get_logger, log_policy_check, get_trace_id
)


class PolicyDecision(BaseModel):
    """Result of a policy evaluation."""
    allowed: bool
    matched_rule_id: Optional[str] = None
    reason: str = ""
    explanation: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEngine:
    """
    Evaluates policies for authorization decisions.

    Features:
    - Rule-based evaluation (first match wins)
    - Budget tracking and enforcement
    - Default deny behavior
    - Detailed decision explanations
    """

    def __init__(self, policy: Optional[Policy] = None):
        self.policy = policy
        self.logger = get_logger("oai-network-policy-engine")

    def evaluate(self, policy: Policy, context: dict[str, Any]) -> PolicyDecision:
        """
        Evaluate a request against the policy.

        First matching rule wins. If no rules match, default deny.

        Args:
            policy: The policy to evaluate
            context: Request context with all relevant attributes

        Returns:
            PolicyDecision with allowed, matched_rule_id, reason, explanation
        """
        trace_id = get_trace_id()
        
        log_policy_check(self.logger, policy.policy_id, True, trace_id,
                        action="evaluate", context_keys=list(context.keys()))
        
        # Check rules in order - first match wins
        for rule in policy.rules:
            if rule.matches(context):
                allowed = rule.effect == PolicyEffect.ALLOW
                explanation = f"Rule '{rule.rule_id}' ({rule.effect.value.upper()}) matched"
                reason = f"Matched rule: {rule.name}" if allowed else f"Denied by rule: {rule.name}"

                # Check budgets if allowed
                if allowed and policy.budgets:
                    cost = context.get("cost", 0.0)
                    for budget in policy.budgets:
                        if budget.is_exceeded(cost):
                            log_policy_check(self.logger, policy.policy_id, False, trace_id,
                                           action="evaluate_budget_exceeded", budget_name=budget.name,
                                           cost=cost)
                            return PolicyDecision(
                                allowed=False,
                                matched_rule_id=rule.rule_id,
                                reason=f"Budget '{budget.name}' exceeded",
                                explanation=f"Rule '{rule.rule_id}' (ALLOW) matched but budget exceeded",
                            )

                log_policy_check(self.logger, policy.policy_id, allowed, trace_id,
                               action="evaluate_complete", rule_id=rule.rule_id,
                               reason=reason)
                
                return PolicyDecision(
                    allowed=allowed,
                    matched_rule_id=rule.rule_id,
                    reason=reason,
                    explanation=explanation,
                )

        # No rules matched - default deny
        log_policy_check(self.logger, policy.policy_id, False, trace_id,
                       action="evaluate_default_deny")
        
        return PolicyDecision(
            allowed=False,
            matched_rule_id=None,
            reason="No matching rule found (default deny)",
            explanation="No rules matched the context",
        )

    def create_default_policy(self) -> Policy:
        """Create a sensible default policy."""
        policy = Policy(
            policy_id="default",
            name="Default Policy",
            description="Default policy with basic delegation rules",
            default_effect=PolicyEffect.DENY,
            rules=[
                PolicyRule(
                    rule_id="allow-delegation",
                    name="Allow delegation for verified agents",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="identity_verified",
                            operator=PolicyOperator.EQUALS,
                            value=True,
                        ),
                    ],
                ),
                PolicyRule(
                    rule_id="deny-dangerous",
                    name="Deny dangerous capabilities",
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.IN,
                            value=["dangerous_capability", "malware"],
                        ),
                    ],
                ),
            ],
        )
        return policy


# Import PolicyOperator for use in create_default_policy
from .models import PolicyOperator