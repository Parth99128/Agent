"""
Registry Service

Service for agent registration, discovery, and health monitoring.
"""

import asyncio
import time
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from .models import (
    RegistryEntry,
    RegistrationRequest,
    RegistrationResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    HealthStatus,
    RegistryConfig,
    DiscoveryQuery,
    DiscoveryResponse,
    DiscoveryAgentResult,
)
from ..core.capabilities.models import AgentManifest


class RegistryService:
    """
    Agent registry service with in-memory backend.

    Features:
    - Agent registration with manifest
    - Heartbeat-based health monitoring
    - Capability-based discovery
    - Automatic stale entry cleanup
    - Registry statistics
    """

    def __init__(self, config: Optional[RegistryConfig] = None):
        self.config = config or RegistryConfig()
        # In-memory registry: agent_did -> RegistryEntry
        self._registry: Dict[str, RegistryEntry] = {}
        self._running = False

    async def start(self):
        """Start background tasks."""
        self._running = True

    async def stop(self):
        """Stop background tasks."""
        self._running = False

    async def register_agent(self, manifest: Any) -> RegistrationResponse:
        """
        Register a new agent.

        Args:
            manifest: AgentManifest object (or JSON string)

        Returns:
            RegistrationResponse with success status
        """
        # Parse manifest if it's a string
        if isinstance(manifest, str):
            manifest = AgentManifest.model_validate_json(manifest)
        elif isinstance(manifest, dict):
            manifest = AgentManifest.model_validate(manifest)

        agent_did = manifest.identity.did

        # Check if agent already registered
        if agent_did in self._registry:
            existing = self._registry[agent_did]
            if existing.status == "active":
                return RegistrationResponse(
                    success=False,
                    agent_did=agent_did,
                    error=f"Agent {agent_did} already registered"
                )

        # Create registry entry
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.config.default_ttl_seconds)
        registration_id = str(uuid.uuid4())
        manifest_json = manifest.model_dump_json()

        # Extract capability names
        cap_names = [cap.name for cap in manifest.capabilities]
        cap_details = {cap.name: cap.model_dump(mode='json') for cap in manifest.capabilities}
        endpoint_urls = [ep.url for ep in manifest.endpoints]

        entry = RegistryEntry(
            id=registration_id,
            agent_did=agent_did,
            name=manifest.name,
            description=manifest.description,
            version=manifest.version,
            manifest=manifest,
            manifest_json=manifest_json,
            endpoints=endpoint_urls,
            capabilities=cap_names,
            capability_details=cap_details,
            identity_verified=True,
            trust_score=manifest.trust_metrics.score,
            status="active",
            health_status=HealthStatus.HEALTHY,
            last_heartbeat=now,
            missed_heartbeats=0,
            registered_at=now,
            updated_at=now,
            expires_at=expires_at,
            tags=manifest.tags if hasattr(manifest, 'tags') else [],
        )

        self._registry[agent_did] = entry

        return RegistrationResponse(
            success=True,
            agent_did=agent_did,
            registration_id=registration_id,
            expires_at=expires_at,
        )

    async def get_agent(self, agent_did: str) -> Optional[RegistryEntry]:
        """
        Get a registry entry by agent DID.

        Args:
            agent_did: DID of the agent

        Returns:
            RegistryEntry if found and active, None otherwise
        """
        entry = self._registry.get(agent_did)
        if entry is None:
            return None
        if entry.status in ("inactive", "expired"):
            return None
        if entry.is_expired():
            return None
        return entry

    async def heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        """
        Process agent heartbeat.

        Args:
            request: HeartbeatRequest with agent_did and status

        Returns:
            HeartbeatResponse with success status
        """
        agent_did = request.agent_did
        entry = self._registry.get(agent_did)

        if entry is None or entry.status != "active":
            return HeartbeatResponse(
                success=False,
                agent_did=agent_did,
                error=f"Agent {agent_did} not registered"
            )

        # Update heartbeat
        now = datetime.now(timezone.utc)
        entry.last_heartbeat = now
        entry.updated_at = now
        entry.missed_heartbeats = 0
        entry.health_status = request.status
        # Map health status to entry status
        if request.status == HealthStatus.HEALTHY:
            entry.status = "active"
        else:
            entry.status = request.status.value  # "degraded", "unhealthy"
        if request.metadata:
            entry.metadata.update(request.metadata)

        # Extend TTL
        entry.expires_at = now + timedelta(seconds=self.config.default_ttl_seconds)

        return HeartbeatResponse(
            success=True,
            agent_did=agent_did,
            next_heartbeat_interval=self.config.heartbeat_interval_seconds,
        )

    async def unregister_agent(self, agent_did: str) -> RegistrationResponse:
        """
        Unregister an agent.

        Args:
            agent_did: DID of the agent to unregister

        Returns:
            RegistrationResponse with success status
        """
        entry = self._registry.get(agent_did)

        if entry is None:
            return RegistrationResponse(
                success=False,
                agent_did=agent_did,
                error=f"Agent {agent_did} not found"
            )

        # Remove from registry
        del self._registry[agent_did]

        return RegistrationResponse(
            success=True,
            agent_did=agent_did,
            registration_id=entry.id,
        )

    async def list_agents(
        self,
        status: Optional[HealthStatus] = None,
    ) -> List[RegistryEntry]:
        """
        List all registered agents, optionally filtered by status.

        Args:
            status: Optional HealthStatus filter

        Returns:
            List of RegistryEntry objects
        """
        results = []
        for entry in self._registry.values():
            if entry.status in ("inactive", "expired"):
                continue
            if entry.is_expired():
                continue
            if status is not None:
                if entry.health_status != status:
                    continue
            results.append(entry)
        return results

    async def discover_agents(
        self,
        query: Optional[DiscoveryQuery] = None,
        capability: Optional[str] = None,
        max_results: int = 10,
        min_trust_score: float = 0.0,
        verified_only: bool = False,
        tags: Optional[list[str]] = None,
        nl_query: Optional[str] = None,
    ) -> list[DiscoveryAgentResult]:
        """
        Discover agents by capability or natural language query.

        Args:
            query: DiscoveryQuery with capability and filters (new style)
            capability: Capability name to search for (legacy style)
            max_results: Maximum number of results
            min_trust_score: Minimum trust score
            verified_only: Only return verified agents
            tags: Filter by tags
            nl_query: Natural language query for semantic matching

        Returns:
            List of DiscoveryAgentResult objects sorted by relevance
        """
        # Support both new DiscoveryQuery object and legacy keyword arguments
        if query is not None:
            capability = query.capability
            max_results = query.max_results
            min_trust_score = query.min_trust_score
            verified_only = query.verified_only
            tags = query.tags
        
        results = []
        for entry in self._registry.values():
            if entry.status in ("inactive", "expired"):
                continue
            if entry.is_expired():
                continue
            if entry.trust_score < min_trust_score:
                continue
            if verified_only and not entry.identity_verified:
                continue
            if tags and not any(tag in entry.tags for tag in tags):
                continue
            
            # If natural language query provided, use semantic matching
            best_match_score = 0.0
            best_capability = capability
            
            if nl_query and entry.manifest:
                # Use capability's matches_query method for semantic matching
                for cap in entry.manifest.capabilities:
                    score = cap.matches_query(nl_query)
                    if score > best_match_score:
                        best_match_score = score
                        best_capability = cap.name
            
            # If no NL query, require exact capability match
            if not nl_query and capability:
                if capability not in entry.capabilities:
                    continue
                best_match_score = 1.0
                best_capability = capability
            elif not nl_query and not capability:
                # No filter - return all
                best_match_score = 1.0
                best_capability = entry.capabilities[0] if entry.capabilities else ""
            
            if best_match_score > 0:
                results.append(DiscoveryAgentResult(
                    agent_did=entry.agent_did,
                    agent_name=entry.name,
                    agent_description=entry.description,
                    capability_name=best_capability,
                    trust_score=entry.trust_score,
                    verified=entry.identity_verified,
                    capabilities=entry.capabilities,
                    endpoints=entry.endpoints,
                    tags=entry.tags,
                    relevance_score=best_match_score,
                ))
        
        # Sort by relevance score (descending) then trust score (descending)
        results.sort(key=lambda r: (r.relevance_score, r.trust_score), reverse=True)
        
        return results[:max_results]
        return results

    async def cleanup_expired(self) -> int:
        """
        Clean up expired and stale entries.

        Returns:
            Number of entries cleaned up
        """
        now = datetime.now(timezone.utc)
        removed = []
        for agent_did, entry in self._registry.items():
            # Check TTL expiration
            if entry.expires_at and entry.expires_at < now:
                removed.append(agent_did)
            # Check stale heartbeats
            elif entry.missed_heartbeats >= self.config.max_heartbeat_missed:
                removed.append(agent_did)
            # Check stale by time
            elif entry.last_heartbeat:
                heartbeat_age = (now - entry.last_heartbeat).total_seconds()
                expected_interval = self.config.heartbeat_interval_seconds * self.config.max_heartbeat_missed
                if heartbeat_age > expected_interval:
                    removed.append(agent_did)

        for agent_did in removed:
            del self._registry[agent_did]

        return len(removed)

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dict with total_agents, active_agents, healthy_agents, degraded_agents, unhealthy_agents
        """
        total = len(self._registry)
        active = 0
        healthy = 0
        degraded = 0
        unhealthy = 0

        for entry in self._registry.values():
            if entry.status not in ("inactive", "expired") and not entry.is_expired():
                active += 1
                if entry.health_status == HealthStatus.HEALTHY:
                    healthy += 1
                elif entry.health_status == HealthStatus.DEGRADED:
                    degraded += 1
                elif entry.health_status == HealthStatus.UNHEALTHY:
                    unhealthy += 1

        return {
            "total_agents": total,
            "active_agents": active,
            "healthy_agents": healthy,
            "degraded_agents": degraded,
            "unhealthy_agents": unhealthy,
        }

    async def update_trust_score(self, agent_did: str, trust_score: float) -> bool:
        """Update an agent's trust score."""
        entry = self._registry.get(agent_did)
        if entry is None:
            return False
        entry.trust_score = max(0.0, min(1.0, trust_score))
        entry.updated_at = datetime.now(timezone.utc)
        return True

    async def update_status(self, agent_did: str, status: HealthStatus) -> bool:
        """Update an agent's health status."""
        entry = self._registry.get(agent_did)
        if entry is None:
            return False
        entry.health_status = status
        entry.status = status.value
        entry.updated_at = datetime.now(timezone.utc)
        return True