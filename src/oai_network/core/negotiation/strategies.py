"""
Negotiation Strategies

Different strategies for negotiating terms.
"""

from abc import ABC, abstractmethod
from typing import Any


class NegotiationStrategy(ABC):
    """Base class for negotiation strategies."""

    @abstractmethod
    def decide(
        self,
        current_offer: dict[str, Any],
        our_limit: dict[str, Any],
        round_number: int,
        max_rounds: int,
    ) -> dict[str, Any]:
        """
        Decide whether to accept, reject, or counter-offer.

        Args:
            current_offer: The current offer parameters
            our_limit: Our maximum acceptable limits
            round_number: Current round number
            max_rounds: Maximum rounds allowed

        Returns:
            Dict with 'action' ('accept', 'reject', 'counter') and 'parameters'
        """
        pass


class CooperativeStrategy(NegotiationStrategy):
    """
    Cooperative strategy - tries to find mutually beneficial terms.
    More willing to compromise, accepts fair offers quickly.
    """

    def __init__(self, flexibility: float = 0.3):
        self.flexibility = flexibility

    def decide(
        self,
        current_offer: dict[str, Any],
        our_limit: dict[str, Any],
        round_number: int,
        max_rounds: int,
    ) -> dict[str, Any]:
        """Decide whether to accept or counter."""
        # Check if offer exceeds our limits
        exceeds_limits = False
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    if offer_val > limit:
                        exceeds_limits = True

        # Check if offer is too far below our limits (unfair)
        too_low = False
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    # If offer is less than 50% of our limit, it's too low
                    if limit > 0 and offer_val < limit * 0.5:
                        too_low = True

        # Accept if offer is within limits and not too low
        if not exceeds_limits and not too_low:
            return {"action": "accept", "parameters": current_offer}

        # Generate counter-offer - move toward middle
        counter = {}
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    # Move toward middle with flexibility
                    target = (offer_val + limit) / 2
                    counter[key] = offer_val + self.flexibility * (target - offer_val)
                else:
                    counter[key] = offer_val
            else:
                counter[key] = limit

        return {"action": "counter", "parameters": counter}


class CompetitiveStrategy(NegotiationStrategy):
    """
    Competitive strategy - pushes for best terms.
    Less willing to compromise, counters aggressively.
    """

    def __init__(self, aggressiveness: float = 0.7):
        self.aggressiveness = aggressiveness

    def decide(
        self,
        current_offer: dict[str, Any],
        our_limit: dict[str, Any],
        round_number: int,
        max_rounds: int,
    ) -> dict[str, Any]:
        """Decide whether to accept or counter."""
        # Check if offer is within our limits
        all_within_limits = True
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    if offer_val > limit:
                        all_within_limits = False

        # Accept if near our limit (late rounds) or within limits
        progress = round_number / max_rounds if max_rounds > 0 else 1.0
        if all_within_limits and progress > 0.6:
            return {"action": "accept", "parameters": current_offer}

        if all_within_limits:
            # Still counter but closer to our limit
            counter = {}
            for key, limit in our_limit.items():
                if key in current_offer:
                    counter[key] = current_offer[key]
                else:
                    counter[key] = limit
            return {"action": "counter", "parameters": counter}

        # Counter aggressively - push toward our limit
        counter = {}
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    # Move aggressively toward our limit
                    counter[key] = offer_val + self.aggressiveness * (limit - offer_val)
                else:
                    counter[key] = offer_val
            else:
                counter[key] = limit

        return {"action": "counter", "parameters": counter}


class BalancedStrategy(NegotiationStrategy):
    """
    Balanced strategy - adapts based on round number.
    More flexible early, more firm late.
    """

    def __init__(self, initial_flexibility: float = 0.5):
        self.initial_flexibility = initial_flexibility

    def decide(
        self,
        current_offer: dict[str, Any],
        our_limit: dict[str, Any],
        round_number: int,
        max_rounds: int,
    ) -> dict[str, Any]:
        """Decide whether to accept or counter, adapting based on round."""
        # Check if offer exceeds our limits
        exceeds_limits = False
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    if offer_val > limit:
                        exceeds_limits = True

        # Calculate flexibility based on round (increases over time - more willing to compromise late)
        progress = round_number / max_rounds if max_rounds > 0 else 1.0
        flexibility = self.initial_flexibility * progress

        # Accept only if offer is exactly at or very near our limit
        if not exceeds_limits:
            near_limit = True
            for key, limit in our_limit.items():
                if key in current_offer:
                    offer_val = current_offer[key]
                    if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                        if limit > 0 and abs(offer_val - limit) / limit > 0.1:
                            near_limit = False
            if near_limit:
                return {"action": "accept", "parameters": current_offer}

        # Generate counter-offer
        counter = {}
        for key, limit in our_limit.items():
            if key in current_offer:
                offer_val = current_offer[key]
                if isinstance(offer_val, (int, float)) and isinstance(limit, (int, float)):
                    # Move toward our limit with decreasing flexibility
                    counter[key] = offer_val + flexibility * (limit - offer_val)
                else:
                    counter[key] = offer_val
            else:
                counter[key] = limit

        return {"action": "counter", "parameters": counter}