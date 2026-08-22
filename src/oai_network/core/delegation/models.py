"""
Delegation Models

Data models for task delegation between agents.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class DelegationStatus(str, Enum):
    """Status of a delegation."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class DelegationPriority(str, Enum):
    """Priority levels for delegation."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DelegationRequest(BaseModel):
    """Request to delegate a task to another agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    delegator_did: str = Field(..., description="DID of delegating agent")
    delegatee_did: Optional[str] = Field(None, description="DID of target agent (auto-discovered if not set)")
    capability: str = Field(..., description="Capability to invoke")
    input_data: dict[str, Any] = Field(default_factory=dict, description="Input data for the task")
    requirements: dict[str, Any] = Field(default_factory=dict, description="Requirements and constraints")
    priority: DelegationPriority = Field(default=DelegationPriority.NORMAL)
    timeout_seconds: int = Field(default=300, description="Task timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    requires_approval: bool = Field(default=False, description="Whether delegatee must approve")
    callback_url: Optional[str] = Field(None, description="URL for completion callback")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When request expires")


class DelegationResponse(BaseModel):
    """Response to a delegation request."""
    request_id: str = Field(..., description="Original request ID")
    delegatee_did: Optional[str] = Field(None, description="DID of responding agent")
    accepted: bool = Field(..., description="Whether delegation was accepted")
    task_id: Optional[str] = Field(None, description="Task ID if accepted")
    rejection_reason: Optional[str] = Field(None, description="Reason if rejected")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelegationTask(BaseModel):
    """Active delegation task."""
    task_id: str = Field(..., description="Task ID")
    request_id: str = Field(..., description="Original request ID")
    delegator_did: str = Field(..., description="DID of delegating agent")
    delegatee_did: Optional[str] = Field(None, description="DID of delegatee agent")
    capability: str = Field(..., description="Capability name")
    input_data: dict[str, Any] = Field(default_factory=dict, description="Input data for the task")
    status: DelegationStatus = Field(default=DelegationStatus.PENDING)
    session_id: Optional[str] = Field(None, description="Negotiation session ID")
    agreement_id: Optional[str] = Field(None, description="Agreement ID")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = Field(default=0)
    last_error: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress 0-1")
    intermediate_results: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    depth: int = Field(default=0, description="Delegation depth in chain")
    estimated_cost: float = Field(default=0.0, description="Estimated cost for budget tracking")

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
            DelegationStatus.TIMEOUT,
        )

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == DelegationStatus.FAILED and
            self.retry_count < 3
        )


class DelegationResult(BaseModel):
    """Result of a completed delegation."""
    task_id: str = Field(..., description="Task ID")
    status: DelegationStatus
    output_data: Optional[dict[str, Any]] = Field(None, description="Task output")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: float = Field(default=0.0, description="Total execution time in ms")
    cost: Optional[float] = Field(None, description="Cost incurred")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class DelegationChain(BaseModel):
    """A chain of delegations (for multi-hop delegation)."""
    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_request_id: Optional[str] = Field(None, description="Original request ID")
    root_delegator_did: str = Field(default="", description="Original delegator")
    tasks: list[str] = Field(default_factory=list, description="List of task IDs in the chain")
    max_depth: int = Field(default=3, description="Maximum delegation depth")
    current_depth: int = Field(default=0)
    status: DelegationStatus = Field(default=DelegationStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def add_task(self, task_id: str):
        """Add a task ID to the chain."""
        self.tasks.append(task_id)
        self.current_depth = len(self.tasks)

    def is_complete(self) -> bool:
        """Check if chain is complete."""
        return self.current_depth >= len(self.tasks) and len(self.tasks) > 0


class DelegationPolicy(BaseModel):
    """Policy controlling delegation behavior."""
    max_depth: int = Field(default=5, description="Maximum delegation depth")
    allowed_delegatees: list[str] = Field(default_factory=list, description="Allowed delegatee DIDs")
    blocked_delegatees: list[str] = Field(default_factory=list, description="Blocked delegatee DIDs")
    require_verified_identity: bool = Field(default=False, description="Require verified delegatee")
    min_trust_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum trust score")
    max_cost_per_delegation: Optional[float] = Field(None, description="Maximum cost per delegation")
    max_total_cost: Optional[float] = Field(None, description="Maximum total cost for chain")
    max_budget: Optional[float] = Field(None, description="Maximum budget for delegator")
    budget_period: str = Field(default="daily", description="Budget period (daily, weekly, monthly)")
    allowed_capabilities: list[str] = Field(default_factory=list, description="Allowed capability names")
    blocked_capabilities: list[str] = Field(default_factory=list, description="Blocked capability names")
    require_approval_above_cost: Optional[float] = Field(None, description="Require approval above cost")
    default_timeout_seconds: int = Field(default=300)
    max_timeout_seconds: int = Field(default=3600)

    def can_delegate_to(self, delegatee_did: str, trust_score: float, verified: bool) -> tuple[bool, Optional[str]]:
        """Check if delegation to an agent is allowed."""
        if delegatee_did in self.blocked_delegatees:
            return False, "Delegatee is blocked"

        if self.allowed_delegatees and delegatee_did not in self.allowed_delegatees:
            return False, "Delegatee not in allowed list"

        if self.require_verified_identity and not verified:
            return False, "Delegatee identity not verified"

        if trust_score < self.min_trust_score:
            return False, f"Trust score {trust_score} below minimum {self.min_trust_score}"

        return True, None

    def can_delegate_capability(self, capability_name: str) -> tuple[bool, Optional[str]]:
        """Check if a capability can be delegated."""
        if capability_name in self.blocked_capabilities:
            return False, "Capability is blocked"

        if self.allowed_capabilities and capability_name not in self.allowed_capabilities:
            return False, "Capability not in allowed list"

        return True, None