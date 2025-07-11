"""Development environment management."""

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import click

from coffeebreak.git.operations import GitOperationError, GitOperations
from coffeebreak.utils.errors import DevelopmentEnvironmentError

from .detector import EnvironmentDetector

if TYPE_CHECKING:
    from coffeebreak.config.manager import ConfigManager


class DevelopmentEnvironment:
    """Manages full CoffeeBreak development environment setup and operations."""

    def __init__(self, config_manager: "ConfigManager", verbose: bool = False):
        """Initialize with configuration manager."""
        self.config_manager = config_manager
        self.verbose = verbose
        self.git_ops = GitOperations(verbose=verbose)
        self.detector = EnvironmentDetector()
        self.config = None

    def initialize(
        self,
        organization: str = "PI-coffeeBreak",
        version: str = "1.0.0",
        env_type: str = "venv",
        env_path_or_name: Optional[str] = None,
        python_path: Optional[str] = None,
    ) -> bool:
        """
        Initialize a new development environment.

        Args:
            organization: GitHub organization name
            version: Project version
            env_type: Environment type ('venv' or 'conda')
            env_path_or_name: Path for venv or name for conda
            python_path: Path to specific Python executable

        Returns:
            bool: True if initialization successful

        Raises:
            DevelopmentEnvironmentError: If initialization fails
        """
        try:
            # Check if already initialized
            if self.detector.is_initialized():
                raise DevelopmentEnvironmentError("Development environment already initialized")

            # Setup Python environment first
            if self.verbose:
                click.echo("Setting up Python environment...")
            env_info = self._setup_python_environment(env_type, env_path_or_name, python_path)

            # Create configuration file with environment info
            config_path = self.config_manager.initialize_main_config(organization=organization, version=version, environment=env_info)

            if self.verbose:
                click.echo(f"Created configuration file: {config_path}")

            # Load the configuration
            self.config = self.config_manager.load_config()

            # Clone repositories
            success = self.clone_repositories()
            if not success:
                raise DevelopmentEnvironmentError("Repository cloning failed")

            # Install dependencies in cloned repositories
            if self.verbose:
                click.echo("Installing dependencies...")
            self._install_repository_dependencies(env_info)

            # Setup Keycloak configuration
            if self.verbose:
                click.echo("Setting up Keycloak configuration...")
            success = self._setup_keycloak_configuration()
            if not success:
                click.echo("Warning: Keycloak configuration setup failed, continuing anyway...")

            if self.verbose:
                click.echo("✓ Development environment initialized successfully")

            return True

        except Exception as e:
            raise DevelopmentEnvironmentError(f"Failed to initialize development environment: {e}")

    def start(self) -> bool:
        """
        Start the development environment.

        Returns:
            bool: True if start successful
        """
        # Implementation will be added in Phase 2
        if self.verbose:
            click.echo("Starting development environment...")
        return True

    def stop(self) -> bool:
        """
        Stop the development environment.

        Returns:
            bool: True if stop successful
        """
        # Implementation will be added in Phase 2
        if self.verbose:
            click.echo("Stopping development environment...")
        return True

    def status(self) -> Dict[str, str]:
        """
        Get status of development environment components.

        Returns:
            Dict[str, str]: Status of each component
        """
        # Implementation will be added in Phase 2
        status = {}

        # Check repository status
        try:
            repos_config = self.config_manager.get_repositories_config()
            for repo in repos_config:
                repo_status = self.git_ops.check_repository_status(repo["path"])
                status[repo["name"]] = "cloned" if repo_status["is_valid"] else "not cloned"
        except Exception as e:
            status["repositories"] = f"error: {e}"

        return status

    def clone_repositories(self) -> bool:
        """
        Clone all required CoffeeBreak repositories.

        Returns:
            bool: True if all repositories cloned successfully

        Raises:
            DevelopmentEnvironmentError: If cloning fails
        """
        try:
            # Load configuration if not already loaded
            if not self.config:
                self.config = self.config_manager.load_config()

            # Get repository configurations
            repos_config = self.config_manager.get_repositories_config()

            if not repos_config:
                raise DevelopmentEnvironmentError("No repositories configured")

            if self.verbose:
                click.echo(f"Cloning {len(repos_config)} repositories...")

            # Validate all repository URLs first
            for repo in repos_config:
                url = repo.get("url")
                if not url:
                    raise DevelopmentEnvironmentError(f"No URL configured for repository {repo.get('name')}")

                try:
                    self.git_ops.validate_repository_access(url)
                except GitOperationError as e:
                    raise DevelopmentEnvironmentError(f"Repository access validation failed for {repo.get('name')}: {e}")

            # Clone repositories
            cloned_repos = self.git_ops.clone_multiple_repositories(repos_config)

            if self.verbose:
                click.echo(f"✓ Successfully cloned {len(cloned_repos)} repositories")
                for name in cloned_repos.keys():
                    click.echo(f"  - {name}")

            return True

        except GitOperationError as e:
            raise DevelopmentEnvironmentError(f"Git operation failed: {e}")
        except Exception as e:
            raise DevelopmentEnvironmentError(f"Unexpected error cloning repositories: {e}")

    def _setup_keycloak_configuration(self) -> bool:
        """
        Setup Keycloak configuration files for development environment.

        Returns:
            bool: True if setup successful
        """
        try:
            # Create keycloak directory
            keycloak_dir = Path("./keycloak")
            keycloak_dir.mkdir(exist_ok=True)

            # Create subdirectories
            (keycloak_dir / "exports").mkdir(exist_ok=True)
            (keycloak_dir / "themes" / "coffeebreak" / "login" / "resources" / "css").mkdir(parents=True, exist_ok=True)
            (keycloak_dir / "themes" / "coffeebreak" / "login" / "resources" / "js").mkdir(parents=True, exist_ok=True)
            (keycloak_dir / "themes" / "coffeebreak" / "login" / "resources" / "img").mkdir(parents=True, exist_ok=True)
            (keycloak_dir / "providers").mkdir(exist_ok=True)

            # Generate Dockerfile
            self._generate_keycloak_dockerfile(keycloak_dir)
            if self.verbose:
                click.echo("  ✓ Generated Dockerfile")

            # Generate realm configuration
            self._generate_keycloak_realm(keycloak_dir)
            if self.verbose:
                click.echo("  ✓ Generated realm configuration")

            # Generate theme files
            self._generate_keycloak_theme(keycloak_dir)
            if self.verbose:
                click.echo("  ✓ Generated custom theme")

            if self.verbose:
                click.echo("✓ Keycloak configuration setup complete")

            return True

        except Exception as e:
            if self.verbose:
                click.echo(f"Error setting up Keycloak configuration: {e}")
            return False

    def _generate_keycloak_dockerfile(self, keycloak_dir: Path) -> None:
        """Generate Keycloak Dockerfile."""
        from coffeebreak.templates.keycloak import get_dockerfile_content

        dockerfile_content = get_dockerfile_content()
        with open(keycloak_dir / "Dockerfile", "w") as f:
            f.write(dockerfile_content)

    def _generate_keycloak_realm(self, keycloak_dir: Path) -> None:
        """Generate minimal Keycloak realm configuration for development."""
        from coffeebreak.templates.keycloak import get_realm_config

        realm_config = get_realm_config()

        import json

        with open(keycloak_dir / "exports" / "coffeebreak-realm.json", "w") as f:
            json.dump(realm_config, f, indent=2)

    def _generate_keycloak_theme(self, keycloak_dir: Path) -> None:
        """Generate basic Keycloak theme files."""
        from coffeebreak.templates.keycloak import get_theme_files

        theme_files = get_theme_files()
        theme_dir = keycloak_dir / "themes" / "coffeebreak" / "login"

        # Write each theme file
        for filename, content in theme_files.items():
            file_path = theme_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)

    def check_repositories_exist(self) -> Dict[str, bool]:
        """
        Check which repositories are already cloned.

        Returns:
            Dict[str, bool]: Mapping of repository names to existence status
        """
        repos_status = {}

        try:
            repos_config = self.config_manager.get_repositories_config()

            for repo in repos_config:
                name = repo.get("name")
                path = repo.get("path")

                if name and path:
                    repo_status = self.git_ops.check_repository_status(path)
                    repos_status[name] = repo_status["is_valid"]
                else:
                    repos_status[name] = False

        except Exception:
            pass

        return repos_status

    def update_repositories(self) -> bool:
        """
        Pull latest changes for all repositories.

        Returns:
            bool: True if all updates successful

        Raises:
            DevelopmentEnvironmentError: If updates fail
        """
        try:
            repos_config = self.config_manager.get_repositories_config()
            updated_repos = []
            failed_repos = []

            if self.verbose:
                click.echo("Updating repositories...")

            for repo in repos_config:
                name = repo.get("name")
                path = repo.get("path")

                try:
                    self.git_ops.pull_repository(path)
                    updated_repos.append(name)
                except GitOperationError as e:
                    failed_repos.append(f"{name}: {e}")

            if failed_repos:
                raise DevelopmentEnvironmentError(f"Failed to update repositories: {'; '.join(failed_repos)}")

            if self.verbose:
                click.echo(f"✓ Successfully updated {len(updated_repos)} repositories")

            return True

        except Exception as e:
            raise DevelopmentEnvironmentError(f"Error updating repositories: {e}")

    def _setup_python_environment(self, env_type: str, env_path_or_name: Optional[str], python_path: Optional[str]) -> Dict:
        """
        Setup Python environment (venv or conda).

        Args:
            env_type: Environment type ('venv' or 'conda')
            env_path_or_name: Path for venv or name for conda
            python_path: Path to specific Python executable

        Returns:
            Dict: Environment information

        Raises:
            DevelopmentEnvironmentError: If environment setup fails
        """
        try:
            from .python_env import PythonEnvironmentManager

            env_manager = PythonEnvironmentManager(verbose=self.verbose)
            env_info = env_manager.setup_environment(env_type, env_path_or_name, python_path)

            if self.verbose:
                if env_info["created"]:
                    click.echo(f"✓ Created new {env_type} environment")
                else:
                    click.echo(f"✓ Using existing {env_type} environment")

            return env_info

        except Exception as e:
            raise DevelopmentEnvironmentError(f"Failed to setup Python environment: {e}")

    def _install_repository_dependencies(self, env_info: Dict) -> None:
        """
        Install dependencies for all cloned repositories.

        Args:
            env_info: Environment information from setup
        """
        try:
            from coffeebreak.utils.npm import NPMManager

            from .python_env import PythonEnvironmentManager

            python_env_manager = PythonEnvironmentManager(verbose=self.verbose)
            npm_manager = NPMManager(verbose=self.verbose)

            repos_config = self.config_manager.get_repositories_config()

            for repo in repos_config:
                repo_path = repo.get("path")
                repo_name = repo.get("name")

                if not repo_path or not Path(repo_path).exists():
                    continue

                if self.verbose:
                    click.echo(f"Installing dependencies for {repo_name}...")

                # Install Python dependencies if requirements.txt exists
                requirements_file = Path(repo_path) / "requirements.txt"
                if requirements_file.exists():
                    try:
                        python_env_manager.install_requirements(env_info, str(requirements_file))
                        if self.verbose:
                            click.echo(f"  ✓ Python requirements installed for {repo_name}")
                    except Exception as e:
                        if self.verbose:
                            click.echo(f"  ⚠ Python requirements failed for {repo_name}: {e}")

                # Install npm dependencies if package.json exists
                package_json = Path(repo_path) / "package.json"
                if package_json.exists():
                    try:
                        npm_manager.install_dependencies(repo_path)
                        if self.verbose:
                            click.echo(f"  ✓ npm dependencies installed for {repo_name}")
                    except Exception as e:
                        if self.verbose:
                            click.echo(f"  ⚠ npm dependencies failed for {repo_name}: {e}")

        except Exception as e:
            if self.verbose:
                click.echo(f"Warning: Error installing repository dependencies: {e}")
