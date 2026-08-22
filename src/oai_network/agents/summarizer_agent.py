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
from oai_network.core.observability import (
    get_logger, log_agent_action, log_error, get_trace_id
)

# Configure structured logging
logger = get_logger("oai-network-summarizer-agent")


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
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "analyze", trace_id,
                        agent_did=self.identity.did if self.identity else None,
                        style=params.get("style", "concise"))
        
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
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "analyze"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            # Store for follow-up
            self._last_summary = result
            
            log_agent_action(logger, "analyze_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None,
                           summary_length=len(result.get("summary", "")))
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "analyze"})
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
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "summarize_file", trace_id,
                        agent_did=self.identity.did if self.identity else None,
                        file_path=params.get("file_path", ""))
        
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
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "summarize_file"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            self._last_summary = result
            
            log_agent_action(logger, "summarize_file_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "summarize_file"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"File summarization failed: {str(e)}"}
            )
    
    async def get_last_summary(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Get the last summary for follow-up queries.
        """
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "get_last_summary", trace_id,
                        agent_did=self.identity.did if self.identity else None)
        
        try:
            result = await self._call_mcp_tool("get_last_summary", {})
            
            if "error" in result:
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "get_last_summary"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            log_agent_action(logger, "get_last_summary_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "get_last_summary"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Failed to get last summary: {str(e)}"}
            )
    
    async def capabilities(self, params: Dict[str, Any]) -> A2AResponse:
        """A2A method: Return agent capabilities."""
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "capabilities", trace_id,
                        agent_did=self.identity.did if self.identity else None)
        
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
        trace_id = get_trace_id()
        method = request.method
        params = request.params or {}
        params["request_id"] = request.id
        
        log_agent_action(logger, "handle_request", trace_id,
                        agent_did=self.identity.did if self.identity else None,
                        method=method)
        
        if method == "analyze":
            return await self.analyze(params)
        elif method == "summarize_file":
            return await self.summarize_file(params)
        elif method == "get_last_summary":
            return await self.get_last_summary(params)
        elif method == "capabilities":
            return await self.capabilities(params)
        else:
            log_error(logger, Exception(f"Method not found: {method}"), trace_id, context={"method": method})
            return A2AResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )


async def create_summarizer_agent(identity: Optional[AgentIdentity] = None) -> SummarizerAgent:
    """Factory function to create a SummarizerAgent."""
    return SummarizerAgent(identity=identity)