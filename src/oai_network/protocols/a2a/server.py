"""
A2A Server

Server implementation for the A2A protocol.
"""

import asyncio
import json
from typing import Optional, Any, Dict, Callable, Awaitable, List
from datetime import datetime, timezone
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .models import (
    A2ARequest, A2AResponse, A2AError, A2AErrorCode,
    AgentCard, CapabilityQuery, CapabilityResponse,
    DelegationRequest, DelegationResponse,
    NegotiationRequest, NegotiationResponse,
)
from ...core.identity.models import AgentIdentity
from ...core.capabilities.models import AgentManifest


class A2AServer:
    """
    A2A Protocol Server.
    
    Handles:
    - Capability queries
    - Task execution requests
    - Delegation requests
    - Negotiation sessions
    - WebSocket connections for real-time updates
    """

    def __init__(
        self,
        agent_identity: AgentIdentity,
        private_key: bytes,
        manifest: AgentManifest,
        discovery_service: Optional[Any] = None,
        negotiation_protocol: Optional[Any] = None,
        delegation_manager: Optional[Any] = None,
        verify_requests: bool = True,
    ):
        self.identity = agent_identity
        self.private_key = private_key
        self.manifest = manifest
        self.discovery = discovery_service
        self.negotiation = negotiation_protocol
        self.delegation = delegation_manager
        self.verify_requests = verify_requests

        # Capability handlers
        self._capability_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}

        # Delegation and negotiation handlers
        self.delegation_handler: Optional[Callable] = None
        self.negotiation_handler: Optional[Callable] = None

        # WebSocket connections
        self._ws_connections: List[WebSocket] = []

        # Create FastAPI app
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        app = FastAPI(
            title=f"A2A Agent: {self.manifest.name}",
            description=self.manifest.description,
            version=self.manifest.version,
        )

        @app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.identity.did}

        @app.get("/.well-known/agent-card.json")
        async def agent_card():
            return {
                "agent_did": self.identity.did,
                "name": self.manifest.name,
                "description": self.manifest.description,
                "version": self.manifest.version,
                "capabilities": [c.name for c in self.manifest.capabilities],
                "endpoints": {"a2a": f"/a2a"},
            }

        @app.post("/a2a")
        async def handle_request(request: Request):
            return await self._handle_a2a_request(request)

        @app.post("/a2a/capabilities/query")
        async def handle_capability_query(request: Request):
            return await self._handle_capability_query(request)

        @app.post("/a2a/delegate")
        async def handle_delegation(request: Request):
            return await self._handle_delegation(request)

        @app.post("/a2a/negotiate")
        async def handle_negotiation(request: Request):
            return await self._handle_negotiation(request)

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

        return app

    def register_capability_handler(self, capability: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]]):
        """Register a capability handler."""
        self._capability_handlers[capability] = handler

    def register_delegation_handler(self, handler: Callable):
        """Register a delegation handler."""
        self.delegation_handler = handler

    def register_negotiation_handler(self, handler: Callable):
        """Register a negotiation handler."""
        self.negotiation_handler = handler

    async def _handle_a2a_request(self, request: Request) -> JSONResponse:
        """Handle an A2A JSON-RPC request."""
        try:
            data = await request.json()
            a2a_request = A2ARequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            error = A2AError(code=A2AErrorCode.PARSE_ERROR, message=f"Invalid request: {str(e)}")
            return JSONResponse(
                status_code=400,
                content=A2AResponse(error=error).model_dump(mode='json'),
            )

        # Execute capability handler if available
        handler = self._capability_handlers.get(a2a_request.method)
        if handler:
            try:
                result = await handler(a2a_request.params)
                return JSONResponse(content=A2AResponse(result=result, id=a2a_request.id).model_dump(mode='json'))
            except Exception as e:
                error = A2AError(code=A2AErrorCode.INTERNAL_ERROR, message=str(e))
                return JSONResponse(
                    status_code=500,
                    content=A2AResponse(error=error, id=a2a_request.id).model_dump(mode='json'),
                )

        error = A2AError(code=A2AErrorCode.METHOD_NOT_FOUND, message=f"Method not found: {a2a_request.method}")
        return JSONResponse(
            status_code=404,
            content=A2AResponse(error=error, id=a2a_request.id).model_dump(mode='json'),
        )

    async def _handle_capability_query(self, request: Request) -> JSONResponse:
        """Handle a capability query."""
        try:
            data = await request.json()
            query = CapabilityQuery(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

        # Return matching agents (simplified)
        agents = []
        for cap in self.manifest.capabilities:
            if query.query.lower() in cap.name.lower() or query.query.lower() in cap.description.lower():
                agents.append({
                    "agent_did": self.identity.did,
                    "capability": cap.name,
                    "relevance_score": 1.0,
                })

        response = CapabilityResponse(agents=agents, total_count=len(agents))
        return JSONResponse(content=response.model_dump(mode='json'))

    async def _handle_delegation(self, request: Request) -> JSONResponse:
        """Handle a delegation request."""
        try:
            data = await request.json()
            del_request = DelegationRequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

        if self.delegation_handler:
            try:
                result = await self.delegation_handler(del_request)
                return JSONResponse(content=result.model_dump(mode='json'))
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content=DelegationResponse(accepted=False, rejection_reason=str(e)).model_dump(mode='json'),
                )

        return JSONResponse(
            content=DelegationResponse(accepted=False, rejection_reason="No delegation handler").model_dump(mode='json')
        )

    async def _handle_negotiation(self, request: Request) -> JSONResponse:
        """Handle a negotiation request."""
        try:
            data = await request.json()
            neg_request = NegotiationRequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

        if self.negotiation_handler:
            try:
                result = await self.negotiation_handler(neg_request)
                return JSONResponse(content=result.model_dump(mode='json'))
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content=NegotiationResponse(accepted=False, rejection_reason=str(e)).model_dump(mode='json'),
                )

        return JSONResponse(
            content=NegotiationResponse(accepted=False, rejection_reason="No negotiation handler").model_dump(mode='json')
        )

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                # Process message
                await websocket.send_json({"status": "received"})
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in self._ws_connections:
                self._ws_connections.remove(websocket)

    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self.app