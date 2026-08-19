"""
Capability Matcher

Matches natural language queries to agent capabilities.
"""

from typing import Optional
from .models import AgentManifest, Capability


class CapabilityMatcher:
    """
    Matches queries to capabilities using multiple strategies.
    
    Strategies:
    1. Exact name match
    2. Tag/category match
    3. Description semantic similarity (simple keyword overlap)
    4. Type-based matching
    """
    
    def __init__(self, min_score: float = 0.3):
        self.min_score = min_score
    
    def match(
        self, 
        query: str, 
        manifests: list[AgentManifest],
        capability_type: Optional[str] = None
    ) -> list[tuple[AgentManifest, Capability, float]]:
        """
        Match a query against multiple agent manifests.
        
        Returns:
            List of (manifest, capability, score) tuples sorted by score descending
        """
        results = []
        
        for manifest in manifests:
            matches = manifest.find_capabilities(query, self.min_score)
            for capability, score in matches:
                # Filter by type if specified
                if capability_type and capability.type.value != capability_type:
                    continue
                results.append((manifest, capability, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results
    
    def match_single_manifest(
        self, 
        query: str, 
        manifest: AgentManifest,
        capability_type: Optional[str] = None
    ) -> list[tuple[Capability, float]]:
        """Match a query against a single manifest."""
        matches = manifest.find_capabilities(query, self.min_score)
        
        if capability_type:
            matches = [
                (cap, score) for cap, score in matches 
                if cap.type.value == capability_type
            ]
        
        return matches
    
    def find_by_type(
        self, 
        capability_type: str, 
        manifests: list[AgentManifest]
    ) -> list[tuple[AgentManifest, Capability]]:
        """Find all capabilities of a specific type."""
        results = []
        for manifest in manifests:
            for cap in manifest.capabilities:
                if cap.type.value == capability_type:
                    results.append((manifest, cap))
        return results
    
    def find_by_tag(
        self, 
        tag: str, 
        manifests: list[AgentManifest]
    ) -> list[tuple[AgentManifest, Capability]]:
        """Find all capabilities with a specific tag."""
        results = []
        tag_lower = tag.lower()
        for manifest in manifests:
            for cap in manifest.capabilities:
                if any(tag_lower in t.lower() for t in cap.tags):
                    results.append((manifest, cap))
        return results
    
    def rank_by_trust(
        self, 
        matches: list[tuple[AgentManifest, Capability, float]]
    ) -> list[tuple[AgentManifest, Capability, float]]:
        """Re-rank matches by trust score."""
        return sorted(
            matches,
            key=lambda x: (x[2] * 0.7 + x[0].trust_metrics.overall_score * 0.3),
            reverse=True
        )
    
    def rank_by_latency(
        self, 
        matches: list[tuple[AgentManifest, Capability, float]]
    ) -> list[tuple[AgentManifest, Capability, float]]:
        """Re-rank matches by estimated latency (lower is better)."""
        return sorted(
            matches,
            key=lambda x: x[1].estimated_latency_ms or float('inf')
        )
    
    def rank_by_price(
        self, 
        matches: list[tuple[AgentManifest, Capability, float]],
        ascending: bool = True
    ) -> list[tuple[AgentManifest, Capability, float]]:
        """Re-rank matches by price."""
        def price_key(item):
            cap = item[1]
            if cap.pricing.value == "free":
                return 0.0
            return cap.price_per_unit or float('inf')
        
        return sorted(matches, key=price_key, reverse=not ascending)