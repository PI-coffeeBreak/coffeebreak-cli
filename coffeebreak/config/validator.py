"""Configuration validation for CoffeeBreak CLI."""

from typing import Any, Dict, List

import jsonschema
import yaml

from .schemas import MAIN_CONFIG_SCHEMA, PLUGIN_CONFIG_SCHEMA


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {'; '.join(errors)}")


class ConfigValidator:
    """Validates CoffeeBreak configuration files."""

    def __init__(self):
        """Initialize validator."""
        pass

    def validate_main_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate main CoffeeBreak configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        try:
            jsonschema.validate(config, MAIN_CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema error: {e.message}")

        # Additional validation logic
        if "coffeebreak" in config:
            cb_config = config["coffeebreak"]

            # Validate repository URLs
            if "repositories" in cb_config:
                for repo in cb_config["repositories"]:
                    if "url" in repo:
                        url_errors = self._validate_repository_url(repo["url"])
                        errors.extend(url_errors)

            # Validate version format
            if "version" in cb_config:
                version_errors = self._validate_version(cb_config["version"])
                errors.extend(version_errors)

        return errors

    def validate_plugin_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate plugin configuration.

        Args:
            config: Plugin configuration dictionary to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        try:
            jsonschema.validate(config, PLUGIN_CONFIG_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema error: {e.message}")

        # Additional validation logic
        if "plugin" in config:
            plugin_config = config["plugin"]

            # Validate plugin name format
            if "name" in plugin_config:
                name_errors = self._validate_plugin_name(plugin_config["name"])
                errors.extend(name_errors)

            # Validate version format
            if "version" in plugin_config:
                version_errors = self._validate_version(plugin_config["version"])
                errors.extend(version_errors)

        # Validate API endpoints
        if "api_endpoints" in config:
            for endpoint in config["api_endpoints"]:
                endpoint_errors = self._validate_api_endpoint(endpoint)
                errors.extend(endpoint_errors)

        return errors

    def validate_config_file(self, file_path: str, config_type: str = "auto") -> List[str]:
        """
        Validate configuration file.

        Args:
            file_path: Path to configuration file
            config_type: Type of config ('main', 'plugin', 'auto')

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        try:
            with open(file_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            return [f"Configuration file not found: {file_path}"]
        except yaml.YAMLError as e:
            return [f"YAML parsing error: {e}"]
        except Exception as e:
            return [f"Error reading configuration file: {e}"]

        if config is None:
            return ["Configuration file is empty"]

        # Auto-detect config type if needed
        if config_type == "auto":
            if "coffeebreak" in config:
                config_type = "main"
            elif "plugin" in config:
                config_type = "plugin"
            else:
                return ["Unable to determine configuration type"]

        # Validate based on type
        if config_type == "main":
            errors = self.validate_main_config(config)
        elif config_type == "plugin":
            errors = self.validate_plugin_config(config)
        else:
            errors = [f"Unknown configuration type: {config_type}"]

        return errors

    def _validate_repository_url(self, url: str) -> List[str]:
        """Validate repository URL format."""
        errors = []

        if not url:
            errors.append("Repository URL cannot be empty")
            return errors

        valid_patterns = ["https://github.com/", "git@github.com:"]

        if not any(url.startswith(pattern) for pattern in valid_patterns):
            errors.append(f"Invalid repository URL format: {url}")

        if not url.endswith(".git"):
            errors.append(f"Repository URL must end with .git: {url}")

        return errors

    def _validate_version(self, version: str) -> List[str]:
        """Validate semantic version format."""
        errors = []

        if not version:
            errors.append("Version cannot be empty")
            return errors

        parts = version.split(".")
        if len(parts) != 3:
            errors.append(f"Version must be in format X.Y.Z: {version}")
            return errors

        for i, part in enumerate(parts):
            try:
                int(part)
            except ValueError:
                errors.append(f"Version part {i + 1} must be numeric: {part}")

        return errors

    def _validate_plugin_name(self, name: str) -> List[str]:
        """Validate plugin name format."""
        errors = []

        if not name:
            errors.append("Plugin name cannot be empty")
            return errors

        if not name.replace("-", "").replace("_", "").isalnum():
            errors.append(f"Plugin name can only contain letters, numbers, hyphens, and underscores: {name}")

        if name.startswith("-") or name.startswith("_"):
            errors.append(f"Plugin name cannot start with hyphen or underscore: {name}")

        if name.endswith("-") or name.endswith("_"):
            errors.append(f"Plugin name cannot end with hyphen or underscore: {name}")

        return errors

    def _validate_api_endpoint(self, endpoint: Dict[str, Any]) -> List[str]:
        """Validate API endpoint configuration."""
        errors = []

        if "path" not in endpoint:
            errors.append("API endpoint must have a path")
            return errors

        path = endpoint["path"]
        if not path.startswith("/"):
            errors.append(f"API endpoint path must start with /: {path}")

        if "methods" not in endpoint:
            errors.append("API endpoint must specify HTTP methods")
        else:
            valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
            for method in endpoint["methods"]:
                if method not in valid_methods:
                    errors.append(f"Invalid HTTP method: {method}")

        return errors
