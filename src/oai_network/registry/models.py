"""
Registry Models

Data models for the agent registry.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import uuid


class HealthStatus(str, Enum):
    """Health status of a registered agent."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RegistryEntry(BaseModel):
    """A registered agent entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_did: str = Field(..., description="Agent DID")
    name: str = Field(default="", description="Agent name")
    description: str = Field(default="", description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")

    # Manifest
    manifest: Optional[Any] = Field(None, description="Agent manifest object")
    manifest_json: str = Field(default="", description="Manifest as JSON")

    # Endpoints
    endpoints: List[str] = Field(default_factory=list, description="Service endpoint URLs")
    protocols: List[str] = Field(default_factory=list, description="Supported protocols (a2a, mcp)")

    # Capabilities
    capabilities: List[str] = Field(default_factory=list, description="Capability names")
    capability_details: Dict[str, Any] = Field(default_factory=dict, description="Full capability details")

    # Identity & Trust
    identity_verified: bool = Field(default=False, description="Whether identity is verified")
    trust_score: float = Field(default=0.0, description="Current trust score")
    public_key: Optional[str] = Field(None, description="Agent public key")

    # Status
    status: str = Field(default="active", description="Entry status (active, inactive, expired, degraded, unhealthy)")
    health_status: HealthStatus = Field(default=HealthStatus.UNKNOWN, description="Health status")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat timestamp")
    missed_heartbeats: int = Field(default=0, description="Number of missed heartbeats")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="When entry expires")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Check if entry is stale (no recent heartbeat)."""
        if self.last_heartbeat is None:
            return True
        age = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return age > max_age_seconds

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def update_heartbeat(self):
        """Update heartbeat timestamp."""
        self.last_heartbeat = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.missed_heartbeats = 0


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
    """Heartbeat request from agent."""
    agent_did: str = Field(..., description="Agent DID")
    status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="Current health status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional status info")


class HeartbeatResponse(BaseModel):
    """Heartbeat response."""
    success: bool
    agent_did: Optional[str] = None
    next_heartbeat_interval: int = Field(default=60, description="Seconds until next expected heartbeat")
    error: Optional[str] = None


class DiscoveryAgentResult(BaseModel):
    """Agent result in discovery response."""
    agent_did: str = Field(..., description="Agent DID")
    agent_name: str = Field(..., description="Agent name")
    agent_description: str = Field(default="", description="Agent description")
    capability_name: str = Field(default="", description="Matched capability name")
    trust_score: float = Field(default=0.0, description="Trust score")
    verified: bool = Field(default=False, description="Whether agent is verified")
    capabilities: list[str] = Field(default_factory=list, description="Capability names")
    endpoints: list[str] = Field(default_factory=list, description="Endpoint URLs")
    tags: list[str] = Field(default_factory=list, description="Tags")
    relevance_score: float = Field(default=0.0, description="Semantic relevance score (0-1)")


class DiscoveryQuery(BaseModel):
    """Query for discovering agents."""
    capability: str = Field(..., description="Capability name to search for")
    max_results: int = Field(default=10, description="Maximum number of results")
    min_trust_score: float = Field(default=0.0, description="Minimum trust score")
    verified_only: bool = Field(default=False, description="Only return verified agents")
    tags: list[str] = Field(default_factory=list, description="Filter by tags")


class DiscoveryResponse(BaseModel):
    """Response from discovery query."""
    agents: list[DiscoveryAgentResult] = Field(default_factory=list)
    total: int = Field(default=0, description="Total matching agents")


class RegistryConfig(BaseModel):
    """Registry configuration."""
    host: str = Field(default="0.0.0.0", description="Bind host")
    port: int = Field(default=8081, description="Bind port")

    # Database
    database_url: str = Field(default="sqlite:///registry.db", description="Database URL")

    # TTL settings
    default_ttl_seconds: int = Field(default=86400, description="Default TTL for registrations")
    heartbeat_interval_seconds: int = Field(default=60, description="Expected heartbeat interval")
    cleanup_interval_seconds: int = Field(default=300, description="Cleanup interval")
    max_heartbeat_missed: int = Field(default=3, description="Max missed heartbeats before removal")

    # Limits
    max_entries: int = Field(default=10000, description="Maximum registry entries")
    max_endpoints_per_agent: int = Field(default=10, description="Max endpoints per agent")
    max_capabilities_per_agent: int = Field(default=100, description="Max capabilities per agent")

    # Verification
    require_identity_proof: bool = Field(default=False, description="Require identity proof on registration")
    auto_verify_identity: bool = Field(default=True, description="Auto-verify identity on registration")

    # Health checks
    health_check_enabled: bool = Field(default=True, description="Enable active health checks")
    health_check_interval_seconds: int = Field(default=300, description="Health check interval")
    health_check_timeout_seconds: int = Field(default=10, description="Health check timeout")

    # Rate limiting
    registration_rate_limit_per_minute: int = Field(default=10, description="Registrations per minute per IP")
    heartbeat_rate_limit_per_minute: int = Field(default=60, description="Heartbeats per minute per agent")