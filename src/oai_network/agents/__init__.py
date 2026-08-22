"""
OAI Network Agents Package

Real agents that perform actual work via MCP servers:
- CodeAnalysisAgent: Security & quality analysis (Bandit + Pylint)
- SummarizerAgent: Text summarization (Ollama LLM)
- TranslatorAgent: Text translation (Ollama LLM)
"""

from oai_network.agents.code_analysis_agent import CodeAnalysisAgent, create_code_analysis_agent
from oai_network.agents.summarizer_agent import SummarizerAgent, create_summarizer_agent
from oai_network.agents.translator_agent import TranslatorAgent, create_translator_agent

__all__ = [
    "CodeAnalysisAgent",
    "create_code_analysis_agent",
    "SummarizerAgent",
    "create_summarizer_agent",
    "TranslatorAgent",
    "create_translator_agent",
]