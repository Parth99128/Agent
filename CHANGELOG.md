# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Stage 12: Observability - Structured JSON logging, trace_id propagation, Prometheus metrics
- Stage 11: Security Hardening - 29 adversarial security tests
- Stage 10: Real Trust & Reputation - Wilson score interval, trust decay, delegation integration
- Stage 9: A2A Interoperability - Agent Card at /.well-known/agent-card.json
- Stage 8: Real Agents via MCP - CodeAnalysisAgent (Bandit/Pylint), SummarizerAgent, TranslatorAgent
- Stage 7: Local AI Routing - Ollama integration with QueryClassifier
- Live demo script demonstrating complete A2A + REST communication flow
- Docker Compose for local development stack
- GitHub Actions CI/CD workflow

### Changed
- Fixed all 328 tests to pass
- Updated CLI to match test expectations exactly
- Fixed MCP server request handler registration
- Fixed CodeAnalysisAgent with fresh connections per request
- Enhanced RequestSizeMiddleware for header size checking

### Fixed
- log_agent_action signature mismatches across services
- log_policy_check signature in PolicyEngine
- log_response missing duration_ms parameter
- MetricsMiddleware missing service_name argument
- TrustStore and TrustCalculator observability integration

## [0.1.0] - 2026-08-22

### Added
- Initial OAI Network framework
- Core capabilities: discovery, identity, delegation, trust, negotiation, policy
- A2A and MCP protocol implementations
- Python and TypeScript SDKs
- Registry and Gateway servers
- Example agents (translator, summarizer)
- Comprehensive test suite (328 tests)