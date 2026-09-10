"""Network mock for simulating API responses and errors"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import time
from enum import Enum


class ResponseStatus(Enum):
    """Response status codes"""
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    SERVER_ERROR = 500
    TIMEOUT = 408


@dataclass
class APIResponse:
    """Simulated API response"""
    success: bool = True
    status_code: int = 200
    data: Dict[str, Any] = field(default_factory=dict)
    delay_ms: int = 0  # Simulated network delay
    
    def __post_init__(self):
        if not self.success and self.status_code == 200:
            self.status_code = 500


@dataclass
class ErrorInjection:
    """Error injection configuration"""
    endpoint: str
    error_code: int
    error_message: str
    trigger_count: int = 1  # How many times to trigger before recovering


class NetworkMock:
    """Mock network layer for API testing"""
    
    def __init__(self):
        self.responses: Dict[str, APIResponse] = {}
        self.error_injections: List[ErrorInjection] = []
        self.offline = False
        self.request_count: Dict[str, int] = {}
        self.response_cache: Dict[str, APIResponse] = {}
    
    def register_response(self, endpoint: str, response_data: Any) -> None:
        """Register a fake response for an endpoint"""
        if isinstance(response_data, APIResponse):
            self.responses[endpoint] = response_data
        else:
            # Convert dict to APIResponse
            self.responses[endpoint] = APIResponse(
                success=response_data.get('success', True),
                status_code=response_data.get('status_code', 200),
                data=response_data
            )
    
    def inject_error(
        self,
        endpoint: str,
        error_code: int = 500,
        error_message: str = "Server error",
        trigger_count: int = 1
    ) -> None:
        """Inject an error for specific endpoint"""
        injection = ErrorInjection(
            endpoint=endpoint,
            error_code=error_code,
            error_message=error_message,
            trigger_count=trigger_count
        )
        self.error_injections.append(injection)
    
    def get_response(
        self,
        endpoint: str,
        timeout_ms: int = 5000,
        skip_cache: bool = False
    ) -> APIResponse:
        """Get response for endpoint with optional delay and timeout"""
        
        # Check if offline
        if self.offline:
            if endpoint in self.response_cache:
                return self.response_cache[endpoint]
            return APIResponse(
                success=False,
                status_code=503,
                data={"error": "Service unavailable (offline)"}
            )
        
        # Track request count
        self.request_count[endpoint] = self.request_count.get(endpoint, 0) + 1
        
        # Check for error injection
        for injection in self.error_injections:
            if injection.endpoint == endpoint:
                if self.request_count[endpoint] <= injection.trigger_count:
                    response = APIResponse(
                        success=False,
                        status_code=injection.error_code,
                        data={"error": injection.error_message}
                    )
                    if self.offline:
                        self.response_cache[endpoint] = response
                    return response
        
        # Get normal response
        if endpoint not in self.responses:
            return APIResponse(
                success=False,
                status_code=404,
                data={"error": f"Endpoint '{endpoint}' not found"}
            )
        
        response = self.responses[endpoint]
        
        # Simulate network delay
        if response.delay_ms > 0:
            delay_seconds = response.delay_ms / 1000.0
            
            # Check timeout
            if response.delay_ms > timeout_ms:
                return APIResponse(
                    success=False,
                    status_code=408,
                    data={"error": f"Request timeout (delay: {response.delay_ms}ms, timeout: {timeout_ms}ms)"}
                )
            
            time.sleep(delay_seconds)
        
        # Cache response for offline mode
        if not skip_cache:
            self.response_cache[endpoint] = response
        
        return response
    
    def set_offline(self, offline: bool) -> None:
        """Set offline mode"""
        self.offline = offline
    
    def is_offline(self) -> bool:
        """Check if in offline mode"""
        return self.offline
    
    def get_request_count(self, endpoint: str) -> int:
        """Get number of requests made to endpoint"""
        return self.request_count.get(endpoint, 0)
    
    def reset(self) -> None:
        """Reset all state"""
        self.responses.clear()
        self.error_injections.clear()
        self.request_count.clear()
        self.response_cache.clear()
        self.offline = False


class APIClient:
    """Simple API client that uses NetworkMock"""
    
    def __init__(self, network_mock: NetworkMock):
        self.network = network_mock
    
    def call(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Call an API endpoint"""
        timeout_ms = kwargs.get('timeout_ms', 5000)
        response = self.network.get_response(endpoint, timeout_ms=timeout_ms)
        
        if not response.success:
            raise Exception(f"API Error: {response.status_code} - {response.data.get('error', 'Unknown')}")
        
        return response.data
