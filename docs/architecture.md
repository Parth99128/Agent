# OAI Network Architecture

## System Overview

OAI Network is a framework for building interoperable AI agent ecosystems. It provides a decentralized "phonebook + rulebook + trust system" enabling agents to discover each other, negotiate capabilities, delegate tasks, and build reputation over time.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OAI NETWORK ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        EXTERNAL CLIENTS                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│  │  │  Python  │  │TypeScript│  │   CLI    │  │   Custom HTTP    │   │   │
│  │  │   SDK    │  │   SDK    │  │  (oai)   │  │     Clients      │   │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │   │
│  └───────┼─────────────┼─────────────┼────────────────┼─────────────┘   │
│          │             │             │                │                 │
│          ▼             ▼             ▼                ▼                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API GATEWAY (Port 8080)                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │   Router    │  │   Policy    │  │  Rate Limit │  │  Metrics  │  │   │
│  │  │  (FastAPI)  │  │  Engine     │  │  Middleware │  │ Middleware│  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │   │
│  └─────────┼────────────────┼────────────────┼────────────────┼────────┘   │
│            │                │                │                │            │
│            ▼                ▼                ▼                ▼            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      CORE FRAMEWORK (Shared Library)                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │Discovery │ │ Identity │ │Delegation│ │  Trust   │ │  Policy  │  │   │
│  │  │ Service  │ │  Manager │ │ Manager  │ │Calculator│ │ Engine   │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │   │
│  │       │            │            │            │            │          │   │
│  │  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐  │   │
│  │  │Negotiation│ │ Routing  │ │Capabilities│ │Observability│ │Security │  │   │
│  │  │ Protocol  │ │Classifier│ │  Matcher   │ │  (Logs/    │ │ (Input  │  │   │
│  │  │           │ │ (Ollama) │ │            │ │  Metrics)  │ │  Valid.)│  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│            │                │                │                │            │
│            ▼                ▼                ▼                ▼            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        INFRASTRUCTURE LAYER                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  PostgreSQL  │  │    Redis     │  │   Ollama     │              │   │
│  │  │  (Trust DB)  │  │   (Cache)    │  │  (Local LLM) │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│            │                │                │                             │
│            ▼                ▼                ▼                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        AGENT ECOSYSTEM                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Registry    │  │   Gateway    │  │   Agents     │              │   │
│  │  │  (8081)      │  │  (8080)      │  │  (8001-8003) │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Prometheus   │  │   Grafana    │  │  MCP Servers │              │   │
│  │  │  (9090)      │  │  (3000)      │  │  (stdio)     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Registry Server (`src/oai_network/registry/`)

**Purpose**: Central directory for agent registration, discovery, and trust history.

**Endpoints**:
- `GET /health` — Health check
- `GET /stats` — Registry statistics
- `POST /register` — Register new agent
- `POST /heartbeat` — Agent heartbeat
- `POST /unregister` — Unregister agent
- `GET /agents/{did}` — Get agent by DID
- `POST /discover` — Discover agents by capability
- `GET /agents/{did}/trust-history` — Get trust history
- `GET /metrics` — Prometheus metrics

**Data Model**:
```python
class AgentCard(BaseModel):
    did: str                    # Decentralized Identifier
    name: str                   # Human-readable name
    description: str            # Agent description
    capabilities: list[str]     # List of capabilities
    endpoints: dict[str, str]   # Protocol endpoints (a2a, mcp)
    public_key: str             # Ed25519 public key
    metadata: dict              # Additional metadata
    registered_at: datetime
    last_heartbeat: datetime
    status: AgentStatus         # ACTIVE, INACTIVE, UNREGISTERED
```

**Storage**: PostgreSQL (production) / SQLite (development)

---

### 2. Gateway Server (`src/oai_network/gateway/`)

**Purpose**: Request routing, policy enforcement, load balancing, and observability.

