# Building OAI Network: A Complete Walkthrough

*From zero to a production-ready AI agent framework in 15 stages*

---

## Introduction

When we started building OAI Network, we had a simple vision: **AI agents should be able to find each other, trust each other, and work together — just like humans do on the internet.**

Today, that vision is reality. OAI Network is a complete framework for building interoperable AI agent ecosystems, featuring:

- **Discovery** — A registry where agents advertise capabilities
- **Identity** — Cryptographic DIDs for verifiable agent identity
- **Delegation** — Task routing with policy enforcement
- **Trust** — Reputation scoring with Wilson intervals and time decay
- **Protocols** — Native MCP and A2A support
- **Observability** — Structured logging, Prometheus metrics, Grafana dashboards
- **Security** — 29 adversarial tests covering injection, traversal, DoS

This post walks through the entire journey — from the first failing test to a production-ready system deployed with Docker Compose and GitHub Actions CI/CD.

---

## Stage 1-6: The Core Framework

### The Foundation

We started with the fundamentals: **identity, discovery, delegation, trust, policy, and negotiation**.

```python
# Core identity - every agent gets a DID and Ed25519 keypair
from oai_network.core.identity import IdentityGenerator, IdentityVerifier

generator = IdentityGenerator()
identity = generator.create_identity(name="My Agent", capabilities=["translation"])

# DID looks like: did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK
print(identity.did)
print(identity.public_key)
```

**Key insight**: We used DIDs (Decentralized Identifiers) from the start. This wasn't premature optimization — it meant every design decision afterward had to work with cryptographic identity, not just string IDs.

### Discovery Service

The registry is the "phonebook." Agents register, heartbeat, and get discovered:

```python
from oai_network.core.discovery import DiscoveryService

service = DiscoveryService(registry_url="http://localhost:8081")

# Register
agent_card = await service.register(identity, name="Translator")

# Discover by capability
agents = await service.discover_agents(capability="translation")
```

### Delegation with Policy

The delegation manager handles the "rulebook" — who can delegate to whom, with what budget, and how deep:

```python
from oai_network.core.delegation import DelegationManager, DelegationPolicy

policy = DelegationPolicy(
    max_depth=3,
    allowed_capabilities=["translation", "summarization"],
    blocked_capabilities=["admin", "delete"],
    min_trust_score=0.5,
    max_budget=100
)

manager = DelegationManager(registry_client, policy=policy)
result = await manager.delegate(
    task="Translate this document to Spanish",
    capability="translation",
    delegator_did=my_did
)
```

---

## Stage 7: Local AI Routing with Ollama

### Why Local AI?

