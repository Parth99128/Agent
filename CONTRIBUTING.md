# Contributing to OAI Network

Thank you for your interest in contributing to OAI Network! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)
- [Architecture Overview](#architecture-overview)

---

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- Docker & Docker Compose (for integration testing)
- Ollama (optional, for local AI features): `curl -fsSL https://ollama.com/install.sh | sh`

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Agent.git
cd Agent

# Add upstream remote
git remote add upstream https://github.com/Parth99128/Agent.git
```

### Install Development Dependencies

```bash
# Install in development mode with all optional dependencies
pip install -e ".[all,dev]"

# Install pre-commit hooks
pre-commit install
```

---

## Development Environment

### Running Tests

```bash
# Run all tests (328 tests)
pytest src/oai_network/tests/ -v

# Run with coverage
pytest src/oai_network/tests/ --cov=oai_network --cov-report=term-missing

# Run specific test categories
pytest src/oai_network/tests/test_cli.py -v           # CLI tests
pytest src/oai_network/tests/test_trust.py -v         # Trust tests
pytest src/oai_network/tests/test_security.py -v      # Security tests (29 tests)
pytest src/oai_network/tests/test_protocols.py -v     # A2A/MCP protocol tests
```

### Running Services Locally

```bash
# Start infrastructure (PostgreSQL, Redis)
docker-compose up -d postgres redis

# Run registry
python -m oai_network.registry.server

# Run gateway (in another terminal)
python -m oai_network.gateway.server

# Run agents (in separate terminals)
python -m oai_network.examples.translator_agent
python -m oai_network.examples.summarizer_agent
python -m oai_network.agents.code_analysis_agent
```

### Using Docker Compose (Full Stack)

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f registry
docker-compose logs -f gateway
docker-compose logs -f code-analysis

# Stop everything
docker-compose down
```

### Running the Live Demo

```bash
# With full stack running
python live_demo.py
```

---

## Coding Standards

### Python Style

- **Formatter**: Ruff (configured in `pyproject.toml`)
- **Line length**: 100 characters
- **Target version**: Python 3.10+
- **Type hints**: Required for all public APIs

```bash
# Check style
ruff check src/

# Auto-fix
ruff check src/ --fix

# Format
ruff format src/
```

### Type Hints

All public functions, methods, and classes must have type hints:

```python
# Good
async def discover_agents(
    self, 
    capability: str, 
    min_trust: float = 0.0
) -> list[AgentCard]:
    ...

# Bad
async def discover_agents(self, capability, min_trust=0.0):
    ...
```

### Docstrings

Use Google-style docstrings for all public APIs:

```python
def calculate_trust_score(
    self, 
    agent_did: str, 
    interactions: list[TrustEvent]
) -> TrustScore:
    """Calculate trust score using Wilson score interval.
    
    Args:
        agent_did: The DID of the agent to score.
        interactions: List of trust events for the agent.
        
    Returns:
        TrustScore with score, confidence, and metadata.
        
    Raises:
        ValueError: If agent_did is empty or interactions contain invalid data.
    """
```

### Imports

- Use absolute imports within the package
- Group imports: standard library, third-party, local
- Sort alphabetically within groups

```python
# Standard library
import asyncio
import json
from datetime import datetime
from typing import Optional

# Third-party
import httpx
from pydantic import BaseModel

# Local
from oai_network.core.trust.models import TrustEvent, TrustScore
from oai_network.core.identity.models import AgentIdentity
```

### Async/Await

- Use `async`/`await` for all I/O operations
- Prefer `asyncio.gather()` for concurrent operations
- Always handle exceptions in async code

```python
async def fetch_agents(self) -> list[AgentCard]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.registry_url}/agents")
            response.raise_for_status()
            return [AgentCard(**a) for a in response.json()]
    except httpx.HTTPError as e:
        logger.error("Failed to fetch agents", error=str(e))
        raise
```

---

## Testing

### Test Structure

```
src/oai_network/tests/
├── conftest.py              # Shared fixtures
├── test_capabilities.py     # Capability matching tests
├── test_cli.py              # CLI command tests (39 tests)
├── test_delegation.py       # Delegation manager tests
├── test_discovery.py        # Discovery service tests
├── test_gateway.py          # Gateway server tests
├── test_identity.py         # Identity/verification tests
├── test_negotiation.py      # Negotiation protocol tests
├── test_policy.py           # Policy engine tests
├── test_protocols.py        # A2A/MCP protocol tests
├── test_registry.py         # Registry server tests
├── test_sdk.py              # Python/TypeScript SDK tests
├── test_security.py         # Security/adversarial tests (29 tests)
└── test_trust.py            # Trust calculator/store tests
```

### Writing Tests

- Use `pytest-asyncio` for async tests
- Use `pytest-mock` for mocking
- Follow AAA pattern: Arrange, Act, Assert
- Test both success and failure paths

```python
import pytest
from unittest.mock import AsyncMock, patch

from oai_network.core.discovery.service import DiscoveryService


class TestDiscoveryService:
    @pytest.fixture
    def service(self):
        return DiscoveryService(registry_url="http://localhost:8081")
    
    @pytest.mark.asyncio
    async def test_discover_agents_success(self, service):
        # Arrange
        mock_response = [{"did": "did:example:1", "name": "Agent 1", "capabilities": ["translation"]}]
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.raise_for_status = lambda: None
            
            # Act
            agents = await service.discover_agents("translation")
            
            # Assert
            assert len(agents) == 1
            assert agents[0].did == "did:example:1"
            assert "translation" in agents[0].capabilities
    
    @pytest.mark.asyncio
    async def test_discover_agents_empty(self, service):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.json.return_value = []
            mock_get.return_value.raise_for_status = lambda: None
            
            agents = await service.discover_agents("nonexistent")
            assert agents == []
```

### Test Coverage

- Target: >90% coverage for core modules
- Run coverage: `pytest --cov=oai_network --cov-report=html`
- View report: `open htmlcov/index.html`

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**
   ```bash
   # Style checks
   ruff check src/
   ruff format src/ --check
   
   # Type checking (if mypy configured)
   # mypy src/
   
   # Tests
   pytest src/oai_network/tests/ -v
   ```

3. **Update documentation** if needed:
   - README.md for user-facing changes
   - Docstrings for API changes
   - CHANGELOG.md (will be updated during release)

### PR Guidelines

- **Title**: Use conventional commits format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **Description**: Explain what changed, why, and any breaking changes
- **Tests**: Add tests for new functionality
- **Commits**: Keep commits focused; squash if needed before merge

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing performed (describe)

## Checklist
- [ ] Code follows style guidelines
- [ ] Type hints added for new public APIs
- [ ] Docstrings updated
- [ ] No new linting errors
```

### Review Process

1. Automated checks must pass (CI)
2. At least one maintainer review required
3. Address review comments
4. Squash and merge (maintainers will handle)

---

## Release Process

### Versioning

Follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps (Maintainers)

1. Update `CHANGELOG.md` with release notes
2. Update version in `pyproject.toml`
3. Create release tag: `git tag v0.x.x`
4. Push tag: `git push origin v0.x.x`
5. GitHub Actions builds and publishes to PyPI
6. Create GitHub Release with changelog

---

## Architecture Overview

### Core Modules

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `core.identity` | DID-based identity & verification | `models.py`, `generator.py`, `verifier.py` |
| `core.discovery` | Agent registration & discovery | `service.py`, `cache.py`, `models.py` |
| `core.delegation` | Task delegation & policy | `manager.py`, `policy.py`, `models.py` |
| `core.trust` | Trust scoring & history | `calculator.py`, `store.py`, `models.py` |
| `core.policy` | Rule engine & budgets | `engine.py`, `loader.py`, `models.py` |
| `core.negotiation` | Protocol negotiation | `protocol.py`, `strategies.py`, `models.py` |
| `core.routing` | Query classification (Ollama) | `classifier.py` |
| `core.observability` | Logging, metrics, tracing | `observability.py` |
| `core.capabilities` | Capability matching | `matcher.py`, `validator.py`, `models.py` |

### Protocols

| Protocol | Implementation | Purpose |
|----------|---------------|---------|
| **MCP** | `protocols/mcp/` | Tool/function calling between agents |
| **A2A** | `protocols/a2a/` | Agent-to-Agent communication |

### Servers

| Server | Port | Entry Point |
|--------|------|-------------|
| Registry | 8081 | `oai_network.registry.server:main` |
| Gateway | 8080 | `oai_network.gateway.server:main` |

### Agents

| Agent | Port | Capabilities |
|-------|------|--------------|
| Translator | 8001 | 20 languages |
| Summarizer | 8002 | 5 styles |
| Code Analysis | 8003 | Bandit, Pylint |

---

## Good First Issues

Look for issues labeled `good first issue` on GitHub. Common areas:

- Adding new capability types
- Improving CLI help text
- Adding test coverage for edge cases
- Documentation improvements
- Type hint additions

---

## Getting Help

- **Discussions**: GitHub Discussions for questions
- **Issues**: Bug reports and feature requests
- **Discord**: (link if available)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.