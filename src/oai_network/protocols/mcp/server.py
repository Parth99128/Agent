"""
MCP Server

Server implementation for the Model Context Protocol (MCP).
"""

import asyncio
import json
from typing import Optional, Any, Dict, List, Callable, Awaitable
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

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
    MCPLoggingSetLevelRequest,
    create_mcp_response, create_mcp_error, create_mcp_notification,
    MCPErrorCode
)
from ...core.capabilities.models import AgentManifest, Capability


class MCPServer:
    """
    MCP Protocol Server.
    
    Exposes agent capabilities as MCP tools, resources, and prompts.
    """
    
    def __init__(
        self,
        manifest: AgentManifest,
        server_info: Optional[Dict[str, str]] = None,
    ):
        self.manifest = manifest
        self.server_info = server_info or {"name": "oai-network-agent", "version": "0.1.0"}
        
        # Capability handlers (mapped to tools)
        self._tool_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        
        # Resource handlers
        self._resource_handlers: Dict[str, Callable[[str], Awaitable[Any]]] = {}
        self._resource_templates: Dict[str, Dict[str, Any]] = {}
        
        # Prompt handlers
        self._prompt_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        self._prompt_definitions: Dict[str, MCPPrompt] = {}
        
        # Logging level
        self._log_level = "info"
        
        # WebSocket connections
        self._ws_connections: List[WebSocket] = []
        
        # Create FastAPI app
        self.app = self._create_app()
        
        # Auto-register capabilities as tools
        self._register_capabilities_as_tools()
    
    def _create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        app = FastAPI(
            title=f"MCP Server: {self.manifest.name}",
            description=self.manifest.description,
            version=self.manifest.version,
        )
        
        # MCP endpoint (HTTP)
        @app.post("/mcp")
        async def handle_mcp(request: Request):
            return await self._handle_mcp_request(request)
        
        # MCP WebSocket endpoint
        @app.websocket("/mcp")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
        
        # Health check
        @app.get("/health")
        async def health():
            return {"status": "healthy", "server": self.server_info["name"]}
        
        return app
    
    def _register_capabilities_as_tools(self):
        """Register agent capabilities as MCP tools."""
        for capability in self.manifest.capabilities:
            tool = MCPTool(
                name=capability.name,
                description=capability.description,
                inputSchema=capability.input_schema.model_dump(),
            )
            # The actual handler needs to be registered separately
            # This just defines the tool schema
            self._tool_handlers[capability.name] = self._default_tool_handler
    
    def _default_tool_handler(self, arguments: Dict[str, Any]) -> Any:
        """Default tool handler - should be overridden."""
        return {"error": "Tool not implemented"}
    
    def register_tool(self, name: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]], description: str = "", input_schema: Optional[Dict[str, Any]] = None):
        """Register a tool handler."""
        self._tool_handlers[name] = handler
        if input_schema:
            # Update tool definition
            pass
    
    def register_resource(self, uri: str, handler: Callable[[str], Awaitable[Any]], name: str = "", description: str = "", mime_type: str = "application/json"):
        """Register a resource handler."""
        self._resource_handlers[uri] = handler
    
    def register_resource_template(self, uri_template: str, handler: Callable[[str], Awaitable[Any]], name: str = "", description: str = "", mime_type: str = "application/json"):
        """Register a resource template handler."""
        self._resource_templates[uri_template] = {
            "handler": handler,
            "name": name,
            "description": description,
            "mimeType": mime_type,
        }
    
    def register_prompt(self, name: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]], description: str = "", arguments: Optional[List[Dict[str, Any]]] = None):
        """Register a prompt handler."""
        self._prompt_handlers[name] = handler
        self._prompt_definitions[name] = MCPPrompt(
            name=name,
            description=description,
            arguments=arguments or [],
        )
    
    async def _handle_mcp_request(self, request: Request) -> JSONResponse:
        """Handle an MCP request over HTTP."""
        try:
            data = await request.json()
            mcp_request = MCPRequest(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse(
                status_code=400,
                content=create_mcp_error(
                    request_id=None,
                    code=MCPErrorCode.PARSE_ERROR,
                    message=f"Parse error: {str(e)}",
                ).model_dump(exclude_none=True)
            )
        
        response = await self._process_request(mcp_request)
        return JSONResponse(content=response.model_dump(exclude_none=True))
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle MCP WebSocket connection."""
        await websocket.accept()
        self._ws_connections.append(websocket)
        
        try:
            while True:
                data = await websocket.receive_json()
                mcp_request = MCPRequest(**data)
                response = await self._process_request(mcp_request)
                await websocket.send_json(response.model_dump(exclude_none=True))
        except WebSocketDisconnect:
            pass
        except Exception as e:
            # Send error response
            error_response = create_mcp_error(
                request_id=None,
                code=MCPErrorCode.INTERNAL_ERROR,
                message=str(e),
            )
            try:
                await websocket.send_json(error_response.model_dump(exclude_none=True))
            except Exception:
                pass
        finally:
            if websocket in self._ws_connections:
                self._ws_connections.remove(websocket)
    
    async def _process_request(self, request: MCPRequest) -> MCPResponse:
        """Process an MCP request."""
        method = request.method
        params = request.params or {}
        
        try:
            if method == "initialize":
                return await self._handle_initialize(request.id, params)
            elif method == "tools/list":
                return await self._handle_tools_list(request.id)
            elif method == "tools/call":
                return await self._handle_tools_call(request.id, params)
            elif method == "resources/list":
                return await self._handle_resources_list(request.id)
            elif method == "resources/read":
                return await self._handle_resources_read(request.id, params)
            elif method == "resources/templates/list":
                return await self._handle_resource_templates_list(request.id)
            elif method == "prompts/list":
                return await self._handle_prompts_list(request.id)
            elif method == "prompts/get":
                return await self._handle_prompts_get(request.id, params)
            elif method == "logging/setLevel":
                return await self._handle_logging_set_level(request.id, params)
            elif method == "ping":
                return create_mcp_response(request.id, {})
            else:
                return create_mcp_error(
                    request_id=request.id,
                    code=MCPErrorCode.METHOD_NOT_FOUND,
                    message=f"Method not found: {method}",
                )
        except Exception as e:
            return create_mcp_error(
                request_id=request.id,
                code=MCPErrorCode.INTERNAL_ERROR,
                message=str(e),
            )
    
    async def _handle_initialize(self, request_id: str, params: Dict[str, Any]) -> MCPResponse:
        """Handle initialize request."""
        # Check protocol version
        client_version = params.get("protocolVersion", "")
        supported_version = "2024-11-05"
        
        if client_version != supported_version:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INVALID_PARAMS,
                message=f"Unsupported protocol version: {client_version}. Supported: {supported_version}",
            )
        
        # Return server capabilities
        capabilities = {
            "tools": {},
            "resources": {},
            "prompts": {},
            "logging": {},
        }
        
        # Add capabilities based on what we have
        if self._tool_handlers:
            capabilities["tools"] = {"listChanged": True}
        if self._resource_handlers or self._resource_templates:
            capabilities["resources"] = {"subscribe": True, "listChanged": True}
        if self._prompt_definitions:
            capabilities["prompts"] = {"listChanged": True}
        
        result = {
            "protocolVersion": supported_version,
            "capabilities": capabilities,
            "serverInfo": self.server_info,
        }
        
        return create_mcp_response(request_id, result)
    
    async def _handle_tools_list(self, request_id: str) -> MCPResponse:
        """Handle tools/list request."""
        tools = []
        for name, handler in self._tool_handlers.items():
            # Find capability for schema
            capability = self.manifest.get_capability(name)
            if capability:
                tools.append(MCPTool(
                    name=name,
                    description=capability.description,
                    inputSchema=capability.input_schema.model_dump(),
                ))
            else:
                tools.append(MCPTool(
                    name=name,
                    description="",
                    inputSchema={"type": "object", "properties": {}},
                ))
        
        result = {"tools": [tool.model_dump() for tool in tools]}
        return create_mcp_response(request_id, result)
    
    async def _handle_tools_call(self, request_id: str, params: Dict[str, Any]) -> MCPResponse:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INVALID_PARAMS,
                message="Tool name is required",
            )
        
        handler = self._tool_handlers.get(name)
        if not handler:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.METHOD_NOT_FOUND,
                message=f"Tool not found: {name}",
            )
        
        try:
            result = await handler(arguments)
            return create_mcp_response(request_id, {"content": [{"type": "text", "text": str(result)}]})
        except Exception as e:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INTERNAL_ERROR,
                message=f"Tool execution failed: {str(e)}",
            )
    
    async def _handle_resources_list(self, request_id: str) -> MCPResponse:
        """Handle resources/list request."""
        resources = []
        for uri in self._resource_handlers:
            resources.append(MCPResource(
                uri=uri,
                name=uri.split("/")[-1],
                mimeType="application/json",
            ).model_dump())
        
        for uri_template, info in self._resource_templates.items():
            resources.append(MCPResource(
                uri=uri_template,
                name=info.get("name", uri_template),
                description=info.get("description"),
                mimeType=info.get("mimeType", "application/json"),
            ).model_dump())
        
        result = {"resources": resources}
        return create_mcp_response(request_id, result)
    
    async def _handle_resources_read(self, request_id: str, params: Dict[str, Any]) -> MCPResponse:
        """Handle resources/read request."""
        uri = params.get("uri")
        
        if not uri:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INVALID_PARAMS,
                message="Resource URI is required",
            )
        
        handler = self._resource_handlers.get(uri)
        if not handler:
            # Check templates
            for template_uri, info in self._resource_templates.items():
                # Simple template matching (in real impl, use proper template matching)
                if self._match_template(template_uri, uri):
                    handler = info["handler"]
                    break
        
        if not handler:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.METHOD_NOT_FOUND,
                message=f"Resource not found: {uri}",
            )
        
        try:
            content = await handler(uri)
            result = {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(content) if not isinstance(content, str) else content,
                }]
            }
            return create_mcp_response(request_id, result)
        except Exception as e:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INTERNAL_ERROR,
                message=f"Resource read failed: {str(e)}",
            )
    
    def _match_template(self, template: str, uri: str) -> bool:
        """Simple template matching."""
        # Convert template to regex
        import re
        pattern = template.replace("{", "(?P<").replace("}", ">[^/]+)")
        return bool(re.match(f"^{pattern}$", uri))
    
    async def _handle_resource_templates_list(self, request_id: str) -> MCPResponse:
        """Handle resources/templates/list request."""
        templates = []
        for uri_template, info in self._resource_templates.items():
            templates.append(MCPResourceTemplate(
                uriTemplate=uri_template,
                name=info.get("name", uri_template),
                description=info.get("description"),
                mimeType=info.get("mimeType", "application/json"),
            ).model_dump())
        
        result = {"resourceTemplates": templates}
        return create_mcp_response(request_id, result)
    
    async def _handle_prompts_list(self, request_id: str) -> MCPResponse:
        """Handle prompts/list request."""
        prompts = [prompt.model_dump() for prompt in self._prompt_definitions.values()]
        result = {"prompts": prompts}
        return create_mcp_response(request_id, result)
    
    async def _handle_prompts_get(self, request_id: str, params: Dict[str, Any]) -> MCPResponse:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INVALID_PARAMS,
                message="Prompt name is required",
            )
        
        handler = self._prompt_handlers.get(name)
        if not handler:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.METHOD_NOT_FOUND,
                message=f"Prompt not found: {name}",
            )
        
        try:
            result = await handler(arguments)
            return create_mcp_response(request_id, result)
        except Exception as e:
            return create_mcp_error(
                request_id=request_id,
                code=MCPErrorCode.INTERNAL_ERROR,
                message=f"Prompt execution failed: {str(e)}",
            )
    
    async def _handle_logging_set_level(self, request_id: str, params: Dict[str, Any]) -> MCPResponse:
        """Handle logging/setLevel request."""
        level = params.get("level", "info")
        self._log_level = level
        return create_mcp_response(request_id, {})
    
    async def broadcast_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Broadcast a notification to all WebSocket connections."""
        notification = create_mcp_notification(method, params)
        for ws in self._ws_connections:
            try:
                await ws.send_json(notification.model_dump(exclude_none=True))
            except Exception:
                pass
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self.app