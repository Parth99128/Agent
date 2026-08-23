"""
Tests for the registry module.
"""

import pytest
from oai_network.registry.models import (
    RegistryEntry, RegistrationRequest, RegistrationResponse,
    HeartbeatRequest, HeartbeatResponse, HealthStatus, RegistryConfig
)
from oai_network.registry.service import RegistryService


class TestRegistryModels:
    """Tests for registry data models."""
    
    def test_registry_entry_creation(self, sample_registry_entry):
        """Test creating a RegistryEntry."""
        assert sample_registry_entry.agent_did.startswith("did:oai:")
        assert sample_registry_entry.manifest is not None
        assert sample_registry_entry.status == "active"
        assert sample_registry_entry.registered_at is not None
        assert sample_registry_entry.last_heartbeat is not None
    
    def test_registration_request(self, sample_manifest):
        """Test creating a RegistrationRequest."""
        request = RegistrationRequest(
            manifest=sample_manifest,
            ttl_seconds=3600
        )
        
        assert request.manifest == sample_manifest
        assert request.ttl_seconds == 3600
    
    def test_registration_response_success(self):
        """Test successful RegistrationResponse."""
        response = RegistrationResponse(
            success=True,
            agent_did="did:oai:test123",
            registration_id="reg-123",
            expires_at=None
        )
        
        assert response.success is True
        assert response.agent_did == "did:oai:test123"
        assert response.registration_id == "reg-123"
    
    def test_registration_response_failure(self):
        """Test failed RegistrationResponse."""
        response = RegistrationResponse(
            success=False,
            agent_did="",
            registration_id="",
            error="Agent already registered"
        )
        
        assert response.success is False
        assert response.error == "Agent already registered"
    
    def test_heartbeat_request(self):
        """Test creating a HeartbeatRequest."""
        request = HeartbeatRequest(
            agent_did="did:oai:test123",
            status=HealthStatus.HEALTHY,
            metadata={"load": 0.5, "active_tasks": 3}
        )
        
        assert request.agent_did == "did:oai:test123"
        assert request.status == HealthStatus.HEALTHY
        assert request.metadata["load"] == 0.5
    
    def test_heartbeat_response(self):
        """Test creating a HeartbeatResponse."""
        response = HeartbeatResponse(
            success=True,
            agent_did="did:oai:test123",
            next_heartbeat_interval=60
        )
        
        assert response.success is True
        assert response.next_heartbeat_interval == 60
    
    def test_health_statuses(self):
        """Test HealthStatus enum."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
    
    def test_registry_config(self):
        """Test RegistryConfig."""
        config = RegistryConfig(
            database_url="sqlite:///test.db",
            default_ttl_seconds=3600,
            cleanup_interval_seconds=300,
            max_heartbeat_missed=3
        )
        
        assert config.database_url == "sqlite:///test.db"
        assert config.default_ttl_seconds == 3600
        assert config.cleanup_interval_seconds == 300
        assert config.max_heartbeat_missed == 3


class TestRegistryService:
    """Tests for RegistryService."""
    
    @pytest.mark.asyncio
    async def test_register_agent(self, registry_service, sample_manifest):
        """Test registering an agent."""
        response = await registry_service.register_agent(sample_manifest)
        
        assert response.success is True
        assert response.agent_did == sample_manifest.identity.did
        assert response.registration_id is not None
    
    @pytest.mark.asyncio
    async def test_register_duplicate_agent(self, registry_service, sample_manifest):
        """Test registering duplicate agent fails."""
        await registry_service.register_agent(sample_manifest)
        response = await registry_service.register_agent(sample_manifest)
        
        assert response.success is False
        assert "already registered" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_get_agent(self, registry_service, sample_manifest):
        """Test getting agent by DID."""
        await registry_service.register_agent(sample_manifest)
        
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        
        assert entry is not None
        assert entry.agent_did == sample_manifest.identity.did
        assert entry.manifest.name == sample_manifest.name
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, registry_service):
        """Test getting nonexistent agent."""
        entry = await registry_service.get_agent("did:oai:nonexistent")
        
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, registry_service, sample_manifest):
        """Test agent heartbeat."""
        await registry_service.register_agent(sample_manifest)
        
        request = HeartbeatRequest(
            agent_did=sample_manifest.identity.did,
            status=HealthStatus.HEALTHY,
            metadata={"load": 0.3}
        )
        
        response = await registry_service.heartbeat(request)
        
        assert response.success is True
        assert response.next_heartbeat_interval > 0
        
        # Verify last_heartbeat updated
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        assert entry.last_heartbeat is not None
    
    @pytest.mark.asyncio
    async def test_heartbeat_unregistered_agent(self, registry_service):
        """Test heartbeat for unregistered agent."""
        request = HeartbeatRequest(
            agent_did="did:oai:unregistered",
            status=HealthStatus.HEALTHY
        )
        
        response = await registry_service.heartbeat(request)
        
        assert response.success is False
        assert "not registered" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_heartbeat_updates_status(self, registry_service, sample_manifest):
        """Test heartbeat updates health status."""
        await registry_service.register_agent(sample_manifest)
        
        # Send degraded status
        request = HeartbeatRequest(
            agent_did=sample_manifest.identity.did,
            status=HealthStatus.DEGRADED,
            metadata={"reason": "high load"}
        )
        
        response = await registry_service.heartbeat(request)
        
        assert response.success is True
        
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        assert entry.status == "degraded"
    
    @pytest.mark.asyncio
    async def test_unregister_agent(self, registry_service, sample_manifest):
        """Test unregistering an agent."""
        await registry_service.register_agent(sample_manifest)
        
        response = await registry_service.unregister_agent(sample_manifest.identity.did)
        
        assert response.success is True
        
        # Verify agent is removed
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_agent(self, registry_service):
        """Test unregistering nonexistent agent."""
        response = await registry_service.unregister_agent("did:oai:nonexistent")
        
        assert response.success is False
        assert "not found" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_list_agents(self, registry_service, sample_manifest):
        """Test listing all agents."""
        await registry_service.register_agent(sample_manifest)
        
        # Add another agent
        from oai_network.core.identity.generator import IdentityGenerator
        generator = IdentityGenerator()
        identity2 = generator.generate_identity(name="Agent 2", key_type="Ed25519")
        
        from oai_network.core.capabilities.models import AgentManifest, ServiceEndpoint, Capability
        manifest2 = AgentManifest(
            identity=identity2.identity,
            name="Agent 2",
            description="Second agent",
            version="1.0.0",
            capabilities=[
                Capability(
                    name="translation",
                    description="Translate text",
                    type="nlp",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"}
                )
            ],
            endpoints=[
                ServiceEndpoint(
                    url="http://localhost:8002/a2a",
                    protocol="a2a"
                )
            ]
        )
        
        await registry_service.register_agent(manifest2)
        
        agents = await registry_service.list_agents()
        
        assert len(agents) == 2
        agent_dids = [a.agent_did for a in agents]
        assert sample_manifest.identity.did in agent_dids
        assert identity2.identity.did in agent_dids
    
    @pytest.mark.asyncio
    async def test_list_agents_with_status_filter(self, registry_service, sample_manifest):
        """Test listing agents with status filter."""
        await registry_service.register_agent(sample_manifest)
        
        # Add degraded agent
        from oai_network.core.identity.generator import IdentityGenerator
        generator = IdentityGenerator()
        identity2 = generator.generate_identity(name="Degraded Agent", key_type="Ed25519")
        
        from oai_network.core.capabilities.models import AgentManifest, ServiceEndpoint, Capability
        manifest2 = AgentManifest(
            identity=identity2.identity,
            name="Degraded Agent",
            description="Degraded agent",
            version="1.0.0",
            capabilities=[
                Capability(
                    name="test",
                    description="Test",
                    type="test",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"}
                )
            ],
            endpoints=[
                ServiceEndpoint(
                    url="http://localhost:8003/a2a",
                    protocol="a2a"
                )
            ]
        )
        
        await registry_service.register_agent(manifest2)
        
        # Set second agent to degraded
        await registry_service.heartbeat(HeartbeatRequest(
            agent_did=identity2.identity.did,
            status=HealthStatus.DEGRADED
        ))
        
        # Filter healthy only
        healthy_agents = await registry_service.list_agents(status=HealthStatus.HEALTHY)
        assert len(healthy_agents) == 1
        assert healthy_agents[0].agent_did == sample_manifest.identity.did
        
        # Filter degraded only
        degraded_agents = await registry_service.list_agents(status=HealthStatus.DEGRADED)
        assert len(degraded_agents) == 1
        assert degraded_agents[0].agent_did == identity2.identity.did
    
    @pytest.mark.asyncio
    async def test_discover_agents(self, registry_service, sample_manifest):
        """Test discovering agents by capability."""
        await registry_service.register_agent(sample_manifest)
        
        results = await registry_service.discover_agents(
            capability="text_summarization",
            max_results=10
        )
        
        assert len(results) == 1
        assert results[0].agent_did == sample_manifest.identity.did
        assert results[0].capability_name == "text_summarization"
    
    @pytest.mark.asyncio
    async def test_discover_agents_no_results(self, registry_service):
        """Test discovering agents with no results."""
        results = await registry_service.discover_agents(
            capability="nonexistent",
            max_results=10
        )
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, registry_service, sample_manifest):
        """Test cleaning up expired registrations."""
        # Register with very short TTL
        request = RegistrationRequest(
            manifest=sample_manifest,
            ttl_seconds=0  # Expired immediately
        )
        
        response = await registry_service.register_agent(sample_manifest)
        assert response.success is True
        
        # Manually expire the entry
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        from datetime import datetime, timezone, timedelta
        entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Run cleanup
        cleaned = await registry_service.cleanup_expired()
        
        assert cleaned >= 1
        
        # Agent should be removed
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_heartbeats(self, registry_service, sample_manifest):
        """Test cleaning up agents with missed heartbeats."""
        await registry_service.register_agent(sample_manifest)
        
        # Manually set last_heartbeat to old
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        from datetime import datetime, timezone, timedelta
        entry.last_heartbeat = datetime.now(timezone.utc) - timedelta(hours=2)
        entry.missed_heartbeats = 5  # Exceeds max of 3
        
        # Run cleanup
        cleaned = await registry_service.cleanup_expired()
        
        assert cleaned >= 1
        
        # Agent should be removed
        entry = await registry_service.get_agent(sample_manifest.identity.did)
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_get_stats(self, registry_service, sample_manifest):
        """Test getting registry statistics."""
        await registry_service.register_agent(sample_manifest)
        
        stats = await registry_service.get_stats()
        
        assert stats["total_agents"] == 1
        assert stats["active_agents"] == 1
        assert stats["healthy_agents"] == 1
        assert stats["degraded_agents"] == 0
        assert stats["unhealthy_agents"] == 0

    @pytest.mark.asyncio
    async def test_registration_discovery_consistency(self, registry_service, sample_manifest):
        """Test that an agent is immediately discoverable after registration.
        
        This test ensures the registration→discovery path is consistent and
        doesn't have timing issues where a newly registered agent isn't found.
        """
        # Register agent
        response = await registry_service.register_agent(sample_manifest)
        assert response.success is True
        agent_did = response.agent_did
        
        # Immediately discover - should find the agent
        results = await registry_service.discover_agents(
            capability="text_summarization",
            max_results=10
        )
        
        assert len(results) == 1
        assert results[0].agent_did == agent_did
        assert results[0].agent_name == sample_manifest.name
        assert results[0].capability_name == "text_summarization"
        assert results[0].trust_score >= 0.0
        assert results[0].verified is True
        
        # Also test with natural language query
        results_nl = await registry_service.discover_agents(
            nl_query="summarize text",
            max_results=10
        )
        
        assert len(results_nl) == 1
        assert results_nl[0].agent_did == agent_did
        
        # Test with trust score filter
        results_trust = await registry_service.discover_agents(
            capability="text_summarization",
            min_trust_score=0.0,
            max_results=10
        )
        
        assert len(results_trust) == 1
        assert results_trust[0].agent_did == agent_did
        
        # Test with verified_only filter
        results_verified = await registry_service.discover_agents(
            capability="text_summarization",
            verified_only=True,
            max_results=10
        )
        
        assert len(results_verified) == 1
        assert results_verified[0].agent_did == agent_did
        assert results_verified[0].verified is True