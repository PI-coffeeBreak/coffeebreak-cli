"""Container management for CoffeeBreak CLI."""

from .dependencies import DependencyManager
from .manager import ContainerManager


# Lazy import for health checker to avoid docker import issues
def get_health_checker():
    """Get HealthChecker class, importing it only when needed."""
    try:
        from .health import HealthChecker
        return HealthChecker
    except ImportError:
        # Return None if docker is not available
        return None

__all__ = ["ContainerManager", "DependencyManager", "get_health_checker"]
