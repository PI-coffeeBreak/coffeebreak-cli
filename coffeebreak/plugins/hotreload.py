"""Plugin hot reload system for CoffeeBreak CLI."""

import os
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from coffeebreak.utils.errors import PluginError

from .integration import PluginContainerIntegration


class PluginFileWatcher(FileSystemEventHandler):
    """Watches plugin files for changes and triggers hot reload."""

    def __init__(
        self,
        plugin_dir: str,
        reload_callback: Callable[[str, str], None],
        verbose: bool = False,
    ):
        """
        Initialize plugin file watcher.

        Args:
            plugin_dir: Plugin directory to watch
            reload_callback: Function to call when files change
            verbose: Whether to enable verbose output
        """
        self.plugin_dir = plugin_dir
        self.reload_callback = reload_callback
        self.verbose = verbose
        self.last_reload_time = 0
        self.reload_debounce = 1.0  # Debounce period in seconds

        # Files and patterns to watch
        self.watch_patterns = [
            "*.py",
            "*.js",
            "*.ts",
            "*.jsx",
            "*.tsx",
            "*.css",
            "*.scss",
            "*.html",
            "*.json",
            "*.yml",
            "*.yaml",
        ]

        # Files and directories to ignore
        self.ignore_patterns = [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            ".vscode",
            ".idea",
            "node_modules",
            "dist",
            "build",
            ".DS_Store",
            "Thumbs.db",
        ]

    def on_any_event(self, event):
        """Handle any file system event."""
        if event.is_directory:
            return

        # Check if file should be watched
        if not self._should_watch_file(event.src_path):
            return

        # Debounce rapid file changes
        current_time = time.time()
        if current_time - self.last_reload_time < self.reload_debounce:
            return

        self.last_reload_time = current_time

        # Determine change type
        if isinstance(event, FileCreatedEvent):
            change_type = "created"
        elif isinstance(event, FileModifiedEvent):
            change_type = "modified"
        elif isinstance(event, FileDeletedEvent):
            change_type = "deleted"
        else:
            change_type = "changed"

        if self.verbose:
            rel_path = os.path.relpath(event.src_path, self.plugin_dir)
            print(f"File {change_type}: {rel_path}")

        # Trigger reload
        try:
            self.reload_callback(event.src_path, change_type)
        except Exception as e:
            if self.verbose:
                print(f"Error in reload callback: {e}")

    def _should_watch_file(self, file_path: str) -> bool:
        """Check if file should be watched for changes."""
        rel_path = os.path.relpath(file_path, self.plugin_dir)

        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if pattern in rel_path or rel_path.endswith(pattern.replace("*", "")):
                return False

        # Check watch patterns
        for pattern in self.watch_patterns:
            if rel_path.endswith(pattern.replace("*", "")):
                return True

        return False


