"""
Routing Module

Local AI routing for query classification and agent selection.
"""

from .classifier import QueryClassifier, CapabilityInfo, create_default_classifier

__all__ = [
    "QueryClassifier",
    "CapabilityInfo", 
    "create_default_classifier",
]