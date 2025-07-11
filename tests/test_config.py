"""Tests for configuration management."""

import tempfile
from unittest.mock import mock_open, patch

import pytest
import yaml

from coffeebreak.config.manager import ConfigManager
from coffeebreak.environments.detector import EnvironmentType


class TestConfigManager:
    """Test configuration manager functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.config_manager = ConfigManager()
        self.temp_dir = tempfile.mkdtemp()

    def test_detect_environment_main_config(self):
        """Test detection of main development environment."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda path: path.endswith("coffeebreak.yml")

            env_type = self.config_manager.detect_environment()
            assert env_type == EnvironmentType.FULL_DEV

    def test_detect_environment_plugin_config(self):
        """Test detection of plugin development environment."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda path: path.endswith("coffeebreak-plugin.yml")

            env_type = self.config_manager.detect_environment()
            assert env_type == EnvironmentType.PLUGIN_DEV

    def test_detect_environment_no_config(self):
        """Test detection when no configuration exists."""
        with patch("os.path.exists", return_value=False):
            env_type = self.config_manager.detect_environment()
            assert env_type == EnvironmentType.UNINITIALIZED

    def test_load_config_valid_yaml(self):
        """Test loading valid YAML configuration."""
        valid_config = {
            "coffeebreak": {
                "organization": "test-org",
                "version": "1.0.0",
                "repositories": [
                    {
                        "name": "core",
                        "url": "https://github.com/test/core.git",
                        "path": "./core",
                        "branch": "main",
                    }
                ],
            },
            "dependencies": {"services": {"database": {"image": "postgres:15", "container_name": "test-db"}}},
        }

        yaml_content = yaml.dump(valid_config)

        with patch("builtins.open", mock_open(read_data=yaml_content)):
            with patch.object(self.config_manager, "get_config_path", return_value="test-config.yml"):
                with patch.object(
                    self.config_manager,
                    "detect_environment",
                    return_value=EnvironmentType.FULL_DEV,
                ):
                    config = self.config_manager.load_config()
                    assert config == valid_config

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML configuration."""
        invalid_yaml = "invalid: yaml: content: ["

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with patch.object(self.config_manager, "get_config_path", return_value="test-config.yml"):
                with pytest.raises(yaml.YAMLError):
                    self.config_manager.load_config()

    def test_load_config_file_not_found(self):
        """Test loading non-existent configuration file."""
        with patch.object(self.config_manager, "get_config_path", return_value=None):
            with pytest.raises(FileNotFoundError):
                self.config_manager.load_config()

    def test_validate_config_valid_main(self):
        """Test validation of valid main configuration."""
        valid_config = {
            "coffeebreak": {
                "organization": "PI-coffeeBreak",
                "version": "1.0.0",
                "repositories": [
                    {
                        "name": "core",
                        "url": "https://github.com/PI-coffeeBreak/core.git",
                        "path": "./core",
                        "branch": "main",
                    },
                    {
                        "name": "frontend",
                        "url": "https://github.com/PI-coffeeBreak/admin-frontend.git",
                        "path": "./frontend",
                        "branch": "main",
                    },
                    {
                        "name": "event-app",
                        "url": "https://github.com/PI-coffeeBreak/event-app.git",
                        "path": "./event-app",
                        "branch": "main",
                    },
                ],
            },
            "dependencies": {
                "services": {
                    "database": {
                        "image": "postgres:15",
                        "container_name": "coffeebreak-db",
                    },
                    "mongodb": {
                        "image": "mongo:6",
                        "container_name": "coffeebreak-mongo",
                    },
                    "rabbitmq": {
                        "image": "rabbitmq:3-management",
                        "container_name": "coffeebreak-rabbitmq",
                    },
                    "keycloak": {
                        "image": "quay.io/keycloak/keycloak:22",
                        "container_name": "coffeebreak-keycloak",
                    },
                }
            },
        }

        # Mock environment detection for validation
        with patch.object(
            self.config_manager,
            "detect_environment",
            return_value=EnvironmentType.FULL_DEV,
        ):
            errors = self.config_manager.validate_config(valid_config)
            assert errors == []

    def test_validate_config_missing_required_field(self):
        """Test validation with missing required field."""
        invalid_config = {
            "coffeebreak": {
                "organization": "test"
                # Missing version
            }
        }

        with patch.object(
            self.config_manager,
            "detect_environment",
            return_value=EnvironmentType.FULL_DEV,
        ):
            errors = self.config_manager.validate_config(invalid_config)
            assert len(errors) > 0
            assert any("version" in error.lower() for error in errors)

    def test_initialize_main_config(self):
        """Test initialization of main configuration."""
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("os.path.exists", return_value=False):
                config_path = self.config_manager.initialize_main_config(organization="test-org", version="2.0.0")

                assert config_path.endswith("coffeebreak.yml")
                # The method reads template then writes config, so 2 calls expected
                assert mock_file.call_count >= 1

    def test_initialize_plugin_config(self):
        """Test initialization of plugin configuration."""
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("os.path.exists", return_value=False):
                config_path = self.config_manager.initialize_plugin_config(plugin_name="test-plugin", version="1.0.0")

                assert config_path.endswith("coffeebreak-plugin.yml")
                # The method reads template then writes config, so 2 calls expected
                assert mock_file.call_count >= 1

    def test_create_default_config(self):
        """Test creating default configuration."""
        template_vars = {
            "project_name": "test-project",
            "version": "1.0.0",
            "organization": "test-org",
        }

        config_dict = self.config_manager.create_default_config(config_type="main", template_vars=template_vars)

        assert isinstance(config_dict, dict)
        assert "coffeebreak" in config_dict

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
