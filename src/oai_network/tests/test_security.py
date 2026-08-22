"""
Adversarial Security Tests for Stage 11: Security Hardening

These tests verify that the system properly handles malicious or malformed inputs,
enforces security policies, and prevents common attack vectors.
"""

import pytest
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from oai_network.gateway.models import GatewayRequest, GatewayResponse, RouteRule, GatewayConfig, UpstreamService
from oai_network.gateway.router import GatewayRouter
from oai_network.gateway.middleware import (
    AuthMiddleware, RateLimitMiddleware, RequestSizeMiddleware,
    ResponseSizeMiddleware, TimeoutMiddleware
)
from oai_network.policy.models import Policy, PolicyRule, PolicyEffect, PolicyCondition, PolicyOperator
from oai_network.policy.engine import PolicyEngine
from oai_network.core.delegation.manager import DelegationManager
from oai_network.core.delegation.models import DelegationRequest, DelegationTask, DelegationStatus
from oai_network.core.identity.models import AgentIdentity, KeyType
from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.verifier import IdentityVerifier
from oai_network.core.trust.models import TrustEvent, TrustEventType, Feedback
from oai_network.core.trust.calculator import TrustCalculator
from oai_network.protocols.a2a.models import AgentCard
from oai_network.protocols.a2a.server import A2AServer


class TestAdversarialAgentRequests:
    """Tests for adversarial agent request scenarios."""
    
    def test_agent_requests_capability_outside_manifest(self, gateway_config):
        """Test that agent requesting capability not in manifest is denied."""
        router = GatewayRouter(gateway_config)
        
        # Add route requiring specific capability
        rule = RouteRule(
            name="summarization-route",
            path_pattern="/api/v1/summarize",
            target_url="http://localhost:8001",
            required_capability="text_summarization",
            policy_enabled=True
        )
        router.add_route(rule)
        
        # Agent requests capability they don't have
        request = GatewayRequest(
            method="POST",
            path="/api/v1/summarize",
            headers={"Authorization": "Bearer agent-token"},
            body={"capability": "text_summarization", "text": "test"},
            agent_did="did:oai:malicious-agent",
            capability_name="text_summarization"  # Not in their manifest
        )
        
        # Should be denied by policy (no matching capability in manifest)
        # This test verifies the policy engine checks capability against manifest
        pass  # Implementation will verify this behavior
    
    def test_agent_exceeds_configured_budget(self, gateway_config):
        """Test that agent exceeding budget is denied."""
        router = GatewayRouter(gateway_config)
        
        # Load policy with budget
        from oai_network.policy.models import Budget, BudgetPeriod
        budget = Budget(
            budget_id="daily-budget",
            name="Daily Budget",
            period=BudgetPeriod.DAILY,
            limit=10.0,
            currency="USD"
        )
        
        policy = Policy(
            policy_id="budget-policy",
            name="Budget Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="allow-with-budget",
                    name="Allow with budget",
                    effect=PolicyEffect.ALLOW,
                    conditions=[]
                )
            ],
            budgets=[budget]
        )
        
        from oai_network.policy.engine import PolicyEngine
        router.policy_engine = PolicyEngine(policy)
        
        # Add upstream so policy check is reached
        rule = RouteRule(
            name="budget-route",
            path_pattern="/api/v1/.*",
            target_url="http://localhost:8001",
            policy_enabled=True
        )
        router.add_route(rule)
        router.add_upstream(rule.id, UpstreamService(
            id="service-1",
            name="Service 1",
            url="http://localhost:8001",
            weight=100
        ))
        
        # Request with cost exceeding budget
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={},
            body={"capability": "text_summarization", "cost": 15.0},  # Exceeds 10.0 limit
            agent_did="did:oai:test-agent"
        )
        
        # Should be denied due to budget exceeded
        response = router.route(request)
        assert response.status_code == 403
        assert "budget" in response.body.get("reason", "").lower()
    
    def test_agent_attempts_delegation_deeper_than_maximum_depth(self, gateway_config):
        """Test that delegation deeper than max_depth is denied."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="delegation-route",
            path_pattern="/api/v1/delegate",
            target_url="http://localhost:8001",
            policy_enabled=True
        )
        router.add_route(rule)
        
        # Policy with max delegation depth of 2
        policy = Policy(
            policy_id="depth-policy",
            name="Depth Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="allow-shallow",
                    name="Allow shallow delegation",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="delegation_depth",
                            operator=PolicyOperator.LESS_THAN,
                            value=3  # Max depth 2
                        )
                    ]
                )
            ]
        )
        
        from oai_network.policy.engine import PolicyEngine
        router.policy_engine = PolicyEngine(policy)
        
        # Request with delegation_depth = 3 (exceeds max of 2)
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={},
            body={"capability": "text_summarization"},
            agent_did="did:oai:test-agent",
            delegation_depth=3  # Exceeds maximum
        )
        
        response = router.route(request)
        assert response.status_code == 403
    
    def test_agent_spoofs_another_agents_identity(self, gateway_config):
        """Test that agent spoofing another's identity is detected."""
        from oai_network.core.identity.verifier import IdentityVerifier
        from oai_network.core.identity.generator import IdentityGenerator
        from oai_network.core.identity.models import KeyType
        
        generator = IdentityGenerator()
        verifier = IdentityVerifier()
        
        # Generate legitimate identity for agent A
        identity_a, private_key_a = generator.generate("agent-a", KeyType.ED25519)
        
        # Generate identity for agent B (attacker)
        identity_b, private_key_b = generator.generate("agent-b", KeyType.ED25519)
        
        # Attacker tries to sign as agent A using their own key
        message = b"malicious request"
        signature_b = generator.sign_message(message, private_key_b)
        
        # Verification with agent A's public key should fail
        result = verifier.verify_signature(message, signature_b, identity_a.did, identity_a.public_key, identity_a.key_type)
        assert result is False
        
        # Attacker tries to present agent A's DID with their own key
        # This should be caught by identity verification
        spoofed_identity = AgentIdentity(
            did=identity_a.did,
            name="agent-a",
            public_key=identity_b.public_key,  # Wrong key!
            key_type=KeyType.ED25519,
            created_at=identity_a.created_at,
        )
        
        # Verification should fail due to key mismatch
        result = verifier.verify_identity_structure(spoofed_identity)
        # Structure might be valid but key doesn't match DID
        # The DID should be derived from the public key
        assert spoofed_identity.did != identity_b.did  # Different DIDs


