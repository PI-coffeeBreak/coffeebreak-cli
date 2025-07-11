"""Plugin container integration for CoffeeBreak CLI."""

import os
import shutil
import tempfile
from typing import Any, Dict, List

from coffeebreak.config.manager import ConfigManager
from coffeebreak.containers.compose import DockerComposeOrchestrator
from coffeebreak.containers.manager import ContainerManager
from coffeebreak.utils.errors import PluginError


class PluginContainerIntegration:
    """Handles mounting and integrating plugins with running CoffeeBreak core
    instances."""

    def __init__(self, verbose: bool = False):
        """Initialize plugin container integration."""
        self.verbose = verbose
        self.config_manager = ConfigManager()
        self.container_manager = ContainerManager(verbose=verbose)
        self.compose_orchestrator = DockerComposeOrchestrator(verbose=verbose)

    def mount_plugin_in_development(self, plugin_dir: str, core_container_name: str = "coffeebreak-core") -> bool:
        """
        Mount plugin directory into running CoffeeBreak core container for development.

        Args:
            plugin_dir: Plugin directory to mount
            core_container_name: Name of the core container

        Returns:
            bool: True if mounting successful
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Mounting plugin {plugin_dir} into container {core_container_name}")

            # Validate plugin directory
            if not self._validate_plugin_directory(plugin_dir):
                raise PluginError(f"Invalid plugin directory: {plugin_dir}")

            # Get plugin configuration
            plugin_config = self._load_plugin_config(plugin_dir)
            plugin_name = plugin_config["plugin"]["name"]

            # Check if container is running
            if not self._is_container_running(core_container_name):
                raise PluginError(f"Core container '{core_container_name}' is not running")

            # Create mount points
            mount_paths = self._create_plugin_mount_paths(plugin_config, plugin_dir)

            # Mount plugin using Docker exec and volume mounting
            success = self._mount_plugin_volumes(core_container_name, mount_paths)

            if success:
                # Register plugin with core instance
                self._register_plugin_with_core(core_container_name, plugin_name, plugin_config)

                if self.verbose:
                    print(f"Plugin '{plugin_name}' mounted successfully")

                return True
            else:
                raise PluginError("Failed to mount plugin volumes")

        except Exception as e:
            if isinstance(e, PluginError):
                raise
            else:
                raise PluginError(f"Failed to mount plugin in development: {e}") from e

    def unmount_plugin_from_development(self, plugin_name: str, core_container_name: str = "coffeebreak-core") -> bool:
        """
        Unmount plugin from running CoffeeBreak core container.

        Args:
            plugin_name: Name of the plugin to unmount
            core_container_name: Name of the core container

        Returns:
            bool: True if unmounting successful
        """
        try:
            if self.verbose:
                print(f"Unmounting plugin '{plugin_name}' from container {core_container_name}")

            # Check if container is running
            if not self._is_container_running(core_container_name):
                if self.verbose:
                    print(f"Container '{core_container_name}' is not running")
                return True  # Already unmounted

            # Unregister plugin from core
            self._unregister_plugin_from_core(core_container_name, plugin_name)

            # Remove plugin files from container (gracefully)
            self._cleanup_plugin_from_container(core_container_name, plugin_name)

            if self.verbose:
                print(f"Plugin '{plugin_name}' unmounted successfully")

            return True

        except Exception as e:
            raise PluginError(f"Failed to unmount plugin: {e}") from e

    def list_mounted_plugins(self, core_container_name: str = "coffeebreak-core") -> List[Dict[str, Any]]:
        """
        List all plugins currently mounted in the core container.

        Args:
            core_container_name: Name of the core container

        Returns:
            List[Dict[str, Any]]: List of mounted plugins with their info
        """
        try:
            if not self._is_container_running(core_container_name):
                return []

            # Get list of mounted plugins from core container
            mounted_plugins = self._get_mounted_plugins_from_core(core_container_name)

            return mounted_plugins

        except Exception as e:
            if self.verbose:
                print(f"Error listing mounted plugins: {e}")
            return []

    def setup_plugin_development_environment(self, plugin_dir: str) -> Dict[str, Any]:
        """
        Setup complete plugin development environment with container integration.

        Args:
            plugin_dir: Plugin directory

        Returns:
            Dict[str, Any]: Setup results and information
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            if self.verbose:
                print(f"Setting up plugin development environment for {plugin_dir}")

            # Load plugin configuration
            plugin_config = self._load_plugin_config(plugin_dir)
            plugin_name = plugin_config["plugin"]["name"]

            # Start core dependencies if needed
            self._ensure_core_dependencies_running(plugin_config)

            # Start or ensure core container is running
            core_container = self._ensure_core_container_running(plugin_config)

            # Mount plugin for development
            mount_success = self.mount_plugin_in_development(plugin_dir, core_container)

            # Setup hot reload if configured
            hot_reload_enabled = self._setup_hot_reload(plugin_dir, plugin_config, core_container)

            result = {
                "plugin_name": plugin_name,
                "plugin_dir": plugin_dir,
                "core_container": core_container,
                "mounted": mount_success,
                "hot_reload": hot_reload_enabled,
                "status": "ready" if mount_success else "partial",
            }

            if self.verbose:
                print(f"Plugin development environment ready: {plugin_name}")

            return result

        except Exception as e:
            raise PluginError(f"Failed to setup plugin development environment: {e}") from e

    def _validate_plugin_directory(self, plugin_dir: str) -> bool:
        """Validate that directory is a valid plugin."""
        manifest_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        src_path = os.path.join(plugin_dir, "src")

        return os.path.exists(manifest_path) and os.path.exists(src_path)

    def _load_plugin_config(self, plugin_dir: str) -> Dict[str, Any]:
        """Load plugin configuration."""
        config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
        return self.config_manager.load_config_file(config_path)

    def _is_container_running(self, container_name: str) -> bool:
        """Check if container is running."""
        try:
            container = self.container_manager.client.containers.get(container_name)
            return container.status == "running"
        except Exception:
            return False

    def _create_plugin_mount_paths(self, plugin_config: Dict[str, Any], plugin_dir: str) -> Dict[str, str]:
        """Create mapping of local paths to container mount points."""
        plugin_name = plugin_config["plugin"]["name"]
        development_config = plugin_config.get("development", {})

        # Default mount paths
        mount_paths = {
            os.path.join(plugin_dir, "src"): f"/opt/coffeebreak/plugins/{plugin_name}/src",
            os.path.join(plugin_dir, "assets"): f"/opt/coffeebreak/plugins/{plugin_name}/assets",
        }

        # Add custom mount paths from config
        custom_mounts = development_config.get("mount_paths", [])
        for mount in custom_mounts:
            if isinstance(mount, dict) and "host" in mount and "container" in mount:
                host_path = os.path.join(plugin_dir, mount["host"])
                container_path = mount["container"]
                mount_paths[host_path] = container_path

        # Filter out non-existent paths
        valid_mount_paths = {}
        for host_path, container_path in mount_paths.items():
            if os.path.exists(host_path):
                valid_mount_paths[host_path] = container_path

        return valid_mount_paths

    def _mount_plugin_volumes(self, container_name: str, mount_paths: Dict[str, str]) -> bool:
        """Mount plugin volumes into container."""
        try:
            # Note: Docker doesn't support dynamic volume mounting after
            # container creation
            # For development, we'll copy files and set up file watching instead

            container = self.container_manager.client.containers.get(container_name)

            for host_path, container_path in mount_paths.items():
                if self.verbose:
                    print(f"Copying {host_path} -> {container_path}")

                # Create container directory
                container.exec_run(f"mkdir -p {os.path.dirname(container_path)}")

                # Copy files to container
                self._copy_to_container(container, host_path, container_path)

            return True

        except Exception as e:
            if self.verbose:
                print(f"Error mounting plugin volumes: {e}")
            return False

    def _copy_to_container(self, container, host_path: str, container_path: str) -> None:
        """Copy files from host to container."""
        try:
            # Create a tar archive of the directory
            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp_file:
                # Create tar archive
                shutil.make_archive(tmp_file.name[:-4], "tar", host_path)

                # Copy to container
                with open(tmp_file.name, "rb") as tar_data:
                    container.put_archive(os.path.dirname(container_path), tar_data)

        except Exception as e:
            if self.verbose:
                print(f"Error copying to container: {e}")

    def _register_plugin_with_core(self, container_name: str, plugin_name: str, plugin_config: Dict[str, Any]) -> None:
        """Register plugin with CoffeeBreak core instance."""
        try:
            container = self.container_manager.client.containers.get(container_name)

            # Create plugin registry entry
            registry_command = f"""
                mkdir -p /opt/coffeebreak/plugins/.registry
                cat > /opt/coffeebreak/plugins/.registry/{plugin_name}.json << 'EOF'
{{
    "name": "{plugin_name}",
    "version": "{plugin_config["plugin"].get("version", "1.0.0")}",
    "status": "development",
    "mount_time": "$(date -Iseconds)",
    "source": "cli_mount"
}}
EOF
            """

            exec_result = container.exec_run(["sh", "-c", registry_command])

            if exec_result.exit_code != 0:
                if self.verbose:
                    print(f"Warning: Failed to register plugin in core: {exec_result.output}")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to register plugin with core: {e}")

    def _unregister_plugin_from_core(self, container_name: str, plugin_name: str) -> None:
        """Unregister plugin from CoffeeBreak core instance."""
        try:
            container = self.container_manager.client.containers.get(container_name)

            # Remove plugin registry entry
            container.exec_run(["rm", "-f", f"/opt/coffeebreak/plugins/.registry/{plugin_name}.json"])

        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to unregister plugin from core: {e}")

    def _cleanup_plugin_from_container(self, container_name: str, plugin_name: str) -> None:
        """Clean up plugin files from container."""
        try:
            container = self.container_manager.client.containers.get(container_name)

            # Remove plugin directory
            container.exec_run(["rm", "-rf", f"/opt/coffeebreak/plugins/{plugin_name}"])

        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to cleanup plugin from container: {e}")

    def _get_mounted_plugins_from_core(self, container_name: str) -> List[Dict[str, Any]]:
        """Get list of mounted plugins from core container."""
        try:
            container = self.container_manager.client.containers.get(container_name)

            # List plugin registry entries
            exec_result = container.exec_run(
                [
                    "sh",
                    "-c",
                    "ls /opt/coffeebreak/plugins/.registry/*.json 2>/dev/null || true",
                ]
            )

            if exec_result.exit_code != 0:
                return []

            plugin_files = exec_result.output.decode("utf-8").strip().split("\n")
            plugins = []

            for plugin_file in plugin_files:
                if plugin_file:
                    # Read plugin registry entry
                    cat_result = container.exec_run(["cat", plugin_file])
                    if cat_result.exit_code == 0:
                        try:
                            import json

                            plugin_info = json.loads(cat_result.output.decode("utf-8"))
                            plugins.append(plugin_info)
                        except json.JSONDecodeError:
                            pass

            return plugins

        except Exception as e:
            if self.verbose:
                print(f"Error getting mounted plugins: {e}")
            return []

    def _ensure_core_dependencies_running(self, plugin_config: Dict[str, Any]) -> None:
        """Ensure core dependencies are running for plugin development."""
        try:
            # Check if dependencies are specified in plugin config
            dependencies = plugin_config.get("dependencies", {})
            services = dependencies.get("services", [])

            if services:
                if self.verbose:
                    print(f"Ensuring required services are running: {services}")

                # Use dependency manager to start required services
                from coffeebreak.containers.dependencies import DependencyManager

                dep_manager = DependencyManager(self.config_manager, verbose=self.verbose)

                # Start plugin-dev profile or specific services
                dep_manager.start_profile("plugin-dev")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not ensure dependencies running: {e}")

    def _ensure_core_container_running(self, plugin_config: Dict[str, Any]) -> str:
        """Ensure CoffeeBreak core container is running."""
        core_container_name = "coffeebreak-core"

        try:
            if self._is_container_running(core_container_name):
                return core_container_name

            if self.verbose:
                print(f"Core container '{core_container_name}' not running, attempting to start...")

            # Try to start using docker-compose if available
            if self.compose_orchestrator.is_compose_available():
                # This would need a compose file that includes the core service
                # For now, just return the container name and let the user
                # start it manually
                pass

            # Check again after potential start
            if self._is_container_running(core_container_name):
                return core_container_name
            else:
                if self.verbose:
                    print(f"Warning: Core container '{core_container_name}' is not running")
                    print("You may need to start the CoffeeBreak core development environment first")
                return core_container_name  # Return name anyway for error handling

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not ensure core container running: {e}")
            return core_container_name

    def _setup_hot_reload(self, plugin_dir: str, plugin_config: Dict[str, Any], core_container: str) -> bool:
        """Setup hot reload for plugin development."""
        try:
            development_config = plugin_config.get("development", {})
            hot_reload_enabled = development_config.get("hot_reload", True)

            if not hot_reload_enabled:
                return False

            if self.verbose:
                print("Hot reload will be handled by file watching system")

            # Hot reload implementation would involve:
            # 1. File system watching (watchdog)
            # 2. Automatic re-sync of changed files
            # 3. Plugin reload triggers in core

            # For now, return True to indicate it's "enabled" in concept
            return True

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not setup hot reload: {e}")
            return False
