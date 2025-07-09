"""Environment management for CoffeeBreak CLI."""

from .detector import EnvironmentDetector
from .development import DevelopmentEnvironment
from .production import ProductionEnvironment

# Note: PluginEnvironment removed to avoid circular import
# Import it directly from .plugin when needed

__all__ = [
    'EnvironmentDetector',
    'DevelopmentEnvironment', 
    'ProductionEnvironment'
]