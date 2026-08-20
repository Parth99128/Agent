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
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--config', type=click.Path(exists=True), help='Config file path')
@click.pass_context
def cli(ctx, verbose, config):
    """OAI Network CLI - Open Agent Identity Network"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    if config:
        ctx.obj['config'] = config
        click.echo(f"Loaded config from {config}")


@cli.group()
def identity():
    """Identity management commands"""
    pass


@identity.command()
@click.option('--name', required=True, help='Agent name')
@click.option('--key-type', type=click.Choice(['Ed25519', 'RSA'], case_sensitive=False), default='Ed25519', help='Key type to generate')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml'], case_sensitive=False), default='json', help='Output format')
def generate(name: str, key_type: str, output: Optional[str], output_format: str):
    """Generate a new agent identity"""
    generator = IdentityGenerator()
    identity_doc = generator.generate_identity(name=name, key_type=key_type)
    
    data = identity_doc.model_dump(mode='json')
    
    if output:
        if output_format == 'yaml':
            try:
                import yaml
                with open(output, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False)
            except ImportError:
                click.echo("PyYAML not installed, falling back to JSON")
                with open(output, 'w') as f:
                    json.dump(data, f, indent=2)
        else:
            with open(output, 'w') as f:
                json.dump(data, f, indent=2)
        click.echo(f"Identity saved to {output}")
    else:
        if output_format == 'yaml':
            try:
                import yaml
                click.echo(yaml.dump(data, default_flow_style=False))
            except ImportError:
                click.echo(json.dumps(data, indent=2))
        else:
            click.echo(json.dumps(data, indent=2))
    
    click.echo(f"DID: {identity_doc.identity.did}")
    click.echo(f"Key Type: {key_type}")
    click.echo(f"Name: {name}")


@identity.command()
@click.option('--input', 'input_file', required=True, type=click.Path(), help='Identity file path')
def show(input_file: str):
    """Show identity details"""
    if not Path(input_file).exists():
        click.echo(f"File not found: {input_file}", err=True)
        sys.exit(1)
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    identity_doc = IdentityDocument(**data)
    click.echo(f"DID: {identity_doc.identity.did}")
    click.echo(f"Name: {identity_doc.identity.metadata.get('name', 'Unknown')}")
    click.echo(f"Key Type: {identity_doc.identity.key_type}")
    click.echo(f"Created: {identity_doc.identity.created_at}")
    click.echo(f"Public Key: {identity_doc.identity.public_key[:50]}...")


@cli.group()
def agent():
    """Agent management commands"""
    pass


@agent.command()
@click.option('--identity', 'identity_file', type=click.Path(exists=True), required=True, help='Identity file')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def register(identity_file: str, registry_url: str):
    """Register an agent with the registry"""
    async def _register():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            click.echo(f"Registering agent {identity.did} with registry at {registry_url}...")
            try:
                from ..core.capabilities.models import AgentManifest
                manifest = AgentManifest(
                    identity=identity,
                    name=identity.metadata.get('name', 'Unknown'),
                    description='Registered via CLI',
                    version='1.0.0',
                    capabilities=[],
                    endpoints=[],
                )
                result = await client.register_agent(manifest)
                click.echo(json.dumps(result, indent=2))
            except Exception as e:
                click.echo(f"Registration failed: {e}")
    
    asyncio.run(_register())


@agent.command()
@click.option('--identity', 'identity_file', type=click.Path(exists=True), required=True, help='Identity file')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
@click.option('--status', default='healthy', help='Agent status')
def heartbeat(identity_file: str, registry_url: str, status: str):
    """Send heartbeat to registry"""
    async def _heartbeat():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            click.echo(f"Sending heartbeat for {identity.did}...")
            try:
                result = await client.heartbeat(status=status)
                click.echo(json.dumps(result, indent=2))
            except Exception as e:
                click.echo(f"Heartbeat failed: {e}")
    
    asyncio.run(_heartbeat())


@agent.command()
@click.option('--identity', 'identity_file', type=click.Path(exists=True), required=True, help='Identity file')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def unregister(identity_file: str, registry_url: str):
    """Unregister agent from registry"""
    async def _unregister():
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            click.echo(f"Unregistering agent {identity.did}...")
            try:
                result = await client.unregister_agent()
                click.echo(f"Unregistered: {result}")
            except Exception as e:
                click.echo(f"Unregister failed: {e}")
    
    asyncio.run(_unregister())


@cli.group()
def discover():
    """Agent discovery commands"""
    pass


@discover.command('find')
@click.option('--query', default='', help='Search query')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
@click.option('--capability', help='Filter by capability name')
@click.option('--type', 'capability_type', help='Filter by capability type')
@click.option('--tags', help='Comma-separated tags')
@click.option('--min-trust', type=float, default=0.0, help='Minimum trust score')
@click.option('--verified-only', is_flag=True, help='Only verified agents')
@click.option('--max-results', 'max_results', type=int, default=20, help='Maximum results')
def find_agent(query: str, registry_url: str, capability: Optional[str], capability_type: Optional[str],
               tags: Optional[str], min_trust: float, verified_only: bool, max_results: int):
    """Find agents matching a natural language query"""
    async def _find():
        async with OAIClient(registry_url=registry_url) as client:
            click.echo(f"Discovering agents with query: {query}...")
            try:
                results = await client.discover(
                    query=query,
                    capability=capability,
                    capability_type=capability_type,
                    tags=tags.split(',') if tags else None,
                    min_trust_score=min_trust,
                    verified_only=verified_only,
                    max_results=max_results,
                )
                
                if not results:
                    click.echo("No agents found")
                    return
                
                for i, result in enumerate(results, 1):
                    click.echo(f"\n{i}. {result.agent_name} ({result.agent_did})")
                    click.echo(f"   Description: {result.agent_description}")
                    click.echo(f"   Trust Score: {result.trust_score:.2f}")
                    click.echo(f"   Verified: {'Yes' if result.verified else 'No'}")
            except Exception as e:
                click.echo(f"Discovery failed: {e}")
    
    asyncio.run(_find())


@discover.command()
@click.option('--did', 'agent_did', required=True, help='Agent DID')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def get(agent_did: str, registry_url: str):
    """Get agent details by DID"""
    async def _get():
        async with OAIClient(registry_url=registry_url) as client:
            click.echo(f"Discovering agent {agent_did}...")
            try:
                agent = await client.get_agent(agent_did)
                if agent:
                    click.echo(json.dumps(agent.model_dump(mode='json'), indent=2))
                else:
                    click.echo(f"Agent not found: {agent_did}")
            except Exception as e:
                click.echo(f"Discovery failed: {e}")
    
    asyncio.run(_get())


@cli.group()
def delegate():
    """Delegation commands"""
    pass


@delegate.command()
@click.option('--identity', 'identity_file', type=click.Path(exists=True), required=True, help='Identity file')
@click.option('--capability', required=True, help='Capability to delegate')
@click.option('--input', 'input_data', help='JSON input data')
@click.option('--input-file', type=click.Path(exists=True), help='Input data file')
@click.option('--preferred-agent', help='Preferred agent DID')
@click.option('--max-depth', type=int, default=3, help='Maximum delegation depth')
@click.option('--timeout', type=int, default=60, help='Timeout in seconds')
@click.option('--max-price', type=float, help='Maximum price')
@click.option('--max-latency', type=int, help='Maximum latency in ms')
@click.option('--min-trust', type=float, help='Minimum trust score')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def run(identity_file: str, capability: str, input_data: Optional[str], input_file: Optional[str],
        preferred_agent: Optional[str], max_depth: int, timeout: int,
        max_price: Optional[float], max_latency: Optional[int], min_trust: Optional[float],
        registry_url: str):
    """Delegate a task to another agent"""
    async def _delegate():
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
            click.echo(f"Delegating task with capability '{capability}'...")
            try:
                result = await client.delegate(
                    task=capability,
                    capability=capability,
                    input_data=data,
                    preferred_agent=preferred_agent,
                    max_depth=max_depth,
                    timeout=timeout,
                )
                click.echo(json.dumps(result.model_dump(mode='json'), indent=2))
            except Exception as e:
                click.echo(f"Delegation failed: {e}")
    
    asyncio.run(_delegate())


@cli.group()
def trust():
    """Trust and reputation commands"""
    pass


@trust.command()
@click.option('--did', 'agent_did', required=True, help='Agent DID')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def score(agent_did: str, registry_url: str):
    """Get trust score for an agent"""
    async def _score():
        async with OAIClient(registry_url=registry_url) as client:
            click.echo(f"Getting trust score for {agent_did}...")
            try:
                score = await client.get_trust_score(agent_did)
                if score:
                    click.echo(json.dumps(score.model_dump(mode='json'), indent=2))
                else:
                    click.echo(f"No trust score found for {agent_did}")
            except Exception as e:
                click.echo(f"Trust score query failed: {e}")
    
    asyncio.run(_score())


@trust.command()
@click.option('--from-did', 'from_did', required=True, help='Reviewer DID')
@click.option('--to-did', 'target_did', required=True, help='Target agent DID')
@click.option('--rating', type=click.IntRange(1, 5), required=True, help='Rating (1-5)')
@click.option('--comment', default='', help='Feedback comment')
@click.option('--capability', help='Capability related to feedback')
@click.option('--interaction-id', help='Interaction ID')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def feedback(from_did: str, target_did: str, rating: int, comment: str, capability: Optional[str],
             interaction_id: Optional[str], registry_url: str):
    """Submit feedback for an agent"""
    async def _feedback():
        async with OAIClient(registry_url=registry_url, identity=None) as client:
            click.echo(f"Submitting feedback from {from_did} to {target_did}...")
            try:
                event = await client.submit_feedback(
                    target_did=target_did,
                    rating=rating,
                    comment=comment,
                    interaction_id=interaction_id,
                )
                click.echo(json.dumps(event.model_dump(mode='json'), indent=2))
            except Exception as e:
                click.echo(f"Feedback submission failed: {e}")
    
    asyncio.run(_feedback())


@cli.group()
def negotiate():
    """Negotiation commands"""
    pass


@negotiate.command()
@click.option('--identity', 'identity_file', type=click.Path(exists=True), required=True, help='Identity file')
@click.option('--responder', 'counterparty_did', required=True, help='Responder DID')
@click.option('--template', default='standard', help='Negotiation template')
@click.option('--params', 'params_json', help='JSON negotiation parameters')
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
def start(identity_file: str, counterparty_did: str, template: str,
          params_json: Optional[str], registry_url: str):
    """Start a negotiation session"""
    async def _negotiate():
        terms = {}
        if params_json:
            terms = json.loads(params_json)
        
        with open(identity_file, 'r') as f:
            identity_data = json.load(f)
        identity = IdentityDocument(**identity_data).identity
        
        async with OAIClient(registry_url=registry_url, identity=identity) as client:
            click.echo(f"Starting negotiation with {counterparty_did}...")
            try:
                session = await client.negotiate(
                    counterparty_did=counterparty_did,
                    terms=terms,
                    template=template,
                )
                click.echo(json.dumps(session.model_dump(mode='json'), indent=2))
            except Exception as e:
                click.echo(f"Negotiation failed: {e}")
    
    asyncio.run(_negotiate())


@cli.command()
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
@click.option('--gateway', 'gateway_url', default='http://localhost:8080', help='Gateway URL')
def health(registry_url: str, gateway_url: str):
    """Check health of OAI Network services"""
    async def _health():
        async with OAIClient(registry_url=registry_url, gateway_url=gateway_url) as client:
            click.echo("Checking health of OAI Network services...")
            try:
                results = await client.health_check()
                click.echo(json.dumps(results, indent=2))
            except Exception as e:
                click.echo(f"Health check failed: {e}")
    
    asyncio.run(_health())


@cli.command()
@click.option('--registry', 'registry_url', default='http://localhost:8081', help='Registry URL')
@click.option('--gateway', 'gateway_url', default='http://localhost:8080', help='Gateway URL')
@click.option('--identity', 'identity_file', type=click.Path(exists=True), help='Identity file')
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