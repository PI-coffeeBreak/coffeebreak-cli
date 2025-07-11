"""Plugin dependency management for CoffeeBreak CLI."""

import json
import os
import subprocess
from typing import Any, Dict, List

from ..containers.manager import ContainerManager
from ..utils.errors import PluginError


class PluginDependencyManager:
    """Manages plugin dependencies including Python packages, npm modules, and services."""

    def __init__(self, verbose: bool = False):
        """Initialize dependency manager."""
        self.verbose = verbose
        self.container_manager = ContainerManager(verbose=verbose)

    def analyze_plugin_dependencies(self, plugin_dir: str) -> Dict[str, Any]:
        """
        Analyze all dependencies required by a plugin.

        Args:
            plugin_dir: Plugin directory to analyze

        Returns:
            Dict[str, Any]: Complete dependency analysis
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Analyzing dependencies for plugin at {plugin_dir}")

            # Load plugin configuration
            config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
            if not os.path.exists(config_path):
                raise PluginError(f"Plugin configuration not found: {config_path}")

            from ..config.manager import ConfigManager

            config_manager = ConfigManager()
            plugin_config = config_manager.load_config_file(config_path)

            # Analyze different types of dependencies
            analysis = {
                "plugin_name": plugin_config["plugin"]["name"],
                "python": self._analyze_python_dependencies(plugin_dir, plugin_config),
                "node": self._analyze_node_dependencies(plugin_dir, plugin_config),
                "services": self._analyze_service_dependencies(
                    plugin_dir, plugin_config
                ),
                "system": self._analyze_system_dependencies(plugin_dir, plugin_config),
                "conflicts": [],
                "recommendations": [],
            }

            # Check for dependency conflicts
            analysis["conflicts"] = self._check_dependency_conflicts(analysis)

            # Generate recommendations
            analysis["recommendations"] = self._generate_dependency_recommendations(
                analysis
            )

            return analysis

        except Exception as e:
            raise PluginError(f"Failed to analyze plugin dependencies: {e}")

    def install_plugin_dependencies(
        self,
        plugin_dir: str,
        install_python: bool = True,
        install_node: bool = True,
        start_services: bool = True,
    ) -> Dict[str, Any]:
        """
        Install all dependencies for a plugin.

        Args:
            plugin_dir: Plugin directory
            install_python: Whether to install Python dependencies
            install_node: Whether to install Node.js dependencies
            start_services: Whether to start required services

        Returns:
            Dict[str, Any]: Installation results
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Installing dependencies for plugin at {plugin_dir}")

            # Analyze dependencies first
            analysis = self.analyze_plugin_dependencies(plugin_dir)

            results = {
                "plugin_name": analysis["plugin_name"],
                "python": {"installed": False, "details": []},
                "node": {"installed": False, "details": []},
                "services": {"started": False, "details": []},
                "errors": [],
                "warnings": [],
            }

            # Install Python dependencies
            if install_python and analysis["python"]["has_requirements"]:
                try:
                    python_result = self._install_python_dependencies(
                        plugin_dir, analysis["python"]
                    )
                    results["python"] = python_result
                except Exception as e:
                    results["errors"].append(
                        f"Python dependency installation failed: {e}"
                    )

            # Install Node.js dependencies
            if install_node and analysis["node"]["has_package_json"]:
                try:
                    node_result = self._install_node_dependencies(
                        plugin_dir, analysis["node"]
                    )
                    results["node"] = node_result
                except Exception as e:
                    results["errors"].append(
                        f"Node.js dependency installation failed: {e}"
                    )

            # Start required services
            if start_services and analysis["services"]["required"]:
                try:
                    service_result = self._start_required_services(analysis["services"])
                    results["services"] = service_result
                except Exception as e:
                    results["errors"].append(f"Service startup failed: {e}")

            # Handle conflicts
            if analysis["conflicts"]:
                for conflict in analysis["conflicts"]:
                    results["warnings"].append(f"Dependency conflict: {conflict}")

            return results

        except Exception as e:
            raise PluginError(f"Failed to install plugin dependencies: {e}")

    def _analyze_python_dependencies(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze Python dependencies."""
        requirements_path = os.path.join(plugin_dir, "requirements.txt")
        setup_py_path = os.path.join(plugin_dir, "setup.py")
        pyproject_path = os.path.join(plugin_dir, "pyproject.toml")

        python_deps = {
            "has_requirements": False,
            "requirements_file": None,
            "packages": [],
            "dev_packages": [],
            "python_version": None,
            "virtual_env_recommended": True,
        }

        # Check requirements.txt
        if os.path.exists(requirements_path):
            python_deps["has_requirements"] = True
            python_deps["requirements_file"] = requirements_path
            python_deps["packages"] = self._parse_requirements_file(requirements_path)

        # Check setup.py
        elif os.path.exists(setup_py_path):
            python_deps["has_requirements"] = True
            python_deps["requirements_file"] = setup_py_path
            # Would need to parse setup.py to extract dependencies

        # Check pyproject.toml
        elif os.path.exists(pyproject_path):
            python_deps["has_requirements"] = True
            python_deps["requirements_file"] = pyproject_path
            # Would need to parse pyproject.toml to extract dependencies

        # Check plugin config for Python version requirements
        dependencies = plugin_config.get("dependencies", {})
        python_info = dependencies.get("python", {})
        if python_info:
            python_deps["python_version"] = python_info.get("version")
            python_deps["virtual_env_recommended"] = python_info.get(
                "virtual_env", True
            )

        return python_deps

    def _analyze_node_dependencies(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze Node.js dependencies."""
        package_json_path = os.path.join(plugin_dir, "package.json")

        node_deps = {
            "has_package_json": False,
            "package_json_path": None,
            "dependencies": {},
            "dev_dependencies": {},
            "node_version": None,
            "npm_scripts": {},
        }

        if os.path.exists(package_json_path):
            node_deps["has_package_json"] = True
            node_deps["package_json_path"] = package_json_path

            try:
                with open(package_json_path) as f:
                    package_data = json.load(f)

                node_deps["dependencies"] = package_data.get("dependencies", {})
                node_deps["dev_dependencies"] = package_data.get("devDependencies", {})
                node_deps["npm_scripts"] = package_data.get("scripts", {})

                # Check for Node version requirements
                if "engines" in package_data:
                    node_deps["node_version"] = package_data["engines"].get("node")

            except (OSError, json.JSONDecodeError) as e:
                if self.verbose:
                    print(f"Warning: Could not parse package.json: {e}")

        # Check plugin config for Node.js requirements
        dependencies = plugin_config.get("dependencies", {})
        node_info = dependencies.get("node", {})
        if node_info:
            if not node_deps["node_version"]:
                node_deps["node_version"] = node_info.get("version")

        return node_deps

    def _analyze_service_dependencies(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze service dependencies."""
        dependencies = plugin_config.get("dependencies", {})
        services_config = dependencies.get("services", [])

        service_deps = {
            "required": services_config,
            "optional": dependencies.get("optional_services", []),
            "profiles": dependencies.get("profiles", ["plugin-dev"]),
            "custom_compose": None,
        }

        # Check for custom docker-compose file
        compose_paths = [
            os.path.join(plugin_dir, "docker-compose.yml"),
            os.path.join(plugin_dir, "docker-compose.yaml"),
            os.path.join(plugin_dir, "compose.yml"),
            os.path.join(plugin_dir, "compose.yaml"),
        ]

        for compose_path in compose_paths:
            if os.path.exists(compose_path):
                service_deps["custom_compose"] = compose_path
                break

        return service_deps

    def _analyze_system_dependencies(
        self, plugin_dir: str, plugin_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze system-level dependencies."""
        dependencies = plugin_config.get("dependencies", {})
        system_config = dependencies.get("system", {})

        system_deps = {
            "os_requirements": system_config.get("os", []),
            "binary_requirements": system_config.get("binaries", []),
            "library_requirements": system_config.get("libraries", []),
            "environment_variables": system_config.get("env_vars", {}),
            "file_permissions": system_config.get("file_permissions", {}),
        }

        return system_deps

    def _parse_requirements_file(self, requirements_path: str) -> List[Dict[str, str]]:
        """Parse requirements.txt file."""
        packages = []

        try:
            with open(requirements_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Simple parsing - could be enhanced
                        if "==" in line:
                            name, version = line.split("==", 1)
                            packages.append(
                                {"name": name.strip(), "version": version.strip()}
                            )
                        elif ">=" in line:
                            name, version = line.split(">=", 1)
                            packages.append(
                                {
                                    "name": name.strip(),
                                    "version": f">={version.strip()}",
                                }
                            )
                        else:
                            packages.append({"name": line, "version": "*"})

        except OSError as e:
            if self.verbose:
                print(f"Warning: Could not read requirements file: {e}")

        return packages

    def _check_dependency_conflicts(self, analysis: Dict[str, Any]) -> List[str]:
        """Check for potential dependency conflicts."""
        conflicts = []

        # Check for known problematic package combinations
        python_packages = {
            pkg["name"].lower() for pkg in analysis["python"]["packages"]
        }

        # Example conflict checks
        if "tensorflow" in python_packages and "torch" in python_packages:
            conflicts.append("TensorFlow and PyTorch together may cause issues")

        if "django" in python_packages and "flask" in python_packages:
            conflicts.append("Django and Flask together may cause routing conflicts")

        # Check Node.js conflicts
        node_deps = analysis["node"]["dependencies"]
        if "react" in node_deps and "vue" in node_deps:
            conflicts.append("React and Vue.js together may cause build conflicts")

        return conflicts

    def _generate_dependency_recommendations(
        self, analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate dependency recommendations."""
        recommendations = []

        # Python recommendations
        python_packages = {
            pkg["name"].lower() for pkg in analysis["python"]["packages"]
        }
        if "numpy" in python_packages or "pandas" in python_packages:
            recommendations.append(
                "Consider using virtual environment for data science packages"
            )

        if "tensorflow" in python_packages or "torch" in python_packages:
            recommendations.append(
                "ML packages detected - ensure sufficient memory for development"
            )

        # Node.js recommendations
        node_deps = analysis["node"]["dependencies"]
        if len(node_deps) > 50:
            recommendations.append(
                "Large number of Node.js dependencies - consider using yarn for faster installs"
            )

        # Service recommendations
        required_services = analysis["services"]["required"]
        if "postgres" in required_services and "mongodb" in required_services:
            recommendations.append(
                "Multiple databases detected - consider using profiles for selective startup"
            )

        return recommendations

    def _install_python_dependencies(
        self, plugin_dir: str, python_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Install Python dependencies."""
        result = {
            "installed": False,
            "details": [],
            "virtual_env": None,
            "packages_installed": [],
        }

        try:
            # For development, we'll install in the current environment
            # In production, this might create a virtual environment

            requirements_file = python_analysis["requirements_file"]
            if requirements_file and requirements_file.endswith("requirements.txt"):
                if self.verbose:
                    print(f"Installing Python dependencies from {requirements_file}")

                # Use pip to install requirements
                cmd = ["pip", "install", "-r", requirements_file]
                subprocess_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                if subprocess_result.returncode == 0:
                    result["installed"] = True
                    result["details"].append(
                        "Successfully installed Python requirements"
                    )
                    result["packages_installed"] = python_analysis["packages"]
                else:
                    result["details"].append(
                        f"pip install failed: {subprocess_result.stderr}"
                    )
            else:
                result["details"].append(
                    "No requirements.txt found or unsupported requirements format"
                )

        except Exception as e:
            result["details"].append(f"Error installing Python dependencies: {e}")

        return result

    def _install_node_dependencies(
        self, plugin_dir: str, node_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Install Node.js dependencies."""
        result = {
            "installed": False,
            "details": [],
            "package_manager": None,
            "packages_installed": [],
        }

        try:
            if node_analysis["has_package_json"]:
                # Check if yarn.lock exists to determine package manager
                yarn_lock_path = os.path.join(plugin_dir, "yarn.lock")
                if os.path.exists(yarn_lock_path):
                    package_manager = "yarn"
                    cmd = ["yarn", "install"]
                else:
                    package_manager = "npm"
                    cmd = ["npm", "install"]

                result["package_manager"] = package_manager

                if self.verbose:
                    print(f"Installing Node.js dependencies using {package_manager}")

                subprocess_result = subprocess.run(
                    cmd, cwd=plugin_dir, capture_output=True, text=True
                )

                if subprocess_result.returncode == 0:
                    result["installed"] = True
                    result["details"].append(
                        f"Successfully installed Node.js dependencies using {package_manager}"
                    )
                    result["packages_installed"] = list(
                        node_analysis["dependencies"].keys()
                    )
                else:
                    result["details"].append(
                        f"{package_manager} install failed: {subprocess_result.stderr}"
                    )
            else:
                result["details"].append("No package.json found")

        except Exception as e:
            result["details"].append(f"Error installing Node.js dependencies: {e}")

        return result

    def _start_required_services(
        self, service_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start required services."""
        result = {
            "started": False,
            "details": [],
            "services_started": [],
            "services_failed": [],
        }

        try:
            required_services = service_analysis["required"]
            profiles = service_analysis["profiles"]

            if required_services:
                if self.verbose:
                    print(f"Starting required services: {required_services}")

                # Use dependency manager to start services
                from ..config.manager import ConfigManager
                from ..containers.dependencies import DependencyManager

                config_manager = ConfigManager()
                dep_manager = DependencyManager(config_manager, verbose=self.verbose)

                # Start services using the first available profile
                profile = profiles[0] if profiles else "plugin-dev"
                started_services = dep_manager.start_profile(profile)

                if started_services:
                    result["started"] = True
                    result["details"].append(
                        f"Started services using profile: {profile}"
                    )
                    result["services_started"] = started_services
                else:
                    result["details"].append("No services were started")
            else:
                result["started"] = True  # No services required
                result["details"].append("No services required")

        except Exception as e:
            result["details"].append(f"Error starting services: {e}")

        return result

    def check_dependency_compatibility(
        self, plugin_dir: str, target_environment: str = "development"
    ) -> Dict[str, Any]:
        """
        Check if plugin dependencies are compatible with target environment.

        Args:
            plugin_dir: Plugin directory
            target_environment: Target environment (development, production, etc.)

        Returns:
            Dict[str, Any]: Compatibility report
        """
        try:
            analysis = self.analyze_plugin_dependencies(plugin_dir)

            compatibility = {
                "compatible": True,
                "environment": target_environment,
                "issues": [],
                "warnings": [],
                "recommendations": analysis["recommendations"],
            }

            # Check Python compatibility
            python_deps = analysis["python"]
            if python_deps["has_requirements"]:
                # Check for development-only packages in production
                if target_environment == "production":
                    dev_packages = ["pytest", "mock", "unittest", "nose", "tox"]
                    for pkg in python_deps["packages"]:
                        if pkg["name"].lower() in dev_packages:
                            compatibility["warnings"].append(
                                f"Development package '{pkg['name']}' found in requirements"
                            )

            # Check service dependencies
            service_deps = analysis["services"]
            if service_deps["required"] and target_environment == "production":
                compatibility["issues"].append(
                    "Plugin requires additional services - ensure they are available in production"
                )

            # Set overall compatibility
            if compatibility["issues"]:
                compatibility["compatible"] = False

            return compatibility

        except Exception as e:
            return {
                "compatible": False,
                "environment": target_environment,
                "error": str(e),
                "issues": [f"Failed to check compatibility: {e}"],
                "warnings": [],
                "recommendations": [],
            }

    def generate_dependency_report(self, plugin_dir: str) -> str:
        """
        Generate a comprehensive dependency report for a plugin.

        Args:
            plugin_dir: Plugin directory

        Returns:
            str: Formatted dependency report
        """
        try:
            analysis = self.analyze_plugin_dependencies(plugin_dir)

            report_lines = [
                f"# Dependency Report for {analysis['plugin_name']}",
                "",
                "## Python Dependencies",
            ]

            python_deps = analysis["python"]
            if python_deps["has_requirements"]:
                report_lines.extend(
                    [
                        f"- Requirements file: {python_deps['requirements_file']}",
                        f"- Package count: {len(python_deps['packages'])}",
                        f"- Virtual environment recommended: {python_deps['virtual_env_recommended']}",
                    ]
                )

                if python_deps["packages"]:
                    report_lines.append("\n### Package List:")
                    for pkg in python_deps["packages"]:
                        report_lines.append(f"- {pkg['name']} {pkg['version']}")
            else:
                report_lines.append("- No Python dependencies found")

            report_lines.extend(["", "## Node.js Dependencies"])

            node_deps = analysis["node"]
            if node_deps["has_package_json"]:
                dep_count = len(node_deps["dependencies"])
                dev_dep_count = len(node_deps["dev_dependencies"])

                report_lines.extend(
                    [
                        f"- Package.json: {node_deps['package_json_path']}",
                        f"- Dependencies: {dep_count}",
                        f"- Dev dependencies: {dev_dep_count}",
                        f"- Node version requirement: {node_deps['node_version'] or 'Not specified'}",
                    ]
                )

                if node_deps["npm_scripts"]:
                    report_lines.append("\n### Available Scripts:")
                    for script, command in node_deps["npm_scripts"].items():
                        report_lines.append(f"- {script}: {command}")
            else:
                report_lines.append("- No Node.js dependencies found")

            report_lines.extend(["", "## Service Dependencies"])

            service_deps = analysis["services"]
            if service_deps["required"]:
                report_lines.extend(
                    [
                        f"- Required services: {', '.join(service_deps['required'])}",
                        f"- Optional services: {', '.join(service_deps['optional'])}",
                        f"- Recommended profiles: {', '.join(service_deps['profiles'])}",
                    ]
                )

                if service_deps["custom_compose"]:
                    report_lines.append(
                        f"- Custom compose file: {service_deps['custom_compose']}"
                    )
            else:
                report_lines.append("- No service dependencies")

            # Add conflicts and recommendations
            if analysis["conflicts"]:
                report_lines.extend(["", "## Dependency Conflicts", ""])
                for conflict in analysis["conflicts"]:
                    report_lines.append(f"⚠️  {conflict}")

            if analysis["recommendations"]:
                report_lines.extend(["", "## Recommendations", ""])
                for rec in analysis["recommendations"]:
                    report_lines.append(f"💡 {rec}")

            return "\n".join(report_lines)

        except Exception as e:
            return f"Error generating dependency report: {e}"
