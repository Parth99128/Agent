"""
Tests for the capabilities module.
"""

import pytest
from oai_network.core.capabilities.models import (
    Capability, CapabilityPricing, ServiceEndpoint, AgentManifest, TrustMetrics
)
from oai_network.core.capabilities.matcher import CapabilityMatcher
from oai_network.core.capabilities.validator import ManifestValidator


class TestCapabilityModels:
    """Tests for capability data models."""
    
    def test_capability_creation(self):
        """Test creating a Capability."""
        capability = Capability(
            name="test_capability",
            description="A test capability",
            type="test",
            input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
            tags=["test", "example"]
        )
        
        assert capability.name == "test_capability"
        assert capability.type == "test"
        assert "input" in capability.input_schema["properties"]
        assert "output" in capability.output_schema["properties"]
        assert "test" in capability.tags
    
    def test_capability_pricing(self):
        """Test capability pricing models."""
        # Free pricing
        free_pricing = CapabilityPricing(model="free")
        assert free_pricing.model == "free"
        
        # Per call pricing
        per_call = CapabilityPricing(
            model="per_call",
            price_per_call=0.01,
            currency="USD"
        )
        assert per_call.price_per_call == 0.01
        
        # Per token pricing
        per_token = CapabilityPricing(
            model="per_token",
            price_per_token=0.0001,
            currency="USD"
        )
        assert per_token.price_per_token == 0.0001
    
    def test_service_endpoint(self):
        """Test service endpoint creation."""
        endpoint = ServiceEndpoint(
            url="http://localhost:8000/a2a",
            protocol="a2a",
            description="A2A endpoint"
        )
        
        assert endpoint.url == "http://localhost:8000/a2a"
        assert endpoint.protocol == "a2a"
    
    def test_agent_manifest(self, sample_manifest):
        """Test agent manifest creation."""
        assert sample_manifest.name == "Test Agent"
        assert len(sample_manifest.capabilities) == 1
        assert len(sample_manifest.endpoints) == 1
        assert sample_manifest.get_capability("text_summarization") is not None
        assert sample_manifest.get_capability("nonexistent") is None
    
    def test_trust_metrics(self):
        """Test trust metrics."""
        metrics = TrustMetrics(
            score=0.85,
            interaction_count=100,
            success_rate=0.95,
            average_latency_ms=150.0
        )
        
        assert metrics.score == 0.85
        assert metrics.interaction_count == 100
        assert metrics.success_rate == 0.95


class TestCapabilityMatcher:
    """Tests for CapabilityMatcher."""
    
    def test_match_exact(self, sample_manifest):
        """Test exact capability matching."""
        matcher = CapabilityMatcher()
        results = matcher.match(
            manifests=[sample_manifest],
            query="text_summarization"
        )
        
        assert len(results) == 1
        assert results[0].agent_did == sample_manifest.identity.did
        assert results[0].relevance_score > 0
    
    def test_match_by_type(self, sample_manifest):
        """Test matching by capability type."""
        matcher = CapabilityMatcher()
        results = matcher.match(
            manifests=[sample_manifest],
            capability_type="nlp"
        )
        
        assert len(results) == 1
    
    def test_match_by_tags(self, sample_manifest):
        """Test matching by tags."""
        matcher = CapabilityMatcher()
        results = matcher.match(
            manifests=[sample_manifest],
            tags=["nlp"]
        )
        
        assert len(results) == 1
    
    def test_match_no_results(self, sample_manifest):
        """Test matching with no results."""
        matcher = CapabilityMatcher()
        results = matcher.match(
            manifests=[sample_manifest],
            query="nonexistent_capability"
        )
        
        assert len(results) == 0
    
    def test_rank_by_trust(self, sample_manifest):
        """Test ranking by trust score."""
        matcher = CapabilityMatcher()
        
        # Create another manifest with lower trust
        from oai_network.core.identity.generator import IdentityGenerator
        generator = IdentityGenerator()
        identity2 = generator.generate_identity(name="Low Trust Agent", key_type="Ed25519")
        
        manifest2 = AgentManifest(
            identity=identity2.identity,
            name="Low Trust Agent",
            description="Low trust agent",
            version="1.0.0",
            capabilities=sample_manifest.capabilities,
            endpoints=sample_manifest.endpoints,
        )
        manifest2.trust_metrics.score = 0.3
        
        sample_manifest.trust_metrics.score = 0.9
        
        results = matcher.match(
            manifests=[sample_manifest, manifest2],
            query="text_summarization",
            rank_by="trust"
        )
        
        assert len(results) == 2
        assert results[0].trust_score > results[1].trust_score
    
    def test_rank_by_latency(self, sample_manifest):
        """Test ranking by latency."""
        matcher = CapabilityMatcher()
        
        from oai_network.core.identity.generator import IdentityGenerator
        generator = IdentityGenerator()
        identity2 = generator.generate_identity(name="Fast Agent", key_type="Ed25519")
        
        manifest2 = AgentManifest(
            identity=identity2.identity,
            name="Fast Agent",
            description="Fast agent",
            version="1.0.0",
            capabilities=sample_manifest.capabilities,
            endpoints=sample_manifest.endpoints,
        )
        manifest2.trust_metrics.average_latency_ms = 50.0
        
        sample_manifest.trust_metrics.average_latency_ms = 200.0
        
        results = matcher.match(
            manifests=[sample_manifest, manifest2],
            query="text_summarization",
            rank_by="latency"
        )
        
        assert len(results) == 2
        assert results[0].average_latency_ms < results[1].average_latency_ms


class TestManifestValidator:
    """Tests for ManifestValidator."""
    
    def test_validate_valid_manifest(self, sample_manifest):
        """Test validating a valid manifest."""
        validator = ManifestValidator()
        result = validator.validate(sample_manifest)
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_validate_missing_name(self, sample_manifest):
        """Test validating manifest with missing name."""
        validator = ManifestValidator()
        sample_manifest.name = ""
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("name" in e.lower() for e in result.errors)
    
    def test_validate_no_capabilities(self, sample_manifest):
        """Test validating manifest with no capabilities."""
        validator = ManifestValidator()
        sample_manifest.capabilities = []
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("capabilit" in e.lower() for e in result.errors)
    
    def test_validate_no_endpoints(self, sample_manifest):
        """Test validating manifest with no endpoints."""
        validator = ManifestValidator()
        sample_manifest.endpoints = []
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("endpoint" in e.lower() for e in result.errors)
    
    def test_validate_duplicate_capability_names(self, sample_manifest):
        """Test validating manifest with duplicate capability names."""
        validator = ManifestValidator()
        
        # Add duplicate capability
        duplicate_cap = Capability(
            name="text_summarization",  # Same name
            description="Duplicate",
            type="nlp",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        sample_manifest.capabilities.append(duplicate_cap)
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("duplicate" in e.lower() for e in result.errors)
    
    def test_validate_invalid_schema(self, sample_manifest):
        """Test validating manifest with invalid schema."""
        validator = ManifestValidator()
        
        # Make schema invalid
        sample_manifest.capabilities[0].input_schema = "not a dict"
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("schema" in e.lower() for e in result.errors)
    
    def test_validate_endpoint_protocols(self, sample_manifest):
        """Test validating endpoint protocols."""
        validator = ManifestValidator()
        
        # Add invalid protocol
        sample_manifest.endpoints[0].protocol = "invalid_protocol"
        
        result = validator.validate(sample_manifest)
        
        assert result.valid is False
        assert any("protocol" in e.lower() for e in result.errors)