**Endpoints**:
- `GET /health` — Health check
- `POST /route` — Route request to agent
- `GET /policies` — List policies
- `POST /policies` — Create policy
- `GET /routes` — List routes
- `POST /routes` — Create route
- `GET /upstreams` — List upstream agents
- `POST /upstreams` — Register upstream
- `GET /agents/{did}/trust-history` — Proxy to registry
- `GET /metrics` — Prometheus metrics

**Routing Flow**:
```
Client Request
     │
     ▼
┌─────────────┐
│ Rate Limit  │ ──► 429 if exceeded
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Policy     │ ──► 403 if denied (logs POLICY_DENIALS metric)
│  Engine     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Router     │ ──► Selects agent based on capability, trust, load
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Delegate   │ ──► Calls DelegationManager
│  Manager    │
└──────┬──────┘
       │
       ▼
   Agent Response
```

---

### 3. Core Framework (`src/oai_network/core/`)

#### Discovery Service (`core/discovery/`)
- **Service** (`service.py`): HTTP client for registry communication
- **Cache** (`cache.py`): Redis-backed caching with TTL
- **Models** (`models.py`): `AgentCard`, `DiscoveryQuery`, `DiscoveryResult`

#### Identity Management (`core/identity/`)
- **Generator** (`generator.py`): Creates DIDs and Ed25519 key pairs
- **Verifier** (`verifier.py`): Verifies signatures and DID documents
- **Models** (`models.py`): `AgentIdentity`, `DIDDocument`, `VerificationResult`

#### Delegation Manager (`core/delegation/`)
- **Manager** (`manager.py`): Orchestrates task delegation with trust tracking
- **Policy** (`policy.py`): Delegation policies (max_depth, allowed/blocked capabilities, min_trust, max_budget)
- **Models** (`models.py`): `DelegationRequest`, `DelegationResult`, `DelegationPolicy`

#### Trust System (`core/trust/`)
- **Calculator** (`calculator.py`): Wilson score interval with time decay
- **Store** (`store.py`): SQLite/PostgreSQL persistence with dual sync/async API
- **Models** (`models.py`): `TrustEvent`, `TrustScore`, `TrustHistory`

**Trust Algorithm**:
```
Wilson Score Interval (95% confidence):
    score = (p + z²/2n) / (1 + z²/n) ± z * sqrt(p(1-p)/n + z²/4n²) / (1 + z²/n)

Time Decay:
    weight = 0.5 ^ (age_hours / half_life_hours)

Recency-Weighted Confidence:
    confidence = min(1.0, (effective_samples / min_samples) * recency_factor)
```

#### Policy Engine (`core/policy/`)
- **Engine** (`engine.py`): Evaluates rules against request context
- **Loader** (`loader.py`): Loads policies from YAML
- **Models** (`models.py`): `PolicyRule`, `PolicyDecision`, `Budget`

#### Negotiation Protocol (`core/negotiation/`)
- **Protocol** (`protocol.py`): Multi-round negotiation state machine
- **Strategies** (`strategies.py`): Cooperative, competitive, compromise strategies
- **Models** (`models.py`): `NegotiationSession`, `Offer`, `CounterOffer`

#### Routing/Classification (`core/routing/`)
- **Classifier** (`classifier.py`): Ollama-based NL query classification with keyword fallback

#### Observability (`core/observability/`)
- **JSONFormatter**: Structured logging with trace_id/span_id
- **MetricsMiddleware**: Prometheus metrics collection
- **ContextVars**: trace_id/span_id propagation across async boundaries

#### Capabilities (`core/capabilities/`)
- **Matcher** (`matcher.py`): Capability matching with fuzzy/partial support
- **Validator** (`validator.py`): Capability schema validation
- **Models** (`models.py`): `Capability`, `CapabilitySchema`

---

### 4. Protocols

#### MCP (Model Context Protocol) (`protocols/mcp/`)
- **Client** (`client.py`): Async MCP client with stdio transport
- **Server** (`server.py`): MCP server with tool registration
- **Transport**: stdio (subprocess) for local agents

