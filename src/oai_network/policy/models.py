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


class PolicyConditionType(str, Enum):
    """Types of policy conditions."""
    # Identity conditions
    AGENT_DID = "agent_did"
    AGENT_NAME = "agent_name"
    IDENTITY_VERIFIED = "identity_verified"
    TRUST_SCORE = "trust_score"
    
    # Capability conditions
    CAPABILITY_NAME = "capability_name"
    CAPABILITY_TYPE = "capability_type"
    CAPABILITY_TAG = "capability_tag"
    
    # Request conditions
    REQUESTER_DID = "requester_did"
    DELEGATION_DEPTH = "delegation_depth"
    IS_DELEGATION = "is_delegation"
    
    # Resource conditions
    RESOURCE_TYPE = "resource_type"
    RESOURCE_PATH = "resource_path"
    
    # Context conditions
    TIME_OF_DAY = "time_of_day"
    DAY_OF_WEEK = "day_of_week"
    IP_ADDRESS = "ip_address"
    
    # Custom
    CUSTOM = "custom"


class PolicyOperator(str, Enum):
    """Operators for policy conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    EXISTS = "exists"


class PolicyCondition(BaseModel):
    """A single policy condition."""
    type: PolicyConditionType = Field(..., description="Condition type")
    operator: PolicyOperator = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    field: Optional[str] = Field(None, description="Field path for custom conditions")
    
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against a context."""
        # Get the value from context
        if self.type == PolicyConditionType.CUSTOM and self.field:
            context_value = self._get_nested(context, self.field)
        else:
            context_value = context.get(self.type.value)
        
        if context_value is None:
            return self.operator == PolicyOperator.NOT_EQUALS or self.operator == PolicyOperator.NOT_IN
        
        # Apply operator
        return self._apply_operator(context_value, self.value)
    
    def _get_nested(self, obj: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        keys = path.split('.')
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            if current is None:
                return None
        return current
    
    def _apply_operator(self, context_value: Any, policy_value: Any) -> bool:
        """Apply the operator to compare values."""
        if self.operator == PolicyOperator.EQUALS:
            return context_value == policy_value
        elif self.operator == PolicyOperator.NOT_EQUALS:
            return context_value != policy_value
        elif self.operator == PolicyOperator.IN:
            return context_value in policy_value if isinstance(policy_value, list) else False
        elif self.operator == PolicyOperator.NOT_IN:
            return context_value not in policy_value if isinstance(policy_value, list) else True
        elif self.operator == PolicyOperator.GREATER_THAN:
            return context_value > policy_value
        elif self.operator == PolicyOperator.GREATER_THAN_OR_EQUAL:
            return context_value >= policy_value
        elif self.operator == PolicyOperator.LESS_THAN:
            return context_value < policy_value
        elif self.operator == PolicyOperator.LESS_THAN_OR_EQUAL:
            return context_value <= policy_value
        elif self.operator == PolicyOperator.CONTAINS:
            return policy_value in str(context_value)
        elif self.operator == PolicyOperator.STARTS_WITH:
            return str(context_value).startswith(str(policy_value))
        elif self.operator == PolicyOperator.ENDS_WITH:
            return str(context_value).endswith(str(policy_value))
        elif self.operator == PolicyOperator.REGEX:
            import re
            return bool(re.match(str(policy_value), str(context_value)))
        elif self.operator == PolicyOperator.EXISTS:
            return context_value is not None
        return False


class PolicyRule(BaseModel):
    """A single policy rule."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
        return all(condition.evaluate(context) for condition in self.conditions)


class BudgetPeriod(str, Enum):
    """Budget period types."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"


class Budget(BaseModel):
    """Budget limits for agent usage."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Budget name")
    agent_did: Optional[str] = Field(None, description="Specific agent (None = global)")
    requester_did: Optional[str] = Field(None, description="Specific requester (None = any)")
    capability_name: Optional[str] = Field(None, description="Specific capability (None = any)")
    period: BudgetPeriod = Field(default=BudgetPeriod.DAILY, description="Budget period")
    max_calls: Optional[int] = Field(None, description="Maximum calls per period")
    max_cost: Optional[float] = Field(None, description="Maximum cost per period")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens per period")
    max_latency_ms: Optional[int] = Field(None, description="Maximum total latency per period")
    current_calls: int = Field(default=0, description="Calls used in current period")
    current_cost: float = Field(default=0.0, description="Cost used in current period")
    current_tokens: int = Field(default=0, description="Tokens used in current period")
    current_latency_ms: int = Field(default=0, description="Latency used in current period")
    period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enabled: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_exceeded(self) -> tuple[bool, list[str]]:
        """Check if budget is exceeded."""
        reasons = []
        
        if self.max_calls is not None and self.current_calls >= self.max_calls:
            reasons.append(f"Call limit exceeded: {self.current_calls}/{self.max_calls}")
        
        if self.max_cost is not None and self.current_cost >= self.max_cost:
            reasons.append(f"Cost limit exceeded: {self.current_cost}/{self.max_cost}")
        
        if self.max_tokens is not None and self.current_tokens >= self.max_tokens:
            reasons.append(f"Token limit exceeded: {self.current_tokens}/{self.max_tokens}")
        
        if self.max_latency_ms is not None and self.current_latency_ms >= self.max_latency_ms:
            reasons.append(f"Latency limit exceeded: {self.current_latency_ms}/{self.max_latency_ms}")
        
        return len(reasons) > 0, reasons
    
    def consume(self, calls: int = 1, cost: float = 0.0, tokens: int = 0, latency_ms: int = 0):
        """Consume budget."""
        self.current_calls += calls
        self.current_cost += cost
        self.current_tokens += tokens
        self.current_latency_ms += latency_ms
    
    def reset_if_needed(self):
        """Reset budget if period has elapsed."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.period_start).total_seconds()
        
        period_seconds = {
            BudgetPeriod.HOURLY: 3600,
            BudgetPeriod.DAILY: 86400,
            BudgetPeriod.WEEKLY: 604800,
            BudgetPeriod.MONTHLY: 2592000,  # ~30 days
        }
        
        if self.period == BudgetPeriod.TOTAL:
            return  # Never reset
        
        if elapsed >= period_seconds.get(self.period, 86400):
            self.current_calls = 0
            self.current_cost = 0.0
            self.current_tokens = 0
            self.current_latency_ms = 0
            self.period_start = now


class Policy(BaseModel):
    """Complete policy document."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
            if rule.id == rule_id:
                self.rules.pop(i)
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False
    
    def add_budget(self, budget: Budget):
        """Add a budget."""
        self.budgets.append(budget)
        self.updated_at = datetime.now(timezone.utc)
    
    def to_yaml(self) -> str:
        """Serialize to YAML."""
        import yaml
        return yaml.dump(self.model_dump(mode='json'), sort_keys=False)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'Policy':
        """Deserialize from YAML."""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls(**data)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Policy':
        """Deserialize from JSON."""
        return cls.model_validate_json(json_str)