"""
Negotiation Protocol

Implements the negotiation protocol between agents.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from .models import (
    NegotiationRequest, NegotiationResponse, NegotiationSession,
    Agreement, NegotiationStatus, NegotiationTopic, NegotiationTemplate
)
from .strategies import NegotiationStrategy, CooperativeStrategy


class NegotiationProtocol:
    """
    Manages negotiation sessions between agents.
    
    Features:
    - Multi-round negotiation
    - Strategy-based term generation
    - Automatic agreement finalization
    - Session persistence
    """
    
    def __init__(self, default_strategy: Optional[NegotiationStrategy] = None):
        self.strategy = default_strategy or CooperativeStrategy()
        self.sessions: dict[str, NegotiationSession] = {}
        self.templates: dict[str, NegotiationTemplate] = {}
        self._register_default_templates()
    
    def _register_default_templates(self):
        """Register default negotiation templates."""
        # Standard A2A capability negotiation
        self.templates['a2a_capability'] = NegotiationTemplate(
            name="A2A Capability Access",
            description="Standard negotiation for accessing an A2A capability",
            default_topics=[
                NegotiationTopic.PROTOCOL,
                NegotiationTopic.DATA_FORMAT,
                NegotiationTopic.AUTH_METHOD,
                NegotiationTopic.PRICING,
                NegotiationTopic.SLA,
                NegotiationTopic.RATE_LIMITS,
                NegotiationTopic.TIMEOUT,
            ],
            default_terms={
                'protocol': 'a2a',
                'data_format': 'json',
                'auth_method': 'bearer_token',
                'pricing_model': 'per_call',
                'price_per_call': 0.0,
                'sla_uptime': 0.99,
                'rate_limit_rpm': 60,
                'timeout_seconds': 30,
            },
            default_constraints={
                'min_sla_uptime': 0.95,
                'max_price_per_call': 10.0,
                'max_timeout_seconds': 300,
            },
        )
        
        # MCP tool negotiation
        self.templates['mcp_tool'] = NegotiationTemplate(
            name="MCP Tool Access",
            description="Negotiation for MCP tool access",
            default_topics=[
                NegotiationTopic.PROTOCOL,
                NegotiationTopic.DATA_FORMAT,
                NegotiationTopic.AUTH_METHOD,
                NegotiationTopic.RATE_LIMITS,
                NegotiationTopic.TIMEOUT,
            ],
            default_terms={
                'protocol': 'mcp',
                'data_format': 'json',
                'auth_method': 'api_key',
                'rate_limit_rpm': 100,
                'timeout_seconds': 60,
            },
            default_constraints={
                'max_timeout_seconds': 600,
            },
        )
        
        # Delegation negotiation
        self.templates['delegation'] = NegotiationTemplate(
            name="Task Delegation",
            description="Negotiation for delegating a task to another agent",
            default_topics=[
                NegotiationTopic.DELEGATION,
                NegotiationTopic.PRIVACY,
                NegotiationTopic.SLA,
                NegotiationTopic.TIMEOUT,
            ],
            default_terms={
                'delegation_depth': 1,
                'data_retention_days': 7,
                'require_approval': True,
                'sla_completion_rate': 0.9,
                'timeout_seconds': 300,
            },
            default_constraints={
                'max_delegation_depth': 3,
                'min_sla_completion_rate': 0.8,
            },
        )
    
    def initiate(
        self, 
        request: NegotiationRequest,
        strategy: Optional[NegotiationStrategy] = None
    ) -> NegotiationSession:
        """
        Initiate a new negotiation session.
        """
        strategy = strategy or self.strategy
        
        # Create session
        session = NegotiationSession(
            id=request.id,
            initiator_did=request.initiator_did,
            responder_did=request.responder_did,
            capability_name=request.capability_name,
            status=NegotiationStatus.IN_PROGRESS,
            topics=request.topics,
            current_terms=request.proposed_terms.copy(),
            expires_at=request.expires_at,
            max_rounds=5,  # Could come from template
        )
        
        self.sessions[session.id] = session
        return session
    
    def respond(
        self, 
        session_id: str, 
        response: NegotiationResponse,
        strategy: Optional[NegotiationStrategy] = None
    ) -> NegotiationSession:
        """
        Process a response to a negotiation.
        """
        strategy = strategy or self.strategy
        
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if not session.can_continue():
            raise ValueError("Negotiation cannot continue")
        
        session.round += 1
        session.updated_at = datetime.now(timezone.utc)
        
        if response.accepted:
            # Accepted - finalize agreement
            session.status = NegotiationStatus.AGREED
            session.agreed_terms = {**session.current_terms, **response.counter_terms}
            session.agreed_at = datetime.now(timezone.utc)
        else:
            # Counter-proposal or rejection
            if response.counter_terms:
                session.current_terms = {**session.current_terms, **response.counter_terms}
                session.status = NegotiationStatus.IN_PROGRESS
            else:
                session.status = NegotiationStatus.REJECTED
        
        return session
    
    def propose_terms(
        self, 
        session_id: str, 
        terms: dict[str, Any],
        strategy: Optional[NegotiationStrategy] = None
    ) -> NegotiationSession:
        """
        Propose new terms in an ongoing negotiation.
        """
        strategy = strategy or self.strategy
        
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if not session.can_continue():
            raise ValueError("Negotiation cannot continue")
        
        session.round += 1
        session.current_terms = {**session.current_terms, **terms}
        session.updated_at = datetime.now(timezone.utc)
        
        return session
    
    def finalize(self, session_id: str) -> Agreement:
        """
        Finalize a negotiation into an agreement.
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status != NegotiationStatus.AGREED:
            raise ValueError("Negotiation not agreed")
        
        agreement = Agreement(
            negotiation_id=session.id,
            initiator_did=session.initiator_did,
            responder_did=session.responder_did,
            capability_name=session.capability_name,
            terms=session.agreed_terms,
            valid_from=datetime.now(timezone.utc),
            valid_until=session.expires_at if session.expires_at > datetime.now(timezone.utc) else None,
        )
        
        return agreement
    
    def get_session(self, session_id: str) -> Optional[NegotiationSession]:
        """Get a negotiation session."""
        return self.sessions.get(session_id)
    
    def cancel(self, session_id: str) -> bool:
        """Cancel a negotiation session."""
        session = self.sessions.get(session_id)
        if session:
            session.status = NegotiationStatus.CANCELLED
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired() or session.status in (
                NegotiationStatus.AGREED, NegotiationStatus.REJECTED,
                NegotiationStatus.CANCELLED, NegotiationStatus.EXPIRED
            )
        ]
        for sid in expired:
            del self.sessions[sid]
        return len(expired)
    
    def get_template(self, name: str) -> Optional[NegotiationTemplate]:
        """Get a negotiation template."""
        return self.templates.get(name)
    
    def register_template(self, template: NegotiationTemplate):
        """Register a custom negotiation template."""
        self.templates[template.name] = template
    
    def create_request_from_template(
        self, 
        template_name: str,
        initiator_did: str,
        responder_did: str,
        capability_name: str,
        custom_terms: Optional[dict[str, Any]] = None,
        custom_constraints: Optional[dict[str, Any]] = None,
        expires_in_seconds: int = 300,
    ) -> NegotiationRequest:
        """Create a negotiation request from a template."""
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        
        terms = template.default_terms.copy()
        if custom_terms:
            terms.update(custom_terms)
        
        constraints = template.default_constraints.copy()
        if custom_constraints:
            constraints.update(custom_constraints)
        
        return NegotiationRequest(
            initiator_did=initiator_did,
            responder_did=responder_did,
            capability_name=capability_name,
            topics=template.default_topics,
            proposed_terms=terms,
            constraints=constraints,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )