"""
Policy Models

Data models for the policy/authorization system.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class PolicyEffect(str, Enum):
    """Effect of a policy rule."""
    ALLOW = "allow"
    DENY = "deny"


class PolicyOperator(str, Enum):
    """Operators for policy conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    EXISTS = "exists"


class BudgetPeriod(str, Enum):
    """Budget period types."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PolicyCondition(BaseModel):
    """A single policy condition."""
    field: str = Field(..., description="Field name in the context to check")
    operator: PolicyOperator = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against a context."""
        context_value = context.get(self.field)
        return self._apply_operator(context_value, self.value)

    def _apply_operator(self, context_value: Any, policy_value: Any) -> bool:
        """Apply the operator to compare values."""
        if self.operator == PolicyOperator.EQUALS:
            return context_value == policy_value
        elif self.operator == PolicyOperator.NOT_EQUALS:
            return context_value != policy_value
        elif self.operator == PolicyOperator.IN:
            return context_value in policy_value if isinstance(policy_value, (list, set, tuple)) else False
        elif self.operator == PolicyOperator.NOT_IN:
            return context_value not in policy_value if isinstance(policy_value, (list, set, tuple)) else True
        elif self.operator == PolicyOperator.GREATER_THAN:
            if context_value is None:
                return False
            return context_value > policy_value
        elif self.operator == PolicyOperator.GREATER_THAN_OR_EQUAL:
            if context_value is None:
                return False
            return context_value >= policy_value
        elif self.operator == PolicyOperator.LESS_THAN:
            if context_value is None:
                return False
            return context_value < policy_value
        elif self.operator == PolicyOperator.LESS_THAN_OR_EQUAL:
            if context_value is None:
                return False
            return context_value <= policy_value
        elif self.operator == PolicyOperator.CONTAINS:
            if context_value is None:
                return False
            return policy_value in context_value if isinstance(context_value, (list, str, dict)) else False
        elif self.operator == PolicyOperator.STARTS_WITH:
            return str(context_value).startswith(str(policy_value)) if context_value is not None else False
        elif self.operator == PolicyOperator.ENDS_WITH:
            return str(context_value).endswith(str(policy_value)) if context_value is not None else False
        elif self.operator == PolicyOperator.REGEX:
            import re
            return bool(re.match(str(policy_value), str(context_value))) if context_value is not None else False
        elif self.operator == PolicyOperator.EXISTS:
            return context_value is not None
        return False


class PolicyRule(BaseModel):
    """A single policy rule."""
    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field(default="", description="Rule description")
    effect: PolicyEffect = Field(..., description="Allow or deny")
    conditions: list[PolicyCondition] = Field(default_factory=list, description="Conditions that must all match")
    priority: int = Field(default=0, description="Higher priority rules evaluated first")
    enabled: bool = Field(default=True, description="Whether rule is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def matches(self, context: dict[str, Any]) -> bool:
        """Check if all conditions match the context."""
        if not self.enabled:
            return False
        if not self.conditions:
            return True  # No conditions = always matches
        return all(condition.evaluate(context) for condition in self.conditions)


class Budget(BaseModel):
    """Budget limits for agent usage."""
    budget_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Budget name")
    period: BudgetPeriod = Field(default=BudgetPeriod.DAILY, description="Budget period")
    limit: float = Field(default=0.0, description="Budget limit")
    currency: str = Field(default="USD", description="Currency for cost budgets")
    current_usage: float = Field(default=0.0, description="Current usage in period")
    enabled: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_exceeded(self, cost: float = 0.0) -> bool:
        """Check if adding cost would exceed the budget."""
        return self.current_usage + cost > self.limit

    def consume(self, cost: float = 0.0):
        """Consume budget."""
        self.current_usage += cost


class Policy(BaseModel):
    """Complete policy document."""
    policy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Policy name")
    description: str = Field(default="", description="Policy description")
    version: str = Field(default="1.0.0", description="Policy version")
    rules: list[PolicyRule] = Field(default_factory=list, description="Policy rules")
    budgets: list[Budget] = Field(default_factory=list, description="Budget limits")
    default_effect: PolicyEffect = Field(default=PolicyEffect.DENY, description="Default if no rules match")
    enabled: bool = Field(default=True, description="Whether policy is active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_rule(self, rule: PolicyRule):
        """Add a rule, maintaining priority order."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.updated_at = datetime.now(timezone.utc)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                self.rules.pop(i)
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False

    def add_budget(self, budget: Budget):
        """Add a budget."""
        self.budgets.append(budget)
        self.updated_at = datetime.now(timezone.utc)