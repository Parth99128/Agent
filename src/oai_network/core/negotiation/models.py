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
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AGREED = "agreed"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class NegotiationRequest(BaseModel):
    """Request to start a negotiation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initiator_did: str = Field(..., description="DID of initiating agent")
    responder_did: str = Field(..., description="DID of responding agent")
    template_id: str = Field(default="standard", description="Template to use")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Negotiation parameters")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NegotiationResponse(BaseModel):
    """Response to a negotiation request."""
    request_id: str = Field(..., description="ID of the request/session")
    responder_did: str = Field(..., description="DID of responding agent")
    accepted: bool = Field(..., description="Whether terms are accepted")
    agreed_parameters: dict[str, Any] = Field(default_factory=dict, description="Agreed parameters")
    counter_parameters: dict[str, Any] = Field(default_factory=dict, description="Counter-offer parameters")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        """Auto-register counter-offer as a round in the matching session."""
        super().model_post_init(__context)
        if self.counter_parameters and not self.accepted:
            # Try to find the session and add a round
            from .protocol import _global_protocol_registry
            protocol = _global_protocol_registry.get(self.request_id)
            if protocol:
                session = protocol.get_session(self.request_id)
                if session:
                    round_num = len(session.rounds) + 1
                    session.rounds.append(NegotiationRound(
                        round_number=round_num,
                        proposer_did=self.responder_did,
                        parameters=self.counter_parameters,
                        message=self.message,
                    ))
                    session.status = "in_progress"


class NegotiationRound(BaseModel):
    """A single round in a negotiation."""
    round_number: int = Field(..., description="Round number")
    proposer_did: str = Field(..., description="DID of proposing agent")
    parameters: dict[str, Any] = Field(..., description="Proposed parameters")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NegotiationSession(BaseModel):
    """Active negotiation session."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    initiator_did: str
    responder_did: str
    template_id: str = Field(default="standard")
    status: str = Field(default="pending")
    parameters: dict[str, Any] = Field(default_factory=dict)
    rounds: list[NegotiationRound] = Field(default_factory=list)
    agreed_parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class NegotiationAgreement(BaseModel):
    """Finalized agreement from a negotiation session."""
    session_id: str = Field(..., description="Original session ID")
    agreed_parameters: dict[str, Any] = Field(..., description="Agreed parameters")
    expires_at: Optional[datetime] = Field(None, description="When agreement expires")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signatures: dict[str, str] = Field(default_factory=dict, description="Signatures by DID")


class NegotiationTemplate(BaseModel):
    """Template for common negotiation scenarios."""
    template_id: str = Field(..., description="Unique template ID")
    name: str = Field(..., description="Template name")
    description: str = Field(default="", description="Template description")
    required_parameters: list[str] = Field(default_factory=list, description="Required parameters")
    optional_parameters: list[str] = Field(default_factory=list, description="Optional parameters")
    default_values: dict[str, Any] = Field(default_factory=dict, description="Default values for parameters")
    max_rounds: int = Field(default=5, description="Maximum negotiation rounds")
    timeout_seconds: int = Field(default=300, description="Negotiation timeout")