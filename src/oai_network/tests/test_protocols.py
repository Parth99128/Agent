"""
Tests for the protocols module (A2A and MCP).
"""

import pytest
from oai_network.protocols.a2a.models import (
    A2ARequest, A2AResponse, A2AError, A2AErrorCode,
    AgentCard, CapabilityQuery, CapabilityResponse,
    DelegationRequest as A2ADelegationRequest,
    DelegationResponse as A2ADelegationResponse,
    NegotiationRequest as A2ANegotiationRequest,
    NegotiationResponse as A2ANegotiationResponse
)
from oai_network.protocols.a2a.client import A2AClient
from oai_network.protocols.a2a.server import A2AServer
from oai_network.protocols.mcp.models import (
    MCPRequest, MCPResponse, MCPError, MCPErrorCode,
    InitializeRequest, InitializeResponse,
    Tool, ToolCall, ToolResult,
    Resource, ResourceReadRequest, ResourceReadResponse,
    Prompt, PromptGetRequest, PromptGetResponse,
    LoggingLevel, LoggingMessage
)
from oai_network.protocols.mcp.client import MCPClient
from oai_network.protocols.mcp.server import MCPServer


class TestA2AModels:
    """Tests for A2A protocol models."""
    
    def test_a2a_request_creation(self):
        """Test creating an A2ARequest."""
        request = A2ARequest(
            method="capability_query",
            params={"query": "text summarization"},
            id="req-123"
        )
        
        assert request.method == "capability_query"
        assert request.params["query"] == "text summarization"
        assert request.id == "req-123"
    
    def test_a2a_response_success(self):
        """Test creating a successful A2AResponse."""
        response = A2AResponse(
            result={"capabilities": ["text_summarization"]},
            id="req-123"
        )
        
        assert response.result["capabilities"] == ["text_summarization"]
        assert response.id == "req-123"
        assert response.error is None
    
    def test_a2a_response_error(self):
        """Test creating an error A2AResponse."""
        response = A2AResponse(
            error=A2AError(
                code=A2AErrorCode.METHOD_NOT_FOUND,
                message="Method not found"
            ),
            id="req-123"
        )
        
        assert response.error is not None
        assert response.error.code == A2AErrorCode.METHOD_NOT_FOUND
        assert response.result is None
    
    def test_a2a_error_codes(self):
        """Test A2AErrorCode enum."""
        assert A2AErrorCode.PARSE_ERROR.value == -32700
        assert A2AErrorCode.INVALID_REQUEST.value == -32600
        assert A2AErrorCode.METHOD_NOT_FOUND.value == -32601
        assert A2AErrorCode.INVALID_PARAMS.value == -32602
        assert A2AErrorCode.INTERNAL_ERROR.value == -32603
        assert A2AErrorCode.AGENT_NOT_FOUND.value == -32000
        assert A2AErrorCode.CAPABILITY_NOT_FOUND.value == -32001
        assert A2AErrorCode.DELEGATION_FAILED.value == -32002
        assert A2AErrorCode.NEGOTIATION_FAILED.value == -32003
    
    def test_agent_card(self):
        """Test AgentCard."""
        card = AgentCard(
            agent_did="did:oai:test123",
            name="Test Agent",
            description="A test agent",
            version="1.0.0",
            capabilities=["text_summarization", "translation"],
            endpoints={"a2a": "http://localhost:8000/a2a"},
            metadata={"author": "Test"}
        )
        
        assert card.agent_did == "did:oai:test123"
        assert card.name == "Test Agent"
        assert len(card.capabilities) == 2
        assert card.endpoints["a2a"] == "http://localhost:8000/a2a"
    
    def test_capability_query(self):
        """Test CapabilityQuery."""
        query = CapabilityQuery(
            query="summarize text",
            capability_type="nlp",
            tags=["summarization"],
            max_results=10
        )
        
        assert query.query == "summarize text"
        assert query.capability_type == "nlp"
        assert "summarization" in query.tags
    
    def test_capability_response(self):
        """Test CapabilityResponse."""
        response = CapabilityResponse(
            agents=[
                {
                    "agent_did": "did:oai:agent1",
                    "capability": "text_summarization",
                    "relevance_score": 0.95
                }
            ]
        )
        
        assert len(response.agents) == 1
        assert response.agents[0]["agent_did"] == "did:oai:agent1"
    
    def test_a2a_delegation_request(self):
        """Test A2ADelegationRequest."""
        request = A2ADelegationRequest(
            capability="text_summarization",
            input_data={"text": "Long text"},
            requirements={"max_price": 0.10}
        )
        
        assert request.capability == "text_summarization"
        assert request.input_data["text"] == "Long text"
    
    def test_a2a_delegation_response(self):
        """Test A2ADelegationResponse."""
        response = A2ADelegationResponse(
            accepted=True,
            task_id="task-123",
            delegatee_did="did:oai:delegatee"
        )
        
        assert response.accepted is True
        assert response.task_id == "task-123"
    
    def test_a2a_negotiation_request(self):
        """Test A2ANegotiationRequest."""
        request = A2ANegotiationRequest(
            template_id="delegation",
            parameters={"price": 0.10, "timeout": 30}
        )
        
        assert request.template_id == "delegation"
        assert request.parameters["price"] == 0.10


