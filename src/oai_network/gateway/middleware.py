"""
Gateway Middleware

Middleware components for the gateway.
"""

import time
import logging
from typing import Optional, Any, Callable, Awaitable
from collections import defaultdict
from threading import Lock
from .models import GatewayRequest, GatewayResponse, GatewayConfig


# Configure logging
logger = logging.getLogger("oai_network.gateway")


class GatewayMiddleware:
    """Base middleware class."""
    
    def __call__(
        self, 
        request: GatewayRequest, 
        route, 
        response: Optional[GatewayResponse] = None,
        phase: str = "pre"
    ) -> Optional[GatewayResponse]:
        """Process request/response."""
        if phase == "pre":
            return self.process_request(request, route)
        elif phase == "post":
            return self.process_response(request, route, response)
        return None
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Process request before routing."""
        return None
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Process response after routing."""
        return None


class AuthMiddleware(GatewayMiddleware):
    """Authentication middleware."""
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.api_keys: dict[str, str] = {}  # key -> agent_did
        self.jwt_secret: Optional[str] = None
    
    def add_api_key(self, api_key: str, agent_did: str):
        """Add an API key mapping."""
        self.api_keys[api_key] = agent_did
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Extract and validate authentication."""
        # Check Authorization header (case-insensitive)
        auth_header = ''
        for key, value in request.headers.items():
            if key.lower() == 'authorization':
                auth_header = value
                break
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            
            # Check API key
            if token in self.api_keys:
                request.agent_did = self.api_keys[token]
                return None
            
            # Check JWT (placeholder)
            if self.jwt_secret:
                # Would validate JWT here
                pass
        
        # Check X-API-Key header (case-insensitive)
        api_key = ''
        for key, value in request.headers.items():
            if key.lower() == 'x-api-key':
                api_key = value
                break
        if api_key and api_key in self.api_keys:
            request.agent_did = self.api_keys[api_key]
            return None
        
        # No valid auth found - return 401 if route requires verification
        if route and route.require_verified:
            return GatewayResponse(
                request_id=request.id,
                status_code=401,
                body={"error": "Authentication required"},
            )
        
        # For routes that don't require verification, allow anonymous access
        return None


class RateLimitMiddleware(GatewayMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.limits: dict[str, dict] = defaultdict(lambda: {
            'count': 0,
            'window_start': time.time(),
            'burst_used': 0,
        })
        self.lock = Lock()
    
    def _get_limit_key(self, request: GatewayRequest, route) -> str:
        """Generate rate limit key."""
        # Use agent DID if available, otherwise IP, otherwise X-Client-ID header (case-insensitive)
        identifier = request.agent_did or request.client_ip
        if not identifier:
            # Check headers case-insensitively
            for key, value in request.headers.items():
                if key.lower() == 'x-client-id':
                    identifier = value
                    break
        if not identifier:
            identifier = 'anonymous'
        return f"{identifier}:{route.id if route else 'global'}"
    
    def _get_limits(self, route) -> tuple[int, int]:
        """Get rate limit and burst for a route."""
        if route and route.rate_limit_rpm:
            rpm = route.rate_limit_rpm
            burst = route.rate_limit_burst or rpm // 10
        else:
            rpm = self.config.global_rate_limit_rpm
            burst = self.config.global_rate_limit_burst
        return rpm, burst
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Check and enforce rate limits."""
        key = self._get_limit_key(request, route)
        rpm, burst = self._get_limits(route)
        
        with self.lock:
            now = time.time()
            limit_data = self.limits[key]
            
            # Reset window if needed
            if now - limit_data['window_start'] >= 60:
                limit_data['count'] = 0
                limit_data['window_start'] = now
                limit_data['burst_used'] = 0
            
            # Check limit
            if limit_data['count'] >= rpm:
                # Check burst
                if limit_data['burst_used'] < burst:
                    limit_data['burst_used'] += 1
                else:
                    return GatewayResponse(
                        request_id=request.id,
                        status_code=429,
                        body={
                            "error": "Rate limit exceeded",
                            "limit": rpm,
                            "window": "minute",
                        },
                        headers={
                            "X-RateLimit-Limit": str(rpm),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(limit_data['window_start'] + 60)),
                        },
                    )
            
            limit_data['count'] += 1
            
            # Add rate limit headers to request for response middleware
            request.headers['_rate_limit_remaining'] = str(rpm - limit_data['count'])
            request.headers['_rate_limit_limit'] = str(rpm)
        
        return None
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Add rate limit headers to response."""
        remaining = request.headers.get('_rate_limit_remaining', '0')
        limit = request.headers.get('_rate_limit_limit', '0')
        
        response.headers['X-RateLimit-Limit'] = limit
        response.headers['X-RateLimit-Remaining'] = remaining
        response.headers['X-RateLimit-Reset'] = str(int(time.time() + 60))
        
        return None


class LoggingMiddleware(GatewayMiddleware):
    """Request/response logging middleware."""
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self.logger = logging.getLogger("oai_network.gateway.access")
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Log incoming request."""
        if not self.config.access_log:
            return None
        
        log_data = {
            "request_id": request.id,
            "method": request.method,
            "path": request.path,
            "client_ip": request.client_ip,
            "agent_did": request.agent_did,
            "capability": request.capability_name,
            "delegation_depth": request.delegation_depth,
        }
        
        if self.config.access_log_format == "json":
            import json
            self.logger.info(json.dumps(log_data))
        else:
            self.logger.info(
                f"{request.method} {request.path} - {request.client_ip} - "
                f"Agent: {request.agent_did or 'anonymous'}"
            )
        
        return None
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Log response."""
        if not self.config.access_log:
            return None
        
        log_data = {
            "request_id": request.id,
            "status_code": response.status_code,
            "latency_ms": response.latency_ms,
            "upstream_latency_ms": response.upstream_latency_ms,
        }
        
        if self.config.access_log_format == "json":
            import json
            self.logger.info(json.dumps(log_data))
        else:
            self.logger.info(
                f"{request.method} {request.path} - {response.status_code} - "
                f"{response.latency_ms:.2f}ms"
            )
        
        return None


class MetricsMiddleware(GatewayMiddleware):
    """Metrics collection middleware."""
    
    def __init__(self):
        self.metrics = {
            'requests_total': 0,
            'requests_by_status': defaultdict(int),
            'requests_by_route': defaultdict(int),
            'latency_sum': 0.0,
            'latency_count': 0,
            'errors_total': 0,
        }
        self.lock = Lock()
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Record request start."""
        with self.lock:
            self.metrics['requests_total'] += 1
            if route:
                self.metrics['requests_by_route'][route.id] += 1
        return None
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Record response metrics."""
        with self.lock:
            self.metrics['requests_by_status'][response.status_code] += 1
            self.metrics['latency_sum'] += response.latency_ms
            self.metrics['latency_count'] += 1
            
            if response.status_code >= 400:
                self.metrics['errors_total'] += 1
        
        return None
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        with self.lock:
            avg_latency = (
                self.metrics['latency_sum'] / self.metrics['latency_count']
                if self.metrics['latency_count'] > 0 else 0
            )
            return {
                **self.metrics,
                'average_latency_ms': avg_latency,
                'error_rate': (
                    self.metrics['errors_total'] / self.metrics['requests_total']
                    if self.metrics['requests_total'] > 0 else 0
                ),
            }
    
    def reset_metrics(self):
        """Reset metrics counters."""
        with self.lock:
            self.metrics = {
                'requests_total': 0,
                'requests_by_status': defaultdict(int),
                'requests_by_route': defaultdict(int),
                'latency_sum': 0.0,
                'latency_count': 0,
                'errors_total': 0,
            }


class CORSMiddleware(GatewayMiddleware):
    """CORS middleware."""
    
    def __init__(self, config: GatewayConfig = None, allowed_origins: list[str] = None, allowed_methods: list[str] = None, allowed_headers: list[str] = None):
        if config:
            self.config = config
            self.allowed_origins = config.cors_origins
            self.allowed_methods = config.cors_methods
            self.allowed_headers = config.cors_headers
            self.enabled = config.cors_enabled
        else:
            self.config = None
            self.allowed_origins = allowed_origins or ["*"]
            self.allowed_methods = allowed_methods or ["*"]
            self.allowed_headers = allowed_headers or ["*"]
            self.enabled = True
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Handle preflight requests and check origin."""
        # Get origin header case-insensitively
        origin = ''
        for key, value in request.headers.items():
            if key.lower() == 'origin':
                origin = value
                break
        
        # Check if origin is allowed
        allowed = False
        if '*' in self.allowed_origins:
            allowed = True
        elif origin in self.allowed_origins:
            allowed = True
        
        if request.method == 'OPTIONS':
            if not allowed:
                return GatewayResponse(
                    request_id=request.id,
                    status_code=403,
                    headers={},
                    body={"error": "Origin not allowed"}
                )
            return GatewayResponse(
                request_id=request.id,
                status_code=204,
                headers=self._cors_headers(request),
            )
        
        if not allowed and origin:
            return GatewayResponse(
                request_id=request.id,
                status_code=403,
                headers={},
                body={"error": "Origin not allowed"}
            )
        
        return None
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Add CORS headers to response."""
        if not self.enabled:
            return response
        
        cors_headers = self._cors_headers(request)
        response.headers.update(cors_headers)
        return response
    
    def _cors_headers(self, request: GatewayRequest) -> dict[str, str]:
        """Generate CORS headers."""
        # HTTP headers are case-insensitive, check both cases
        origin = request.headers.get('origin', '') or request.headers.get('Origin', '')
        
        # Check if origin is allowed
        allowed = False
        if '*' in self.allowed_origins:
            allowed = True
        elif origin in self.allowed_origins:
            allowed = True
        
        headers = {}
        if allowed:
            headers['Access-Control-Allow-Origin'] = origin or '*'
            headers['Access-Control-Allow-Methods'] = ', '.join(self.allowed_methods)
            headers['Access-Control-Allow-Headers'] = ', '.join(self.allowed_headers)
            headers['Access-Control-Allow-Credentials'] = 'true'
            headers['Access-Control-Max-Age'] = '86400'
        
        return headers


class RequestSizeMiddleware(GatewayMiddleware):
    """Request size limiting middleware."""
    
    def __init__(self, config: GatewayConfig = None, max_size_bytes: int = None):
        if config:
            self.config = config
            self.max_size = config.max_request_size_mb * 1024 * 1024
        else:
            self.config = None
            self.max_size = max_size_bytes or 10 * 1024 * 1024
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Check request size."""
        # In real implementation, would check Content-Length header or stream size
        # For now, just check if body is too large (rough estimate)
        if request.body:
            import sys
            size = sys.getsizeof(str(request.body))
            if size > self.max_size:
                max_mb = self.config.max_request_size_mb if self.config else self.max_size // (1024*1024)
                return GatewayResponse(
                    request_id=request.id,
                    status_code=413,
                    body={"error": "Request too large", "max_size_mb": max_mb},
                )
        return None


