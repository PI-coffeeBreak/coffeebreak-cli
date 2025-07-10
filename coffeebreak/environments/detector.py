"""Environment detection logic for CoffeeBreak CLI."""

import os
from typing import Optional
from enum import Enum


class EnvironmentType(Enum):
    """Supported environment types."""

    FULL_DEV = "dev"
    PLUGIN_DEV = "plugin-dev"
    PRODUCTION = "production"
    UNINITIALIZED = "uninitialized"


class EnvironmentDetector:
    """Detects the current environment type based on directory contents."""

    def __init__(self, path: Optional[str] = None):
        """Initialize detector with optional custom path."""
        self.path = path or os.getcwd()

    def detect_environment(self) -> EnvironmentType:
        """
        Detect environment type based on configuration files present.

        Returns:
            EnvironmentType: The detected environment type
        """
        # Check for plugin development context
        plugin_config = os.path.join(self.path, "coffeebreak-plugin.yml")
        if os.path.exists(plugin_config):
            return EnvironmentType.PLUGIN_DEV

        # Check for full development context
        main_config = os.path.join(self.path, "coffeebreak.yml")
        if os.path.exists(main_config):
            return EnvironmentType.FULL_DEV

        # Check for production indicators
        production_config = "/etc/coffeebreak/config.yml"
        if os.path.exists(production_config):
            return EnvironmentType.PRODUCTION

        # No configuration found - uninitialized
        return EnvironmentType.UNINITIALIZED

    def get_config_path(self) -> Optional[str]:
        """
        Get the path to the configuration file for the detected environment.

        Returns:
            Optional[str]: Path to config file or None if uninitialized
        """
        env_type = self.detect_environment()

        if env_type == EnvironmentType.PLUGIN_DEV:
            return os.path.join(self.path, "coffeebreak-plugin.yml")
        elif env_type == EnvironmentType.FULL_DEV:
            return os.path.join(self.path, "coffeebreak.yml")
        elif env_type == EnvironmentType.PRODUCTION:
            return "/etc/coffeebreak/config.yml"

        return None

    def is_initialized(self) -> bool:
        """Check if current directory is initialized for any environment."""
        return self.detect_environment() != EnvironmentType.UNINITIALIZED

    def is_plugin_environment(self) -> bool:
        """Check if current directory is a plugin development environment."""
        return self.detect_environment() == EnvironmentType.PLUGIN_DEV

    def is_full_dev_environment(self) -> bool:
        """Check if current directory is a full development environment."""
        return self.detect_environment() == EnvironmentType.FULL_DEV

    def is_production_environment(self) -> bool:
        """Check if current directory is a production environment."""
        return self.detect_environment() == EnvironmentType.PRODUCTION

    def get_environment_description(self) -> str:
        """Get a human-readable description of the detected environment."""
        env_type = self.detect_environment()

        descriptions = {
            EnvironmentType.FULL_DEV: "Full CoffeeBreak development environment",
            EnvironmentType.PLUGIN_DEV: "CoffeeBreak plugin development environment",
            EnvironmentType.PRODUCTION: "CoffeeBreak production environment",
            EnvironmentType.UNINITIALIZED: "Uninitialized directory",
        }

        return descriptions[env_type]

    def get_expected_structure(self) -> dict:
        """
        Get the expected directory structure for the detected environment.

        Returns:
            dict: Expected files and directories for this environment type
        """
        env_type = self.detect_environment()

        if env_type == EnvironmentType.FULL_DEV:
            return {
                "required_files": ["coffeebreak.yml"],
                "expected_dirs": ["core", "frontend", "event-app"],
                "optional_files": [".env.local", ".env.secrets"],
            }
        elif env_type == EnvironmentType.PLUGIN_DEV:
            return {
                "required_files": ["coffeebreak-plugin.yml"],
                "expected_dirs": ["src", "scripts"],
                "optional_files": ["README.md", "LICENSE", ".env.local"],
            }
        elif env_type == EnvironmentType.PRODUCTION:
            return {
                "required_files": ["/etc/coffeebreak/config.yml"],
                "expected_dirs": ["/opt/coffeebreak", "/var/log/coffeebreak"],
                "optional_files": ["/etc/coffeebreak/secrets.yml"],
            }

        return {"required_files": [], "expected_dirs": [], "optional_files": []}