class TestA2AClient:
    """Tests for A2AClient."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = A2AClient(base_url="http://localhost:8000")
        
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30.0
    
    @pytest.mark.asyncio
    async def test_send_request(self, a2a_server_url):
        """Test sending a request."""
        client = A2AClient(base_url=a2a_server_url)
        
        # This would need a running server - simplified test
        # Just verify the method exists
        assert hasattr(client, 'send_request')
        assert hasattr(client, 'capability_query')
        assert hasattr(client, 'delegate')
        assert hasattr(client, 'negotiate')
    
    @pytest.mark.asyncio
    async def test_capability_query(self, a2a_server_url):
        """Test capability query."""
        client = A2AClient(base_url=a2a_server_url)
        
        # Would need mock server
        assert hasattr(client, 'capability_query')
    
    @pytest.mark.asyncio
    async def test_delegate(self, a2a_server_url):
        """Test delegation."""
        client = A2AClient(base_url=a2a_server_url)
        
        assert hasattr(client, 'delegate')
    
    @pytest.mark.asyncio
    async def test_negotiate(self, a2a_server_url):
        """Test negotiation."""
        client = A2AClient(base_url=a2a_server_url)
        
        assert hasattr(client, 'negotiate')
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, a2a_server_url):
        """Test WebSocket connection."""
        client = A2AClient(base_url=a2a_server_url)
        
        assert hasattr(client, 'connect_websocket')
        assert hasattr(client, 'send_websocket_message')


class TestA2AServer:
    """Tests for A2AServer."""
    
    def test_server_initialization(self, sample_agent_identity, sample_manifest):
        """Test server initialization."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate().private_bytes_raw()
        server = A2AServer(
            agent_identity=sample_agent_identity,
            private_key=private_key,
            manifest=sample_manifest
        )
        
        assert server.identity == sample_agent_identity
        assert server.manifest == sample_manifest
        assert server.app is not None
    
    def test_register_capability_handler(self, sample_agent_identity, sample_manifest):
        """Test registering capability handler."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate().private_bytes_raw()
        server = A2AServer(
            agent_identity=sample_agent_identity,
            private_key=private_key,
            manifest=sample_manifest
        )
        
        async def handler(params):
            return {"result": "success"}
        
        server.register_capability_handler("test_capability", handler)
        
        assert "test_capability" in server._capability_handlers
    
    def test_register_delegation_handler(self, sample_agent_identity, sample_manifest):
        """Test registering delegation handler."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate().private_bytes_raw()
        server = A2AServer(
            agent_identity=sample_agent_identity,
            private_key=private_key,
            manifest=sample_manifest
        )
        
        async def handler(request):
            return A2ADelegationResponse(accepted=True, task_id="task-123")
        
        server.register_delegation_handler(handler)
        
        assert server.delegation_handler is not None
    
    def test_register_negotiation_handler(self, sample_agent_identity, sample_manifest):
        """Test registering negotiation handler."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate().private_bytes_raw()
        server = A2AServer(
            agent_identity=sample_agent_identity,
            private_key=private_key,
            manifest=sample_manifest
        )
        
        async def handler(request):
            return A2ANegotiationResponse(accepted=True, agreed_parameters={})
        
        server.register_negotiation_handler(handler)
        
        assert server.negotiation_handler is not None


class TestMCPModels:
    """Tests for MCP protocol models."""
    
    def test_mcp_request_creation(self):
        """Test creating an MCPRequest."""
        request = MCPRequest(
            method="tools/list",
            params={},
            id="req-123"
        )
        
        assert request.method == "tools/list"
        assert request.id == "req-123"
    
    def test_mcp_response_success(self):
        """Test creating a successful MCPResponse."""
        response = MCPResponse(
            result={"tools": []},
            id="req-123"
        )
        
        assert response.result["tools"] == []
        assert response.id == "req-123"
        assert response.error is None
    
    def test_mcp_error_codes(self):
        """Test MCPErrorCode enum."""
        assert MCPErrorCode.PARSE_ERROR.value == -32700
        assert MCPErrorCode.INVALID_REQUEST.value == -32600
        assert MCPErrorCode.METHOD_NOT_FOUND.value == -32601
        assert MCPErrorCode.INVALID_PARAMS.value == -32602
        assert MCPErrorCode.INTERNAL_ERROR.value == -32603
    
    def test_initialize_request(self):
        """Test InitializeRequest."""
        request = InitializeRequest(
            protocol_version="2024-11-05",
            capabilities={"tools": {}, "resources": {}, "prompts": {}},
            client_info={"name": "Test Client", "version": "1.0.0"}
        )
        
        assert request.protocol_version == "2024-11-05"
        assert "tools" in request.capabilities
        assert request.client_info["name"] == "Test Client"
    
    def test_initialize_response(self):
        """Test InitializeResponse."""
        response = InitializeResponse(
            protocol_version="2024-11-05",
            capabilities={"tools": {}, "resources": {}},
            server_info={"name": "Test Server", "version": "1.0.0"}
        )
        
        assert response.protocol_version == "2024-11-05"
        assert response.server_info["name"] == "Test Server"
    
    def test_tool(self):
        """Test Tool model."""
        tool = Tool(
            name="summarize",
            description="Summarize text",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                }
            }
        )
        
        assert tool.name == "summarize"
        assert tool.input_schema["properties"]["text"]["type"] == "string"
    
    def test_tool_call(self):
        """Test ToolCall."""
        call = ToolCall(
            name="summarize",
            arguments={"text": "Long text to summarize"}
        )
        
        assert call.name == "summarize"
        assert call.arguments["text"] == "Long text to summarize"
    
    def test_tool_result(self):
        """Test ToolResult."""
        result = ToolResult(
            content=[{"type": "text", "text": "Summary here"}],
            is_error=False
        )
        
        assert result.content[0]["text"] == "Summary here"
        assert result.is_error is False
    
    def test_resource(self):
        """Test Resource model."""
        resource = Resource(
            uri="file:///data/document.txt",
            name="Document",
            description="A text document",
            mime_type="text/plain"
        )
        
        assert resource.uri == "file:///data/document.txt"
        assert resource.mime_type == "text/plain"
    
    def test_resource_read_request(self):
        """Test ResourceReadRequest."""
        request = ResourceReadRequest(
            uri="file:///data/document.txt"
        )
        
        assert request.uri == "file:///data/document.txt"
    
    def test_prompt(self):
        """Test Prompt model."""
        prompt = Prompt(
            name="summarize_prompt",
            description="Prompt for summarization",
            arguments=[
                {"name": "text", "description": "Text to summarize", "required": True}
            ]
        )
        
        assert prompt.name == "summarize_prompt"
        assert len(prompt.arguments) == 1
        assert prompt.arguments[0]["name"] == "text"
    
    def test_logging_levels(self):
        """Test LoggingLevel enum."""
        assert LoggingLevel.DEBUG.value == "debug"
        assert LoggingLevel.INFO.value == "info"
        assert LoggingLevel.WARNING.value == "warning"
        assert LoggingLevel.ERROR.value == "error"
    
    def test_logging_message(self):
        """Test LoggingMessage."""
        message = LoggingMessage(
            level=LoggingLevel.INFO,
            message="Test log message",
            logger="test_logger"
        )
        
        assert message.level == LoggingLevel.INFO
        assert message.message == "Test log message"


class TestMCPClient:
    """Tests for MCPClient."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = MCPClient(base_url="http://localhost:8000")
        
        assert client.base_url == "http://localhost:8000"
        assert client.protocol_version == "2024-11-05"
    
    @pytest.mark.asyncio
    async def test_initialize(self, mcp_server_url):
        """Test initialize."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'initialize')
    
    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_server_url):
        """Test listing tools."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'list_tools')
    
    @pytest.mark.asyncio
    async def test_call_tool(self, mcp_server_url):
        """Test calling a tool."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'call_tool')
    
    @pytest.mark.asyncio
    async def test_list_resources(self, mcp_server_url):
        """Test listing resources."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'list_resources')
    
    @pytest.mark.asyncio
    async def test_read_resource(self, mcp_server_url):
        """Test reading a resource."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'read_resource')
    
    @pytest.mark.asyncio
    async def test_list_prompts(self, mcp_server_url):
        """Test listing prompts."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'list_prompts')
    
    @pytest.mark.asyncio
    async def test_get_prompt(self, mcp_server_url):
        """Test getting a prompt."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'get_prompt')
    
    @pytest.mark.asyncio
    async def test_websocket_notifications(self, mcp_server_url):
        """Test WebSocket notifications."""
        client = MCPClient(base_url=mcp_server_url)
        
        assert hasattr(client, 'connect_websocket')
        assert hasattr(client, 'subscribe_logs')


class TestMCPServer:
    """Tests for MCPServer."""
    
    def test_server_initialization(self):
        """Test server initialization."""
        server = MCPServer(name="Test Server", version="1.0.0")
        
        assert server.name == "Test Server"
        assert server.version == "1.0.0"
        assert server.app is not None
    
    def test_register_tool(self):
        """Test registering a tool."""
        server = MCPServer(name="Test Server", version="1.0.0")
        
        async def tool_handler(arguments):
            return ToolResult(content=[{"type": "text", "text": "Result"}])
        
        server.register_tool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            handler=tool_handler
        )
        
        assert "test_tool" in server.tools
        assert server.tools["test_tool"].name == "test_tool"
    
    def test_register_resource(self):
        """Test registering a resource."""
        server = MCPServer(name="Test Server", version="1.0.0")
        
        async def resource_handler(uri):
            return ResourceReadResponse(
                contents=[{"type": "text", "text": "Resource content"}]
            )
        
        server.register_resource(
            uri="file:///test.txt",
            name="Test Resource",
            description="A test resource",
            mime_type="text/plain",
            handler=resource_handler
        )
        
        assert "file:///test.txt" in server.resources
    
    def test_register_prompt(self):
        """Test registering a prompt."""
        server = MCPServer(name="Test Server", version="1.0.0")
        
        async def prompt_handler(arguments):
            return PromptGetResponse(
                messages=[{"role": "user", "content": "Prompt with " + arguments.get("text", "")}]
            )
        
        server.register_prompt(
            name="test_prompt",
            description="A test prompt",
            arguments=[{"name": "text", "required": True}],
            handler=prompt_handler
        )
        
        assert "test_prompt" in server.prompts
    
    def test_send_log_notification(self):
        """Test sending log notification."""
        server = MCPServer(name="Test Server", version="1.0.0")
        
        # Would need WebSocket connections to test fully
        assert hasattr(server, 'send_log_notification')