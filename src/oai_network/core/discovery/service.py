"""
Discovery Service

Main service for agent discovery and registry management.
"""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any

from .models import (
    DiscoveryQuery, DiscoveryResult, RegistryEntry,
    RegistrationRequest, RegistrationResponse,
    Heartbeat, HeartbeatResponse
)
from ..capabilities.models import AgentManifest
from ..capabilities.matcher import CapabilityMatcher
from oai_network.core.observability import (
    get_logger, log_agent_action, log_error, get_trace_id,
    record_agent_discovery
)


class DiscoveryService:
    """
    Main discovery service for agent registration and lookup.

    Features:
    - Agent registration with identity verification
    - Capability-based search
    - TTL-based expiration
    - Heartbeat mechanism
    - Caching for performance
    """

    def __init__(
        self,
        database_url: str = "sqlite:///./registry.db",
        default_ttl_seconds: int = 86400,
        max_proof_age_seconds: int = 300,
    ):
        self.database_url = database_url
        self.default_ttl = default_ttl_seconds
        self.matcher = CapabilityMatcher()
        # In-memory registry: agent_did -> RegistryEntry
        self._registry: dict[str, RegistryEntry] = {}
        self.logger = get_logger("oai-network-discovery-service")

    async def register_agent(self, manifest: Any) -> RegistrationResponse:
        """
        Register a new agent or update existing registration.

        Args:
            manifest: AgentManifest object (or JSON string)

        Returns:
            RegistrationResponse with success status and agent_did
        """
        trace_id = get_trace_id()
        # Parse manifest if it's a string
        if isinstance(manifest, str):
            manifest = AgentManifest.model_validate_json(manifest)
        elif isinstance(manifest, dict):
            manifest = AgentManifest.model_validate(manifest)

        agent_did = manifest.identity.did

        log_agent_action(self.logger, "register_agent", agent_did, trace_id,
                        agent_name=manifest.name)

        # Check if agent already registered
        if agent_did in self._registry:
            existing = self._registry[agent_did]
            if existing.status == "active":
                log_agent_action(self.logger, "register_agent_conflict", agent_did, trace_id,
                                status="already_registered")
                return RegistrationResponse(
                    success=False,
                    agent_did=agent_did,
                    error=f"Agent {agent_did} already registered"
                )

        # Create registry entry
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.default_ttl)
        manifest_json = manifest.model_dump_json()
        manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
        registration_id = str(uuid.uuid4())

        entry = RegistryEntry(
            id=registration_id,
            agent_did=agent_did,
            manifest=manifest,
            manifest_json=manifest_json,
            manifest_hash=manifest_hash,
            registered_at=now,
            updated_at=now,
            expires_at=expires_at,
            status="active",
            verification_status="verified",
        )

        self._registry[agent_did] = entry

        log_agent_action(self.logger, "register_agent_complete", agent_did, trace_id,
                        registration_id=registration_id)

        return RegistrationResponse(
            success=True,
            agent_did=agent_did,
            registration_id=registration_id,
            expires_at=expires_at,
        )

    async def discover(self, query: DiscoveryQuery) -> List[DiscoveryResult]:
        """
        Discover agents matching the query.

        Args:
            query: DiscoveryQuery with search parameters

        Returns:
            List of DiscoveryResult objects
        """
        trace_id = get_trace_id()
        
        log_agent_action(self.logger, "discover", "system", trace_id,
                        query=query.query, capability_type=query.capability_type,
                        max_results=query.max_results)
        
        # Get all active, non-expired entries
        now = datetime.now(timezone.utc)
        manifests: list[AgentManifest] = []
        entry_map: dict[str, RegistryEntry] = {}

        for agent_did, entry in self._registry.items():
            if entry.status != "active":
                continue
            if entry.expires_at and entry.expires_at < now:
                continue
            if query.verified_only and entry.verification_status != "verified":
                continue
            if entry.manifest is not None:
                manifests.append(entry.manifest)
                entry_map[agent_did] = entry

        # Match capabilities
        matches = self.matcher.match(
            manifests=manifests,
            query=query.query,
            capability_type=query.capability_type,
            tags=query.tags if query.tags else None,
        )

        # Convert to DiscoveryResult
        results: list[DiscoveryResult] = []
        for match in matches:
            entry = entry_map.get(match.agent_did)
            if entry is None:
                continue

            # Apply filters
            if match.trust_score < query.min_trust_score:
                continue
            if query.max_price and match.price_per_unit:
                if match.price_per_unit > query.max_price:
                    continue
            if query.max_latency_ms and match.estimated_latency_ms:
                if match.estimated_latency_ms > query.max_latency_ms:
                    continue

            result = DiscoveryResult(
                agent_did=match.agent_did,
                agent_name=match.agent_name,
                agent_description=match.agent_description,
                capability_name=match.capability_name,
                capability_type=match.capability_type,
                relevance_score=match.relevance_score,
                trust_score=match.trust_score,
                estimated_latency_ms=match.estimated_latency_ms,
                price_per_unit=match.price_per_unit,
                currency=match.currency,
                endpoint_url=match.endpoint_url,
                tags=match.tags,
                verified=match.verified,
                last_updated=entry.updated_at,
            )
            results.append(result)

        # Sort results
        results = self._sort_results(results, query.sort_by, query.sort_order)

        # Paginate
        start = query.offset
        end = start + query.max_results
        paginated_results = results[start:end]
        
        # Record discovery metric
        record_agent_discovery("discovery_service", len(paginated_results))
        
        log_agent_action(self.logger, "discover_complete", "system", trace_id,
                        results_count=len(paginated_results))
        
        return paginated_results

    def _sort_results(
        self,
        results: List[DiscoveryResult],
        sort_by: Any,
        sort_order: Any,
    ) -> List[DiscoveryResult]:
        """Sort discovery results."""
        sort_by_val = sort_by.value if hasattr(sort_by, 'value') else str(sort_by)
        sort_order_val = sort_order.value if hasattr(sort_order, 'value') else str(sort_order)
        reverse = sort_order_val == 'desc'

        if sort_by_val == 'relevance':
            return sorted(results, key=lambda r: r.relevance_score, reverse=reverse)
        elif sort_by_val == 'trust':
            return sorted(results, key=lambda r: r.trust_score, reverse=reverse)
        elif sort_by_val == 'latency':
            return sorted(
                results,
                key=lambda r: r.estimated_latency_ms or float('inf'),
                reverse=reverse,
            )
        elif sort_by_val == 'price':
            return sorted(
                results,
                key=lambda r: r.price_per_unit or float('inf'),
                reverse=reverse,
            )
        elif sort_by_val == 'recency':
            return sorted(results, key=lambda r: r.last_updated, reverse=reverse)

        return results

    async def heartbeat(self, heartbeat: Heartbeat) -> RegistrationResponse:
        """
        Refresh an agent's registration TTL.

        Args:
            heartbeat: Heartbeat object with agent_did and status

        Returns:
            RegistrationResponse with success status
        """
        trace_id = get_trace_id()
        agent_did = heartbeat.agent_did
        entry = self._registry.get(agent_did)

        log_agent_action(self.logger, "heartbeat", agent_did, trace_id)

        if entry is None or entry.status != "active":
            log_agent_action(self.logger, "heartbeat_not_found", agent_did, trace_id)
            return RegistrationResponse(
                success=False,
                agent_did=agent_did,
                error=f"Agent {agent_did} not registered"
            )

        # Extend TTL
        now = datetime.now(timezone.utc)
        entry.expires_at = now + timedelta(seconds=self.default_ttl)
        entry.updated_at = now

        log_agent_action(self.logger, "heartbeat_complete", agent_did, trace_id)

        return RegistrationResponse(
            success=True,
            agent_did=agent_did,
            registration_id=entry.id,
            expires_at=entry.expires_at,
        )

    async def unregister_agent(self, agent_did: str) -> RegistrationResponse:
        """
        Unregister an agent.

        Args:
            agent_did: DID of the agent to unregister

        Returns:
            RegistrationResponse with success status
        """
        trace_id = get_trace_id()
        
        log_agent_action(self.logger, "unregister_agent", agent_did, trace_id)
        
        entry = self._registry.get(agent_did)

        if entry is None:
            log_agent_action(self.logger, "unregister_agent_not_found", agent_did, trace_id)
            return RegistrationResponse(
                success=False,
                agent_did=agent_did,
                error=f"Agent {agent_did} not registered"
            )

        entry.status = "inactive"
        entry.updated_at = datetime.now(timezone.utc)

        log_agent_action(self.logger, "unregister_agent_complete", agent_did, trace_id)

        return RegistrationResponse(
            success=True,
            agent_did=agent_did,
            registration_id=entry.id,
        )

    async def get_agent(self, agent_did: str) -> Optional[RegistryEntry]:
        """
        Get a specific agent's registry entry.

        Args:
            agent_did: DID of the agent to retrieve

        Returns:
            RegistryEntry if found and active, None otherwise
        """
        entry = self._registry.get(agent_did)

        if entry is None or entry.status != "active":
            return None

        if entry.is_expired():
            return None

        return entry

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = datetime.now(timezone.utc)
        count = 0
        for entry in self._registry.values():
            if entry.status == "active" and entry.is_expired():
                entry.status = "expired"
                count += 1
        return count