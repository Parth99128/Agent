"""
Observability Module

Provides structured JSON logging, trace_id propagation, and Prometheus metrics
for the OAI Network services.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Context variable for trace_id propagation
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


def get_trace_id() -> str:
    """Get current trace_id or generate new one."""
    trace_id = trace_id_var.get()
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
        trace_id_var.set(trace_id)
    return trace_id


def get_span_id() -> str:
    """Get current span_id or generate new one."""
    span_id = span_id_var.get()
    if span_id is None:
        span_id = str(uuid.uuid4())[:8]
        span_id_var.set(span_id)
    return span_id


def set_trace_id(trace_id: str) -> None:
    """Set trace_id for current context."""
    trace_id_var.set(trace_id)


def set_span_id(span_id: str) -> None:
    """Set span_id for current context."""
    span_id_var.set(span_id)


@dataclass
class LogContext:
    """Structured log context."""
    trace_id: str = field(default_factory=get_trace_id)
    span_id: str = field(default_factory=get_span_id)
    service: str = "oai-network"
    level: str = "INFO"
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "service": self.service,
            "level": self.level,
            "message": self.message,
            **self.extra,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))


class JSONFormatter(logging.Formatter):
    """JSON log formatter with trace_id support."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get trace_id from context or record
        trace_id = getattr(record, "trace_id", None) or trace_id_var.get() or "no-trace"
        span_id = getattr(record, "span_id", None) or span_id_var.get() or "no-span"
        
        log_data = {
            "timestamp": time.time(),
            "trace_id": trace_id,
            "span_id": span_id,
            "service": getattr(record, "service", "oai-network"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "name", "pathname", "process", "processName",
                "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "trace_id", "span_id", "service"
            }:
                log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, separators=(",", ":"))


def setup_json_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup structured JSON logging for a service."""
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger with JSON formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        setup_json_logging(name)
    return logger


# Prometheus Metrics
REQUEST_COUNT = Counter(
    "oai_requests_total",
    "Total number of requests",
    ["service", "method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "oai_request_duration_seconds",
    "Request latency in seconds",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

ACTIVE_REQUESTS = Gauge(
    "oai_active_requests",
    "Number of active requests",
    ["service"]
)

POLICY_DENIALS = Counter(
    "oai_policy_denials_total",
    "Total number of policy denials",
    ["service", "reason"]
)

AGENT_SUCCESS_RATE = Gauge(
    "oai_agent_success_rate",
    "Agent success rate",
    ["agent_did"]
)

AGENT_DISCOVERY_COUNT = Counter(
    "oai_agent_discovery_total",
    "Total number of agent discoveries",
    ["service", "capability_type"]
)

DELEGATION_COUNT = Counter(
    "oai_delegations_total",
    "Total number of delegations",
    ["service", "status"]
)

TRUST_SCORE = Gauge(
    "oai_agent_trust_score",
    "Agent trust score",
    ["agent_did"]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics."""
    
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name
    
    async def dispatch(self, request: Request, call_next):
        # Generate trace_id if not present
        trace_id = request.headers.get("x-trace-id") or get_trace_id()
        set_trace_id(trace_id)
        
        # Add trace_id to request state for downstream use
        request.state.trace_id = trace_id
        
        # Start timing
        start_time = time.time()
        ACTIVE_REQUESTS.labels(service=self.service_name).inc()
        
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                service=self.service_name,
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            REQUEST_LATENCY.labels(
                service=self.service_name,
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # Add trace_id to response headers
            response.headers["x-trace-id"] = trace_id
            
            return response
        except Exception as e:
            REQUEST_COUNT.labels(
                service=self.service_name,
                method=request.method,
                endpoint=request.url.path,
                status=500
            ).inc()
            raise
        finally:
            ACTIVE_REQUESTS.labels(service=self.service_name).dec()


def record_policy_denial(service: str, reason: str) -> None:
    """Record a policy denial."""
    POLICY_DENIALS.labels(service=service, reason=reason).inc()


def record_agent_discovery(service: str, capability_type: str) -> None:
    """Record an agent discovery."""
    AGENT_DISCOVERY_COUNT.labels(service=service, capability_type=capability_type).inc()


def record_delegation(service: str, status: str) -> None:
    """Record a delegation attempt."""
    DELEGATION_COUNT.labels(service=service, status=status).inc()


def update_agent_success_rate(agent_did: str, rate: float) -> None:
    """Update agent success rate metric."""
    AGENT_SUCCESS_RATE.labels(agent_did=agent_did).set(rate)


def update_trust_score(agent_did: str, score: float) -> None:
    """Update agent trust score metric."""
    TRUST_SCORE.labels(agent_did=agent_did).set(score)


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# Logging helper functions
def log_request(logger: logging.Logger, method: str, path: str, trace_id: str, **extra) -> None:
    """Log an incoming request."""
    logger.info(
        f"Request: {method} {path}",
        extra={
            "trace_id": trace_id,
            "method": method,
            "path": path,
            **extra
        }
    )


def log_response(logger: logging.Logger, method: str, path: str, status_code: int, 
                 duration_ms: float, trace_id: str, **extra) -> None:
    """Log a response."""
    logger.info(
        f"Response: {method} {path} -> {status_code} ({duration_ms:.2f}ms)",
        extra={
            "trace_id": trace_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            **extra
        }
    )


def log_error(logger: logging.Logger, message: str, trace_id: str, 
              error: Exception = None, **extra) -> None:
    """Log an error."""
    extra_data = {"trace_id": trace_id, **extra}
    if error:
        extra_data["error_type"] = type(error).__name__
        extra_data["error_message"] = str(error)
    logger.error(message, extra=extra_data)


def log_agent_action(logger: logging.Logger, action: str, agent_did: str, 
                     trace_id: str, **extra) -> None:
    """Log an agent action."""
    logger.info(
        f"Agent {action}: {agent_did}",
        extra={
            "trace_id": trace_id,
            "agent_did": agent_did,
            "action": action,
            **extra
        }
    )


def log_policy_check(logger: logging.Logger, policy_id: str, allowed: bool, 
                     trace_id: str, **extra) -> None:
    """Log a policy check result."""
    logger.info(
        f"Policy check: {policy_id} -> {'ALLOWED' if allowed else 'DENIED'}",
        extra={
            "trace_id": trace_id,
            "policy_id": policy_id,
            "allowed": allowed,
            **extra
        }
    )


def log_delegation(logger: logging.Logger, from_did: str, to_did: str, 
                   task_id: str, trace_id: str, **extra) -> None:
    """Log a delegation."""
    logger.info(
        f"Delegation: {from_did} -> {to_did} (task: {task_id})",
        extra={
            "trace_id": trace_id,
            "from_did": from_did,
            "to_did": to_did,
            "task_id": task_id,
            **extra
        }
    )