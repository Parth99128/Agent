# Good First Issues

Welcome to OAI Network! This document lists beginner-friendly issues to help you get started contributing. Each issue is designed to be approachable while making a meaningful contribution.

---

## How to Get Started

1. **Pick an issue** from the list below
2. **Comment on the issue** to let others know you're working on it
3. **Fork the repo** and create a feature branch
4. **Make your changes** following our [Contributing Guide](CONTRIBUTING.md)
5. **Submit a PR** — we'll review and merge!

---

## Documentation Issues

### 📝 Improve CLI Help Text
**Labels**: `good first issue`, `documentation`, `cli`
**Difficulty**: ⭐ Easy

The CLI commands could use more descriptive help text and examples.

**Files to modify**:
- `src/oai_network/cli/main.py`

**Tasks**:
- Add examples to each command's help
- Improve description of `--registry`, `--identity`, `--name` options
- Add `--help` output for subcommands

**Example**:
```python
@click.command(help="Register an agent with the registry")
@click.option("--identity", required=True, help="Path to agent identity JSON file (created with 'oai create-identity')")
@click.option("--name", required=True, help="Display name for the agent")
@click.option("--registry", default="http://localhost:8081", help="Registry URL")
def register(identity, name, registry):
    ...
```

---

### 📝 Add Docstrings to Core Modules
**Labels**: `good first issue`, `documentation`, `core`
**Difficulty**: ⭐ Easy

Several internal modules are missing docstrings.

**Files to modify**:
- `src/oai_network/core/capabilities/matcher.py`
- `src/oai_network/core/capabilities/validator.py`
- `src/oai_network/core/negotiation/protocol.py`
- `src/oai_network/core/negotiation/strategies.py`

**Tasks**:
- Add module-level docstrings
- Add class and method docstrings (Google style)
- Document parameters, returns, and exceptions

---

### 📝 Create Architecture Diagrams
**Labels**: `good first issue`, `documentation`, `diagrams`
**Difficulty**: ⭐⭐ Medium

Create Mermaid diagrams for key flows.

**Files to create/modify**:
- `docs/architecture.md` (add diagrams)
- `docs/sequence-diagrams.md` (new file)

**Diagrams needed**:
1. Agent registration sequence
2. Task delegation sequence
3. Trust scoring computation
4. Policy evaluation flow
5. MCP tool call flow
6. A2A request/response flow

---

## Code Quality Issues

### 🔧 Add Type Hints to Untyped Functions
**Labels**: `good first issue`, `type-hints`, `code-quality`
**Difficulty**: ⭐ Easy

Some functions are missing type hints.

**Files to check**:
- `src/oai_network/core/discovery/cache.py`
- `src/oai_network/core/identity/generator.py`
- `src/oai_network/protocols/mcp/client.py`
- `src/oai_network/protocols/a2a/client.py`

**Tasks**:
- Run `mypy src/oai_network --ignore-missing-imports` to find untyped functions
- Add type hints to parameters and return values
- Use `from __future__ import annotations` for forward references

---

### 🔧 Fix Ruff Linting Warnings
**Labels**: `good first issue`, `linting`, `code-quality`
**Difficulty**: ⭐ Easy

Clean up minor linting issues.

**Command**:
```bash
ruff check src/ --fix
```

**Common issues**:
- Unused imports (F401)
- Line too long (E501)
- Trailing whitespace (W291)
- Missing blank lines (E302, E305)

---

### 🔧 Add Missing Test Coverage
**Labels**: `good first issue`, `testing`, `coverage`
**Difficulty**: ⭐⭐ Medium

Increase test coverage for specific modules.

**Target modules** (current coverage < 80%):
- `src/oai_network/core/negotiation/` (~65%)
- `src/oai_network/core/policy/` (~70%)
- `src/oai_network/protocols/mcp/` (~60%)