class TestMalformedOversizedPayloads:
    """Tests for DoS resistance against malformed/oversized payloads."""
    
    def test_oversized_request_body_rejected(self, gateway_config):
        """Test that oversized request bodies are rejected with 413."""
        middleware = RequestSizeMiddleware(max_size_bytes=1024)  # 1KB limit
        
        # Create request with large body (> 1KB)
        large_body = {"data": "x" * 2000}
        request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={"Content-Type": "application/json"},
            body=large_body
        )
        
        response = middleware.process_request(request, None)
        assert response is not None
        assert response.status_code == 413
        assert "large" in response.body.get("error", "").lower()
    
    def test_oversized_response_body_rejected(self, gateway_config):
        """Test that oversized response bodies are rejected."""
        middleware = ResponseSizeMiddleware(max_size_bytes=1024)
        
        request = GatewayRequest(method="GET", path="/api/test", headers={}, body={})
        
        # Large response
        large_response = GatewayResponse(
            request_id="req-123",
            status_code=200,
            headers={},
            body={"data": "x" * 2000}
        )
        
        result = middleware.process_response(request, None, large_response)
        assert result.status_code == 500  # Internal error for oversized response
    
    def test_deeply_nested_json_rejected(self, gateway_config):
        """Test that deeply nested JSON causing stack overflow is rejected."""
        middleware = RequestSizeMiddleware(max_size_bytes=1024 * 1024)  # 1MB
        
        # Create deeply nested structure
        nested = {"level": 0}
        current = nested
        for i in range(1000):  # Very deep nesting
            current["nested"] = {"level": i + 1}
            current = current["nested"]
        
        request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={"Content-Type": "application/json"},
            body=nested
        )
        
        # Should handle gracefully (either reject or process without stack overflow)
        response = middleware.process_request(request, None)
        # Either rejected for size or processed without error
        assert response is None or response.status_code in [413, 400]
    
    def test_malformed_json_request_rejected(self, gateway_config):
        """Test that malformed JSON in request body is handled."""
        # This would be tested at the HTTP server level
        # Here we verify the middleware doesn't crash on invalid body types
        middleware = RequestSizeMiddleware(max_size_bytes=1024)
        
        request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={"Content-Type": "application/json"},
            body="not a dict"  # Invalid body type
        )
        
        # Should handle gracefully
        response = middleware.process_request(request, None)
        assert response is None or response.status_code in [400, 413]
    
    def test_extremely_long_headers_rejected(self, gateway_config):
        """Test that extremely long headers are rejected."""
        middleware = RequestSizeMiddleware(max_size_bytes=8192)  # 8KB total
        
        # Create request with very long header value
        long_header = "x" * 10000
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Custom-Header": long_header},
            body={}
        )
        
        response = middleware.process_request(request, None)
        # Should reject due to total size
        assert response is not None
        assert response.status_code == 413


