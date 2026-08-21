"""
Gateway Router

Routes requests through the gateway with policy enforcement.
"""

import time
import re
from typing import Optional, List, Any, Callable
from .models import (
    GatewayRequest, GatewayResponse, RouteRule, GatewayConfig,
    UpstreamService, LoadBalancer
)
from ..policy.engine import PolicyEngine
from ..policy.models import Policy
from ..core.discovery.service import DiscoveryService


class GatewayRouter:
    """
    Main gateway router with policy enforcement.
    
    Features:
    - Path-based routing with regex patterns
    - Policy enforcement per route
    - Load balancing
    - Rate limiting
    - Request/response transformation
    - Metrics and logging
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.routes: List[RouteRule] = []
        self.upstreams: dict[str, List[UpstreamService]] = {}
        self.lb_state: dict = {}
        self.policy_engine: Optional[PolicyEngine] = None
        self.discovery: Optional[DiscoveryService] = None
        self.middlewares: List[Callable] = []
        
        # Load policy if configured
        if config.policy_path:
            self._load_policy()
    
    def _load_policy(self):
        """Load policy from file or directory."""
        from ..policy.loader import PolicyLoader
        from pathlib import Path
        
        path = Path(self.config.policy_path)
        if path.is_dir():
            policy = PolicyLoader.load_from_directory(str(path))
        else:
            policy = PolicyLoader.load_from_file(str(path))
        
        self.policy_engine = PolicyEngine(policy)
    
    def add_route(self, route: RouteRule):
        """Add a routing rule."""
        self.routes.append(route)
        # Sort by priority (highest first)
        self.routes.sort(key=lambda r: r.priority, reverse=True)
    
    def add_upstream(self, route_id: str, service: UpstreamService):
        """Add an upstream service for a route."""
        if route_id not in self.upstreams:
            self.upstreams[route_id] = []
        self.upstreams[route_id].append(service)
    
    def set_discovery(self, discovery: DiscoveryService):
        """Set discovery service for dynamic routing."""
        self.discovery = discovery
    
    def add_middleware(self, middleware: Callable):
        """Add a middleware function."""
        self.middlewares.append(middleware)
    
    def route(self, request: GatewayRequest) -> GatewayResponse:
        """
        Route a request through the gateway.
        
        This is the main entry point for request processing.
        """
        start_time = time.time()
        
        # Find matching route
        route = self._find_route(request)
        if not route:
            return GatewayResponse(
                request_id=request.id,
                status_code=404,
                body={"error": "No matching route"},
                latency_ms=(time.time() - start_time) * 1000,
            )
        
        # Run pre-routing middlewares
        for middleware in self.middlewares:
            result = middleware(request, route, phase="pre")
            if result is not None:
                return result  # Middleware returned a response
        
        # Enforce policy
        if route.policy_enabled and self.policy_engine:
            policy_decision = self._enforce_policy(request, route)
            if not policy_decision.allowed:
                return GatewayResponse(
                    request_id=request.id,
                    status_code=403,
                    body={"error": "Policy denied", "reason": policy_decision.reason},
                    latency_ms=(time.time() - start_time) * 1000,
                )
        
        # Select upstream
        upstream = self._select_upstream(route)
        if not upstream:
            return GatewayResponse(
                request_id=request.id,
                status_code=503,
                body={"error": "No healthy upstream available"},
                latency_ms=(time.time() - start_time) * 1000,
            )
        
        # Forward request
        response = self._forward_request(request, route, upstream)
        
        # Run post-routing middlewares
        for middleware in self.middlewares:
            result = middleware(request, route, response, phase="post")
            if result is not None:
                return result
        
        response.latency_ms = (time.time() - start_time) * 1000
        return response
    
    def _find_route(self, request: GatewayRequest) -> Optional[RouteRule]:
        """Find the first matching route."""
        for route in self.routes:
            if route.matches(request):
                return route
        return None
    
    def _enforce_policy(self, request: GatewayRequest, route: RouteRule):
        """Enforce policy for a request."""
        # Build context from request
        context = {
            'agent_did': request.agent_did,
            'requester_did': request.requester_did,
            'capability_name': request.capability_name or route.required_capability,
            'delegation_depth': request.delegation_depth,
            'is_delegation': request.is_delegation,
            'client_ip': request.client_ip,
            'path': request.path,
            'method': request.method,
        }
        
        # Add route-specific requirements
        if route.required_trust_score > 0:
            context['min_trust_score'] = route.required_trust_score
        if route.require_verified:
            context['require_verified'] = True
        
        return self.policy_engine.evaluate(context)
    
    def _select_upstream(self, route: RouteRule) -> Optional[UpstreamService]:
        """Select an upstream service using load balancing."""
        # Check static upstreams first
        if route.id in self.upstreams and self.upstreams[route.id]:
            services = self.upstreams[route.id]
            return self._load_balance(services, route.load_balancer)
        
        # Fall back to discovery if configured
        if self.discovery and route.required_capability:
            # Would query discovery service for capable agents
            # For now, return None
            pass
        
        return None
    
    def _load_balance(
        self, 
        services: List[UpstreamService], 
        strategy: str
    ) -> Optional[UpstreamService]:
        """Apply load balancing strategy."""
        if strategy == "round_robin":
            return LoadBalancer.round_robin(services, self.lb_state)
        elif strategy == "weighted_round_robin":
            return LoadBalancer.weighted_round_robin(services, self.lb_state)
        elif strategy == "least_connections":
            return LoadBalancer.least_connections(services, self.lb_state)
        elif strategy == "random":
            return LoadBalancer.random(services, self.lb_state)
        else:
            # Default to first healthy
            for s in services:
                if s.is_healthy():
                    return s
            return None
    
    def _forward_request(
        self, 
        request: GatewayRequest, 
        route: RouteRule, 
        upstream: UpstreamService
    ) -> GatewayResponse:
        """Forward request to upstream service."""
        # This is a placeholder - in real implementation would use httpx/aiohttp
        # For now, return a mock response
        upstream_start = time.time()
        
        # Simulate upstream call
        # In reality: response = await http_client.request(...)
        
        upstream_latency = (time.time() - upstream_start) * 1000
        
        return GatewayResponse(
            request_id=request.id,
            status_code=200,
            body={"message": "Request forwarded", "upstream": upstream.url},
            upstream_latency_ms=upstream_latency,
        )
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        healthy_upstreams = 0
        total_upstreams = 0
        
        for services in self.upstreams.values():
            for service in services:
                total_upstreams += 1
                if service.is_healthy():
                    healthy_upstreams += 1
        
        return {
            "status": "healthy" if healthy_upstreams > 0 else "degraded",
            "upstreams": {
                "healthy": healthy_upstreams,
                "total": total_upstreams,
            },
            "routes": len(self.routes),
            "policy_loaded": self.policy_engine is not None,
        }
    
    def get_metrics(self) -> dict:
        """Get gateway metrics."""
        return {
            "routes": len(self.routes),
            "upstreams": sum(len(s) for s in self.upstreams.values()),
            "middlewares": len(self.middlewares),
            "policy_rules": len(self.policy_engine.policy.rules) if self.policy_engine else 0,
        }
    
    def list_routes(self) -> list:
        """List all routes."""
        return [
            {
                "id": r.id,
                "name": r.name,
                "path_pattern": r.path_pattern,
                "methods": r.methods,
                "target_url": r.target_url,
                "required_capability": r.required_capability,
                "enabled": r.enabled,
                "priority": r.priority,
            }
            for r in self.routes
        ]
    
    def list_upstreams(self) -> dict:
        """List all upstreams grouped by route."""
        result = {}
        for route_id, services in self.upstreams.items():
            result[route_id] = [
                {
                    "id": s.id,
                    "name": s.name,
                    "url": s.url,
                    "weight": s.weight,
                    "healthy": s.healthy,
                }
                for s in services
            ]
        return result