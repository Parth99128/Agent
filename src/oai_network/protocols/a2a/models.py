"""
A2A Protocol Models

Data models for the Agent-to-Agent (A2A) protocol.
JSON-RPC 2.0 compatible.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import uuid


class A2AErrorCode(int, Enum):
    """A2A error codes (JSON-RPC compatible)."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    AGENT_NOT_FOUND = -32000
    CAPABILITY_NOT_FOUND = -32001
    DELEGATION_FAILED = -32002
    NEGOTIATION_FAILED = -32003


class A2ARequest(BaseModel):
    """A2A JSON-RPC request."""
    jsonrpc: str = Field(default="2.0")
    method: str = Field(...)
    params: Dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class A2AError(BaseModel):
    """A2A error object."""
    code: A2AErrorCode = Field(...)
    message: str = Field(...)
    data: Optional[Any] = Field(None)


class A2AResponse(BaseModel):
    """A2A JSON-RPC response."""
    jsonrpc: str = Field(default="2.0")
    result: Optional[Any] = Field(None)
    error: Optional[A2AError] = Field(None)
    id: Optional[str] = Field(None)


class AgentCard(BaseModel):
    """A2A Agent Card - describes an agent's capabilities and endpoints."""
    agent_did: str = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    version: str = Field(...)
    capabilities: List[str] = Field(default_factory=list)
    endpoints: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityQuery(BaseModel):
    """A2A Capability Query."""
    query: str = Field(...)
    capability_type: Optional[str] = Field(None)
    tags: List[str] = Field(default_factory=list)
    max_results: int = Field(default=10)


class CapabilityResponse(BaseModel):
    """A2A Capability Response."""
    agents: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(default=0)


class DelegationRequest(BaseModel):
    """A2A Delegation Request."""
    capability: str = Field(...)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    requirements: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DelegationResponse(BaseModel):
    """A2A Delegation Response."""
    accepted: bool = Field(...)
    task_id: Optional[str] = Field(None)
    delegatee_did: Optional[str] = Field(None)
    rejection_reason: Optional[str] = Field(None)
    estimated_completion_ms: Optional[int] = Field(None)


class NegotiationRequest(BaseModel):
    """A2A Negotiation Request."""
    template_id: str = Field(...)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NegotiationResponse(BaseModel):
    """A2A Negotiation Response."""
    accepted: bool = Field(...)
    agreed_parameters: Dict[str, Any] = Field(default_factory=dict)
    counter_parameters: Optional[Dict[str, Any]] = Field(None)
    rejection_reason: Optional[str] = Field(None)
    message: Optional[str] = Field(None)


# Backward-compatible aliases
A2ADelegationRequest = DelegationRequest
A2ADelegationResponse = DelegationResponse
A2ANegotiationRequest = NegotiationRequest
A2ANegotiationResponse = NegotiationResponse