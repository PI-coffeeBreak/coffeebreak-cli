"""Python environment management for CoffeeBreak CLI."""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import click


class PythonEnvironmentError(Exception):
    """Raised when Python environment operations fail."""

    pass


class EnvironmentActivator:
    """Handles activation of existing CoffeeBreak environments."""

    def __init__(self, config_path: str = "./coffeebreak.yml"):
        """
        Initialize environment activator.

        Args:
            config_path: Path to coffeebreak.yml configuration file
        """
        self.config_path = config_path
        self.config = None

    def load_config(self) -> Dict[str, Any]:
        """Load CoffeeBreak configuration file."""
        try:
            import yaml

            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
            return self.config
        except FileNotFoundError:
            raise PythonEnvironmentError(
                f"Configuration file not found: {self.config_path}"
            )
        except Exception as e:
            raise PythonEnvironmentError(f"Error loading configuration: {e}")

    def get_environment_info(self) -> Dict[str, Any]:
        """Get environment information from configuration."""
        if not self.config:
            self.load_config()

        try:
            env_config = self.config["coffeebreak"]["environment"]
            return env_config
        except KeyError:
            raise PythonEnvironmentError(
                "No environment configuration found in coffeebreak.yml"
            )

    def get_activation_command(self, shell: Optional[str] = None) -> str:
        """
        Get activation command for the configured environment.

        Args:
            shell: Target shell (bash, zsh, fish, cmd, powershell) or None for auto-detect

        Returns:
            str: Activation command
        """
        env_info = self.get_environment_info()
        env_type = env_info["type"]

        if env_type == "venv":
            return self._get_venv_activation(env_info["path"], shell)
        elif env_type == "conda":
            return self._get_conda_activation(env_info["name"], shell)
        else:
            raise PythonEnvironmentError(f"Unknown environment type: {env_type}")

    def _get_venv_activation(self, venv_path: str, shell: Optional[str]) -> str:
        """Get virtual environment activation command."""
        if not shell:
            shell = self._detect_shell()

        venv_path = Path(venv_path)

        if shell in ["bash", "zsh"]:
            return f"source {venv_path}/bin/activate"
        elif shell == "fish":
            return f"source {venv_path}/bin/activate.fish"
        elif shell == "cmd":
            return f"{venv_path}\\Scripts\\activate.bat"
        elif shell == "powershell":
            return f"{venv_path}\\Scripts\\Activate.ps1"
        else:
            # Default to bash-style
            return f"source {venv_path}/bin/activate"

    def _get_conda_activation(self, env_name: str, shell: Optional[str]) -> str:
        """Get conda environment activation command."""
        return f"conda activate {env_name}"

    def _detect_shell(self) -> str:
        """Detect current shell."""
        shell = os.environ.get("SHELL", "")
        if "bash" in shell:
            return "bash"
        elif "zsh" in shell:
            return "zsh"
        elif "fish" in shell:
            return "fish"
        elif os.name == "nt":
            return "cmd"
        else:
            return "bash"  # Default fallback


