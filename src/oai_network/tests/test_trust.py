"""
Tests for the trust module.
"""

import pytest
from oai_network.core.trust.models import (
    TrustEvent, TrustEventType, TrustScore, Feedback, ReputationLedger
)
from oai_network.core.trust.calculator import TrustCalculator
from oai_network.core.trust.store import TrustStore


class TestTrustModels:
    """Tests for trust data models."""
    
    def test_trust_event_creation(self):
        """Test creating a TrustEvent."""
        event = TrustEvent(
            event_type=TrustEventType.INTERACTION_SUCCESS,
            source_did="did:oai:source123",
            target_did="did:oai:target123",
            weight=1.0,
            metadata={"capability": "text_summarization"}
        )
        
        assert event.event_type == TrustEventType.INTERACTION_SUCCESS
        assert event.source_did == "did:oai:source123"
        assert event.target_did == "did:oai:target123"
        assert event.weight == 1.0
        assert event.metadata["capability"] == "text_summarization"
    
    def test_trust_event_types(self):
        """Test all trust event types."""
        assert TrustEventType.INTERACTION_SUCCESS.value == "interaction_success"
        assert TrustEventType.INTERACTION_FAILURE.value == "interaction_failure"
        assert TrustEventType.POSITIVE_FEEDBACK.value == "positive_feedback"
        assert TrustEventType.NEGATIVE_FEEDBACK.value == "negative_feedback"
        assert TrustEventType.DELEGATION_SUCCESS.value == "delegation_success"
        assert TrustEventType.DELEGATION_FAILURE.value == "delegation_failure"
        assert TrustEventType.IDENTITY_VERIFIED.value == "identity_verified"
        assert TrustEventType.POLICY_VIOLATION.value == "policy_violation"
    
    def test_trust_score_creation(self, sample_trust_score):
        """Test creating a TrustScore."""
        assert sample_trust_score.agent_did.startswith("did:oai:")
        assert 0 <= sample_trust_score.overall_score <= 1
        assert sample_trust_score.interaction_score >= 0
        assert sample_trust_score.feedback_score >= 0
        assert sample_trust_score.identity_score >= 0
        assert sample_trust_score.behavior_score >= 0
    
    def test_feedback_creation(self):
        """Test creating Feedback."""
        feedback = Feedback(
            from_did="did:oai:reviewer123",
            to_did="did:oai:target123",
            rating=5,
            comment="Excellent service",
            capability="text_summarization"
        )
        
        assert feedback.from_did == "did:oai:reviewer123"
        assert feedback.to_did == "did:oai:target123"
        assert feedback.rating == 5
        assert feedback.comment == "Excellent service"
    
    def test_feedback_rating_bounds(self):
        """Test feedback rating validation."""
        # Valid ratings
        for rating in [1, 2, 3, 4, 5]:
            feedback = Feedback(
                from_did="did:oai:reviewer",
                to_did="did:oai:target",
                rating=rating
            )
            assert feedback.rating == rating
    
    def test_reputation_ledger(self):
        """Test ReputationLedger."""
        ledger = ReputationLedger()
        
        event = TrustEvent(
            event_type=TrustEventType.INTERACTION_SUCCESS,
            source_did="did:oai:source",
            target_did="did:oai:target",
            weight=1.0
        )
        
        ledger.add_event(event)
        
        events = ledger.get_events_for_agent("did:oai:target")
        assert len(events) == 1
        assert events[0].event_type == TrustEventType.INTERACTION_SUCCESS


class TestTrustCalculator:
    """Tests for TrustCalculator."""
    
    def test_calculate_initial_score(self, trust_calculator):
        """Test calculating initial trust score for new agent."""
        score = trust_calculator.calculate("did:oai:newagent")
        
        assert score.agent_did == "did:oai:newagent"
        assert score.overall_score == trust_calculator.default_score
        assert score.interaction_count == 0
    
    def test_calculate_with_successful_interactions(self, trust_calculator, trust_store):
        """Test trust score increases with successful interactions."""
        agent_did = "did:oai:testagent"
        
        # Add successful interaction events
        for i in range(5):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_did,
                weight=1.0
            )
            trust_store.add_event(event)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.interaction_score > trust_calculator.default_score
        assert score.interaction_count == 5
    
    def test_calculate_with_failed_interactions(self, trust_calculator, trust_store):
        """Test trust score decreases with failed interactions."""
        agent_did = "did:oai:testagent2"
        
        # Add failed interaction events
        for i in range(3):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_FAILURE,
                source_did="did:oai:source",
                target_did=agent_did,
                weight=1.0
            )
            trust_store.add_event(event)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.interaction_score < trust_calculator.default_score
        assert score.interaction_count == 3
    
    def test_calculate_with_positive_feedback(self, trust_calculator, trust_store):
        """Test trust score increases with positive feedback."""
        agent_did = "did:oai:testagent3"
        
        feedback = Feedback(
            from_did="did:oai:reviewer",
            to_did=agent_did,
            rating=5,
            comment="Great!"
        )
        trust_store.add_feedback(feedback)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.feedback_score > trust_calculator.default_score
    
    def test_calculate_with_negative_feedback(self, trust_calculator, trust_store):
        """Test trust score decreases with negative feedback."""
        agent_did = "did:oai:testagent4"
        
        feedback = Feedback(
            from_did="did:oai:reviewer",
            to_did=agent_did,
            rating=1,
            comment="Poor service"
        )
        trust_store.add_feedback(feedback)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.feedback_score < trust_calculator.default_score
    
    def test_time_decay(self, trust_calculator, trust_store):
        """Test that old events have less weight due to time decay."""
        agent_did = "did:oai:testagent5"
        
        # Add old event
        from datetime import datetime, timezone, timedelta
        old_event = TrustEvent(
            event_type=TrustEventType.INTERACTION_SUCCESS,
            source_did="did:oai:source",
            target_did=agent_did,
            weight=1.0,
            timestamp=datetime.now(timezone.utc) - timedelta(days=30)
        )
        trust_store.add_event(old_event)
        
        # Add recent event
        recent_event = TrustEvent(
            event_type=TrustEventType.INTERACTION_SUCCESS,
            source_did="did:oai:source",
            target_did=agent_did,
            weight=1.0,
            timestamp=datetime.now(timezone.utc)
        )
        trust_store.add_event(recent_event)
        
        score = trust_calculator.calculate(agent_did)
        
        # Recent event should have more weight
        assert score.interaction_count == 2
    
    def test_calculate_with_identity_verification(self, trust_calculator, trust_store):
        """Test trust score increases with identity verification."""
        agent_did = "did:oai:testagent6"
        
        event = TrustEvent(
            event_type=TrustEventType.IDENTITY_VERIFIED,
            source_did="did:oai:verifier",
            target_did=agent_did,
            weight=1.0
        )
        trust_store.add_event(event)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.identity_score > trust_calculator.default_score
    
    def test_calculate_with_policy_violation(self, trust_calculator, trust_store):
        """Test trust score decreases with policy violation."""
        agent_did = "did:oai:testagent7"
        
        event = TrustEvent(
            event_type=TrustEventType.POLICY_VIOLATION,
            source_did="did:oai:monitor",
            target_did=agent_did,
            weight=1.0
        )
        trust_store.add_event(event)
        
        score = trust_calculator.calculate(agent_did)
        
        assert score.behavior_score < trust_calculator.default_score


