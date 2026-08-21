"""
Stage 7: Local AI Routing - Query Classifier using Ollama

This module uses a local LLM (via Ollama) to classify natural language queries
into capability names for agent discovery.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import ollama

logger = logging.getLogger(__name__)


@dataclass
class CapabilityInfo:
    """Information about a registered capability."""
    name: str
    description: str
    tags: List[str]


class QueryClassifier:
    """
    Uses local LLM to classify natural language queries into capability names.
    
    This is Stage 7 of the build guide - adding local AI routing.
    """
    
    def __init__(
        self,
        model: str = "llama3.2:3b",
        ollama_host: str = "http://localhost:11434",
        capabilities: Optional[List[CapabilityInfo]] = None,
    ):
        self.model = model
        self.client = ollama.Client(host=ollama_host)
        self.capabilities = capabilities or []
        self._capability_cache: Dict[str, str] = {}  # query -> capability
    
    def add_capability(self, name: str, description: str, tags: List[str] = None):
        """Add a capability to the classifier's knowledge."""
        self.capabilities.append(CapabilityInfo(
            name=name,
            description=description,
            tags=tags or []
        ))
    
    def _build_prompt(self, query: str) -> str:
        """Build the classification prompt."""
        cap_list = "\n".join([
            f"- {c.name}: {c.description} (tags: {', '.join(c.tags)})"
            for c in self.capabilities
        ])
        
        valid_names = ", ".join([c.name for c in self.capabilities])
        
        return f"""You are a query classifier. Map the user query to ONE capability name from this list: {valid_names}

Available capabilities:
{cap_list}

Query: "{query}"

Output ONLY the capability name. Examples:
- "analyze python code" -> code_analysis
- "translate to french" -> translation
- "summarize document" -> summarization

Capability name:"""
    
    def classify(self, query: str) -> str:
        """
        Classify a natural language query into a capability name.
        
        Uses caching to avoid repeated LLM calls for the same query.
        """
        # Check cache first
        if query in self._capability_cache:
            return self._capability_cache[query]
        
        # If no capabilities registered, fall back to keyword matching
        if not self.capabilities:
            return self._fallback_classify(query)
        
        try:
            prompt = self._build_prompt(query)
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.1,  # Low temperature for consistent classification
                    "num_predict": 20,   # Short response
                }
            )
            
            raw_response = response.get("response", "").strip()
            # Handle tinyllama's "response: " prefix
            if raw_response.startswith("response:"):
                raw_response = raw_response[len("response:"):].strip()
            capability = raw_response.lower()
            
            # Validate the response is a known capability
            valid_names = [c.name for c in self.capabilities]
            if capability in valid_names:
                self._capability_cache[query] = capability
                return capability
            
            # Try to find partial match
            for valid in valid_names:
                if valid in capability or capability in valid:
                    self._capability_cache[query] = valid
                    return valid
            
            logger.warning(f"LLM returned unknown capability: '{capability}', falling back")
            return self._fallback_classify(query)
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}, falling back to keyword matching")
            return self._fallback_classify(query)
    
    def _fallback_classify(self, query: str) -> str:
        """Fallback keyword-based classification."""
        query_lower = query.lower()
        
        # Simple keyword matching
        if any(kw in query_lower for kw in ["analyze", "analysis", "security", "audit", "bug", "code", "repository", "repo", "python", "static"]):
            return "code_analysis"
        elif any(kw in query_lower for kw in ["translate", "translation", "language"]):
            return "translation"
        elif any(kw in query_lower for kw in ["summarize", "summary", "summarization"]):
            return "summarization"
        
        # Default to first capability or general
        return self.capabilities[0].name if self.capabilities else "general"


def create_default_classifier(model: str = "llama3.2:3b") -> QueryClassifier:
    """Create a classifier with default OAI Network capabilities."""
    classifier = QueryClassifier(model=model)
    
    classifier.add_capability(
        name="code_analysis",
        description="Analyze code repositories for bugs, security vulnerabilities, and quality issues",
        tags=["code", "security", "analysis", "python", "static-analysis"]
    )
    
    classifier.add_capability(
        name="translation",
        description="Translate text between languages",
        tags=["nlp", "translation", "language", "multilingual"]
    )
    
    classifier.add_capability(
        name="summarization",
        description="Summarize long text into concise form",
        tags=["nlp", "summarization", "text-processing"]
    )
    
    return classifier


if __name__ == "__main__":
    # Test the classifier
    logging.basicConfig(level=logging.INFO)
    
    classifier = create_default_classifier()
    
    test_queries = [
        "analyze python repository for security issues",
        "translate english to spanish",
        "summarize this long document",
        "find bugs in my code",
        "security audit my repo",
    ]
    
    print("Testing Query Classifier:")
    print("=" * 60)
    
    for query in test_queries:
        capability = classifier.classify(query)
        print(f"Query: {query}")
        print(f"  -> Capability: {capability}")
        print()