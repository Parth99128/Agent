"""
OAI Network Python SDK Client

Main client for interacting with OAI Network services.
"""

import asyncio
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.exceptions import InvalidSignature

from ...core.identity.models import AgentIdentity, IdentityDocument, KeyType
from ...core.identity.generator import IdentityGenerator
from ...core.capabilities.models import AgentManifest, Capability, ServiceEndpoint
from ...core.discovery.models import DiscoveryQuery, DiscoveryResult, RegistryEntry
from ...core.delegation.models import DelegationRequest, DelegationResponse, DelegationTask, DelegationResult
from ...core.trust.models import TrustScore, TrustEvent
from ...core.negotiation.models import NegotiationSession, NegotiationRequest, NegotiationResponse
from ...protocols.a2a.client import A2AClient
from ...protocols.mcp.client import MCPClient


class OAIClient:
    """
    Main client for OAI Network.
    
    Provides high-level interface for:
    - Identity management
    - Agent discovery
    - Capability queries
    - Delegation
    - Trust scoring
    - Negotiation
    - A2A/MCP protocol communication
    """
    
    def __init__(
        self,
        registry_url: str = "http://localhost:8081",
        gateway_url: str = "http://localhost:8080",
        identity: Optional[AgentIdentity] = None,
        timeout: float = 30.0,
    ):
        self.registry_url = registry_url.rstrip('/')
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout
        
        # Auto-generate identity if none provided
        if identity is not None:
            self.identity = identity
        else:
            self.identity = self._generate_default_identity()
        
        # Store private key for signing
        self._private_key_pem: Optional[str] = None
        
        # Protocol clients - initialize lazily but make available
        self._a2a_client: Optional[A2AClient] = A2AClient(
            base_url="http://localhost:8000",
        )
        self._mcp_client: Optional[MCPClient] = MCPClient(
            base_url="http://localhost:8001",
            client_info={"name": "oai-network-sdk", "version": "0.1.0"},
        )
        self._http_client: Optional[httpx.AsyncClient] = None
    
    def _generate_default_identity(self) -> AgentIdentity:
        """Generate a default identity for the client."""
        generator = IdentityGenerator(key_type=KeyType.ED25519)
        identity, private_key_pem = generator.create_identity(
            metadata={"name": "OAI SDK Client"}
        )
        self._private_key_pem = private_key_pem
        return identity
    
    @property
    def a2a_client(self) -> Optional[A2AClient]:
        """Get the A2A client instance."""
        return self._a2a_client
    
    @property
    def mcp_client(self) -> Optional[MCPClient]:
        """Get the MCP client instance."""
        return self._mcp_client
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close all connections."""
        if self._http_client:
            await self._http_client.aclose()
        if self._a2a_client:
            try:
                await self._a2a_client.disconnect_websocket()
            except Exception:
                pass
        if self._mcp_client:
            try:
                await self._mcp_client.disconnect_websocket()
            except Exception:
                pass
    
    # Identity management
    def generate_identity(
        self,
        name: str,
        key_type: str = "Ed25519",
    ) -> IdentityDocument:
        """Generate a new agent identity."""
        generator = IdentityGenerator()
        return generator.generate_identity(name=name, key_type=key_type)
    
    async def create_identity(
        self,
        name: str,
        key_type: str = "Ed25519",
    ) -> AgentIdentity:
        """Create a new identity via SDK."""
        generator = IdentityGenerator()
        # Generate identity and capture the private key
        identity, private_key_pem = generator.create_identity(
            metadata={"name": name}
        )
        # Override key_type with the display name string
        identity.key_type = key_type
        self.identity = identity
        self._private_key_pem = private_key_pem
        return self.identity
    
    def load_identity(self, identity_doc: IdentityDocument) -> AgentIdentity:
        """Load an identity from a document."""
        self.identity = identity_doc.identity
        return self.identity
    
    def save_identity(self, path: str):
        """Save identity to file."""
        if not self.identity:
            raise ValueError("No identity loaded")
        with open(path, 'w') as f:
            json.dump(self.identity.model_dump(mode='json'), f, indent=2)
    
    @classmethod
    def load_identity_from_file(cls, path: str) -> 'OAIClient':
        """Create client with identity loaded from file."""
        with open(path, 'r') as f:
            data = json.load(f)
        identity = AgentIdentity(**data)
        return cls(identity=identity)
    
    # Registry operations
    async def register_agent(
        self,
        manifest: AgentManifest,
        identity_proof: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register an agent with the registry."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        # Send manifest as JSON string as expected by registry
        payload = {
            "manifest": manifest.model_dump(mode='json'),
            "ttl_seconds": 86400,
        }
        
        response = await self._http_client.post(
            f"{self.registry_url}/register",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def heartbeat(self, status: str = "healthy", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send heartbeat to registry."""
        if not self.identity:
            raise ValueError("No identity loaded")
        
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        payload = {
            "agent_did": self.identity.did,
            "status": status,
            "metadata": metadata or {},
        }
        
        response = await self._http_client.post(
            f"{self.registry_url}/heartbeat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def unregister_agent(self) -> bool:
        """Unregister agent from registry."""
        if not self.identity:
            raise ValueError("No identity loaded")
        
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        response = await self._http_client.delete(
            f"{self.registry_url}/agents/{self.identity.did}",
        )
        return response.status_code == 200
    
    # Discovery operations
    async def discover(
        self,
        query: str = "",
        capability: Optional[str] = None,
        capability_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_trust_score: float = 0.0,
        verified_only: bool = False,
        max_results: int = 20,
    ) -> List[DiscoveryResult]:
        """Discover agents matching criteria."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        # Use POST with JSON body as expected by registry
        payload = {
            "capability": capability or query or "general",
            "max_results": max_results,
            "min_trust_score": min_trust_score,
            "verified_only": verified_only,
            "tags": tags or [],
        }
        
        response = await self._http_client.post(
            f"{self.registry_url}/discover",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        
        # Map registry DiscoveryAgentResult to SDK DiscoveryResult
        results = []
        for item in data.get("agents", []):
            results.append(DiscoveryResult(
                agent_did=item.get("agent_did", ""),
                agent_name=item.get("agent_name", ""),
                agent_description=item.get("agent_description", ""),
                capability_name=item.get("capabilities", [""])[0] if item.get("capabilities") else "",
                capability_type="",
                relevance_score=0.8,  # Default relevance
                trust_score=item.get("trust_score", 0.0),
                estimated_latency_ms=None,
                price_per_unit=None,
                currency="USD",
                endpoint_url=item.get("endpoints", [""])[0] if item.get("endpoints") else "",
                tags=item.get("tags", []),
                verified=item.get("verified", False),
            ))
        return results
    
    async def discover_agents(
        self,
        query: str = "",
        capability: Optional[str] = None,
        capability_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_trust_score: float = 0.0,
        verified_only: bool = False,
        max_results: int = 20,
    ) -> List[DiscoveryResult]:
        """Alias for discover."""
        return await self.discover(
            query=query,
            capability=capability,
            capability_type=capability_type,
            tags=tags,
            min_trust_score=min_trust_score,
            verified_only=verified_only,
            max_results=max_results,
        )
    
    async def find_agent(self, query: str) -> List[DiscoveryResult]:
        """Natural language agent discovery (main entry point)."""
        return await self.discover(query=query)
    
    async def get_agent(self, agent_did: str) -> Optional[RegistryEntry]:
        """Get agent details by DID."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        response = await self._http_client.get(
            f"{self.registry_url}/agents/{agent_did}",
        )
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        return RegistryEntry(**response.json())
    
    # Capability operations
    async def query_capability(
        self,
        agent_did: str,
        capability_name: str,
        input_data: Dict[str, Any],
    ) -> Any:
        """Query a specific capability on an agent."""
        agent = await self.get_agent(agent_did)
        if not agent:
            raise ValueError(f"Agent not found: {agent_did}")
        
        a2a_client = await self._get_a2a_client(agent)
        return await a2a_client.query_capability(capability_name, input_data)
    
    # Delegation operations
    async def delegate(
        self,
        task: str,
        capability: str,
        input_data: Dict[str, Any],
        preferred_agent: Optional[str] = None,
        max_depth: int = 3,
        timeout: float = 60.0,
    ) -> DelegationResult:
        """Delegate a task to another agent."""
        if not self.identity:
            raise ValueError("No identity loaded")
        
        agents = await self.discover(
            capability=capability,
            min_trust_score=0.5,
            verified_only=True,
        )
        
        if not agents:
            raise ValueError(f"No agents found with capability: {capability}")
        
        target_agent = None
        if preferred_agent:
            target_agent = next((a for a in agents if a.agent_did == preferred_agent), None)
        
        if not target_agent:
            target_agent = agents[0]
        
        delegation_request = DelegationRequest(
            delegator_did=self.identity.did,
            delegatee_did=target_agent.agent_did,
            task=DelegationTask(
                capability=capability,
                input_data=input_data,
                description=task,
            ),
            max_depth=max_depth,
            timeout_seconds=int(timeout),
        )
        
        a2a_client = await self._get_a2a_client(target_agent)
        response = await a2a_client.delegate(delegation_request)
        
        if not response.accepted:
            raise Exception(f"Delegation rejected: {response.reason}")
        
        return await self._wait_for_delegation_result(a2a_client, response.delegation_id, timeout)
    
    async def delegate_task(
        self,
        task: str,
        capability: str,
        input_data: Dict[str, Any],
        preferred_agent: Optional[str] = None,
        max_depth: int = 3,
        timeout: float = 60.0,
    ) -> DelegationResult:
        """Alias for delegate."""
        return await self.delegate(
            task=task,
            capability=capability,
            input_data=input_data,
            preferred_agent=preferred_agent,
            max_depth=max_depth,
            timeout=timeout,
        )
    
    async def _wait_for_delegation_result(
        self,
        client: A2AClient,
        delegation_id: str,
        timeout: float,
    ) -> DelegationResult:
        """Wait for delegation result."""
        start = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start < timeout:
            status = await client.get_delegation_status(delegation_id)
            
            if status.status.value == "completed":
                return DelegationResult(
                    delegation_id=delegation_id,
                    status=status.status,
                    result=status.result,
                    completed_at=datetime.now(timezone.utc),
                )
            elif status.status.value == "failed":
                raise Exception(f"Delegation failed: {status.error}")
            
            await asyncio.sleep(1)
        
        raise TimeoutError(f"Delegation timed out after {timeout}s")
    
    # Trust operations
    async def get_trust_score(self, agent_did: str) -> Optional[TrustScore]:
        """Get trust score for an agent."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        response = await self._http_client.get(
            f"{self.registry_url}/trust/{agent_did}",
        )
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        return TrustScore(**response.json())
    
    async def submit_feedback(
        self,
        target_did: str,
        rating: float,
        comment: str = "",
        interaction_id: Optional[str] = None,
    ) -> TrustEvent:
        """Submit feedback for an agent."""
        if not self.identity:
            raise ValueError("No identity loaded")
        
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        payload = {
            "source_did": self.identity.did,
            "target_did": target_did,
            "rating": rating,
            "comment": comment,
            "interaction_id": interaction_id,
        }
        
        response = await self._http_client.post(
            f"{self.registry_url}/feedback",
            json=payload,
        )
        response.raise_for_status()
        return TrustEvent(**response.json())
    
    # Negotiation operations
    async def negotiate(
        self,
        counterparty_did: str,
        terms: Dict[str, Any],
        template: str = "standard",
    ) -> NegotiationSession:
        """Start a negotiation session."""
        if not self.identity:
            raise ValueError("No identity loaded")
        
        request = NegotiationRequest(
            initiator_did=self.identity.did,
            responder_did=counterparty_did,
            template_id=template,
            parameters=terms,
        )
        
        counterparty = await self.get_agent(counterparty_did)
        if not counterparty:
            raise ValueError(f"Counterparty not found: {counterparty_did}")
        
        a2a_client = await self._get_a2a_client(counterparty)
        response = await a2a_client.negotiate(request)
        
        return NegotiationSession(
            session_id=response.request_id,
            initiator_did=self.identity.did,
            responder_did=counterparty_did,
            template_id=template,
            status="active",
            parameters=response.counter_parameters or terms,
        )
    
    # Protocol clients
    async def _get_a2a_client(self, agent: RegistryEntry) -> A2AClient:
        """Get or create A2A client for an agent."""
        if not self._a2a_client:
            a2a_endpoint = None
            for endpoint in agent.endpoints:
                if 'a2a' in endpoint.lower():
                    a2a_endpoint = endpoint
                    break
            
            if not a2a_endpoint and agent.endpoints:
                a2a_endpoint = agent.endpoints[0]
            
            if not a2a_endpoint:
                raise ValueError(f"No A2A endpoint for agent {agent.agent_did}")
            
            self._a2a_client = A2AClient(
                base_url=a2a_endpoint,
                identity=self.identity,
            )
            await self._a2a_client.connect()
        
        return self._a2a_client
    
    async def get_mcp_client(self, agent: RegistryEntry) -> MCPClient:
        """Get MCP client for an agent."""
        mcp_endpoint = None
        for endpoint in agent.endpoints:
            if 'mcp' in endpoint.lower():
                mcp_endpoint = endpoint
                break
        
        if not mcp_endpoint and agent.endpoints:
            mcp_endpoint = agent.endpoints[0]
        
        if not mcp_endpoint:
            raise ValueError(f"No MCP endpoint for agent {agent.agent_did}")
        
        if not self._mcp_client:
            self._mcp_client = MCPClient(
                base_url=mcp_endpoint,
                client_info={"name": "oai-network-sdk", "version": "0.1.0"},
            )
            await self._mcp_client.initialize()
        
        return self._mcp_client
    
    # Signing and verification
    async def sign_message(self, message: str) -> str:
        """Sign a message with the client's private key."""
        if not self._private_key_pem:
            # Generate a key pair for signing and update identity's public key
            generator = IdentityGenerator(key_type=KeyType.ED25519)
            identity, private_key_pem = generator.create_identity(
                metadata=self.identity.metadata
            )
            self._private_key_pem = private_key_pem
            # Update the identity's public key to match the private key
            self.identity.public_key = identity.public_key
        
        private_key = load_pem_private_key(
            self._private_key_pem.encode('utf-8'),
            password=None,
        )
        
        message_bytes = message.encode('utf-8')
        
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            signature = private_key.sign(message_bytes)
        else:  # RSA
            signature = private_key.sign(
                message_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        
        return signature.hex()
    
    async def verify_signature(
        self,
        agent_did: str,
        message: str,
        signature: str,
    ) -> bool:
        """Verify a signature from an agent."""
        try:
            # Load the public key from the identity
            public_key_pem = self.identity.public_key
            public_key = load_pem_public_key(public_key_pem.encode('utf-8'))
            
            message_bytes = message.encode('utf-8')
            signature_bytes = bytes.fromhex(signature)
            
            if isinstance(public_key, ed25519.Ed25519PublicKey):
                public_key.verify(signature_bytes, message_bytes)
            else:  # RSA
                public_key.verify(
                    signature_bytes,
                    message_bytes,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
    
    # Utility methods
    async def health_check(self) -> Dict[str, Any]:
        """Check health of registry and gateway."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        results = {}
        
        try:
            response = await self._http_client.get(f"{self.registry_url}/health")
            results["registry"] = response.json()
        except Exception as e:
            results["registry"] = {"status": "unhealthy", "error": str(e)}
        
        try:
            response = await self._http_client.get(f"{self.gateway_url}/health")
            results["gateway"] = response.json()
        except Exception as e:
            results["gateway"] = {"status": "unhealthy", "error": str(e)}
        
        return results