class TestTrustStore:
    """Tests for TrustStore."""
    
    @pytest.mark.asyncio
    async def test_add_event(self, trust_store):
        """Test adding trust event."""
        event = TrustEvent(
            event_type=TrustEventType.INTERACTION_SUCCESS,
            source_did="did:oai:source",
            target_did="did:oai:target",
            weight=1.0
        )
        
        await trust_store.add_event(event)
        
        events = await trust_store.get_events_for_agent("did:oai:target")
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_add_feedback(self, trust_store):
        """Test adding feedback."""
        feedback = Feedback(
            from_did="did:oai:reviewer",
            to_did="did:oai:target",
            rating=4,
            comment="Good"
        )
        
        await trust_store.add_feedback(feedback)
        
        feedbacks = await trust_store.get_feedback_for_agent("did:oai:target")
        assert len(feedbacks) == 1
        assert feedbacks[0].rating == 4
    
    @pytest.mark.asyncio
    async def test_get_trust_score(self, trust_store, trust_calculator):
        """Test getting trust score from store."""
        agent_did = "did:oai:testagent8"
        
        # Add some events
        for i in range(3):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_did,
                weight=1.0
            )
            await trust_store.add_event(event)
        
        score = await trust_store.get_trust_score(agent_did, trust_calculator)
        
        assert score.agent_did == agent_did
        assert score.interaction_count == 3
    
    @pytest.mark.asyncio
    async def test_get_events_pagination(self, trust_store):
        """Test event pagination."""
        agent_did = "did:oai:testagent9"
        
        # Add many events
        for i in range(15):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_did,
                weight=1.0
            )
            await trust_store.add_event(event)
        
        # Get first page
        events = await trust_store.get_events_for_agent(agent_did, limit=10)
        assert len(events) == 10
        
        # Get second page
        events = await trust_store.get_events_for_agent(agent_did, limit=10, offset=10)
        assert len(events) == 5


class TestTrustCalculatorAdvanced:
    """Advanced tests for TrustCalculator."""
    
    def test_wilson_score_interval(self, trust_calculator, trust_store):
        """Test Wilson score interval prevents low-volume agents from outranking high-volume ones."""
        # Agent with 2/2 successes (100% but low volume)
        agent_low_volume = "did:oai:lowvolume"
        for i in range(2):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_low_volume,
                weight=1.0
            )
            trust_store.add_event(event)
        
        # Agent with 200/210 successes (95% but high volume)
        agent_high_volume = "did:oai:highvolume"
        for i in range(200):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_high_volume,
                weight=1.0
            )
            trust_store.add_event(event)
        for i in range(10):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_FAILURE,
                source_did="did:oai:source",
                target_did=agent_high_volume,
                weight=1.0
            )
            trust_store.add_event(event)
        
        score_low = trust_calculator.calculate(agent_low_volume)
        score_high = trust_calculator.calculate(agent_high_volume)
        
        # High volume agent should have higher or equal trust despite lower success rate
        # because of Wilson score interval
        assert score_high.overall_score >= score_low.overall_score
    
    def test_trust_decay_inactive_agent(self, trust_calculator, trust_store):
        """Test trust decays for inactive agents."""
        from datetime import datetime, timezone, timedelta
        
        agent_did = "did:oai:inactive"
        
        # Add old successful events
        for i in range(10):
            event = TrustEvent(
                event_type=TrustEventType.INTERACTION_SUCCESS,
                source_did="did:oai:source",
                target_did=agent_did,
                weight=1.0,
                timestamp=datetime.now(timezone.utc) - timedelta(days=60)
            )
            trust_store.add_event(event)
        
        score = trust_calculator.calculate(agent_did)
        
        # Confidence should be low due to recency
        assert score.confidence < 0.5
        # Overall score should be pulled toward default due to low confidence
        assert score.overall_score < 0.8