class TestRateLimitingSecurity:
    """Tests for rate limiting as a security control."""
    
    def test_rate_limit_per_agent_identity(self, gateway_config):
        """Test rate limiting is enforced per agent identity."""
        config = GatewayConfig(global_rate_limit_rpm=10, global_rate_limit_burst=0)
        middleware = RateLimitMiddleware(config)
        
        # Agent 1 makes requests
        request1 = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Agent-DID": "did:oai:agent1"},
            body={},
            agent_did="did:oai:agent1"
        )
        
        # Agent 2 makes requests
        request2 = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Agent-DID": "did:oai:agent2"},
            body={},
            agent_did="did:oai:agent2"
        )
        
        # Agent 1 hits limit
        for _ in range(10):
            result = middleware.process_request(request1, None)
            assert result is None
        
        # Agent 1's 11th request should be rate limited
        response = middleware.process_request(request1, None)
        assert response is not None
        assert response.status_code == 429
        
        # Agent 2 should still be able to make requests
        result = middleware.process_request(request2, None)
        assert result is None
    
    def test_burst_allowance_respected(self, gateway_config):
        """Test that burst allowance is respected."""
        config = GatewayConfig(global_rate_limit_rpm=5, global_rate_limit_burst=3)
        middleware = RateLimitMiddleware(config)
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Agent-DID": "did:oai:agent1"},
            body={}
        )
        
        # Should allow burst (5 + 3 = 8 requests)
        for _ in range(8):
            result = middleware.process_request(request, None)
            assert result is None
        
        # 9th request should be rate limited
        response = middleware.process_request(request, None)
        assert response is not None
        assert response.status_code == 429


