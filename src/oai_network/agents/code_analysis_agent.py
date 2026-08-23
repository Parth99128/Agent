"""
Code Analysis Agent

A real agent that wraps the MCP server with Bandit/Pylint tools.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
import uvicorn

from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.models import IdentityDocument, KeyType, AgentIdentity
from oai_network.core.capabilities.models import AgentManifest, Capability, ServiceEndpoint, CapabilityPricing
from oai_network.sdk.python.client import OAIClient
from oai_network.core.observability import (
    setup_json_logging, get_logger, MetricsMiddleware, metrics_endpoint,
    log_request, log_response, log_error, log_agent_action, get_trace_id
)

# MCP client imports
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

# Configure structured logging
logger = setup_json_logging("oai-network-code-analysis-agent")


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
        
        # Add observability middleware
        self.app.add_middleware(MetricsMiddleware, service_name="code-analysis-agent")
        
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
        
        @self.app.get("/metrics")
        async def metrics(request: Request):
            """Prometheus metrics endpoint."""
            return await metrics_endpoint(request)
        
        @self.app.post("/a2a")
        async def a2a_endpoint(request: Request):
            """A2A protocol endpoint."""
            trace_id = get_trace_id()
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")
            
            log_request(logger, "A2A", method, trace_id, agent_did=self.identity.identity.did if self.identity else None)
            
            try:
                if method == "analyze":
                    result = await self._handle_analyze(params, request_id)
                elif method == "get_security_issues":
                    result = await self._handle_get_security_issues(params, request_id)
                elif method == "get_quality_metrics":
                    result = await self._handle_get_quality_metrics(params, request_id)
                elif method == "capabilities":
                    result = await self._handle_capabilities(request_id)
                else:
                    result = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                
                log_response(logger, "A2A", method, 200 if "error" not in result else 500, 0.0, trace_id)
                return result
            except Exception as e:
                log_error(logger, e, trace_id, context={"method": method, "agent": self.name})
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": str(e)}
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
        trace_id = get_trace_id()
        log_agent_action(logger, "analyze", 
                        self.identity.identity.did if self.identity else "unknown", trace_id,
                        path=params.get("path", "."))
        
        try:
            import sys
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp import ClientSession
            
            # Create a fresh connection for each request
            import os
            params_mcp = StdioServerParameters(
                command=sys.executable, 
                args=['-m', 'src.oai_network.agents.code_analysis_mcp_server'],
                cwd=os.getcwd()
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
                    
                    log_agent_action(logger, "analyze_complete", 
                                   self.identity.identity.did if self.identity else "unknown", trace_id,
                                   issues_found=len(result_data.get("security_issues", [])))
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result_data
                    }
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "analyze", "agent": self.name})
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    async def _handle_get_security_issues(self, params: dict, request_id: str) -> dict:
        """Handle get security issues request."""
        trace_id = get_trace_id()
        log_agent_action(logger, "get_security_issues", 
                        self.identity.identity.did if self.identity else "unknown", trace_id,
                        severity=params.get("severity", "ALL"))
        
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
            
            log_agent_action(logger, "get_security_issues_complete", 
                           self.identity.identity.did if self.identity else "unknown", trace_id,
                           issues_returned=len(security_issues))
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result_data
            }
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "get_security_issues", "agent": self.name})
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)}
            }
    
    async def _handle_get_quality_metrics(self, params: dict, request_id: str) -> dict:
        """Handle get quality metrics request."""
        trace_id = get_trace_id()
        log_agent_action(logger, "get_quality_metrics", 
                        self.identity.identity.did if self.identity else "unknown", trace_id)
        
        try:
            # Use stored analysis results
            metrics = self._last_analysis.get("metrics", {})
            quality_issues = self._last_analysis.get("quality_issues", [])
            
            result_data = {
                "metrics": metrics,
                "quality_issues_sample": quality_issues[:20],
            }
            
            log_agent_action(logger, "get_quality_metrics_complete", 
                           self.identity.identity.did if self.identity else "unknown", trace_id)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result_data
            }
        except Exception as e:
            log_error(logger, e, trace_id, context={"method": "get_quality_metrics", "agent": self.name})
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
    
    async def register_with_registry(self, registry_url: str = None, max_retries: int = 10, base_delay: float = 2.0):
        """Register with the OAI Network registry with retry logic."""
        if registry_url is None:
            import os
            registry_url = os.environ.get("REGISTRY_URL", "http://localhost:8081")
        if not self.manifest:
            self.create_manifest(registry_url)
        
        for attempt in range(max_retries):
            try:
                async with OAIClient(registry_url=registry_url, identity=self.identity.identity) as client:
                    result = await client.register_agent(self.manifest)
                    logger.info(f"Registered with registry: {result}")
                    return result
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Registration attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Registration failed after {max_retries} attempts: {e}")
                    raise
    
    async def start_heartbeat(self, registry_url: str = None, interval: int = 60, max_retries: int = 5, base_delay: float = 2.0):
        """Send periodic heartbeats with retry logic."""
        if registry_url is None:
            import os
            registry_url = os.environ.get("REGISTRY_URL", "http://localhost:8081")
        
        while True:
            for attempt in range(max_retries):
                try:
                    async with OAIClient(registry_url=registry_url, identity=self.identity.identity) as client:
                        await client.heartbeat()
                        logger.debug(f"Heartbeat sent for {self.identity.identity.did}")
                        break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Heartbeat attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Heartbeat failed after {max_retries} attempts: {e}")
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