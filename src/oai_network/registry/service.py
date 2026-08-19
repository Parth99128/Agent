"""
Registry Service

Service for agent registration, discovery, and health monitoring.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, Boolean, Integer, JSON, select, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from .models import (
    RegistryEntry,
    RegistrationRequest,
    RegistrationResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    HealthStatus,
    RegistryConfig,
)
from ..core.identity.verifier import IdentityVerifier
from ..core.capabilities.validator import ManifestValidator
from ..core.capabilities.models import AgentManifest, Capability


Base = declarative_base()


class RegistryEntryDB(Base):
    """Database model for registry entries."""
    __tablename__ = 'registry_entries'
    
    id = Column(String(36), primary_key=True)
    agent_did = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    version = Column(String(50), default="1.0.0")
    endpoints = Column(JSON, default=list)
    protocols = Column(JSON, default=list)
    capabilities = Column(JSON, default=list)
    capability_details = Column(JSON, default=dict)
    identity_verified = Column(Boolean, default=False)
    trust_score = Column(Float, default=0.0)
    public_key = Column(Text, nullable=True)
    status = Column(String(20), default=HealthStatus.UNKNOWN.value)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    registered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    entry_metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)


class RegistryService:
    """
    Agent registry service with SQLite backend.
    
    Features:
    - Agent registration with identity verification
    - Heartbeat-based health monitoring
    - Capability-based discovery
    - Automatic stale entry cleanup
    - Rate limiting
    """
    
    def __init__(self, config: Optional[RegistryConfig] = None):
        self.config = config or RegistryConfig()
        self.engine = create_engine(self.config.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.identity_verifier = IdentityVerifier()
        self.manifest_validator = ManifestValidator()
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Rate limiting
        self._registration_counts: Dict[str, List[float]] = {}
        self._heartbeat_counts: Dict[str, List[float]] = {}
    
    async def start(self):
        """Start background tasks."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.config.health_check_enabled:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop(self):
        """Stop background tasks."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
    
    def _get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def _check_registration_rate_limit(self, client_ip: str) -> bool:
        """Check registration rate limit."""
        now = time.time()
        if client_ip not in self._registration_counts:
            self._registration_counts[client_ip] = []
        
        # Clean old entries
        self._registration_counts[client_ip] = [
            t for t in self._registration_counts[client_ip] if now - t < 60
        ]
        
        if len(self._registration_counts[client_ip]) >= self.config.registration_rate_limit_per_minute:
            return False
        
        self._registration_counts[client_ip].append(now)
        return True
    
    def _check_heartbeat_rate_limit(self, agent_did: str) -> bool:
        """Check heartbeat rate limit."""
        now = time.time()
        if agent_did not in self._heartbeat_counts:
            self._heartbeat_counts[agent_did] = []
        
        # Clean old entries
        self._heartbeat_counts[agent_did] = [
            t for t in self._heartbeat_counts[agent_did] if now - t < 60
        ]
        
        if len(self._heartbeat_counts[agent_did]) >= self.config.heartbeat_rate_limit_per_minute:
            return False
        
        self._heartbeat_counts[agent_did].append(now)
        return True
    
    async def register(self, request: RegistrationRequest, client_ip: str = "unknown") -> RegistrationResponse:
        """Register a new agent."""
        # Check rate limit
        if not self._check_registration_rate_limit(client_ip):
            return RegistrationResponse(
                success=False,
                message="Registration rate limit exceeded",
            )
        
        # Verify identity if required
        identity_verified = False
        if self.config.require_identity_proof and request.identity_proof:
            # In real implementation, would verify the proof
            # For now, just check if we can verify
            identity_verified = True
        elif self.config.auto_verify_identity:
            identity_verified = True
        
        # Validate capabilities if provided
        capability_details = request.capability_details
        if capability_details:
            # Would validate against capability schemas
            pass
        
        # Check max entries
        session = self._get_session()
        try:
            count = session.query(func.count(RegistryEntryDB.id)).scalar()
            if count >= self.config.max_entries:
                return RegistrationResponse(
                    success=False,
                    message="Registry is full",
                )
            
            # Create entry
            entry = RegistryEntry(
                agent_did=request.agent_did,
                name=request.name,
                description=request.description,
                version=request.version,
                endpoints=request.endpoints[:self.config.max_endpoints_per_agent],
                protocols=request.protocols,
                capabilities=request.capabilities[:self.config.max_capabilities_per_agent],
                capability_details=capability_details,
                identity_verified=identity_verified,
                public_key=request.public_key,
                metadata=request.metadata,
                tags=request.tags,
            )
            
            # Save to database
            db_entry = RegistryEntryDB(
                id=entry.id,
                agent_did=entry.agent_did,
                name=entry.name,
                description=entry.description,
                version=entry.version,
                endpoints=entry.endpoints,
                protocols=entry.protocols,
                capabilities=entry.capabilities,
                capability_details=entry.capability_details,
                identity_verified=entry.identity_verified,
                trust_score=entry.trust_score,
                public_key=entry.public_key,
                status=entry.status.value,
                metadata=entry.metadata,
                tags=entry.tags,
            )
            
            session.add(db_entry)
            session.commit()
            
            return RegistrationResponse(
                success=True,
                entry_id=entry.id,
                agent_did=entry.agent_did,
                message="Registration successful",
            )
            
        except IntegrityError:
            session.rollback()
            return RegistrationResponse(
                success=False,
                message=f"Agent with DID {request.agent_did} already registered",
            )
        except Exception as e:
            session.rollback()
            return RegistrationResponse(
                success=False,
                message=f"Registration failed: {str(e)}",
            )
        finally:
            session.close()
    
    async def heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        """Process agent heartbeat."""
        # Check rate limit
        if not self._check_heartbeat_rate_limit(request.agent_did):
            return HeartbeatResponse(
                success=False,
                message="Heartbeat rate limit exceeded",
            )
        
        session = self._get_session()
        try:
            # Find entry
            query = select(RegistryEntryDB).where(RegistryEntryDB.agent_did == request.agent_did)
            if request.entry_id:
                query = query.where(RegistryEntryDB.id == request.entry_id)
            
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return HeartbeatResponse(
                    success=False,
                    message="Agent not found",
                )
            
            # Update entry
            db_entry.last_heartbeat = datetime.now(timezone.utc)
            db_entry.status = request.status.value
            db_entry.updated_at = datetime.now(timezone.utc)
            if request.metadata:
                db_entry.metadata.update(request.metadata)
            
            session.commit()
            
            return HeartbeatResponse(
                success=True,
                entry_id=db_entry.id,
                message="Heartbeat accepted",
                next_heartbeat_seconds=self.config.heartbeat_ttl_seconds,
            )
            
        except Exception as e:
            session.rollback()
            return HeartbeatResponse(
                success=False,
                message=f"Heartbeat failed: {str(e)}",
            )
        finally:
            session.close()
    
    async def unregister(self, agent_did: str) -> bool:
        """Unregister an agent."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(RegistryEntryDB.agent_did == agent_did)
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return False
            
            session.delete(db_entry)
            session.commit()
            return True
            
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    
    async def get_entry(self, agent_did: str) -> Optional[RegistryEntry]:
        """Get a registry entry by agent DID."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(RegistryEntryDB.agent_did == agent_did)
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return None
            
            return self._db_to_entry(db_entry)
        finally:
            session.close()
    
    async def get_entry_by_id(self, entry_id: str) -> Optional[RegistryEntry]:
        """Get a registry entry by ID."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(RegistryEntryDB.id == entry_id)
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return None
            
            return self._db_to_entry(db_entry)
        finally:
            session.close()
    
    async def list_entries(
        self,
        status: Optional[HealthStatus] = None,
        capability: Optional[str] = None,
        protocol: Optional[str] = None,
        verified_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RegistryEntry]:
        """List registry entries with filters."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB)
            
            if status:
                query = query.where(RegistryEntryDB.status == status.value)
            if capability:
                query = query.where(RegistryEntryDB.capabilities.contains([capability]))
            if protocol:
                query = query.where(RegistryEntryDB.protocols.contains([protocol]))
            if verified_only:
                query = query.where(RegistryEntryDB.identity_verified == True)
            
            query = query.order_by(RegistryEntryDB.updated_at.desc()).limit(limit).offset(offset)
            
            db_entries = session.execute(query).scalars().all()
            return [self._db_to_entry(e) for e in db_entries]
        finally:
            session.close()
    
    async def search(
        self,
        query: str,
        limit: int = 50,
    ) -> List[RegistryEntry]:
        """Search registry entries by name, description, or tags."""
        session = self._get_session()
        try:
            search_term = f"%{query}%"
            db_query = select(RegistryEntryDB).where(
                (RegistryEntryDB.name.ilike(search_term)) |
                (RegistryEntryDB.description.ilike(search_term)) |
                (RegistryEntryDB.tags.contains([query]))
            ).limit(limit)
            
            db_entries = session.execute(db_query).scalars().all()
            return [self._db_to_entry(e) for e in db_entries]
        finally:
            session.close()
    
    async def update_trust_score(self, agent_did: str, trust_score: float) -> bool:
        """Update an agent's trust score."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(RegistryEntryDB.agent_did == agent_did)
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return False
            
            db_entry.trust_score = max(0.0, min(1.0, trust_score))
            db_entry.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
            
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    
    async def update_status(self, agent_did: str, status: HealthStatus) -> bool:
        """Update an agent's health status."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(RegistryEntryDB.agent_did == agent_did)
            db_entry = session.execute(query).scalar_one_or_none()
            
            if not db_entry:
                return False
            
            db_entry.status = status.value
            db_entry.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
            
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    
    def _db_to_entry(self, db_entry: RegistryEntryDB) -> RegistryEntry:
        """Convert database model to domain model."""
        return RegistryEntry(
            id=db_entry.id,
            agent_did=db_entry.agent_did,
            name=db_entry.name,
            description=db_entry.description,
            version=db_entry.version,
            endpoints=db_entry.endpoints or [],
            protocols=db_entry.protocols or [],
            capabilities=db_entry.capabilities or [],
            capability_details=db_entry.capability_details or {},
            identity_verified=db_entry.identity_verified,
            trust_score=db_entry.trust_score,
            public_key=db_entry.public_key,
            status=HealthStatus(db_entry.status),
            last_heartbeat=db_entry.last_heartbeat,
            registered_at=db_entry.registered_at,
            updated_at=db_entry.updated_at,
            metadata=db_entry.metadata or {},
            tags=db_entry.tags or [],
        )
    
    async def _cleanup_loop(self):
        """Background task to clean up stale entries."""
        while self._running:
            try:
                await asyncio.sleep(self.config.stale_cleanup_interval_seconds)
                await self._cleanup_stale_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Cleanup error: {e}")
    
    async def _cleanup_stale_entries(self):
        """Remove stale entries."""
        session = self._get_session()
        try:
            # Find stale entries
            cutoff = datetime.now(timezone.utc).timestamp() - self.config.heartbeat_ttl_seconds
            # Note: This is simplified - in reality would use proper datetime comparison
            query = select(RegistryEntryDB).where(
                RegistryEntryDB.last_heartbeat.isnot(None)
            )
            db_entries = session.execute(query).scalars().all()
            
            removed = 0
            for db_entry in db_entries:
                if db_entry.last_heartbeat:
                    age = (datetime.now(timezone.utc) - db_entry.last_heartbeat).total_seconds()
                    if age > self.config.heartbeat_ttl_seconds:
                        session.delete(db_entry)
                        removed += 1
            
            if removed > 0:
                session.commit()
                print(f"Cleaned up {removed} stale registry entries")
                
        except Exception as e:
            session.rollback()
            print(f"Cleanup failed: {e}")
        finally:
            session.close()
    
    async def _health_check_loop(self):
        """Background task for active health checks."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)
                await self._run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Health check error: {e}")
    
    async def _run_health_checks(self):
        """Run health checks on all registered agents."""
        session = self._get_session()
        try:
            query = select(RegistryEntryDB).where(
                RegistryEntryDB.status != HealthStatus.UNHEALTHY.value
            )
            db_entries = session.execute(query).scalars().all()
            
            for db_entry in db_entries:
                # In real implementation, would make HTTP request to health endpoint
                # For now, just check if heartbeat is recent
                if db_entry.last_heartbeat:
                    age = (datetime.now(timezone.utc) - db_entry.last_heartbeat).total_seconds()
                    if age > self.config.heartbeat_ttl_seconds * 2:
                        db_entry.status = HealthStatus.UNHEALTHY.value
                    elif age > self.config.heartbeat_ttl_seconds:
                        db_entry.status = HealthStatus.DEGRADED.value
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            print(f"Health checks failed: {e}")
        finally:
            session.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        session = self._get_session()
        try:
            total = session.query(func.count(RegistryEntryDB.id)).scalar()
            healthy = session.query(func.count(RegistryEntryDB.id)).filter(
                RegistryEntryDB.status == HealthStatus.HEALTHY.value
            ).scalar()
            verified = session.query(func.count(RegistryEntryDB.id)).filter(
                RegistryEntryDB.identity_verified == True
            ).scalar()
            
            return {
                "total_entries": total,
                "healthy_entries": healthy,
                "verified_entries": verified,
                "stale_entries": total - healthy,
            }
        finally:
            session.close()