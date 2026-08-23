"""
Gateway Server

FastAPI server for the OAI Network Gateway with policy enforcement.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import Response

from .router import GatewayRouter, GatewayConfig
from .models import (
    GatewayRequest,
    GatewayResponse,
    RouteRule,
    UpstreamService,
    LoadBalancer,
)
from ..policy.engine import PolicyEngine
from ..policy.models import Policy
from ..core.discovery.service import DiscoveryService
from ..core.observability import (
    setup_json_logging, get_logger, MetricsMiddleware, metrics_endpoint,
    record_policy_denial, record_delegation, log_request, log_response,
    log_error, log_policy_check, log_delegation
)

# Global gateway router
_gateway_router: Optional[GatewayRouter] = None

# Setup structured logging
logger = setup_json_logging("oai-network-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _gateway_router
    config = GatewayConfig()
    _gateway_router = GatewayRouter(config)
    yield
    # Cleanup if needed


app = FastAPI(
    title="OAI Network Gateway",
    description="Policy-enforced gateway for agent communication",
    version="0.1.0",
    lifespan=lifespan,
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware, service_name="gateway")

# Add metrics endpoint
app.add_route("/metrics", metrics_endpoint, methods=["GET"])


def get_gateway() -> GatewayRouter:
    if _gateway_router is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return _gateway_router


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/health", trace_id)
    return {"status": "healthy", "service": "oai-network-gateway"}


@app.post("/route", response_model=GatewayResponse)
async def route_request(
    request: Request,
    gw_request: GatewayRequest,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Route a request through the gateway with policy enforcement."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/route", trace_id, target=gw_request.path)
    
    try:
        response = gateway.route(gw_request)
        
        # Log policy check result
        log_policy_check(logger, "routing", True, trace_id, target=gw_request.path)
        
        # Record delegation metric
        record_delegation("gateway", "success")
        
        log_response(logger, "POST", "/route", 200, 0, trace_id, target=gw_request.path)
        return response
    except Exception as e:
        # Check if it's a policy denial
        if "policy" in str(e).lower() or "denied" in str(e).lower():
            record_policy_denial("gateway", "policy_violation")
            log_policy_check(logger, "routing", False, trace_id, target=gw_request.path, error=str(e))
        else:
            record_delegation("gateway", "error")
            log_error(logger, "Routing failed", trace_id, error=e, target=gw_request.path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/policies")
async def add_policy(
    request: Request,
    policy: Policy,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add a policy to the gateway."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/policies", trace_id, policy_id=policy.policy_id)
    
    try:
        gateway.policy_engine.add_policy(policy)
        log_response(logger, "POST", "/policies", 200, 0, trace_id, policy_id=policy.policy_id)
        return {"success": True, "policy_id": policy.policy_id}
    except Exception as e:
        log_error(logger, "Failed to add policy", trace_id, error=e, policy_id=policy.policy_id)
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/policies/{policy_id}")
async def remove_policy(
    request: Request,
    policy_id: str,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Remove a policy from the gateway."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "DELETE", f"/policies/{policy_id}", trace_id, policy_id=policy_id)
    
    try:
        gateway.policy_engine.remove_policy(policy_id)
        log_response(logger, "DELETE", f"/policies/{policy_id}", 200, 0, trace_id, policy_id=policy_id)
        return {"success": True}
    except Exception as e:
        log_error(logger, "Failed to remove policy", trace_id, error=e, policy_id=policy_id)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/policies")
async def list_policies(
    request: Request,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all policies."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/policies", trace_id)
    return {"policies": gateway.policy_engine.list_policies()}


@app.post("/routes")
async def add_route(
    request: Request,
    route: RouteRule,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add a route rule."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/routes", trace_id, route_id=route.id)
    
    try:
        gateway.add_route(route)
        log_response(logger, "POST", "/routes", 200, 0, trace_id, route_id=route.id)
        return {"success": True, "route_id": route.id}
    except Exception as e:
        log_error(logger, "Failed to add route", trace_id, error=e, route_id=route.id)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/routes")
async def list_routes(
    request: Request,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all routes."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/routes", trace_id)
    return {"routes": gateway.list_routes()}


@app.post("/upstreams")
async def add_upstream(
    request: Request,
    route_id: str,
    upstream: UpstreamService,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add an upstream service for a route."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/upstreams", trace_id, route_id=route_id, upstream_id=upstream.id)
    
    try:
        gateway.add_upstream(route_id, upstream)
        log_response(logger, "POST", "/upstreams", 200, 0, trace_id, route_id=route_id, upstream_id=upstream.id)
        return {"success": True, "upstream_id": upstream.id}
    except Exception as e:
        log_error(logger, "Failed to add upstream", trace_id, error=e, route_id=route_id, upstream_id=upstream.id)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/upstreams")
async def list_upstreams(
    request: Request,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all upstream services."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/upstreams", trace_id)
    return {"upstreams": gateway.list_upstreams()}


@app.get("/agents/{agent_did}/trust-history")
async def get_trust_history(
    request: Request,
    agent_did: str,
    limit: int = 100,
    offset: int = 0,
):
    """Get trust history for an agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", f"/agents/{agent_did}/trust-history", trace_id, agent_did=agent_did)
    
    from ..core.trust.store import TrustStore
    trust_store = TrustStore()
    events = trust_store.get_events_for_agent(agent_did, limit=limit, offset=offset)
    
    return {
        "agent_did": agent_did,
        "events": [e.model_dump(mode='json') for e in events],
        "total": len(events),
        "limit": limit,
        "offset": offset,
    }


@app.get("/trust/{agent_did}")
async def get_trust_score(
    request: Request,
    agent_did: str,
):
    """Get trust score for an agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", f"/trust/{agent_did}", trace_id, agent_did=agent_did)
    
    from ..core.trust.store import TrustStore
    from ..core.trust.calculator import TrustCalculator
    trust_store = TrustStore()
    calculator = TrustCalculator(store=trust_store)
    
    # Calculate trust score - returns default score (0.5) for new agents with no history
    score = calculator.calculate(agent_did, store=trust_store)
    
    return score.model_dump(mode='json')


def main():
    """Run the gateway server."""
    uvicorn.run(
        "oai_network.gateway.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()