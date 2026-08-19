"""
Gateway Models

Data models for the API gateway.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class GatewayRequest(BaseModel):
    """Incoming request to the gateway."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Request path")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    query_params: dict[str, str] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Any] = Field(None, description="Request body")
    client_ip: Optional[str] = Field(None, description="Client IP address")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Extracted context
    agent_did: Optional[str] = Field(None, description="Authenticated agent DID")
    capability_name: Optional[str] = Field(None, description="Target capability")
    delegation_depth: int = Field(default=0, description="Current delegation depth")
    is_delegation: bool = Field(default=False, description="Whether this is a delegated request")
    requester_did: Optional[str] = Field(None, description="Original requester DID")


class GatewayResponse(BaseModel):
    """Response from the gateway."""
    request_id: str = Field(..., description="Original request ID")
    status_code: int = Field(..., description="HTTP status code")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Optional[Any] = Field(None, description="Response body")
    latency_ms: float = Field(default=0.0, description="Total latency")
    upstream_latency_ms: Optional[float] = Field(None, description="Upstream latency")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = Field(None, description="Error message if failed")


class RouteRule(BaseModel):
    """Routing rule for the gateway."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Rule name")
    path_pattern: str = Field(..., description="Path pattern to match (regex)")
    methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"], description="Allowed HTTP methods")
    target_url: str = Field(..., description="Target service URL")
    target_type: str = Field(default="http", description="Target type (http, grpc, ws)")
    
    # Policy
    policy_enabled: bool = Field(default=True, description="Whether to enforce policy")
    required_capability: Optional[str] = Field(None, description="Required capability name")
    required_trust_score: float = Field(default=0.0, description="Minimum trust score")
    require_verified: bool = Field(default=False, description="Require verified identity")
    
    # Rate limiting
    rate_limit_rpm: Optional[int] = Field(None, description="Requests per minute limit")
    rate_limit_burst: Optional[int] = Field(None, description="Burst allowance")
    
    # Timeouts
    connect_timeout_ms: int = Field(default=5000, description="Connection timeout")
    request_timeout_ms: int = Field(default=30000, description="Request timeout")
    
    # Retry
    max_retries: int = Field(default=3, description="Maximum retries")
    retry_on: list[int] = Field(default_factory=lambda: [500, 502, 503, 504], description="Status codes to retry")
    
    # Load balancing
    load_balancer: str = Field(default="round_robin", description="Load balancing strategy")
    
    # Metadata
    priority: int = Field(default=0, description="Rule priority (higher = first)")
    enabled: bool = Field(default=True, description="Whether rule is active")
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def matches(self, request: GatewayRequest) -> bool:
        """Check if rule matches a request."""
        if not self.enabled:
            return False
        
        if request.method not in self.methods:
            return False
        
        import re
        return bool(re.match(self.path_pattern, request.path))


class GatewayConfig(BaseModel):
    """Gateway configuration."""
    host: str = Field(default="0.0.0.0", description="Bind host")
    port: int = Field(default=8080, description="Bind port")
    workers: int = Field(default=4, description="Worker processes")
    
    # Routes and upstreams (for testing)
    routes: list = Field(default_factory=list, description="Route rules")
    upstreams: dict = Field(default_factory=dict, description="Upstream services")
    default_timeout: float = Field(default=30.0, description="Default timeout")
    max_request_size: int = Field(default=1024 * 1024, description="Max request size")
    
    # TLS
    tls_enabled: bool = Field(default=False, description="Enable TLS")
    tls_cert_path: Optional[str] = Field(None, description="TLS certificate path")
    tls_key_path: Optional[str] = Field(None, description="TLS key path")
    
    # Policy
    policy_path: Optional[str] = Field(None, description="Path to policy file/directory")
    default_policy: str = Field(default="default", description="Default policy name")
    
    # Discovery
    discovery_url: Optional[str] = Field(None, description="Discovery service URL")
    registry_url: Optional[str] = Field(None, description="Registry service URL")
    
    # Rate limiting (global defaults)
    global_rate_limit_rpm: int = Field(default=1000, description="Global requests per minute")
    global_rate_limit_burst: int = Field(default=100, description="Global burst allowance")
    
    # Timeouts
    default_connect_timeout_ms: int = Field(default=5000)
    default_request_timeout_ms: int = Field(default=30000)
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    access_log: bool = Field(default=True, description="Enable access logging")
    access_log_format: str = Field(default="json", description="Access log format")
    
    # Metrics
    metrics_enabled: bool = Field(default=True, description="Enable metrics")
    metrics_path: str = Field(default="/metrics", description="Metrics endpoint path")
    
    # Health checks
    health_check_path: str = Field(default="/health", description="Health check path")
    health_check_interval_seconds: int = Field(default=30, description="Health check interval")
    
    # CORS
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="Allowed origins")
    cors_methods: list[str] = Field(default_factory=lambda: ["*"], description="Allowed methods")
    cors_headers: list[str] = Field(default_factory=lambda: ["*"], description="Allowed headers")
    
    # Request limits
    max_request_size_mb: int = Field(default=10, description="Max request size in MB")
    max_response_size_mb: int = Field(default=50, description="Max response size in MB")


class UpstreamService(BaseModel):
    """Upstream service definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Service name")
    url: str = Field(..., description="Service URL")
    weight: int = Field(default=1, description="Load balancing weight")
    healthy: bool = Field(default=True, description="Health status")
    last_health_check: Optional[datetime] = Field(None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def is_healthy(self, max_age_seconds: int = 60) -> bool:
        """Check if service is considered healthy."""
        if not self.healthy:
            return False
        if self.last_health_check is None:
            return True  # Unknown, assume healthy
        age = (datetime.now(timezone.utc) - self.last_health_check).total_seconds()
        return age <= max_age_seconds


class LoadBalancerStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"


class LoadBalancer:
    """Load balancing strategies."""
    
    @staticmethod
    def round_robin(services: list[UpstreamService], state: dict) -> Optional[UpstreamService]:
        """Round-robin load balancing."""
        healthy = [s for s in services if s.is_healthy()]
        if not healthy:
            return None
        
        index = state.get('rr_index', 0) % len(healthy)
        state['rr_index'] = index + 1
        return healthy[index]
    
    @staticmethod
    def weighted_round_robin(services: list[UpstreamService], state: dict) -> Optional[UpstreamService]:
        """Weighted round-robin load balancing."""
        healthy = [s for s in services if s.is_healthy()]
        if not healthy:
            return None
        
        # Build weighted list
        weighted = []
        for s in healthy:
            weighted.extend([s] * s.weight)
        
        if not weighted:
            return None
        
        index = state.get('wrr_index', 0) % len(weighted)
        state['wrr_index'] = index + 1
        return weighted[index]
    
    @staticmethod
    def least_connections(services: list[UpstreamService], state: dict) -> Optional[UpstreamService]:
        """Least connections load balancing."""
        healthy = [s for s in services if s.is_healthy()]
        if not healthy:
            return None
        
        connections = state.get('connections', {})
        min_conn = min(connections.get(s.id, 0) for s in healthy)
        candidates = [s for s in healthy if connections.get(s.id, 0) == min_conn]
        return candidates[0]
    
    @staticmethod
    def random(services: list[UpstreamService], state: dict) -> Optional[UpstreamService]:
        """Random load balancing."""
        import random
        healthy = [s for s in services if s.is_healthy()]
        if not healthy:
            return None
        return random.choice(healthy)