**Tasks**:
- Identify uncovered lines with `pytest --cov=oai_network --cov-report=term-missing`
- Write tests for uncovered branches
- Focus on error paths and edge cases

---

## Feature Issues

### ✨ Add New Capability Type
**Labels**: `good first issue`, `feature`, `capabilities`
**Difficulty**: ⭐⭐ Medium

Add a new built-in capability type.

**Files to modify**:
- `src/oai_network/core/capabilities/models.py` — Add capability definition
- `src/oai_network/core/capabilities/matcher.py` — Add matching logic
- `src/oai_network/core/capabilities/validator.py` — Add validation
- `src/oai_network/tests/test_capabilities.py` — Add tests

**Suggested capabilities**:
- `code_generation` — Generate code from specifications
- `data_analysis` — Analyze datasets
- `image_generation` — Generate images from prompts
- `web_search` — Search the web for information

---

### ✨ Add CLI Command for Trust History Export
**Labels**: `good first issue`, `feature`, `cli`, `trust`
**Difficulty**: ⭐⭐ Medium

Add a command to export trust history to JSON/CSV.

**Files to modify**:
- `src/oai_network/cli/main.py` — Add new command
- `src/oai_network/core/trust/store.py` — Add export method

**Command design**:
```bash
oai trust-export --agent-did <DID> --format json|csv --output trust_history.json
```

**Features**:
- Filter by date range
- Filter by event type (success/failure/timeout)
- Output formats: JSON, CSV
- Include computed trust scores

---

### ✨ Add Health Check Endpoint to Agents
**Labels**: `good first issue`, `feature`, `agents`, `observability`
**Difficulty**: ⭐ Easy

Ensure all agents have a consistent `/health` endpoint.

**Files to modify**:
- `src/oai_network/agents/code_analysis_agent.py`
- `src/oai_network/examples/translator_agent.py`
- `src/oai_network/examples/summarizer_agent.py`

**Standard response**:
```json
{
  "status": "healthy",
  "agent": "code-analysis-agent",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "checks": {
    "mcp_server": "ok",
    "ollama": "ok",
    "bandit": "ok",
    "pylint": "ok"
  }
}
```

---

### ✨ Add Configuration Validation
**Labels**: `good first issue`, `feature`, `config`, `validation`
**Difficulty**: ⭐⭐ Medium

Validate configuration files on startup.

**Files to modify**:
- `src/oai_network/core/policy/loader.py` — Add schema validation
- `src/oai_network/gateway/server.py` — Validate on startup
- `src/oai_network/registry/server.py` — Validate on startup

**Tasks**:
- Define JSON Schema for policy.yaml
- Validate required fields
- Provide clear error messages for invalid config
- Add tests for invalid configurations

---

## Testing Issues

### 🧪 Add Property-Based Tests
**Labels**: `good first issue`, `testing`, `property-based`
**Difficulty**: ⭐⭐⭐ Hard

Use Hypothesis for property-based testing.

**Target modules**:
- `src/oai_network/core/trust/calculator.py` — Trust score properties
- `src/oai_network/core/capabilities/matcher.py` — Matching properties
- `src/oai_network/core/negotiation/protocol.py` — Negotiation invariants

**Example**:
```python
from hypothesis import given, strategies as st
from oai_network.core.trust.calculator import TrustCalculator

@given(st.lists(st.booleans(), min_size=1, max_size=100))
def test_trust_score_bounds(events):
    """Trust score should always be between 0 and 1."""
    calculator = TrustCalculator()
    score = calculator.compute_score("did:test:1", events)
    assert 0.0 <= score.score <= 1.0
    assert 0.0 <= score.confidence <= 1.0
```

---

### 🧪 Add Integration Test for Full Delegation Flow
**Labels**: `good first issue`, `testing`, `integration`
**Difficulty**: ⭐⭐ Medium

Test the complete delegation flow: discover → delegate → trust update.

**File to create**:
- `src/oai_network/tests/test_integration_delegation.py`

