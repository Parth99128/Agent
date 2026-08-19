"""
Tests for the negotiation module.
"""

import pytest
from oai_network.core.negotiation.models import (
    NegotiationRequest, NegotiationResponse, NegotiationSession,
    NegotiationAgreement, NegotiationTemplate, NegotiationRound
)
from oai_network.core.negotiation.protocol import NegotiationProtocol
from oai_network.core.negotiation.strategies import (
    CooperativeStrategy, CompetitiveStrategy, BalancedStrategy
)


class TestNegotiationModels:
    """Tests for negotiation data models."""
    
    def test_negotiation_request_creation(self):
        """Test creating a NegotiationRequest."""
        request = NegotiationRequest(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"capability": "text_summarization", "max_price": 0.10}
        )
        
        assert request.initiator_did == "did:oai:initiator"
        assert request.responder_did == "did:oai:responder"
        assert request.template_id == "a2a_delegation"
        assert request.parameters["capability"] == "text_summarization"
    
    def test_negotiation_response_accept(self):
        """Test creating an accepting NegotiationResponse."""
        response = NegotiationResponse(
            request_id="req-123",
            responder_did="did:oai:responder",
            accepted=True,
            agreed_parameters={"price": 0.05}
        )
        
        assert response.accepted is True
        assert response.agreed_parameters["price"] == 0.05
    
    def test_negotiation_response_reject(self):
        """Test creating a rejecting NegotiationResponse."""
        response = NegotiationResponse(
            request_id="req-123",
            responder_did="did:oai:responder",
            accepted=False,
            rejection_reason="Price too low"
        )
        
        assert response.accepted is False
        assert response.rejection_reason == "Price too low"
    
    def test_negotiation_session(self, sample_negotiation_session):
        """Test NegotiationSession."""
        assert sample_negotiation_session.session_id
        assert sample_negotiation_session.initiator_did == "did:oai:initiator"
        assert sample_negotiation_session.responder_did == "did:oai:responder"
        assert sample_negotiation_session.status == "pending"
        assert len(sample_negotiation_session.rounds) == 0
    
    def test_negotiation_agreement(self):
        """Test NegotiationAgreement."""
        agreement = NegotiationAgreement(
            session_id="session-123",
            agreed_parameters={"price": 0.05, "timeout": 30},
            expires_at=None
        )
        
        assert agreement.session_id == "session-123"
        assert agreement.agreed_parameters["price"] == 0.05
    
    def test_negotiation_template(self):
        """Test NegotiationTemplate."""
        template = NegotiationTemplate(
            template_id="test_template",
            name="Test Template",
            description="A test template",
            required_parameters=["param1", "param2"],
            optional_parameters=["param3"],
            default_values={"param3": "default"}
        )
        
        assert template.template_id == "test_template"
        assert "param1" in template.required_parameters
        assert "param3" in template.optional_parameters
        assert template.default_values["param3"] == "default"
    
    def test_negotiation_round(self):
        """Test NegotiationRound."""
        round_obj = NegotiationRound(
            round_number=1,
            proposer_did="did:oai:initiator",
            parameters={"price": 0.10},
            message="Initial offer"
        )
        
        assert round_obj.round_number == 1
        assert round_obj.proposer_did == "did:oai:initiator"
        assert round_obj.parameters["price"] == 0.10