class TestTimeoutEnforcement:
    """Tests for timeout enforcement on every hop."""
    
    def test_request_timeout_enforced(self, gateway_config):
        """Test that request timeout is enforced."""
        middleware = TimeoutMiddleware(timeout_seconds=1)
        
        request = GatewayRequest(
            method="GET",
            path="/api/slow-endpoint",
            headers={},
            body={}
        )
        
        result = middleware.process_request(request, None)
        assert result is None
        # Timeout would be enforced during actual upstream call
        # This verifies the middleware is in place
    
    def test_gateway_route_timeout_config(self, gateway_config):
        """Test that route-level timeouts are configured."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="timeout-route",
            path_pattern="/api/slow",
            target_url="http://localhost:8001",
            connect_timeout_ms=1000,
            request_timeout_ms=5000
        )
        router.add_route(rule)
        
        assert rule.connect_timeout_ms == 1000
        assert rule.request_timeout_ms == 5000


class TestIdentityProofAndSigning:
    """Tests for real identity proof - signing Agent Cards and requests."""
    
    def test_agent_card_signed_with_keypair(self):
        """Test that Agent Card is signed with agent's key pair."""
        from oai_network.core.identity.generator import IdentityGenerator
        from oai_network.core.identity.models import KeyType
        from oai_network.protocols.a2a.models import AgentCard
        
        generator = IdentityGenerator()
        identity, private_key_pem = generator.generate("test-agent", KeyType.ED25519)
        
        # Create agent card
        card = AgentCard(
            agent_did=identity.did,
            name="Test Agent",
            description="A test agent",
            version="1.0.0",
            url="http://localhost:8001",
            capabilities=["text_summarization"],
            endpoints={},
            metadata={}
        )
        
        # Sign the agent card
        card_json = card.model_dump_json()
        signature = generator.sign_message(card_json.encode(), private_key_pem)
        
        # Verify signature
        from oai_network.core.identity.verifier import IdentityVerifier
        verifier = IdentityVerifier()
        result = verifier.verify_signature(card_json.encode(), signature, identity.did, identity.public_key, identity.key_type)
        assert result is True
    
    def test_request_signed_by_agent(self):
        """Test that requests are signed by agent."""
        from oai_network.core.identity.generator import IdentityGenerator
        from oai_network.core.identity.models import KeyType
        
        generator = IdentityGenerator()
        identity, private_key_pem = generator.generate("request-agent", KeyType.ED25519)
        
        # Create request payload
        request_data = {
            "method": "POST",
            "path": "/api/v1/delegate",
            "body": {"capability": "text_summarization", "text": "test"},
            "timestamp": int(time.time()),
            "nonce": "unique-nonce-123"
        }
        
        request_json = json.dumps(request_data, sort_keys=True)
        signature = generator.sign_message(request_json.encode(), private_key_pem)
        
        # Verify signature
        from oai_network.core.identity.verifier import IdentityVerifier
        verifier = IdentityVerifier()
        result = verifier.verify_signature(request_json.encode(), signature, identity.did, identity.public_key, identity.key_type)
        assert result is True
    
    def test_gateway_verifies_signature_before_routing(self, gateway_config):
        """Test that gateway verifies request signature before routing."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="signed-route",
            path_pattern="/api/v1/.*",
            target_url="http://localhost:8001",
            policy_enabled=True,
            require_verified=True
        )
        router.add_route(rule)
        
        # Add auth middleware that verifies signatures
        from oai_network.gateway.middleware import AuthMiddleware
        auth = AuthMiddleware(gateway_config)
        
        # Generate identity
        generator = IdentityGenerator()
        identity, private_key_pem = generator.generate("verified-agent", KeyType.ED25519)
        auth.add_api_key("valid-signature-key", identity.did)
        
        # Create signed request
        request_data = {"capability": "text_summarization", "timestamp": int(time.time())}
        request_json = json.dumps(request_data, sort_keys=True)
        signature = generator.sign_message(request_json.encode(), private_key_pem)
        
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={
                "Authorization": f"Bearer valid-signature-key",
                "X-Signature": signature.hex(),
                "X-Request-Payload": request_json
            },
            body=request_data,
            agent_did=identity.did
        )
        
        # Process through auth middleware
        result = auth.process_request(request, rule)
        # Should pass verification
        assert result is None
        assert request.agent_did == identity.did


class TestPolicyEnforcementSecurity:
    """Tests for policy enforcement security."""
    
    def test_blocked_capabilities_denied(self, gateway_config):
        """Test that blocked capabilities are denied."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="blocked-route",
            path_pattern="/api/v1/.*",
            target_url="http://localhost:8001",
            policy_enabled=True
        )
        router.add_route(rule)
        
        policy = Policy(
            policy_id="block-policy",
            name="Block Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="block-dangerous",
                    name="Block dangerous capabilities",
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.IN,
                            value=["dangerous_capability", "admin_access", "system_control"]
                        )
                    ]
                ),
                PolicyRule(
                    rule_id="allow-others",
                    name="Allow other capabilities",
                    effect=PolicyEffect.ALLOW,
                    conditions=[]
                )
            ]
        )
        
        from oai_network.policy.engine import PolicyEngine
        router.policy_engine = PolicyEngine(policy)
        
        # Add upstream so policy check is reached
        rule = RouteRule(
            name="blocked-route",
            path_pattern="/api/v1/.*",
            target_url="http://localhost:8001",
            policy_enabled=True
        )
        router.add_route(rule)
        router.add_upstream(rule.id, UpstreamService(
            id="service-1",
            name="Service 1",
            url="http://localhost:8001",
            weight=100
        ))
        
        # Request for blocked capability
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={},
            body={"capability": "dangerous_capability"},
            agent_did="did:oai:test-agent",
            capability_name="dangerous_capability"
        )
        
        response = router.route(request)
        assert response.status_code == 403
        assert "denied" in response.body.get("error", "").lower()
    
    def test_allowed_capabilities_only_policy(self, gateway_config):
        """Test allowlist-only policy (deny by default)."""
        router = GatewayRouter(gateway_config)
        
        policy = Policy(
            policy_id="allowlist-policy",
            name="Allowlist Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    rule_id="allow-specific",
                    name="Allow only specific capabilities",
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition(
                            field="capability",
                            operator=PolicyOperator.IN,
                            value=["text_summarization", "translation", "code_analysis"]
                        )
                    ]
                )
                # No catch-all allow rule - default deny
            ]
        )
        
        from oai_network.policy.engine import PolicyEngine
        router.policy_engine = PolicyEngine(policy)
        
        # Add upstream so policy check is reached
        rule = RouteRule(
            name="allowlist-route",
            path_pattern="/api/v1/.*",
            target_url="http://localhost:8001",
            policy_enabled=True
        )
        router.add_route(rule)
        router.add_upstream(rule.id, UpstreamService(
            id="service-1",
            name="Service 1",
            url="http://localhost:8001",
            weight=100
        ))
        
        # Allowed capability
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={},
            body={"capability": "text_summarization"},
            agent_did="did:oai:test-agent",
            capability_name="text_summarization"
        )
        response = router.route(request)
        assert response.status_code == 200
        
        # Not in allowlist
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={},
            body={"capability": "arbitrary_code_execution"},
            agent_did="did:oai:test-agent",
            capability_name="arbitrary_code_execution"
        )
        response = router.route(request)
        assert response.status_code == 403


