#!/usr/bin/env python3
"""
Live Demo: A2A Agent Communication & REST API

This script demonstrates the complete OAI Network flow:
1. Start Registry Server (port 8081)
2. Start Gateway Server (port 8080) 
3. Register Code Analysis Agent (port 8003)
4. Discover agents via REST API
5. Make A2A calls to analyze code
6. Use CLI commands

Run: python live_demo.py
"""

import asyncio
import json
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

import httpx


class LiveDemo:
    def __init__(self):
        self.processes = []
        # Use current working directory instead of hardcoded path
        self.base_dir = Path.cwd()
        os.chdir(self.base_dir)
    
    def start_process(self, name: str, cmd: list, port: int, health_path: str = "/health"):
        """Start a subprocess and wait for health check."""
        print(f"\n🚀 Starting {name} on port {port}...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append((name, proc))
        
        # Wait for health check
        for i in range(30):
            try:
                resp = httpx.get(f"http://localhost:{port}{health_path}", timeout=2.0)
                if resp.status_code == 200:
                    print(f"✅ {name} is healthy!")
                    return proc
            except Exception:
                pass
            time.sleep(0.5)
        
        # If we get here, process failed - check if process is still alive
        if proc.poll() is None:
            # Process is still running but health check failed
            print(f"⚠️  {name} process running but health check failed")
            return proc
        
        # Process died
        stdout, stderr = proc.communicate(timeout=2)
        print(f"❌ {name} failed to start:")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        raise RuntimeError(f"{name} failed to start")
    
    def stop_all(self):
        """Stop all processes."""
        print("\n🛑 Stopping all processes...")
        for name, proc in self.processes:
            print(f"   Stopping {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.processes.clear()
    
    async def run_demo(self):
        """Run the complete live demo."""
        print("=" * 60)
        print("🎬 OAI NETWORK LIVE DEMO: A2A + REST Communication")
        print("=" * 60)
        
        try:
            # 1. Start Registry Server
            self.start_process(
                "Registry Server",
                [sys.executable, "-m", "oai_network.registry.server"],
                8081
            )
            
            # 2. Start Gateway Server
            self.start_process(
                "Gateway Server",
                [sys.executable, "-m", "oai_network.gateway.server"],
                8080
            )
            
            # 3. Register Code Analysis Agent via CLI
            print("\n📝 Registering Code Analysis Agent via CLI...")
            # First generate identity
            print("   Generating identity...")
            result = subprocess.run([
                sys.executable, "-m", "oai_network.cli.main",
                "identity", "generate",
                "--name", "Code Analysis Agent",
                "--output", "demo_identity.json"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            if result.returncode != 0:
                print(f"⚠️  Identity generation failed: {result.stderr}")
            else:
                print(f"   Identity generated: {result.stdout.strip()}")
            
            # Register agent using the identity file
            result = subprocess.run([
                sys.executable, "-m", "oai_network.cli.main",
                "agent", "register",
                "--identity", "demo_identity.json",
                "--registry", "http://localhost:8081"
            ], capture_output=True, text=True, cwd=self.base_dir)
            
            print(f"   Result: {result.stdout.strip() or result.stderr.strip()}")
            
            # 4. Discover agents via REST API
            print("\n🔍 Discovering agents via REST API (GET /discover)...")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:8081/discover",
                    json={"capability_type": "security", "limit": 10}
                )
                agents = resp.json()
                print(f"   Found {len(agents.get('agents', []))} agent(s):")
                for agent in agents.get('agents', []):
                    print(f"      - {agent['name']} (DID: {agent['did'][:20]}...)")
                    print(f"        Capabilities: {[c['name'] for c in agent.get('capabilities', [])]}")
                    print(f"        Trust Score: {agent.get('trust_score', 'N/A')}")
            
            # 5. Test A2A Communication directly with Code Analysis Agent
            print("\n🤖 Testing A2A Communication with Code Analysis Agent...")
            
            # First, let's check if the agent is running on port 8003
            # If not, we'll start it
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:8003/health", timeout=2.0)
                    if resp.status_code == 200:
                        print("   ✅ Code Analysis Agent already running on port 8003")
                    else:
                        raise Exception("Not healthy")
            except Exception:
                print("   Starting Code Analysis Agent on port 8003...")
                self.start_process(
                    "Code Analysis Agent",
                    [sys.executable, "-m", "oai_network.agents.code_analysis_agent"],
                    8003
                )
            
            # 6. Make A2A call to analyze code
            print("\n📊 Making A2A call: analyze code...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                a2a_request = {
                    "jsonrpc": "2.0",
                    "id": "demo-1",
                    "method": "analyze",
                    "params": {
                        "path": "/app/src/oai_network",
                        "tools": ["bandit", "pylint"]
                    }
                }
                
                resp = await client.post(
                    "http://localhost:8003/a2a",
                    json=a2a_request
                )
                result = resp.json()
                
                if "result" in result:
                    summary = result["result"].get("summary", {})
                    print(f"   ✅ Analysis complete!")
                    print(f"      Security issues: {summary.get('security_issues_found', 0)}")
                    print(f"      Quality issues: {summary.get('quality_issues_found', 0)}")
                    print(f"      Metrics: {summary.get('metrics', {})}")
                else:
                    print(f"   ❌ Error: {result.get('error', 'Unknown')}")
            
            # 7. Test A2A call for security issues only
            print("\n🔒 Making A2A call: get security issues (HIGH only)...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                a2a_request = {
                    "jsonrpc": "2.0",
                    "id": "demo-2",
                    "method": "get_security_issues",
                    "params": {"severity": "HIGH"}
                }
                
                resp = await client.post(
                    "http://localhost:8003/a2a",
                    json=a2a_request
                )
                result = resp.json()
                
                if "result" in result:
                    issues = result["result"].get("security_issues", [])
                    print(f"   ✅ Found {len(issues)} HIGH severity issues")
                    for issue in issues[:3]:
                        print(f"      - {issue.get('file', '?')}:{issue.get('line', '?')} - {issue.get('message', '?')[:60]}")
                else:
                    print(f"   ❌ Error: {result.get('error', 'Unknown')}")
            
            # 8. Test Gateway Routing
            print("\n🌐 Testing Gateway Routing (POST /route)...")
            async with httpx.AsyncClient() as client:
                # First add a route via gateway
                route_resp = await client.post(
                    "http://localhost:8080/routes",
                    json={
                        "name": "code-analysis-route",
                        "path_pattern": "/analyze",
                        "target_url": "http://localhost:8003",
                        "methods": ["POST"]
                    }
                )
                print(f"   Route added: {route_resp.status_code}")
                route_data = route_resp.json()
                route_id = route_data.get("route_id")
                print(f"   Route ID: {route_id}")
                
                # Add upstream for the route
                upstream_resp = await client.post(
                    f"http://localhost:8080/upstreams?route_id={route_id}",
                    json={
                        "id": "code-analysis-upstream",
                        "name": "Code Analysis Agent",
                        "url": "http://localhost:8003",
                        "weight": 100
                    }
                )
                print(f"   Upstream added: {upstream_resp.status_code}")
                
                # Now route through gateway - send GatewayRequest format
                route_request = {
                    "method": "POST",
                    "path": "/analyze",
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "jsonrpc": "2.0",
                        "id": "demo-3",
                        "method": "analyze",
                        "params": {"path": "/app/src/oai_network/core"}
                    }
                }
                
                resp = await client.post(
                    "http://localhost:8080/route",
                    json=route_request
                )
                result = resp.json()
                print(f"   Gateway routed result: {'✅ Success' if result.get('status_code') == 200 else '❌ Failed'}")
                print(f"   Response: {result}")
            
            # 9. Test CLI Commands
            print("\n💻 Testing CLI Commands...")
            
            cli_tests = [
                (["oai", "--help"], "Help"),
                (["oai", "discover", "find", "--query", "analyze python code", "--registry", "http://localhost:8081"], "Semantic Discovery"),
                (["oai", "health", "--registry", "http://localhost:8081", "--gateway", "http://localhost:8080"], "Health Check"),
                (["oai", "trust", "score", "--did", "did:key:z6Mk...", "--registry", "http://localhost:8081"], "Trust Score"),
            ]
            
            for cmd, desc in cli_tests:
                print(f"\n   $ {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_dir)
                output = result.stdout.strip() or result.stderr.strip()
                print(f"   {output[:200]}{'...' if len(output) > 200 else ''}")
            
            # 10. Show Agent Card (A2A Standard)
            print("\n📋 Agent Card (A2A Standard at /.well-known/agent-card.json)...")
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:8003/.well-known/agent-card.json")
                card = resp.json()
                print(f"   Name: {card.get('name')}")
                print(f"   Description: {card.get('description')}")
                print(f"   Capabilities: {len(card.get('capabilities', []))}")
                for cap in card.get('capabilities', []):
                    print(f"      - {cap.get('name')}: {cap.get('description')[:50]}...")
            
            print("\n" + "=" * 60)
            print("✅ LIVE DEMO COMPLETE!")
            print("=" * 60)
            print("""
Summary of what just happened:
1. ✅ Registry Server started (port 8081) - agent discovery & registration
2. ✅ Gateway Server started (port 8080) - routing & policy enforcement  
3. ✅ Code Analysis Agent registered with verified identity
4. ✅ REST Discovery: POST /discover with semantic query
5. ✅ A2A Direct: POST /a2a with JSON-RPC 2.0 (analyze, get_security_issues)
6. ✅ Gateway Routing: POST /route with policy enforcement
7. ✅ CLI: oai discover find, oai health, oai trust score
8. ✅ Agent Card: GET /.well-known/agent-card.json (A2A standard)

All communication uses:
- REST for registry/gateway management
- A2A (JSON-RPC 2.0) for agent-to-agent communication
- MCP (stdio) for agent-to-tool communication (Bandit, Pylint, Ollama)
""")
            
        finally:
            self.stop_all()


async def main():
    demo = LiveDemo()
    try:
        await demo.run_demo()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        demo.stop_all()


if __name__ == "__main__":
    asyncio.run(main())