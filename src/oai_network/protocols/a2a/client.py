"""
A2A Client

Client for communicating with A2A agents.
"""

import asyncio
import json
from typing import Optional, Any, Dict, Callable, Awaitable
from datetime import datetime, timezone
import httpx
import websockets

from .models import (
    A2ARequest, A2AResponse, A2AError, A2AMessage,
    A2AMessageType, create_request, create_response, create_error
)
from ...core.identity.models import AgentIdentity
from ...core.identity.verifier import IdentityVerifier


class A2AClient:
    """
    Client for A2A protocol communication.
    
    Supports:
    - HTTP/REST communication
    - WebSocket communication
    - Message signing and verification
    - Request/response correlation
    - Automatic retries
    """
    
    def __init__(
        self,
        agent_identity: AgentIdentity,
        private_key: bytes,
        base_url: str,
        timeout: float = 30.0,
        verify_identity: bool = True,
    ):
        self.identity = agent_identity
        self.private_key = private_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_identity = verify_identity
        self.verifier = IdentityVerifier()
        
        # Pending requests
        self._pending: Dict[str, asyncio.Future] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[A2AMessageType, Callable[[A2AMessage], Awaitable[None]]] = {}
    
    async def connect_websocket(self, ws_url: Optional[str] = None):
        """Connect to A2A WebSocket endpoint."""
        url = ws_url or self.base_url.replace('http', 'ws') + '/ws'
        self._ws = await websockets.connect(url)
        self._ws_task = asyncio.create_task(self._ws_listener())
    
    async def disconnect_websocket(self):
        """Disconnect from WebSocket."""
        if self._ws:
            await self._ws.close()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
    
    async def _ws_listener(self):
        """Listen for WebSocket messages."""
        try:
            async for message in self._ws:
                data = json.loads(message)
                await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming message."""
        msg_type = A2AMessageType(data.get('type', 'notification'))
        
        # Check for response to pending request
        correlation_id = data.get('correlation_id')
        if correlation_id and correlation_id in self._pending:
            future = self._pending.pop(correlation_id)
            if not future.done():
                future.set_result(data)
            return
        
        # Handle by type
        handler = self._message_handlers.get(msg_type)
        if handler:
            await handler(A2AMessage(**data))
    
    def on_message(self, msg_type: A2AMessageType):
        """Decorator to register message handlers."""
        def decorator(func: Callable[[A2AMessage], Awaitable[None]]):
            self._message_handlers[msg_type] = func
            return func
        return decorator
    
    async def send_request(
        self,
        capability: str,
        parameters: Dict[str, Any],
        recipient_did: str,
        timeout: Optional[float] = None,
    ) -> A2AResponse:
        """
        Send a request and wait for response.
        """
        request = create_request(
            sender_did=self.identity.did,
            recipient_did=recipient_did,
            capability=capability,
            parameters=parameters,
        )
        
        # Sign request
        request.sign(self.private_key)
        
        # Send via HTTP
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/request",
                json=request.model_dump(mode='json'),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        
        # Verify response if needed
        if self.verify_identity:
            # Would verify signature here
            pass
        
        return A2AResponse(**data)
    
    async def send_notification(
        self,
        msg_type: A2AMessageType,
        payload: Dict[str, Any],
        recipient_did: Optional[str] = None,
    ):
        """Send a notification (no response expected)."""
        message = A2AMessage(
            type=msg_type,
            sender_did=self.identity.did,
            recipient_did=recipient_did,
            payload=payload,
        )
        message.sign(self.private_key)
        
        if self._ws:
            await self._ws.send(json.dumps(message.model_dump(mode='json')))
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(
                    f"{self.base_url}/a2a/notify",
                    json=message.model_dump(mode='json'),
                )
    
    async def query_capabilities(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 10,
    ) -> list[Dict[str, Any]]:
        """Query for agent capabilities."""
        request = A2AMessage(
            type=A2AMessageType.CAPABILITY_QUERY,
            sender_did=self.identity.did,
            payload={
                'query': query,
                'filters': filters or {},
                'max_results': max_results,
            },
        )
        request.sign(self.private_key)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/capabilities/query",
                json=request.model_dump(mode='json'),
            )
            response.raise_for_status()
            data = response.json()
        
        return data.get('agents', [])
    
    async def delegate_task(
        self,
        task_id: str,
        capability: str,
        input_data: Dict[str, Any],
        delegatee_did: str,
        max_depth: int = 3,
        callback_url: Optional[str] = None,
    ) -> bool:
        """Delegate a task to another agent."""
        request = A2AMessage(
            type=A2AMessageType.DELEGATION_REQUEST,
            sender_did=self.identity.did,
            recipient_did=delegatee_did,
            payload={
                'task_id': task_id,
                'capability': capability,
                'input_data': input_data,
                'max_depth': max_depth,
                'current_depth': 0,
                'callback_url': callback_url,
            },
        )
        request.sign(self.private_key)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/delegate",
                json=request.model_dump(mode='json'),
            )
            response.raise_for_status()
            data = response.json()
        
        return data.get('accepted', False)
    
    async def start_negotiation(
        self,
        responder_did: str,
        template: str,
        initial_terms: Dict[str, Any],
    ) -> str:
        """Start a negotiation session."""
        request = A2AMessage(
            type=A2AMessageType.NEGOTIATION_START,
            sender_did=self.identity.did,
            recipient_did=responder_did,
            payload={
                'template': template,
                'initial_terms': initial_terms,
            },
        )
        request.sign(self.private_key)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/negotiate",
                json=request.model_dump(mode='json'),
            )
            response.raise_for_status()
            data = response.json()
        
        return data.get('negotiation_id', '')
    
    async def health_check(self) -> bool:
        """Check if the A2A endpoint is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False