"""Plugin validation for CoffeeBreak CLI."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from ..config.manager import ConfigManager
from ..config.validator import ConfigValidator


class PluginValidator:
    """Validates plugin structure and configuration."""

    def __init__(self, verbose: bool = False):
        """Initialize plugin validator."""
        self.verbose = verbose
        self.config_manager = ConfigManager()
        self.config_validator = ConfigValidator()

    def validate_plugin(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """
        Validate a plugin directory and configuration.

        Args:
            plugin_dir: Plugin directory path

        Returns:
            Dict containing validation results

        Raises:
            PluginError: If validation fails critically
        """
        plugin_dir = os.path.abspath(plugin_dir)

        if self.verbose:
            print(f"Validating plugin at {plugin_dir}")

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {},
            "checks": {},
        }

        try:
            # Check if directory exists
            if not os.path.exists(plugin_dir):
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Plugin directory does not exist: {plugin_dir}"
                )
                return validation_result

            # Basic structure validation
            self._validate_directory_structure(plugin_dir, validation_result)

            # Configuration validation
            self._validate_plugin_config(plugin_dir, validation_result)

            # Source code validation
            self._validate_source_code(plugin_dir, validation_result)

            # Dependencies validation
            self._validate_dependencies(plugin_dir, validation_result)

            # Build system validation
            self._validate_build_system(plugin_dir, validation_result)

            # Documentation validation
            self._validate_documentation(plugin_dir, validation_result)

            # Security validation
            self._validate_security(plugin_dir, validation_result)

            # Set overall validity
            validation_result["valid"] = len(validation_result["errors"]) == 0

            if self.verbose:
                status = "VALID" if validation_result["valid"] else "INVALID"
                print(f"Plugin validation: {status}")
                if validation_result["errors"]:
                    print(f"Errors: {len(validation_result['errors'])}")
                if validation_result["warnings"]:
                    print(f"Warnings: {len(validation_result['warnings'])}")

            return validation_result

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {e}")
            return validation_result

    def _validate_directory_structure(
        self, plugin_dir: str, result: Dict[str, Any]
    ) -> None:
        """Validate plugin directory structure."""
        required_files = ["coffeebreak-plugin.yml"]
        recommended_dirs = ["src", "scripts", "tests", "docs"]
        recommended_files = ["README.md", "requirements.txt"]

        # Check required files
        for file in required_files:
            file_path = os.path.join(plugin_dir, file)
            if os.path.exists(file_path):
                result["checks"][f"has_{file.replace('.', '_').replace('-', '_')}"] = (
                    True
                )
            else:
                result["errors"].append(f"Missing required file: {file}")
                result["checks"][f"has_{file.replace('.', '_').replace('-', '_')}"] = (
                    False
                )

        # Check recommended directories
        for directory in recommended_dirs:
            dir_path = os.path.join(plugin_dir, directory)
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                result["checks"][f"has_{directory}_dir"] = True
            else:
                result["warnings"].append(f"Missing recommended directory: {directory}")
                result["checks"][f"has_{directory}_dir"] = False

        # Check recommended files
        for file in recommended_files:
            file_path = os.path.join(plugin_dir, file)
            if os.path.exists(file_path):
                result["checks"][f"has_{file.replace('.', '_').replace('-', '_')}"] = (
                    True
                )
            else:
                result["warnings"].append(f"Missing recommended file: {file}")
                result["checks"][f"has_{file.replace('.', '_').replace('-', '_')}"] = (
                    False
                )

    def _validate_plugin_config(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin configuration file."""
        config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")

        if not os.path.exists(config_path):
            return  # Already handled in structure validation

        try:
            # Load and validate config
            config = self.config_manager.load_config_file(config_path)

            # Basic config structure validation
            if "plugin" not in config:
                result["errors"].append("Missing 'plugin' section in configuration")
                return

            plugin_config = config["plugin"]

            # Validate required plugin fields
            required_fields = ["name", "version"]
            for field in required_fields:
                if field not in plugin_config:
                    result["errors"].append(f"Missing required plugin field: {field}")
                else:
                    result["checks"][f"has_plugin_{field}"] = True

            # Validate plugin name format
            if "name" in plugin_config:
                self._validate_plugin_name(plugin_config["name"], result)

            # Validate version format
            if "version" in plugin_config:
                self._validate_version_format(plugin_config["version"], result)

            # Validate optional fields
            self._validate_optional_config_fields(plugin_config, result)

            # Store plugin info
            result["info"]["plugin_name"] = plugin_config.get("name", "unknown")
            result["info"]["plugin_version"] = plugin_config.get("version", "unknown")
            result["info"]["plugin_description"] = plugin_config.get("description", "")

        except Exception as e:
            result["errors"].append(f"Failed to load plugin configuration: {e}")

    def _validate_plugin_name(self, name: str, result: Dict[str, Any]) -> None:
        """Validate plugin name format."""
        if not name:
            result["errors"].append("Plugin name cannot be empty")
            return

        # Check format
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            result["errors"].append(
                "Plugin name must contain only lowercase letters, numbers, and hyphens, "
                "and cannot start or end with hyphens"
            )

        # Check length
        if len(name) > 50:
            result["errors"].append("Plugin name must be 50 characters or less")
        elif len(name) < 3:
            result["warnings"].append("Plugin name should be at least 3 characters")

        result["checks"]["valid_plugin_name"] = (
            len([e for e in result["errors"] if "name" in e]) == 0
        )

    def _validate_version_format(self, version: str, result: Dict[str, Any]) -> None:
        """Validate version format (semantic versioning)."""
        if not version:
            result["errors"].append("Plugin version cannot be empty")
            return

        # Check semantic versioning format
        semver_pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"

        if not re.match(semver_pattern, version):
            result["warnings"].append(
                "Plugin version should follow semantic versioning (e.g., 1.0.0)"
            )

        result["checks"]["valid_version_format"] = True

    def _validate_optional_config_fields(
        self, plugin_config: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """Validate optional configuration fields."""
        # Check for description
        if "description" not in plugin_config:
            result["warnings"].append("Plugin description is recommended")
        elif len(plugin_config["description"]) < 10:
            result["warnings"].append("Plugin description should be more descriptive")

        # Check for author information
        if "author" not in plugin_config:
            result["warnings"].append("Plugin author information is recommended")

        # Validate CoffeeBreak compatibility
        if "coffeebreak" in plugin_config:
            cb_config = plugin_config["coffeebreak"]
            if "min_version" in cb_config:
                # Could validate against known CoffeeBreak versions
                result["checks"]["has_min_version"] = True
            else:
                result["warnings"].append("CoffeeBreak minimum version not specified")

    def _validate_source_code(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin source code."""
        src_dir = os.path.join(plugin_dir, "src")

        if not os.path.exists(src_dir):
            return  # Already handled in structure validation

        # Check for Python files
        python_files = list(Path(src_dir).rglob("*.py"))

        if not python_files:
            result["warnings"].append("No Python source files found in src/ directory")
            result["checks"]["has_python_source"] = False
        else:
            result["checks"]["has_python_source"] = True
            result["info"]["python_files_count"] = len(python_files)

        # Check for __init__.py
        init_file = os.path.join(src_dir, "__init__.py")
        if os.path.exists(init_file):
            result["checks"]["has_init_py"] = True
        else:
            result["warnings"].append("Missing __init__.py in src/ directory")
            result["checks"]["has_init_py"] = False

        # Basic syntax validation
        self._validate_python_syntax(python_files, result)

    def _validate_python_syntax(
        self, python_files: List[Path], result: Dict[str, Any]
    ) -> None:
        """Validate Python syntax in source files."""
        syntax_errors = []

        for py_file in python_files:
            try:
                with open(py_file, encoding="utf-8") as f:
                    source = f.read()

                compile(source, str(py_file), "exec")

            except SyntaxError as e:
                syntax_errors.append(f"{py_file.name}:{e.lineno}: {e.msg}")
            except UnicodeDecodeError:
                syntax_errors.append(f"{py_file.name}: File encoding issues")
            except Exception as e:
                syntax_errors.append(f"{py_file.name}: {e}")

        if syntax_errors:
            result["errors"].extend(
                [f"Python syntax error: {error}" for error in syntax_errors]
            )
            result["checks"]["valid_python_syntax"] = False
        else:
            result["checks"]["valid_python_syntax"] = True

    def _validate_dependencies(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin dependencies."""
        requirements_file = os.path.join(plugin_dir, "requirements.txt")

        if not os.path.exists(requirements_file):
            return  # Not required, but noted in structure validation

        try:
            with open(requirements_file, encoding="utf-8") as f:
                lines = f.readlines()

            dependencies = []
            invalid_lines = []

            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Basic dependency format validation
                if self._is_valid_dependency_line(line):
                    dependencies.append(line)
                else:
                    invalid_lines.append(f"Line {i}: {line}")

            if invalid_lines:
                result["warnings"].extend(
                    [f"Invalid dependency format: {line}" for line in invalid_lines]
                )

            result["info"]["dependencies_count"] = len(dependencies)
            result["checks"]["valid_requirements"] = len(invalid_lines) == 0

            # Check for known problematic dependencies
            self._check_problematic_dependencies(dependencies, result)

        except Exception as e:
            result["warnings"].append(f"Could not validate requirements.txt: {e}")

    def _is_valid_dependency_line(self, line: str) -> bool:
        """Check if dependency line has valid format."""
        # Very basic validation - could be more sophisticated
        return bool(re.match(r"^[a-zA-Z0-9_-]+([>=<]=?[\d.]+)?(\s*#.*)?$", line))

    def _check_problematic_dependencies(
        self, dependencies: List[str], result: Dict[str, Any]
    ) -> None:
        """Check for dependencies that might cause issues in .pyz packaging."""
        problematic = [
            "numpy",
            "scipy",
            "pandas",
            "torch",
            "tensorflow",
            "opencv-python",
            "pillow",
            "lxml",
            "cryptography",
            "psycopg2",
            "pyzmq",
            "greenlet",
        ]

        found_problematic = []
        for dep in dependencies:
            dep_name = dep.split("=")[0].split(">")[0].split("<")[0].strip()
            if dep_name.lower() in problematic:
                found_problematic.append(dep_name)

        if found_problematic:
            result["warnings"].append(
                f"Dependencies with native extensions detected: {', '.join(found_problematic)}. "
                "These will be excluded from .pyz packaging."
            )

    def _validate_build_system(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin build system."""
        scripts_dir = os.path.join(plugin_dir, "scripts")

        if not os.path.exists(scripts_dir):
            return

        # Check for build scripts
        build_scripts = ["build.sh", "package.sh", "test.sh", "validate.sh"]

        for script in build_scripts:
            script_path = os.path.join(scripts_dir, script)
            if os.path.exists(script_path):
                result["checks"][f"has_{script.replace('.', '_')}"] = True

                # Check if script is executable
                if os.access(script_path, os.X_OK):
                    result["checks"][f"{script.replace('.', '_')}_executable"] = True
                else:
                    result["warnings"].append(f"Build script not executable: {script}")
            else:
                result["checks"][f"has_{script.replace('.', '_')}"] = False

    def _validate_documentation(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin documentation."""
        docs_dir = os.path.join(plugin_dir, "docs")
        readme_file = os.path.join(plugin_dir, "README.md")

        # Check README
        if os.path.exists(readme_file):
            try:
                with open(readme_file, encoding="utf-8") as f:
                    readme_content = f.read()

                if len(readme_content.strip()) < 100:
                    result["warnings"].append("README.md should be more comprehensive")

                # Check for basic sections
                sections = ["installation", "usage", "configuration"]
                missing_sections = []
                for section in sections:
                    if section.lower() not in readme_content.lower():
                        missing_sections.append(section)

                if missing_sections:
                    result["warnings"].append(
                        f"README.md missing recommended sections: {', '.join(missing_sections)}"
                    )

                result["checks"]["comprehensive_readme"] = len(missing_sections) == 0

            except Exception:
                result["warnings"].append("Could not read README.md")

        # Check docs directory
        if os.path.exists(docs_dir):
            doc_files = list(Path(docs_dir).rglob("*.md"))
            result["info"]["docs_files_count"] = len(doc_files)
            result["checks"]["has_documentation"] = len(doc_files) > 0
        else:
            result["checks"]["has_documentation"] = False

    def _validate_security(self, plugin_dir: str, result: Dict[str, Any]) -> None:
        """Validate plugin security aspects."""
        security_issues = []

        # Check for common security issues in Python files
        src_dir = os.path.join(plugin_dir, "src")
        if os.path.exists(src_dir):
            python_files = list(Path(src_dir).rglob("*.py"))

            for py_file in python_files:
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()

                    # Check for potential security issues
                    if "eval(" in content:
                        security_issues.append(f"{py_file.name}: Uses eval() function")

                    if "exec(" in content:
                        security_issues.append(f"{py_file.name}: Uses exec() function")

                    if "__import__(" in content:
                        security_issues.append(
                            f"{py_file.name}: Uses __import__() function"
                        )

                    # Check for hardcoded credentials patterns
                    if re.search(
                        r'(password|secret|key)\s*=\s*["\'][^"\']+["\']',
                        content,
                        re.IGNORECASE,
                    ):
                        security_issues.append(
                            f"{py_file.name}: Possible hardcoded credentials"
                        )

                except Exception:
                    pass

        if security_issues:
            result["warnings"].extend(
                [f"Security concern: {issue}" for issue in security_issues]
            )

        result["checks"]["security_scan_passed"] = len(security_issues) == 0

    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """Generate a human-readable validation summary."""
        lines = []

        # Header
        status = "VALID" if validation_result["valid"] else "INVALID"
        lines.append(f"Plugin Validation: {status}")
        lines.append("=" * 40)

        # Plugin info
        if validation_result["info"]:
            info = validation_result["info"]
            lines.append("Plugin Information:")
            if "plugin_name" in info:
                lines.append(f"  Name: {info['plugin_name']}")
            if "plugin_version" in info:
                lines.append(f"  Version: {info['plugin_version']}")
            if "plugin_description" in info:
                lines.append(f"  Description: {info['plugin_description']}")
            lines.append("")

        # Errors
        if validation_result["errors"]:
            lines.append(f"Errors ({len(validation_result['errors'])}):")
            for error in validation_result["errors"]:
                lines.append(f"  ✗ {error}")
            lines.append("")

        # Warnings
        if validation_result["warnings"]:
            lines.append(f"Warnings ({len(validation_result['warnings'])}):")
            for warning in validation_result["warnings"]:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        # Summary
        if validation_result["valid"]:
            lines.append("✓ Plugin validation passed")
        else:
            lines.append("✗ Plugin validation failed")

        return "\n".join(lines)