**Test scenario**:
1. Start registry and gateway
2. Register two agents (delegator, worker)
3. Delegator discovers worker
4. Delegator delegates task to worker
5. Verify trust events recorded
6. Verify trust score updated

---

## Infrastructure Issues

### 🐳 Optimize Docker Images
**Labels**: `good first issue`, `docker`, `performance`
**Difficulty**: ⭐⭐ Medium

Reduce Docker image sizes and improve build times.

**Files to modify**:
- `docker/Dockerfile.agent`
- `docker/Dockerfile.gateway`
- `docker/Dockerfile.registry`

**Optimizations**:
- Use multi-stage builds
- Leverage layer caching
- Use `.dockerignore`
- Switch to `python:3.12-slim` base
- Combine RUN commands

---

### 🐳 Add Health Checks to Docker Compose
**Labels**: `good first issue`, `docker`, `reliability`
**Difficulty**: ⭐ Easy

Add health checks to all services in docker-compose.yml.

**File to modify**:
- `docker-compose.yml`

**Example**:
```yaml
services:
  registry:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
```

---

## SDK Issues

### 📦 Add TypeScript SDK Tests
**Labels**: `good first issue`, `typescript`, `sdk`, `testing`
**Difficulty**: ⭐⭐ Medium

Add unit tests for the TypeScript SDK.

**Files to create**:
- `src/oai_network/sdk/typescript/tests/client.test.ts`

**Test cases**:
- Client initialization
- Identity creation
- Agent registration
- Agent discovery
- Task delegation
- Trust score retrieval
- Error handling

---

### 📦 Add Python SDK Async Context Manager
**Labels**: `good first issue`, `python`, `sdk`, `api`
**Difficulty**: ⭐ Easy

Make `OAIClient` usable as an async context manager.

**File to modify**:
- `src/oai_network/sdk/python/client.py`

**Implementation**:
```python
class OAIClient:
    async def __aenter__(self) -> "OAIClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
```

**Usage**:
```python
async with OAIClient(registry_url="http://localhost:8081") as client:
    agents = await client.discover_agents("translation")
```

---

## Security Issues

### 🔒 Add Security Headers Middleware
**Labels**: `good first issue`, `security`, `middleware`
**Difficulty**: ⭐ Easy

Add standard security headers to all HTTP responses.

**File to create**:
- `src/oai_network/core/security/middleware.py`

**Headers to add**:
- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: ...`

**Integration**:
- Add to gateway server
- Add to registry server
- Add to agent servers

---

### 🔒 Add Input Sanitization Tests
**Labels**: `good first issue`, `security`, `testing`
**Difficulty**: ⭐⭐ Medium

Add tests for input sanitization edge cases.

**File to create**:
- `src/oai_network/tests/test_security_sanitization.py`

**Test cases**:
- SQL injection attempts in query parameters
- XSS payloads in JSON bodies
- Path traversal in file paths
- Command injection in shell commands
- Oversized payloads
- Malformed JSON/Unicode

---

## How to Claim an Issue

1. **Comment** on the GitHub issue: "I'll work on this!"
2. **Assign** yourself if you have write access
3. **Create a branch**: `git checkout -b feat/issue-description`
4. **Reference the issue** in your PR: "Fixes #123"

---

## Need Help?

- **Ask questions** in the GitHub issue comments
- **Join discussions** in GitHub Discussions
- **Check existing PRs** for similar changes
- **Read the docs**: [CONTRIBUTING.md](CONTRIBUTING.md), [Architecture](docs/architecture.md)

---

## Issue Templates

When creating new issues, please use our templates:

- **Bug Report**: `.github/ISSUE_TEMPLATE/bug_report.md`
- **Feature Request**: `.github/ISSUE_TEMPLATE/feature_request.md`
- **Documentation**: `.github/ISSUE_TEMPLATE/documentation.md`

---

*Last updated: 2026-08-22*
*Maintainers: @Parth99128*