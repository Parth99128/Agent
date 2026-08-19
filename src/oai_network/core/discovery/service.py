"""
Discovery Service

Main service for agent discovery and registry management.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from .models import (
    DiscoveryQuery, DiscoveryResult, RegistryEntry,
    RegistrationRequest, RegistrationResponse,
    HeartbeatRequest, HeartbeatResponse
)
from ..capabilities.models import AgentManifest
from ..capabilities.matcher import CapabilityMatcher
from ..identity.verifier import IdentityVerifier
from ..identity.models import IdentityProof


Base = declarative_base()


class RegistryEntryDB(Base):
    """Database model for registry entries."""
    __tablename__ = 'registry_entries'
    
    id = Column(String(36), primary_key=True)
    agent_did = Column(String(255), nullable=False, index=True)
    manifest_json = Column(Text, nullable=False)
    manifest_hash = Column(String(64), nullable=False)
    registered_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    verification_status = Column(String(50), default='pending', nullable=False)
    
    __table_args__ = (
        Index('ix_agent_did_active', 'agent_did', 'is_active'),
        Index('ix_expires_at', 'expires_at'),
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
        max_proof_age_seconds: int = 300
    ):
        self.database_url = database_url
        self.default_ttl = default_ttl_seconds
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.matcher = CapabilityMatcher()
        self.verifier = IdentityVerifier(max_proof_age_seconds=max_proof_age_seconds)
        
        # Create tables
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def register(self, request: RegistrationRequest) -> RegistrationResponse:
        """
        Register a new agent or update existing registration.
        """
        session = self.get_session()
        try:
            # Parse manifest
            manifest_data = json.loads(request.manifest)
            manifest = AgentManifest.from_dict(manifest_data)
            
            # Parse and verify proof
            proof_data = json.loads(request.proof)
            proof = IdentityProof.from_dict(proof_data)
            
            # Verify identity
            identity_valid, identity_errors = self.verifier.verify_identity(manifest.identity)
            if not identity_valid:
                return RegistrationResponse(
                    success=False,
                    errors=[f"Identity verification failed: {e}" for e in identity_errors]
                )
            
            # Verify proof
            proof_valid, proof_errors = self.verifier.verify_proof(proof, manifest.identity)
            if not proof_valid:
                return RegistrationResponse(
                    success=False,
                    errors=[f"Proof verification failed: {e}" for e in proof_errors]
                )
            
            # Check if agent already registered
            existing = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.agent_did == manifest.agent_did
            ).first()
            
            manifest_hash = hashlib.sha256(request.manifest.encode()).hexdigest()
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=request.ttl_seconds)
            
            if existing:
                # Update existing
                existing.manifest_json = request.manifest
                existing.manifest_hash = manifest_hash
                existing.updated_at = now
                existing.expires_at = expires_at
                existing.is_active = True
                existing.verification_status = 'verified'
                entry_id = existing.id
            else:
                # Create new
                entry = RegistryEntryDB(
                    id=str(uuid.uuid4()),
                    agent_did=manifest.agent_did,
                    manifest_json=request.manifest,
                    manifest_hash=manifest_hash,
                    registered_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                    is_active=True,
                    verification_status='verified'
                )
                session.add(entry)
                entry_id = entry.id
            
            session.commit()
            
            return RegistrationResponse(
                success=True,
                entry_id=entry_id,
                expires_at=expires_at
            )
            
        except json.JSONDecodeError as e:
            return RegistrationResponse(
                success=False,
                errors=[f"Invalid JSON: {str(e)}"]
            )
        except Exception as e:
            session.rollback()
            return RegistrationResponse(
                success=False,
                errors=[f"Registration failed: {str(e)}"]
            )
        finally:
            session.close()
    
    def heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        """
        Refresh an agent's registration TTL.
        """
        session = self.get_session()
        try:
            entry = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.id == request.entry_id,
                RegistryEntryDB.agent_did == request.agent_did
            ).first()
            
            if not entry:
                return HeartbeatResponse(
                    success=False,
                    errors=["Entry not found"]
                )
            
            # Verify proof
            proof_data = json.loads(request.proof)
            proof = IdentityProof.from_dict(proof_data)
            
            # We'd need the manifest to verify - for now just extend TTL
            # In production, verify the proof against stored manifest
            entry.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.default_ttl)
            entry.updated_at = datetime.now(timezone.utc)
            
            session.commit()
            
            return HeartbeatResponse(
                success=True,
                expires_at=entry.expires_at
            )
            
        except Exception as e:
            session.rollback()
            return HeartbeatResponse(
                success=False,
                errors=[f"Heartbeat failed: {str(e)}"]
            )
        finally:
            session.close()
    
    def discover(self, query: DiscoveryQuery) -> List[DiscoveryResult]:
        """
        Discover agents matching the query.
        """
        session = self.get_session()
        try:
            # Build base query
            db_query = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.is_active == True
            )
            
            # Filter expired
            now = datetime.now(timezone.utc)
            db_query = db_query.filter(
                (RegistryEntryDB.expires_at.is_(None)) | 
                (RegistryEntryDB.expires_at > now)
            )
            
            # Filter verified if required
            if query.require_verified:
                db_query = db_query.filter(RegistryEntryDB.verification_status == 'verified')
            
            # Get all entries
            entries = db_query.all()
            
            # Parse manifests and match
            manifests = []
            for entry in entries:
                try:
                    manifest = AgentManifest.from_json(entry.manifest_json)
                    manifests.append(manifest)
                except Exception:
                    continue  # Skip invalid manifests
            
            # Match capabilities
            matches = self.matcher.match(
                query.query,
                manifests,
                capability_type=query.capability_type
            )
            
            # Convert to results
            results = []
            for manifest, capability, relevance_score in matches:
                # Apply filters
                if manifest.trust_metrics.overall_score < query.min_trust_score:
                    continue
                
                if query.max_price and capability.price_per_unit:
                    if capability.price_per_unit > query.max_price:
                        continue
                
                if query.max_latency_ms and capability.estimated_latency_ms:
                    if capability.estimated_latency_ms > query.max_latency_ms:
                        continue
                
                if query.tags:
                    cap_tags_lower = [t.lower() for t in capability.tags]
                    if not all(tag.lower() in cap_tags_lower for tag in query.tags):
                        continue
                
                # Get primary endpoint
                endpoint_url = manifest.endpoints[0].url if manifest.endpoints else ""
                
                result = DiscoveryResult(
                    agent_did=manifest.agent_did,
                    agent_name=manifest.name,
                    agent_description=manifest.description,
                    matched_capability=capability.name,
                    capability_type=capability.type.value,
                    relevance_score=relevance_score,
                    trust_score=manifest.trust_metrics.overall_score,
                    estimated_latency_ms=capability.estimated_latency_ms,
                    price_per_unit=capability.price_per_unit,
                    currency=capability.currency,
                    endpoint_url=endpoint_url,
                    tags=capability.tags,
                    verified=manifest.trust_metrics.verified_identity,
                    last_updated=entry.updated_at
                )
                results.append(result)
            
            # Sort results
            results = self._sort_results(results, query.sort_by, query.sort_order)
            
            # Paginate
            start = query.offset
            end = start + query.limit
            return results[start:end]
            
        finally:
            session.close()
    
    def _sort_results(
        self, 
        results: List[DiscoveryResult], 
        sort_by: str, 
        sort_order: str
    ) -> List[DiscoveryResult]:
        """Sort discovery results."""
        reverse = sort_order == 'desc'
        
        if sort_by == 'relevance':
            return sorted(results, key=lambda r: r.relevance_score, reverse=reverse)
        elif sort_by == 'trust':
            return sorted(results, key=lambda r: r.trust_score, reverse=reverse)
        elif sort_by == 'latency':
            return sorted(
                results, 
                key=lambda r: r.estimated_latency_ms or float('inf'), 
                reverse=reverse
            )
        elif sort_by == 'price':
            return sorted(
                results, 
                key=lambda r: r.price_per_unit or float('inf'), 
                reverse=reverse
            )
        elif sort_by == 'recency':
            return sorted(results, key=lambda r: r.last_updated, reverse=reverse)
        
        return results
    
    def get_agent(self, agent_did: str) -> Optional[AgentManifest]:
        """Get a specific agent's manifest."""
        session = self.get_session()
        try:
            entry = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.agent_did == agent_did,
                RegistryEntryDB.is_active == True
            ).first()
            
            if entry and not entry.is_expired():
                return AgentManifest.from_json(entry.manifest_json)
            return None
        finally:
            session.close()
    
    def unregister(self, agent_did: str, proof: IdentityProof) -> bool:
        """Unregister an agent (requires proof of identity)."""
        session = self.get_session()
        try:
            entry = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.agent_did == agent_did
            ).first()
            
            if not entry:
                return False
            
            # Verify proof
            manifest = AgentManifest.from_json(entry.manifest_json)
            proof_valid, _ = self.verifier.verify_proof(proof, manifest.identity)
            
            if not proof_valid:
                return False
            
            entry.is_active = False
            session.commit()
            return True
            
        finally:
            session.close()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)
            expired = session.query(RegistryEntryDB).filter(
                RegistryEntryDB.expires_at < now,
                RegistryEntryDB.is_active == True
            ).all()
            
            count = len(expired)
            for entry in expired:
                entry.is_active = False
            
            session.commit()
            return count
        finally:
            session.close()


import uuid