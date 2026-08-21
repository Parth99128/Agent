"""
Example Agent: Summarizer

A simple text summarization agent that demonstrates the OAI Network framework.
"""

import asyncio
import json
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.models import IdentityDocument, KeyType
from oai_network.core.capabilities.models import AgentManifest, Capability, ServiceEndpoint, CapabilityPricing
from oai_network.sdk.python.client import OAIClient


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SummarizationRequest(BaseModel):
    """Request to summarize text."""
    text: str
    max_length: Optional[int] = 100
    style: Optional[str] = "concise"  # concise, bullet_points, detailed


class SummarizationResponse(BaseModel):
    """Summarization response."""
    summary: str
    original_length: int
    summary_length: int
    compression_ratio: float


class SummarizerAgent:
    """A simple text summarization agent."""
    
    def __init__(self, name: str = "Summarizer Agent", port: int = 8002):
        self.name = name
        self.port = port
        self.identity: Optional[IdentityDocument] = None
        self.manifest: Optional[AgentManifest] = None
        self.app = FastAPI(title=f"OAI Network - {name}")
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.name}
        
        @self.app.get("/agent-card")
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
            
            if method == "summarize":
                return await self._handle_summarize(params, request_id)
            elif method == "capabilities":
                return await self._handle_capabilities(request_id)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
    
    async def _handle_summarize(self, params: dict, request_id: str) -> dict:
        """Handle summarization request."""
        try:
            text = params.get("text", "")
            max_length = params.get("max_length", 100)
            style = params.get("style", "concise")
            
            # Simple mock summarization (in real agent, call LLM API)
            if style == "bullet_points":
                sentences = text.split(". ")
                summary = "\n".join([f"• {s.strip()}" for s in sentences[:3] if s.strip()])
            elif style == "detailed":
                summary = f"Summary: {text[:max_length]}... (detailed analysis would go here)"
            else:  # concise
                words = text.split()
                summary = " ".join(words[:max_length//5]) + "..." if len(words) > max_length//5 else text
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "summary": summary,
                    "original_length": len(text),
                    "summary_length": len(summary),
                    "compression_ratio": len(summary) / max(len(text), 1)
                }
            }
        except Exception as e:
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
        
        # Define summarization capability
        summarization_cap = Capability(
            name="summarization",
            type="nlp",
            description="Summarize long text into concise form",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "max_length": {"type": "integer", "default": 100},
                    "style": {"type": "string", "enum": ["concise", "bullet_points", "detailed"], "default": "concise"}
                },
                "required": ["text"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "original_length": {"type": "integer"},
                    "summary_length": {"type": "integer"},
                    "compression_ratio": {"type": "number"}
                }
            },
            tags=["nlp", "summarization", "text-processing"],
            pricing=CapabilityPricing(cost_per_call=0.002),
            estimated_latency_ms=800,
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
            description="Text summarization agent with multiple styles",
            version="1.0.0",
            capabilities=[summarization_cap],
            endpoints=[endpoint],
            tags=["nlp", "summarization", "text-processing"],
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


async def main():
    """Main entry point for the summarizer agent."""
    agent = SummarizerAgent(name="Summarizer Agent", port=8002)
    
    # Generate identity
    agent.generate_identity()
    
    # Create manifest
    agent.create_manifest()
    
    # Save identity for CLI use
    import json
    with open("summarizer_identity.json", "w") as f:
        json.dump(agent.identity.model_dump(mode='json'), f, indent=2)
    logger.info("Saved identity to summarizer_identity.json")
    
    # Register with registry (if running)
    try:
        await agent.register_with_registry()
    except Exception as e:
        logger.warning(f"Could not register with registry: {e}")
    
    # Start heartbeat in background
    asyncio.create_task(agent.start_heartbeat())
    
    # Run server
    await agent.run_async()


if __name__ == "__main__":
    asyncio.run(main())