"""
Capability Models

Data models for agent capabilities and manifests.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field, field_validator
import json


class PricingModel(str, Enum):
    """Pricing models for agent services."""
    FREE = "free"
    PER_CALL = "per_call"
    PER_TOKEN = "per_token"
    PER_SECOND = "per_second"
    SUBSCRIPTION = "subscription"
    CUSTOM = "custom"


class CapabilityPricing(BaseModel):
    """Pricing configuration for a capability."""
    model: PricingModel = Field(default=PricingModel.FREE, description="Pricing model")
    price_per_call: Optional[float] = Field(None, description="Price per call")
    price_per_token: Optional[float] = Field(None, description="Price per token")
    price_per_second: Optional[float] = Field(None, description="Price per second")
    currency: str = Field(default="USD", description="Currency code")
    subscription_tier: Optional[str] = Field(None, description="Subscription tier name")


class ServiceEndpoint(BaseModel):
    """Network endpoint where the agent can be reached."""
    url: str = Field(..., description="Base URL for the agent's API")
    protocol: str = Field(default="http", description="Protocol (http, https, ws, wss)")
    description: str = Field(default="", description="Endpoint description")
    auth_required: bool = Field(default=True, description="Whether authentication is required")
    auth_type: str = Field(default="bearer", description="Authentication type")
    rate_limit: Optional[int] = Field(None, description="Requests per minute limit")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")


class Capability(BaseModel):
    """
    A single capability that an agent offers.
    
    This is the core unit of discovery - agents register capabilities,
    and other agents search for capabilities they need.
    """
    name: str = Field(..., description="Unique name for this capability")
    type: str = Field(..., description="Type of capability")
    description: str = Field(..., description="Human-readable description")
    version: str = Field(default="1.0.0", description="Capability version")
    
    # I/O schemas (as raw dicts for flexibility)
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="Expected input format")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="Expected output format")
    
    # Pricing and limits
    pricing: CapabilityPricing = Field(default_factory=lambda: CapabilityPricing(), description="Pricing configuration")
    
    # Performance hints
    estimated_latency_ms: Optional[int] = Field(None, description="Estimated latency in milliseconds")
    max_concurrent_requests: int = Field(default=10, description="Max concurrent requests")
    
    # Tags for discovery
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    categories: list[str] = Field(default_factory=list, description="High-level categories")
    
    # Requirements
    requires_auth: bool = Field(default=True, description="Whether capability requires authentication")
    required_permissions: list[str] = Field(default_factory=list, description="Required permissions")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Capability name cannot be empty")
        return v.strip().lower().replace(' ', '_')
    
    @field_validator('input_schema', 'output_schema', mode='before')
    @classmethod
    def validate_schema(cls, v):
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        return {}
    
    def matches_query(self, query: str, threshold: float = 0.5) -> float:
        """
        Check if this capability matches a natural language query.
        Returns a similarity score between 0 and 1.
        """
        query_lower = query.lower().strip()
        score = 0.0

        # Normalize: replace spaces with underscores for name comparison
        query_underscore = query_lower.replace(" ", "_")
        name_lower = self.name.lower()

        # Check name match (exact or substring, with space or underscore)
        if query_lower in name_lower or query_underscore in name_lower:
            score += 0.4
        elif name_lower in query_lower:
            score += 0.3

        # Check description match
        desc_lower = self.description.lower()
        if query_lower in desc_lower:
            score += 0.3
        else:
            # Check word-level overlap
            query_words = set(query_lower.split())
            desc_words = set(desc_lower.replace("_", " ").split())
            overlap = query_words & desc_words
            if overlap:
                score += min(0.3, 0.1 * len(overlap))

        # Check tags
        for tag in self.tags:
            tag_lower = tag.lower()
            if query_lower in tag_lower or query_underscore in tag_lower:
                score += 0.2
                break
            # Check word-level tag match
            tag_words = set(tag_lower.replace("_", " ").split())
            query_words = set(query_lower.split())
            if tag_words & query_words:
                score += 0.15
                break

        # Check categories
        for cat in self.categories:
            if query_lower in cat.lower():
                score += 0.1
                break

        return min(score, 1.0)


class TrustMetrics(BaseModel):
    """Trust and reputation metrics for an agent."""
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall trust score (0-1)")
    interaction_count: int = Field(default=0, description="Total number of interactions")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Successful interactions / total")
    average_latency_ms: float = Field(default=0.0, description="Average response latency")
    positive_feedback: int = Field(default=0, description="Positive feedback count")
    negative_feedback: int = Field(default=0, description="Negative feedback count")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")
    verified_identity: bool = Field(default=False, description="Whether identity is verified")
    
    def update_on_success(self, latency_ms: float):
        """Update metrics after a successful interaction."""
        self.interaction_count += 1
        self.success_rate = (
            (self.success_rate * (self.interaction_count - 1) + 1.0) / self.interaction_count
        )
        self.average_latency_ms = (
            (self.average_latency_ms * (self.interaction_count - 1) + latency_ms) / self.interaction_count
        )
        self.last_interaction = datetime.now(timezone.utc)
        self._recalculate_score()
    
    def update_on_failure(self):
        """Update metrics after a failed interaction."""
        self.interaction_count += 1
        self.success_rate = (
            self.success_rate * (self.interaction_count - 1) / self.interaction_count
        )
        self.last_interaction = datetime.now(timezone.utc)
        self._recalculate_score()
    
    def add_feedback(self, positive: bool):
        """Add user feedback."""
        if positive:
            self.positive_feedback += 1
        else:
            self.negative_feedback += 1
        self._recalculate_score()
    
    def _recalculate_score(self):
        """Recalculate overall trust score."""
        # Weighted combination of factors
        weights = {
            'success_rate': 0.4,
            'feedback': 0.3,
            'recency': 0.2,
            'volume': 0.1,
        }
        
        # Feedback score
        total_feedback = self.positive_feedback + self.negative_feedback
        feedback_score = 0.5
        if total_feedback > 0:
            feedback_score = self.positive_feedback / total_feedback
        
        # Recency score (decays over time)
        recency_score = 1.0
        if self.last_interaction:
            days_since = (datetime.now(timezone.utc) - self.last_interaction).days
            recency_score = max(0.1, 1.0 - (days_since * 0.05))
        
        # Volume score (more interactions = more confidence)
        volume_score = min(1.0, self.interaction_count / 100)
        
        self.score = (
            weights['success_rate'] * self.success_rate +
            weights['feedback'] * feedback_score +
            weights['recency'] * recency_score +
            weights['volume'] * volume_score
        )


class AgentManifest(BaseModel):
    """
    Complete agent manifest - the "phonebook entry" for an agent.
    
    This is what gets published to the registry for discovery.
    """
    # Identity
    identity: 'AgentIdentity' = Field(..., description="Agent's identity")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Detailed description of the agent")
    version: str = Field(default="1.0.0", description="Agent version")
    
    # Capabilities
    capabilities: list[Capability] = Field(default_factory=list, description="List of capabilities")
    
    # Network
    endpoints: list[ServiceEndpoint] = Field(default_factory=list, description="Service endpoints")
    
    # Tags for discovery
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    
    # Trust
    trust_metrics: TrustMetrics = Field(default_factory=TrustMetrics, description="Trust metrics")
    
    # Policy
    max_delegation_depth: int = Field(default=3, description="Max delegation depth allowed")
    allowed_delegation_targets: list[str] = Field(default_factory=list, description="Allowed delegation targets")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    
    def get_capability(self, name: str) -> Optional[Capability]:
        """Get a capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None
    
    def find_capabilities(self, query: str, threshold: float = 0.3) -> list[tuple[Capability, float]]:
        """Find capabilities matching a query, returning (capability, score) pairs."""
        results = []
        for cap in self.capabilities:
            score = cap.matches_query(query, threshold)
            if score >= threshold:
                results.append((cap, score))
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def to_json(self) -> str:
        """Serialize manifest to JSON."""
        return self.model_dump_json()
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentManifest':
        """Deserialize manifest from JSON."""
        return cls.model_validate_json(json_str)


# Forward reference resolution
from oai_network.core.identity.models import AgentIdentity
AgentManifest.model_rebuild()