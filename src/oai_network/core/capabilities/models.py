"""
Capability Models

Data models for agent capabilities and manifests.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
import json


class CapabilityType(str, Enum):
    """Types of capabilities an agent can offer."""
    # Data processing
    CODE_ANALYSIS = "code_analysis"
    DATA_ANALYSIS = "data_analysis"
    TEXT_PROCESSING = "text_processing"
    IMAGE_PROCESSING = "image_processing"
    AUDIO_PROCESSING = "audio_processing"
    
    # Code operations
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DEBUGGING = "debugging"
    
    # Information retrieval
    SEARCH = "search"
    RESEARCH = "research"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    
    # System operations
    FILE_OPERATIONS = "file_operations"
    SHELL_COMMANDS = "shell_commands"
    API_INTEGRATION = "api_integration"
    DATABASE_QUERY = "database_query"
    
    # AI/ML operations
    MODEL_INFERENCE = "model_inference"
    MODEL_TRAINING = "model_training"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    
    # Coordination
    TASK_DELEGATION = "task_delegation"
    WORKFLOW_ORCHESTRATION = "workflow_orchestration"
    AGENT_COORDINATION = "agent_coordination"
    
    # Custom/extensible
    CUSTOM = "custom"


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
    auth_required: bool = Field(default=True, description="Whether authentication is required")
    auth_type: str = Field(default="bearer", description="Authentication type")
    rate_limit: Optional[int] = Field(None, description="Requests per minute limit")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")


class InputSchema(BaseModel):
    """JSON Schema for capability input validation."""
    type: str = Field(default="object", description="Schema type")
    properties: dict[str, Any] = Field(default_factory=dict, description="Property definitions")
    required: list[str] = Field(default_factory=list, description="Required property names")
    additional_properties: bool = Field(default=False, description="Allow additional properties")
    
    def validate(self, data: dict) -> tuple[bool, list[str]]:
        """Validate input data against this schema."""
        import jsonschema
        try:
            jsonschema.validate(instance=data, schema=self.model_dump())
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]


class OutputSchema(BaseModel):
    """JSON Schema for capability output validation."""
    type: str = Field(default="object", description="Schema type")
    properties: dict[str, Any] = Field(default_factory=dict, description="Property definitions")
    required: list[str] = Field(default_factory=list, description="Required property names")


class Capability(BaseModel):
    """
    A single capability that an agent offers.
    
    This is the core unit of discovery - agents register capabilities,
    and other agents search for capabilities they need.
    """
    name: str = Field(..., description="Unique name for this capability")
    type: CapabilityType = Field(..., description="Type of capability")
    description: str = Field(..., description="Human-readable description")
    version: str = Field(default="1.0.0", description="Capability version")
    
    # I/O schemas
    input_schema: InputSchema = Field(default_factory=InputSchema, description="Expected input format")
    output_schema: OutputSchema = Field(default_factory=OutputSchema, description="Expected output format")
    
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
    
    def matches_query(self, query: str, threshold: float = 0.5) -> float:
        """
        Check if this capability matches a natural language query.
        Returns a similarity score between 0 and 1.
        """
        query_lower = query.lower()
        score = 0.0
        
        # Check name match
        if query_lower in self.name.lower():
            score += 0.4
        
        # Check description match
        if query_lower in self.description.lower():
            score += 0.3
        
        # Check tags
        for tag in self.tags:
            if query_lower in tag.lower():
                score += 0.2
                break
        
        # Check categories
        for cat in self.categories:
            if query_lower in cat.lower():
                score += 0.1
                break
        
        return min(score, 1.0)


class TrustMetrics(BaseModel):
    """Trust and reputation metrics for an agent."""
    overall_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall trust score (0-1)")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Successful interactions / total")
    avg_latency_ms: float = Field(default=0.0, description="Average response latency")
    total_interactions: int = Field(default=0, description="Total number of interactions")
    positive_feedback: int = Field(default=0, description="Positive feedback count")
    negative_feedback: int = Field(default=0, description="Negative feedback count")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")
    verified_identity: bool = Field(default=False, description="Whether identity is verified")
    
    def update_on_success(self, latency_ms: float):
        """Update metrics after a successful interaction."""
        self.total_interactions += 1
        self.success_rate = (
            (self.success_rate * (self.total_interactions - 1) + 1.0) / self.total_interactions
        )
        self.avg_latency_ms = (
            (self.avg_latency_ms * (self.total_interactions - 1) + latency_ms) / self.total_interactions
        )
        self.last_interaction = datetime.now(timezone.utc)
        self._recalculate_score()
    
    def update_on_failure(self):
        """Update metrics after a failed interaction."""
        self.total_interactions += 1
        self.success_rate = (
            self.success_rate * (self.total_interactions - 1) / self.total_interactions
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
        volume_score = min(1.0, self.total_interactions / 100)
        
        self.overall_score = (
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
    agent_did: str = Field(..., description="Agent's decentralized identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Detailed description of the agent")
    version: str = Field(default="1.0.0", description="Agent version")
    
    # Capabilities
    capabilities: list[Capability] = Field(default_factory=list, description="List of capabilities")
    
    # Network
    endpoints: list[ServiceEndpoint] = Field(default_factory=list, description="Service endpoints")
    
    # Trust
    trust_metrics: TrustMetrics = Field(default_factory=TrustMetrics, description="Trust metrics")
    
    # Policy
    max_delegation_depth: int = Field(default=3, description="Max delegation depth allowed")
    allowed_delegation_targets: list[str] = Field(default_factory=list, description="Allowed delegation targets")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('agent_did')
    @classmethod
    def validate_did(cls, v: str) -> str:
        if not v.startswith('did:'):
            raise ValueError('Agent DID must start with "did:"')
        return v
    
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
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentManifest':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentManifest':
        """Create from dictionary."""
        return cls(**data)