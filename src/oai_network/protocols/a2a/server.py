"""
A2A Server

Server implementation for the A2A protocol.
"""

import asyncio
import json
from typing import Optional, Any, Dict, Callable, Awaitable, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .models import (
    A2ARequest, A2AResponse, A2AError, A2AMessage,
    A2AMessageType, A2ACapabilityQuery, A2ACapabilityResponse,
    A2ADelegationRequest, A2ADelegationResponse, A2ADelegationStatus,
    A2ANegotiationStart, A2ANegotiationOffer, A2ANegotiationAccept,
    A2ANegotiationReject, A2ANegotiationComplete,
    create_response, create_error
)
from ...core.identity.models import AgentIdentity
from ...core.identity.verifier import IdentityVerifier
from ...core.capabilities.models import AgentManifest, Capability
from ...core.discovery.service import DiscoveryService
from ...core.negotiation.protocol import NegotiationProtocol
from ...core.delegation.manager import DelegationManager


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
        discovery_service: Optional[DiscoveryService] = None,
        negotiation_protocol: Optional[NegotiationProtocol] = None,
        delegation_manager: Optional[DelegationManager] = None,
        verify_requests: bool = True,
    ):
        self.identity = agent_identity
        self.private_key = private_key
        self.manifest = manifest
        self.discovery = discovery_service
        self.negotiation = negotiation_protocol
        self.delegation = delegation_manager
        self.verify_requests = verify_requests
        self.verifier = IdentityVerifier()
        
        # Capability handlers
        self._capability_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        
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
        
        # Health check
        @app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.identity.did}
        
        # Agent card endpoint (A2A standard)
        @app.get("/.well-known/agent-card")
        async def agent_card():
            return self.manifest.to_dict()
        
        # A2A request endpoint
        @app.post("/a2a/request")
        async def handle_request(request: Request):
            return await self._handle_a2a_request(request)
        
        # A2A notification endpoint
        @app.post("/a2a/notify")
        async def handle_notification(request: Request):
            return await self._handle_a2a_notification(request)
        
        # Capability query endpoint
        @app.post("/a2a/capabilities/query")
        async def handle_capability_query(request: Request):
            return await self._handle_capability_query(request)
        
        # Delegation endpoint
        @app.post("/a2a/delegate")
        async def handle_delegation(request: Request):
            return await self._handle_delegation(request)
        
        # Negotiation endpoint
        @app.post("/a2a/negotiate")
        async def handle_negotiation(request: Request):
            return await self._handle_negotiation(request)
        
        # WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
        
        return app
    
    def register_capability(self, name: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]]):
        """Register a capability handler."""
        self._capability_handlers[name] = handler
    
    async def _handle_a2a_request(self, request: Request) -> JSONResponse:
        """Handle an A2A request."""
        try:
            data = await request.json()
            a2a_request = A2ARequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content=create_error(
                    sender_did=self.identity.did,
                    code="INVALID_REQUEST",
                    message=f"Invalid request format: {str(e)}",
                ).model_dump(mode='json')
            )
        
        # Verify signature if enabled
        if self.verify_requests:
            if not a2a_request.signature:
                return JSONResponse(
                    status_code=401,
                    content=create_error(
                        sender_did=self.identity.did,
                        code="UNAUTHORIZED",
                        message="Missing signature",
                    ).model_dump(mode='json')
                )
            
            # In real implementation, would verify signature against sender's public key
            # For now, skip actual verification
        
        # Check if we have the capability
        capability = self.manifest.get_capability(a2a_request.capability)
        if not capability:
            return JSONResponse(
                status_code=404,
                content=create_error(
                    sender_did=self.identity.did,
                    code="CAPABILITY_NOT_FOUND",
                    message=f"Capability '{a2a_request.capability}' not found",
                ).model_dump(mode='json')
            )
        
        # Validate input
        valid, errors = capability.input_schema.validate(a2a_request.parameters)
        if not valid:
            return JSONResponse(
                status_code=400,
                content=create_error(
                    sender_did=self.identity.did,
                    code="INVALID_PARAMETERS",
                    message=f"Invalid parameters: {', '.join(errors)}",
                ).model_dump(mode='json')
            )
        
        # Execute capability
        handler = self._capability_handlers.get(a2a_request.capability)
        if not handler:
            return JSONResponse(
                status_code=501,
                content=create_error(
                    sender_did=self.identity.did,
                    code="NOT_IMPLEMENTED",
                    message=f"Capability '{a2a_request.capability}' not implemented",
                ).model_dump(mode='json')
            )
        
        try:
            start_time = datetime.now(timezone.utc)
            result = await handler(a2a_request.parameters)
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            response = create_response(
                sender_did=self.identity.did,
                request_id=a2a_request.id,
                success=True,
                result=result,
                latency_ms=latency_ms,
            )
            response.sign(self.private_key)
            
            return JSONResponse(content=response.model_dump(mode='json'))
            
        except Exception as e:
            response = create_response(
                sender_did=self.identity.did,
                request_id=a2a_request.id,
                success=False,
                error=str(e),
            )
            response.sign(self.private_key)
            
            return JSONResponse(
                status_code=500,
                content=response.model_dump(mode='json')
            )
    
    async def _handle_a2a_notification(self, request: Request) -> JSONResponse:
        """Handle an A2A notification."""
        try:
            data = await request.json()
            message = A2AMessage(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid notification: {str(e)}"}
            )
        
        # Process notification based on type
        # In a real implementation, would route to appropriate handlers
        
        return JSONResponse(content={"status": "received"})
    
    async def _handle_capability_query(self, request: Request) -> JSONResponse:
        """Handle a capability query."""
        try:
            data = await request.json()
            query = A2ACapabilityQuery(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content=create_error(
                    sender_did=self.identity.did,
                    code="INVALID_QUERY",
                    message=f"Invalid query format: {str(e)}",
                ).model_dump(mode='json')
            )
        
        # Use discovery service if available
        if self.discovery:
            from ..core.discovery.models import DiscoveryQuery, SortBy, SortOrder
            discovery_query = DiscoveryQuery(
                query=query.payload.get('query', ''),
                capability_type=query.payload.get('filters', {}).get('capability_type'),
                tags=query.payload.get('filters', {}).get('tags', []),
                min_trust_score=query.payload.get('filters', {}).get('min_trust_score', 0.0),
                limit=query.payload.get('max_results', 10),
                sort_by=SortBy.RELEVANCE,
            )
            results = self.discovery.discover(discovery_query)
            agents = [r.to_dict() for r in results]
        else:
            # Fallback: return self if matches
            matches = self.manifest.find_capabilities(query.payload.get('query', ''))
            agents = [self.manifest.to_dict()] if matches else []
        
        response = A2ACapabilityResponse(
            sender_did=self.identity.did,
            query_id=query.id,
            agents=agents,
            total_count=len(agents),
        )
        response.sign(self.private_key)
        
        return JSONResponse(content=response.model_dump(mode='json'))
    
    async def _handle_delegation(self, request: Request) -> JSONResponse:
        """Handle a delegation request."""
        try:
            data = await request.json()
            delegation = A2ADelegationRequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content=create_error(
                    sender_did=self.identity.did,
                    code="INVALID_DELEGATION",
                    message=f"Invalid delegation request: {str(e)}",
                ).model_dump(mode='json')
            )
        
        # Check delegation depth
        if delegation.payload.get('current_depth', 0) >= delegation.payload.get('max_depth', 3):
            response = A2ADelegationResponse(
                sender_did=self.identity.did,
                task_id=delegation.payload['task_id'],
                accepted=False,
                error="Maximum delegation depth reached",
            )
            response.sign(self.private_key)
            return JSONResponse(content=response.model_dump(mode='json'))
        
        # Check if we have the capability
        capability_name = delegation.payload.get('capability')
        capability = self.manifest.get_capability(capability_name)
        if not capability:
            response = A2ADelegationResponse(
                sender_did=self.identity.did,
                task_id=delegation.payload['task_id'],
                accepted=False,
                error=f"Capability '{capability_name}' not available",
            )
            response.sign(self.private_key)
            return JSONResponse(content=response.model_dump(mode='json'))
        
        # Accept delegation
        response = A2ADelegationResponse(
            sender_did=self.identity.did,
            task_id=delegation.payload['task_id'],
            accepted=True,
            estimated_completion_ms=capability.estimated_latency_ms or 5000,
        )
        response.sign(self.private_key)
        
        # Execute delegation asynchronously
        asyncio.create_task(self._execute_delegation(delegation))
        
        return JSONResponse(content=response.model_dump(mode='json'))
    
    async def _execute_delegation(self, delegation: A2ADelegationRequest):
        """Execute a delegated task."""
        task_id = delegation.payload['task_id']
        capability_name = delegation.payload['capability']
        input_data = delegation.payload.get('input_data', {})
        callback_url = delegation.payload.get('callback_url')
        
        handler = self._capability_handlers.get(capability_name)
        if not handler:
            await self._send_status_update(task_id, "failed", error="Capability not implemented")
            return
        
        try:
            # Send progress update
            await self._send_status_update(task_id, "running", progress=0.1)
            
            # Execute
            result = await handler(input_data)
            
            # Send completion
            await self._send_status_update(task_id, "completed", result=result, progress=1.0)
            
            # Call callback if provided
            if callback_url:
                await self._call_callback(callback_url, task_id, "completed", result)
                
        except Exception as e:
            await self._send_status_update(task_id, "failed", error=str(e))
            if callback_url:
                await self._call_callback(callback_url, task_id, "failed", error=str(e))
    
    async def _send_status_update(
        self, 
        task_id: str, 
        status: str, 
        progress: float = 0.0,
        result: Any = None,
        error: str = None
    ):
        """Send a delegation status update via WebSocket."""
        message = A2ADelegationStatus(
            sender_did=self.identity.did,
            task_id=task_id,
            status=status,
            progress=progress,
            result=result,
            error=error,
        )
        message.sign(self.private_key)
        
        # Broadcast to WebSocket connections
        for ws in self._ws_connections:
            try:
                await ws.send_json(message.model_dump(mode='json'))
            except Exception:
                pass
    
    async def _call_callback(self, url: str, task_id: str, status: str, result: Any = None, error: str = None):
        """Call a callback URL."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json={
                    "task_id": task_id,
                    "status": status,
                    "result": result,
                    "error": error,
                })
        except Exception:
            pass
    
    async def _handle_negotiation(self, request: Request) -> JSONResponse:
        """Handle a negotiation request."""
        try:
            data = await request.json()
            # Determine message type and parse accordingly
            msg_type = data.get('type')
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content=create_error(
                    sender_did=self.identity.did,
                    code="INVALID_NEGOTIATION",
                    message=f"Invalid negotiation message: {str(e)}",
                ).model_dump(mode='json')
            )
        
        # In a real implementation, would route to negotiation protocol
        # For now, return a simple response
        return JSONResponse(content={"status": "negotiation not fully implemented"})
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        
        try:
            while True:
                data = await websocket.receive_json()
                # Handle incoming WebSocket messages
                # Could be used for real-time negotiation, status updates, etc.
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            if websocket in self._ws_connections:
                self._ws_connections.remove(websocket)
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self.app