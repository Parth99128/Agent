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
    name: str = Field(..., description="Agent name")
    description: str = Field(default="", description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    
    # Endpoints
    endpoints: List[str] = Field(default_factory=list, description="Service endpoints")
    protocols: List[str] = Field(default_factory=list, description="Supported protocols (a2a, mcp)")
    
    # Capabilities
    capabilities: List[str] = Field(default_factory=list, description="Capability names")
    capability_details: Dict[str, Any] = Field(default_factory=dict, description="Full capability details")
    
    # Identity & Trust
    identity_verified: bool = Field(default=False, description="Whether identity is verified")
    trust_score: float = Field(default=0.0, description="Current trust score")
    public_key: Optional[str] = Field(None, description="Agent public key")
    
    # Status
    status: HealthStatus = Field(default=HealthStatus.UNKNOWN, description="Health status")
    last_heartbeat: Optional[datetime] = Field(None, description="Last heartbeat timestamp")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    
    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Check if entry is stale (no recent heartbeat)."""
        if self.last_heartbeat is None:
            return True
        age = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return age > max_age_seconds
    
    def update_heartbeat(self):
        """Update heartbeat timestamp."""
        self.last_heartbeat = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


class RegistrationRequest(BaseModel):
    """Request to register an agent."""
    agent_did: str = Field(..., description="Agent DID")
    name: str = Field(..., description="Agent name")
    description: str = Field(default="", description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    endpoints: List[str] = Field(default_factory=list, description="Service endpoints")
    protocols: List[str] = Field(default_factory=list, description="Supported protocols")
    capabilities: List[str] = Field(default_factory=list, description="Capability names")
    capability_details: Dict[str, Any] = Field(default_factory=dict, description="Full capability details")
    public_key: Optional[str] = Field(None, description="Agent public key")
    identity_proof: Optional[str] = Field(None, description="Identity proof for verification")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class RegistrationResponse(BaseModel):
    """Response from registration."""
    success: bool = Field(..., description="Whether registration succeeded")
    entry_id: Optional[str] = Field(None, description="Registry entry ID")
    agent_did: Optional[str] = Field(None, description="Agent DID")
    message: str = Field(default="", description="Response message")
    expires_at: Optional[datetime] = Field(None, description="Registration expiry")


class HeartbeatRequest(BaseModel):
    """Heartbeat request from agent."""
    agent_did: str = Field(..., description="Agent DID")
    entry_id: Optional[str] = Field(None, description="Registry entry ID")
    status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="Current health status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional status info")


class HeartbeatResponse(BaseModel):
    """Heartbeat response."""
    success: bool = Field(..., description="Whether heartbeat was accepted")
    entry_id: Optional[str] = Field(None, description="Registry entry ID")
    message: str = Field(default="", description="Response message")
    next_heartbeat_seconds: int = Field(default=60, description="Seconds until next expected heartbeat")


class RegistryConfig(BaseModel):
    """Registry configuration."""
    host: str = Field(default="0.0.0.0", description="Bind host")
    port: int = Field(default=8081, description="Bind port")
    
    # Database
    database_url: str = Field(default="sqlite:///registry.db", description="Database URL")
    
    # TTL settings
    heartbeat_ttl_seconds: int = Field(default=300, description="Heartbeat TTL")
    stale_cleanup_interval_seconds: int = Field(default=60, description="Stale entry cleanup interval")
    
    # Limits
    max_entries: int = Field(default=10000, description="Maximum registry entries")
    max_endpoints_per_agent: int = Field(default=10, description="Max endpoints per agent")
    max_capabilities_per_agent: int = Field(default=100, description="Max capabilities per agent")
    
    # Verification
    require_identity_proof: bool = Field(default=True, description="Require identity proof on registration")
    auto_verify_identity: bool = Field(default=False, description="Auto-verify identity on registration")
    
    # Health checks
    health_check_enabled: bool = Field(default=True, description="Enable active health checks")
    health_check_interval_seconds: int = Field(default=300, description="Health check interval")
    health_check_timeout_seconds: int = Field(default=10, description="Health check timeout")
    
    # Rate limiting
    registration_rate_limit_per_minute: int = Field(default=10, description="Registrations per minute per IP")
    heartbeat_rate_limit_per_minute: int = Field(default=60, description="Heartbeats per minute per agent")