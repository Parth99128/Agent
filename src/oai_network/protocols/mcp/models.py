"""
MCP Protocol Models

Data models for the Model Context Protocol (MCP).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import uuid


class MCPMessageType(str, Enum):
    """MCP message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    PING = "ping"
    PONG = "pong"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_TEMPLATES_LIST = "resources/templates/list"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    LOGGING_SET_LEVEL = "logging/setLevel"


class MCPMessage(BaseModel):
    """Base MCP message."""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Request ID")
    method: Optional[str] = Field(None, description="Method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")
    result: Optional[Any] = Field(None, description="Response result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error object")


class MCPRequest(MCPMessage):
    """MCP request message."""
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MCPResponse(MCPMessage):
    """MCP response message."""
    result: Any = Field(..., description="Response result")


class MCPNotification(MCPMessage):
    """MCP notification message (no response expected)."""
    method: str = Field(..., description="Notification method")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    id: None = Field(default=None, description="Notifications have no ID")


class MCPError(MCPMessage):
    """MCP error response."""
    error: Dict[str, Any] = Field(..., description="Error object")
    result: None = Field(default=None)


# Initialize messages
class MCPInitializeRequest(MCPRequest):
    """MCP initialize request."""
    method: str = "initialize"
    params: Dict[str, Any] = Field(default_factory=lambda: {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "oai-network", "version": "0.1.0"},
    })


class MCPInitializeResponse(MCPResponse):
    """MCP initialize response."""
    result: Dict[str, Any] = Field(default_factory=lambda: {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
            "resources": {},
            "prompts": {},
            "logging": {},
        },
        "serverInfo": {"name": "oai-network-agent", "version": "0.1.0"},
    })


# Aliases for backward compatibility
InitializeRequest = MCPInitializeRequest
InitializeResponse = MCPInitializeResponse


# Tools
class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: Dict[str, Any] = Field(..., description="JSON Schema for input")


class MCPToolsListRequest(MCPRequest):
    """MCP tools/list request."""
    method: str = "tools/list"
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPToolsListResponse(MCPResponse):
    """MCP tools/list response."""
    result: Dict[str, List[MCPTool]] = Field(default_factory=lambda: {"tools": []})


class MCPToolsCallRequest(MCPRequest):
    """MCP tools/call request."""
    method: str = "tools/call"
    params: Dict[str, Any] = Field(..., description="Tool call parameters")


class MCPToolsCallResponse(MCPResponse):
    """MCP tools/call response."""
    result: Dict[str, Any] = Field(..., description="Tool call result")


# Aliases for backward compatibility
Tool = MCPTool
ToolCall = MCPToolsCallRequest
ToolResult = MCPToolsCallResponse


# Resources
class MCPResource(BaseModel):
    """MCP resource definition."""
    uri: str = Field(..., description="Resource URI")
    name: str = Field(..., description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    mimeType: Optional[str] = Field(None, description="MIME type")


class MCPResourceTemplate(BaseModel):
    """MCP resource template."""
    uriTemplate: str = Field(..., description="URI template")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    mimeType: Optional[str] = Field(None, description="MIME type")


class MCPResourcesListRequest(MCPRequest):
    """MCP resources/list request."""
    method: str = "resources/list"
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPResourcesListResponse(MCPResponse):
    """MCP resources/list response."""
    result: Dict[str, List[MCPResource]] = Field(default_factory=lambda: {"resources": []})


class MCPResourcesReadRequest(MCPRequest):
    """MCP resources/read request."""
    method: str = "resources/read"
    params: Dict[str, Any] = Field(..., description="Read parameters")


class MCPResourcesReadResponse(MCPResponse):
    """MCP resources/read response."""
    result: Dict[str, Any] = Field(..., description="Resource contents")


# Aliases for backward compatibility
Resource = MCPResource
ResourceReadRequest = MCPResourcesReadRequest
ResourceReadResponse = MCPResourcesReadResponse


# Prompts
class MCPPrompt(BaseModel):
    """MCP prompt definition."""
    name: str = Field(..., description="Prompt name")
    description: Optional[str] = Field(None, description="Prompt description")
    arguments: List[Dict[str, Any]] = Field(default_factory=list, description="Prompt arguments")


class MCPPromptArgument(BaseModel):
    """MCP prompt argument."""
    name: str = Field(..., description="Argument name")
    description: Optional[str] = Field(None, description="Argument description")
    required: bool = Field(default=False, description="Whether argument is required")


class MCPPromptsListRequest(MCPRequest):
    """MCP prompts/list request."""
    method: str = "prompts/list"
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPPromptsListResponse(MCPResponse):
    """MCP prompts/list response."""
    result: Dict[str, List[MCPPrompt]] = Field(default_factory=lambda: {"prompts": []})


class MCPPromptsGetRequest(MCPRequest):
    """MCP prompts/get request."""
    method: str = "prompts/get"
    params: Dict[str, Any] = Field(..., description="Get parameters")


class MCPPromptsGetResponse(MCPResponse):
    """MCP prompts/get response."""
    result: Dict[str, Any] = Field(..., description="Prompt result")


# Aliases for backward compatibility
Prompt = MCPPrompt
PromptGetRequest = MCPPromptsGetRequest
PromptGetResponse = MCPPromptsGetResponse


# Logging
class MCPLoggingSetLevelRequest(MCPRequest):
    """MCP logging/setLevel request."""
    method: str = "logging/setLevel"
    params: Dict[str, Any] = Field(..., description="Log level parameters")


# Aliases for backward compatibility
LoggingLevel = str
LoggingMessage = Dict[str, Any]


# Error codes
class MCPErrorCode(int, Enum):
    """MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_NOT_INITIALIZED = -32000
    UNKNOWN_ERROR = -32001


def create_mcp_error(
    request_id: Optional[str],
    code: MCPErrorCode,
    message: str,
    data: Optional[Any] = None,
) -> MCPError:
    """Create an MCP error response."""
    return MCPError(
        id=request_id,
        error={
            "code": code.value,
            "message": message,
            "data": data,
        }
    )


def create_mcp_response(request_id: str, result: Any) -> MCPResponse:
    """Create an MCP success response."""
    return MCPResponse(id=request_id, result=result)


def create_mcp_notification(method: str, params: Optional[Dict[str, Any]] = None) -> MCPNotification:
    """Create an MCP notification."""
    return MCPNotification(method=method, params=params or {})