"""
Identity Verifier

Verifies agent identities and cryptographic proofs.
"""

from datetime import datetime, timezone
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, padding
from cryptography.exceptions import InvalidSignature

from .models import AgentIdentity, IdentityProof, IdentityDocument, KeyType


class IdentityVerifier:
    """
    Verifies agent identities and cryptographic proofs.
    
    Handles verification of:
    - Identity document structure
    - Proof of possession (signature verification)
    - Key format and validity
    """
    
    def __init__(self, max_proof_age_seconds: int = 300):
        self.max_proof_age_seconds = max_proof_age_seconds
    
    def verify_identity(self, identity: AgentIdentity) -> tuple[bool, list[str]]:
        """
        Verify an agent identity's structure and format.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check DID format
        if not identity.did.startswith('did:'):
            errors.append("DID must start with 'did:'")
        
        # Check public key format
        if not identity.public_key.strip():
            errors.append("Public key cannot be empty")
        
        # Try to load public key to validate format
        try:
            self._load_public_key(identity.public_key, identity.key_type)
        except Exception as e:
            errors.append(f"Invalid public key format: {str(e)}")
        
        # Check key type is supported
        if identity.key_type not in KeyType:
            errors.append(f"Unsupported key type: {identity.key_type}")
        
        return len(errors) == 0, errors
    
    def verify_identity_structure(self, identity: AgentIdentity) -> bool:
        """
        Verify an agent identity's structure.
        
        Returns:
            True if valid, False otherwise
        """
        valid, _ = self.verify_identity(identity)
        return valid
    
    def verify_proof(self, proof: IdentityProof, identity: AgentIdentity) -> tuple[bool, list[str]]:
        """
        Verify a proof of possession against an identity.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check proof matches identity
        if proof.identity_did != identity.did:
            errors.append("Proof DID does not match identity DID")
        
        if proof.key_type != identity.key_type:
            errors.append("Proof key type does not match identity key type")
        
        # Check proof is not expired
        if not proof.is_valid(self.max_proof_age_seconds):
            errors.append("Proof has expired or is too old")
        
        # Verify signature
        try:
            public_key = self._load_public_key(identity.public_key, identity.key_type)
            challenge_bytes = proof.challenge.encode('utf-8')
            signature_bytes = bytes.fromhex(proof.signature)
            
            if identity.key_type == KeyType.ED25519:
                public_key.verify(signature_bytes, challenge_bytes)
            else:  # RSA
                public_key.verify(
                    signature_bytes,
                    challenge_bytes,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
        except InvalidSignature:
            errors.append("Invalid signature")
        except Exception as e:
            errors.append(f"Signature verification failed: {str(e)}")
        
        return len(errors) == 0, errors
    
    def verify_document(self, document: IdentityDocument) -> tuple[bool, list[str]]:
        """
        Verify a complete identity document.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        all_errors = []
        
        # Verify identity
        identity_valid, identity_errors = self.verify_identity(document.identity)
        all_errors.extend(identity_errors)
        
        # Verify proof
        proof_valid, proof_errors = self.verify_proof(document.proof, document.identity)
        all_errors.extend(proof_errors)
        
        return len(all_errors) == 0, all_errors
    
    def _load_public_key(self, public_key_pem: str, key_type: KeyType):
        """Load a public key from PEM format."""
        key_bytes = public_key_pem.encode('utf-8')
        
        if key_type == KeyType.ED25519:
            return serialization.load_pem_public_key(key_bytes)
        elif key_type in (KeyType.RSA_2048, KeyType.RSA_4096):
            return serialization.load_pem_public_key(key_bytes)
        else:
            raise ValueError(f"Unsupported key type: {key_type}")
    
    def extract_public_key_info(self, identity: AgentIdentity) -> dict:
        """Extract information from a public key."""
        public_key = self._load_public_key(identity.public_key, identity.key_type)
        
        info = {
            "key_type": identity.key_type.value,
            "fingerprint": identity.fingerprint(),
        }
        
        if identity.key_type == KeyType.ED25519:
            info["key_size"] = 256
        elif identity.key_type in (KeyType.RSA_2048, KeyType.RSA_4096):
            info["key_size"] = public_key.key_size
        
        return info
    
    def verify_signature(self, message: bytes, signature: bytes, identity_did: str, public_key_pem: str = None, key_type: KeyType = KeyType.ED25519) -> bool:
        """
        Verify a signature against a message and identity.
        
        Args:
            message: The message that was signed
            signature: The signature bytes
            identity_did: The DID of the identity (for logging/context)
            public_key_pem: Optional public key PEM (if not provided, would need to look up from registry)
            key_type: The key type
            
        Returns:
            True if signature is valid, False otherwise
        """
        if public_key_pem is None:
            # In a real implementation, would look up the public key from the registry
            # For now, we can't verify without the public key
            return False
        
        try:
            public_key = self._load_public_key(public_key_pem, key_type)
            
            if key_type == KeyType.ED25519:
                public_key.verify(signature, message)
            else:  # RSA
                public_key.verify(
                    signature,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False