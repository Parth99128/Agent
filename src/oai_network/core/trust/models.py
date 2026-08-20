"""
Trust Models

Data models for trust and reputation system.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class TrustEventType(str, Enum):
    """Types of trust-affecting events."""
    INTERACTION_SUCCESS = "interaction_success"
    INTERACTION_FAILURE = "interaction_failure"
    INTERACTION_TIMEOUT = "interaction_timeout"
    POSITIVE_FEEDBACK = "positive_feedback"
    NEGATIVE_FEEDBACK = "negative_feedback"
    IDENTITY_VERIFIED = "identity_verified"
    IDENTITY_REVOKED = "identity_revoked"
    POLICY_VIOLATION = "policy_violation"
    DELEGATION_SUCCESS = "delegation_success"
    DELEGATION_FAILURE = "delegation_failure"


class TrustEvent(BaseModel):
    """A single trust-affecting event."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., description="Type of event")
    source_did: str = Field(..., description="Source agent DID")
    target_did: str = Field(..., description="Target agent DID")
    value: float = Field(default=1.0, description="Event value for trust calculation")
    weight: float = Field(default=1.0, description="Event weight for trust calculation")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    interaction_id: Optional[str] = Field(None, description="Related interaction ID")
    capability_name: Optional[str] = Field(None, description="Capability involved")
    
    # Metrics
    latency_ms: Optional[float] = Field(None, description="Latency for interaction events")
    cost: Optional[float] = Field(None, description="Cost incurred")
    
    # Feedback
    feedback_text: Optional[str] = Field(None, description="Optional feedback text")
    feedback_rating: Optional[int] = Field(None, ge=1, le=5, description="Rating 1-5")
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="system", description="Event source (system, user, peer)")


class TrustScore(BaseModel):
    """Current trust score for an agent."""
    agent_did: str = Field(..., description="Agent DID")
    overall_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall trust (0-1)")
    interaction_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Interaction-based score")
    feedback_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Feedback-based score")
    identity_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Identity verification score")
    behavior_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Behavior pattern score")
    
    # Component metrics
    event_count: int = Field(default=0, description="Total number of trust events")
    interaction_count: int = Field(default=0, description="Total interactions")
    successful_interactions: int = Field(default=0)
    failed_interactions: int = Field(default=0)
    avg_latency_ms: float = Field(default=0.0)
    total_feedback: int = Field(default=0)
    positive_feedback: int = Field(default=0)
    negative_feedback: int = Field(default=0)
    identity_verified: bool = Field(default=False)
    policy_violations: int = Field(default=0)
    
    # Time decay
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_interaction: Optional[datetime] = Field(None)
    
    # Confidence (based on volume of data)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in score")
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.interaction_count == 0:
            return 0.5
        return self.successful_interactions / self.interaction_count
    
    def feedback_ratio(self) -> float:
        """Calculate positive feedback ratio."""
        if self.total_feedback == 0:
            return 0.5
        return self.positive_feedback / self.total_feedback
    
    def recency_factor(self, half_life_days: int = 30) -> float:
        """Calculate recency factor (1.0 = recent, decays over time)."""
        if self.last_interaction is None:
            return 0.5
        days_since = (datetime.now(timezone.utc) - self.last_interaction).days
        return max(0.1, 0.5 ** (days_since / half_life_days))
    
    def volume_factor(self, target_interactions: int = 100) -> float:
        """Calculate volume factor (more interactions = higher confidence)."""
        return min(1.0, self.interaction_count / target_interactions)


class Feedback(BaseModel):
    """User feedback on an agent interaction."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_did: str = Field(..., description="Agent/person giving feedback")
    to_did: str = Field(..., description="Agent being rated")
    interaction_id: Optional[str] = Field(None, description="Interaction being rated")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: Optional[str] = Field(None, description="Optional comment")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verified: bool = Field(default=False, description="Whether feedback is verified")
    
    def is_positive(self) -> bool:
        """Check if feedback is positive (4-5 stars)."""
        return self.rating >= 4
    
    def is_negative(self) -> bool:
        """Check if feedback is negative (1-2 stars)."""
        return self.rating <= 2


class ReputationLedger(BaseModel):
    """Immutable ledger of trust events for an agent."""
    agent_did: Optional[str] = Field(None, description="Agent DID")
    events: list[TrustEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_event(self, event: TrustEvent):
        """Add an event to the ledger."""
        self.events.append(event)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_events_for_agent(self, agent_did: str) -> list[TrustEvent]:
        """Get events for a specific agent."""
        return [e for e in self.events if e.target_did == agent_did]
    
    def get_events_since(self, since: datetime) -> list[TrustEvent]:
        """Get events since a given time."""
        return [e for e in self.events if e.timestamp >= since]
    
    def get_events_by_type(self, event_type: TrustEventType) -> list[TrustEvent]:
        """Get events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]
    
    def calculate_score(self) -> TrustScore:
        """Calculate trust score from ledger."""
        from .calculator import TrustCalculator
        calculator = TrustCalculator()
        return calculator.calculate_from_ledger(self)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ReputationLedger':
        """Create from dictionary."""
        return cls(**data)