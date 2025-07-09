"""Configuration management for CoffeeBreak CLI."""

from .manager import ConfigManager
from .schemas import MAIN_CONFIG_SCHEMA, PLUGIN_CONFIG_SCHEMA

__all__ = ['ConfigManager', 'MAIN_CONFIG_SCHEMA', 'PLUGIN_CONFIG_SCHEMA']