class TestNegotiationProtocol:
    """Tests for NegotiationProtocol."""
    
    def test_create_session(self, negotiation_protocol):
        """Test creating a negotiation session."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"capability": "text_summarization"}
        )
        
        assert session.initiator_did == "did:oai:initiator"
        assert session.responder_did == "did:oai:responder"
        assert session.template_id == "a2a_delegation"
        assert session.status == "pending"
    
    def test_get_session(self, negotiation_protocol):
        """Test getting a session by ID."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={}
        )
        
        retrieved = negotiation_protocol.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_nonexistent_session(self, negotiation_protocol):
        """Test getting nonexistent session."""
        session = negotiation_protocol.get_session("nonexistent")
        
        assert session is None
    
    def test_process_response_accept(self, negotiation_protocol):
        """Test processing an accepting response."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"price": 0.10}
        )
        
        response = NegotiationResponse(
            request_id=session.session_id,
            responder_did="did:oai:responder",
            accepted=True,
            agreed_parameters={"price": 0.10}
        )
        
        agreement = negotiation_protocol.process_response(response)
        
        assert agreement is not None
        assert agreement.agreed_parameters["price"] == 0.10
        
        # Check session status updated
        updated_session = negotiation_protocol.get_session(session.session_id)
        assert updated_session.status == "agreed"
    
    def test_process_response_reject(self, negotiation_protocol):
        """Test processing a rejecting response."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"price": 0.10}
        )
        
        response = NegotiationResponse(
            request_id=session.session_id,
            responder_did="did:oai:responder",
            accepted=False,
            rejection_reason="Price too high"
        )
        
        agreement = negotiation_protocol.process_response(response)
        
        assert agreement is None
        
        updated_session = negotiation_protocol.get_session(session.session_id)
        assert updated_session.status == "rejected"
    
    def test_process_counter_offer(self, negotiation_protocol):
        """Test processing a counter-offer."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"price": 0.10}
        )
        
        response = NegotiationResponse(
            request_id=session.session_id,
            responder_did="did:oai:responder",
            accepted=False,
            counter_parameters={"price": 0.15},
            message="Counter offer"
        )
        
        # Should create a new round
        updated_session = negotiation_protocol.get_session(session.session_id)
        assert len(updated_session.rounds) == 1
        assert updated_session.rounds[0].parameters["price"] == 0.15
    
    def test_max_rounds_exceeded(self, negotiation_protocol):
        """Test negotiation fails after max rounds."""
        session = negotiation_protocol.create_session(
            initiator_did="did:oai:initiator",
            responder_did="did:oai:responder",
            template_id="a2a_delegation",
            parameters={"price": 0.10}
        )
        
        # Simulate max rounds
        for i in range(negotiation_protocol.max_rounds):
            response = NegotiationResponse(
                request_id=session.session_id,
                responder_did="did:oai:responder" if i % 2 == 0 else "did:oai:initiator",
                accepted=False,
                counter_parameters={"price": 0.10 + i * 0.01}
            )
            negotiation_protocol.process_response(response)
        
        # Next round should fail
        response = NegotiationResponse(
            request_id=session.session_id,
            responder_did="did:oai:responder",
            accepted=False,
            counter_parameters={"price": 0.20}
        )
        
        agreement = negotiation_protocol.process_response(response)
        
        assert agreement is None
        updated_session = negotiation_protocol.get_session(session.session_id)
        assert updated_session.status == "failed"


class TestNegotiationStrategies:
    """Tests for negotiation strategies."""
    
    def test_cooperative_strategy(self):
        """Test CooperativeStrategy makes reasonable compromises."""
        strategy = CooperativeStrategy()
        
        # Should accept fair offers
        decision = strategy.decide(
            current_offer={"price": 0.10},
            our_limit={"price": 0.15},
            round_number=1,
            max_rounds=5
        )
        
        assert decision["action"] == "accept"
    
    def test_cooperative_strategy_counter(self):
        """Test CooperativeStrategy counters when offer is low."""
        strategy = CooperativeStrategy()
        
        decision = strategy.decide(
            current_offer={"price": 0.01},  # Very low
            our_limit={"price": 0.15},
            round_number=1,
            max_rounds=5
        )
        
        assert decision["action"] == "counter"
        assert decision["parameters"]["price"] > 0.01
        assert decision["parameters"]["price"] <= 0.15
    
    def test_competitive_strategy(self):
        """Test CompetitiveStrategy pushes for best terms."""
        strategy = CompetitiveStrategy()
        
        decision = strategy.decide(
            current_offer={"price": 0.10},
            our_limit={"price": 0.15},
            round_number=1,
            max_rounds=5
        )
        
        # Competitive strategy should counter with higher price
        assert decision["action"] == "counter"
        assert decision["parameters"]["price"] >= 0.10
    
    def test_competitive_strategy_accept_near_limit(self):
        """Test CompetitiveStrategy accepts when near limit."""
        strategy = CompetitiveStrategy()
        
        decision = strategy.decide(
            current_offer={"price": 0.14},  # Close to our limit of 0.15
            our_limit={"price": 0.15},
            round_number=4,  # Late round
            max_rounds=5
        )
        
        assert decision["action"] == "accept"
    
    def test_balanced_strategy(self):
        """Test BalancedStrategy adapts based on round."""
        strategy = BalancedStrategy()
        
        # Early round - should be more flexible
        decision_early = strategy.decide(
            current_offer={"price": 0.08},
            our_limit={"price": 0.15},
            round_number=1,
            max_rounds=5
        )
        
        # Late round - should be more firm
        decision_late = strategy.decide(
            current_offer={"price": 0.08},
            our_limit={"price": 0.15},
            round_number=4,
            max_rounds=5
        )
        
        # Both should counter but late round should be closer to limit
        assert decision_early["action"] == "counter"
        assert decision_late["action"] == "counter"
        assert decision_late["parameters"]["price"] >= decision_early["parameters"]["price"]
    
    def test_strategy_with_multiple_parameters(self):
        """Test strategies work with multiple parameters."""
        strategy = BalancedStrategy()
        
        decision = strategy.decide(
            current_offer={"price": 0.10, "timeout": 60},
            our_limit={"price": 0.15, "timeout": 30},
            round_number=2,
            max_rounds=5
        )
        
        assert decision["action"] in ["accept", "counter"]
        if decision["action"] == "counter":
            assert "price" in decision["parameters"]
            assert "timeout" in decision["parameters"]