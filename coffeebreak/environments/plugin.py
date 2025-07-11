"""Plugin development environment for CoffeeBreak CLI."""

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..config.manager import ConfigManager
from ..plugins.builder import PluginBuilder
from ..plugins.creator import PluginCreator
from ..plugins.dependencies import PluginDependencyManager
from ..plugins.devtools import PluginDeveloperTools
from ..plugins.documentation import PluginDocumentationGenerator
from ..plugins.hotreload import PluginDevelopmentWorkflow, PluginHotReloadManager
from ..plugins.integration import PluginContainerIntegration
from ..plugins.testing import PluginTestFramework
from ..plugins.validator import PluginValidator
from .detector import EnvironmentDetector


class PluginEnvironment:
    """Manages plugin development environment."""

    def __init__(self, config_manager: "ConfigManager", verbose: bool = False):
        """Initialize plugin environment."""
        self.config_manager = config_manager
        self.verbose = verbose
        self.detector = EnvironmentDetector()
        self.creator = PluginCreator(verbose=verbose)
        self.builder = PluginBuilder(verbose=verbose)
        self.validator = PluginValidator(verbose=verbose)
        self.integration = PluginContainerIntegration(verbose=verbose)
        self.hot_reload_manager = PluginHotReloadManager(verbose=verbose)
        self.development_workflow = PluginDevelopmentWorkflow(verbose=verbose)
        self.dependency_manager = PluginDependencyManager(verbose=verbose)
        self.test_framework = PluginTestFramework(verbose=verbose)
        self.documentation_generator = PluginDocumentationGenerator(verbose=verbose)
        self.developer_tools = PluginDeveloperTools(verbose=verbose)

    def create_plugin(
        self,
        name: str,
        template: str = "basic",
        target_dir: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Create a new plugin from template.

        Args:
            name: Plugin name
            template: Template to use
            target_dir: Target directory for plugin
            **kwargs: Additional template variables

        Returns:
            str: Path to created plugin directory
        """
        try:
            plugin_dir = self.creator.create_plugin(name=name, template=template, target_dir=target_dir, **kwargs)

            if self.verbose:
                print(f"Plugin '{name}' created successfully at {plugin_dir}")

            return plugin_dir

        except Exception as e:
            raise OSError(f"Failed to create plugin: {e}")

    def initialize_plugin_dev(self, plugin_dir: str = ".") -> bool:
        """
        Initialize plugin development environment.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            bool: True if initialization successful
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Initializing plugin development environment in {plugin_dir}")

            # Check if already a plugin directory
            if self.detector.is_plugin_environment():
                if self.verbose:
                    print("Directory is already a plugin development environment")
                return True

            # Validate directory is suitable for plugin development
            if not os.path.exists(plugin_dir):
                raise OSError(f"Directory does not exist: {plugin_dir}")

            # Create basic plugin structure if missing
            self._ensure_plugin_structure(plugin_dir)

            # Generate plugin manifest if missing
            manifest_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
            if not os.path.exists(manifest_path):
                self._generate_basic_manifest(plugin_dir)

            if self.verbose:
                print("Plugin development environment initialized")

            return True

        except Exception as e:
            raise OSError(f"Failed to initialize plugin development environment: {e}")

    def build_plugin(
        self,
        plugin_dir: str = ".",
        output_dir: str = "dist",
        exclude_native: bool = True,
    ) -> str:
        """
        Build the plugin into a .pyz package.

        Args:
            plugin_dir: Plugin directory path
            output_dir: Output directory for built package
            exclude_native: Whether to exclude native modules

        Returns:
            str: Path to created .pyz file
        """
        try:
            if self.verbose:
                print("Building plugin...")

            pyz_path = self.builder.build_plugin(
                plugin_dir=plugin_dir,
                output_dir=output_dir,
                exclude_native=exclude_native,
            )

            if self.verbose:
                print(f"Plugin built successfully: {pyz_path}")

            return pyz_path

        except Exception as e:
            raise OSError(f"Failed to build plugin: {e}")

    def validate_plugin(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """
        Validate plugin structure and configuration.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Dict: Validation results
        """
        try:
            if self.verbose:
                print("Validating plugin...")

            validation_result = self.validator.validate_plugin(plugin_dir)

            if self.verbose:
                status = "VALID" if validation_result["valid"] else "INVALID"
                print(f"Plugin validation: {status}")

                if validation_result["errors"]:
                    print(f"Errors: {len(validation_result['errors'])}")
                if validation_result["warnings"]:
                    print(f"Warnings: {len(validation_result['warnings'])}")

            return validation_result

        except Exception as e:
            raise OSError(f"Failed to validate plugin: {e}")

    def get_plugin_info(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """
        Get plugin information.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Dict[str, Any]: Plugin information
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            # Load plugin configuration
            config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
            if not os.path.exists(config_path):
                return {"error": "No plugin configuration found"}

            config = self.config_manager.load_config_file(config_path)
            plugin_config = config.get("plugin", {})

            # Get build information
            build_info = self.builder.get_build_info(plugin_dir)

            # Get validation info
            validation_result = self.validator.validate_plugin(plugin_dir)

            info = {
                "name": plugin_config.get("name", "unknown"),
                "version": plugin_config.get("version", "unknown"),
                "description": plugin_config.get("description", ""),
                "author": plugin_config.get("author", ""),
                "path": plugin_dir,
                "valid": validation_result["valid"],
                "errors_count": len(validation_result["errors"]),
                "warnings_count": len(validation_result["warnings"]),
                "build_info": build_info,
                "last_validation": validation_result,
            }

            return info

        except Exception as e:
            return {"error": str(e)}

    def list_available_templates(self) -> List[str]:
        """
        List available plugin templates.

        Returns:
            List[str]: Available template names
        """
        return self.creator.list_available_templates()

    def get_template_info(self, template: str) -> Dict[str, Any]:
        """
        Get information about a plugin template.

        Args:
            template: Template name

        Returns:
            Dict[str, Any]: Template information
        """
        return self.creator.get_template_info(template)

    def _ensure_plugin_structure(self, plugin_dir: str) -> None:
        """Ensure basic plugin directory structure exists."""
        directories = ["src", "scripts", "tests", "docs", "assets"]

        for directory in directories:
            dir_path = os.path.join(plugin_dir, directory)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                if self.verbose:
                    print(f"Created directory: {directory}")

    def _generate_basic_manifest(self, plugin_dir: str) -> None:
        """Generate a basic plugin manifest."""
        plugin_name = os.path.basename(plugin_dir)

        # Use the creator to generate manifest with minimal info
        self.creator._generate_plugin_manifest(
            name=plugin_name,
            plugin_dir=plugin_dir,
            description=f"CoffeeBreak plugin: {plugin_name}",
            version="1.0.0",
            author="Unknown",
        )

        if self.verbose:
            print("Generated basic plugin manifest")

    # Complete Plugin Development Workflow Integration

    def start_development_workflow(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """
        Start complete plugin development workflow with hot reload and container integration.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Dict[str, Any]: Development session information
        """
        try:
            if self.verbose:
                print("Starting complete plugin development workflow...")

            # First ensure dependencies are installed
            dependency_result = self.install_plugin_dependencies(plugin_dir)

            # Start the complete development workflow
            workflow_result = self.development_workflow.start_plugin_development(plugin_dir)

            # Add dependency information to the result
            workflow_result["dependencies"] = dependency_result

            if self.verbose:
                print("Plugin development workflow started successfully")

            return workflow_result

        except Exception as e:
            raise OSError(f"Failed to start development workflow: {e}")

    def stop_development_workflow(self, plugin_name: str) -> bool:
        """
        Stop plugin development workflow.

        Args:
            plugin_name: Name of the plugin

        Returns:
            bool: True if stopped successfully
        """
        try:
            if self.verbose:
                print(f"Stopping development workflow for '{plugin_name}'...")

            success = self.development_workflow.stop_plugin_development(plugin_name)

            if self.verbose:
                print("Development workflow stopped successfully")

            return success

        except Exception as e:
            if self.verbose:
                print(f"Error stopping development workflow: {e}")
            return False

    def get_development_status(self) -> Dict[str, Any]:
        """
        Get status of active development sessions.

        Returns:
            Dict[str, Any]: Development status information
        """
        try:
            return self.development_workflow.get_development_status()
        except Exception as e:
            return {"error": str(e), "status": "error"}

    # Plugin Dependencies Management

    def analyze_plugin_dependencies(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """
        Analyze plugin dependencies.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Dict[str, Any]: Dependency analysis results
        """
        try:
            return self.dependency_manager.analyze_plugin_dependencies(plugin_dir)
        except Exception as e:
            raise OSError(f"Failed to analyze dependencies: {e}")

    def install_plugin_dependencies(
        self,
        plugin_dir: str = ".",
        install_python: bool = True,
        install_node: bool = True,
        start_services: bool = True,
    ) -> Dict[str, Any]:
        """
        Install plugin dependencies.

        Args:
            plugin_dir: Plugin directory path
            install_python: Whether to install Python dependencies
            install_node: Whether to install Node.js dependencies
            start_services: Whether to start required services

        Returns:
            Dict[str, Any]: Installation results
        """
        try:
            return self.dependency_manager.install_plugin_dependencies(
                plugin_dir=plugin_dir,
                install_python=install_python,
                install_node=install_node,
                start_services=start_services,
            )
        except Exception as e:
            raise OSError(f"Failed to install dependencies: {e}")

    def check_dependency_compatibility(self, plugin_dir: str = ".", target_environment: str = "development") -> Dict[str, Any]:
        """
        Check plugin dependency compatibility.

        Args:
            plugin_dir: Plugin directory path
            target_environment: Target environment (development, production)

        Returns:
            Dict[str, Any]: Compatibility report
        """
        try:
            return self.dependency_manager.check_dependency_compatibility(plugin_dir, target_environment)
        except Exception as e:
            raise OSError(f"Failed to check compatibility: {e}")

    # Plugin Testing Framework

    def run_plugin_tests(
        self,
        plugin_dir: str = ".",
        test_types: Optional[List[str]] = None,
        coverage: bool = False,
        fail_fast: bool = False,
    ) -> Dict[str, Any]:
        """
        Run comprehensive tests for the plugin.

        Args:
            plugin_dir: Plugin directory path
            test_types: Specific test types to run
            coverage: Whether to generate coverage reports
            fail_fast: Whether to stop on first test failure

        Returns:
            Dict[str, Any]: Test results
        """
        try:
            return self.test_framework.run_plugin_tests(
                plugin_dir=plugin_dir,
                test_types=test_types,
                coverage=coverage,
                fail_fast=fail_fast,
            )
        except Exception as e:
            raise OSError(f"Failed to run plugin tests: {e}")

    def generate_test_report(self, test_results: Dict[str, Any], format: str = "text") -> str:
        """
        Generate a formatted test report.

        Args:
            test_results: Test results from run_plugin_tests
            format: Report format (text, json, html)

        Returns:
            str: Formatted test report
        """
        return self.test_framework.generate_test_report(test_results, format)

    # Plugin Documentation Generation

    def generate_plugin_documentation(
        self,
        plugin_dir: str = ".",
        output_dir: str = "docs",
        formats: Optional[List[str]] = None,
        include_api: bool = True,
        include_examples: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive documentation for the plugin.

        Args:
            plugin_dir: Plugin directory path
            output_dir: Output directory for documentation
            formats: Documentation formats to generate
            include_api: Whether to include API documentation
            include_examples: Whether to include usage examples

        Returns:
            Dict[str, Any]: Documentation generation results
        """
        try:
            return self.documentation_generator.generate_plugin_documentation(
                plugin_dir=plugin_dir,
                output_dir=output_dir,
                formats=formats,
                include_api=include_api,
                include_examples=include_examples,
            )
        except Exception as e:
            raise OSError(f"Failed to generate documentation: {e}")

    # Plugin Developer Tools

    def run_quality_assurance(
        self,
        plugin_dir: str = ".",
        tools: Optional[List[str]] = None,
        fix_issues: bool = False,
        generate_report: bool = True,
    ) -> Dict[str, Any]:
        """
        Run comprehensive quality assurance checks.

        Args:
            plugin_dir: Plugin directory path
            tools: Specific tools to run
            fix_issues: Whether to automatically fix issues
            generate_report: Whether to generate a report

        Returns:
            Dict[str, Any]: Quality assurance results
        """
        try:
            return self.developer_tools.run_quality_assurance(
                plugin_dir=plugin_dir,
                tools=tools,
                fix_issues=fix_issues,
                generate_report=generate_report,
            )
        except Exception as e:
            raise OSError(f"Failed to run quality assurance: {e}")

    # Container Integration

    def mount_plugin_in_development(self, plugin_dir: str = ".", core_container_name: str = "coffeebreak-core") -> bool:
        """
        Mount plugin in running CoffeeBreak core container.

        Args:
            plugin_dir: Plugin directory path
            core_container_name: Name of the core container

        Returns:
            bool: True if mounting successful
        """
        try:
            return self.integration.mount_plugin_in_development(plugin_dir, core_container_name)
        except Exception as e:
            raise OSError(f"Failed to mount plugin: {e}")

    def unmount_plugin_from_development(self, plugin_name: str, core_container_name: str = "coffeebreak-core") -> bool:
        """
        Unmount plugin from running CoffeeBreak core container.

        Args:
            plugin_name: Name of the plugin
            core_container_name: Name of the core container

        Returns:
            bool: True if unmounting successful
        """
        try:
            return self.integration.unmount_plugin_from_development(plugin_name, core_container_name)
        except Exception as e:
            raise OSError(f"Failed to unmount plugin: {e}")

    def list_mounted_plugins(self, core_container_name: str = "coffeebreak-core") -> List[Dict[str, Any]]:
        """
        List plugins currently mounted in core container.

        Args:
            core_container_name: Name of the core container

        Returns:
            List[Dict[str, Any]]: List of mounted plugins
        """
        try:
            return self.integration.list_mounted_plugins(core_container_name)
        except Exception as e:
            if self.verbose:
                print(f"Error listing mounted plugins: {e}")
            return []

    # Hot Reload Management

    def start_hot_reload(self, plugin_dir: str = ".", core_container: str = "coffeebreak-core") -> bool:
        """
        Start hot reload for plugin development.

        Args:
            plugin_dir: Plugin directory path
            core_container: Core container name

        Returns:
            bool: True if hot reload started successfully
        """
        try:
            return self.hot_reload_manager.start_hot_reload(plugin_dir, core_container)
        except Exception as e:
            raise OSError(f"Failed to start hot reload: {e}")

    def stop_hot_reload(self, plugin_name: str) -> bool:
        """
        Stop hot reload for a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            bool: True if hot reload stopped successfully
        """
        try:
            return self.hot_reload_manager.stop_hot_reload(plugin_name)
        except Exception as e:
            if self.verbose:
                print(f"Error stopping hot reload: {e}")
            return False

    def get_active_hot_reload_sessions(self) -> List[str]:
        """
        Get list of plugins with active hot reload.

        Returns:
            List[str]: List of plugin names with active hot reload
        """
        try:
            return self.hot_reload_manager.get_active_watchers()
        except Exception as e:
            if self.verbose:
                print(f"Error getting hot reload sessions: {e}")
            return []

    # Comprehensive Plugin Workflow

    def run_complete_plugin_workflow(
        self,
        plugin_dir: str = ".",
        include_tests: bool = True,
        include_docs: bool = True,
        include_qa: bool = True,
        start_dev_environment: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the complete plugin development workflow.

        Args:
            plugin_dir: Plugin directory path
            include_tests: Whether to run tests
            include_docs: Whether to generate documentation
            include_qa: Whether to run quality assurance
            start_dev_environment: Whether to start development environment

        Returns:
            Dict[str, Any]: Complete workflow results
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print("Running complete plugin workflow...")

            results = {
                "plugin_dir": plugin_dir,
                "validation": {},
                "dependencies": {},
                "tests": {},
                "documentation": {},
                "quality_assurance": {},
                "development_environment": {},
                "overall_success": True,
                "errors": [],
                "warnings": [],
            }

            # Step 1: Validate plugin
            try:
                results["validation"] = self.validate_plugin(plugin_dir)
                if not results["validation"]["valid"]:
                    results["overall_success"] = False
                    results["errors"].extend(results["validation"]["errors"])
            except Exception as e:
                results["errors"].append(f"Validation failed: {e}")
                results["overall_success"] = False

            # Step 2: Analyze and install dependencies
            try:
                results["dependencies"] = self.install_plugin_dependencies(plugin_dir)
                if results["dependencies"]["errors"]:
                    results["warnings"].extend(results["dependencies"]["errors"])
            except Exception as e:
                results["errors"].append(f"Dependency installation failed: {e}")

            # Step 3: Run tests if requested
            if include_tests:
                try:
                    results["tests"] = self.run_plugin_tests(plugin_dir, coverage=True)
                    if not results["tests"]["overall_success"]:
                        results["warnings"].append("Some tests failed")
                except Exception as e:
                    results["errors"].append(f"Testing failed: {e}")

            # Step 4: Generate documentation if requested
            if include_docs:
                try:
                    results["documentation"] = self.generate_plugin_documentation(plugin_dir)
                    if results["documentation"]["errors"]:
                        results["warnings"].extend(results["documentation"]["errors"])
                except Exception as e:
                    results["errors"].append(f"Documentation generation failed: {e}")

            # Step 5: Run quality assurance if requested
            if include_qa:
                try:
                    results["quality_assurance"] = self.run_quality_assurance(plugin_dir)
                    if results["quality_assurance"]["overall_score"] < 70:
                        results["warnings"].append("Quality score is below 70")
                except Exception as e:
                    results["errors"].append(f"Quality assurance failed: {e}")

            # Step 6: Start development environment if requested
            if start_dev_environment:
                try:
                    results["development_environment"] = self.start_development_workflow(plugin_dir)
                    if not results["development_environment"].get("hot_reload_active", False):
                        results["warnings"].append("Hot reload could not be activated")
                except Exception as e:
                    results["errors"].append(f"Development environment setup failed: {e}")

            # Final assessment
            if results["errors"]:
                results["overall_success"] = False

            if self.verbose:
                self._print_workflow_summary(results)

            return results

        except Exception as e:
            raise OSError(f"Failed to run complete plugin workflow: {e}")

    def _print_workflow_summary(self, results: Dict[str, Any]) -> None:
        """Print a summary of the complete workflow results."""
        print("\n=== Plugin Workflow Summary ===")
        print(f"Overall Success: {'✓' if results['overall_success'] else '✗'}")
        print(f"Plugin Directory: {results['plugin_dir']}")

        # Validation
        validation = results.get("validation", {})
        if validation:
            status = "✓" if validation.get("valid", False) else "✗"
            print(f"Validation: {status}")

        # Dependencies
        dependencies = results.get("dependencies", {})
        if dependencies:
            python_installed = dependencies.get("python", {}).get("installed", False)
            node_installed = dependencies.get("node", {}).get("installed", False)
            services_started = dependencies.get("services", {}).get("started", False)
            print(f"Dependencies: Python={'✓' if python_installed else '✗'}, Node={'✓' if node_installed else '✗'}, Services={'✓' if services_started else '✗'}")

        # Tests
        tests = results.get("tests", {})
        if tests:
            status = "✓" if tests.get("overall_success", False) else "✗"
            test_count = tests.get("summary", {}).get("total_tests", 0)
            print(f"Tests: {status} ({test_count} tests)")

        # Documentation
        docs = results.get("documentation", {})
        if docs:
            file_count = len(docs.get("generated_files", []))
            status = "✓" if file_count > 0 else "✗"
            print(f"Documentation: {status} ({file_count} files generated)")

        # Quality Assurance
        qa = results.get("quality_assurance", {})
        if qa:
            score = qa.get("overall_score", 0)
            print(f"Quality Score: {score}/100")

        # Development Environment
        dev_env = results.get("development_environment", {})
        if dev_env:
            status = "✓" if dev_env.get("workflow_status") == "active" else "✗"
            print(f"Development Environment: {status}")

        # Errors and Warnings
        if results["errors"]:
            print(f"\nErrors ({len(results['errors'])}):")
            for error in results["errors"][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(results["errors"]) > 5:
                print(f"  ... and {len(results['errors']) - 5} more errors")

        if results["warnings"]:
            print(f"\nWarnings ({len(results['warnings'])}):")
            for warning in results["warnings"][:3]:  # Show first 3 warnings
                print(f"  - {warning}")
            if len(results["warnings"]) > 3:
                print(f"  ... and {len(results['warnings']) - 3} more warnings")
