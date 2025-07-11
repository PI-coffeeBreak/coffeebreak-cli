"""Plugin management for CoffeeBreak CLI."""

from .builder import PluginBuilder
from .creator import PluginCreator
from .dependencies import PluginDependencyManager
from .devtools import PluginDeveloperTools
from .documentation import PluginDocumentationGenerator
from .hotreload import PluginDevelopmentWorkflow, PluginHotReloadManager
from .integration import PluginContainerIntegration
from .testing import PluginTestFramework
from .validator import PluginValidator

__all__ = [
    "PluginCreator",
    "PluginBuilder",
    "PluginValidator",
    "PluginContainerIntegration",
    "PluginHotReloadManager",
    "PluginDevelopmentWorkflow",
    "PluginDependencyManager",
    "PluginTestFramework",
    "PluginDocumentationGenerator",
    "PluginDeveloperTools",
]
