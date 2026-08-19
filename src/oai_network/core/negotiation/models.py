"""
Negotiation Models

Data models for agent-to-agent negotiation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class NegotiationStatus(str, Enum):
    """Status of a negotiation session."""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    AGREED = "agreed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NegotiationTopic(str, Enum):
    """Topics that can be negotiated."""
    PROTOCOL = "protocol"           # Communication protocol (A2A, MCP, custom)
    DATA_FORMAT = "data_format"     # Data serialization format (JSON, msgpack, protobuf)
    AUTH_METHOD = "auth_method"     # Authentication method
    PRICING = "pricing"             # Pricing model and rates
    SLA = "sla"                     # Service level agreements
    RATE_LIMITS = "rate_limits"     # Rate limiting parameters
    TIMEOUT = "timeout"             # Request timeouts
    DELEGATION = "delegation"       # Delegation permissions
    PRIVACY = "privacy"             # Data privacy requirements


class NegotiationRequest(BaseModel):
    """Request to start a negotiation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initiator_did: str = Field(..., description="DID of initiating agent")
    responder_did: str = Field(..., description="DID of responding agent")
    capability_name: str = Field(..., description="Capability being negotiated")
    topics: list[NegotiationTopic] = Field(..., description="Topics to negotiate")
    proposed_terms: dict[str, Any] = Field(default_factory=dict, description="Proposed terms")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Hard constraints")
    expires_at: datetime = Field(..., description="When negotiation expires")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NegotiationResponse(BaseModel):
    """Response to a negotiation request."""
    negotiation_id: str = Field(..., description="ID of negotiation")
    responder_did: str = Field(..., description="DID of responding agent")
    accepted: bool = Field(..., description="Whether terms are accepted")
    counter_terms: dict[str, Any] = Field(default_factory=dict, description="Counter-proposed terms")
    rejected_topics: list[NegotiationTopic] = Field(default_factory=list, description="Topics rejected")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NegotiationSession(BaseModel):
    """Active negotiation session."""
    id: str = Field(..., description="Session ID")
    initiator_did: str
    responder_did: str
    capability_name: str
    status: NegotiationStatus = Field(default=NegotiationStatus.INITIATED)
    topics: list[NegotiationTopic]
    current_terms: dict[str, Any] = Field(default_factory=dict)
    agreed_terms: dict[str, Any] = Field(default_factory=dict)
    round: int = Field(default=0, description="Negotiation round number")
    max_rounds: int = Field(default=5, description="Maximum negotiation rounds")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    agreed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def can_continue(self) -> bool:
        """Check if negotiation can continue."""
        return (
            self.status == NegotiationStatus.IN_PROGRESS and
            not self.is_expired() and
            self.round < self.max_rounds
        )


class Agreement(BaseModel):
    """Finalized agreement between two agents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    negotiation_id: str = Field(..., description="Original negotiation ID")
    initiator_did: str
    responder_did: str
    capability_name: str
    terms: dict[str, Any] = Field(..., description="Agreed terms")
    valid_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Optional[datetime] = Field(None, description="When agreement expires")
    signatures: dict[str, str] = Field(default_factory=dict, description="Signatures by DID")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_valid(self) -> bool:
        """Check if agreement is currently valid."""
        now = datetime.now(timezone.utc)
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    def has_signature(self, did: str) -> bool:
        """Check if a DID has signed."""
        return did in self.signatures
    
    def add_signature(self, did: str, signature: str):
        """Add a signature."""
        self.signatures[did] = signature
    
    def is_fully_signed(self) -> bool:
        """Check if both parties have signed."""
        return self.initiator_did in self.signatures and self.responder_did in self.signatures


class NegotiationTemplate(BaseModel):
    """Template for common negotiation scenarios."""
    name: str
    description: str
    default_topics: list[NegotiationTopic]
    default_terms: dict[str, Any]
    default_constraints: dict[str, Any]
    max_rounds: int = 5
    timeout_seconds: int = 300


class NegotiationAgreement(BaseModel):
    """Finalized agreement from a negotiation session."""
    session_id: str = Field(..., description="Original session ID")
    agreed_parameters: dict[str, Any] = Field(..., description="Agreed parameters")
    expires_at: Optional[datetime] = Field(None, description="When agreement expires")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signatures: dict[str, str] = Field(default_factory=dict, description="Signatures by DID")


class NegotiationRound(BaseModel):
    """A single round in a negotiation."""
    round_number: int = Field(..., description="Round number")
    proposer_did: str = Field(..., description="DID of proposing agent")
    parameters: dict[str, Any] = Field(..., description="Proposed parameters")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))