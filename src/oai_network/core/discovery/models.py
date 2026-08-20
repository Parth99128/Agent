"""
Discovery Models

Data models for the discovery service.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, List
from pydantic import BaseModel, Field
import uuid


class SortBy(str, Enum):
    """Sort options for discovery results."""
    RELEVANCE = "relevance"
    TRUST = "trust"
    LATENCY = "latency"
    PRICE = "price"
    RECENCY = "recency"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class DiscoveryQuery(BaseModel):
    """Query for discovering agents."""
    query: str = Field(..., description="Natural language query")
    capability_type: Optional[str] = Field(None, description="Filter by capability type")
    tags: list[str] = Field(default_factory=list, description="Filter by tags")
    min_trust_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum trust score")
    max_price: Optional[float] = Field(None, description="Maximum price per unit")
    max_latency_ms: Optional[int] = Field(None, description="Maximum latency in milliseconds")
    verified_only: bool = Field(default=False, description="Require verified identity")
    sort_by: SortBy = Field(default=SortBy.RELEVANCE, description="Sort results by")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="Sort order")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    # Context for better matching
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    requester_did: Optional[str] = Field(None, description="DID of requesting agent")


class DiscoveryResult(BaseModel):
    """A single discovery result."""
    agent_did: str = Field(..., description="Agent's DID")
    agent_name: str = Field(default="", description="Agent's name")
    agent_description: str = Field(default="", description="Agent's description")
    capability_name: str = Field(..., description="Name of matched capability")
    capability_type: str = Field(default="", description="Type of matched capability")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="Agent's trust score")
    estimated_latency_ms: Optional[int] = Field(None, description="Estimated latency")
    price_per_unit: Optional[float] = Field(None, description="Price per unit")
    currency: str = Field(default="USD", description="Currency")
    endpoint_url: str = Field(default="", description="Primary endpoint URL")
    tags: list[str] = Field(default_factory=list, description="Capability tags")
    verified: bool = Field(default=False, description="Whether identity is verified")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump(mode='json')


class RegistryEntry(BaseModel):
    """An entry in the agent registry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique entry ID")
    agent_did: str = Field(..., description="Agent's DID")
    manifest: Optional[Any] = Field(None, description="Agent manifest object")
    manifest_json: str = Field(default="", description="Full manifest as JSON")
    manifest_hash: str = Field(default="", description="Hash of manifest for change detection")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When entry expires")
    status: str = Field(default="active", description="Entry status (active, inactive, expired)")
    verification_status: str = Field(default="pending", description="Verification status")

    @property
    def is_active(self) -> bool:
        """Check if entry is active."""
        return self.status == "active"

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump(mode='json')


class RegistrationRequest(BaseModel):
    """Request to register an agent."""
    manifest: Any = Field(..., description="Agent manifest object (or JSON string)")
    ttl_seconds: int = Field(default=86400, description="Time to live in seconds")


class RegistrationResponse(BaseModel):
    """Response from registration."""
    success: bool
    agent_did: Optional[str] = None
    registration_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    """Heartbeat to keep registration alive."""
    entry_id: str
    agent_did: str
    proof: str = Field(default="", description="Identity proof")


class HeartbeatResponse(BaseModel):
    """Response to heartbeat."""
    success: bool
    expires_at: Optional[datetime] = None
    errors: list[str] = Field(default_factory=list)


class Heartbeat(BaseModel):
    """Heartbeat from an agent."""
    agent_did: str = Field(..., description="Agent's DID")
    status: str = Field(default="healthy", description="Agent status")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))