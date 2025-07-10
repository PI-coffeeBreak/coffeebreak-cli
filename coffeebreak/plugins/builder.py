"""Plugin build system for CoffeeBreak CLI."""

import os
import shutil
import subprocess
import zipapp
import glob
import importlib.util
import sys
import tempfile
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from ..utils.files import FileManager
from ..utils.errors import PluginError, CoffeeBreakError
from ..config.manager import ConfigManager


class PluginBuilder:
    """Builds plugins into distributable .pyz packages."""

    def __init__(self, verbose: bool = False):
        """Initialize plugin builder."""
        self.verbose = verbose
        self.file_manager = FileManager(verbose=verbose)
        self.config_manager = ConfigManager()

        # Known native modules that should be excluded from .pyz
        self.known_native_modules = {
            "regex",
            "_regex",
            "regex._regex",
            "numpy",
            "scipy",
            "pandas",
            "torch",
            "tensorflow",
            "pydantic_core",
            "_pydantic_core",
            "transformers",
            "tokenizers",
            "safetensors",
            "huggingface_hub",
            "cv2",
            "PIL",
            "Pillow",
            "lxml",
            "psycopg2",
            "cryptography",
            "pyzmq",
            "zmq",
            "greenlet",
            "gevent",
        }

    def build_plugin(
        self,
        plugin_dir: str = ".",
        output_dir: str = "dist",
        exclude_native: bool = True,
        additional_excludes: Optional[List[str]] = None,
    ) -> str:
        """
        Build plugin into .pyz package.

        Args:
            plugin_dir: Plugin source directory
            output_dir: Output directory for built package
            exclude_native: Whether to exclude native modules
            additional_excludes: Additional modules to exclude

        Returns:
            str: Path to created .pyz file

        Raises:
            PluginError: If build fails
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Building plugin from {plugin_dir}")

            # Load plugin configuration
            config = self._load_plugin_config(plugin_dir)
            plugin_name = config["plugin"]["name"]

            if self.verbose:
                print(f"Plugin name: {plugin_name}")

            # Create build directory
            build_dir = os.path.join(plugin_dir, ".build")
            self._cleanup_build_dir(build_dir)
            os.makedirs(build_dir, exist_ok=True)

            # Create output directory
            output_dir = os.path.abspath(output_dir)
            os.makedirs(output_dir, exist_ok=True)

            # Run pre-build hooks
            self._run_build_hooks(plugin_dir, config, "pre_build")

            # Copy plugin source
            self._copy_plugin_source(plugin_dir, build_dir, config)

            # Install dependencies
            self._install_dependencies(plugin_dir, build_dir)

            # Handle native module exclusion
            if exclude_native:
                excluded_modules = self._exclude_native_modules(
                    build_dir, additional_excludes or []
                )
                if self.verbose and excluded_modules:
                    print(f"Excluded {len(excluded_modules)} native modules")

            # Run build hooks
            self._run_build_hooks(plugin_dir, config, "build")

            # Create .pyz package
            pyz_path = self._create_pyz_package(
                plugin_name, build_dir, output_dir, config
            )

            # Run post-build hooks
            self._run_build_hooks(plugin_dir, config, "post_build")

            # Cleanup
            self._cleanup_build_dir(build_dir)

            if self.verbose:
                print(f"Plugin built successfully: {pyz_path}")

            return pyz_path

        except Exception as e:
            # Cleanup on error
            build_dir = os.path.join(plugin_dir, ".build")
            self._cleanup_build_dir(build_dir)

            if isinstance(e, CoffeeBreakError):
                raise
            else:
                raise PluginError(f"Failed to build plugin: {e}")

    def _load_plugin_config(self, plugin_dir: str) -> Dict[str, Any]:
        """Load plugin configuration."""
        config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")

        if not os.path.exists(config_path):
            raise PluginError(f"Plugin configuration not found: {config_path}")

        try:
            return self.config_manager.load_config_file(config_path)
        except Exception as e:
            raise PluginError(f"Failed to load plugin configuration: {e}")

    def _cleanup_build_dir(self, build_dir: str) -> None:
        """Clean up build directory."""
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir, ignore_errors=True)

    def _copy_plugin_source(
        self, plugin_dir: str, build_dir: str, config: Dict[str, Any]
    ) -> None:
        """Copy plugin source files to build directory."""
        plugin_name = config["plugin"]["name"]
        package_name = plugin_name.replace("-", "_")

        # Copy main source directory
        src_dir = os.path.join(plugin_dir, "src")
        if os.path.exists(src_dir):
            build_src_dir = os.path.join(build_dir, package_name)
            shutil.copytree(src_dir, build_src_dir)

            if self.verbose:
                print(f"Copied source: src -> {package_name}")

        # Copy additional files specified in config
        build_config = config.get("build", {})
        include_files = build_config.get("include_files", [])
        exclude_patterns = build_config.get("exclude_patterns", [])

        for file_pattern in include_files:
            self._copy_matching_files(
                plugin_dir, build_dir, file_pattern, exclude_patterns
            )

        # Create __main__.py entry point
        main_file = os.path.join(build_dir, "__main__.py")
        main_content = f"# {plugin_name} plugin entry point\n"

        with open(main_file, "w", encoding="utf-8") as f:
            f.write(main_content)

        if self.verbose:
            print("Created __main__.py entry point")

    def _copy_matching_files(
        self, source_dir: str, build_dir: str, pattern: str, exclude_patterns: List[str]
    ) -> None:
        """Copy files matching pattern, excluding specified patterns."""
        source_files = glob.glob(os.path.join(source_dir, pattern))

        for source_file in source_files:
            # Check if file should be excluded
            rel_path = os.path.relpath(source_file, source_dir)

            excluded = False
            for exclude_pattern in exclude_patterns:
                if glob.fnmatch.fnmatch(rel_path, exclude_pattern):
                    excluded = True
                    break

            if not excluded:
                target_file = os.path.join(build_dir, rel_path)
                target_dir = os.path.dirname(target_file)

                os.makedirs(target_dir, exist_ok=True)

                if os.path.isfile(source_file):
                    shutil.copy2(source_file, target_file)
                elif os.path.isdir(source_file):
                    if not os.path.exists(target_file):
                        shutil.copytree(source_file, target_file)

                if self.verbose:
                    print(f"Included: {rel_path}")

    def _install_dependencies(self, plugin_dir: str, build_dir: str) -> None:
        """Install plugin dependencies."""
        requirements_file = os.path.join(plugin_dir, "requirements.txt")

        if not os.path.exists(requirements_file):
            if self.verbose:
                print("No requirements.txt found, skipping dependency installation")
            return

        if self.verbose:
            print("Installing dependencies...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    requirements_file,
                    "-t",
                    build_dir,
                    "--no-deps",  # Don't install sub-dependencies to avoid conflicts
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            if self.verbose and result.stdout:
                print("Dependencies installed successfully")

        except subprocess.CalledProcessError as e:
            raise PluginError(f"Failed to install dependencies: {e.stderr}")

    def _exclude_native_modules(
        self, build_dir: str, additional_excludes: List[str]
    ) -> Set[str]:
        """Detect and exclude native modules from build."""
        excluded_modules = set()

        # Combine known native modules with user-specified excludes
        modules_to_check = self.known_native_modules.union(set(additional_excludes))

        for item in os.listdir(build_dir):
            item_path = os.path.join(build_dir, item)

            if os.path.isdir(item_path):
                # Check if directory contains native extensions
                if self._has_native_extensions(item_path):
                    excluded_modules.add(item)
                    self._remove_module(item_path, item)

                # Check if it's a known problematic module
                elif item in modules_to_check:
                    excluded_modules.add(item)
                    self._remove_module(item_path, item)

                # Test import safety
                elif not self._can_import_safely(item, build_dir):
                    excluded_modules.add(item)
                    self._remove_module(item_path, item)

            elif item.endswith((".so", ".pyd", ".dll", ".dylib")):
                # Native extension file
                module_name = item.split(".")[0]
                excluded_modules.add(module_name)
                os.remove(item_path)
                if self.verbose:
                    print(f"Removed native extension: {item}")

        return excluded_modules

    def _has_native_extensions(self, module_path: str) -> bool:
        """Check if module contains native extensions."""
        for root, dirs, files in os.walk(module_path):
            for file in files:
                # Native extension files
                if file.endswith((".so", ".pyd", ".dll", ".dylib")):
                    return True
                # C source files
                if file.endswith((".c", ".cpp", ".cxx", ".cc", ".h", ".hpp")):
                    return True

        # Check wheel metadata
        dist_info_dirs = glob.glob(os.path.join(module_path, "*.dist-info"))
        for dist_info in dist_info_dirs:
            wheel_file = os.path.join(dist_info, "WHEEL")
            if os.path.exists(wheel_file):
                try:
                    with open(wheel_file, "r") as f:
                        content = f.read()
                        # Non-universal wheels likely have native code
                        if "Tag: py2.py3-none-any" not in content:
                            return True
                except Exception:
                    pass

        return False

    def _can_import_safely(self, module_name: str, build_dir: str) -> bool:
        """Test if module can be imported safely."""
        try:
            old_path = sys.path[:]
            sys.path.insert(0, build_dir)

            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return True

            # Check for native submodules
            if spec.submodule_search_locations:
                for location in spec.submodule_search_locations:
                    if self._has_native_extensions(location):
                        return False

            return True

        except Exception:
            return False
        finally:
            sys.path[:] = old_path

    def _remove_module(self, module_path: str, module_name: str) -> None:
        """Remove a module directory or file."""
        try:
            if os.path.isdir(module_path):
                shutil.rmtree(module_path)
            else:
                os.remove(module_path)

            if self.verbose:
                print(f"Excluded native module: {module_name}")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not remove module {module_name}: {e}")

    def _create_pyz_package(
        self, plugin_name: str, build_dir: str, output_dir: str, config: Dict[str, Any]
    ) -> str:
        """Create .pyz package from build directory."""
        pyz_filename = f"{plugin_name}.pyz"
        pyz_path = os.path.join(output_dir, pyz_filename)

        try:
            if self.verbose:
                print(f"Creating .pyz package: {pyz_filename}")

            zipapp.create_archive(
                source=build_dir,
                target=pyz_path,
                main=None,  # Plugin will be loaded by CoffeeBreak, not executed directly
            )

            return pyz_path

        except Exception as e:
            raise PluginError(f"Failed to create .pyz package: {e}")

    def _run_build_hooks(
        self, plugin_dir: str, config: Dict[str, Any], hook_type: str
    ) -> None:
        """Run build hooks if configured."""
        build_config = config.get("build", {})
        hooks = build_config.get("hooks", {})
        hook_command = hooks.get(hook_type)

        if not hook_command:
            return

        if self.verbose:
            print(f"Running {hook_type} hook: {hook_command}")

        try:
            result = subprocess.run(
                hook_command,
                shell=True,
                cwd=plugin_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise PluginError(
                    f"{hook_type} hook failed with exit code {result.returncode}: "
                    f"{result.stderr}"
                )

            if self.verbose and result.stdout:
                print(f"{hook_type} hook output: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise PluginError(f"{hook_type} hook timed out")
        except Exception as e:
            raise PluginError(f"Failed to run {hook_type} hook: {e}")

    def get_build_info(self, plugin_dir: str = ".") -> Dict[str, Any]:
        """Get build information for a plugin."""
        try:
            config = self._load_plugin_config(plugin_dir)
            plugin_name = config["plugin"]["name"]

            info = {
                "plugin_name": plugin_name,
                "plugin_dir": os.path.abspath(plugin_dir),
                "has_requirements": os.path.exists(
                    os.path.join(plugin_dir, "requirements.txt")
                ),
                "has_src": os.path.exists(os.path.join(plugin_dir, "src")),
                "build_config": config.get("build", {}),
                "estimated_size": self._estimate_build_size(plugin_dir),
            }

            return info

        except Exception as e:
            raise PluginError(f"Failed to get build info: {e}")

    def _estimate_build_size(self, plugin_dir: str) -> str:
        """Estimate the size of the plugin build."""
        try:
            total_size = 0

            # Calculate source size
            src_dir = os.path.join(plugin_dir, "src")
            if os.path.exists(src_dir):
                total_size += self._get_directory_size(src_dir)

            # Estimate dependency size if requirements.txt exists
            requirements_file = os.path.join(plugin_dir, "requirements.txt")
            if os.path.exists(requirements_file):
                # Rough estimate: 1MB per dependency line
                with open(requirements_file, "r") as f:
                    lines = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.startswith("#")
                    ]
                    total_size += len(lines) * 1024 * 1024

            # Format size
            if total_size < 1024:
                return f"{total_size} B"
            elif total_size < 1024 * 1024:
                return f"{total_size / 1024:.1f} KB"
            else:
                return f"{total_size / (1024 * 1024):.1f} MB"

        except Exception:
            return "Unknown"

    def _get_directory_size(self, directory: str) -> int:
        """Calculate total size of directory."""
        total_size = 0
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, IOError):
                    pass
        return total_size
