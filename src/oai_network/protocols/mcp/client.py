"""
MCP Client

Client for communicating with MCP servers.
"""

import asyncio
import json
from typing import Optional, Any, Dict, List, Callable, Awaitable
from datetime import datetime, timezone
import httpx
import websockets

from .models import (
    MCPRequest, MCPResponse, MCPNotification, MCPError,
    MCPMessageType, MCPTool, MCPResource, MCPPrompt,
    MCPInitializeRequest, MCPInitializeResponse,
    MCPToolsListRequest, MCPToolsListResponse,
    MCPToolsCallRequest, MCPToolsCallResponse,
    MCPResourcesListRequest, MCPResourcesListResponse,
    MCPResourcesReadRequest, MCPResourcesReadResponse,
    MCPPromptsListRequest, MCPPromptsListResponse,
    MCPPromptsGetRequest, MCPPromptsGetResponse,
    create_mcp_response, create_mcp_error, create_mcp_notification,
    MCPErrorCode
)


class MCPClient:
    """
    Client for MCP protocol communication.
    
    Supports:
    - HTTP/REST communication
    - WebSocket communication
    - Tool calling
    - Resource reading
    - Prompt management
    - Automatic initialization
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        client_info: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client_info = client_info or {"name": "oai-network-client", "version": "0.1.0"}
        
        # Pending requests
        self._pending: Dict[str, asyncio.Future] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._server_info: Optional[Dict[str, Any]] = None
        self._server_capabilities: Optional[Dict[str, Any]] = None
        self._notification_handlers: Dict[str, Callable[[MCPNotification], Awaitable[None]]] = {}
    
    async def initialize(self) -> MCPInitializeResponse:
        """Initialize connection to MCP server."""
        request = MCPInitializeRequest()
        request.params["clientInfo"] = self.client_info
        
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Initialization failed: {response.error}")
        
        self._initialized = True
        self._server_info = response.result.get("serverInfo")
        self._server_capabilities = response.result.get("capabilities")
        
        return MCPInitializeResponse(**response.model_dump())
    
    async def connect_websocket(self, ws_url: Optional[str] = None):
        """Connect to MCP WebSocket endpoint."""
        url = ws_url or self.base_url.replace('http', 'ws') + '/mcp'
        self._ws = await websockets.connect(url)
        self._ws_task = asyncio.create_task(self._ws_listener())
        
        # Initialize over WebSocket
        if not self._initialized:
            await self.initialize()
    
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
        # Check for response to pending request
        request_id = data.get('id')
        if request_id and request_id in self._pending:
            future = self._pending.pop(request_id)
            if not future.done():
                future.set_result(data)
            return
        
        # Handle notifications
        if 'method' in data and 'id' not in data:
            notification = MCPNotification(**data)
            handler = self._notification_handlers.get(notification.method)
            if handler:
                await handler(notification)
    
    def on_notification(self, method: str):
        """Decorator to register notification handlers."""
        def decorator(func: Callable[[MCPNotification], Awaitable[None]]):
            self._notification_handlers[method] = func
            return func
        return decorator
    
    async def _send_request(self, request: MCPRequest) -> MCPResponse:
        """Send a request and wait for response."""
        if self._ws:
            # Send via WebSocket
            future = asyncio.get_event_loop().create_future()
            self._pending[request.id] = future
            
            await self._ws.send(json.dumps(request.model_dump(exclude_none=True)))
            
            try:
                response_data = await asyncio.wait_for(future, timeout=self.timeout)
            except asyncio.TimeoutError:
                self._pending.pop(request.id, None)
                raise Exception(f"Request {request.id} timed out")
        else:
            # Send via HTTP
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    json=request.model_dump(exclude_none=True),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                response_data = response.json()
        
        if 'error' in response_data:
            return MCPError(**response_data)
        return MCPResponse(**response_data)
    
    async def send_notification(self, notification: MCPNotification):
        """Send a notification (no response expected)."""
        if self._ws:
            await self._ws.send(json.dumps(notification.model_dump(exclude_none=True)))
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(
                    f"{self.base_url}/mcp",
                    json=notification.model_dump(exclude_none=True),
                )
    
    # Tool methods
    async def list_tools(self) -> List[MCPTool]:
        """List available tools."""
        request = MCPToolsListRequest()
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Failed to list tools: {response.error}")
        
        tools_data = response.result.get("tools", [])
        return [MCPTool(**tool) for tool in tools_data]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool."""
        request = MCPToolsCallRequest()
        request.params = {"name": name, "arguments": arguments}
        
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Tool call failed: {response.error}")
        
        return response.result
    
    # Resource methods
    async def list_resources(self) -> List[MCPResource]:
        """List available resources."""
        request = MCPResourcesListRequest()
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Failed to list resources: {response.error}")
        
        resources_data = response.result.get("resources", [])
        return [MCPResource(**res) for res in resources_data]
    
    async def read_resource(self, uri: str) -> Any:
        """Read a resource."""
        request = MCPResourcesReadRequest()
        request.params = {"uri": uri}
        
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Failed to read resource: {response.error}")
        
        return response.result
    
    # Prompt methods
    async def list_prompts(self) -> List[MCPPrompt]:
        """List available prompts."""
        request = MCPPromptsListRequest()
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Failed to list prompts: {response.error}")
        
        prompts_data = response.result.get("prompts", [])
        return [MCPPrompt(**prompt) for prompt in prompts_data]
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Get a prompt."""
        request = MCPPromptsGetRequest()
        request.params = {"name": name, "arguments": arguments or {}}
        
        response = await self._send_request(request)
        
        if response.error:
            raise Exception(f"Failed to get prompt: {response.error}")
        
        return response.result
    
    # Utility methods
    async def ping(self) -> bool:
        """Send a ping to check connection."""
        request = MCPRequest(method="ping", params={})
        response = await self._send_request(request)
        return response.error is None
    
    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized
    
    @property
    def server_info(self) -> Optional[Dict[str, Any]]:
        """Get server info."""
        return self._server_info
    
    @property
    def server_capabilities(self) -> Optional[Dict[str, Any]]:
        """Get server capabilities."""
        return self._server_capabilities