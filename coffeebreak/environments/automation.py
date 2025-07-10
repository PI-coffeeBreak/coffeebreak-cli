"""Development environment automation for CoffeeBreak CLI."""

import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..config.manager import ConfigManager
from ..containers.dependencies import DependencyManager
from ..git.operations import GitOperations
from ..utils.errors import CoffeeBreakError, EnvironmentError
from ..utils.files import FileManager
from .detector import EnvironmentType


class DevEnvironmentAutomation:
    """Automates development environment setup and management."""

    def __init__(self, verbose: bool = False):
        """Initialize development environment automation."""
        self.verbose = verbose
        self.config_manager = ConfigManager()
        self.dependency_manager = DependencyManager(
            self.config_manager, verbose=verbose
        )
        self.git_operations = GitOperations(verbose=verbose)
        self.file_manager = FileManager(verbose=verbose)
        self.processes = {}  # Track running processes
        self.log_dir = self._get_log_directory()

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            import psutil

            return psutil.pid_exists(pid)
        except ImportError:
            # Fallback without psutil
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def _is_in_coffeebreak_group(self) -> bool:
        """Check if current user is in the coffeebreak group."""
        try:
            import grp

            groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
            return "coffeebreak" in groups
        except:
            return False

    def _get_log_directory(self) -> Path:
        """Get appropriate log directory with fallback."""

        # Try system directory if user is in coffeebreak group
        if self._is_in_coffeebreak_group():
            return Path("/var/log/coffeebreak")

        # Fallback to user directory following XDG specification
        return Path.home() / ".local/state/coffeebreak/logs"

    def _get_running_processes(self) -> Dict[str, Dict[str, Any]]:
        """Get currently running development processes."""
        running = {}
        pids_file = Path(".coffeebreak/pids.json")

        if not pids_file.exists():
            return running

        try:
            import json

            with open(pids_file, "r") as f:
                saved_pids = json.load(f)

            for service, info in saved_pids.items():
                pid = info.get("pid")
                if pid and self._is_process_running(pid):
                    running[service] = info

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not check processes: {e}")

        return running

    def _save_process_info(
        self, service: str, pid: int, command: List[str], cwd: str, log_file: str = None
    ):
        """Save process information."""
        try:
            import json
            from datetime import datetime

            pids_file = Path(".coffeebreak/pids.json")
            pids_file.parent.mkdir(exist_ok=True)

            # Load existing PIDs
            if pids_file.exists():
                with open(pids_file, "r") as f:
                    pids = json.load(f)
            else:
                pids = {}

            # Add/update this service
            pids[service] = {
                "pid": pid,
                "command": command,
                "cwd": cwd,
                "started_at": datetime.now().isoformat(),
            }

            # Add log file path if provided
            if log_file:
                pids[service]["log_file"] = log_file

            # Save updated PIDs
            with open(pids_file, "w") as f:
                json.dump(pids, f, indent=2)

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not save process info: {e}")

    def _tee_process_output(self, process, log_file: Path, name: str):
        """Tee process output to both console (for live logs) and log file."""
        try:
            with open(log_file, "w") as log:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break

                    # Write to log file immediately
                    log.write(line)
                    log.flush()

                    # Also store in a buffer for live logs to pick up
                    # The live logs will read from stdout as before

        except Exception as e:
            if self.verbose:
                print(f"Error in log tee for {name}: {e}")

    def _cleanup_dead_processes(self):
        """Remove dead processes from PID file."""
        try:
            import json

            pids_file = Path(".coffeebreak/pids.json")

            if not pids_file.exists():
                return

            with open(pids_file, "r") as f:
                pids = json.load(f)

            # Filter out dead processes
            alive_pids = {}
            for service, info in pids.items():
                if self._is_process_running(info.get("pid", 0)):
                    alive_pids[service] = info

            # Save cleaned up PIDs
            with open(pids_file, "w") as f:
                json.dump(alive_pids, f, indent=2)

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not cleanup processes: {e}")

    def start_development_environment(
        self,
        profile: Optional[str] = None,
        services: Optional[List[str]] = None,
        skip_clone: bool = False,
        skip_deps: bool = False,
        detach: bool = False,
    ) -> bool:
        """
        Start complete development environment.

        Args:
            profile: Dependency profile to use (full, minimal, etc.)
            services: Specific services to start
            skip_clone: Skip repository cloning
            skip_deps: Skip dependency startup

        Returns:
            bool: True if environment started successfully
        """
        try:
            env_type = self.config_manager.detect_environment()

            if env_type == EnvironmentType.UNINITIALIZED:
                raise EnvironmentError(
                    "No CoffeeBreak configuration found. Run 'coffeebreak init dev' first.",
                    suggestions=[
                        "Run 'coffeebreak init dev' to initialize a development environment",
                        "Ensure you're in the correct directory",
                    ],
                )

            if self.verbose:
                print(f"Detected environment type: {env_type.value}")

            # Load configuration
            config = self.config_manager.load_config()

            if env_type == EnvironmentType.FULL_DEV:
                return self._start_full_dev_environment(
                    config, profile, services, skip_clone, skip_deps, detach
                )
            elif env_type == EnvironmentType.PLUGIN_DEV:
                return self._start_plugin_dev_environment(
                    config, profile, services, skip_deps
                )
            else:
                raise EnvironmentError(f"Unsupported environment type: {env_type}")

        except Exception as e:
            if isinstance(e, CoffeeBreakError):
                raise
            else:
                raise EnvironmentError(f"Failed to start development environment: {e}")

    def _start_full_dev_environment(
        self,
        config: Dict[str, Any],
        profile: Optional[str],
        services: Optional[List[str]],
        skip_clone: bool,
        skip_deps: bool,
        detach: bool = False,
    ) -> bool:
        """Start full development environment."""
        print("Starting CoffeeBreak full development environment...")

        success_steps = []

        try:
            # Step 1: Clone repositories if needed
            if not skip_clone:
                if self._setup_repositories(config):
                    success_steps.append("repositories")
                else:
                    print("Repository setup had issues, continuing...")

            # Step 2: Start dependencies
            if not skip_deps:
                print("\nStarting dependency services...")
                if self._start_dependencies(config, profile, services):
                    success_steps.append("dependencies")
                    print("Dependencies started")

                    # Step 2a: Start health monitoring
                    print("\nStarting health monitoring...")
                    if self.dependency_manager.start_health_monitoring():
                        success_steps.append("monitoring")
                        print("Health monitoring active")
                    else:
                        print("Health monitoring could not be started")
                else:
                    print("Failed to start dependencies")
                    return False

            # Step 3: Generate environment files
            print("\nGenerating environment files...")
            if self._generate_environment_files(config):
                success_steps.append("environment")
                print("Environment files generated")

            # Step 4: Start development servers
            print("\nStarting development servers...")
            if self._start_development_servers(config, detach):
                success_steps.append("servers")
                print("Development servers started")

            # Step 5: Show status
            self._show_environment_status()

            # Step 6: Show health status
            print("\nHealth Status:")
            health_report = self.dependency_manager.get_health_report()
            print(health_report)

            # Show different messages based on mode
            if detach:
                print("\nDevelopment environment ready!")
                print("\nNext steps:")
                print("  - Visit http://localhost:3000 for the admin frontend")
                print("  - Visit http://localhost:8080 for Keycloak admin")
                print("  - Check logs with 'coffeebreak deps logs'")
                print("  - View health status with 'coffeebreak status'")
                print("  - Stop environment with 'coffeebreak stop'")
                print(f"\nRunning in background. Logs available in: {self.log_dir}")
                print("Use 'coffeebreak stop' to stop all services")
            else:
                print("\nDevelopment environment ready!")
                print("\nNext steps:")
                print("  - Visit http://localhost:3000 for the admin frontend")
                print("  - Visit http://localhost:8080 for Keycloak admin")
                print("  - View health status with 'coffeebreak status'")
                print("  - Stop environment with Ctrl+C")

            return True

        except Exception as e:
            print(f"\n Error during setup: {e}")
            self._cleanup_failed_setup(success_steps)
            return False

    def _start_plugin_dev_environment(
        self,
        config: Dict[str, Any],
        profile: Optional[str],
        services: Optional[List[str]],
        skip_deps: bool,
    ) -> bool:
        """Start plugin development environment."""
        print("Starting CoffeeBreak plugin development environment...")

        try:
            # Step 1: Validate plugin configuration
            plugin_config = config.get("plugin", {})
            if not plugin_config.get("name"):
                raise EnvironmentError("Plugin name not found in configuration")

            plugin_name = plugin_config["name"]
            print(f"Plugin: {plugin_name}")

            # Step 2: Start core dependencies
            if not skip_deps:
                print("\n   Starting core dependencies...")
                # Use plugin-dev profile by default
                dep_profile = profile or "plugin-dev"
                if self._start_dependencies(config, dep_profile, services):
                    print(" Core dependencies started")

                    # Start health monitoring for plugin dev too
                    print("\n   Starting health monitoring...")
                    if self.dependency_manager.start_health_monitoring():
                        print(" Health monitoring active")
                else:
                    print(" Failed to start dependencies")
                    return False

            # Step 3: Generate environment files
            print("\n Generating environment files...")
            if self._generate_environment_files(config):
                print(" Environment files generated")

            # Step 4: Start plugin development server
            print("\n   Starting plugin development...")
            if self._start_plugin_development(config):
                print(" Plugin development environment ready")

            print("\n Plugin development environment ready!")
            print(f"\n Developing plugin: {plugin_name}")
            print("  • Plugin files are being watched for changes")
            print("  • Hot reload is enabled")
            print("  • Check logs with 'coffeebreak deps logs'")

            return True

        except Exception as e:
            print(f"\n Error during plugin setup: {e}")
            return False

    def _setup_repositories(self, config: Dict[str, Any]) -> bool:
        """Verify repositories exist, clone if missing (no auto-pull for dev workflow)."""
        try:
            coffeebreak_config = config.get("coffeebreak", {})
            repositories = coffeebreak_config.get("repositories", [])

            if not repositories:
                if self.verbose:
                    print("No repositories configured, skipping...")
                return True

            # First pass: check which repos need cloning
            repos_to_clone = []
            existing_repos = []

            for repo_config in repositories:
                name = repo_config.get("name")
                url = repo_config.get("url")
                path = repo_config.get("path", f"./{name}")

                if not name or not url:
                    if self.verbose:
                        print(f"  Skipping invalid repository config: {repo_config}")
                    continue

                repo_path = os.path.abspath(path)

                if os.path.exists(repo_path) and os.path.isdir(
                    os.path.join(repo_path, ".git")
                ):
                    existing_repos.append(name)
                else:
                    repos_to_clone.append(repo_config)

            # Only show output if there's work to do OR if verbose mode
            if repos_to_clone or self.verbose:
                if repos_to_clone:
                    print(
                        f"\nSetting up repositories... ({len(repos_to_clone)} to clone)"
                    )
                elif self.verbose:
                    print("\nVerifying repositories...")

            # Show existing repos only in verbose mode
            if existing_repos and self.verbose:
                for name in existing_repos:
                    print(f"     {name}: Repository exists ✓")

            # Clone missing repositories
            cloned_any = False
            for repo_config in repos_to_clone:
                name = repo_config.get("name")
                url = repo_config.get("url")
                path = repo_config.get("path", f"./{name}")
                branch = repo_config.get("branch", "main")
                repo_path = os.path.abspath(path)

                print(f"     {name}: Cloning...")
                try:
                    self.git_operations.clone_repository(url, repo_path, branch)
                    print(f"   {name}: Cloned ✓")
                    cloned_any = True

                    # Run startup commands if specified
                    startup_commands = repo_config.get("startup_command", [])
                    if startup_commands:
                        print(f"     {name}: Running startup commands...")
                        self._run_startup_commands(repo_path, startup_commands)

                except Exception as e:
                    print(f"   {name}: Clone failed - {e}")
                    continue

            # Summary message only if there was actual work or verbose mode
            if cloned_any:
                print(f"Repositories ready ({len(repos_to_clone)} cloned)")
            elif self.verbose and existing_repos:
                print(f"All {len(existing_repos)} repositories already exist")

            return True

        except Exception as e:
            print(f"Repository setup error: {e}")
            return False

    def _start_dependencies(
        self,
        config: Dict[str, Any],
        profile: Optional[str],
        services: Optional[List[str]],
    ) -> bool:
        """Start dependency services."""
        try:
            # Use the DependencyManager to start services
            if services:
                # Start specific services
                for service in services:
                    if not self.dependency_manager.start_service(service):
                        return False
            else:
                # Start all services in profile
                if not self.dependency_manager.start_profile(profile or "full"):
                    return False

            # Wait for services to be healthy
            print("     Waiting for services to be ready...")
            if self._wait_for_services_healthy():
                return True
            else:
                print("    Some services may not be fully ready")
                return True  # Continue anyway

        except Exception as e:
            print(f"Dependency startup error: {e}")
            return False

    def _generate_environment_files(self, config: Dict[str, Any]) -> bool:
        """Generate environment files for development."""
        try:
            # Generate connection info from running containers
            connection_info = self.dependency_manager.generate_connection_info()

            # Generate main .env.local file
            env_path = self.file_manager.generate_env_file(
                connection_info=connection_info,
                output_path=".env.local",
                include_secrets=True,
            )

            # Update .gitignore
            self.file_manager.create_gitignore()

            return True

        except Exception as e:
            print(f"Environment file generation error: {e}")
            return False

    def _start_development_servers(
        self, config: Dict[str, Any], detach: bool = False
    ) -> bool:
        """Start development servers for all repositories."""
        try:
            coffeebreak_config = config.get("coffeebreak", {})
            repositories = coffeebreak_config.get("repositories", [])

            # Get connection info from running dependency services
            connection_info = {}
            try:
                connection_info = self.dependency_manager.generate_connection_info()
                if self.verbose and connection_info:
                    print(
                        f"    Generated connection info for {len(connection_info)} services"
                    )
            except Exception as e:
                if self.verbose:
                    print(f"    Warning: Could not generate connection info: {e}")

            # Start all development servers with enhanced environment
            for repo_config in repositories:
                name = repo_config.get("name")
                path = repo_config.get("path", f"./{name}")
                startup_command = repo_config.get("startup_command", [])

                if not startup_command:
                    continue

                repo_path = os.path.abspath(path)
                if not os.path.exists(repo_path):
                    continue

                print(f"     Starting {name} development server...")
                self._start_background_process(
                    repo_path,
                    startup_command,
                    name,
                    detach=detach,
                    env_vars=connection_info,
                )

            print("DETACH MODE:", detach)
            if not detach:
                # Show live logs immediately
                if self.processes:
                    print("\n" + "=" * 60)
                    print("LIVE LOGS (Press Ctrl+C to stop)")
                    print("=" * 60)
                    self._show_live_logs()

            return True

        except Exception as e:
            print(f"Development server startup error: {e}")
            return False

    def _start_plugin_development(self, config: Dict[str, Any]) -> bool:
        """Start plugin development environment."""
        try:
            plugin_config = config.get("plugin", {})

            # Enable hot reload for plugin files
            if plugin_config.get("hot_reload", True):
                print("   Hot reload enabled")

            # Mount plugin paths if specified
            mount_paths = plugin_config.get("mount_paths", [])
            if mount_paths:
                print(f"     Plugin paths mounted: {len(mount_paths)} paths")

            return True

        except Exception as e:
            print(f"Plugin development setup error: {e}")
            return False

    def _wait_for_services_healthy(self, timeout: int = 60) -> bool:
        """Wait for services to become healthy."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                if self.dependency_manager.check_all_services_healthy():
                    return True
                time.sleep(2)
            except Exception:
                time.sleep(2)

        return False

    def _run_startup_commands(self, repo_path: str, commands: List[str]) -> None:
        """Run startup commands in repository."""
        try:
            for command in commands:
                if self.verbose:
                    print(f"    Running: {command}")

                result = subprocess.run(
                    command.split(),
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    print(f"      Command failed: {command}")
                    if self.verbose:
                        print(f"    Error: {result.stderr}")
                elif self.verbose:
                    print(f"     Command completed")

        except subprocess.TimeoutExpired:
            print(f"      Command timed out: {command}")
        except Exception as e:
            print(f"      Command error: {e}")

    def _start_background_process(
        self,
        repo_path: str,
        command: List[str],
        name: str,
        detach: bool = False,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        """Start a background development process with enhanced environment variables."""
        try:
            import subprocess
            import threading

            command_str = " ".join(command)
            print(f"    Starting: {command_str} (in {repo_path})")

            # Setup enhanced environment variables
            enhanced_env = self._prepare_process_environment(env_vars)

            # Create log directory recursively with fallback
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                log_file = self.log_dir / f"{name}.log"
            except PermissionError:
                # Fallback to user directory if system directory fails
                fallback_dir = Path.home() / ".local/state/coffeebreak/logs"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                log_file = fallback_dir / f"{name}.log"
                if self.verbose:
                    print(f"    Using fallback log directory: {fallback_dir}")

            # Start process
            if detach:
                # Detached mode - redirect to log files only
                with open(log_file, "w") as log:
                    process = subprocess.Popen(
                        command,
                        cwd=repo_path,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env=enhanced_env,
                        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                    )
                print(f"    ✓ {name} started (PID: {process.pid}, logs: {log_file})")
            else:
                # Interactive mode - use PIPE but also log to file
                process = subprocess.Popen(
                    command,
                    cwd=repo_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=enhanced_env,
                    universal_newlines=True,
                    bufsize=1,
                )
                print(f"    ✓ {name} started (PID: {process.pid}, logs: {log_file})")

                # Start background thread to tee output to both console and log file
                log_thread = threading.Thread(
                    target=self._tee_process_output,
                    args=(process, log_file, name),
                    daemon=True,
                )
                log_thread.start()

            # Save process info with log file path
            self._save_process_info(
                name, process.pid, command, repo_path, str(log_file)
            )

            # Store process for later management
            self.processes[name] = process

            return process.pid

        except Exception as e:
            print(f"      ✗ Failed to start {name}: {e}")
            return None

    def _prepare_process_environment(
        self, env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Prepare enhanced environment variables for development processes.

        Args:
            env_vars: Additional environment variables to include

        Returns:
            Dict[str, str]: Enhanced environment variables
        """
        import os

        # Start with current environment
        enhanced_env = os.environ.copy()

        # Add virtual environment variables if available
        try:
            venv_env = self._get_virtual_environment_vars()
            enhanced_env.update(venv_env)
        except Exception as e:
            if self.verbose:
                print(f"    Note: Could not load virtual environment variables: {e}")

        # Add development-specific variables
        dev_env = {
            "NODE_ENV": "development",
            "ENVIRONMENT": "development",
            "API_BASE_URL": "http://localhost:8000",
        }
        enhanced_env.update(dev_env)

        # Add passed environment variables (highest priority)
        if env_vars:
            enhanced_env.update(env_vars)
            if self.verbose:
                print(f"    Added {len(env_vars)} connection environment variables")

        return enhanced_env

    def _get_virtual_environment_vars(self) -> Dict[str, str]:
        """
        Get virtual environment variables from the project configuration.

        Returns:
            Dict[str, str]: Virtual environment variables
        """
        venv_vars = {}

        try:
            # Load environment configuration from coffeebreak.yml
            config = self.config_manager.load_config()
            env_config = config.get("coffeebreak", {}).get("environment", {})

            if env_config.get("type") == "venv":
                venv_path = env_config.get("path")
                if venv_path:
                    import os
                    from pathlib import Path

                    venv_path = Path(venv_path).resolve()
                    if venv_path.exists():
                        venv_vars["VIRTUAL_ENV"] = str(venv_path)
                        venv_vars["PATH"] = (
                            f"{venv_path / 'bin'}:{os.environ.get('PATH', '')}"
                        )

                        # Remove PYTHONHOME if present
                        if "PYTHONHOME" in venv_vars:
                            del venv_vars["PYTHONHOME"]

            elif env_config.get("type") == "conda":
                conda_name = env_config.get("name")
                if conda_name:
                    venv_vars["CONDA_DEFAULT_ENV"] = conda_name

        except Exception as e:
            if self.verbose:
                print(f"    Warning: Could not load environment config: {e}")

        return venv_vars

    def _show_live_logs(self):
        """Show live logs from all running processes."""
        try:
            import select
            import signal
            import sys

            def signal_handler(sig, frame):
                print("\n\nShutting down development environment...")
                self._stop_all_processes()
                sys.exit(0)

            # Set up signal handler for Ctrl+C
            signal.signal(signal.SIGINT, signal_handler)

            # Color codes for different services
            colors = {
                "core": "\033[94m",  # Blue
                "frontend": "\033[92m",  # Green
                "event-app": "\033[93m",  # Yellow
                "reset": "\033[0m",  # Reset
            }

            service_names = list(self.processes.keys())

            while True:
                # Check if any processes are still alive
                alive_processes = []
                for name, process in self.processes.items():
                    if process.poll() is None:  # Process is still running
                        alive_processes.append(name)

                if not alive_processes:
                    print("\nAll development servers have stopped.")
                    break

                # Read output from processes
                for name, process in self.processes.items():
                    if process.poll() is None and process.stdout:
                        try:
                            # Use select to check if there's data to read (Unix only)
                            if hasattr(select, "select"):
                                ready, _, _ = select.select(
                                    [process.stdout], [], [], 0.1
                                )
                                if ready:
                                    line = process.stdout.readline()
                                    if line:
                                        color = colors.get(name, "")
                                        reset = colors["reset"]
                                        print(f"{color}[{name}]{reset} {line.rstrip()}")
                            else:
                                # Fallback for Windows
                                try:
                                    line = process.stdout.readline()
                                    if line:
                                        print(f"[{name}] {line.rstrip()}")
                                except:
                                    pass
                        except:
                            continue

                # Small delay to prevent excessive CPU usage
                import time

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\nShutting down development environment...")
            self._stop_all_processes()
        except Exception as e:
            print(f"Error in live logs: {e}")

    def _stop_all_processes(self):
        """Stop all running development processes."""
        for name, process in self.processes.items():
            try:
                if process.poll() is None:  # Process is still running
                    print(f"Stopping {name}...")
                    process.terminate()

                    # Wait a bit for graceful shutdown
                    import time

                    time.sleep(2)

                    # Force kill if still running
                    if process.poll() is None:
                        process.kill()
            except Exception as e:
                print(f"Error stopping {name}: {e}")

        # Clear processes
        self.processes.clear()

        # Clean up PID file
        try:
            pids_file = Path(".coffeebreak/pids.json")
            if pids_file.exists():
                pids_file.unlink()
        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not clean PID file: {e}")

    def _show_environment_status(self) -> None:
        """Show current environment status."""
        try:
            print("\n Environment Status:")

            # Show running containers
            running_containers = self.dependency_manager.get_running_containers()
            if running_containers:
                print("     Running containers:")
                for container in running_containers:
                    status = "" if container.get("healthy", True) else ""
                    print(f"    {status} {container['name']} - {container['status']}")

            # Show network info
            network_info = self.dependency_manager.get_network_info()
            if network_info:
                print(f"     Network: {network_info.get('name', 'default')}")

        except Exception as e:
            print(f"    Could not get environment status: {e}")

    def get_health_status_summary(self) -> str:
        """Get a summary of the current health status."""
        try:
            return self.dependency_manager.get_health_report()
        except Exception as e:
            return f"Error getting health status: {e}"

    def _cleanup_failed_setup(self, success_steps: List[str]) -> None:
        """Clean up after failed setup."""
        try:
            print("\n Cleaning up failed setup...")

            if "dependencies" in success_steps:
                print("  Stopping started dependencies...")
                self.dependency_manager.stop_health_monitoring()
                self.dependency_manager.stop_all_services()

            if "monitoring" in success_steps:
                print("  Stopping health monitoring...")
                self.dependency_manager.stop_health_monitoring()

            print("  Cleanup completed")

        except Exception as e:
            print(f"    Cleanup error: {e}")

    def stop_development_environment(self) -> bool:
        """Stop the development environment."""
        try:
            print(" Stopping development environment...")

            # Stop health monitoring first
            print("  Stopping health monitoring...")
            self.dependency_manager.stop_health_monitoring()

            # Stop all dependency services
            print("  Stopping dependency services...")
            self.dependency_manager.stop_all_services()

            # Clean up environment files
            env_files = [".env.local", ".env.secrets"]
            for env_file in env_files:
                if os.path.exists(env_file):
                    os.remove(env_file)
                    print(f"  Removed {env_file}")

            print(" Development environment stopped")

            # Clean up process tracking
            self._cleanup_dead_processes()

            return True

        except Exception as e:
            print(f" Error stopping environment: {e}")
            return False

    def get_environment_status(self) -> Dict[str, Any]:
        """Get current environment status."""
        try:
            env_type = self.config_manager.detect_environment()

            status = {
                "environment_type": env_type.value if env_type else "unknown",
                "is_running": False,
                "services": {},
                "repositories": {},
                "errors": [],
            }

            # Check if we have a configuration
            if env_type != EnvironmentType.UNINITIALIZED:
                try:
                    config = self.config_manager.load_config()
                    status["config_loaded"] = True
                except Exception as e:
                    status["errors"].append(f"Config load error: {e}")
                    return status
            else:
                status["errors"].append("No configuration found")
                return status

            # Check running status from actual processes
            running_processes = self._get_running_processes()
            status["is_running"] = len(running_processes) > 0
            status["running_processes"] = running_processes

            # Check service status using health monitoring
            try:
                health_status = self.dependency_manager.get_health_status()
                status["monitoring_active"] = health_status.get(
                    "monitoring_active", False
                )

                # Add container health info
                containers_info = health_status.get("containers", {})
                for container_name, health_info in containers_info.items():
                    status["services"][container_name] = {
                        "status": health_info["status"],
                        "healthy": health_info["status"] == "healthy",
                        "method": health_info.get("method", "unknown"),
                    }

                # Add overall health status
                status["overall_health"] = health_status.get(
                    "overall_status", "unknown"
                )

            except Exception as e:
                status["errors"].append(f"Service check error: {e}")

            # Check repository status
            if env_type == EnvironmentType.FULL_DEV:
                try:
                    coffeebreak_config = config.get("coffeebreak", {})
                    repositories = coffeebreak_config.get("repositories", [])

                    for repo_config in repositories:
                        name = repo_config.get("name")
                        path = repo_config.get("path", f"./{name}")

                        if name:
                            repo_status = self.git_operations.check_repository_status(
                                path
                            )
                            status["repositories"][name] = repo_status

                except Exception as e:
                    status["errors"].append(f"Repository check error: {e}")

            return status

        except Exception as e:
            return {
                "environment_type": "unknown",
                "is_running": False,
                "services": {},
                "repositories": {},
                "errors": [f"Status check error: {e}"],
            }
