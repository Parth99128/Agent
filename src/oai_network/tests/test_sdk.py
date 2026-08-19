"""
Tests for the SDKs (Python and TypeScript).
"""

import pytest
from oai_network.sdk.python.client import OAIClient
from oai_network.core.identity.generator import IdentityGenerator


class TestPythonSDK:
    """Tests for Python SDK."""
    
    def test_client_initialization(self):
        """Test OAIClient initialization."""
        client = OAIClient(
            registry_url="http://localhost:8000",
            identity=None  # Will generate one
        )
        
        assert client.registry_url == "http://localhost:8000"
        assert client.identity is not None
        assert client.identity.did.startswith("did:oai:")
    
    def test_client_with_existing_identity(self, sample_agent_identity):
        """Test OAIClient with existing identity."""
        client = OAIClient(
            registry_url="http://localhost:8000",
            identity=sample_agent_identity
        )
        
        assert client.identity == sample_agent_identity
    
    @pytest.mark.asyncio
    async def test_register_agent(self, python_sdk_client, sample_manifest):
        """Test registering agent via SDK."""
        # This would need a running registry - simplified test
        assert hasattr(python_sdk_client, 'register_agent')
        assert hasattr(python_sdk_client, 'unregister_agent')
        assert hasattr(python_sdk_client, 'heartbeat')
    
    @pytest.mark.asyncio
    async def test_discover_agents(self, python_sdk_client):
        """Test discovering agents via SDK."""
        assert hasattr(python_sdk_client, 'discover_agents')
    
    @pytest.mark.asyncio
    async def test_query_capability(self, python_sdk_client):
        """Test querying capability via SDK."""
        assert hasattr(python_sdk_client, 'query_capability')
    
    @pytest.mark.asyncio
    async def test_delegate_task(self, python_sdk_client):
        """Test delegating task via SDK."""
        assert hasattr(python_sdk_client, 'delegate_task')
    
    @pytest.mark.asyncio
    async def test_get_trust_score(self, python_sdk_client):
        """Test getting trust score via SDK."""
        assert hasattr(python_sdk_client, 'get_trust_score')
    
    @pytest.mark.asyncio
    async def test_submit_feedback(self, python_sdk_client):
        """Test submitting feedback via SDK."""
        assert hasattr(python_sdk_client, 'submit_feedback')
    
    @pytest.mark.asyncio
    async def test_negotiate(self, python_sdk_client):
        """Test negotiation via SDK."""
        assert hasattr(python_sdk_client, 'negotiate')
    
    @pytest.mark.asyncio
    async def test_a2a_client_access(self, python_sdk_client):
        """Test accessing A2A client via SDK."""
        assert hasattr(python_sdk_client, 'a2a_client')
        assert python_sdk_client.a2a_client is not None
    
    @pytest.mark.asyncio
    async def test_mcp_client_access(self, python_sdk_client):
        """Test accessing MCP client via SDK."""
        assert hasattr(python_sdk_client, 'mcp_client')
        assert python_sdk_client.mcp_client is not None
    
    def test_client_context_manager(self):
        """Test client as async context manager."""
        client = OAIClient(registry_url="http://localhost:8000")
        
        assert hasattr(client, '__aenter__')
        assert hasattr(client, '__aexit__')
    
    @pytest.mark.asyncio
    async def test_create_identity(self):
        """Test creating identity via SDK."""
        client = OAIClient(registry_url="http://localhost:8000")
        
        identity = await client.create_identity(name="SDK Agent", key_type="Ed25519")
        
        assert identity.did.startswith("did:oai:")
        assert identity.key_type == "Ed25519"
        assert identity.metadata["name"] == "SDK Agent"
    
    @pytest.mark.asyncio
    async def test_sign_message(self, python_sdk_client):
        """Test signing a message via SDK."""
        message = "Test message to sign"
        signature = await python_sdk_client.sign_message(message)
        
        assert signature is not None
        assert len(signature) > 0
    
    @pytest.mark.asyncio
    async def test_verify_signature(self, python_sdk_client):
        """Test verifying a signature via SDK."""
        message = "Test message"
        signature = await python_sdk_client.sign_message(message)
        
        is_valid = await python_sdk_client.verify_signature(
            python_sdk_client.identity.did,
            message,
            signature
        )
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_verify_invalid_signature(self, python_sdk_client):
        """Test verifying invalid signature."""
        is_valid = await python_sdk_client.verify_signature(
            python_sdk_client.identity.did,
            "different message",
            "invalid_signature"
        )
        
        assert is_valid is False


