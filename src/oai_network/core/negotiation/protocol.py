"""
Negotiation Protocol

Implements the negotiation protocol between agents.
"""

from datetime import datetime, timezone
from typing import Optional, Any
from .models import (
    NegotiationRequest, NegotiationResponse, NegotiationSession,
    NegotiationAgreement, NegotiationRound, NegotiationTemplate
)

# Global registry for auto-linking NegotiationResponse to sessions
_global_protocol_registry: dict[str, "NegotiationProtocol"] = {}


class NegotiationProtocol:
    """
    Manages negotiation sessions between agents.
    
    Features:
    - Create negotiation sessions
    - Process responses (accept, reject, counter-offer)
    - Track rounds
    - Finalize agreements
    """

    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds
        self.sessions: dict[str, NegotiationSession] = {}
        self.templates: dict[str, NegotiationTemplate] = {}
        self._register_default_templates()

    def _register_default_templates(self):
        """Register default negotiation templates."""
        self.templates['a2a_delegation'] = NegotiationTemplate(
            template_id="a2a_delegation",
            name="A2A Delegation",
            description="Standard A2A delegation negotiation",
            required_parameters=["capability", "max_price"],
            optional_parameters=["timeout", "max_calls"],
            default_values={"timeout": 30, "max_calls": 100},
        )
        self.templates['standard'] = NegotiationTemplate(
            template_id="standard",
            name="Standard",
            description="Standard negotiation template",
            required_parameters=[],
            optional_parameters=[],
            default_values={},
        )

    def create_session(
        self,
        initiator_did: str,
        responder_did: str,
        template_id: str = "standard",
        parameters: Optional[dict[str, Any]] = None,
    ) -> NegotiationSession:
        """Create a new negotiation session."""
        session = NegotiationSession(
            initiator_did=initiator_did,
            responder_did=responder_did,
            template_id=template_id,
            status="pending",
            parameters=parameters or {},
        )
        self.sessions[session.session_id] = session
        _global_protocol_registry[session.session_id] = self
        return session

    def get_session(self, session_id: str) -> Optional[NegotiationSession]:
        """Get a negotiation session by ID."""
        return self.sessions.get(session_id)

    def process_response(self, response: NegotiationResponse) -> Optional[NegotiationAgreement]:
        """
        Process a negotiation response.

        Returns:
            NegotiationAgreement if accepted, None otherwise
        """
        session = self.sessions.get(response.request_id)
        if not session:
            return None

        session.updated_at = datetime.now(timezone.utc)

        if response.accepted:
            # Accept the negotiation
            session.status = "agreed"
            session.agreed_parameters = response.agreed_parameters or session.parameters.copy()
            return NegotiationAgreement(
                session_id=session.session_id,
                agreed_parameters=session.agreed_parameters,
            )

        # Not accepted - check for counter-offer
        if response.counter_parameters:
            # Add a new round with the counter-offer
            round_num = len(session.rounds) + 1
            session.rounds.append(NegotiationRound(
                round_number=round_num,
                proposer_did=response.responder_did,
                parameters=response.counter_parameters,
                message=response.message,
            ))
            session.status = "in_progress"

            # Check if max rounds exceeded
            if round_num >= self.max_rounds:
                session.status = "failed"
            return None

        # Plain rejection
        session.status = "rejected"
        return None

    def cancel(self, session_id: str) -> bool:
        """Cancel a negotiation session."""
        session = self.sessions.get(session_id)
        if session:
            session.status = "cancelled"
            return True
        return False

    def get_template(self, template_id: str) -> Optional[NegotiationTemplate]:
        """Get a negotiation template."""
        return self.templates.get(template_id)

    def register_template(self, template: NegotiationTemplate):
        """Register a custom negotiation template."""
        self.templates[template.template_id] = template