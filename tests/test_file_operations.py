"""Tests for file operations."""

import os
import tempfile
import pytest
from unittest.mock import patch, mock_open

from coffeebreak.utils.files import FileManager


class TestFileManager:
    """Test file manager functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.file_manager = FileManager(verbose=False)
        self.temp_dir = tempfile.mkdtemp()
    
    def test_generate_env_file_basic(self):
        """Test basic environment file generation."""
        connection_info = {
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'MONGODB_URL': 'mongodb://user:pass@localhost:27017/db'
        }
        
        output_path = os.path.join(self.temp_dir, '.env.test')
        
        result_path = self.file_manager.generate_env_file(
            connection_info=connection_info,
            output_path=output_path,
            include_secrets=False
        )
        
        assert result_path == output_path
        assert os.path.exists(output_path)
        
        # Verify file contents
        with open(output_path, 'r') as f:
            content = f.read()
            
        assert 'DATABASE_URL=postgresql://user:pass@localhost:5432/db' in content
        assert 'MONGODB_URL=mongodb://user:pass@localhost:27017/db' in content
        assert 'COFFEEBREAK_ENV=development' in content
    
    def test_generate_env_file_with_secrets(self):
        """Test environment file generation with secrets."""
        connection_info = {'DATABASE_URL': 'postgresql://localhost:5432/db'}
        output_path = os.path.join(self.temp_dir, '.env.test')
        
        result_path = self.file_manager.generate_env_file(
            connection_info=connection_info,
            output_path=output_path,
            include_secrets=True
        )
        
        with open(output_path, 'r') as f:
            content = f.read()
        
        # Should include development secrets
        assert 'DB_PASSWORD=' in content
        assert 'JWT_SECRET=' in content
        assert 'API_SECRET_KEY=' in content
    
    def test_generate_env_file_permissions(self):
        """Test that generated env file has correct permissions."""
        connection_info = {'TEST_VAR': 'test_value'}
        output_path = os.path.join(self.temp_dir, '.env.test')
        
        self.file_manager.generate_env_file(
            connection_info=connection_info,
            output_path=output_path
        )
        
        # Check file permissions (should be 600 - user read/write only)
        file_mode = os.stat(output_path).st_mode
        permissions = file_mode & 0o777
        assert permissions == 0o600
    
    def test_create_gitignore_new_file(self):
        """Test creating new .gitignore file."""
        gitignore_path = os.path.join(self.temp_dir, '.gitignore')
        
        result_path = self.file_manager.create_gitignore(gitignore_path)
        
        assert result_path == gitignore_path
        assert os.path.exists(gitignore_path)
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        assert '.env.local' in content
        assert '*.log' in content
        assert 'node_modules/' in content
    
    def test_create_gitignore_update_existing(self):
        """Test updating existing .gitignore file."""
        gitignore_path = os.path.join(self.temp_dir, '.gitignore')
        
        # Create existing .gitignore with some content
        existing_content = "# Existing content\n*.pyc\n"
        with open(gitignore_path, 'w') as f:
            f.write(existing_content)
        
        self.file_manager.create_gitignore(gitignore_path)
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        # Should preserve existing content and add new entries
        assert existing_content.strip() in content
        assert '.env.local' in content
    
    def test_create_directory_structure(self):
        """Test creating directory structure from specification."""
        structure = {
            'src': {
                'components': {},
                'utils': {
                    'helpers.py': 'def helper_function():\n    pass\n'
                }
            },
            'tests': {},
            'README.md': '# Test Project\n'
        }
        
        created_paths = self.file_manager.create_directory_structure(
            self.temp_dir, structure
        )
        
        # Verify directories were created
        assert os.path.isdir(os.path.join(self.temp_dir, 'src'))
        assert os.path.isdir(os.path.join(self.temp_dir, 'src', 'components'))
        assert os.path.isdir(os.path.join(self.temp_dir, 'src', 'utils'))
        assert os.path.isdir(os.path.join(self.temp_dir, 'tests'))
        
        # Verify files were created with content
        helpers_path = os.path.join(self.temp_dir, 'src', 'utils', 'helpers.py')
        assert os.path.isfile(helpers_path)
        
        with open(helpers_path, 'r') as f:
            content = f.read()
        assert 'def helper_function()' in content
        
        readme_path = os.path.join(self.temp_dir, 'README.md')
        assert os.path.isfile(readme_path)
        
        # Verify return value
        assert len(created_paths) > 0
    
    def test_set_file_permissions(self):
        """Test setting file permissions."""
        test_file = os.path.join(self.temp_dir, 'test.txt')
        
        # Create test file
        with open(test_file, 'w') as f:
            f.write('test content')
        
        # Set specific permissions
        self.file_manager.set_file_permissions(test_file, 0o644)
        
        # Verify permissions
        file_mode = os.stat(test_file).st_mode
        permissions = file_mode & 0o777
        assert permissions == 0o644
    
    def test_backup_file(self):
        """Test creating file backup."""
        original_file = os.path.join(self.temp_dir, 'original.txt')
        original_content = 'Original content'
        
        # Create original file
        with open(original_file, 'w') as f:
            f.write(original_content)
        
        # Create backup
        backup_path = self.file_manager.backup_file(original_file)
        
        # Verify backup exists
        assert os.path.exists(backup_path)
        assert backup_path.endswith('.backup')
        
        # Verify backup content
        with open(backup_path, 'r') as f:
            backup_content = f.read()
        
        assert backup_content == original_content
    
    def test_backup_file_multiple_backups(self):
        """Test creating multiple backups of the same file."""
        original_file = os.path.join(self.temp_dir, 'original.txt')
        
        with open(original_file, 'w') as f:
            f.write('test content')
        
        # Create first backup
        backup1 = self.file_manager.backup_file(original_file)
        
        # Create second backup
        backup2 = self.file_manager.backup_file(original_file)
        
        # Should create numbered backups
        assert backup1 != backup2
        assert os.path.exists(backup1)
        assert os.path.exists(backup2)
        assert '.backup.1' in backup2
    
    def test_backup_file_not_found(self):
        """Test backing up non-existent file."""
        non_existent = os.path.join(self.temp_dir, 'does_not_exist.txt')
        
        with pytest.raises(FileNotFoundError):
            self.file_manager.backup_file(non_existent)
    
    def test_generate_development_secrets(self):
        """Test development secrets generation."""
        secrets = self.file_manager._generate_development_secrets()
        
        # Verify expected secret keys
        expected_keys = [
            'DB_PASSWORD', 'MONGODB_PASSWORD', 'RABBITMQ_PASSWORD',
            'JWT_SECRET', 'API_SECRET_KEY', 'ENCRYPTION_KEY',
            'SESSION_SECRET', 'KEYCLOAK_ADMIN_PASSWORD'
        ]
        
        for key in expected_keys:
            assert key in secrets
            assert len(secrets[key]) > 0
        
        # Verify passwords have adequate length
        assert len(secrets['DB_PASSWORD']) >= 16
        assert len(secrets['JWT_SECRET']) >= 16
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)