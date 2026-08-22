"""
Real Translator Agent - wraps the Translation MCP Server.
Performs actual text translation using local LLM (Ollama) via MCP.
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
logger = get_logger("oai-network-translator-agent")


class TranslatorAgent:
    """Real Translator Agent using MCP server with Ollama for actual translation."""
    
    def __init__(self, identity: Optional[AgentIdentity] = None):
        self.identity = identity
        self._last_translation: Dict[str, Any] = {}
        self._mcp_server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "oai_network.agents.translation_mcp_server"],
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
    
    async def translate(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Translate text.
        Expected params: {text, target_language, source_language?, model?}
        """
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "translate", trace_id,
                        agent_did=self.identity.did if self.identity else None,
                        target_language=params.get("target_language", ""))
        
        try:
            text = params.get("text", "")
            target_language = params.get("target_language", "")
            source_language = params.get("source_language", "auto")
            model = params.get("model", "llama3.2:3b")
            
            if not text.strip():
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "Empty text provided"}
                )
            
            if not target_language:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "target_language is required"}
                )
            
            result = await self._call_mcp_tool("translate", {
                "text": text,
                "target_language": target_language,
                "source_language": source_language,
                "model": model,
            })
            
            if "error" in result:
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "translate"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            # Store for follow-up
            self._last_translation = result
            
            log_agent_action(logger, "translate_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None,
                           target_language=target_language)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "translate"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Translation failed: {str(e)}"}
            )
    
    async def translate_file(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Translate a file.
        Expected params: {file_path, target_language, source_language?, model?}
        """
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "translate_file", trace_id,
                        agent_did=self.identity.did if self.identity else None,
                        file_path=params.get("file_path", ""),
                        target_language=params.get("target_language", ""))
        
        try:
            file_path = params.get("file_path", "")
            target_language = params.get("target_language", "")
            source_language = params.get("source_language", "auto")
            model = params.get("model", "llama3.2:3b")
            
            if not file_path:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "file_path is required"}
                )
            
            if not target_language:
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32602, "message": "target_language is required"}
                )
            
            result = await self._call_mcp_tool("translate_file", {
                "file_path": file_path,
                "target_language": target_language,
                "source_language": source_language,
                "model": model,
            })
            
            if "error" in result:
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "translate_file"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            self._last_translation = result
            
            log_agent_action(logger, "translate_file_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "translate_file"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"File translation failed: {str(e)}"}
            )
    
    async def get_last_translation(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: Get the last translation for follow-up queries.
        """
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "get_last_translation", trace_id,
                        agent_did=self.identity.did if self.identity else None)
        
        try:
            result = await self._call_mcp_tool("get_last_translation", {})
            
            if "error" in result:
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "get_last_translation"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            log_agent_action(logger, "get_last_translation_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "get_last_translation"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Failed to get last translation: {str(e)}"}
            )
    
    async def list_languages(self, params: Dict[str, Any]) -> A2AResponse:
        """
        A2A method: List supported languages.
        """
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "list_languages", trace_id,
                        agent_did=self.identity.did if self.identity else None)
        
        try:
            result = await self._call_mcp_tool("list_languages", {})
            
            if "error" in result:
                log_error(logger, Exception(result["error"]), trace_id, context={"method": "list_languages"})
                return A2AResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error={"code": -32603, "message": result["error"]}
                )
            
            log_agent_action(logger, "list_languages_complete", trace_id,
                           agent_did=self.identity.did if self.identity else None)
            
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                result=result
            )
            
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "list_languages"})
            return A2AResponse(
                jsonrpc="2.0",
                id=request_id,
                error={"code": -32603, "message": f"Failed to list languages: {str(e)}"}
            )
    
    async def capabilities(self, params: Dict[str, Any]) -> A2AResponse:
        """A2A method: Return agent capabilities."""
        trace_id = get_trace_id()
        request_id = params.get("request_id", "unknown")
        
        log_agent_action(logger, "capabilities", trace_id,
                        agent_did=self.identity.did if self.identity else None)
        
        caps = {
            "name": "Translator Agent",
            "description": "Real text translation using local LLM (Ollama) via MCP",
            "methods": [
                {"name": "translate", "description": "Translate text to target language"},
                {"name": "translate_file", "description": "Translate content from a file"},
                {"name": "get_last_translation", "description": "Get previous translation for follow-up"},
                {"name": "list_languages", "description": "List all supported languages"},
            ],
            "supported_languages": 20,
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
        
        if method == "translate":
            return await self.translate(params)
        elif method == "translate_file":
            return await self.translate_file(params)
        elif method == "get_last_translation":
            return await self.get_last_translation(params)
        elif method == "list_languages":
            return await self.list_languages(params)
        elif method == "capabilities":
            return await self.capabilities(params)
        else:
            log_error(logger, Exception(f"Method not found: {method}"), trace_id, context={"method": method})
            return A2AResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )


async def create_translator_agent(identity: Optional[AgentIdentity] = None) -> TranslatorAgent:
    """Factory function to create a TranslatorAgent."""
    return TranslatorAgent(identity=identity)