"""
Identity Models

Data models for agent identity and cryptographic proofs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import hashlib
import json


class KeyType(str, Enum):
    """Supported key types for agent identity."""
    ED25519 = "ed25519"
    SECP256K1 = "secp256k1"
    RSA_2048 = "rsa-2048"
    RSA_4096 = "rsa-4096"


class AgentIdentity(BaseModel):
    """
    Represents an agent's identity in the network.
    
    An agent identity consists of:
    - A unique identifier (DID-like)
    - Public key for verification
    - Key type
    - Creation timestamp
    - Optional metadata
    """
    did: str = Field(..., description="Decentralized identifier for the agent")
    public_key: str = Field(..., description="Public key in PEM or multicodec format")
    key_type: KeyType = Field(..., description="Type of cryptographic key")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this identity was created")
    metadata: dict = Field(default_factory=dict, description="Additional metadata about the agent")
    
    @field_validator('did')
    @classmethod
    def validate_did(cls, v: str) -> str:
        if not v.startswith('did:'):
            raise ValueError('DID must start with "did:"')
        return v
    
    def fingerprint(self) -> str:
        """Generate a short fingerprint of the public key."""
        key_bytes = self.public_key.encode('utf-8')
        return hashlib.sha256(key_bytes).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentIdentity':
        """Create from dictionary."""
        return cls(**data)


class IdentityProof(BaseModel):
    """
    Cryptographic proof that an agent controls their private key.
    
    This is used during registration and authentication to prove
    ownership of the identity without revealing the private key.
    """
    identity_did: str = Field(..., description="DID of the identity being proven")
    challenge: str = Field(..., description="Random challenge from verifier")
    signature: str = Field(..., description="Signature of challenge with private key")
    key_type: KeyType = Field(..., description="Type of key used for signing")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When proof was created")
    expires_at: Optional[datetime] = Field(None, description="When proof expires")
    
    def is_valid(self, max_age_seconds: int = 300) -> bool:
        """Check if proof is still valid (not expired)."""
        now = datetime.now(timezone.utc)
        if self.expires_at and now > self.expires_at:
            return False
        age = (now - self.timestamp).total_seconds()
        return age <= max_age_seconds
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IdentityProof':
        """Create from dictionary."""
        return cls(**data)


class IdentityDocument(BaseModel):
    """
    Complete identity document combining identity and proof.
    
    This is what gets stored in the registry and shared with other agents.
    """
    identity: AgentIdentity
    proof: IdentityProof
    verified: bool = Field(default=False, description="Whether identity has been verified")
    verified_at: Optional[datetime] = Field(None, description="When identity was last verified")
    document_id: str = Field(default_factory=lambda: f"doc-{datetime.now(timezone.utc).timestamp()}", description="Unique document identifier")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IdentityDocument':
        """Create from dictionary."""
        return cls(**data)