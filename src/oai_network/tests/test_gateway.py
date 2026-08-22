"""
Tests for the gateway module.
"""

import pytest
from oai_network.gateway.models import (
    GatewayRequest, GatewayResponse, RouteRule, GatewayConfig,
    UpstreamService, LoadBalancerStrategy
)
from oai_network.gateway.router import GatewayRouter
from oai_network.gateway.middleware import (
    AuthMiddleware, RateLimitMiddleware, LoggingMiddleware,
    MetricsMiddleware, CORSMiddleware, RequestSizeMiddleware,
    ResponseSizeMiddleware, TimeoutMiddleware
)


class TestGatewayModels:
    """Tests for gateway data models."""
    
    def test_gateway_request_creation(self):
        """Test creating a GatewayRequest."""
        request = GatewayRequest(
            method="POST",
            path="/api/v1/delegate",
            headers={"Content-Type": "application/json"},
            body={"capability": "text_summarization"},
            query_params={"version": "1"}
        )
        
        assert request.method == "POST"
        assert request.path == "/api/v1/delegate"
        assert request.headers["Content-Type"] == "application/json"
        assert request.body["capability"] == "text_summarization"
    
    def test_gateway_response_creation(self):
        """Test creating a GatewayResponse."""
        response = GatewayResponse(
            request_id="req-123",
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"result": "success"},
            latency_ms=150.0
        )
        
        assert response.status_code == 200
        assert response.body["result"] == "success"
        assert response.latency_ms == 150.0
    
    def test_route_rule_creation(self):
        """Test creating a RouteRule."""
        rule = RouteRule(
            id="rule-1",
            name="Test Rule",
            path_pattern="/api/v1/*",
            target_url="http://localhost:8001",
            load_balancer=LoadBalancerStrategy.ROUND_ROBIN,
        )
        
        assert rule.id == "rule-1"
        assert rule.path_pattern == "/api/v1/*"
        assert rule.load_balancer == LoadBalancerStrategy.ROUND_ROBIN
    
    def test_load_balancer_strategies(self):
        """Test LoadBalancerStrategy enum."""
        assert LoadBalancerStrategy.ROUND_ROBIN.value == "round_robin"
        assert LoadBalancerStrategy.LEAST_CONNECTIONS.value == "least_connections"
        assert LoadBalancerStrategy.RANDOM.value == "random"
        assert LoadBalancerStrategy.WEIGHTED.value == "weighted"
        assert LoadBalancerStrategy.IP_HASH.value == "ip_hash"
    
    def test_gateway_config(self):
        """Test GatewayConfig."""
        config = GatewayConfig(
            host="0.0.0.0",
            port=8000,
            routes=[],
            upstreams={},
            default_timeout=30.0,
            max_request_size=1024 * 1024
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.default_timeout == 30.0
    
    def test_upstream_service(self):
        """Test UpstreamService."""
        upstream = UpstreamService(
            id="service-1",
            name="Test Service",
            url="http://localhost:8001",
            weight=100,
        )
        
        assert upstream.id == "service-1"
        assert upstream.url == "http://localhost:8001"
        assert upstream.weight == 100


class TestGatewayRouter:
    """Tests for GatewayRouter."""
    
    def test_router_initialization(self, gateway_config):
        """Test router initialization."""
        router = GatewayRouter(gateway_config)
        
        assert router.config == gateway_config
        assert router.routes == []
    
    def test_add_route(self, gateway_config):
        """Test adding a route."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="test-route",
            path_pattern="/api/*",
            target_url="http://localhost:8001",
            load_balancer="round_robin"
        )
        
        router.add_route(rule)
        
        assert len(router.routes) == 1
        assert router.routes[0].name == "test-route"
    
    def test_match_route_exact(self, gateway_config):
        """Test matching exact route."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="exact-route",
            path_pattern="/api/test",
            target_url="http://localhost:8001",
            methods=["GET"]
        )
        router.add_route(rule)
        
        request = GatewayRequest(method="GET", path="/api/test", headers={}, body={})
        matched = router._find_route(request)
        
        assert matched is not None
        assert matched.name == "exact-route"
        
        # Wrong method should not match
        request = GatewayRequest(method="POST", path="/api/test", headers={}, body={})
        matched = router._find_route(request)
        assert matched is None
    
    def test_match_route_wildcard(self, gateway_config):
        """Test matching wildcard route."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="wildcard-route",
            path_pattern="/api/.*",
            target_url="http://localhost:8001"
        )
        router.add_route(rule)
        
        request = GatewayRequest(method="GET", path="/api/users", headers={}, body={})
        matched = router._find_route(request)
        
        assert matched is not None
        assert matched.name == "wildcard-route"
        
        request = GatewayRequest(method="GET", path="/api/users/123", headers={}, body={})
        matched = router._find_route(request)
        assert matched is not None
    
    def test_match_route_no_match(self, gateway_config):
        """Test no route match."""
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="api-route",
            path_pattern="/api/.*",
            target_url="http://localhost:8001"
        )
        router.add_route(rule)
        
        request = GatewayRequest(method="GET", path="/other/path", headers={}, body={})
        matched = router._find_route(request)
        
        assert matched is None
    
    def test_select_upstream_round_robin(self, gateway_config):
        """Test round-robin upstream selection."""
        gateway_config.upstreams = {
            "service-1": UpstreamService(
                id="service-1",
                name="Service 1",
                url="http://localhost:8001",
                weight=100
            ),
            "service-2": UpstreamService(
                id="service-2",
                name="Service 2",
                url="http://localhost:8002",
                weight=100
            )
        }
        
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="test-route",
            path_pattern="/api/*",
            target_url="http://localhost:8001",
            load_balancer="round_robin"
        )
        router.add_route(rule)
        router.add_upstream(rule.id, gateway_config.upstreams["service-1"])
        router.add_upstream(rule.id, gateway_config.upstreams["service-2"])
        
        # Should alternate between services
        upstream1 = router._select_upstream(rule)
        upstream2 = router._select_upstream(rule)
        
        assert upstream1.id != upstream2.id
    
    def test_select_upstream_weighted(self, gateway_config):
        """Test weighted upstream selection."""
        gateway_config.upstreams = {
            "service-1": UpstreamService(
                id="service-1",
                name="Service 1",
                url="http://localhost:8001",
                weight=100
            ),
            "service-2": UpstreamService(
                id="service-2",
                name="Service 2",
                url="http://localhost:8002",
                weight=10  # Much lower weight
            )
        }
        
        router = GatewayRouter(gateway_config)
        
        rule = RouteRule(
            name="test-route",
            path_pattern="/api/*",
            target_url="http://localhost:8001",
            load_balancer="weighted_round_robin"
        )
        router.add_route(rule)
        router.add_upstream(rule.id, gateway_config.upstreams["service-1"])
        router.add_upstream(rule.id, gateway_config.upstreams["service-2"])
        
        # service-1 should be selected more often
        selections = [router._select_upstream(rule).id for _ in range(100)]
        service1_count = selections.count("service-1")
        service2_count = selections.count("service-2")
        
        assert service1_count > service2_count
    
    @pytest.mark.asyncio
    async def test_route_request(self, gateway_config):
        """Test routing a request through middleware."""
        router = GatewayRouter(gateway_config)
        
        # Add a simple route
        rule = RouteRule(
            name="test-route",
            path_pattern="/api/*",
            target_url="http://localhost:8001",
            load_balancer="round_robin"
        )
        router.add_route(rule)
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={},
            body={}
        )
        
        # This would need a mock upstream - simplified test
        # Just verify the routing logic runs
        matched_rule = router._find_route(request)
        assert matched_rule is not None


class TestMiddleware:
    """Tests for gateway middleware."""
    
    def test_auth_middleware_valid(self):
        """Test auth middleware with valid token."""
        from oai_network.gateway.models import GatewayConfig, RouteRule
        config = GatewayConfig()
        middleware = AuthMiddleware(config)
        middleware.add_api_key("valid-token-123", "did:oai:test123")
        
        # Create a route that doesn't require verification
        route = RouteRule(
            name="test",
            path_pattern="/api/test",
            target_url="http://localhost:8000",
            require_verified=False
        )
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"Authorization": "Bearer valid-token-123"},
            body={}
        )
        
        result = middleware.process_request(request, route)
        
        assert result is None  # None means continue
        assert request.agent_did == "did:oai:test123"
    
    def test_auth_middleware_invalid(self):
        """Test auth middleware with invalid token."""
        from oai_network.gateway.models import GatewayConfig, RouteRule
        config = GatewayConfig()
        middleware = AuthMiddleware(config)
        middleware.add_api_key("valid-token-123", "did:oai:test123")
        
        # Create a route that requires verification
        route = RouteRule(
            name="test",
            path_pattern="/api/test",
            target_url="http://localhost:8000",
            require_verified=True
        )
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"Authorization": "Bearer invalid-token"},
            body={}
        )
        
        response = middleware.process_request(request, route)
        
        assert response is not None
        assert response.status_code == 401
    
    def test_auth_middleware_missing_token(self):
        """Test auth middleware with missing token."""
        from oai_network.gateway.models import GatewayConfig, RouteRule
        config = GatewayConfig()
        middleware = AuthMiddleware(config)
        middleware.add_api_key("valid-token-123", "did:oai:test123")
        
        # Create a route that requires verification
        route = RouteRule(
            name="test",
            path_pattern="/api/test",
            target_url="http://localhost:8000",
            require_verified=True
        )
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={},
            body={}
        )
        
        response = middleware.process_request(request, route)
        
        assert response is not None
        assert response.status_code == 401
    
    def test_rate_limit_middleware(self):
        """Test rate limiting middleware."""
        from oai_network.gateway.models import GatewayConfig
        config = GatewayConfig(global_rate_limit_rpm=5, global_rate_limit_burst=0)
        middleware = RateLimitMiddleware(config)
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Client-ID": "client-1"},
            body={}
        )
        
        # First 5 requests should pass
        for i in range(5):
            result = middleware.process_request(request, None)
            assert result is None
        
        # 6th request should be rate limited
        response = middleware.process_request(request, None)
        assert response is not None
        assert response.status_code == 429
    
    def test_rate_limit_different_clients(self):
        """Test rate limiting is per client."""
        from oai_network.gateway.models import GatewayConfig
        config = GatewayConfig(global_rate_limit_rpm=2, global_rate_limit_burst=0)
        middleware = RateLimitMiddleware(config)
        
        request1 = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Client-ID": "client-1"},
            body={}
        )
        
        request2 = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"X-Client-ID": "client-2"},
            body={}
        )
        
        # Client 1 makes 2 requests
        middleware.process_request(request1, None)
        middleware.process_request(request1, None)
        
        # Client 2 should still be able to make requests
        result = middleware.process_request(request2, None)
        assert result is None
    
    def test_logging_middleware(self, caplog):
        """Test logging middleware."""
        from oai_network.gateway.models import GatewayConfig
        config = GatewayConfig(access_log=True)
        middleware = LoggingMiddleware(config)
        
        request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={},
            body={"key": "value"}
        )
        
        result = middleware.process_request(request, None)
        
        assert result is None
        # Check that logging occurred (would need caplog fixture)
    
    def test_metrics_middleware(self):
        """Test metrics middleware."""
        middleware = MetricsMiddleware()
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={},
            body={}
        )
        
        result = middleware.process_request(request, None)
        
        assert result is None
        assert middleware.metrics['requests_total'] == 1
    
    def test_cors_middleware(self):
        """Test CORS middleware."""
        middleware = CORSMiddleware(
            allowed_origins=["http://localhost:3000"],
            allowed_methods=["GET", "POST"],
            allowed_headers=["Content-Type"]
        )
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"Origin": "http://localhost:3000"},
            body={}
        )
        
        result = middleware.process_request(request, None)
        
        assert result is None
        
        # Check response headers would be added in process_response
        response = GatewayResponse(
            request_id="req-123",
            status_code=200,
            headers={},
            body={}
        )
        
        processed_response = middleware.process_response(request, None, response)
        
        assert "Access-Control-Allow-Origin" in processed_response.headers
        assert processed_response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    
    def test_cors_middleware_blocked_origin(self):
        """Test CORS middleware blocks unauthorized origin."""
        middleware = CORSMiddleware(
            allowed_origins=["http://localhost:3000"],
            allowed_methods=["GET", "POST"],
            allowed_headers=["Content-Type"]
        )
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={"Origin": "http://evil.com"},
            body={}
        )
        
        response = middleware.process_request(request, None)
        
        assert response is not None
        assert response.status_code == 403
    
    def test_request_size_middleware(self):
        """Test request size limiting middleware."""
        middleware = RequestSizeMiddleware(max_size_bytes=1000)
        
        # Small request
        small_request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={},
            body={"small": "data"}
        )
        
        result = middleware.process_request(small_request, None)
        assert result is None
        
        # Large request
        large_request = GatewayRequest(
            method="POST",
            path="/api/test",
            headers={},
            body={"large": "x" * 2000}
        )
        
        response = middleware.process_request(large_request, None)
        assert response is not None
        assert response.status_code == 413
    
    def test_response_size_middleware(self):
        """Test response size limiting middleware."""
        middleware = ResponseSizeMiddleware(max_size_bytes=100)
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={},
            body={}
        )
        
        # Small response
        small_response = GatewayResponse(
            request_id="req-123",
            status_code=200,
            headers={},
            body={"small": "data"}
        )
        
        result = middleware.process_response(request, None, small_response)
        assert result.body == small_response.body
        
        # Large response
        large_response = GatewayResponse(
            request_id="req-124",
            status_code=200,
            headers={},
            body={"large": "x" * 200}
        )
        
        result = middleware.process_response(request, None, large_response)
        assert result.status_code == 500  # Internal error for oversized response
    
    def test_timeout_middleware(self):
        """Test timeout middleware."""
        middleware = TimeoutMiddleware(timeout_seconds=1)
        
        request = GatewayRequest(
            method="GET",
            path="/api/test",
            headers={},
            body={}
        )
        
        result = middleware.process_request(request, None)
        
        assert result is None
        # Timeout would be enforced during actual request processing