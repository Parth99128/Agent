"""
Tests for the identity module.
"""

import pytest
from oai_network.core.identity.models import AgentIdentity, IdentityProof, IdentityDocument, KeyType
from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.verifier import IdentityVerifier


class TestIdentityModels:
    """Tests for identity data models."""
    
    def test_agent_identity_creation(self):
        """Test creating an AgentIdentity."""
        identity = AgentIdentity(
            did="did:oai:test123",
            public_key="test-public-key",
            key_type=KeyType.ED25519,
            metadata={"name": "Test Agent"}
        )
        
        assert identity.did == "did:oai:test123"
        assert identity.key_type == KeyType.ED25519
        assert identity.metadata["name"] == "Test Agent"
        assert identity.public_key == "test-public-key"
    
    def test_identity_proof_creation(self):
        """Test creating an IdentityProof."""
        proof = IdentityProof(
            challenge="test-challenge",
            signature="test-signature",
            identity_did="did:oai:test123",
            key_type=KeyType.ED25519
        )
        
        assert proof.challenge == "test-challenge"
        assert proof.signature == "test-signature"
        assert proof.identity_did == "did:oai:test123"
    
    def test_identity_document_creation(self, sample_identity):
        """Test creating an IdentityDocument."""
        assert isinstance(sample_identity, IdentityDocument)
        assert sample_identity.identity.did.startswith("did:oai:")
        assert sample_identity.proof.challenge
        assert sample_identity.document_id


class TestIdentityGenerator:
    """Tests for IdentityGenerator."""
    
    def test_generate_ed25519_identity(self, identity_generator):
        """Test generating Ed25519 identity."""
        identity_doc, _ = identity_generator.create_identity_document(
            metadata={"name": "Test Agent"}
        )
        
        assert identity_doc.identity.key_type == KeyType.ED25519
        assert identity_doc.identity.did.startswith("did:oai:")
        assert identity_doc.identity.metadata["name"] == "Test Agent"
        assert identity_doc.proof.challenge
        assert identity_doc.proof.signature
        assert identity_doc.proof.identity_did == identity_doc.identity.did
    
    def test_generate_rsa_identity(self):
        """Test generating RSA identity."""
        generator = IdentityGenerator(key_type=KeyType.RSA_2048)
        identity_doc, _ = generator.create_identity_document(
            metadata={"name": "RSA Agent"}
        )
        
        assert identity_doc.identity.key_type == KeyType.RSA_2048
        assert identity_doc.identity.did.startswith("did:oai:")
    
    def test_generate_key_pair_ed25519(self, identity_generator):
        """Test Ed25519 key pair generation."""
        private_key = identity_generator.generate_private_key()
        private_key_pem = identity_generator.private_key_to_pem(private_key)
        public_key_pem = identity_generator.public_key_to_pem(private_key)
        
        assert private_key_pem is not None
        assert public_key_pem is not None
        assert len(public_key_pem) > 0
    
    def test_generate_key_pair_rsa(self):
        """Test RSA key pair generation."""
        generator = IdentityGenerator(key_type=KeyType.RSA_2048)
        private_key = generator.generate_private_key()
        private_key_pem = generator.private_key_to_pem(private_key)
        public_key_pem = generator.public_key_to_pem(private_key)
        
        assert private_key_pem is not None
        assert public_key_pem is not None
        assert len(public_key_pem) > 0
    
    def test_create_did(self, identity_generator):
        """Test DID creation."""
        public_key = "test-public-key"
        did = identity_generator.generate_did(public_key)
        
        assert did.startswith("did:oai:")
        assert len(did) > 10
    
    def test_sign_and_verify_challenge(self, identity_generator):
        """Test signing and verifying a challenge."""
        challenge = "test-challenge"
        
        # Create a fresh identity with private key
        identity, private_key_pem = identity_generator.create_identity()
        proof = identity_generator.create_proof(identity, challenge, private_key_pem)
        
        assert proof.signature
        
        # Verify using verifier
        verifier = IdentityVerifier()
        is_valid, errors = verifier.verify_proof(proof, identity)
        
        assert is_valid is True
    
    def test_invalid_signature_verification(self, identity_generator):
        """Test that invalid signatures fail verification."""
        identity, private_key_pem = identity_generator.create_identity()
        challenge = "test-challenge"
        proof = identity_generator.create_proof(identity, challenge, private_key_pem)
        
        verifier = IdentityVerifier()
        is_valid, errors = verifier.verify_proof(proof, identity)
        
        assert is_valid is True
        
        # Now test with wrong challenge
        bad_proof = IdentityProof(
            identity_did=identity.did,
            challenge="wrong-challenge",
            signature=proof.signature,
            key_type=identity.key_type
        )
        
        is_valid, errors = verifier.verify_proof(bad_proof, identity)
        
        assert is_valid is False


