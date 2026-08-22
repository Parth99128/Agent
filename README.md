# OAI Network

**Open phonebook + rulebook + trust system for AI agents** — discovery, identity, and delegation over MCP & A2A.

[![CI](https://github.com/Parth99128/Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Parth99128/Agent/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

OAI Network is a framework for building interoperable AI agent ecosystems. It provides:

- **🔍 Discovery** — Registry for agent registration, heartbeats, and capability-based search
- **🆔 Identity** — DID-based agent identities with cryptographic verification
- **🤝 Delegation** — Task delegation with trust-aware routing and policy enforcement
- **🛡️ Trust & Reputation** — Wilson score interval, time decay, recency-weighted scoring
- **📜 Policy Engine** — Rule-based access control with budget tracking
- **🔄 Protocols** — Native MCP (Model Context Protocol) and A2A (Agent-to-Agent) support
- **📊 Observability** — Structured JSON logging, trace_id propagation, Prometheus metrics
- **🔒 Security** — Input validation, rate limiting, adversarial test coverage (29 tests)

---

## Quickstart

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for full stack)
- Ollama (optional, for local AI routing): `curl -fsSL https://ollama.com/install.sh | sh`

### Installation

```bash
# Clone the repository
git clone https://github.com/Parth99128/Agent.git
cd Agent

# Install with all optional dependencies (includes httpx for live demo)
pip install -e ".[all]"

# Or install minimal dependencies + demo requirements
pip install -e ".[demo]"

# Or install minimal dependencies only
pip install -e .
```

### Run the Full Stack (Docker Compose)

```bash
# Start all services: registry, gateway, agents, Prometheus, Grafana
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
sleep 30

# Verify services are healthy
curl http://localhost:8081/health  # Registry
curl http://localhost:8080/health  # Gateway
curl http://localhost:8001/health  # Translator Agent
curl http://localhost:8002/health  # Summarizer Agent
curl http://localhost:8003/health  # Code Analysis Agent
```

### Run the Live Demo

```bash
# With Docker stack running (services on localhost ports)
python live_demo.py
```

The demo shows:
1. Registry & Gateway health checks
2. Code Analysis Agent registration
3. REST-based agent discovery
4. A2A protocol communication
5. CLI-based discovery
6. Agent Card endpoint (A2A interoperability)

> **Note:** The live demo runs on the host and requires `httpx`. Install with `pip install -e ".[demo]"` or `pip install -e ".[all]"` before running.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        OAI Network                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Registry   │◄───│   Gateway    │◄───│   Agents     │      │
│  │  (Port 8081) │    │  (Port 8080) │    │  (8001-8003) │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Core Services (Shared Library)              │  │
│  │  Discovery │ Identity │ Delegation │ Trust │ Policy      │  │
│  │  Negotiation │ Routing │ Observability │ Security        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  PostgreSQL  │    │    Redis     │    │   Ollama     │      │
│  │  (Trust DB)  │    │  (Cache)     │    │  (Local LLM) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Port | Description |
|-----------|------|-------------|
| **Registry** | 8081 | Agent registration, discovery, trust history |
| **Gateway** | 8080 | Request routing, policy enforcement, load balancing |
| **Translator Agent** | 8001 | Multi-language translation (20 languages) |
| **Summarizer Agent** | 8002 | Text summarization (5 styles) |
| **Code Analysis Agent** | 8003 | Bandit/Pylint security & quality analysis |
| **Prometheus** | 9090 | Metrics collection |
| **Grafana** | 3000 | Dashboards & visualization |

---

## CLI Usage

```bash
# Create a new agent identity
oai create-identity --name "My Agent" --capabilities "analysis,translation"

# Register an agent with the registry
oai register --identity ./my_identity.json --name "My Agent" --registry http://localhost:8081

# Discover agents by capability
oai find-agent --capability "translation" --registry http://localhost:8081

# Delegate a task to an agent
oai delegate --task "Translate hello to Spanish" --capability "translation" --registry http://localhost:8081

# Check agent trust score
oai trust-score --agent-did <DID> --registry http://localhost:8081

# View trust history
oai trust-history --agent-did <DID> --registry http://localhost:8081
```

### CLI Options

All commands support:
- `--registry` — Registry URL (default: http://localhost:8081)
- `--identity` — Path to identity JSON file
- `--name` — Agent name for registration

---

## Python SDK

```python
from oai_network import OAIClient

# Create client
client = OAIClient(registry_url="http://localhost:8081")

# Create identity
identity = client.create_identity(name="My Agent", capabilities=["analysis"])

# Register agent
agent_card = client.register(identity, name="My Agent")

# Discover agents
agents = client.discover_agents(capability="translation")

# Delegate task
result = client.delegate_task(
    task="Analyze this Python file for security issues",
    capability="code_analysis",
    target_agent_did=agents[0].did
)

# Get trust score
trust = client.get_trust_score(agent_did=agents[0].did)
print(f"Trust score: {trust.score:.2f} (confidence: {trust.confidence:.2f})")

# Close client
client.close()
```

---

## TypeScript SDK

```typescript
import { OAIClient } from '@oai-network/sdk';

const client = new OAIClient({ registryUrl: 'http://localhost:8081' });

// Create identity
const identity = await client.createIdentity({
  name: 'My Agent',
  capabilities: ['translation']
});

// Register agent
const agentCard = await client.register(identity, 'My Agent');

// Discover agents
const agents = await client.discoverAgents({ capability: 'translation' });

// Delegate task
const result = await client.delegateTask({
  task: 'Translate hello to French',
  capability: 'translation',
  targetAgentDid: agents[0].did
});

console.log('Result:', result);
```

---

## Agent Development

### Creating an MCP Agent

```python
from oai_network.agents import BaseMCPAgent
from mcp import Server

class MyAgent(BaseMCPAgent):
    def __init__(self):
        super().__init__(
            name="my-agent",
            description="Custom agent description",
            capabilities=["custom_capability"]
        )
        self.server = Server("my-agent")
        self._register_tools()
    
    def _register_tools(self):
        @self.server.call_tool()
        async def my_tool(arg: str) -> str:
            return f"Processed: {arg}"
    
    async def handle_a2a_request(self, method: str, params: dict) -> dict:
        if method == "my_capability":
            return await self.server.call_tool("my_tool", {"arg": params["input"]})
        raise ValueError(f"Unknown method: {method}")

# Run the agent
if __name__ == "__main__":
    agent = MyAgent()
    agent.run(host="0.0.0.0", port=8004)
```

### Agent Card (A2A Interoperability)

Every agent exposes an Agent Card at `/.well-known/agent-card.json`:

```json
{
  "name": "Code Analysis Agent",
  "description": "Analyzes code for security and quality issues",
  "version": "1.0.0",
  "capabilities": ["code_analysis", "security_audit", "quality_metrics"],
  "endpoints": {
    "a2a": "http://localhost:8003/a2a",
    "mcp": "stdio"
  },
  "authentication": {
    "type": "none"
  }
}
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OAI_REGISTRY_URL` | `http://localhost:8081` | Registry endpoint |
| `OAI_GATEWAY_URL` | `http://localhost:8080` | Gateway endpoint |
| `OAI_DATABASE_URL` | `sqlite:///trust.db` | Trust database |
| `OAI_REDIS_URL` | `redis://localhost:6379` | Cache backend |
| `OAI_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `OAI_LOG_LEVEL` | `INFO` | Logging level |
| `OAI_POLICY_FILE` | `policy.yaml` | Policy configuration |

### Policy Configuration

```yaml
# policy.yaml
rules:
  - name: "max_delegation_depth"
    condition: "delegation.depth <= 3"
    action: "deny"
  - name: "min_trust_score"
    condition: "trust.score >= 0.5"
    action: "deny"
  - name: "blocked_capabilities"
    condition: "capability in ['dangerous_action']"
    action: "deny"

budgets:
  default: 100
  per_agent:
    "did:example:agent1": 50
```

---

## Observability

### Prometheus Metrics

All services expose `/metrics` endpoint:

```bash
# Registry metrics
curl http://localhost:8081/metrics

# Gateway metrics
curl http://localhost:8080/metrics

# Agent metrics
curl http://localhost:8003/metrics
```

Key metrics:
- `oai_requests_total` — Total requests by service, method, status
- `oai_request_duration_seconds` — Request latency histogram
- `oai_active_requests` — Currently active requests
- `oai_policy_denials_total` — Policy denial count
- `oai_agent_success_rate` — Agent success rate
- `oai_delegation_total` — Delegation count by outcome
- `oai_trust_score` — Current trust scores

### Structured Logging

All services emit JSON logs with trace_id propagation:

```json
{
  "timestamp": "2026-08-22T10:30:00.123Z",
  "level": "INFO",
  "service": "registry",
  "trace_id": "abc123",
  "span_id": "def456",
  "message": "Agent registered",
  "agent_did": "did:example:agent1",
  "capabilities": ["translation"]
}
```

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin):
- **OAI Network Overview** — System health, request rates, latency
- **Agent Performance** — Per-agent success rates, trust scores
- **Delegation Flow** — Delegation chains, depth, outcomes

---

## Testing

```bash
# Run all tests
pytest src/oai_network/tests/ -v

# Run with coverage
pytest src/oai_network/tests/ --cov=oai_network --cov-report=html

# Run specific test module
pytest src/oai_network/tests/test_trust.py -v

# Run security tests
pytest src/oai_network/tests/test_security.py -v
```

---

## Project Structure

```
src/oai_network/
├── agents/                 # MCP-based agents
│   ├── code_analysis_agent.py
│   ├── code_analysis_mcp_server.py
│   ├── summarizer_agent.py
│   ├── translation_mcp_server.py
│   └── translator_agent.py
├── cli/                    # Command-line interface
│   └── main.py
├── core/                   # Core framework
│   ├── capabilities/       # Capability matching & validation
│   ├── delegation/         # Delegation manager & policies
│   ├── discovery/          # Agent discovery & caching
│   ├── identity/           # DID-based identity
│   ├── negotiation/        # Negotiation protocols
│   ├── observability/      # Logging, metrics, tracing
│   ├── policy/             # Policy engine
│   ├── routing/            # Query classification (Ollama)
│   └── trust/              # Trust calculator & store
├── gateway/                # API Gateway server
├── protocols/              # A2A & MCP protocol implementations
├── registry/               # Registry server
├── sdk/                    # Python & TypeScript SDKs
└── tests/                  # Test suite (328 tests)
```

---

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development environment setup
- Coding standards (ruff, type hints)
- Testing guidelines
- Pull request process
- Release process

---

## Roadmap

- [x] Stage 1-6: Core framework (discovery, identity, delegation, trust, policy, negotiation)
- [x] Stage 7: Local AI routing with Ollama
- [x] Stage 8: Real agents via MCP (Code Analysis, Summarizer, Translator)
- [x] Stage 9: A2A interoperability (Agent Card)
- [x] Stage 10: Real trust & reputation (Wilson score, decay)
- [x] Stage 11: Security hardening (29 adversarial tests)
- [x] Stage 12: Observability (JSON logging, Prometheus, Grafana)
- [x] Stage 13: CI/CD & Packaging (GitHub Actions, Docker, PyPI)
- [ ] Stage 14: Documentation (this README, CONTRIBUTING, architecture docs)
- [ ] Stage 15: Go distributed (cross-machine deployment)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Links

- **Repository**: https://github.com/Parth99128/Agent
- **Issues**: https://github.com/Parth99128/Agent/issues
- **Changelog**: https://github.com/Parth99128/Agent/blob/main/CHANGELOG.md
- **Documentation**: https://github.com/Parth99128/Agent/wiki