class PythonEnvironmentManager:
    """Manages Python virtual environments and conda environments."""

    def __init__(self, verbose: bool = False):
        """
        Initialize Python environment manager.

        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose

    def setup_environment(
        self, env_type: str, env_path_or_name: Optional[str], python_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        Setup Python environment (venv or conda).

        Args:
            env_type: Environment type ('venv' or 'conda')
            env_path_or_name: Path for venv or name for conda (None for defaults)
            python_path: Path to specific Python executable (optional)

        Returns:
            Dict[str, Any]: Environment information
        """
        if env_type == "venv":
            return self.setup_venv(env_path_or_name or ".venv", python_path)
        elif env_type == "conda":
            return self.setup_conda(env_path_or_name, python_path)
        else:
            raise PythonEnvironmentError(f"Unknown environment type: {env_type}")

    def setup_venv(self, venv_path: str, python_path: Optional[str]) -> Dict[str, Any]:
        """
        Create new venv OR reuse existing one.

        Args:
            venv_path: Path where venv should be created/exists
            python_path: Optional path to specific Python executable

        Returns:
            Dict[str, Any]: Environment information
        """
        venv_path = Path(venv_path).resolve()

        if self.venv_exists(venv_path):
            if self.verbose:
                click.echo(f"Reusing existing virtual environment: {venv_path}")
            return self.validate_existing_venv(venv_path, python_path)
        else:
            if self.verbose:
                click.echo(f"Creating new virtual environment: {venv_path}")
            return self.create_new_venv(venv_path, python_path)

    def setup_conda(
        self, env_name: Optional[str], python_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        Create new conda env OR reuse existing one.

        Args:
            env_name: Name of conda environment (None for auto-generate)
            python_path: Optional path to specific Python executable

        Returns:
            Dict[str, Any]: Environment information
        """
        if not env_name:
            env_name = self.generate_conda_name()

        if self.conda_env_exists(env_name):
            if self.verbose:
                click.echo(f"Reusing existing conda environment: {env_name}")
            return self.validate_existing_conda(env_name, python_path)
        else:
            if self.verbose:
                click.echo(f"Creating new conda environment: {env_name}")
            return self.create_new_conda(env_name, python_path)

    def venv_exists(self, path: Path) -> bool:
        """Check if virtual environment already exists at path."""
        return path.exists() and path.is_dir() and (path / "pyvenv.cfg").exists()

    def conda_env_exists(self, name: str) -> bool:
        """Check if conda environment already exists."""
        try:
            result = subprocess.run(
                ["conda", "env", "list"], capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0 and name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def create_new_venv(
        self, venv_path: Path, python_path: Optional[str]
    ) -> Dict[str, Any]:
        """Create a new virtual environment."""
        try:
            # Determine Python executable to use
            python_executable = python_path or sys.executable

            # Validate Python executable
            if not self._validate_python_executable(python_executable):
                raise PythonEnvironmentError(
                    f"Invalid Python executable: {python_executable}"
                )

            # Create parent directories if they don't exist
            venv_path.parent.mkdir(parents=True, exist_ok=True)

            if self.verbose:
                click.echo(
                    f"Creating virtual environment with Python: {python_executable}"
                )

            # Create virtual environment
            result = subprocess.run(
                [python_executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                raise PythonEnvironmentError(
                    f"Failed to create virtual environment: {result.stderr}"
                )

            if self.verbose:
                click.echo(f"✓ Virtual environment created: {venv_path}")

            return {
                "type": "venv",
                "path": str(venv_path),
                "python_path": python_executable,
                "created": True,
            }

        except subprocess.TimeoutExpired:
            raise PythonEnvironmentError("Virtual environment creation timed out")
        except Exception as e:
            raise PythonEnvironmentError(f"Error creating virtual environment: {e}")

    def create_new_conda(
        self, env_name: str, python_path: Optional[str]
    ) -> Dict[str, Any]:
        """Create a new conda environment."""
        try:
            # Check if conda is available
            if not self._check_conda_available():
                raise PythonEnvironmentError("Conda is not available")

            cmd = ["conda", "create", "-n", env_name, "-y"]

            # Add Python version if specified
            if python_path:
                python_version = self._get_python_version(python_path)
                if python_version:
                    cmd.extend(["python=" + python_version])
            else:
                # Default to Python 3.12 if available, otherwise latest
                cmd.append("python>=3.12")

            if self.verbose:
                click.echo(f"Creating conda environment: {env_name}")

            result = subprocess.run(
                cmd,
                capture_output=not self.verbose,
                text=True,
                timeout=300,  # 5 minutes
            )

            if result.returncode != 0:
                raise PythonEnvironmentError(
                    f"Failed to create conda environment: {result.stderr}"
                )

            if self.verbose:
                click.echo(f"✓ Conda environment created: {env_name}")

            return {
                "type": "conda",
                "name": env_name,
                "python_path": python_path,
                "created": True,
            }

        except subprocess.TimeoutExpired:
            raise PythonEnvironmentError("Conda environment creation timed out")
        except Exception as e:
            raise PythonEnvironmentError(f"Error creating conda environment: {e}")

    def validate_existing_venv(
        self, venv_path: Path, python_path: Optional[str]
    ) -> Dict[str, Any]:
        """Validate existing virtual environment is compatible."""
        try:
            # Get Python executable from venv
            if os.name == "nt":
                venv_python = venv_path / "Scripts" / "python.exe"
            else:
                venv_python = venv_path / "bin" / "python"

            if not venv_python.exists():
                raise PythonEnvironmentError(
                    f"Virtual environment appears corrupted: {venv_path}"
                )

            # Check Python version compatibility if requested
            if python_path:
                existing_version = self._get_python_version(str(venv_python))
                requested_version = self._get_python_version(python_path)

                if (
                    existing_version
                    and requested_version
                    and existing_version != requested_version
                ):
                    if self.verbose:
                        click.echo(
                            f"Warning: Existing venv uses Python {existing_version}, "
                            f"but you specified Python {requested_version}"
                        )
                    if not click.confirm("Continue with existing environment?"):
                        raise PythonEnvironmentError("Environment validation failed")

            if self.verbose:
                version = self._get_python_version(str(venv_python))
                click.echo(f"✓ Using existing virtual environment (Python {version})")

            return {
                "type": "venv",
                "path": str(venv_path),
                "python_path": str(venv_python),
                "created": False,
            }

        except Exception as e:
            raise PythonEnvironmentError(f"Error validating virtual environment: {e}")

    def validate_existing_conda(
        self, env_name: str, python_path: Optional[str]
    ) -> Dict[str, Any]:
        """Validate existing conda environment is compatible."""
        try:
            # Get conda environment info
            result = subprocess.run(
                ["conda", "info", "--envs", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise PythonEnvironmentError("Could not get conda environment info")

            import json

            env_info = json.loads(result.stdout)

            # Find the environment
            env_path = None
            for env in env_info.get("envs", []):
                if env.endswith(env_name):
                    env_path = env
                    break

            if not env_path:
                raise PythonEnvironmentError(f"Conda environment not found: {env_name}")

            if self.verbose:
                click.echo(f"✓ Using existing conda environment: {env_name}")

            return {
                "type": "conda",
                "name": env_name,
                "path": env_path,
                "python_path": python_path,
                "created": False,
            }

        except Exception as e:
            raise PythonEnvironmentError(f"Error validating conda environment: {e}")

    def install_requirements(
        self, env_info: Dict[str, Any], requirements_file: str
    ) -> bool:
        """
        Install Python requirements into the environment.

        Args:
            env_info: Environment information from setup_environment
            requirements_file: Path to requirements.txt file

        Returns:
            bool: True if installation successful
        """
        if not Path(requirements_file).exists():
            if self.verbose:
                click.echo(f"Requirements file not found: {requirements_file}")
            return True

        try:
            if env_info["type"] == "venv":
                return self._install_requirements_venv(env_info, requirements_file)
            elif env_info["type"] == "conda":
                return self._install_requirements_conda(env_info, requirements_file)
            else:
                raise PythonEnvironmentError(
                    f"Unknown environment type: {env_info['type']}"
                )

        except Exception as e:
            raise PythonEnvironmentError(f"Error installing requirements: {e}")

    def _install_requirements_venv(
        self, env_info: Dict[str, Any], requirements_file: str
    ) -> bool:
        """Install requirements into virtual environment."""
        venv_path = Path(env_info["path"])

        if os.name == "nt":
            pip_executable = venv_path / "Scripts" / "pip.exe"
        else:
            pip_executable = venv_path / "bin" / "pip"

        if not pip_executable.exists():
            raise PythonEnvironmentError(
                f"pip not found in virtual environment: {venv_path}"
            )

        if self.verbose:
            click.echo(f"Installing requirements from {requirements_file}...")

        result = subprocess.run(
            [str(pip_executable), "install", "-r", requirements_file],
            capture_output=not self.verbose,
            text=True,
            timeout=600,  # 10 minutes
        )

        if result.returncode == 0:
            if self.verbose:
                click.echo("✓ Python requirements installed successfully")
            return True
        else:
            raise PythonEnvironmentError(
                f"Failed to install requirements: {result.stderr}"
            )

    def _install_requirements_conda(
        self, env_info: Dict[str, Any], requirements_file: str
    ) -> bool:
        """Install requirements into conda environment."""
        env_name = env_info["name"]

        if self.verbose:
            click.echo(
                f"Installing requirements from {requirements_file} into conda env {env_name}..."
            )

        # Try conda install first, then fall back to pip
        result = subprocess.run(
            ["conda", "run", "-n", env_name, "pip", "install", "-r", requirements_file],
            capture_output=not self.verbose,
            text=True,
            timeout=600,  # 10 minutes
        )

        if result.returncode == 0:
            if self.verbose:
                click.echo("✓ Python requirements installed successfully")
            return True
        else:
            raise PythonEnvironmentError(
                f"Failed to install requirements: {result.stderr}"
            )

    def generate_conda_name(self) -> str:
        """Generate a unique conda environment name."""
        # Use timestamp and short hash for uniqueness
        timestamp = str(int(time.time()))
        hash_input = f"coffeebreak-{timestamp}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:6]
        return f"coffeebreak-{short_hash}"

    def _validate_python_executable(self, python_path: str) -> bool:
        """Validate that Python executable exists and works."""
        try:
            result = subprocess.run(
                [python_path, "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_python_version(self, python_path: str) -> Optional[str]:
        """Get Python version from executable."""
        try:
            result = subprocess.run(
                [python_path, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Parse "Python 3.12.1" -> "3.12.1"
                version_line = result.stdout.strip()
                if version_line.startswith("Python "):
                    return version_line[7:]  # Remove "Python " prefix
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _check_conda_available(self) -> bool:
        """Check if conda is available."""
        try:
            result = subprocess.run(
                ["conda", "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_environment_python_path(self, env_info: Dict[str, Any]) -> str:
        """Get the Python executable path for an environment."""
        if env_info["type"] == "venv":
            venv_path = Path(env_info["path"])
            if os.name == "nt":
                return str(venv_path / "Scripts" / "python.exe")
            else:
                return str(venv_path / "bin" / "python")
        elif env_info["type"] == "conda":
            # For conda, we'll use 'conda run' to execute python
            return f"conda run -n {env_info['name']} python"
        else:
            raise PythonEnvironmentError(
                f"Unknown environment type: {env_info['type']}"
            )
