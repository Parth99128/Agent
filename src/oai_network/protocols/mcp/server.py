"""
MCP Server

Server implementation for the Model Context Protocol (MCP).
"""

import asyncio
import json
import uuid
from typing import Optional, Any, Dict, List, Callable, Awaitable
from datetime import datetime, timezone
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .models import (
    MCPRequest, MCPResponse, MCPError, MCPErrorCode,
    InitializeRequest, InitializeResponse,
    Tool, ToolCall, ToolResult,
    Resource, ResourceReadRequest, ResourceReadResponse,
    Prompt, PromptGetRequest, PromptGetResponse,
    LoggingLevel, LoggingMessage,
)


class MCPServer:
    """
    MCP Protocol Server.
    
    Exposes agent capabilities as MCP tools, resources, and prompts.
    """

    def __init__(
        self,
        name: str = "MCP Server",
        version: str = "1.0.0",
        manifest: Optional[Any] = None,
    ):
        self.name = name
        self.version = version
        self.manifest = manifest
        self.server_info = {"name": name, "version": version}

        # Tools, resources, prompts
        self.tools: Dict[str, Tool] = {}
        self.resources: Dict[str, Resource] = {}
        self.prompts: Dict[str, Prompt] = {}

        # Handlers (separate from definitions)
        self._tool_handlers: Dict[str, Callable] = {}
        self._resource_handlers: Dict[str, Callable] = {}
        self._prompt_handlers: Dict[str, Callable] = {}

        # Logging level
        self._log_level = LoggingLevel.INFO

        # WebSocket connections
        self._ws_connections: List[WebSocket] = []

        # Create FastAPI app
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        app = FastAPI(
            title=f"MCP Server: {self.name}",
            version=self.version,
        )

        @app.post("/mcp")
        async def handle_mcp(request: Request):
            return await self._handle_mcp_request(request)

        @app.websocket("/mcp")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

        @app.get("/health")
        async def health():
            return {"status": "healthy", "server": self.name}

        return app

    def register_tool(
        self,
        name: str,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        handler: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None,
    ):
        """Register a tool."""
        self.tools[name] = Tool(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
        )
        self._tool_handlers[name] = handler

    def register_resource(
        self,
        uri: str,
        name: str = "",
        description: str = "",
        mime_type: str = "application/json",
        handler: Optional[Callable[[str], Awaitable[Any]]] = None,
    ):
        """Register a resource."""
        self.resources[uri] = Resource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )
        self._resource_handlers[uri] = handler

    def register_prompt(
        self,
        name: str,
        description: str = "",
        arguments: Optional[List[Dict[str, Any]]] = None,
        handler: Optional[Callable[[Dict[str, Any]], Awaitable[Any]]] = None,
    ):
        """Register a prompt."""
        self.prompts[name] = Prompt(
            name=name,
            description=description,
            arguments=arguments or [],
        )
        self._prompt_handlers[name] = handler

    async def send_log_notification(self, level: LoggingLevel, message: str, logger: Optional[str] = None):
        """Send a log notification to all WebSocket connections."""
        log_msg = LoggingMessage(level=level, message=message, logger=logger)
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": log_msg.model_dump(mode='json'),
        }
        for ws in self._ws_connections:
            try:
                await ws.send_json(notification)
            except Exception:
                pass

    async def _handle_mcp_request(self, request: Request) -> JSONResponse:
        """Handle an MCP request over HTTP."""
        try:
            data = await request.json()
        except json.JSONDecodeError as e:
            error = MCPError(code=MCPErrorCode.PARSE_ERROR, message=str(e))
            return JSONResponse(
                status_code=400,
                content={"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": None},
            )

        response = await self._process_request(data)
        return JSONResponse(content=response)

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle MCP WebSocket connection."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                response = await self._process_request(data)
                await websocket.send_json(response)
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in self._ws_connections:
                self._ws_connections.remove(websocket)

    async def _process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an MCP request."""
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")

        try:
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tools_call(request_id, params)
            elif method == "resources/list":
                return self._handle_resources_list(request_id)
            elif method == "resources/read":
                return await self._handle_resources_read(request_id, params)
            elif method == "prompts/list":
                return self._handle_prompts_list(request_id)
            elif method == "prompts/get":
                return await self._handle_prompts_get(request_id, params)
            elif method == "logging/setLevel":
                return self._handle_logging_set_level(request_id, params)
            elif method == "ping":
                return {"jsonrpc": "2.0", "result": {}, "id": request_id}
            else:
                error = MCPError(code=MCPErrorCode.METHOD_NOT_FOUND, message=f"Method not found: {method}")
                return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}
        except Exception as e:
            error = MCPError(code=MCPErrorCode.INTERNAL_ERROR, message=str(e))
            return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

    def _handle_initialize(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        capabilities = {
            "tools": {"listChanged": True} if self.tools else {},
            "resources": {"subscribe": True, "listChanged": True} if self.resources else {},
            "prompts": {"listChanged": True} if self.prompts else {},
            "logging": {},
        }
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities,
            "serverInfo": self.server_info,
        }
        return {"jsonrpc": "2.0", "result": result, "id": request_id}

    def _handle_tools_list(self, request_id: str) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []
        for name, tool in self.tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            })
        return {"jsonrpc": "2.0", "result": {"tools": tools}, "id": request_id}

    async def _handle_tools_call(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name or name not in self.tools:
            error = MCPError(code=MCPErrorCode.METHOD_NOT_FOUND, message=f"Tool not found: {name}")
            return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        handler = self._tool_handlers.get(name)
        if handler:
            try:
                result = await handler(arguments)
                if isinstance(result, ToolResult):
                    return {"jsonrpc": "2.0", "result": result.model_dump(mode='json'), "id": request_id}
                return {"jsonrpc": "2.0", "result": result, "id": request_id}
            except Exception as e:
                error = MCPError(code=MCPErrorCode.INTERNAL_ERROR, message=str(e))
                return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        return {"jsonrpc": "2.0", "result": {"content": [], "is_error": False}, "id": request_id}

    def _handle_resources_list(self, request_id: str) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = []
        for uri, resource in self.resources.items():
            resources.append({
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mime_type,
            })
        return {"jsonrpc": "2.0", "result": {"resources": resources}, "id": request_id}

    async def _handle_resources_read(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")

        if not uri or uri not in self.resources:
            error = MCPError(code=MCPErrorCode.METHOD_NOT_FOUND, message=f"Resource not found: {uri}")
            return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        handler = self._resource_handlers.get(uri)
        if handler:
            try:
                result = await handler(uri)
                if isinstance(result, ResourceReadResponse):
                    return {"jsonrpc": "2.0", "result": result.model_dump(mode='json'), "id": request_id}
                return {"jsonrpc": "2.0", "result": result, "id": request_id}
            except Exception as e:
                error = MCPError(code=MCPErrorCode.INTERNAL_ERROR, message=str(e))
                return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        return {"jsonrpc": "2.0", "result": {"contents": []}, "id": request_id}

    def _handle_prompts_list(self, request_id: str) -> Dict[str, Any]:
        """Handle prompts/list request."""
        prompts = []
        for name, prompt in self.prompts.items():
            prompts.append({
                "name": prompt.name,
                "description": prompt.description,
                "arguments": prompt.arguments,
            })
        return {"jsonrpc": "2.0", "result": {"prompts": prompts}, "id": request_id}

    async def _handle_prompts_get(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name or name not in self.prompts:
            error = MCPError(code=MCPErrorCode.METHOD_NOT_FOUND, message=f"Prompt not found: {name}")
            return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        handler = self._prompt_handlers.get(name)
        if handler:
            try:
                result = await handler(arguments)
                if isinstance(result, PromptGetResponse):
                    return {"jsonrpc": "2.0", "result": result.model_dump(mode='json'), "id": request_id}
                return {"jsonrpc": "2.0", "result": result, "id": request_id}
            except Exception as e:
                error = MCPError(code=MCPErrorCode.INTERNAL_ERROR, message=str(e))
                return {"jsonrpc": "2.0", "error": error.model_dump(mode='json'), "id": request_id}

        return {"jsonrpc": "2.0", "result": {"messages": []}, "id": request_id}

    def _handle_logging_set_level(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle logging/setLevel request."""
        level = params.get("level", "info")
        try:
            self._log_level = LoggingLevel(level)
        except ValueError:
            pass
        return {"jsonrpc": "2.0", "result": {}, "id": request_id}

    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self.app