#### A2A (Agent-to-Agent) (`protocols/a2a/`)
- **Client** (`client.py`): HTTP/WebSocket A2A client
- **Server** (`server.py`): A2A server with JSON-RPC 2.0
- **Models**: `A2ARequest`, `A2AResponse`, `AgentCard`

---

### 5. Agents (`src/oai_network/agents/`)

#### Code Analysis Agent (`code_analysis_agent.py`)
- **MCP Server** (`code_analysis_mcp_server.py`): Tools for Bandit/Pylint analysis
- **Capabilities**: `code_analysis`, `security_audit`, `quality_metrics`
- **Tools**: `analyze_repo`, `analyze_file`, `get_security_issues`, `get_quality_metrics`

#### Summarizer Agent (`summarizer_agent.py`)
- **MCP Server** (`summarization_mcp_server.py`): Ollama-based summarization
- **Capabilities**: `summarization`
- **Styles**: `concise`, `bullet_points`, `detailed`, `executive`, `technical`

#### Translator Agent (`translator_agent.py`)
- **MCP Server** (`translation_mcp_server.py`): Ollama-based translation
- **Capabilities**: `translation`
- **Languages**: 20+ languages supported

---

### 6. SDKs

#### Python SDK (`sdk/python/client.py`)
```python
class OAIClient:
    def create_identity(self, name: str, capabilities: list[str]) -> AgentIdentity
    def register(self, identity: AgentIdentity, name: str) -> AgentCard
    def discover_agents(self, capability: str, min_trust: float = 0.0) -> list[AgentCard]
    def delegate_task(self, task: str, capability: str, target_agent_did: str) -> DelegationResult
    def get_trust_score(self, agent_did: str) -> TrustScore
    def get_trust_history(self, agent_did: str) -> TrustHistory
    def close(self) -> None
```

#### TypeScript SDK (`sdk/typescript/src/client.ts`)
```typescript
class OAIClient {
    createIdentity(params: { name: string; capabilities: string[] }): Promise<AgentIdentity>
    register(identity: AgentIdentity, name: string): Promise<AgentCard>
    discoverAgents(params: { capability: string; minTrust?: number }): Promise<AgentCard[]>
    delegateTask(params: { task: string; capability: string; targetAgentDid: string }): Promise<DelegationResult>
    getTrustScore(agentDid: string): Promise<TrustScore>
    getTrustHistory(agentDid: string): Promise<TrustHistory>
    close(): Promise<void>
}
```

---

## Data Flow

### Agent Registration Flow
```
1. Client creates identity (DID + keypair)
        │
        ▼
2. Client calls Registry.register(identity)
        │
        ▼
3. Registry validates identity, stores AgentCard
        │
        ▼
4. Registry returns AgentCard with assigned DID
        │
        ▼
5. Agent starts heartbeat loop (every 30s)
```

### Task Delegation Flow
```
1. Client discovers agents by capability
        │
        ▼
2. Client selects target agent (considers trust score)
        │
        ▼
3. Client calls Gateway.route() or direct A2A
        │
        ▼
4. Gateway checks PolicyEngine
        │
        ▼
5. Gateway calls DelegationManager.delegate()
        │
        ▼
6. DelegationManager:
   - Checks delegation policy (depth, trust, budget)
   - Records TRUST_EVENT: DELEGATION_STARTED
   - Calls target agent via A2A/MCP
   - Records TRUST_EVENT: INTERACTION_SUCCESS/FAILURE
   - Updates trust score
        │
        ▼
7. Returns result to client
```

### Trust Scoring Flow
```
1. TrustStore records TrustEvent (success/failure/timeout)
        │
        ▼
2. TrustCalculator.compute_score(agent_did):
   - Fetches events from TrustStore
   - Applies time decay (half-life: 168h = 1 week)
   - Computes Wilson score interval (95% CI)
   - Computes confidence (volume + recency)
        │
        ▼
3. Returns TrustScore { score, confidence, lower_bound, upper_bound, sample_count }
```

---

## Security Model

