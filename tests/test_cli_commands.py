"""Tests for CLI commands."""

import pytest
import sys
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

# Mock docker module for testing
sys.modules['docker'] = MagicMock()

from coffeebreak.cli import cli


class TestCLICommands:
    """Test CLI command functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
    
    def test_cli_version(self):
        """Test CLI version display."""
        result = self.runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert 'version' in result.output.lower()
    
    def test_cli_help(self):
        """Test CLI help display."""
        result = self.runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'CoffeeBreak CLI' in result.output
        assert 'Commands:' in result.output
    
    def test_cli_verbose_flag(self):
        """Test verbose flag functionality."""
        result = self.runner.invoke(cli, ['--verbose', '--help'])
        
        assert result.exit_code == 0
        # Verbose flag should be processed without error
    
    def test_cli_dry_run_flag(self):
        """Test dry-run flag functionality."""
        result = self.runner.invoke(cli, ['--dry-run', 'build'])
        
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
    
    def test_init_dev_command(self):
        """Test init dev command."""
        with patch('coffeebreak.config.ConfigManager') as mock_config:
            with patch('coffeebreak.environments.DevelopmentEnvironment') as mock_dev_env:
                mock_dev_instance = MagicMock()
                mock_dev_instance.initialize.return_value = True
                mock_dev_env.return_value = mock_dev_instance
                
                result = self.runner.invoke(cli, ['init', 'dev'])
                
                assert result.exit_code == 0
                assert 'Initializing CoffeeBreak development environment' in result.output
    
    def test_init_dev_command_with_options(self):
        """Test init dev command with custom options."""
        with patch('coffeebreak.config.ConfigManager'):
            with patch('coffeebreak.environments.DevelopmentEnvironment') as mock_dev_env:
                mock_dev_instance = MagicMock()
                mock_dev_instance.initialize.return_value = True
                mock_dev_env.return_value = mock_dev_instance
                
                result = self.runner.invoke(cli, [
                    'init', 'dev', 
                    '--organization', 'test-org',
                    '--version', '2.0.0'
                ])
                
                assert result.exit_code == 0
                mock_dev_instance.initialize.assert_called_with(
                    organization='test-org',
                    version='2.0.0'
                )
    
    def test_init_dev_command_failure(self):
        """Test init dev command with initialization failure."""
        with patch('coffeebreak.config.ConfigManager'):
            with patch('coffeebreak.environments.DevelopmentEnvironment') as mock_dev_env:
                mock_dev_instance = MagicMock()
                mock_dev_instance.initialize.return_value = False
                mock_dev_env.return_value = mock_dev_instance
                
                result = self.runner.invoke(cli, ['init', 'dev'])
                
                assert result.exit_code == 1
                assert 'Failed to initialize development environment' in result.output
    
    def test_init_production_command(self):
        """Test init production command."""
        result = self.runner.invoke(cli, ['init', 'production'])
        
        assert result.exit_code == 0
        assert 'Initializing CoffeeBreak production environment' in result.output
    
    def test_build_command_without_plugin(self):
        """Test build command without plugin specification."""
        result = self.runner.invoke(cli, ['build'])
        
        assert result.exit_code == 0
        assert 'Building CoffeeBreak system' in result.output
    
    def test_build_command_with_plugin(self):
        """Test build command with plugin specification."""
        result = self.runner.invoke(cli, ['build', 'test-plugin'])
        
        assert result.exit_code == 0
        assert 'Building plugin: test-plugin' in result.output
    
    def test_deploy_command(self):
        """Test deploy command."""
        result = self.runner.invoke(cli, ['deploy'])
        
        assert result.exit_code == 0
        assert 'Deploying to production' in result.output
    
    def test_deps_start_command(self):
        """Test deps start command."""
        result = self.runner.invoke(cli, ['deps', 'start'])
        
        assert result.exit_code == 0
        assert 'Starting all dependency containers' in result.output
    
    def test_deps_start_with_services(self):
        """Test deps start command with specific services."""
        result = self.runner.invoke(cli, ['deps', 'start', 'postgres', 'mongodb'])
        
        assert result.exit_code == 0
        assert 'Starting services: postgres, mongodb' in result.output
    
    def test_deps_start_with_profile(self):
        """Test deps start command with profile."""
        result = self.runner.invoke(cli, ['deps', 'start', '--profile', 'minimal'])
        
        assert result.exit_code == 0
        assert 'Starting dependencies with profile: minimal' in result.output
    
    def test_deps_stop_command(self):
        """Test deps stop command."""
        result = self.runner.invoke(cli, ['deps', 'stop'])
        
        assert result.exit_code == 0
        assert 'Stopping dependency containers' in result.output
    
    def test_deps_status_command(self):
        """Test deps status command."""
        with patch('sys.modules', {'coffeebreak.containers': MagicMock()}):
            with patch('coffeebreak.containers.DependencyManager') as mock_deps:
                # Mock the dependency manager to avoid Docker dependency
                mock_instance = mock_deps.return_value
                mock_instance.get_health_status.return_value = {
                    'total_containers': 0,
                    'healthy': 0,
                    'overall_status': 'unknown',
                    'monitoring_active': False,
                    'containers': {}
                }
                
                result = self.runner.invoke(cli, ['deps', 'status'])
                
                assert result.exit_code == 0
                assert 'No dependency containers running' in result.output
    
    def test_deps_logs_command(self):
        """Test deps logs command."""
        result = self.runner.invoke(cli, ['deps', 'logs'])
        
        assert result.exit_code == 0
        assert 'Showing logs for all dependencies' in result.output
    
    def test_deps_logs_with_service(self):
        """Test deps logs command with specific service."""
        result = self.runner.invoke(cli, ['deps', 'logs', 'postgres'])
        
        assert result.exit_code == 0
        assert 'Showing logs for service: postgres' in result.output
    
    def test_deps_env_command(self):
        """Test deps env command."""
        # Mock the imports that happen inside the CLI command
        with patch('coffeebreak.config.ConfigManager') as mock_config_mgr:
            with patch('coffeebreak.utils.files.FileManager') as mock_file_mgr:
                # Create mock instances
                mock_config_instance = MagicMock()
                mock_config_mgr.return_value = mock_config_instance
                
                mock_file_instance = MagicMock()
                mock_file_instance.generate_env_file.return_value = '.env.local'
                mock_file_mgr.return_value = mock_file_instance
                
                # Mock the containers module to provide DependencyManager
                mock_containers_module = MagicMock()
                mock_deps_class = MagicMock()
                mock_containers_module.DependencyManager = mock_deps_class
                
                mock_deps_instance = MagicMock()
                mock_deps_instance.generate_connection_info.return_value = {
                    'DATABASE_URL': 'postgresql://localhost:5432/db'
                }
                mock_deps_class.return_value = mock_deps_instance
                
                # Also mock the utils module since FileManager is imported from there
                mock_utils_module = MagicMock()
                mock_utils_module.FileManager = mock_file_mgr
                
                with patch.dict('sys.modules', {
                    'coffeebreak.containers': mock_containers_module,
                    'coffeebreak.utils': mock_utils_module
                }):
                    result = self.runner.invoke(cli, ['deps', 'env'])
                    
                    assert result.exit_code == 0
                    assert 'Generating .env.local file' in result.output
    
    def test_deps_clean_command(self):
        """Test deps clean command."""
        result = self.runner.invoke(cli, ['deps', 'clean'])
        
        assert result.exit_code == 0
        assert 'Cleaning up dependency containers' in result.output
    
    def test_plugin_create_command(self):
        """Test plugin create command."""
        with patch('coffeebreak.environments.plugin.PluginEnvironment') as mock_env:
            mock_instance = mock_env.return_value
            mock_instance.create_plugin.return_value = '/path/to/test-plugin'
            
            result = self.runner.invoke(cli, ['plugin', 'create', 'test-plugin'])
            
            assert result.exit_code == 0
            assert 'test-plugin' in result.output
    
    def test_plugin_create_with_template(self):
        """Test plugin create command with template."""
        with patch('coffeebreak.environments.plugin.PluginEnvironment') as mock_env:
            mock_instance = mock_env.return_value
            mock_instance.create_plugin.return_value = '/path/to/test-plugin'
            
            result = self.runner.invoke(cli, [
                'plugin', 'create', 'test-plugin', 
                '--template', 'react'
            ])
            
            assert result.exit_code == 0
            assert 'test-plugin' in result.output
    
    def test_plugin_init_command(self):
        """Test plugin init command."""
        with patch('coffeebreak.environments.plugin.PluginEnvironment') as mock_env:
            mock_instance = mock_env.return_value
            mock_instance.initialize_plugin_dev.return_value = True
            
            result = self.runner.invoke(cli, ['plugin', 'init'])
            
            assert result.exit_code == 0
            assert 'initialized successfully' in result.output
    
    def test_plugin_build_command(self):
        """Test plugin build command."""
        with patch('coffeebreak.environments.plugin.PluginEnvironment') as mock_env, \
             patch('coffeebreak.config.ConfigManager') as mock_config, \
             patch('os.path.getsize', return_value=1024):
            mock_instance = mock_env.return_value
            mock_instance.build_plugin.return_value = '/path/to/plugin.pyz'
            
            result = self.runner.invoke(cli, ['plugin', 'build-plugin'])
            
            assert result.exit_code == 0
            assert 'built successfully' in result.output
    
    def test_plugin_publish_command(self):
        """Test plugin publish command shows not implemented."""
        result = self.runner.invoke(cli, ['plugin', 'publish'])
        
        assert result.exit_code == 0
        assert 'not yet implemented' in result.output
    
    def test_secrets_rotate_command(self):
        """Test secrets rotate command."""
        result = self.runner.invoke(cli, ['secrets', 'rotate'])
        
        assert result.exit_code == 0
        assert 'Rotating all secrets' in result.output
    
    def test_secrets_show_command(self):
        """Test secrets show command."""
        result = self.runner.invoke(cli, ['secrets', 'show'])
        
        assert result.exit_code == 0
        assert 'Displaying secrets' in result.output
    
    def test_secrets_backup_command(self):
        """Test secrets backup command."""
        result = self.runner.invoke(cli, ['secrets', 'backup'])
        
        assert result.exit_code == 0
        assert 'Backing up secrets' in result.output
    
    def test_production_install_command(self):
        """Test production install command."""
        result = self.runner.invoke(cli, [
            'production', 'install', 
            '--domain', 'example.com'
        ])
        
        assert result.exit_code == 0
        assert 'Installing CoffeeBreak for domain: example.com' in result.output
    
    def test_production_generate_command(self):
        """Test production generate command."""
        result = self.runner.invoke(cli, ['production', 'generate'])
        
        assert result.exit_code == 0
        assert 'Generating Docker production project' in result.output
    
    def test_production_deploy_command(self):
        """Test production deploy command."""
        result = self.runner.invoke(cli, ['production', 'deploy-prod'])
        
        assert result.exit_code == 0
        assert 'Deploying to configured production environment' in result.output