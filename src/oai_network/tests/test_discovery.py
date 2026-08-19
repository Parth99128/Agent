"""
Tests for the discovery module.
"""

import pytest
from oai_network.core.discovery.models import (
    DiscoveryQuery, DiscoveryResult, RegistryEntry, 
    RegistrationRequest, RegistrationResponse, Heartbeat
)
from oai_network.core.discovery.service import DiscoveryService
from oai_network.core.discovery.cache import DiscoveryCache


class TestDiscoveryModels:
    """Tests for discovery data models."""
    
    def test_discovery_query_creation(self):
        """Test creating a DiscoveryQuery."""
        query = DiscoveryQuery(
            query="text summarization",
            capability_type="nlp",
            tags=["summarization"],
            max_results=10,
            min_trust_score=0.5
        )
        
        assert query.query == "text summarization"
        assert query.capability_type == "nlp"
        assert "summarization" in query.tags
        assert query.max_results == 10
        assert query.min_trust_score == 0.5
    
    def test_discovery_result_creation(self, sample_discovery_result):
        """Test creating a DiscoveryResult."""
        assert sample_discovery_result.agent_did.startswith("did:oai:")
        assert sample_discovery_result.capability_name == "text_summarization"
        assert sample_discovery_result.relevance_score > 0
        assert sample_discovery_result.trust_score >= 0
    
    def test_registry_entry_creation(self, sample_registry_entry):
        """Test creating a RegistryEntry."""
        assert sample_registry_entry.agent_did.startswith("did:oai:")
        assert sample_registry_entry.manifest is not None
        assert sample_registry_entry.status == "active"
        assert sample_registry_entry.registered_at is not None
    
    def test_registration_request(self, sample_manifest):
        """Test creating a RegistrationRequest."""
        request = RegistrationRequest(
            manifest=sample_manifest,
            ttl_seconds=3600
        )
        
        assert request.manifest == sample_manifest
        assert request.ttl_seconds == 3600
    
    def test_registration_response(self):
        """Test creating a RegistrationResponse."""
        response = RegistrationResponse(
            success=True,
            agent_did="did:oai:test123",
            registration_id="reg-123",
            expires_at=None
        )
        
        assert response.success is True
        assert response.agent_did == "did:oai:test123"
    
    def test_heartbeat(self):
        """Test creating a Heartbeat."""
        heartbeat = Heartbeat(
            agent_did="did:oai:test123",
            status="healthy",
            metadata={"load": 0.5}
        )
        
        assert heartbeat.agent_did == "did:oai:test123"
        assert heartbeat.status == "healthy"
        assert heartbeat.metadata["load"] == 0.5


class TestDiscoveryService:
    """Tests for DiscoveryService."""
    
    @pytest.mark.asyncio
    async def test_register_agent(self, discovery_service, sample_manifest):
        """Test registering an agent."""
        response = await discovery_service.register_agent(sample_manifest)
        
        assert response.success is True
        assert response.agent_did == sample_manifest.identity.did
        assert response.registration_id is not None
    
    @pytest.mark.asyncio
    async def test_register_duplicate_agent(self, discovery_service, sample_manifest):
        """Test registering duplicate agent fails."""
        await discovery_service.register_agent(sample_manifest)
        response = await discovery_service.register_agent(sample_manifest)
        
        assert response.success is False
        assert "already registered" in response.error.lower()
    
    @pytest.mark.asyncio
    async def test_discover_agents(self, discovery_service, sample_manifest):
        """Test discovering agents."""
        await discovery_service.register_agent(sample_manifest)
        
        query = DiscoveryQuery(
            query="text summarization",
            max_results=10
        )
        
        results = await discovery_service.discover(query)
        
        assert len(results) == 1
        assert results[0].agent_did == sample_manifest.identity.did
    
    @pytest.mark.asyncio
    async def test_discover_no_results(self, discovery_service):
        """Test discovering with no results."""
        query = DiscoveryQuery(
            query="nonexistent capability",
            max_results=10
        )
        
        results = await discovery_service.discover(query)
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, discovery_service, sample_manifest):
        """Test agent heartbeat."""
        await discovery_service.register_agent(sample_manifest)
        
        heartbeat = Heartbeat(
            agent_did=sample_manifest.identity.did,
            status="healthy"
        )
        
        response = await discovery_service.heartbeat(heartbeat)
        
        assert response.success is True
    
    @pytest.mark.asyncio
    async def test_heartbeat_unregistered_agent(self, discovery_service):
        """Test heartbeat for unregistered agent."""
        heartbeat = Heartbeat(
            agent_did="did:oai:unregistered",
            status="healthy"
        )
        
        response = await discovery_service.heartbeat(heartbeat)
        
        assert response.success is False
    
    @pytest.mark.asyncio
    async def test_unregister_agent(self, discovery_service, sample_manifest):
        """Test unregistering an agent."""
        await discovery_service.register_agent(sample_manifest)
        
        response = await discovery_service.unregister_agent(sample_manifest.identity.did)
        
        assert response.success is True
        
        # Verify agent is unregistered
        query = DiscoveryQuery(query="text summarization", max_results=10)
        results = await discovery_service.discover(query)
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_get_agent(self, discovery_service, sample_manifest):
        """Test getting agent by DID."""
        await discovery_service.register_agent(sample_manifest)
        
        entry = await discovery_service.get_agent(sample_manifest.identity.did)
        
        assert entry is not None
        assert entry.agent_did == sample_manifest.identity.did
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, discovery_service):
        """Test getting nonexistent agent."""
        entry = await discovery_service.get_agent("did:oai:nonexistent")
        
        assert entry is None


class TestDiscoveryCache:
    """Tests for DiscoveryCache."""
    
    def test_cache_set_get(self):
        """Test basic cache set and get."""
        cache = DiscoveryCache(ttl_seconds=60, max_size=100)
        
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        
        assert result == {"data": "value1"}
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = DiscoveryCache(ttl_seconds=60, max_size=100)
        
        result = cache.get("nonexistent")
        
        assert result is None
    
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        cache = DiscoveryCache(ttl_seconds=0, max_size=100)  # Immediate expiration
        
        cache.set("key1", {"data": "value1"})
        
        # Should be expired immediately
        result = cache.get("key1")
        
        assert result is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = DiscoveryCache(ttl_seconds=60, max_size=2)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
    
    def test_cache_clear(self):
        """Test clearing cache."""
        cache = DiscoveryCache(ttl_seconds=60, max_size=100)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = DiscoveryCache(ttl_seconds=60, max_size=100)
        
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        
        stats = cache.get_stats()
        
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1