"""
A2A Protocol Models

Data models for the Agent-to-Agent (A2A) protocol.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import uuid


class A2AMessageType(str, Enum):
    """A2A message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"
    DELEGATION_REQUEST = "delegation_request"
    DELEGATION_RESPONSE = "delegation_response"
    DELEGATION_STATUS = "delegation_status"
    NEGOTIATION_START = "negotiation_start"
    NEGOTIATION_OFFER = "negotiation_offer"
    NEGOTIATION_ACCEPT = "negotiation_accept"
    NEGOTIATION_REJECT = "negotiation_reject"
    NEGOTIATION_COMPLETE = "negotiation_complete"


class A2AMessage(BaseModel):
    """Base A2A message."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: A2AMessageType = Field(..., description="Message type")
    sender_did: str = Field(..., description="Sender DID")
    recipient_did: Optional[str] = Field(None, description="Recipient DID (None for broadcast)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = Field(None, description="Correlation ID for request/response")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Message payload")
    signature: Optional[str] = Field(None, description="Message signature")
    
    def sign(self, private_key: bytes) -> str:
        """Sign the message with a private key."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        # Create signing data
        data = f"{self.id}{self.type.value}{self.sender_did}{self.recipient_did or ''}{self.timestamp.isoformat()}{self.correlation_id or ''}{self.payload}".encode()
        
        private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        signature = private_key_obj.sign(data)
        self.signature = signature.hex()
        return self.signature
    
    def verify(self, public_key: bytes) -> bool:
        """Verify the message signature."""
        if not self.signature:
            return False
        
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        data = f"{self.id}{self.type.value}{self.sender_did}{self.recipient_did or ''}{self.timestamp.isoformat()}{self.correlation_id or ''}{self.payload}".encode()
        
        try:
            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            public_key_obj.verify(bytes.fromhex(self.signature), data)
            return True
        except Exception:
            return False


class A2ARequest(A2AMessage):
    """A2A request message."""
    type: A2AMessageType = A2AMessageType.REQUEST
    capability: str = Field(..., description="Capability being requested")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Capability parameters")
    timeout_ms: int = Field(default=30000, description="Request timeout in milliseconds")
    requires_response: bool = Field(default=True, description="Whether response is required")


class A2AResponse(A2AMessage):
    """A2A response message."""
    type: A2AMessageType = A2AMessageType.RESPONSE
    request_id: str = Field(..., description="Original request ID")
    success: bool = Field(..., description="Whether request succeeded")
    result: Optional[Any] = Field(None, description="Response result")
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: int = Field(default=0, description="Processing latency")


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


class AgentCard(BaseModel):
    """A2A Agent Card - describes an agent's capabilities and endpoints."""
    agent_did: str = Field(..., description="Agent DID")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    capabilities: List[str] = Field(default_factory=list, description="List of capability names")
    endpoints: Dict[str, str] = Field(default_factory=dict, description="Protocol endpoints")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CapabilityQuery(BaseModel):
    """A2A Capability Query."""
    query: str = Field(..., description="Natural language query")
    capability_type: Optional[str] = Field(None, description="Capability type filter")
    tags: List[str] = Field(default_factory=list, description="Tags to filter by")
    max_results: int = Field(default=10, description="Maximum results")


class CapabilityResponse(BaseModel):
    """A2A Capability Response."""
    agents: List[Dict[str, Any]] = Field(default_factory=list, description="Matching agents")
    total_count: int = Field(default=0, description="Total matching agents")


class A2AError(A2AMessage):
    """A2A error message."""
    type: A2AMessageType = A2AMessageType.ERROR
    code: A2AErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    retryable: bool = Field(default=False, description="Whether request can be retried")


class A2ACapabilityQuery(A2AMessage):
    """A2A capability query message."""
    type: A2AMessageType = A2AMessageType.CAPABILITY_QUERY
    query: str = Field(..., description="Natural language query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Query filters")
    max_results: int = Field(default=10, description="Maximum results")


class A2ACapabilityResponse(A2AMessage):
    """A2A capability response message."""
    type: A2AMessageType = A2AMessageType.CAPABILITY_RESPONSE
    query_id: str = Field(..., description="Original query ID")
    agents: List[Dict[str, Any]] = Field(default_factory=list, description="Matching agents")
    total_count: int = Field(default=0, description="Total matching agents")


