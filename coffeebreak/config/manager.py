"""Configuration management for CoffeeBreak CLI."""

import os
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from coffeebreak.environments.detector import EnvironmentDetector, EnvironmentType

from .validator import ConfigValidationError, ConfigValidator


class ConfigManager:
    """Manages CoffeeBreak configuration files."""

    def __init__(self, path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            path: Optional custom path (defaults to current directory)
        """
        self.path = path or os.getcwd()
        self.detector = EnvironmentDetector(self.path)
        self.validator = ConfigValidator()
        self._config_cache = {}

        # Setup Jinja2 for template rendering
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir), trim_blocks=True, lstrip_blocks=True)

    def detect_environment(self) -> EnvironmentType:
        """Get the detected environment type."""
        return self.detector.detect_environment()

    def get_config_path(self) -> Optional[str]:
        """Get path to configuration file for current environment."""
        return self.detector.get_config_path()

    def load_config(self, validate: bool = True) -> Dict[str, Any]:
        """
        Load configuration for current environment.

        Args:
            validate: Whether to validate the configuration

        Returns:
            Dict[str, Any]: Loaded configuration

        Raises:
            ConfigValidationError: If validation fails
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        config_path = self.get_config_path()
        if not config_path:
            raise FileNotFoundError("No configuration file found for current environment")

        # Check cache first
        if config_path in self._config_cache:
            return self._config_cache[config_path]

        # Load configuration
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML file {config_path}: {e}")

        if config is None:
            config = {}

        # Validate if requested
        if validate:
            errors = self.validate_config(config)
            if errors:
                raise ConfigValidationError(errors)

        # Cache and return
        self._config_cache[config_path] = config
        return config

    def load_config_file(self, config_path: str, validate: bool = True) -> Dict[str, Any]:
        """
        Load configuration from a specific file.

        Args:
            config_path: Path to configuration file
            validate: Whether to validate the configuration

        Returns:
            Dict[str, Any]: Loaded configuration

        Raises:
            ConfigValidationError: If configuration is invalid
            FileNotFoundError: If config file doesn't exist
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            if validate:
                # Determine config type by filename
                if "plugin" in os.path.basename(config_path):
                    self.validator.validate_plugin_config(config)
                else:
                    self.validator.validate_main_config(config)

            return config

        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in {config_path}: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading config file {config_path}: {e}")

    def save_config(self, config: Dict[str, Any], config_path: Optional[str] = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration to save
            config_path: Optional custom path (defaults to detected path)
        """
        if config_path is None:
            config_path = self.get_config_path()
            if not config_path:
                raise ValueError("No configuration path available")

        # Validate before saving
        errors = self.validate_config(config)
        if errors:
            raise ConfigValidationError(errors)

        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Save configuration
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        # Update cache
        self._config_cache[config_path] = config

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration.

        Args:
            config: Configuration to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        env_type = self.detect_environment()

        if env_type == EnvironmentType.PLUGIN_DEV:
            return self.validator.validate_plugin_config(config)
        elif env_type in [EnvironmentType.FULL_DEV, EnvironmentType.PRODUCTION]:
            return self.validator.validate_main_config(config)
        else:
            return ["Cannot validate configuration for uninitialized environment"]

    def create_default_config(self, config_type: str, template_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create default configuration from template.

        Args:
            config_type: Type of config ('main' or 'plugin')
            template_vars: Variables for template rendering

        Returns:
            Dict[str, Any]: Generated configuration
        """
        template_vars = template_vars or {}

        if config_type == "main":
            template = self.jinja_env.get_template("coffeebreak.yml.j2")
            config_yaml = template.render(**template_vars)
        elif config_type == "plugin":
            template = self.jinja_env.get_template("coffeebreak-plugin.yml.j2")
            config_yaml = template.render(**template_vars)
        else:
            raise ValueError(f"Unknown config type: {config_type}")

        return yaml.safe_load(config_yaml)

    def initialize_main_config(
        self,
        organization: str = "PI-coffeeBreak",
        version: str = "1.0.0",
        environment: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Initialize main CoffeeBreak configuration file.

        Args:
            organization: GitHub organization name
            version: Project version
            environment: Environment information (venv/conda details)

        Returns:
            str: Path to created configuration file
        """
        template_vars = {
            "organization": organization,
            "version": version,
            "working_dir": os.path.abspath(self.path),
        }

        if environment:
            template_vars["environment"] = environment

        config = self.create_default_config("main", template_vars)

        # Add environment section directly to coffeebreak config
        if environment:
            config["coffeebreak"]["environment"] = {"type": environment["type"]}

            if environment["type"] == "venv" and "path" in environment:
                config["coffeebreak"]["environment"]["path"] = environment["path"]
            elif environment["type"] == "conda" and "name" in environment:
                config["coffeebreak"]["environment"]["name"] = environment["name"]

            if "python_path" in environment:
                config["coffeebreak"]["environment"]["python_path"] = environment["python_path"]

        config_path = os.path.join(self.path, "coffeebreak.yml")

        # Save configuration
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config_path

    def initialize_plugin_config(
        self,
        plugin_name: str,
        description: str = "A CoffeeBreak plugin",
        author: str = "Plugin Developer",
        version: str = "1.0.0",
    ) -> str:
        """
        Initialize plugin configuration file.

        Args:
            plugin_name: Name of the plugin
            description: Plugin description
            author: Plugin author
            version: Plugin version

        Returns:
            str: Path to created configuration file
        """
        template_vars = {
            "plugin_name": plugin_name,
            "description": description,
            "author": author,
            "version": version,
        }

        config = self.create_default_config("plugin", template_vars)
        config_path = os.path.join(self.path, "coffeebreak-plugin.yml")

        # Save configuration
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return config_path

    def get_repositories_config(self) -> List[Dict[str, Any]]:
        """
        Get repository configuration for current environment.

        Returns:
            List[Dict[str, Any]]: Repository configurations
        """
        config = self.load_config()

        if "coffeebreak" in config and "repositories" in config["coffeebreak"]:
            return config["coffeebreak"]["repositories"]

        return []

    def get_dependencies_config(self) -> Dict[str, Any]:
        """
        Get dependencies configuration.

        Returns:
            Dict[str, Any]: Dependencies configuration
        """
        config = self.load_config()

        if "dependencies" in config:
            return config["dependencies"]

        return {"profiles": {}, "services": {}}

    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._config_cache.clear()
