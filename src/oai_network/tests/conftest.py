"""
Test configuration and fixtures for OAI Network tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator

from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.models import IdentityDocument, AgentIdentity
from oai_network.core.capabilities.models import AgentManifest, Capability, ServiceEndpoint
from oai_network.core.discovery.models import (
    DiscoveryQuery,
    DiscoveryResult,
    RegistryEntry as DiscoveryRegistryEntry,
)
from oai_network.core.discovery.service import DiscoveryService
from oai_network.registry.models import RegistryEntry, HealthStatus
from oai_network.registry.service import RegistryService
from oai_network.core.trust.models import TrustScore, TrustEvent
from oai_network.core.trust.calculator import TrustCalculator
from oai_network.core.trust.store import TrustStore
from oai_network.core.negotiation.models import NegotiationSession
from oai_network.core.negotiation.protocol import NegotiationProtocol
from oai_network.core.delegation.models import DelegationRequest, DelegationTask, DelegationStatus, DelegationPriority
from oai_network.core.delegation.manager import DelegationManager
from oai_network.core.delegation.policy import DelegationPolicyEngine
from oai_network.policy.models import Policy, PolicyRule, PolicyEffect, PolicyCondition, Budget, BudgetPeriod, PolicyOperator
from oai_network.policy.engine import PolicyEngine
from oai_network.policy.loader import PolicyLoader
from oai_network.gateway.models import GatewayConfig
from oai_network.protocols.a2a.models import AgentCard


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def identity_generator() -> IdentityGenerator:
    """Create an identity generator."""
    return IdentityGenerator()


@pytest.fixture
def sample_identity(identity_generator) -> IdentityDocument:
    """Generate a sample identity."""
    identity_doc, _ = identity_generator.create_identity_document()
    return identity_doc


@pytest.fixture
def sample_agent_identity(sample_identity) -> AgentIdentity:
    """Get the agent identity from a sample identity document."""
    return sample_identity.identity


@pytest.fixture
def sample_capability() -> Capability:
    """Create a sample capability."""
    return Capability(
        name="text_summarization",
        description="Summarize long text into key points",
        type="nlp",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "max_length": {"type": "integer", "default": 100}
            },
            "required": ["text"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            }
        },
        tags=["nlp", "summarization", "text"]
    )


@pytest.fixture
def sample_endpoint() -> ServiceEndpoint:
    """Create a sample service endpoint."""
    return ServiceEndpoint(
        url="http://localhost:8000/a2a",
        protocol="a2a",
        description="A2A endpoint for test agent"
    )


@pytest.fixture
def sample_manifest(sample_agent_identity, sample_capability, sample_endpoint) -> AgentManifest:
    """Create a sample agent manifest."""
    return AgentManifest(
        identity=sample_agent_identity,
        name="Test Agent",
        description="A test agent for unit testing",
        version="1.0.0",
        capabilities=[sample_capability],
        endpoints=[sample_endpoint],
        tags=["test", "nlp"]
    )


@pytest.fixture
def sample_discovery_query() -> DiscoveryQuery:
    """Create a sample discovery query."""
    return DiscoveryQuery(
        query="summarize text",
        capability_type="nlp",
        min_trust_score=0.0,
        verified_only=False,
        max_results=10
    )


@pytest.fixture
def sample_discovery_result(sample_agent_identity) -> DiscoveryResult:
    """Create a sample discovery result."""
    return DiscoveryResult(
        agent_did=sample_agent_identity.did,
        agent_name="Test Agent",
        agent_description="A test agent for unit testing",
        capability_name="text_summarization",
        capability_type="nlp",
        relevance_score=0.85,
        trust_score=0.9,
        endpoint_url="http://localhost:8000/a2a",
        tags=["nlp", "summarization", "text"],
        verified=True,
    )


@pytest.fixture
def sample_registry_entry(sample_manifest) -> RegistryEntry:
    """Create a sample registry entry."""
    from datetime import datetime, timezone
    return RegistryEntry(
        agent_did=sample_manifest.identity.did,
        name=sample_manifest.name,
        description=sample_manifest.description,
        manifest=sample_manifest,
        manifest_json=sample_manifest.model_dump_json(),
        status="active",
        health_status=HealthStatus.HEALTHY,
        last_heartbeat=datetime.now(timezone.utc),
        registered_at=datetime.now(timezone.utc),
        capabilities=[cap.name for cap in sample_manifest.capabilities],
    )


@pytest.fixture
def discovery_service() -> DiscoveryService:
    """Create a discovery service instance."""
    return DiscoveryService()


@pytest.fixture
def registry_service() -> RegistryService:
    """Create a registry service instance."""
    return RegistryService()


@pytest.fixture
def sample_trust_score(sample_agent_identity) -> TrustScore:
    """Create a sample trust score."""
    return TrustScore(
        agent_did=sample_agent_identity.did,
        overall_score=0.85,
        interaction_score=0.9,
        feedback_score=0.8,
        identity_score=1.0,
        behavior_score=0.7,
        event_count=100
    )


@pytest.fixture
def sample_trust_event(sample_agent_identity) -> TrustEvent:
    """Create a sample trust event."""
    return TrustEvent(
        event_type="successful_interaction",
        source_did=sample_agent_identity.did,
        target_did="did:oai:target123",
        value=1.0,
        weight=1.0,
        metadata={"capability": "text_summarization"}
    )


@pytest.fixture
def trust_calculator(trust_store) -> TrustCalculator:
    """Create a trust calculator."""
    calculator = TrustCalculator()
    calculator.set_store(trust_store)
    return calculator


@pytest.fixture
def trust_store() -> TrustStore:
    """Create a trust store."""
    return TrustStore()


@pytest.fixture
def sample_negotiation_session(sample_agent_identity) -> NegotiationSession:
    """Create a sample negotiation session."""
    return NegotiationSession(
        session_id="neg-123",
        initiator_did="did:oai:initiator",
        responder_did="did:oai:responder",
        status="pending",
        parameters={"price": 0.01, "max_calls": 1000},
        template_id="standard"
    )


@pytest.fixture
def negotiation_protocol():
    """Create a negotiation protocol."""
    return NegotiationProtocol()


@pytest.fixture
def sample_delegation_request(sample_agent_identity, sample_capability) -> DelegationRequest:
    """Create a sample delegation request."""
    return DelegationRequest(
        delegator_did=sample_agent_identity.did,
        delegatee_did="did:oai:delegatee",
        capability=sample_capability.name,
        input_data={"text": "Long text to summarize...", "max_length": 50},
        requirements={"min_trust_score": 0.5},
        priority=DelegationPriority.NORMAL,
        timeout_seconds=60,
        max_retries=3,
    )


@pytest.fixture
def delegation_policy_engine():
    """Create a delegation policy engine."""
    return DelegationPolicyEngine()


@pytest.fixture
def delegation_manager(sample_manifest, sample_capability):
    """Create a delegation manager with a registered agent."""
    import asyncio
    from oai_network.core.discovery.service import DiscoveryService

    discovery = DiscoveryService()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(discovery.register_agent(sample_manifest))
    finally:
        loop.close()

    return DelegationManager(discovery_service=discovery)


@pytest.fixture
def sample_policy() -> Policy:
    """Create a sample policy."""
    policy = Policy(
        policy_id="test-policy",
        name="Test Policy",
        description="Policy for testing",
        version="1.0.0",
        default_effect=PolicyEffect.DENY
    )
    
    # Add allow rule for verified agents with good trust
    policy.add_rule(PolicyRule(
        rule_id="allow-verified",
        name="Allow Verified High-Trust",
        effect=PolicyEffect.ALLOW,
        priority=100,
        conditions=[
            PolicyCondition(
                field="identity_verified",
                operator=PolicyOperator.EQUALS,
                value=True
            ),
            PolicyCondition(
                field="trust_score",
                operator=PolicyOperator.GREATER_THAN_OR_EQUAL,
                value=0.7
            )
        ]
    ))
    
    # Add budget
    policy.add_budget(Budget(
        budget_id="daily-limit",
        name="Daily Limit",
        period=BudgetPeriod.DAILY,
        limit=10.0
    ))
    
    return policy


@pytest.fixture
def policy_engine() -> PolicyEngine:
    """Create a policy engine."""
    return PolicyEngine()


@pytest.fixture
def policy_loader() -> PolicyLoader:
    """Create a policy loader."""
    return PolicyLoader()


@pytest.fixture
def gateway_config() -> GatewayConfig:
    """Create a gateway configuration for testing."""
    from oai_network.gateway.models import GatewayConfig
    return GatewayConfig(
        host="0.0.0.0",
        port=8080,
        routes=[],
        upstreams={},
        default_timeout=30.0,
        max_request_size=1024 * 1024
    )


# Async fixtures
@pytest.fixture
async def async_client():
    """Create an async test client."""
    # This would be implemented with actual test client
    yield None


@pytest.fixture
def a2a_server_url() -> str:
    """A2A server URL for testing."""
    return "http://localhost:8000"


@pytest.fixture
def mcp_server_url() -> str:
    """MCP server URL for testing."""
    return "http://localhost:8001"


@pytest.fixture
def sample_agent_card() -> AgentCard:
    """Create a sample agent card."""
    return AgentCard(
        agent_did="did:oai:test123",
        name="Test Agent",
        description="A test agent",
        version="1.0.0",
        capabilities=["text_summarization"],
        endpoints={"a2a": "http://localhost:8000/a2a"}
    )


@pytest.fixture
def python_sdk_client(sample_agent_identity):
    """Create a Python SDK client for testing."""
    from oai_network.sdk.python.client import OAIClient
    return OAIClient(
        registry_url="http://localhost:8000",
        identity=sample_agent_identity,
    )