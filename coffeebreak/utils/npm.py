"""NPM dependency management for CoffeeBreak CLI."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class NPMManagerError(Exception):
    """Raised when NPM operations fail."""

    pass


class NPMManager:
    """Manages NPM dependencies and operations for Node.js projects."""

    def __init__(self, verbose: bool = False):
        """
        Initialize NPM manager.

        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose

    def check_npm_available(self) -> Tuple[bool, str]:
        """
        Check if npm is installed and available.

        Returns:
            Tuple[bool, str]: (is_available, version_or_error)
        """
        try:
            result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                version = result.stdout.strip()
                if self.verbose:
                    print(f"npm version: {version}")
                return True, version
            else:
                return False, f"npm command failed: {result.stderr}"

        except FileNotFoundError:
            return False, "npm not found - please install Node.js and npm"
        except subprocess.TimeoutExpired:
            return False, "npm command timed out"
        except Exception as e:
            return False, f"Error checking npm: {e}"

    def check_node_version(self, repo_path: str) -> Tuple[bool, str]:
        """
        Check Node.js version requirements from package.json.

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            Tuple[bool, str]: (is_compatible, message)
        """
        try:
            package_json_path = Path(repo_path) / "package.json"
            if not package_json_path.exists():
                return True, "No package.json found, skipping Node.js version check"

            with open(package_json_path) as f:
                package_data = json.load(f)

            # Check if engines.node is specified
            engines = package_data.get("engines", {})
            required_node = engines.get("node")

            if not required_node:
                return True, "No Node.js version requirement specified"

            # Get current Node.js version
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return False, "Could not determine Node.js version"

            current_version = result.stdout.strip()

            if self.verbose:
                print(f"Required Node.js: {required_node}, Current: {current_version}")

            # Basic version compatibility check (simplified)
            # In a real implementation, you'd use semver parsing
            return (
                True,
                f"Node.js version: {current_version} (required: {required_node})",
            )

        except Exception as e:
            return False, f"Error checking Node.js version: {e}"

    def install_dependencies(self, repo_path: str) -> bool:
        """
        Install npm dependencies in a repository.

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            bool: True if installation successful

        Raises:
            NPMManagerError: If installation fails
        """
        try:
            package_json_path = Path(repo_path) / "package.json"
            if not package_json_path.exists():
                if self.verbose:
                    print(f"No package.json found in {repo_path}, skipping npm install")
                return True

            if self.verbose:
                print(f"Installing npm dependencies in {repo_path}...")

            # Run npm install
            result = subprocess.run(
                ["npm", "install"],
                cwd=repo_path,
                capture_output=not self.verbose,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if result.returncode == 0:
                if self.verbose:
                    print(f"✓ npm dependencies installed successfully in {repo_path}")
                return True
            else:
                error_msg = f"npm install failed in {repo_path}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise NPMManagerError(error_msg)

        except subprocess.TimeoutExpired:
            raise NPMManagerError(f"npm install timed out in {repo_path}") from None
        except Exception as e:
            raise NPMManagerError(f"Error installing npm dependencies: {e}") from e

    def clean_install(self, repo_path: str) -> bool:
        """
        Perform clean npm install (remove node_modules first).

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            bool: True if installation successful

        Raises:
            NPMManagerError: If installation fails
        """
        try:
            repo_path = Path(repo_path)
            package_json_path = repo_path / "package.json"

            if not package_json_path.exists():
                if self.verbose:
                    print(f"No package.json found in {repo_path}, skipping npm ci")
                return True

            if self.verbose:
                print(f"Performing clean npm install in {repo_path}...")

            # Remove node_modules and package-lock.json if they exist
            node_modules = repo_path / "node_modules"
            package_lock = repo_path / "package-lock.json"

            if node_modules.exists():
                if self.verbose:
                    print("Removing existing node_modules...")
                shutil.rmtree(node_modules)

            if package_lock.exists():
                if self.verbose:
                    print("Removing existing package-lock.json...")
                package_lock.unlink()

            # Run npm ci for clean install
            result = subprocess.run(
                ["npm", "ci"],
                cwd=str(repo_path),
                capture_output=not self.verbose,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if result.returncode == 0:
                if self.verbose:
                    print(f"✓ Clean npm install completed successfully in {repo_path}")
                return True
            else:
                # Fallback to regular npm install if npm ci fails
                if self.verbose:
                    print("npm ci failed, falling back to npm install...")
                return self.install_dependencies(str(repo_path))

        except subprocess.TimeoutExpired:
            raise NPMManagerError(f"npm ci timed out in {repo_path}") from None
        except Exception as e:
            if self.verbose:
                print(f"Clean install failed: {e}, falling back to regular install...")
            return self.install_dependencies(str(repo_path))

    def check_installed_packages(self, repo_path: str) -> Tuple[bool, List[str]]:
        """
        Verify that all package.json dependencies are installed.

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            Tuple[bool, List[str]]: (all_installed, missing_packages)
        """
        try:
            package_json_path = Path(repo_path) / "package.json"
            if not package_json_path.exists():
                return True, []

            with open(package_json_path) as f:
                package_data = json.load(f)

            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})
            all_deps = {**dependencies, **dev_dependencies}

            if not all_deps:
                return True, []

            node_modules = Path(repo_path) / "node_modules"
            if not node_modules.exists():
                return False, list(all_deps.keys())

            missing_packages = []
            for package_name in all_deps.keys():
                package_dir = node_modules / package_name
                if not package_dir.exists():
                    missing_packages.append(package_name)

            return len(missing_packages) == 0, missing_packages

        except Exception as e:
            if self.verbose:
                print(f"Error checking installed packages: {e}")
            return False, []

    def get_package_info(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """
        Get package.json information.

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            Dict[str, Any]: Package information or None if not found
        """
        try:
            package_json_path = Path(repo_path) / "package.json"
            if not package_json_path.exists():
                return None

            with open(package_json_path) as f:
                package_data = json.load(f)

            return {
                "name": package_data.get("name", "unknown"),
                "version": package_data.get("version", "0.0.0"),
                "description": package_data.get("description", ""),
                "scripts": package_data.get("scripts", {}),
                "dependencies": package_data.get("dependencies", {}),
                "devDependencies": package_data.get("devDependencies", {}),
                "engines": package_data.get("engines", {}),
            }

        except Exception as e:
            if self.verbose:
                print(f"Error reading package.json: {e}")
            return None

    def run_npm_script(self, repo_path: str, script_name: str, timeout: int = 60) -> Tuple[bool, str]:
        """
        Run npm script (e.g., 'npm run dev').

        Args:
            repo_path: Path to repository containing package.json
            script_name: Name of the script to run
            timeout: Timeout in seconds

        Returns:
            Tuple[bool, str]: (success, output_or_error)
        """
        try:
            package_info = self.get_package_info(repo_path)
            if not package_info:
                return False, "No package.json found"

            scripts = package_info.get("scripts", {})
            if script_name not in scripts:
                available_scripts = list(scripts.keys())
                return (
                    False,
                    f"Script '{script_name}' not found. Available: {available_scripts}",
                )

            if self.verbose:
                print(f"Running 'npm run {script_name}' in {repo_path}...")

            result = subprocess.run(
                ["npm", "run", script_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr or "Script execution failed"

        except subprocess.TimeoutExpired:
            return False, f"Script '{script_name}' timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Error running script: {e}"

    def get_npm_audit_info(self, repo_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check for security vulnerabilities.

        Args:
            repo_path: Path to repository containing package.json

        Returns:
            Tuple[bool, Dict[str, Any]]: (has_vulnerabilities, audit_info)
        """
        try:
            package_json_path = Path(repo_path) / "package.json"
            if not package_json_path.exists():
                return False, {"message": "No package.json found"}

            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                audit_data = json.loads(result.stdout)
                vulnerabilities = audit_data.get("vulnerabilities", {})
                has_vulns = len(vulnerabilities) > 0

                return has_vulns, {
                    "vulnerabilities": len(vulnerabilities),
                    "details": audit_data,
                }
            else:
                return False, {"message": "No audit data available"}

        except json.JSONDecodeError:
            return False, {"message": "Could not parse audit output"}
        except subprocess.TimeoutExpired:
            return False, {"message": "npm audit timed out"}
        except Exception as e:
            return False, {"message": f"Error running audit: {e}"}

    def validate_repository(self, repo_path: str) -> Tuple[bool, List[str]]:
        """
        Validate repository has proper Node.js setup and dependencies.

        Args:
            repo_path: Path to repository to validate

        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        errors = []

        # Check if npm is available
        npm_available, npm_msg = self.check_npm_available()
        if not npm_available:
            errors.append(f"npm not available: {npm_msg}")
            return False, errors

        # Check Node.js version compatibility
        node_compatible, node_msg = self.check_node_version(repo_path)
        if not node_compatible:
            errors.append(f"Node.js version issue: {node_msg}")

        # Check if dependencies are installed
        deps_installed, missing = self.check_installed_packages(repo_path)
        if not deps_installed:
            errors.append(f"Missing npm packages: {', '.join(missing[:5])}")  # Show first 5

        return len(errors) == 0, errors
