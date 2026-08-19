"""
OAI Network CLI

Command-line interface for the OAI Network.
"""

import click
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from ..core.identity.generator import IdentityGenerator
from ..core.identity.models import IdentityDocument
from ..sdk.python.client import OAIClient


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """OAI Network CLI - Open Agent Identity Network"""
    pass


@cli.group()
def identity():
    """Identity management commands"""
    pass


@identity.command()
@click.argument('name')
@click.option('--key-type', type=click.Choice(['Ed25519', 'RSA']), default='Ed25519', help='Key type to generate')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def generate(name: str, key_type: str, output: Optional[str]):
    """Generate a new agent identity"""
    generator = IdentityGenerator()
    identity_doc = generator.generate_identity(name=name, key_type=key_type)
    
    if output:
        with open(output, 'w') as f:
            json.dump(identity_doc.model_dump(mode='json'), f, indent=2)
        click.echo(f"Identity saved to {output}")
    else:
        click.echo(json.dumps(identity_doc.model_dump(mode='json'), indent=2))


@identity.command()
@click.argument('identity_file', type=click.Path(exists=True))
def show(identity_file: str):
    """Show identity details"""
    with open(identity_file, 'r') as f:
        data = json.load(f)
    
    identity_doc = IdentityDocument(**data)
    click.echo(f"DID: {identity_doc.identity.did}")
    click.echo(f"Name: {identity_doc.identity.metadata.get('name', 'Unknown')}")
    click.echo(f"Key Type: {identity_doc.identity.key_type}")
    click.echo(f"Created: {identity_doc.identity.created_at}")
    click.echo(f"Public Key: {identity_doc.identity.public_key_pem[:50]}...")


@cli.group()
def agent():
    """Agent management commands"""
    pass


@agent.command()
@click.argument('manifest_file', type=click.Path(exists=True))
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), help='Identity file for authentication')
def register(manifest_file: str, registry_url: str, identity_file: Optional[str]):
    """Register an agent with the registry"""
    async def _register():
        # Load manifest
        with open(manifest_file, 'r') as f:
            manifest_data = json.load(f)
        
        # Load identity if provided
        identity = None
        if identity_file:
            with open(identity_file, 'r') as f:
                identity_data = json.load(f)
            identity = IdentityDocument(**identity_data).identity
        
        # Create client and register
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            # Convert manifest data to AgentManifest
            from ..core.capabilities.models import AgentManifest, Capability, ServiceEndpoint
            from ..core.identity.models import AgentIdentity
            
            manifest = AgentManifest(**manifest_data)
            result = await client.register_agent(manifest)
            click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_register())


@agent.command()
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), required=True, help='Identity file')
def heartbeat(registry_url: str, identity_file: str):
    """Send heartbeat to registry"""
    async def _heartbeat():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            result = await client.heartbeat()
            click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_heartbeat())


@agent.command()
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), required=True, help='Identity file')
def unregister(registry_url: str, identity_file: str):
    """Unregister agent from registry"""
    async def _unregister():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            result = await client.unregister_agent()
            click.echo(f"Unregistered: {result}")
    
    asyncio.run(_unregister())


@cli.group()
def discover():
    """Agent discovery commands"""
    pass


@discover.command('find')
@click.argument('query')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--capability', help='Filter by capability name')
@click.option('--capability-type', help='Filter by capability type')
@click.option('--tags', help='Comma-separated tags')
@click.option('--min-trust', type=float, default=0.0, help='Minimum trust score')
@click.option('--verified-only', is_flag=True, help='Only verified agents')
@click.option('--limit', type=int, default=20, help='Maximum results')
def find_agent(query: str, registry_url: str, capability: Optional[str], capability_type: Optional[str],
               tags: Optional[str], min_trust: float, verified_only: bool, limit: int):
    """Find agents matching a natural language query"""
    async def _find():
        async with OAIClient(registry_url=registry_url) as client:
            results = await client.discover(
                query=query,
                capability=capability,
                capability_type=capability_type,
                tags=tags.split(',') if tags else None,
                min_trust_score=min_trust,
                verified_only=verified_only,
                max_results=limit,
            )
            
            if not results:
                click.echo("No agents found")
                return
            
            for i, result in enumerate(results, 1):
                click.echo(f"\n{i}. {result.name} ({result.agent_did})")
                click.echo(f"   Description: {result.description}")
                click.echo(f"   Capabilities: {', '.join(result.capabilities)}")
                click.echo(f"   Trust Score: {result.trust_score:.2f}")
                click.echo(f"   Verified: {'Yes' if result.identity_verified else 'No'}")
                click.echo(f"   Status: {result.status}")
                if result.relevance_score:
                    click.echo(f"   Relevance: {result.relevance_score:.2f}")
    
    asyncio.run(_find())


@discover.command()
@click.argument('agent_did')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
def get(agent_did: str, registry_url: str):
    """Get agent details by DID"""
    async def _get():
        async with OAIClient(registry_url=registry_url) as client:
            agent = await client.get_agent(agent_did)
            if agent:
                click.echo(json.dumps(agent.model_dump(mode='json'), indent=2))
            else:
                click.echo(f"Agent not found: {agent_did}")
    
    asyncio.run(_get())


@cli.group()
def delegate():
    """Delegation commands"""
    pass