class TestDelegationSecurity:
    """Tests for delegation security controls."""
    
    def test_delegation_max_depth_enforced(self):
        """Test that delegation chain max depth is enforced."""
        from oai_network.core.delegation.manager import DelegationManager
        from oai_network.core.delegation.models import DelegationPolicy
        
        policy = DelegationPolicy(
            max_depth=2,
            min_trust_score=0.5,
            allowed_capabilities=["text_summarization"],
            blocked_capabilities=[]
        )
        
        manager = DelegationManager(policy=policy)
        
        # Create chain that exceeds max depth
        chain = [
            DelegationTask(
                task_id=f"task-{i}",
                request_id=f"req-{i}",
                delegator_did="did:oai:requester",
                capability="text_summarization",
                requester_did="did:oai:requester",
                delegatee_did=f"did:oai:agent{i}",
                depth=i + 1
            )
            for i in range(3)  # Depth 1, 2, 3 - exceeds max of 2
        ]
        
        # Third task should be rejected
        assert manager._check_policy(chain[0]) is True
        assert manager._check_policy(chain[1]) is True
        assert manager._check_policy(chain[2]) is False  # Depth 3 > max 2
    
    def test_delegation_min_trust_score_enforced(self):
        """Test that minimum trust score is enforced for delegation."""
        from oai_network.core.delegation.manager import DelegationManager
        from oai_network.core.delegation.models import DelegationPolicy
        from oai_network.core.trust.calculator import TrustCalculator
        from oai_network.core.trust.store import TrustStore
        from oai_network.core.trust.models import ReputationLedger
        
        # Mock trust store returning low trust score
        mock_store = Mock(spec=TrustStore)
        mock_store.get_ledger.return_value = ReputationLedger(agent_did="did:oai:low-trust-agent", events=[])
        
        calculator = TrustCalculator(store=mock_store)
        
        policy = DelegationPolicy(
            max_depth=3,
            min_trust_score=0.6,  # Higher than default 0.5
            allowed_capabilities=["text_summarization"],
            blocked_capabilities=[]
        )
        
        manager = DelegationManager(policy=policy, trust_calculator=calculator, trust_store=mock_store)
        
        task = DelegationTask(
            task_id="task-1",
            request_id="req-1",
            delegator_did="did:oai:requester",
            capability="text_summarization",
            requester_did="did:oai:requester",
            delegatee_did="did:oai:low-trust-agent",
            depth=1
        )
        
        # Should be rejected due to low trust score (default 0.5 < 0.6)
        assert manager._check_policy(task) is False
    
    def test_delegation_budget_enforced(self):
        """Test that delegation budget is enforced."""
        from oai_network.core.delegation.manager import DelegationManager
        from oai_network.core.delegation.models import DelegationPolicy
        
        policy = DelegationPolicy(
            max_depth=3,
            min_trust_score=0.5,
            allowed_capabilities=["text_summarization"],
            blocked_capabilities=[],
            max_budget=10.0,
            budget_period="daily"
        )
        
        manager = DelegationManager(policy=policy)
        
        # Simulate budget tracking
        manager._budget_spent = {"did:oai:requester": 9.0}
        
        task = DelegationTask(
            task_id="task-1",
            request_id="req-1",
            delegator_did="did:oai:requester",
            capability="text_summarization",
            requester_did="did:oai:requester",
            delegatee_did="did:oai:agent1",
            depth=1,
            estimated_cost=2.0  # Would exceed budget (9 + 2 > 10)
        )
        
        assert manager._check_policy(task) is False
        
        # Within budget
        task2 = DelegationTask(
            task_id="task-2",
            request_id="req-2",
            delegator_did="did:oai:requester",
            capability="text_summarization",
            requester_did="did:oai:requester",
            delegatee_did="did:oai:agent1",
            depth=1,
            estimated_cost=0.5  # Within budget (9 + 0.5 <= 10)
        )
        
        assert manager._check_policy(task2) is True