class PluginHotReloadManager:
    """Manages hot reload for plugin development."""

    def __init__(self, verbose: bool = False):
        """Initialize hot reload manager."""
        self.verbose = verbose
        self.integration = PluginContainerIntegration(verbose=verbose)
        self.watchers = {}  # plugin_name -> (observer, watcher)
        self.reload_callbacks = {}  # plugin_name -> callback
        self._lock = threading.Lock()

    def start_hot_reload(self, plugin_dir: str, core_container: str = "coffeebreak-core") -> bool:
        """
        Start hot reload for a plugin.

        Args:
            plugin_dir: Plugin directory to watch
            core_container: Core container name

        Returns:
            bool: True if hot reload started successfully
        """
        try:
            plugin_dir = os.path.abspath(plugin_dir)

            # Load plugin configuration
            config_path = os.path.join(plugin_dir, "coffeebreak-plugin.yml")
            if not os.path.exists(config_path):
                raise PluginError(f"Plugin configuration not found: {config_path}")

            from coffeebreak.config.manager import ConfigManager

            config_manager = ConfigManager()
            plugin_config = config_manager.load_config_file(config_path)
            plugin_name = plugin_config["plugin"]["name"]

            if self.verbose:
                print(f"Starting hot reload for plugin '{plugin_name}'")

            # Check if already watching
            with self._lock:
                if plugin_name in self.watchers:
                    if self.verbose:
                        print(f"Hot reload already active for '{plugin_name}'")
                    return True

            # Create reload callback
            def reload_callback(file_path: str, change_type: str):
                self._handle_file_change(plugin_dir, plugin_name, core_container, file_path, change_type)

            # Create file watcher
            watcher = PluginFileWatcher(plugin_dir, reload_callback, self.verbose)

            # Start observer
            observer = Observer()
            observer.schedule(watcher, plugin_dir, recursive=True)
            observer.start()

            # Store watcher info
            with self._lock:
                self.watchers[plugin_name] = (observer, watcher)
                self.reload_callbacks[plugin_name] = reload_callback

            if self.verbose:
                print(f"Hot reload started for plugin '{plugin_name}' at {plugin_dir}")

            return True

        except Exception as e:
            raise PluginError(f"Failed to start hot reload: {e}") from e

    def stop_hot_reload(self, plugin_name: str) -> bool:
        """
        Stop hot reload for a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            bool: True if hot reload stopped successfully
        """
        try:
            with self._lock:
                if plugin_name not in self.watchers:
                    if self.verbose:
                        print(f"No hot reload active for plugin '{plugin_name}'")
                    return True

                observer, watcher = self.watchers[plugin_name]
                del self.watchers[plugin_name]
                del self.reload_callbacks[plugin_name]

            # Stop observer
            observer.stop()
            observer.join(timeout=5)

            if self.verbose:
                print(f"Hot reload stopped for plugin '{plugin_name}'")

            return True

        except Exception as e:
            if self.verbose:
                print(f"Error stopping hot reload: {e}")
            return False

    def stop_all_hot_reload(self) -> None:
        """Stop hot reload for all plugins."""
        with self._lock:
            plugin_names = list(self.watchers.keys())

        for plugin_name in plugin_names:
            self.stop_hot_reload(plugin_name)

    def get_active_watchers(self) -> List[str]:
        """Get list of plugins with active hot reload."""
        with self._lock:
            return list(self.watchers.keys())

    def _handle_file_change(
        self,
        plugin_dir: str,
        plugin_name: str,
        core_container: str,
        file_path: str,
        change_type: str,
    ) -> None:
        """Handle file change event."""
        try:
            if self.verbose:
                rel_path = os.path.relpath(file_path, plugin_dir)
                print(f"Reloading plugin '{plugin_name}' due to {change_type}: {rel_path}")

            # Sync changed file to container
            self._sync_file_to_container(plugin_dir, plugin_name, core_container, file_path, change_type)

            # Trigger plugin reload in core
            self._trigger_plugin_reload(plugin_name, core_container)

        except Exception as e:
            if self.verbose:
                print(f"Error handling file change: {e}")

    def _sync_file_to_container(
        self,
        plugin_dir: str,
        plugin_name: str,
        core_container: str,
        file_path: str,
        change_type: str,
    ) -> None:
        """Sync individual file to container."""
        try:
            from coffeebreak.containers.manager import ContainerManager

            container_manager = ContainerManager(verbose=self.verbose)
            container = container_manager.client.containers.get(core_container)

            # Calculate relative path and container path
            rel_path = os.path.relpath(file_path, plugin_dir)
            container_path = f"/opt/coffeebreak/plugins/{plugin_name}/{rel_path}"

            if change_type == "deleted":
                # Remove file from container
                exec_result = container.exec_run(["rm", "-f", container_path])
                if self.verbose and exec_result.exit_code == 0:
                    print(f"Removed {container_path} from container")
            else:
                # Copy file to container
                if os.path.exists(file_path):
                    self._copy_file_to_container(container, file_path, container_path)
                    if self.verbose:
                        print(f"Synced {rel_path} to container")

        except Exception as e:
            if self.verbose:
                print(f"Error syncing file to container: {e}")

    def _copy_file_to_container(self, container, host_file: str, container_path: str) -> None:
        """Copy a single file to container."""
        try:
            # Create directory in container
            container_dir = os.path.dirname(container_path)
            container.exec_run(["mkdir", "-p", container_dir])

            # Read file content
            with open(host_file, "rb") as f:
                file_content = f.read()

            # Create temporary tar file
            with tempfile.NamedTemporaryFile(suffix=".tar") as tmp_file:
                import tarfile

                with tarfile.open(tmp_file.name, "w") as tar:
                    # Add file to tar
                    tarinfo = tarfile.TarInfo(name=os.path.basename(container_path))
                    tarinfo.size = len(file_content)
                    tar.addfile(tarinfo, fileobj=tempfile.BytesIO(file_content))

                # Copy tar to container
                with open(tmp_file.name, "rb") as tar_data:
                    container.put_archive(container_dir, tar_data)

        except Exception as e:
            if self.verbose:
                print(f"Error copying file to container: {e}")

    def _trigger_plugin_reload(self, plugin_name: str, core_container: str) -> None:
        """Trigger plugin reload in core container."""
        try:
            from coffeebreak.containers.manager import ContainerManager

            container_manager = ContainerManager(verbose=self.verbose)
            container = container_manager.client.containers.get(core_container)

            # Send reload signal to core
            reload_command = f"""
                # Create reload trigger file
                touch /opt/coffeebreak/plugins/.reload/{plugin_name}

                # Try to send signal to core process (if available)
                pkill -USR1 -f "coffeebreak.*core" 2>/dev/null || true
            """

            exec_result = container.exec_run(["sh", "-c", reload_command])

            if self.verbose and exec_result.exit_code == 0:
                print(f"Triggered reload for plugin '{plugin_name}'")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not trigger plugin reload: {e}")


