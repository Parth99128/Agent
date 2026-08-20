"""
Trust Calculator

Calculates trust scores from reputation ledgers and events.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from .models import TrustEvent, TrustScore, TrustEventType, ReputationLedger


class TrustCalculator:
    """
    Calculates trust scores using multiple factors:
    - Interaction success rate
    - Feedback ratings
    - Identity verification status
    - Behavior patterns
    - Time decay
    - Volume confidence
    """
    
    def __init__(
        self,
        interaction_weight: float = 0.35,
        feedback_weight: float = 0.25,
        identity_weight: float = 0.20,
        behavior_weight: float = 0.20,
        half_life_days: int = 30,
        target_interactions: int = 100,
        store: Optional['TrustStore'] = None,
    ):
        self.weights = {
            'interaction': interaction_weight,
            'feedback': feedback_weight,
            'identity': identity_weight,
            'behavior': behavior_weight,
        }
        self.half_life_days = half_life_days
        self.target_interactions = target_interactions
        self.default_score = 0.5
        self.store = store
    
    def set_store(self, store: 'TrustStore'):
        """Set the trust store for calculating scores."""
        self.store = store
    
    def calculate_from_ledger(self, ledger: ReputationLedger) -> TrustScore:
        """Calculate trust score from a reputation ledger."""
        events = ledger.events
        
        if not events:
            return TrustScore(agent_did=ledger.agent_did)
        
        # Separate events by type
        interaction_events = [
            e for e in events 
            if e.event_type in (
                TrustEventType.INTERACTION_SUCCESS,
                TrustEventType.INTERACTION_FAILURE,
                TrustEventType.INTERACTION_TIMEOUT,
            )
        ]
        feedback_events = [
            e for e in events 
            if e.event_type in (
                TrustEventType.POSITIVE_FEEDBACK,
                TrustEventType.NEGATIVE_FEEDBACK,
            )
        ]
        identity_events = [
            e for e in events 
            if e.event_type in (
                TrustEventType.IDENTITY_VERIFIED,
                TrustEventType.IDENTITY_REVOKED,
            )
        ]
        behavior_events = [
            e for e in events 
            if e.event_type in (
                TrustEventType.POLICY_VIOLATION,
                TrustEventType.DELEGATION_SUCCESS,
                TrustEventType.DELEGATION_FAILURE,
            )
        ]
        
        # Calculate component scores
        interaction_score = self._calculate_interaction_score(interaction_events)
        feedback_score = self._calculate_feedback_score(feedback_events)
        identity_score = self._calculate_identity_score(identity_events)
        behavior_score = self._calculate_behavior_score(behavior_events)
        
        # Calculate overall score
        overall = (
            self.weights['interaction'] * interaction_score +
            self.weights['feedback'] * feedback_score +
            self.weights['identity'] * identity_score +
            self.weights['behavior'] * behavior_score
        )
        
        # Calculate metrics
        total_interactions = len(interaction_events)
        successful = len([e for e in interaction_events if e.event_type == TrustEventType.INTERACTION_SUCCESS])
        failed = len([e for e in interaction_events if e.event_type == TrustEventType.INTERACTION_FAILURE])
        
        latencies = [e.latency_ms for e in interaction_events if e.latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        total_feedback = len(feedback_events)
        positive_feedback = len([e for e in feedback_events if e.event_type == TrustEventType.POSITIVE_FEEDBACK])
        negative_feedback = len([e for e in feedback_events if e.event_type == TrustEventType.NEGATIVE_FEEDBACK])
        
        identity_verified = any(e.event_type == TrustEventType.IDENTITY_VERIFIED for e in identity_events)
        policy_violations = len([e for e in behavior_events if e.event_type == TrustEventType.POLICY_VIOLATION])
        
        last_interaction = None
        if interaction_events:
            last_interaction = max(e.timestamp for e in interaction_events)
        
        # Confidence based on volume and recency
        volume_factor = min(1.0, total_interactions / self.target_interactions)
        recency_factor = 1.0
        if last_interaction:
            days_since = (datetime.now(timezone.utc) - last_interaction).days
            recency_factor = max(0.1, 0.5 ** (days_since / self.half_life_days))
        confidence = (volume_factor + recency_factor) / 2
        
        return TrustScore(
            agent_did=ledger.agent_did,
            overall_score=max(0.0, min(1.0, overall)),
            interaction_score=interaction_score,
            feedback_score=feedback_score,
            identity_score=identity_score,
            behavior_score=behavior_score,
            event_count=len(events),
            interaction_count=total_interactions,
            successful_interactions=successful,
            failed_interactions=failed,
            avg_latency_ms=avg_latency,
            total_feedback=total_feedback,
            positive_feedback=positive_feedback,
            negative_feedback=negative_feedback,
            identity_verified=identity_verified,
            policy_violations=policy_violations,
            last_updated=datetime.now(timezone.utc),
            last_interaction=last_interaction,
            confidence=confidence,
        )
    
    def _calculate_interaction_score(self, events: list[TrustEvent]) -> float:
        """Calculate score from interaction events."""
        if not events:
            return 0.5
        
        # Weight by recency
        now = datetime.now(timezone.utc)
        total_weight = 0.0
        weighted_sum = 0.0
        
        for event in events:
            days_old = (now - event.timestamp).days
            recency_weight = 0.5 ** (days_old / self.half_life_days)
            
            event_weight = 1.0
            if event.event_type == TrustEventType.INTERACTION_SUCCESS:
                event_weight = 1.0
            elif event.event_type == TrustEventType.INTERACTION_FAILURE:
                event_weight = 0.0
            elif event.event_type == TrustEventType.INTERACTION_TIMEOUT:
                event_weight = 0.3
            
            weighted_sum += event_weight * recency_weight
            total_weight += recency_weight
        
        if total_weight == 0:
            return 0.5
        
        return weighted_sum / total_weight
    
    def _calculate_feedback_score(self, events: list[TrustEvent]) -> float:
        """Calculate score from feedback events."""
        if not events:
            return 0.5
        
        # Weight by recency and rating
        now = datetime.now(timezone.utc)
        total_weight = 0.0
        weighted_sum = 0.0
        
        for event in events:
            days_old = (now - event.timestamp).days
            recency_weight = 0.5 ** (days_old / self.half_life_days)
            
            # Convert rating to 0-1 score
            if event.feedback_rating:
                rating_score = (event.feedback_rating - 1) / 4  # 1->0, 5->1
            elif event.event_type == TrustEventType.POSITIVE_FEEDBACK:
                rating_score = 0.8
            elif event.event_type == TrustEventType.NEGATIVE_FEEDBACK:
                rating_score = 0.2
            else:
                rating_score = 0.5
            
            weighted_sum += rating_score * recency_weight
            total_weight += recency_weight
        
        if total_weight == 0:
            return 0.5
        
        return weighted_sum / total_weight
    
    def _calculate_identity_score(self, events: list[TrustEvent]) -> float:
        """Calculate score from identity events."""
        if not events:
            return 0.5
        
        # Identity verified is strong positive, revoked is strong negative
        verified = any(e.event_type == TrustEventType.IDENTITY_VERIFIED for e in events)
        revoked = any(e.event_type == TrustEventType.IDENTITY_REVOKED for e in events)
        
        if revoked:
            return 0.0
        if verified:
            return 1.0
        return 0.5
    
    def _calculate_behavior_score(self, events: list[TrustEvent]) -> float:
        """Calculate score from behavior events."""
        if not events:
            return 0.5
        
        now = datetime.now(timezone.utc)
        total_weight = 0.0
        weighted_sum = 0.0
        
        for event in events:
            days_old = (now - event.timestamp).days
            recency_weight = 0.5 ** (days_old / self.half_life_days)
            
            event_weight = 0.5
            if event.event_type == TrustEventType.POLICY_VIOLATION:
                event_weight = 0.0
            elif event.event_type == TrustEventType.DELEGATION_SUCCESS:
                event_weight = 0.7
            elif event.event_type == TrustEventType.DELEGATION_FAILURE:
                event_weight = 0.3
            
            weighted_sum += event_weight * recency_weight
            total_weight += recency_weight
        
        if total_weight == 0:
            return 0.5
        
        return weighted_sum / total_weight
    
    def update_score_incremental(
        self, 
        current: TrustScore,
        event: TrustEvent
    ) -> TrustScore:
        """Update a trust score incrementally with a new event."""
        # For simplicity, recalculate from a synthetic ledger
        # In production, you'd use a more efficient incremental algorithm
        from .models import ReputationLedger
        ledger = ReputationLedger(agent_did=current.agent_did)
        
        # Add synthetic events to match current score
        # This is a simplified approach
        return self.calculate_from_ledger(ledger)
    
    def calculate(self, agent_did: str, store: Optional['TrustStore'] = None) -> TrustScore:
        """Calculate trust score for an agent."""
        # Use provided store or the one set on the calculator
        effective_store = store or self.store
        if effective_store is not None:
            ledger = effective_store.get_ledger(agent_did)
            return self.calculate_from_ledger(ledger)
        return TrustScore(agent_did=agent_did, overall_score=self.default_score)