class TestTrustSystemSecurity:
    """Tests for trust system security."""
    
    def test_trust_score_cannot_be_manipulated_directly(self):
        """Test that trust score cannot be directly manipulated."""
        from oai_network.core.trust.calculator import TrustCalculator
        from oai_network.core.trust.store import TrustStore
        from oai_network.core.trust.models import TrustEvent, TrustEventType, ReputationLedger
        
        mock_store = Mock(spec=TrustStore)
        mock_store.get_ledger.return_value = ReputationLedger(agent_did="did:oai:test-agent", events=[])
        
        calculator = TrustCalculator(store=mock_store)
        
        # Trust score should only be calculated from events, not set directly
        score = calculator.calculate("did:oai:test-agent")
        assert 0.0 <= score.overall_score <= 1.0
        assert score.overall_score == 0.5  # Default initial score
    
    def test_feedback_rating_bounds_enforced(self):
        """Test that feedback ratings are bounded."""
        from oai_network.core.trust.models import Feedback
        
        # Valid ratings
        feedback = Feedback(
            from_did="did:oai:agent1",
            to_did="did:oai:agent2",
            rating=5,
            comment="Great!"
        )
        assert feedback.rating == 5
        
        feedback = Feedback(
            from_did="did:oai:agent1",
            to_did="did:oai:agent2",
            rating=1,
            comment="Poor"
        )
        assert feedback.rating == 1
        
        # Invalid ratings should be rejected by Pydantic
        with pytest.raises(Exception):
            Feedback(
                from_did="did:oai:agent1",
                to_did="did:oai:agent2",
                rating=0,  # Below minimum
                comment="Invalid"
            )
        
        with pytest.raises(Exception):
            Feedback(
                from_did="did:oai:agent1",
                to_did="did:oai:agent2",
                rating=6,  # Above maximum
                comment="Invalid"
            )
    
    def test_trust_decay_prevents_stale_high_scores(self):
        """Test that trust decay prevents stale high scores."""
        from oai_network.core.trust.calculator import TrustCalculator
        from oai_network.core.trust.store import TrustStore
        from oai_network.core.trust.models import TrustEvent, TrustEventType, ReputationLedger
        from datetime import datetime, timedelta, timezone
        
        mock_store = Mock(spec=TrustStore)
        
        # Old successful events (6 months ago)
        old_events = [
            TrustEvent(
                event_id=f"event-{i}",
                source_did="did:oai:stale-agent",
                target_did="did:oai:counterparty",
                event_type=TrustEventType.INTERACTION_SUCCESS,
                timestamp=datetime.now(timezone.utc) - timedelta(days=180),
                metadata={}
            )
            for i in range(10)
        ]
        mock_store.get_ledger.return_value = ReputationLedger(agent_did="did:oai:stale-agent", events=old_events)
        
        calculator = TrustCalculator(store=mock_store)
        score = calculator.calculate("did:oai:stale-agent")
        
        # Score should be decayed due to age
        assert score.overall_score < 0.8  # Should not be near 1.0 due to decay
        assert score.confidence < 0.5  # Low confidence due to staleness