class PluginDevelopmentWorkflow:
    """Complete plugin development workflow with hot reload."""

    def __init__(self, verbose: bool = False):
        """Initialize development workflow."""
        self.verbose = verbose
        self.integration = PluginContainerIntegration(verbose=verbose)
        self.hot_reload = PluginHotReloadManager(verbose=verbose)

    def start_plugin_development(self, plugin_dir: str) -> Dict[str, Any]:
        """
        Start complete plugin development workflow.

        Args:
            plugin_dir: Plugin directory

        Returns:
            Dict[str, Any]: Development session info
        """
        try:
            if self.verbose:
                print(f"Starting plugin development workflow for {plugin_dir}")

            # Setup container integration
            setup_result = self.integration.setup_plugin_development_environment(plugin_dir)

            if not setup_result["mounted"]:
                raise PluginError("Failed to mount plugin in development environment")

            # Start hot reload
            hot_reload_started = self.hot_reload.start_hot_reload(plugin_dir, setup_result["core_container"])

            result = {
                **setup_result,
                "hot_reload_active": hot_reload_started,
                "workflow_status": "active",
            }

            if self.verbose:
                print(f"Plugin development workflow active for '{setup_result['plugin_name']}'")

            return result

        except Exception as e:
            raise PluginError(f"Failed to start plugin development workflow: {e}") from e

    def stop_plugin_development(self, plugin_name: str) -> bool:
        """
        Stop plugin development workflow.

        Args:
            plugin_name: Name of the plugin

        Returns:
            bool: True if stopped successfully
        """
        try:
            if self.verbose:
                print(f"Stopping plugin development workflow for '{plugin_name}'")

            # Stop hot reload
            hot_reload_stopped = self.hot_reload.stop_hot_reload(plugin_name)

            # Unmount plugin
            unmount_success = self.integration.unmount_plugin_from_development(plugin_name)

            if self.verbose:
                print(f"Plugin development workflow stopped for '{plugin_name}'")

            return hot_reload_stopped and unmount_success

        except Exception as e:
            if self.verbose:
                print(f"Error stopping plugin development workflow: {e}")
            return False

    def get_development_status(self) -> Dict[str, Any]:
        """Get status of active development sessions."""
        try:
            active_watchers = self.hot_reload.get_active_watchers()
            mounted_plugins = self.integration.list_mounted_plugins()

            return {
                "active_plugins": len(active_watchers),
                "hot_reload_active": active_watchers,
                "mounted_plugins": mounted_plugins,
                "status": "active" if active_watchers else "inactive",
            }

        except Exception as e:
            return {"error": str(e), "status": "error"}