class ResponseSizeMiddleware(GatewayMiddleware):
    """Response size limiting middleware."""
    
    def __init__(self, config: GatewayConfig = None, max_size_bytes: int = None):
        if config:
            self.config = config
            self.max_size = config.max_response_size_mb * 1024 * 1024
        else:
            self.config = None
            self.max_size = max_size_bytes or 50 * 1024 * 1024
    
    def process_response(
        self, 
        request: GatewayRequest, 
        route, 
        response: GatewayResponse
    ) -> Optional[GatewayResponse]:
        """Check response size."""
        if response.body:
            import sys
            size = sys.getsizeof(str(response.body))
            if size > self.max_size:
                return GatewayResponse(
                    request_id=request.id,
                    status_code=500,
                    body={"error": "Response too large", "max_size_mb": self.config.max_response_size_mb if self.config else self.max_size // (1024*1024)},
                )
        return response


class TimeoutMiddleware(GatewayMiddleware):
    """Request timeout middleware."""
    
    def __init__(self, config: GatewayConfig = None, timeout_seconds: float = None):
        if config:
            self.config = config
        else:
            self.config = None
        self.timeout_seconds = timeout_seconds or 30.0
    
    def process_request(self, request: GatewayRequest, route) -> Optional[GatewayResponse]:
        """Store timeout info for upstream."""
        if route and hasattr(route, 'request_timeout_ms'):
            timeout = route.request_timeout_ms
        elif self.config and hasattr(self.config, 'default_request_timeout_ms'):
            timeout = self.config.default_request_timeout_ms
        else:
            timeout = int(self.timeout_seconds * 1000)
        request.headers['_request_timeout_ms'] = str(timeout)
        return None


# Middleware chain builder
def create_default_middlewares(config: GatewayConfig) -> list[GatewayMiddleware]:
    """Create default middleware stack."""
    return [
        CORSMiddleware(config),
        AuthMiddleware(config),
        RateLimitMiddleware(config),
        RequestSizeMiddleware(config),
        TimeoutMiddleware(config),
        LoggingMiddleware(config),
        MetricsMiddleware(),
        ResponseSizeMiddleware(config),
    ]