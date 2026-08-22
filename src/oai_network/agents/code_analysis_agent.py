"""
Code Analysis Agent

A real agent that wraps the MCP server with Bandit/Pylint tools.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.models import IdentityDocument, KeyType, AgentIdentity
from oai_network.core.capabilities.models import AgentManifest, Capability, ServiceEndpoint, CapabilityPricing
from oai_network.sdk.python.client import OAIClient

# MCP client imports
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request to analyze code."""
    path: str
    tools: Optional[List[str]] = None  # ["bandit", "pylint"] or None for both


class AnalysisResponse(BaseModel):
    """Analysis response."""
    summary: Dict[str, Any]
    security_issues: List[Dict[str, Any]]
    quality_issues: List[Dict[str, Any]]


class CodeAnalysisAgent:
    """A code analysis agent that wraps the MCP server."""
    
    def __init__(self, name: str = "Code Analysis Agent", port: int = 8003):
        self.name = name
        self.port = port
        self.identity: Optional[IdentityDocument] = None
        self.manifest: Optional[AgentManifest] = None
        self.app = FastAPI(title=f"OAI Network - {name}")
        self._mcp_session: Optional[ClientSession] = None
        self._mcp_read = None
        self._mcp_write = None
        self._mcp_task_group = None
        self._last_analysis: Dict[str, Any] = {}
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.name}
        
        @self.app.get("/.well-known/agent-card.json")
        async def agent_card():
            """Return agent manifest (A2A Agent Card)."""
            if self.manifest:
                return self.manifest.model_dump(mode='json')
            return {"error": "Not initialized"}
        
        @self.app.post("/a2a")
        async def a2a_endpoint(request: dict):
            """A2A protocol endpoint."""
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            if method == "analyze":
                return await self._handle_analyze(params, request_id)
            elif method == "get_security_issues":
                return await self._handle_get_security_issues(params, request_id)
            elif method == "get_quality_metrics":
                return await self._handle_get_quality_metrics(params, request_id)
            elif method == "capabilities":
                return await self._handle_capabilities(request_id)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
    
    async def _ensure_mcp_connection(self):
        """Ensure MCP connection is established."""
        if self._mcp_session is None:
            import sys
            params = StdioServerParameters(
                command=sys.executable, 
                args=['-m', 'src.oai_network.agents.code_analysis_mcp_server']
            )
            # Use stdio_client as async context manager properly
            self._mcp_client_cm = stdio_client(params)
            self._mcp_read, self._mcp_write = await self._mcp_client_cm.__aenter__()
            self._mcp_session = ClientSession(self._mcp_read, self._mcp_write)
            await self._mcp_session.initialize()
            logger.info("MCP connection established")
    
    async def _close_mcp_connection(self):
        """Close MCP connection."""
        if self._mcp_session:
            try:
                await self._mcp_session.__aexit__(None, None, None)
            except Exception:
                pass
        if hasattr(self, '_mcp_client_cm') and self._mcp_client_cm:
            try:
                await self._mcp_client_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._mcp_session = None
        self._mcp_read = None
        self._mcp_write = None
        self._mcp_client_cm = None
    
    async def _handle_analyze(self, params: dict, request_id: str) -> dict:
        """Handle analysis request."""
        try:
            import sys
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp import ClientSession
            
            # Create a fresh connection for each request
            params_mcp = StdioServerParameters(
                command=sys.executable, 
                args=['-m', 'src.oai_network.agents.code_analysis_mcp_server']
            )
            
            async with stdio_client(params_mcp) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    path = params.get("path", ".")
                    tools = params.get("tools")
                    
                    # Call MCP analyze_repo tool
                    result = await session.call_tool('analyze_repo', {'path': path})
                    
                    # Parse the result
                    import json
                    result_text = result.content[0].text
                    result_data = json.loads(result_text)
                    
                    # Store for follow-up queries
                    self._last_analysis = result_data
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result_data
                    }
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    async def _handle_get_security_issues(self, params: dict, request_id: str) -> dict:
        """Handle get security issues request."""
        try:
            # Use stored analysis results
            severity = params.get("severity", "ALL").upper()
            security_issues = self._last_analysis.get("security_issues", [])
            
            if severity != "ALL":
                security_issues = [i for i in security_issues if i.get("severity", "").upper() == severity]
            
            result_data = {
                "security_issues": security_issues,
                "count": len(security_issues),
                "filter": severity,
            }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result_data
            }
        except Exception as e:
            logger.error(f"Get security issues failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    async def _handle_get_quality_metrics(self, params: dict, request_id: str) -> dict:
        """Handle get quality metrics request."""
        try:
            # Use stored analysis results
            metrics = self._last_analysis.get("metrics", {})
            quality_issues = self._last_analysis.get("quality_issues", [])
            
            result_data = {
                "metrics": metrics,
                "quality_issues_sample": quality_issues[:20],
            }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result_data
            }
        except Exception as e:
            logger.error(f"Get quality metrics failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    async def _handle_capabilities(self, request_id: str) -> dict:
        """Return capabilities."""
        caps = []
        if self.manifest:
            for cap in self.manifest.capabilities:
                caps.append({
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema,
                })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"capabilities": caps}
        }
    
    def generate_identity(self, key_type: KeyType = KeyType.ED25519):
        """Generate agent identity."""
        generator = IdentityGenerator(key_type=key_type)
        self.identity = generator.generate_identity(name=self.name)
        logger.info(f"Generated identity: {self.identity.identity.did}")
        return self.identity
    
    def create_manifest(self, registry_url: str = "http://localhost:8081"):
        """Create agent manifest."""
        if not self.identity:
            self.generate_identity()
        
        # Define code analysis capability
        analysis_cap = Capability(
            name="code_analysis",
            type="security",
            description="Analyze code repositories for security vulnerabilities and quality issues using Bandit and Pylint",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to analyze (file or directory)"},
                    "tools": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["bandit", "pylint"]},
                        "description": "Tools to run (default: both)"
                    }
                },
                "required": ["path"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "object"},
                    "security_issues": {"type": "array"},
                    "quality_issues": {"type": "array"}
                }
            },
            tags=["security", "analysis", "bandit", "pylint", "code-quality"],
            pricing=CapabilityPricing(cost_per_call=0.01),
            estimated_latency_ms=5000,
        )
        
        # Define security issues capability
        security_cap = Capability(
            name="get_security_issues",
            type="security",
            description="Get security issues filtered by severity",
            input_schema={
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "issues": {"type": "array"}
                }
            },
            tags=["security", "vulnerabilities"],
            pricing=CapabilityPricing(cost_per_call=0.001),
            estimated_latency_ms=1000,
        )
        
        # Define quality metrics capability
        quality_cap = Capability(
            name="get_quality_metrics",
            type="quality",
            description="Get code quality metrics from Pylint",
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {
                    "metrics": {"type": "object"}
                }
            },
            tags=["quality", "metrics", "pylint"],
            pricing=CapabilityPricing(cost_per_call=0.001),
            estimated_latency_ms=1000,
        )
        
        # Define endpoint
        endpoint = ServiceEndpoint(
            url=f"http://localhost:{self.port}/a2a",
            protocol="a2a",
            description="A2A protocol endpoint"
        )
        
        self.manifest = AgentManifest(
            identity=self.identity.identity,
            name=self.name,
            description="Code analysis agent using Bandit (security) and Pylint (quality) via MCP",
            version="1.0.0",
            capabilities=[analysis_cap, security_cap, quality_cap],
            endpoints=[endpoint],
            tags=["security", "analysis", "code-quality", "bandit", "pylint"],
        )
        
        logger.info(f"Created manifest with {len(self.manifest.capabilities)} capabilities")
        return self.manifest
    
    async def register_with_registry(self, registry_url: str = "http://localhost:8081"):
        """Register with the OAI Network registry."""
        if not self.manifest:
            self.create_manifest(registry_url)
        
        async with OAIClient(registry_url=registry_url, identity=self.identity.identity) as client:
            result = await client.register_agent(self.manifest)
            logger.info(f"Registered with registry: {result}")
            return result
    
    async def start_heartbeat(self, registry_url: str = "http://localhost:8081", interval: int = 60):
        """Send periodic heartbeats."""
        while True:
            try:
                async with OAIClient(registry_url=registry_url, identity=self.identity.identity) as client:
                    await client.heartbeat()
                    logger.debug(f"Heartbeat sent for {self.identity.identity.did}")
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            await asyncio.sleep(interval)
    
    async def run_async(self):
        """Run the agent server asynchronously."""
        logger.info(f"Starting {self.name} on port {self.port}")
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def cleanup(self):
        """Cleanup MCP connection."""
        await self._close_mcp_connection()


async def main():
    """Main entry point for the code analysis agent."""
    agent = CodeAnalysisAgent(name="Code Analysis Agent", port=8003)
    
    # Generate identity
    agent.generate_identity()
    
    # Create manifest
    agent.create_manifest()
    
    # Save identity for CLI use
    import json
    with open("code_analysis_identity.json", "w") as f:
        json.dump(agent.identity.model_dump(mode='json'), f, indent=2)
    logger.info("Saved identity to code_analysis_identity.json")
    
    # Register with registry (if running)
    try:
        await agent.register_with_registry()
    except Exception as e:
        logger.warning(f"Could not register with registry: {e}")
    
    # Start heartbeat in background
    asyncio.create_task(agent.start_heartbeat())
    
    # Run server
    try:
        await agent.run_async()
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())


async def create_code_analysis_agent(identity: Optional[AgentIdentity] = None) -> CodeAnalysisAgent:
    """Factory function to create a CodeAnalysisAgent."""
    return CodeAnalysisAgent(identity=identity)