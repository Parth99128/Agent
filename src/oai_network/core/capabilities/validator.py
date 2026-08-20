"""
Manifest Validator

Validates agent manifests against schemas and business rules.
"""

from typing import Optional
from dataclasses import dataclass
from .models import AgentManifest, Capability, ServiceEndpoint


@dataclass
class ValidationResult:
    """Result of manifest validation."""
    valid: bool
    errors: list[str]
    warnings: list[str]


class ManifestValidator:
    """
    Validates agent manifests for correctness and completeness.
    """
    
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def validate(self, manifest: AgentManifest) -> ValidationResult:
        """
        Validate a complete agent manifest.
        
        Returns:
            ValidationResult with valid, errors, warnings
        """
        self.errors = []
        self.warnings = []
        
        # Validate identity
        self._validate_identity(manifest)
        
        # Validate capabilities
        self._validate_capabilities(manifest)
        
        # Validate endpoints
        self._validate_endpoints(manifest)
        
        # Validate trust metrics
        self._validate_trust(manifest)
        
        # Validate policy settings
        self._validate_policy(manifest)
        
        return ValidationResult(
            valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def _validate_identity(self, manifest: AgentManifest):
        """Validate identity fields."""
        if not manifest.identity or not manifest.identity.did or not manifest.identity.did.startswith('did:'):
            self.errors.append("Invalid agent DID: must start with 'did:'")
        
        if not manifest.name or not manifest.name.strip():
            self.errors.append("Agent name is required")
        
        if not manifest.description or not manifest.description.strip():
            self.warnings.append("Agent description is empty")
    
    def _validate_capabilities(self, manifest: AgentManifest):
        """Validate capabilities list."""
        if not manifest.capabilities:
            self.errors.append("Agent has no capabilities registered")
            return
        
        seen_names = set()
        for i, cap in enumerate(manifest.capabilities):
            # Check for duplicate names
            if cap.name in seen_names:
                self.errors.append(f"Duplicate capability name: {cap.name}")
            seen_names.add(cap.name)
            
            # Validate capability
            self._validate_capability(cap, i)
    
    def _validate_capability(self, cap: Capability, index: int):
        """Validate a single capability."""
        prefix = f"Capability[{index}]"
        
        if not cap.name:
            self.errors.append(f"{prefix}: Name is required")
        
        if not cap.description:
            self.warnings.append(f"{prefix}: Description is empty")
        
        # Validate input schema
        if isinstance(cap.input_schema, dict):
            if cap.input_schema.get("type") != "object":
                self.warnings.append(f"{prefix}: Input schema should be type 'object'")
        else:
            self.errors.append(f"{prefix}: Input schema must be a dictionary")
        
        # Validate pricing
        if cap.pricing.model != "free" and cap.pricing.price_per_call is None:
            self.errors.append(f"{prefix}: Price per call required for paid capabilities")
        
        if cap.pricing.price_per_call is not None and cap.pricing.price_per_call < 0:
            self.errors.append(f"{prefix}: Price per call cannot be negative")
        
        # Validate limits
        if cap.max_concurrent_requests <= 0:
            self.errors.append(f"{prefix}: Max concurrent requests must be positive")
        
        if cap.estimated_latency_ms is not None and cap.estimated_latency_ms < 0:
            self.errors.append(f"{prefix}: Estimated latency cannot be negative")
    
    def _validate_endpoints(self, manifest: AgentManifest):
        """Validate service endpoints."""
        if not manifest.endpoints:
            self.errors.append("No service endpoints defined")
            return
        
        for i, endpoint in enumerate(manifest.endpoints):
            if not endpoint.url:
                self.errors.append(f"Endpoint[{i}]: URL is required")
            
            if not endpoint.url.startswith(('http://', 'https://', 'ws://', 'wss://')):
                self.errors.append(f"Endpoint[{i}]: URL must use http, https, ws, or wss protocol")
            
            if endpoint.timeout_seconds <= 0:
                self.errors.append(f"Endpoint[{i}]: Timeout must be positive")
            
            if endpoint.rate_limit is not None and endpoint.rate_limit <= 0:
                self.errors.append(f"Endpoint[{i}]: Rate limit must be positive")
            
            # Validate protocol
            valid_protocols = ["http", "https", "grpc", "websocket", "a2a", "mcp"]
            if endpoint.protocol not in valid_protocols:
                self.errors.append(f"Endpoint[{i}]: Invalid protocol '{endpoint.protocol}'. Must be one of: {', '.join(valid_protocols)}")
    
    def _validate_trust(self, manifest: AgentManifest):
        """Validate trust metrics."""
        trust = manifest.trust_metrics
        
        if not 0.0 <= trust.score <= 1.0:
            self.errors.append("Trust score must be between 0 and 1")
        
        if not 0.0 <= trust.success_rate <= 1.0:
            self.errors.append("Trust success_rate must be between 0 and 1")
        
        if trust.average_latency_ms < 0:
            self.errors.append("Trust average_latency_ms cannot be negative")
        
        if trust.interaction_count < 0:
            self.errors.append("Trust interaction_count cannot be negative")
    
    def _validate_policy(self, manifest: AgentManifest):
        """Validate policy settings."""
        if manifest.max_delegation_depth < 0:
            self.errors.append("Max delegation depth cannot be negative")
        
        if manifest.max_delegation_depth > 10:
            self.warnings.append("Max delegation depth > 10 may cause issues")
    
    def validate_capability_schema(self, capability: Capability) -> tuple[bool, list[str]]:
        """Validate a capability's input/output schemas."""
        errors = []
        
        # Validate input schema
        try:
            import jsonschema
            # Test with empty object
            jsonschema.validate(instance={}, schema=capability.input_schema.model_dump())
        except jsonschema.SchemaError as e:
            errors.append(f"Invalid input schema: {str(e)}")
        except Exception:
            # Empty object might not be valid, that's OK
            pass
        
        # Validate output schema
        try:
            jsonschema.validate(instance={}, schema=capability.output_schema.model_dump())
        except jsonschema.SchemaError as e:
            errors.append(f"Invalid output schema: {str(e)}")
        except Exception:
            pass
        
        return len(errors) == 0, errors