@delegate.command()
@click.argument('task')
@click.argument('capability')
@click.option('--input', 'input_data', help='JSON input data')
@click.option('--input-file', type=click.Path(exists=True), help='Input data file')
@click.option('--preferred-agent', help='Preferred agent DID')
@click.option('--max-depth', type=int, default=3, help='Maximum delegation depth')
@click.option('--timeout', type=int, default=60, help='Timeout in seconds')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), required=True, help='Identity file')
def run(task: str, capability: str, input_data: Optional[str], input_file: Optional[str],
        preferred_agent: Optional[str], max_depth: int, timeout: int,
        registry_url: str, identity_file: str):
    """Delegate a task to another agent"""
    async def _delegate():
        # Parse input data
        data = {}
        if input_data:
            data = json.loads(input_data)
        elif input_file:
            with open(input_file, 'r') as f:
                data = json.load(f)
        
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            result = await client.delegate(
                task=task,
                capability=capability,
                input_data=data,
                preferred_agent=preferred_agent,
                max_depth=max_depth,
                timeout=timeout,
            )
            click.echo(json.dumps(result.model_dump(mode='json'), indent=2))
    
    asyncio.run(_delegate())


@cli.group()
def trust():
    """Trust and reputation commands"""
    pass


@trust.command()
@click.argument('agent_did')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
def score(agent_did: str, registry_url: str):
    """Get trust score for an agent"""
    async def _score():
        async with OAIClient(registry_url=registry_url) as client:
            score = await client.get_trust_score(agent_did)
            if score:
                click.echo(json.dumps(score.model_dump(mode='json'), indent=2))
            else:
                click.echo(f"No trust score found for {agent_did}")
    
    asyncio.run(_score())


@trust.command()
@click.argument('target_did')
@click.argument('rating', type=float)
@click.option('--comment', default='', help='Feedback comment')
@click.option('--interaction-id', help='Interaction ID')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), required=True, help='Identity file')
def feedback(target_did: str, rating: float, comment: str, interaction_id: Optional[str],
             registry_url: str, identity_file: str):
    """Submit feedback for an agent"""
    async def _feedback():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            event = await client.submit_feedback(
                target_did=target_did,
                rating=rating,
                comment=comment,
                interaction_id=interaction_id,
            )
            click.echo(json.dumps(event.model_dump(mode='json'), indent=2))
    
    asyncio.run(_feedback())


@cli.group()
def negotiate():
    """Negotiation commands"""
    pass


@negotiate.command()
@click.argument('counterparty_did')
@click.argument('terms_file', type=click.Path(exists=True))
@click.option('--template', default='standard', help='Negotiation template')
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--identity-file', type=click.Path(exists=True), required=True, help='Identity file')
def start(counterparty_did: str, terms_file: str, template: str,
          registry_url: str, identity_file: str):
    """Start a negotiation session"""
    async def _negotiate():
        with open(terms_file, 'r') as f:
            terms = json.load(f)
        
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            session = await client.negotiate(
                counterparty_did=counterparty_did,
                terms=terms,
                template=template,
            )
            click.echo(json.dumps(session.model_dump(mode='json'), indent=2))
    
    asyncio.run(_negotiate())


@cli.command()
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--gateway-url', default='http://localhost:8080', help='Gateway URL')
def health(registry_url: str, gateway_url: str):
    """Check health of OAI Network services"""
    async def _health():
        async with OAIClient(registry_url=registry_url, gateway_url=gateway_url) as client:
            results = await client.health_check()
            click.echo(json.dumps(results, indent=2))
    
    asyncio.run(_health())


@cli.command()
@click.option('--registry-url', default='http://localhost:8081', help='Registry URL')
@click.option('--gateway-url', default='http://localhost:8080', help='Gateway URL')
@click.option('--identity-file', type=click.Path(exists=True), help='Identity file')
def interactive(registry_url: str, gateway_url: str, identity_file: Optional[str]):
    """Start interactive REPL"""
    click.echo("OAI Network Interactive Mode")
    click.echo("Type 'help' for commands, 'exit' to quit")
    
    identity = None
    if identity_file:
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        click.echo(f"Loaded identity: {identity.did}")
    
    client = OAIClient(registry_url=registry_url, gateway_url=gateway_url, identity=identity)
    
    async def run_repl():
        await client.__aenter__()
        try:
            while True:
                try:
                    cmd = input("\noai> ").strip()
                    if cmd in ('exit', 'quit'):
                        break
                    elif cmd == 'help':
                        click.echo("Commands: find <query>, get <did>, delegate <task> <capability>, trust <did>, health, exit")
                    elif cmd.startswith('find '):
                        query = cmd[5:]
                        results = await client.discover(query=query)
                        for r in results[:5]:
                            click.echo(f"  {r.name} ({r.agent_did}) - {r.trust_score:.2f}")
                    elif cmd.startswith('get '):
                        did = cmd[4:]
                        agent = await client.get_agent(did)
                        if agent:
                            click.echo(f"  {agent.name} - {agent.description}")
                        else:
                            click.echo("  Not found")
                    elif cmd == 'health':
                        results = await client.health_check()
                        click.echo(json.dumps(results, indent=2))
                    else:
                        click.echo(f"Unknown command: {cmd}")
                except EOFError:
                    break
                except Exception as e:
                    click.echo(f"Error: {e}")
        finally:
            await client.close()
    
    asyncio.run(run_repl())


if __name__ == '__main__':
    cli()