class TestIdentityVerifier:
    """Tests for IdentityVerifier."""
    
    def test_verify_identity_structure_valid(self, sample_identity):
        """Test verifying valid identity structure."""
        verifier = IdentityVerifier()
        is_valid, errors = verifier.verify_identity(sample_identity.identity)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_verify_identity_structure_invalid_did(self):
        """Test verifying identity with invalid DID."""
        verifier = IdentityVerifier()
        
        # Create a valid identity with a proper public key
        generator = IdentityGenerator(key_type=KeyType.ED25519)
        identity, _ = generator.create_identity()
        
        # Test with valid identity
        is_valid, errors = verifier.verify_identity(identity)
        assert is_valid is True
        
        # Test with invalid DID by creating a mock object to bypass Pydantic validation
        from pydantic import BaseModel
        invalid_identity = AgentIdentity.model_construct(
            did="invalid-did",
            public_key=identity.public_key,
            key_type=KeyType.ED25519
        )
        
        is_valid, errors = verifier.verify_identity(invalid_identity)
        
        assert is_valid is False
        assert any("DID" in e for e in errors)
        
        assert is_valid is False
        assert any("DID" in e for e in errors)
    
    def test_verify_identity_structure_missing_key(self):
        """Test verifying identity with missing public key."""
        verifier = IdentityVerifier()
        identity = AgentIdentity(
            did="did:oai:test123",
            public_key="",
            key_type=KeyType.ED25519
        )
        
        is_valid, errors = verifier.verify_identity(identity)
        
        assert is_valid is False
        assert any("public key" in e.lower() for e in errors)
    
    def test_verify_proof_valid(self, sample_identity):
        """Test verifying a valid proof."""
        verifier = IdentityVerifier()
        is_valid, errors = verifier.verify_proof(sample_identity.proof, sample_identity.identity)
        
        assert is_valid is True
    
    def test_verify_proof_invalid_signature(self, sample_identity):
        """Test verifying proof with invalid signature."""
        verifier = IdentityVerifier()
        
        # Create a proof with wrong signature
        bad_proof = IdentityProof(
            challenge="different-challenge",
            signature=sample_identity.proof.signature,
            identity_did=sample_identity.identity.did,
            key_type=sample_identity.identity.key_type
        )
        
        is_valid, errors = verifier.verify_proof(bad_proof, sample_identity.identity)
        
        assert is_valid is False
    
    def test_verify_document_valid(self, sample_identity):
        """Test verifying a complete valid document."""
        verifier = IdentityVerifier()
        is_valid, errors = verifier.verify_document(sample_identity)
        
        assert is_valid is True
    
    def test_verify_document_expired(self, sample_identity):
        """Test verifying an expired document."""
        verifier = IdentityVerifier()
        
        # Create expired proof
        from datetime import datetime, timezone, timedelta
        expired_proof = IdentityProof(
            identity_did=sample_identity.identity.did,
            challenge=sample_identity.proof.challenge,
            signature=sample_identity.proof.signature,
            key_type=sample_identity.identity.key_type,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        expired_doc = IdentityDocument(
            identity=sample_identity.identity,
            proof=expired_proof
        )
        
        is_valid, errors = verifier.verify_document(expired_doc)
        
        assert is_valid is False
        assert any("expired" in e.lower() for e in errors)