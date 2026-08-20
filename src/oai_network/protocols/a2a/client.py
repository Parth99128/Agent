"""
A2A Client

Client for communicating with A2A agents.
"""

import asyncio
import json
import uuid
from typing import Optional, Any, Dict, Callable, Awaitable
from datetime import datetime, timezone

from .models import (
    A2ARequest, A2AResponse, A2AError, A2AErrorCode,
    AgentCard, CapabilityQuery, CapabilityResponse,
    DelegationRequest, DelegationResponse,
    NegotiationRequest, NegotiationResponse,
)


class A2AClient:
    """
    Client for A2A protocol communication.
    
    Supports:
    - HTTP/REST communication
    - WebSocket communication
    - Capability queries
    - Delegation
    - Negotiation
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._ws = None
        self._ws_task: Optional[asyncio.Task] = None

    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> A2AResponse:
        """Send a JSON-RPC request and return the response."""
        import httpx

        request = A2ARequest(
            method=method,
            params=params or {},
            id=request_id or str(uuid.uuid4()),
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a",
                json=request.model_dump(mode='json'),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return A2AResponse(**data)

    async def capability_query(
        self,
        query: str,
        capability_type: Optional[str] = None,
        tags: Optional[list] = None,
        max_results: int = 10,
    ) -> CapabilityResponse:
        """Query for agent capabilities."""
        import httpx

        cap_query = CapabilityQuery(
            query=query,
            capability_type=capability_type,
            tags=tags or [],
            max_results=max_results,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/capabilities/query",
                json=cap_query.model_dump(mode='json'),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return CapabilityResponse(**data)

    async def delegate(
        self,
        capability: str,
        input_data: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None,
    ) -> DelegationResponse:
        """Delegate a task to another agent."""
        import httpx

        request = DelegationRequest(
            capability=capability,
            input_data=input_data,
            requirements=requirements or {},
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/delegate",
                json=request.model_dump(mode='json'),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return DelegationResponse(**data)

    async def negotiate(
        self,
        template_id: str,
        parameters: Dict[str, Any],
    ) -> NegotiationResponse:
        """Start a negotiation session."""
        import httpx

        request = NegotiationRequest(
            template_id=template_id,
            parameters=parameters,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/a2a/negotiate",
                json=request.model_dump(mode='json'),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return NegotiationResponse(**data)

    async def connect_websocket(self, ws_url: Optional[str] = None):
        """Connect to A2A WebSocket endpoint."""
        import websockets

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
                pass  # Handle messages
        except Exception:
            pass

    async def send_websocket_message(self, message: Dict[str, Any]):
        """Send a message over WebSocket."""
        if self._ws:
            await self._ws.send(json.dumps(message))

    async def health_check(self) -> bool:
        """Check if the A2A endpoint is healthy."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False