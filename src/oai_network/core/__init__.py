"""
Core module for OAI Network.
"""

from .observability import (
    setup_json_logging,
    get_logger,
    JSONFormatter,
    get_trace_id,
    get_span_id,
    set_trace_id,
    set_span_id,
    log_request,
    log_response,
    log_error,
    log_agent_action,
    log_policy_check,
    log_delegation,
    record_policy_denial,
    record_agent_discovery,
    record_delegation,
    update_agent_success_rate,
    update_trust_score,
    MetricsMiddleware,
    metrics_endpoint,
)

__all__ = [
    "setup_json_logging",
    "get_logger",
    "JSONFormatter",
    "get_trace_id",
    "get_span_id",
    "set_trace_id",
    "set_span_id",
    "log_request",
    "log_response",
    "log_error",
    "log_agent_action",
    "log_policy_check",
    "log_delegation",
    "record_policy_denial",
    "record_agent_discovery",
    "record_delegation",
    "update_agent_success_rate",
    "update_trust_score",
    "MetricsMiddleware",
    "metrics_endpoint",
]