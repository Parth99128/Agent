"""
MCP Client

Client for communicating with MCP servers.
"""

import asyncio
import json
import uuid
from typing import Optional, Any, Dict, List, Callable, Awaitable

from .models import (
    MCPRequest, MCPResponse, MCPError, MCPErrorCode,
    InitializeRequest, InitializeResponse,
    Tool, ToolCall, ToolResult,
    Resource, ResourceReadRequest, ResourceReadResponse,
    Prompt, PromptGetRequest, PromptGetResponse,
    LoggingLevel, LoggingMessage,
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
        protocol_version: str = "2024-11-05",
        client_info: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.protocol_version = protocol_version
        self.client_info = client_info or {"name": "oai-network-client", "version": "0.1.0"}

        # Pending requests
        self._pending: Dict[str, asyncio.Future] = {}
        self._ws = None
        self._ws_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._server_info: Optional[Dict[str, Any]] = None
        self._server_capabilities: Optional[Dict[str, Any]] = None
        self._notification_handlers: Dict[str, Callable] = {}

    async def initialize(self) -> InitializeResponse:
        """Initialize connection to MCP server."""
        import httpx

        request = InitializeRequest(
            protocol_version=self.protocol_version,
            capabilities={"tools": {}, "resources": {}, "prompts": {}},
            client_info=self.client_info,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": request.model_dump(mode='json'),
                    "id": str(uuid.uuid4()),
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("error"):
            raise Exception(f"Initialization failed: {data['error']}")

        result = data.get("result", {})
        self._initialized = True
        self._server_info = result.get("serverInfo")
        self._server_capabilities = result.get("capabilities")

        return InitializeResponse(
            protocol_version=result.get("protocolVersion", self.protocol_version),
            capabilities=result.get("capabilities", {}),
            server_info=result.get("serverInfo", {}),
        )

    async def connect_websocket(self, ws_url: Optional[str] = None):
        """Connect to MCP WebSocket endpoint."""
        import websockets

        url = ws_url or self.base_url.replace('http', 'ws') + '/mcp'
        self._ws = await websockets.connect(url)
        self._ws_task = asyncio.create_task(self._ws_listener())

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
                request_id = data.get('id')
                if request_id and request_id in self._pending:
                    future = self._pending.pop(request_id)
                    if not future.done():
                        future.set_result(data)
                elif 'method' in data and 'id' not in data:
                    handler = self._notification_handlers.get(data['method'])
                    if handler:
                        await handler(data)
        except Exception:
            pass

    async def subscribe_logs(self, level: LoggingLevel = LoggingLevel.INFO):
        """Subscribe to log notifications."""
        if self._ws:
            notification = {
                "jsonrpc": "2.0",
                "method": "logging/setLevel",
                "params": {"level": level.value},
            }
            await self._ws.send(json.dumps(notification))

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """Send a request and wait for response."""
        import httpx

        request_id = str(uuid.uuid4())
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id,
        }

        if self._ws:
            future = asyncio.get_event_loop().create_future()
            self._pending[request_id] = future
            await self._ws.send(json.dumps(request_data))
            try:
                response_data = await asyncio.wait_for(future, timeout=self.timeout)
            except asyncio.TimeoutError:
                self._pending.pop(request_id, None)
                raise Exception(f"Request {request_id} timed out")
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp",
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                response_data = response.json()

        if response_data.get("error"):
            return MCPResponse(
                error=MCPError(**response_data["error"]),
                id=response_data.get("id"),
            )
        return MCPResponse(result=response_data.get("result"), id=response_data.get("id"))

    async def list_tools(self) -> List[Tool]:
        """List available tools."""
        response = await self._send_request("tools/list")
        if response.error:
            raise Exception(f"Failed to list tools: {response.error}")
        tools_data = (response.result or {}).get("tools", [])
        return [Tool(**tool) for tool in tools_data]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call a tool."""
        response = await self._send_request("tools/call", {"name": name, "arguments": arguments})
        if response.error:
            raise Exception(f"Tool call failed: {response.error}")
        return ToolResult(**(response.result or {}))

    async def list_resources(self) -> List[Resource]:
        """List available resources."""
        response = await self._send_request("resources/list")
        if response.error:
            raise Exception(f"Failed to list resources: {response.error}")
        resources_data = (response.result or {}).get("resources", [])
        return [Resource(**res) for res in resources_data]

    async def read_resource(self, uri: str) -> ResourceReadResponse:
        """Read a resource."""
        response = await self._send_request("resources/read", {"uri": uri})
        if response.error:
            raise Exception(f"Failed to read resource: {response.error}")
        return ResourceReadResponse(**(response.result or {}))

    async def list_prompts(self) -> List[Prompt]:
        """List available prompts."""
        response = await self._send_request("prompts/list")
        if response.error:
            raise Exception(f"Failed to list prompts: {response.error}")
        prompts_data = (response.result or {}).get("prompts", [])
        return [Prompt(**prompt) for prompt in prompts_data]

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> PromptGetResponse:
        """Get a prompt."""
        response = await self._send_request("prompts/get", {"name": name, "arguments": arguments or {}})
        if response.error:
            raise Exception(f"Failed to get prompt: {response.error}")
        return PromptGetResponse(**(response.result or {}))

    async def ping(self) -> bool:
        """Send a ping to check connection."""
        response = await self._send_request("ping")
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