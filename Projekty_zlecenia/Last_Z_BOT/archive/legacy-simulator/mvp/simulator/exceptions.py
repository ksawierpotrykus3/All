"""
Exception hierarchy for Extended Game Simulator.

Defines all custom exceptions used throughout the simulator for consistent error handling.
"""


class SimulatorError(Exception):
    """Base exception for all simulator errors."""
    
    pass


class ConfigurationError(SimulatorError):
    """Raised when configuration is invalid or missing required fields."""
    
    pass


class SimulationError(SimulatorError):
    """Raised during simulation execution."""
    
    pass


class IterationError(SimulationError):
    """Raised when an iteration fails."""
    
    pass


class MetricsError(SimulatorError):
    """Raised when metrics collection or aggregation fails."""
    
    pass


class ReportingError(SimulatorError):
    """Raised when report generation fails."""
    
    pass


class VisualizationError(ReportingError):
    """Raised when chart/visualization generation fails."""
    
    pass


class BotIntegrationError(SimulationError):
    """Raised when bot integration fails."""
    
    pass


class UIError(SimulatorError):
    """Raised when UI initialization or rendering fails."""
    
    pass


class ThreadError(SimulatorError):
    """Raised when threading operations fail."""
    
    pass


class CircuitBreakerOpen(SimulatorError):
    """Raised when circuit breaker is open (too many failures)."""
    
    pass


class RetryExhausted(SimulatorError):
    """Raised when retries are exhausted."""
    
    pass


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient (can be retried).
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is transient, False otherwise
    """
    transient_exceptions = (
        TimeoutError,
        ConnectionError,
        BrokenPipeError,
        ConnectionResetError,
        IOError,
    )
    
    return isinstance(error, transient_exceptions)
