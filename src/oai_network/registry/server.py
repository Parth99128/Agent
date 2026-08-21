"""
Registry Server

FastAPI server for the OAI Network Agent Registry.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
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

# Global registry service
_registry_service: Optional[RegistryService] = None


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


def get_registry() -> RegistryService:
    if _registry_service is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return _registry_service


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "oai-network-registry"}


@app.get("/stats")
async def get_stats(registry: RegistryService = Depends(get_registry)):
    """Get registry statistics."""
    return await registry.get_stats()


@app.post("/register", response_model=RegistrationResponse)
async def register_agent(
    request: RegistrationRequest,
    registry: RegistryService = Depends(get_registry),
):
    """Register a new agent."""
    try:
        manifest = AgentManifest(**request.manifest)
        response = await registry.register_agent(manifest)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    request: HeartbeatRequest,
    registry: RegistryService = Depends(get_registry),
):
    """Receive agent heartbeat."""
    try:
        response = await registry.heartbeat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/unregister")
async def unregister_agent(
    agent_did: str,
    registry: RegistryService = Depends(get_registry),
):
    """Unregister an agent."""
    try:
        await registry.unregister_agent(agent_did)
        return {"success": True, "message": f"Agent {agent_did} unregistered"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents/{agent_did}", response_model=RegistryEntry)
async def get_agent(
    agent_did: str,
    registry: RegistryService = Depends(get_registry),
):
    """Get agent by DID."""
    entry = await registry.get_agent(agent_did)
    if not entry:
        raise HTTPException(status_code=404, detail="Agent not found")
    return entry


@app.get("/agents/{agent_did}/trust-history")
async def get_trust_history(
    agent_did: str,
    limit: int = 100,
    offset: int = 0,
    registry: RegistryService = Depends(get_registry),
):
    """Get trust history for an agent."""
    entry = await registry.get_agent(agent_did)
    if not entry:
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


@app.post("/discover", response_model=DiscoveryResponse)
async def discover_agents(
    query: DiscoveryQuery,
    registry: RegistryService = Depends(get_registry),
):
    """Discover agents matching criteria."""
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
        return DiscoveryResponse(agents=results, total=len(results))
    except Exception as e:
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