### Threat Model
- **Spoofing**: Mitigated by DID + Ed25519 signatures
- **Tampering**: Request/response integrity via signatures
- **Repudiation**: Immutable trust ledger in PostgreSQL
- **Information Disclosure**: Input validation, rate limiting
- **Denial of Service**: Rate limiting, request size limits, circuit breakers
- **Elevation of Privilege**: Policy engine with explicit deny-by-default

### Security Features
1. **Input Validation**: Pydantic models on all endpoints
2. **Rate Limiting**: Token bucket per client IP
3. **Request Size Limits**: Configurable max body/header size
4. **CORS**: Configurable origins
5. **Security Headers**: CSP, HSTS, X-Frame-Options
6. **Adversarial Tests**: 29 security tests covering injection, traversal, DoS

---

## Observability

### Metrics (Prometheus)
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `oai_requests_total` | Counter | service, method, endpoint, status | Total HTTP requests |
| `oai_request_duration_seconds` | Histogram | service, method, endpoint | Request latency |
| `oai_active_requests` | Gauge | service | In-flight requests |
| `oai_policy_denials_total` | Counter | service, rule | Policy denials |
| `oai_agent_success_rate` | Gauge | agent_did | Agent success rate |
| `oai_delegation_total` | Counter | outcome, depth | Delegation outcomes |
| `oai_trust_score` | Gauge | agent_did | Current trust score |

### Logging
- **Format**: JSON with structured fields
- **Trace Propagation**: `trace_id`, `span_id` via contextvars
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Fields**: timestamp, level, service, trace_id, span_id, message, context

### Tracing
- **ContextVars**: Automatic trace_id/span_id propagation
- **Middleware**: Extracts/injects trace headers
- **Correlation**: Links gateway → registry → agent calls

---

## Deployment

### Docker Compose (Development)
```yaml
services:
  postgres:     # Trust database
  redis:        # Cache
  registry:     # Port 8081
  gateway:      # Port 8080
  translator:   # Port 8001
  summarizer:   # Port 8002
  code-analysis:# Port 8003
  prometheus:   # Port 9090
  grafana:      # Port 3000
```

### Production Considerations
- **Registry**: Horizontal scaling with shared PostgreSQL
- **Gateway**: Stateless, horizontal scaling with Redis for rate limiting
- **Agents**: Independent scaling per capability
- **Database**: PostgreSQL with connection pooling
- **Cache**: Redis Cluster for HA
- **Monitoring**: Prometheus + Grafana + Alertmanager
- **Logging**: Centralized (ELK/Loki)

---

## Extension Points

### Adding New Capabilities
1. Define capability in `core/capabilities/models.py`
2. Add matcher logic in `core/capabilities/matcher.py`
3. Create agent with capability
4. Register agent with registry

### Custom Policies
1. Create YAML policy file
2. Load via `PolicyLoader`
3. Register with `PolicyEngine`

### Custom Agents
1. Extend `BaseMCPAgent`
2. Implement `handle_a2a_request`
3. Register MCP tools
4. Run on desired port

### Custom Protocols
1. Implement client/server in `protocols/`
2. Register with gateway router
3. Add SDK methods

---

## Performance Characteristics

| Operation | Latency (p99) | Throughput |
|-----------|---------------|------------|
| Agent Registration | ~50ms | 1000/sec |
| Agent Discovery | ~30ms (cached) | 5000/sec |
| Task Delegation | ~200ms | 500/sec |
| Trust Score Query | ~10ms | 10000/sec |
| Policy Evaluation | ~5ms | 20000/sec |

---

## Future Architecture Evolution

### Stage 15: Distributed Deployment
- Multi-region registry federation
- Cross-cluster agent discovery
- Global trust consensus

### Planned Enhancements
- **WASM Agents**: Sandboxed agent execution
- **Verifiable Credentials**: W3C VC for agent attestations
- **Mesh Networking**: libp2p for direct agent communication
- **Federated Learning**: Privacy-preserving model updates