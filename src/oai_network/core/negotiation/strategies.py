"""
Negotiation Strategies

Different strategies for negotiating terms.
"""

from abc import ABC, abstractmethod
from typing import Any
from .models import NegotiationSession, NegotiationTopic, NegotiationRequest


class NegotiationStrategy(ABC):
    """Base class for negotiation strategies."""
    
    @abstractmethod
    def generate_initial_terms(
        self, 
        request: NegotiationRequest,
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate initial proposed terms."""
        pass
    
    @abstractmethod
    def generate_counter_terms(
        self, 
        session: NegotiationSession,
        received_terms: dict[str, Any],
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate counter-terms in response to received terms."""
        pass
    
    @abstractmethod
    def evaluate_terms(
        self, 
        terms: dict[str, Any],
        agent_capabilities: dict[str, Any],
        constraints: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """
        Evaluate if terms are acceptable.
        
        Returns:
            Tuple of (accepted, counter_terms)
        """
        pass


class CooperativeStrategy(NegotiationStrategy):
    """
    Cooperative strategy - tries to find mutually beneficial terms.
    
    Characteristics:
    - Willing to compromise on price/latency
    - Prioritizes agreement over optimal terms
    - Good for long-term relationships
    """
    
    def __init__(self, flexibility: float = 0.3):
        self.flexibility = flexibility  # How much to compromise (0-1)
    
    def generate_initial_terms(
        self, 
        request: NegotiationRequest,
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate fair initial terms based on capabilities."""
        terms = request.proposed_terms.copy()
        
        # Adjust based on our capabilities
        if 'price_per_call' in terms and 'our_price' in agent_capabilities:
            # Meet in the middle
            their_price = terms['price_per_call']
            our_price = agent_capabilities['our_price']
            terms['price_per_call'] = (their_price + our_price) / 2
        
        if 'timeout_seconds' in terms and 'our_max_timeout' in agent_capabilities:
            # Use minimum of both
            terms['timeout_seconds'] = min(
                terms['timeout_seconds'],
                agent_capabilities['our_max_timeout']
            )
        
        if 'rate_limit_rpm' in terms and 'our_rate_limit' in agent_capabilities:
            # Use minimum
            terms['rate_limit_rpm'] = min(
                terms['rate_limit_rpm'],
                agent_capabilities['our_rate_limit']
            )
        
        return terms
    
    def generate_counter_terms(
        self, 
        session: NegotiationSession,
        received_terms: dict[str, Any],
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate compromise counter-terms."""
        counter = {}
        current = session.current_terms
        
        # Price negotiation - move toward middle
        if 'price_per_call' in received_terms and 'our_price' in agent_capabilities:
            their_price = received_terms['price_per_call']
            our_price = agent_capabilities['our_price']
            current_price = current.get('price_per_call', their_price)
            
            # Move toward middle with flexibility
            target = (their_price + our_price) / 2
            counter['price_per_call'] = current_price + self.flexibility * (target - current_price)
        
        # Timeout - use minimum
        if 'timeout_seconds' in received_terms and 'our_max_timeout' in agent_capabilities:
            counter['timeout_seconds'] = min(
                received_terms['timeout_seconds'],
                agent_capabilities['our_max_timeout']
            )
        
        # Rate limit - use minimum
        if 'rate_limit_rpm' in received_terms and 'our_rate_limit' in agent_capabilities:
            counter['rate_limit_rpm'] = min(
                received_terms['rate_limit_rpm'],
                agent_capabilities['our_rate_limit']
            )
        
        # SLA - try to meet their requirement if reasonable
        if 'sla_uptime' in received_terms and 'our_uptime' in agent_capabilities:
            their_sla = received_terms['sla_uptime']
            our_uptime = agent_capabilities['our_uptime']
            if our_uptime >= their_sla:
                counter['sla_uptime'] = their_sla
            else:
                # Offer what we can do
                counter['sla_uptime'] = our_uptime
        
        return counter
    
    def evaluate_terms(
        self, 
        terms: dict[str, Any],
        agent_capabilities: dict[str, Any],
        constraints: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """Evaluate if terms are acceptable."""
        counter = {}
        acceptable = True
        
        # Check price
        if 'price_per_call' in terms and 'our_price' in agent_capabilities:
            if terms['price_per_call'] < agent_capabilities['our_price'] * (1 - self.flexibility):
                acceptable = False
                counter['price_per_call'] = agent_capabilities['our_price']
        
        # Check constraints
        if 'min_sla_uptime' in constraints and 'sla_uptime' in terms:
            if terms['sla_uptime'] < constraints['min_sla_uptime']:
                acceptable = False
                counter['sla_uptime'] = constraints['min_sla_uptime']
        
        if 'max_price_per_call' in constraints and 'price_per_call' in terms:
            if terms['price_per_call'] > constraints['max_price_per_call']:
                acceptable = False
                counter['price_per_call'] = constraints['max_price_per_call']
        
        if 'max_timeout_seconds' in constraints and 'timeout_seconds' in terms:
            if terms['timeout_seconds'] > constraints['max_timeout_seconds']:
                acceptable = False
                counter['timeout_seconds'] = constraints['max_timeout_seconds']
        
        return acceptable, counter


class CompetitiveStrategy(NegotiationStrategy):
    """
    Competitive strategy - tries to get the best terms for ourselves.
    
    Characteristics:
    - Pushes for favorable pricing
    - Less willing to compromise
    - Good for one-off interactions
    """
    
    def __init__(self, aggressiveness: float = 0.7):
        self.aggressiveness = aggressiveness  # How aggressive (0-1)
    
    def generate_initial_terms(
        self, 
        request: NegotiationRequest,
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate aggressive initial terms."""
        terms = request.proposed_terms.copy()
        
        # Push for better price
        if 'price_per_call' in terms and 'our_price' in agent_capabilities:
            # Ask for more than our cost
            terms['price_per_call'] = agent_capabilities['our_price'] * (1 + self.aggressiveness)
        
        # Push for higher rate limits
        if 'rate_limit_rpm' in terms and 'our_rate_limit' in agent_capabilities:
            terms['rate_limit_rpm'] = int(agent_capabilities['our_rate_limit'] * 0.8)
        
        # Push for longer timeouts
        if 'timeout_seconds' in terms and 'our_max_timeout' in agent_capabilities:
            terms['timeout_seconds'] = int(agent_capabilities['our_max_timeout'] * 0.9)
        
        return terms
    
    def generate_counter_terms(
        self, 
        session: NegotiationSession,
        received_terms: dict[str, Any],
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate counter-terms that favor us."""
        counter = {}
        current = session.current_terms
        
        # Price - barely move
        if 'price_per_call' in received_terms and 'our_price' in agent_capabilities:
            their_price = received_terms['price_per_call']
            our_price = agent_capabilities['our_price']
            current_price = current.get('price_per_call', their_price)
            
            # Only move slightly toward their price
            min_acceptable = our_price * (1 + self.aggressiveness * 0.5)
            if their_price < min_acceptable:
                counter['price_per_call'] = min_acceptable
            else:
                counter['price_per_call'] = current_price * 0.95  # Small concession
        
        # Other terms - minimal concessions
        if 'timeout_seconds' in received_terms:
            counter['timeout_seconds'] = max(
                received_terms['timeout_seconds'],
                current.get('timeout_seconds', 30)
            )
        
        return counter
    
    def evaluate_terms(
        self, 
        terms: dict[str, Any],
        agent_capabilities: dict[str, Any],
        constraints: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """Evaluate terms - reject unless very favorable."""
        counter = {}
        acceptable = True
        
        # Price must be above our minimum
        if 'price_per_call' in terms and 'our_price' in agent_capabilities:
            min_price = agent_capabilities['our_price'] * (1 + self.aggressiveness * 0.3)
            if terms['price_per_call'] < min_price:
                acceptable = False
                counter['price_per_call'] = min_price
        
        # Check hard constraints
        if 'max_price_per_call' in constraints and 'price_per_call' in terms:
            if terms['price_per_call'] > constraints['max_price_per_call']:
                acceptable = False
                counter['price_per_call'] = constraints['max_price_per_call']
        
        return acceptable, counter


class BalancedStrategy(NegotiationStrategy):
    """
    Balanced strategy - adapts based on context.
    
    Characteristics:
    - Cooperative with high-trust agents
    - Competitive with unknown agents
    - Considers relationship history
    """
    
    def __init__(self, trust_threshold: float = 0.7):
        self.trust_threshold = trust_threshold
        self.cooperative = CooperativeStrategy()
        self.competitive = CompetitiveStrategy()
    
    def _choose_strategy(self, session: NegotiationSession) -> NegotiationStrategy:
        """Choose strategy based on trust score."""
        # In practice, would look up trust score for counterparty
        # For now, default to cooperative
        return self.cooperative
    
    def generate_initial_terms(
        self, 
        request: NegotiationRequest,
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        strategy = self._choose_strategy(None)
        return strategy.generate_initial_terms(request, agent_capabilities)
    
    def generate_counter_terms(
        self, 
        session: NegotiationSession,
        received_terms: dict[str, Any],
        agent_capabilities: dict[str, Any]
    ) -> dict[str, Any]:
        strategy = self._choose_strategy(session)
        return strategy.generate_counter_terms(session, received_terms, agent_capabilities)
    
    def evaluate_terms(
        self, 
        terms: dict[str, Any],
        agent_capabilities: dict[str, Any],
        constraints: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        strategy = self._choose_strategy(None)
        return strategy.evaluate_terms(terms, agent_capabilities, constraints)