class A2ADelegationRequest(A2AMessage):
    """A2A delegation request message."""
    type: A2AMessageType = A2AMessageType.DELEGATION_REQUEST
    task_id: str = Field(..., description="Task ID")
    capability: str = Field(..., description="Required capability")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Task input data")
    max_depth: int = Field(default=3, description="Maximum delegation depth")
    current_depth: int = Field(default=0, description="Current delegation depth")
    parent_task_id: Optional[str] = Field(None, description="Parent task ID")
    callback_url: Optional[str] = Field(None, description="Callback URL for completion")


# Alias for backward compatibility
DelegationRequest = A2ADelegationRequest


class A2ADelegationResponse(A2AMessage):
    """A2A delegation response message."""
    type: A2AMessageType = A2AMessageType.DELEGATION_RESPONSE
    task_id: str = Field(..., description="Task ID")
    accepted: bool = Field(..., description="Whether delegation was accepted")
    estimated_completion_ms: Optional[int] = Field(None, description="Estimated completion time")
    error: Optional[str] = Field(None, description="Error if not accepted")


# Alias for backward compatibility
DelegationResponse = A2ADelegationResponse


class A2ADelegationStatus(A2AMessage):
    """A2A delegation status update."""
    type: A2AMessageType = A2AMessageType.DELEGATION_STATUS
    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Task status (pending, running, completed, failed)")
    progress: float = Field(default=0.0, description="Progress (0.0 to 1.0)")
    result: Optional[Any] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error if failed")


class A2ANegotiationMessage(A2AMessage):
    """Base A2A negotiation message."""
    negotiation_id: str = Field(..., description="Negotiation session ID")
    round: int = Field(default=1, description="Negotiation round number")


class A2ANegotiationStart(A2ANegotiationMessage):
    """A2A negotiation start message."""
    type: A2AMessageType = A2AMessageType.NEGOTIATION_START
    template: str = Field(..., description="Negotiation template name")
    initial_terms: Dict[str, Any] = Field(default_factory=dict, description="Initial terms")


class A2ANegotiationOffer(A2ANegotiationMessage):
    """A2A negotiation offer message."""
    type: A2AMessageType = A2AMessageType.NEGOTIATION_OFFER
    terms: Dict[str, Any] = Field(..., description="Proposed terms")
    expires_at: Optional[datetime] = Field(None, description="Offer expiration")


class A2ANegotiationAccept(A2ANegotiationMessage):
    """A2A negotiation accept message."""
    type: A2AMessageType = A2AMessageType.NEGOTIATION_ACCEPT
    accepted_terms: Dict[str, Any] = Field(..., description="Accepted terms")


class A2ANegotiationReject(A2ANegotiationMessage):
    """A2A negotiation reject message."""
    type: A2AMessageType = A2AMessageType.NEGOTIATION_REJECT
    reason: str = Field(..., description="Rejection reason")
    counter_offer: Optional[Dict[str, Any]] = Field(None, description="Counter-offer terms")


class A2ANegotiationComplete(A2ANegotiationMessage):
    """A2A negotiation complete message."""
    type: A2AMessageType = A2AMessageType.NEGOTIATION_COMPLETE
    agreement: Dict[str, Any] = Field(..., description="Final agreement terms")
    signatures: Dict[str, str] = Field(default_factory=dict, description="Party signatures")


# Aliases for backward compatibility
NegotiationRequest = A2ANegotiationStart
NegotiationResponse = A2ANegotiationAccept


# Message factory
def create_request(
    sender_did: str,
    recipient_did: str,
    capability: str,
    parameters: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> A2ARequest:
    """Create an A2A request."""
    return A2ARequest(
        sender_did=sender_did,
        recipient_did=recipient_did,
        capability=capability,
        parameters=parameters,
        correlation_id=correlation_id,
    )


def create_response(
    sender_did: str,
    request_id: str,
    success: bool,
    result: Optional[Any] = None,
    error: Optional[str] = None,
    latency_ms: int = 0,
) -> A2AResponse:
    """Create an A2A response."""
    return A2AResponse(
        sender_did=sender_did,
        request_id=request_id,
        success=success,
        result=result,
        error=error,
        latency_ms=latency_ms,
    )


def create_error(
    sender_did: str,
    code: A2AErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
) -> A2AError:
    """Create an A2A error."""
    return A2AError(
        sender_did=sender_did,
        code=code,
        message=message,
        details=details,
        retryable=retryable,
    )