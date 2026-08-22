"""
Real Summarizer Agent - wraps the Summarization MCP Server.
Performs actual text summarization using local LLM (Ollama) via MCP.
"""

import asyncio
import json
import sys
from typing import Any, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from oai_network.core.identity.models import AgentIdentity
from oai_network.protocols.a2a.models import A2ARequest, A2AResponse


class SummarizerAgent:
    """Real Summarizer Agent using MCP server with Ollama for actual summarization."""
    
    def __init__(self, identity: Optional[AgentIdentity] = None):
        self.identity = identity
        self._last_summary: Dict[str, Any] = {}
        self._mcp_server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "oai_network.agents.summarization_mcp_server"],
        )
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server with a fresh connection."""
        async with stdio_client(self._mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                # Parse the text content from the result
                if result.content and len(result.content) > 0:
                    text_content = result.content[0]
                    if hasattr(text_content, 'text'):
                        return json.loads(text_content.text)
                return {"error": "No content returned"}
    
    async def analyze(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Summarize text.
        Expected params: {text, style?, max_length?, model?}
        """
        request_id = params.get("request_id", "unknown")
        
        try:
            text = params.get("text", "")
            style = params.get("style", "concise")
            max_length = params.get("max_length", 200)
            model = params.get("model", "llama3.2:3b")
            
            if not text.strip():
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "Empty text provided"}
                )
            
            result = await self._call_mcp_tool("summarize", {
                "text": text,
                "style": style,
                "max_length": max_length,
                "model": model,
            })
            
            if "error" in result:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            # Store for follow-up
            self._last_summary = result
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Summarization failed: {str(e)}"}
            )
    
    async def summarize_file(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Summarize a file.
        Expected params: {file_path, style?, max_length?, model?}
        """
        request_id = params.get("request_id", "unknown")
        
        try:
            file_path = params.get("file_path", "")
            style = params.get("style", "concise")
            max_length = params.get("max_length", 200)
            model = params.get("model", "llama3.2:3b")
            
            if not file_path:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "file_path is required"}
                )
            
            result = await self._call_mcp_tool("summarize_file", {
                "file_path": file_path,
                "style": style,
                "max_length": max_length,
                "model": model,
            })
            
            if "error" in result:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            self._last_summary = result
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"File summarization failed: {str(e)}"}
            )
    
    async def get_last_summary(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Get the last summary for follow-up queries.
        """
        request_id = params.get("request_id", "unknown")
        
        try:
            result = await self._call_mcp_tool("get_last_summary", {})
            
            if "error" in result:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Failed to get last summary: {str(e)}"}
            )
    
    async def capabilities(self, params: Dict[str, Any]) -> A2AResponse:
        """A2A method: Return agent capabilities."""
        request_id = params.get("request_id", "unknown")
        
        caps = {
            "name": "Summarizer Agent",
            "description": "Real text summarization using local LLM (Ollama) via MCP",
            "methods": [
                {"name": "analyze", "description": "Summarize text with style options"},
                {"name": "summarize_file", "description": "Summarize content from a file"},
                {"name": "get_last_summary", "description": "Get previous summary for follow-up"},
            ],
            "styles": ["concise", "bullet_points", "detailed", "executive", "technical"],
            "models": ["llama3.2:3b", "phi3:mini", "tinyllama"],
            "version": "1.0.0",
        }
        
        return A2AResponse(
            jsonrpc="2.0",
            id=request_id,
            result=caps
        )
    
    async def handle_request(self, request: A2ARequest) -> A2AResponse:
        """Route A2A requests to appropriate handler."""
        method = request.method
        params = request.params or {}
        params["request_id"] = request.id
        
        if method == "analyze":
            return await self.analyze(params)
        elif method == "summarize_file":
            return await self.summarize_file(params)
        elif method == "get_last_summary":
            return await self.get_last_summary(params)
        elif method == "capabilities":
            return await self.capabilities(params)
        else:
            return A2AResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )


async def create_summarizer_agent(identity: Optional[AgentIdentity] = None) -> SummarizerAgent:
    """Factory function to create a SummarizerAgent."""
    return SummarizerAgent(identity=identity)