Cloud APIs are great, but for a framework about **agent autonomy**, we needed local inference. Enter [Ollama](https://ollama.com) — run LLMs locally with a simple API.

### Query Classifier

We built a `QueryClassifier` that routes natural language to the right capability:

```python
from oai_network.core.routing import QueryClassifier

classifier = QueryClassifier(ollama_url="http://localhost:11434", model="llama3.2:3b")

# Classify a user query
result = await classifier.classify("analyze this Python file for security issues")
# Returns: {"capability": "code_analysis", "confidence": 0.92, "reasoning": "..."}

# Falls back to keyword matching if Ollama unavailable
result = await classifier.classify("translate hello to French")
# Returns: {"capability": "translation", "confidence": 0.95, "reasoning": "keyword match"}
```

**Architecture decision**: The classifier caches results and has a keyword fallback. This means the system works even without Ollama — it's just smarter with it.

---

## Stage 8: Real Agents via MCP

### Model Context Protocol (MCP)

MCP is the emerging standard for tool/function calling. We built three production agents using MCP servers:

#### 1. Code Analysis Agent (Bandit + Pylint)

```python
# MCP Server exposes tools
@server.call_tool()
async def analyze_repo(path: str) -> dict:
    # Runs Bandit (security) + Pylint (quality)
    return {"security_issues": [...], "quality_metrics": {...}}

@server.call_tool()
async def analyze_file(path: str) -> dict:
    ...

@server.call_tool()
async def get_security_issues(path: str) -> list:
    ...

@server.call_tool()
async def get_quality_metrics(path: str) -> dict:
    ...
```

**Critical learning**: MCP stdio connections hang if reused. We create **fresh connections per request**:

```python
async def _call_mcp_tool(self, tool_name: str, args: dict) -> dict:
    # Fresh connection every time - no hanging!
    async with stdio_client(self._get_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, args)
```

#### 2. Summarizer Agent (5 Styles)

```python
styles = ["concise", "bullet_points", "detailed", "executive", "technical"]

@server.call_tool()
async def summarize(text: str, style: str = "concise", max_length: int = 500) -> str:
    prompt = f"Summarize in {style} style (max {max_length} words):\n\n{text}"
    return await ollama.generate(model="llama3.2:3b", prompt=prompt)
```

#### 3. Translator Agent (20 Languages)

```python
languages = ["Spanish", "French", "German", "Chinese", "Japanese", "Korean", 
             "Portuguese", "Italian", "Russian", "Arabic", "Hindi", "Dutch",
             "Polish", "Turkish", "Swedish", "Norwegian", "Danish", "Finnish",
             "Hebrew", "Thai"]

@server.call_tool()
async def translate(text: str, target_language: str, source_language: str = "auto") -> str:
    prompt = f"Translate from {source_language} to {target_language}:\n\n{text}"
    return await ollama.generate(model="llama3.2:3b", prompt=prompt)
```

---

## Stage 9: A2A Interoperability

### Agent Card Standard

A2A (Agent-to-Agent) protocol requires every agent to expose an **Agent Card** at `/.well-known/agent-card.json`:

```json
{
  "name": "Code Analysis Agent",
  "description": "Analyzes code for security and quality issues using Bandit and Pylint",
  "version": "1.0.0",
  "capabilities": ["code_analysis", "security_audit", "quality_metrics"],
  "endpoints": {
    "a2a": "http://localhost:8003/a2a",
    "mcp": "stdio"
  },
  "authentication": {
    "type": "none"
  },
  "skills": [
    {
      "name": "analyze_repo",
      "description": "Analyze entire repository for security and quality issues",
      "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}
    }
  ]
}
```

This makes OAI Network agents **interoperable with any A2A-compliant system** — Google's A2A, Microsoft's AutoGen, etc.

---

## Stage 10: Real Trust & Reputation

### The Trust Problem

Simple averages don't work for trust:
- New agent with 1 success (100%) shouldn't outrank veteran with 99/100 (99%)
- Old successes shouldn't count as much as recent ones
- Need confidence intervals, not point estimates

### Wilson Score Interval

We use the **Wilson score interval** (95% confidence) — the same math Reddit uses for comment ranking:

```python
from oai_network.core.trust import TrustCalculator

calculator = TrustCalculator(half_life_hours=168)  # 1 week half-life

# Record events
await store.record_event(TrustEvent(
    agent_did=agent_did,
    event_type=TrustEventType.INTERACTION_SUCCESS,
    counterparty_did=my_did,
    metadata={"task": "translation", "latency_ms": 150}
))

# Compute score
score = calculator.compute_score(agent_did, events)
# TrustScore(score=0.87, confidence=0.92, lower_bound=0.82, upper_bound=0.91, sample_count=47)
```

### Time Decay

Trust decays exponentially — a success from 6 months ago matters less than yesterday:

```python
# Weight = 0.5 ^ (age_hours / half_life_hours)
# Half-life of 168 hours (1 week) means:
# - 1 week old: 50% weight
# - 2 weeks old: 25% weight
# - 1 month old: ~6% weight
```

### Confidence = Volume × Recency

```python
confidence = min(1.0, (effective_samples / MIN_SAMPLES) * recency_factor)
# MIN_SAMPLES = 10 (need at least 10 interactions for full confidence)
# recency_factor = average weight of recent events
```

This prevents **low-volume agents from gaming the system** and ensures **stale reputations fade**.

---

## Stage 11: Security Hardening

### 29 Adversarial Tests

We wrote comprehensive security tests covering:

| Category | Tests | Examples |
|----------|-------|----------|
| **Injection** | 8 | SQLi in query params, command injection, LDAP injection |
| **Path Traversal** | 4 | `../../../etc/passwd`, URL encoding bypasses |
| **XSS** | 5 | Script tags in JSON, Unicode bypasses, CSP evasion |
| **DoS** | 6 | Oversized payloads, deep nesting, regex ReDoS |
| **Auth/Z** | 6 | Token replay, privilege escalation, IDOR |

```python
# Example: SQL injection test
@pytest.mark.asyncio
async def test_sql_injection_in_discovery(client):
    # Attempt SQL injection in capability parameter
    malicious = "translation'; DROP TABLE agents; --"
    response = await client.post("/discover", json={"capability": malicious})
    assert response.status_code == 422  # Validation error, not 500
    # Verify database intact
    agents = await client.get("/agents")
    assert len(agents) > 0
```

### Defense in Depth

1. **Pydantic validation** on all endpoints
2. **Rate limiting** (token bucket per IP)
3. **Request size limits** (configurable, default 10MB)
4. **Security headers** (CSP, HSTS, X-Frame-Options)
5. **Input sanitization** for file paths, shell commands

---

## Stage 12: Observability

### Structured JSON Logging

Every log entry is JSON with trace correlation:

```json
{
  "timestamp": "2026-08-22T10:30:00.123Z",
  "level": "INFO",
  "service": "gateway",
  "trace_id": "abc123def456",
  "span_id": "span789",
  "message": "Delegation completed",
  "delegation_id": "del_abc123",
  "delegator_did": "did:key:z6Mk...",
  "target_did": "did:key:z6Mk...",
  "capability": "translation",
  "duration_ms": 245,
  "outcome": "success"
}
```

### Trace Propagation

Using Python's `contextvars` for automatic trace_id/span_id propagation across async boundaries:

```python
from oai_network.core.observability import get_trace_id, set_trace_id

# In middleware - extract or generate trace_id
trace_id = request.headers.get("x-trace-id") or generate_trace_id()
set_trace_id(trace_id)

# Anywhere in the call chain - automatically available
logger.info("Processing request", extra={"trace_id": get_trace_id()})
```

### Prometheus Metrics

Every service exposes `/metrics`:

```prometheus
# HELP oai_requests_total Total HTTP requests
# TYPE oai_requests_total counter
oai_requests_total{service="gateway",method="POST",endpoint="/route",status="200"} 1523

# HELP oai_request_duration_seconds Request latency
# TYPE oai_request_duration_seconds histogram
oai_request_duration_seconds_bucket{service="registry",le="0.1"} 1200
oai_request_duration_seconds_bucket{service="registry",le="0.5"} 1450

# HELP oai_trust_score Current trust score
# TYPE oai_trust_score gauge
oai_trust_score{agent_did="did:key:z6Mk..."} 0.87
```

### Grafana Dashboards

Pre-built dashboards for:
- **System Overview**: Request rates, latency, error rates
- **Agent Performance**: Per-agent success rates, trust scores
- **Delegation Flow**: Delegation chains, depth distribution, outcomes

---

## Stage 13: CI/CD & Packaging

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[all,dev]"
      - run: ruff check src/
      - run: pytest src/oai_network/tests/ -v --cov=oai_network

  docker:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose build
      - run: docker-compose up -d
      - run: sleep 10 && python live_demo.py
      - run: docker-compose down

  publish:
    needs: docker
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

### Docker Compose (Production-Ready)

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: oai_network
      POSTGRES_USER: oai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U oai"]
      interval: 10s

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  registry:
    build:
      context: .
      dockerfile: docker/Dockerfile.registry
    ports: ["8081:8081"]
    environment:
      DATABASE_URL: postgresql://oai:${POSTGRES_PASSWORD}@postgres/oai_network
      REDIS_URL: redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  gateway:
    build:
      context: .
      dockerfile: docker/Dockerfile.gateway
    ports: ["8080:8080"]
    environment:
      REGISTRY_URL: http://registry:8081
      REDIS_URL: redis://redis:6379
    depends_on: [registry, redis]

  # Agents...
  translator:
    build:
      context: .
      dockerfile: docker/Dockerfile.agent
    ports: ["8001:8001"]
    environment:
      REGISTRY_URL: http://registry:8081
      OLLAMA_URL: http://host.docker.internal:11434

  # Observability
  prometheus:
    image: prom/prometheus:v2.47
    ports: ["9090:9090"]
    volumes:
      - ./docker/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:10.1
    ports: ["3000:3000"]
    volumes:
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./docker/grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
```

### PyPI Packaging

```toml
# pyproject.toml
[project]
name = "oai-network"
version = "0.1.0"
description = "Open phonebook + rulebook + trust system for AI agents"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4", "pytest-cov>=4.0"]
mcp = ["mcp>=2.0.0"]
ollama = ["ollama>=0.3.0"]
agents = ["bandit>=1.7", "pylint>=3.0"]
observability = ["prometheus-client>=0.19", "structlog>=24.0"]
all = ["mcp>=2.0.0", "ollama>=0.3.0", "bandit>=1.7", "pylint>=3.0", "prometheus-client>=0.19", "structlog>=24.0"]

[project.scripts]
oai = "oai_network.cli:main"
oai-registry = "oai_network.registry.server:main"
oai-gateway = "oai_network.gateway.server:main"
oai-translator = "oai_network.examples.translator_agent:main"
oai-summarizer = "oai_network.examples.summarizer_agent:main"
oai-code-analysis = "oai_network.agents.code_analysis_agent:main"
```

---

## Stage 14: Documentation (This Post!)

We've now created comprehensive documentation:

1. **README.md** — Project overview, quickstart, architecture, API reference
2. **CONTRIBUTING.md** — Development setup, coding standards, PR process
3. **docs/architecture.md** — Detailed system design with diagrams
4. **docs/good-first-issues.md** — 20+ beginner-friendly issues
5. **This blog post** — Complete walkthrough

---

## Live Demo: See It In Action

```bash
# Clone and start
git clone https://github.com/Parth99128/Agent.git
cd Agent
docker-compose up -d

# Run the demo
python live_demo.py
```

**Output**:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    OAI NETWORK LIVE DEMONSTRATION                            ║
║         Open phonebook + rulebook + trust system for AI agents              ║
╚══════════════════════════════════════════════════════════════════════════════╝

🔧 STEP 1: Health Checks
──────────────────────────────────────────────────────────────────────────────
✅ Registry healthy at http://localhost:8081
   Status: healthy | Agents registered: 0
✅ Gateway healthy at http://localhost:8080
   Status: healthy

🔧 STEP 2: Register Code Analysis Agent
──────────────────────────────────────────────────────────────────────────────
✅ Code Analysis Agent registered
   DID: did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK
   Name: Code Analysis Agent
   Capabilities: ['code_analysis', 'security_audit', 'quality_metrics']

🔧 STEP 3: REST Discovery
──────────────────────────────────────────────────────────────────────────────
🔍 Discovering agents with capability: code_analysis
✅ Found 1 agent(s):
   - Code Analysis Agent (did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK)
     Trust: 0.85 | Status: ACTIVE

🔧 STEP 4: A2A Protocol Communication
──────────────────────────────────────────────────────────────────────────────
📡 Calling agent via A2A protocol...
✅ A2A Response received:
   Security Issues Found: 3
   Quality Score: 8.5/10
   Files Analyzed: 12

🔧 STEP 5: CLI Discovery
──────────────────────────────────────────────────────────────────────────────
$ oai find-agent --capability code_analysis --registry http://localhost:8081
✅ Found: Code Analysis Agent (trust: 0.85)

🔧 STEP 6: Agent Card (A2A Interoperability)
──────────────────────────────────────────────────────────────────────────────
📋 Agent Card retrieved from /.well-known/agent-card.json
   Name: Code Analysis Agent
   Version: 1.0.0
   Capabilities: code_analysis, security_audit, quality_metrics
   A2A Endpoint: http://localhost:8003/a2a
   MCP Endpoint: stdio

╔══════════════════════════════════════════════════════════════════════════════╗
║                         DEMO COMPLETE ✅                                     ║
║  All systems operational: Registry, Gateway, Agents, A2A, CLI, Trust        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## What's Next: Stage 15 — Go Distributed

The framework works beautifully locally. Next up: **cross-machine deployment**.

### Planned for Stage 15:
- Deploy to free-tier VMs (Railway, Render, Fly.io)
- Configure cross-machine agent registration
- Demonstrate full flow across the internet
- Federation: multiple registries sharing trust data
- DNS-based agent discovery

---

## Key Lessons Learned

### 1. Test-Driven Means Exact API Matching
> "The tests are the spec. If the test expects `--registry`, you build `--registry`, not `--registry-url`."

We had 328 tests written first. Every implementation decision was driven by making those tests pass. This forced clean, consistent APIs.

### 2. MCP Requires Fresh Connections
> "Reusing stdio connections causes hangs. Fresh connection per request = reliability."

This was our biggest MCP debugging session. The fix was simple but non-obvious.

### 3. Wilson Score Prevents Gaming
> "Simple averages let new agents game the system. Wilson intervals require evidence."

The math is battle-tested (Reddit, Stack Overflow). Don't reinvent reputation systems.

### 4. Time Decay Needs Recency in Confidence
> "Decay the score, but also decay the confidence. Old data = uncertain data."

Our confidence formula combines volume AND recency — this was a key insight.

### 5. Structured Logging Enables Distributed Tracing
> "JSON logs with trace_id = debuggable distributed systems."

Once we had trace_id propagation, debugging multi-service flows became trivial.

### 6. Budget Enforcement Needs Body Inspection
> "Policy checks on headers aren't enough. You need to parse the request body for cost."

Our policy engine extracts `cost` from JSON bodies to enforce budgets.

---

## Get Started Today

```bash
# 1. Clone
git clone https://github.com/Parth99128/Agent.git
cd Agent

# 2. Install
pip install -e ".[all]"

# 3. Run full stack
docker-compose up -d

# 4. Try the demo
python live_demo.py

# 5. Build your own agent
# See CONTRIBUTING.md and docs/good-first-issues.md
```

---

## Links

- **GitHub**: https://github.com/Parth99128/Agent
- **Documentation**: https://github.com/Parth99128/Agent/wiki
- **Issues**: https://github.com/Parth99128/Agent/issues
- **Changelog**: https://github.com/Parth99128/Agent/blob/main/CHANGELOG.md

---

## Acknowledgments

Built with:
- **FastAPI** — Modern, fast web framework
- **Pydantic** — Data validation using Python type hints
- **MCP SDK** — Model Context Protocol implementation
- **Ollama** — Local LLM inference
- **Prometheus/Grafana** — Observability stack
- **Bandit/Pylint** — Python security and quality analysis
- **Click** — Composable command line interfaces

---

*OAI Network is MIT licensed. Contributions welcome!*

---

**Next up**: Stage 15 — deploying agents across the internet. Follow the repo to watch the journey continue! 🚀