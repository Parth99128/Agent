"""
Capability Matcher

Matches natural language queries to agent capabilities.
"""

from typing import Optional
from dataclasses import dataclass
from .models import AgentManifest, Capability


@dataclass
class MatchResult:
    """Result of a capability match."""
    agent_did: str
    agent_name: str
    agent_description: str
    capability_name: str
    capability_type: str
    relevance_score: float
    trust_score: float
    estimated_latency_ms: Optional[int] = None
    price_per_unit: Optional[float] = None
    currency: str = "USD"
    endpoint_url: str = ""
    tags: list[str] = None
    verified: bool = False
    last_updated: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @property
    def average_latency_ms(self) -> Optional[int]:
        """Alias for estimated_latency_ms for backward compatibility."""
        return self.estimated_latency_ms


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
        manifests: list[AgentManifest],
        query: Optional[str] = None,
        capability_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        rank_by: Optional[str] = None
    ) -> list[MatchResult]:
        """
        Match a query against multiple agent manifests.
        
        Returns:
            List of MatchResult objects sorted by score descending
        """
        results = []
        
        for manifest in manifests:
            if query:
                matches = manifest.find_capabilities(query, self.min_score)
            else:
                # If no query, match all capabilities
                matches = [(cap, 1.0) for cap in manifest.capabilities]
            
            for capability, score in matches:
                # Filter by type if specified
                if capability_type and capability.type != capability_type:
                    continue
                
                # Filter by tags if specified
                if tags:
                    tag_match = any(tag.lower() in [t.lower() for t in capability.tags] for tag in tags)
                    if not tag_match:
                        continue
                
                # Get primary endpoint
                endpoint_url = ""
                if manifest.endpoints:
                    endpoint_url = manifest.endpoints[0].url
                
                result = MatchResult(
                    agent_did=manifest.identity.did,
                    agent_name=manifest.name,
                    agent_description=manifest.description,
                    capability_name=capability.name,
                    capability_type=capability.type,
                    relevance_score=score,
                    trust_score=manifest.trust_metrics.score,
                    estimated_latency_ms=manifest.trust_metrics.average_latency_ms or capability.estimated_latency_ms,
                    price_per_unit=capability.pricing.price_per_call,
                    currency=capability.pricing.currency,
                    endpoint_url=endpoint_url,
                    tags=capability.tags,
                    verified=manifest.trust_metrics.verified_identity,
                    last_updated=manifest.updated_at.isoformat() if manifest.updated_at else ""
                )
                results.append(result)
        
        # Apply ranking
        if rank_by == "trust":
            results.sort(key=lambda x: x.trust_score, reverse=True)
        elif rank_by == "latency":
            results.sort(key=lambda x: x.estimated_latency_ms or float('inf'))
        elif rank_by == "price":
            results.sort(key=lambda x: x.price_per_unit or float('inf'))
        else:
            # Default: sort by relevance score
            results.sort(key=lambda x: x.relevance_score, reverse=True)
        
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
                if cap.type == capability_type
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
                if cap.type == capability_type:
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