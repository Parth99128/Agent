"""
MCP Protocol Adapter

Implements the Model Context Protocol (MCP) for agent-tool communication.
"""

from .models import MCPMessage, MCPRequest, MCPResponse, MCPNotification, MCPError, MCPResourceTemplate
from .client import MCPClient
from .server import MCPServer

__all__ = [
    "MCPMessage",
    "MCPRequest",
    "MCPResponse",
    "MCPNotification",
    "MCPError",
    "MCPResourceTemplate",
    "MCPClient",
    "MCPServer",
]