"""
Identity Generator

Generates new agent identities with cryptographic key pairs.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .models import AgentIdentity, IdentityProof, IdentityDocument, KeyType


class IdentityGenerator:
    """
    Generates new agent identities with cryptographic key pairs.
    
    Supports multiple key types:
    - Ed25519 (recommended): Fast, small keys, modern
    - RSA-2048: Compatible with legacy systems
    - RSA-4096: Higher security, larger keys
    """
    
    def __init__(self, key_type: KeyType = KeyType.ED25519):
        self.key_type = key_type
    
    def generate_private_key(self):
        """Generate a new private key based on the configured key type."""
        if self.key_type == KeyType.ED25519:
            return ed25519.Ed25519PrivateKey.generate()
        elif self.key_type == KeyType.RSA_2048:
            return rsa.generate_private_key(public_exponent=65537, key_size=2048)
        elif self.key_type == KeyType.RSA_4096:
            return rsa.generate_private_key(public_exponent=65537, key_size=4096)
        else:
            raise ValueError(f"Unsupported key type: {self.key_type}")
    
    def private_key_to_pem(self, private_key) -> str:
        """Serialize private key to PEM format."""
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
    
    def public_key_to_pem(self, private_key) -> str:
        """Extract and serialize public key to PEM format."""
        public_key = private_key.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def generate_did(self, public_key_pem: str) -> str:
        """Generate a DID from the public key."""
        # Simple DID generation using key fingerprint
        import hashlib
        key_hash = hashlib.sha256(public_key_pem.encode('utf-8')).hexdigest()[:32]
        return f"did:oai:{key_hash}"
    
    def create_identity(self, metadata: Optional[dict] = None) -> tuple[AgentIdentity, str]:
        """
        Create a new agent identity with key pair.
        
        Returns:
            Tuple of (AgentIdentity, private_key_pem)
        """
        private_key = self.generate_private_key()
        private_key_pem = self.private_key_to_pem(private_key)
        public_key_pem = self.public_key_to_pem(private_key)
        did = self.generate_did(public_key_pem)
        
        identity = AgentIdentity(
            did=did,
            public_key=public_key_pem,
            key_type=self.key_type,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        return identity, private_key_pem
    
    def generate_identity(self, name: str, key_type: str = "Ed25519", metadata: Optional[dict] = None) -> IdentityDocument:
        """
        Generate a new agent identity with key pair.
        
        Args:
            name: Agent name (added to metadata)
            key_type: Key type string (Ed25519, RSA_2048, RSA_4096)
            metadata: Additional metadata
            
        Returns:
            IdentityDocument with identity and proof
        """
        # Update key type if provided
        if key_type:
            key_type_map = {
                "Ed25519": KeyType.ED25519,
                "RSA_2048": KeyType.RSA_2048,
                "RSA_4096": KeyType.RSA_4096,
            }
            if key_type in key_type_map:
                self.key_type = key_type_map[key_type]
        
        # Add name to metadata
        meta = metadata or {}
        meta["name"] = name
        
        identity_doc, _ = self.create_identity_document(meta)
        return identity_doc
    
    def create_identity_document(
        self, 
        metadata: Optional[dict] = None,
        challenge: Optional[str] = None
    ) -> tuple[IdentityDocument, str]:
        """
        Create a complete identity document with proof of possession.
        
        Returns:
            Tuple of (IdentityDocument, private_key_pem)
        """
        identity, private_key_pem = self.create_identity(metadata)
        
        # Generate proof of possession
        if challenge is None:
            challenge = secrets.token_hex(32)
        
        proof = self.create_proof(identity, challenge, private_key_pem)
        
        document = IdentityDocument(
            identity=identity,
            proof=proof,
            verified=False
        )
        
        return document, private_key_pem
    
    def create_proof(
        self, 
        identity: AgentIdentity, 
        challenge: str, 
        private_key_pem: str
    ) -> IdentityProof:
        """Create a proof of possession for the given identity."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        private_key = load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
        
        # Sign the challenge
        if self.key_type == KeyType.ED25519:
            signature = private_key.sign(challenge.encode('utf-8'))
        else:  # RSA
            signature = private_key.sign(
                challenge.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        
        return IdentityProof(
            identity_did=identity.did,
            challenge=challenge,
            signature=signature.hex(),
            key_type=self.key_type,
            timestamp=datetime.now(timezone.utc)
        )