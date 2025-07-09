"""Pytest configuration and shared fixtures."""

import os
import tempfile
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    client = MagicMock()
    client.ping.return_value = True
    client.containers.list.return_value = []
    client.images.list.return_value = []
    client.networks.list.return_value = []
    return client


@pytest.fixture
def mock_git_repo():
    """Mock Git repository for testing."""
    repo = MagicMock()
    repo.git_dir = '/test/repo/.git'
    repo.working_dir = '/test/repo'
    repo.active_branch.name = 'main'
    return repo


@pytest.fixture
def sample_main_config():
    """Sample main configuration for testing."""
    return {
        'project': {
            'name': 'coffeebreak',
            'version': '1.0.0',
            'organization': 'PI-coffeeBreak'
        },
        'repositories': [
            {
                'name': 'core',
                'url': 'https://github.com/PI-coffeeBreak/core.git'
            },
            {
                'name': 'frontend',
                'url': 'https://github.com/PI-coffeeBreak/admin-frontend.git'
            },
            {
                'name': 'event-app',
                'url': 'https://github.com/PI-coffeeBreak/event-app.git'
            }
        ],
        'dependencies': {
            'postgresql': {
                'image': 'postgres:15',
                'environment': {
                    'POSTGRES_DB': 'coffeebreak',
                    'POSTGRES_USER': 'coffeebreak',
                    'POSTGRES_PASSWORD': 'development'
                },
                'ports': ['5432:5432']
            },
            'mongodb': {
                'image': 'mongo:6',
                'environment': {
                    'MONGO_INITDB_ROOT_USERNAME': 'coffeebreak',
                    'MONGO_INITDB_ROOT_PASSWORD': 'development'
                },
                'ports': ['27017:27017']
            },
            'rabbitmq': {
                'image': 'rabbitmq:3-management',
                'environment': {
                    'RABBITMQ_DEFAULT_USER': 'coffeebreak',
                    'RABBITMQ_DEFAULT_PASS': 'development'
                },
                'ports': ['5672:5672', '15672:15672']
            },
            'keycloak': {
                'image': 'quay.io/keycloak/keycloak:22',
                'environment': {
                    'KEYCLOAK_ADMIN': 'admin',
                    'KEYCLOAK_ADMIN_PASSWORD': 'development'
                },
                'ports': ['8080:8080']
            }
        }
    }


@pytest.fixture
def sample_plugin_config():
    """Sample plugin configuration for testing."""
    return {
        'plugin': {
            'name': 'test-plugin',
            'version': '1.0.0',
            'description': 'Test plugin for CoffeeBreak'
        },
        'development': {
            'api_url': 'http://localhost:3000',
            'hot_reload': True
        },
        'build': {
            'entry': 'src/index.js',
            'output': 'dist'
        }
    }


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """Mock environment variables for testing."""
    test_env = {
        'COFFEEBREAK_ENV': 'test',
        'DEBUG': 'true',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db'
    }
    
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    
    return test_env


@pytest.fixture
def mock_file_system(temp_directory):
    """Mock file system structure for testing."""
    file_structure = {
        'coffeebreak.yml': """
project:
  name: coffeebreak
  version: 1.0.0
  organization: PI-coffeeBreak
repositories:
  - name: core
    url: https://github.com/PI-coffeeBreak/core.git
""",
        'src': {
            'main.py': 'print("Hello, CoffeeBreak!")',
            'config.py': 'CONFIG = {"debug": True}'
        },
        'tests': {
            'test_main.py': 'def test_main(): assert True'
        },
        '.gitignore': '*.pyc\n__pycache__/\n'
    }
    
    def create_structure(base_path, structure):
        for name, content in structure.items():
            path = os.path.join(base_path, name)
            
            if isinstance(content, dict):
                os.makedirs(path, exist_ok=True)
                create_structure(path, content)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
    
    create_structure(temp_directory, file_structure)
    return temp_directory


@pytest.fixture(autouse=True)
def isolate_filesystem(temp_directory, monkeypatch):
    """Isolate filesystem operations to temporary directory."""
    monkeypatch.chdir(temp_directory)
    return temp_directory