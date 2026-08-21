#!/usr/bin/env python3
"""
Register a code analyzer agent with proper capabilities for the First Milestone demo.
"""

import asyncio
import json
from oai_network.core.identity.generator import IdentityGenerator
from oai_network.core.identity.models import IdentityDocument, KeyType
from oai_network.core.capabilities.models import (
    AgentManifest, Capability, ServiceEndpoint, CapabilityPricing, TrustMetrics
)
from oai_network.sdk.python.client import OAIClient


async def main():
    # Load or generate identity
    try:
        with open("code_analyzer_identity.json", "r") as f:
            identity_data = json.load(f)
        identity_doc = IdentityDocument(**identity_data)
        identity = identity_doc.identity
        print(f"Loaded existing identity: {identity.did}")
    except FileNotFoundError:
        generator = IdentityGenerator(key_type=KeyType.ED25519)
        identity_doc = generator.generate_identity(name="Code Analyzer Agent")
        identity = identity_doc.identity
        with open("code_analyzer_identity.json", "w") as f:
            json.dump(identity_doc.model_dump(mode='json'), f, indent=2)
        print(f"Generated new identity: {identity.did}")

    # Define code analysis capability
    code_analysis_cap = Capability(
        name="code_analysis",
        type="code",
        description="Analyze Python repositories for bugs, security issues, and code quality",
        input_schema={
            "type": "object",
            "properties": {
                "repository_url": {"type": "string"},
                "analysis_type": {"type": "string", "enum": ["security", "quality", "bugs", "all"], "default": "all"},
                "branch": {"type": "string", "default": "main"}
            },
            "required": ["repository_url"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "issues_found": {"type": "integer"},
                "security_issues": {"type": "integer"},
                "quality_score": {"type": "number"},
                "report": {"type": "string"}
            }
        },
        tags=["code-analysis", "python", "security", "static-analysis"],
        pricing=CapabilityPricing(cost_per_call=0.01),
        estimated_latency_ms=5000,
    )

    # Define endpoint (mock - in real deployment this would be a real A2A endpoint)
    endpoint = ServiceEndpoint(
        url="http://localhost:8003/a2a",
        protocol="a2a",
        description="A2A protocol endpoint for code analysis"
    )

    # Create manifest with trust metrics
    trust_metrics = TrustMetrics(
        score=0.85,
        interaction_count=10,
        success_rate=0.9,
        average_latency_ms=3200,
        positive_feedback=9,
        negative_feedback=1,
        verified_identity=True
    )

    manifest = AgentManifest(
        identity=identity,
        name="Code Analyzer Agent",
        description="Analyzes Python repositories for bugs, security vulnerabilities, and code quality issues",
        version="1.0.0",
        capabilities=[code_analysis_cap],
        endpoints=[endpoint],
        tags=["code-analysis", "python", "security", "static-analysis"],
        trust_metrics=trust_metrics,
        max_delegation_depth=3,
    )

    # Register with registry
    async with OAIClient(registry_url="http://localhost:8081", identity=identity) as client:
        print(f"Registering agent {identity.did} with registry...")
        result = await client.register_agent(manifest)
        print(f"Registration result: {json.dumps(result, indent=2)}")

    print("\n✅ Code Analyzer Agent registered with 'code_analysis' capability!")
    print("Now test: oai discover find --query \"analyze python repository\" --registry http://localhost:8081")


if __name__ == "__main__":
    asyncio.run(main())