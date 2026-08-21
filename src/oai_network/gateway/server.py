"""
Gateway Server

FastAPI server for the OAI Network Gateway with policy enforcement.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

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


# Global gateway router
_gateway_router: Optional[GatewayRouter] = None


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


def get_gateway() -> GatewayRouter:
    if _gateway_router is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return _gateway_router


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "oai-network-gateway"}


@app.post("/route", response_model=GatewayResponse)
async def route_request(
    request: GatewayRequest,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Route a request through the gateway with policy enforcement."""
    try:
        response = gateway.route(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/policies")
async def add_policy(
    policy: Policy,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add a policy to the gateway."""
    try:
        gateway.policy_engine.add_policy(policy)
        return {"success": True, "policy_id": policy.policy_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/policies/{policy_id}")
async def remove_policy(
    policy_id: str,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Remove a policy from the gateway."""
    try:
        gateway.policy_engine.remove_policy(policy_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/policies")
async def list_policies(
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all policies."""
    return {"policies": gateway.policy_engine.list_policies()}


@app.post("/routes")
async def add_route(
    route: RouteRule,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add a route rule."""
    try:
        gateway.add_route(route)
        return {"success": True, "route_id": route.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/routes")
async def list_routes(
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all routes."""
    return {"routes": gateway.list_routes()}


@app.post("/upstreams")
async def add_upstream(
    route_id: str,
    upstream: UpstreamService,
    gateway: GatewayRouter = Depends(get_gateway),
):
    """Add an upstream service for a route."""
    try:
        gateway.add_upstream(route_id, upstream)
        return {"success": True, "upstream_id": upstream.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/upstreams")
async def list_upstreams(
    gateway: GatewayRouter = Depends(get_gateway),
):
    """List all upstream services."""
    return {"upstreams": gateway.list_upstreams()}


def main():
    """Run the gateway server."""
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "oai_network.gateway.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()