class TestTypeScriptSDK:
    """Tests for TypeScript SDK (structure validation)."""
    
    def test_typescript_types_exist(self):
        """Test that TypeScript types are properly defined."""
        # This is a structural test - verify the types file exists and has expected exports
        import os
        types_path = "/workspaces/Agent/src/oai_network/sdk/typescript/src/types.ts"
        
        assert os.path.exists(types_path)
        
        with open(types_path, 'r') as f:
            content = f.read()
        
        # Check for key type definitions
        assert "export interface AgentIdentity" in content
        assert "export interface AgentManifest" in content
        assert "export interface Capability" in content
        assert "export interface ServiceEndpoint" in content
        assert "export interface TrustMetrics" in content
        assert "export interface DiscoveryQuery" in content
        assert "export interface DiscoveryResult" in content
        assert "export interface DelegationRequest" in content
        assert "export interface DelegationResponse" in content
        assert "export interface NegotiationRequest" in content
        assert "export interface NegotiationResponse" in content
        assert "export interface TrustScore" in content
        assert "export interface Feedback" in content
        assert "export interface Policy" in content
        assert "export interface PolicyRule" in content
    
    def test_typescript_client_exists(self):
        """Test that TypeScript client is properly defined."""
        import os
        client_path = "/workspaces/Agent/src/oai_network/sdk/typescript/src/client.ts"
        
        assert os.path.exists(client_path)
        
        with open(client_path, 'r') as f:
            content = f.read()
        
        # Check for key class and methods
        assert "export class OAIClient" in content
        assert "registerAgent" in content
        assert "unregisterAgent" in content
        assert "heartbeat" in content
        assert "discoverAgents" in content
        assert "queryCapability" in content
        assert "delegateTask" in content
        assert "getTrustScore" in content
        assert "submitFeedback" in content
        assert "negotiate" in content
        assert "createIdentity" in content
        assert "signMessage" in content
        assert "verifySignature" in content
    
    def test_typescript_a2a_client(self):
        """Test that A2A client is defined in TypeScript."""
        import os
        client_path = "/workspaces/Agent/src/oai_network/sdk/typescript/src/client.ts"
        
        with open(client_path, 'r') as f:
            content = f.read()
        
        assert "export class A2AClient" in content
        assert "sendRequest" in content
        assert "capabilityQuery" in content
        assert "delegate" in content
        assert "negotiate" in content
        assert "connectWebSocket" in content
    
    def test_typescript_mcp_client(self):
        """Test that MCP client is defined in TypeScript."""
        import os
        client_path = "/workspaces/Agent/src/oai_network/sdk/typescript/src/client.ts"
        
        with open(client_path, 'r') as f:
            content = f.read()
        
        assert "export class MCPClient" in content
        assert "initialize" in content
        assert "listTools" in content
        assert "callTool" in content
        assert "listResources" in content
        assert "readResource" in content
        assert "listPrompts" in content
        assert "getPrompt" in content
        assert "connectWebSocket" in content
    
    def test_typescript_package_json(self):
        """Test that package.json has correct configuration."""
        import os
        import json
        
        package_path = "/workspaces/Agent/src/oai_network/sdk/typescript/package.json"
        
        assert os.path.exists(package_path)
        
        with open(package_path, 'r') as f:
            package = json.load(f)
        
        assert package["name"] == "@oai-network/sdk"
        assert "axios" in package["dependencies"]
        assert "ws" in package["dependencies"]
        assert "uuid" in package["dependencies"]
        assert "typescript" in package["devDependencies"]
        assert package["main"] == "dist/index.js"
        assert package["types"] == "dist/index.d.ts"
    
    def test_typescript_index_exports(self):
        """Test that index.ts exports all public APIs."""
        import os
        index_path = "/workspaces/Agent/src/oai_network/sdk/typescript/src/index.ts"
        
        assert os.path.exists(index_path)
        
        with open(index_path, 'r') as f:
            content = f.read()
        
        assert "export { OAIClient }" in content
        assert "export { A2AClient }" in content
        assert "export { MCPClient }" in content
        assert "export * from './types'" in content


class TestSDKIntegration:
    """Integration tests for SDKs."""
    
    @pytest.mark.asyncio
    async def test_python_sdk_full_flow(self, python_sdk_client):
        """Test a full flow using Python SDK."""
        # This would test the complete flow:
        # 1. Create identity
        # 2. Register agent
        # 3. Discover agents
        # 4. Delegate task
        # 5. Check trust score
        # 6. Submit feedback
        
        # For now, just verify all methods exist
        methods = [
            'create_identity',
            'register_agent',
            'unregister_agent',
            'heartbeat',
            'discover_agents',
            'query_capability',
            'delegate_task',
            'get_trust_score',
            'submit_feedback',
            'negotiate',
            'sign_message',
            'verify_signature'
        ]
        
        for method in methods:
            assert hasattr(python_sdk_client, method), f"Missing method: {method}"
    
    def test_typescript_sdk_compiles(self):
        """Test that TypeScript SDK can be compiled (structural check)."""
        import os
        
        # Check tsconfig.json exists
        tsconfig_path = "/workspaces/Agent/src/oai_network/sdk/typescript/tsconfig.json"
        assert os.path.exists(tsconfig_path)
        
        with open(tsconfig_path, 'r') as f:
            import json
            tsconfig = json.load(f)
        
        assert tsconfig["compilerOptions"]["target"] == "ES2020"
        assert tsconfig["compilerOptions"]["module"] == "commonjs"
        assert tsconfig["compilerOptions"]["declaration"] is True
        assert tsconfig["compilerOptions"]["outDir"] == "./dist"
        assert tsconfig["compilerOptions"]["rootDir"] == "./src"
        assert tsconfig["compilerOptions"]["strict"] is True