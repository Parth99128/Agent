"""
Registry Server

FastAPI server for the OAI Network Agent Registry.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from .service import RegistryService, RegistryConfig
from .models import (
    RegistryEntry,
    RegistrationRequest,
    RegistrationResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    HealthStatus,
    DiscoveryQuery,
    DiscoveryResponse,
)
from ..core.capabilities.models import AgentManifest
from ..core.observability import (
    setup_json_logging, get_logger, MetricsMiddleware, metrics_endpoint,
    record_agent_discovery, log_request, log_response, log_error,
    log_agent_action
)

# Global registry service
_registry_service: Optional[RegistryService] = None

# Setup structured logging
logger = setup_json_logging("oai-network-registry")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _registry_service
    config = RegistryConfig()
    _registry_service = RegistryService(config)
    await _registry_service.start()
    yield
    await _registry_service.stop()


app = FastAPI(
    title="OAI Network Registry",
    description="Agent registry for discovery and health monitoring",
    version="0.1.0",
    lifespan=lifespan,
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware, service_name="registry")

# Add metrics endpoint
app.add_route("/metrics", metrics_endpoint, methods=["GET"])


def get_registry() -> RegistryService:
    if _registry_service is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return _registry_service


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/health", trace_id)
    return {"status": "healthy", "service": "oai-network-registry"}


@app.get("/stats")
async def get_stats(request: Request, registry: RegistryService = Depends(get_registry)):
    """Get registry statistics."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", "/stats", trace_id)
    return await registry.get_stats()


@app.post("/register", response_model=RegistrationResponse)
async def register_agent(
    request: Request,
    reg_request: RegistrationRequest,
    registry: RegistryService = Depends(get_registry),
):
    """Register a new agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/register", trace_id)
    
    try:
        manifest = AgentManifest(**reg_request.manifest)
        response = await registry.register_agent(manifest)
        
        # Log agent registration
        log_agent_action(logger, "registered", response.agent_did, trace_id)
        
        return response
    except Exception as e:
        log_error(logger, "Failed to register agent", trace_id, error=e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    request: Request,
    hb_request: HeartbeatRequest,
    registry: RegistryService = Depends(get_registry),
):
    """Receive agent heartbeat."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/heartbeat", trace_id, agent_did=hb_request.agent_did)
    
    try:
        response = await registry.heartbeat(hb_request)
        
        # Log agent heartbeat
        log_agent_action(logger, "heartbeat", hb_request.agent_did, trace_id)
        
        return response
    except Exception as e:
        log_error(logger, "Heartbeat failed", trace_id, error=e, agent_did=hb_request.agent_did)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/unregister")
async def unregister_agent(
    request: Request,
    agent_did: str,
    registry: RegistryService = Depends(get_registry),
):
    """Unregister an agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/unregister", trace_id, agent_did=agent_did)
    
    try:
        await registry.unregister_agent(agent_did)
        
        # Log agent unregistration
        log_agent_action(logger, "unregistered", agent_did, trace_id)
        
        return {"success": True, "message": f"Agent {agent_did} unregistered"}
    except Exception as e:
        log_error(logger, "Failed to unregister agent", trace_id, error=e, agent_did=agent_did)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents/{agent_did}", response_model=RegistryEntry)
async def get_agent(
    request: Request,
    agent_did: str,
    registry: RegistryService = Depends(get_registry),
):
    """Get agent by DID."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", f"/agents/{agent_did}", trace_id, agent_did=agent_did)
    
    entry = await registry.get_agent(agent_did)
    if not entry:
        log_error(logger, "Agent not found", trace_id, agent_did=agent_did)
        raise HTTPException(status_code=404, detail="Agent not found")
    return entry


@app.get("/agents/{agent_did}/trust-history")
async def get_trust_history(
    request: Request,
    agent_did: str,
    limit: int = 100,
    offset: int = 0,
    registry: RegistryService = Depends(get_registry),
):
    """Get trust history for an agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", f"/agents/{agent_did}/trust-history", trace_id, agent_did=agent_did)
    
    entry = await registry.get_agent(agent_did)
    if not entry:
        log_error(logger, "Agent not found", trace_id, agent_did=agent_did)
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get trust events from trust store
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
    registry: RegistryService = Depends(get_registry),
):
    """Get trust score for an agent."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "GET", f"/trust/{agent_did}", trace_id, agent_did=agent_did)
    
    entry = await registry.get_agent(agent_did)
    if not entry:
        log_error(logger, "Agent not found", trace_id, agent_did=agent_did)
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get trust score from trust store
    from ..core.trust.store import TrustStore
    from ..core.trust.calculator import TrustCalculator
    trust_store = TrustStore()
    calculator = TrustCalculator(store=trust_store)
    
    # Calculate trust score - returns default score (0.5) for new agents with no history
    score = calculator.calculate(agent_did, store=trust_store)
    
    return score.model_dump(mode='json')


@app.post("/discover", response_model=DiscoveryResponse)
async def discover_agents(
    request: Request,
    query: DiscoveryQuery,
    registry: RegistryService = Depends(get_registry),
):
    """Discover agents matching criteria."""
    trace_id = getattr(request.state, "trace_id", "no-trace")
    log_request(logger, "POST", "/discover", trace_id, capability=query.capability)
    
    try:
        # Extract natural language query from capability field if it looks like a query
        nl_query = None
        capability = query.capability
        if capability and (" " in capability or len(capability) > 30):
            # Looks like a natural language query
            nl_query = capability
            capability = "general"
        
        results = await registry.discover_agents(
            query=query,
            capability=capability,
            nl_query=nl_query,
        )
        
        # Record discovery metric
        record_agent_discovery("registry", capability or "unknown")
        
        # Log discovery
        log_agent_action(logger, "discovered", f"{len(results)} agents", trace_id, 
                        capability=capability, nl_query=nl_query)
        
        return DiscoveryResponse(agents=results, total=len(results))
    except Exception as e:
        log_error(logger, "Discovery failed", trace_id, error=e)
        raise HTTPException(status_code=400, detail=str(e))


def main():
    """Run the registry server."""
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "oai_network.registry.server:app",
        host="0.0.0.0",
        port=8081,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()