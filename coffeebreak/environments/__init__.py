"""Environment management for CoffeeBreak CLI."""

from .detector import EnvironmentDetector
from .development import DevelopmentEnvironment
from .production import ProductionEnvironment
# Do NOT import PluginEnvironment here to avoid circular imports.
# Import it directly from coffeebreak.environments.plugin where needed.

__all__ = ["EnvironmentDetector", "DevelopmentEnvironment", "ProductionEnvironment"]
