"""
MCP Protocol Models

Data models for the Model Context Protocol (MCP).
JSON-RPC 2.0 compatible.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import uuid


class MCPErrorCode(int, Enum):
    """MCP error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_NOT_INITIALIZED = -32000
    UNKNOWN_ERROR = -32001


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""
    jsonrpc: str = Field(default="2.0")
    method: str = Field(...)
    params: Dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class MCPError(BaseModel):
    """MCP error object."""
    code: MCPErrorCode = Field(...)
    message: str = Field(...)
    data: Optional[Any] = Field(None)


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""
    jsonrpc: str = Field(default="2.0")
    result: Optional[Any] = Field(None)
    error: Optional[MCPError] = Field(None)
    id: Optional[str] = Field(None)


class InitializeRequest(BaseModel):
    """MCP initialize request."""
    protocol_version: str = Field(default="2024-11-05")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    client_info: Dict[str, str] = Field(default_factory=lambda: {"name": "oai-network", "version": "0.1.0"})


class InitializeResponse(BaseModel):
    """MCP initialize response."""
    protocol_version: str = Field(default="2024-11-05")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    server_info: Dict[str, str] = Field(default_factory=lambda: {"name": "oai-network-agent", "version": "0.1.0"})


class Tool(BaseModel):
    """MCP tool definition."""
    name: str = Field(...)
    description: str = Field(...)
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """MCP tool call."""
    name: str = Field(...)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """MCP tool result."""
    content: List[Dict[str, Any]] = Field(default_factory=list)
    is_error: bool = Field(default=False)


class Resource(BaseModel):
    """MCP resource definition."""
    uri: str = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(None)
    mime_type: Optional[str] = Field(None)


class ResourceReadRequest(BaseModel):
    """MCP resource read request."""
    uri: str = Field(...)


class ResourceReadResponse(BaseModel):
    """MCP resource read response."""
    contents: List[Dict[str, Any]] = Field(default_factory=list)


class Prompt(BaseModel):
    """MCP prompt definition."""
    name: str = Field(...)
    description: Optional[str] = Field(None)
    arguments: List[Dict[str, Any]] = Field(default_factory=list)


class PromptGetRequest(BaseModel):
    """MCP prompt get request."""
    name: str = Field(...)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class PromptGetResponse(BaseModel):
    """MCP prompt get response."""
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class LoggingLevel(str, Enum):
    """MCP logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LoggingMessage(BaseModel):
    """MCP logging message."""
    level: LoggingLevel = Field(...)
    message: str = Field(...)
    logger: Optional[str] = Field(None)
    data: Optional[Any] = Field(None)


# Backward-compatible aliases
MCPTool = Tool
MCPResource = Resource
MCPPrompt = Prompt