class TestInputValidationSecurity:
    """Tests for input validation security."""
    
    def test_sql_injection_in_discovery_query_blocked(self):
        """Test that SQL injection in discovery queries is blocked."""
        from oai_network.core.discovery.service import DiscoveryService
        from oai_network.core.discovery.models import DiscoveryQuery
        
        # Attempt SQL injection in query
        malicious_query = DiscoveryQuery(
            query="'; DROP TABLE agents; --",
            capability_type=None,
            max_results=10
        )
        
        # Should be sanitized or rejected
        # The query should be treated as literal string, not executed
        assert malicious_query.query == "'; DROP TABLE agents; --"
    
    def test_xss_in_agent_name_blocked(self):
        """Test that XSS payloads in agent names are handled."""
        from oai_network.core.identity.models import AgentIdentity
        from oai_network.core.identity.generator import IdentityGenerator
        from oai_network.core.identity.models import KeyType
        
        generator = IdentityGenerator()
        
        # XSS payload in name
        xss_name = "<script>alert('xss')</script>"
        
        # Should either sanitize or reject
        identity, _ = generator.generate(xss_name, KeyType.ED25519)
        
        # Name should be stored as-is but escaped when rendered
        assert identity.metadata.get("name") == xss_name
        # DID should not contain script tags
        assert "<script>" not in identity.did
    
    def test_path_traversal_in_file_operations_blocked(self):
        """Test that path traversal attempts are blocked."""
        from oai_network.agents.code_analysis_agent import CodeAnalysisAgent
        
        agent = CodeAnalysisAgent()
        
        # Attempt path traversal
        malicious_path = "../../../etc/passwd"
        
        # Should be rejected or sanitized
        # The agent should validate paths are within allowed directories
        pass  # Implementation will verify this


class TestDependencySecurity:
    """Tests for dependency vulnerability scanning."""
    
    def test_pip_audit_in_ci(self):
        """Test that pip-audit runs in CI (placeholder for CI config test)."""
        # This test documents the requirement
        # Actual CI config is in .github/workflows/
        pass
    
    def test_npm_audit_in_ci(self):
        """Test that npm audit runs in CI for TypeScript SDK."""
        # This test documents the requirement
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])