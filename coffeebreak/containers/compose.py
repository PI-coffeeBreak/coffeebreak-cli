"""Docker Compose orchestration for CoffeeBreak CLI."""

import os
import subprocess
from typing import Any, Dict, List, Optional

import yaml

from ..utils.errors import DockerError
from ..utils.files import FileManager


class DockerComposeOrchestrator:
    """Manages Docker Compose files and orchestration for CoffeeBreak dependencies."""

    def __init__(self, verbose: bool = False):
        """Initialize Docker Compose orchestrator."""
        self.verbose = verbose
        self.file_manager = FileManager(verbose=verbose)
        self.compose_file = "docker-compose.coffeebreak.yml"
        self.network_name = "coffeebreak-network"

    def generate_compose_file(
        self,
        dependencies_config: Dict[str, Any],
        profile: Optional[str] = None,
        services: Optional[List[str]] = None,
    ) -> str:
        """
        Generate Docker Compose file for specified dependencies.

        Args:
            dependencies_config: Dependencies configuration from config file
            profile: Profile name to use (full, minimal, plugin-dev)
            services: Specific services to include

        Returns:
            str: Path to generated compose file
        """
        try:
            # Determine which services to include
            if services:
                service_names = services
            elif profile:
                profiles = dependencies_config.get("profiles", {})
                service_names = profiles.get(profile, [])
            else:
                # Use all available services
                service_names = list(dependencies_config.get("services", {}).keys())

            if not service_names:
                raise DockerError(f"No services found for profile '{profile}' or services list")

            # Generate compose configuration
            compose_config = self._generate_compose_config(dependencies_config, service_names)

            # Write compose file
            with open(self.compose_file, "w", encoding="utf-8") as f:
                yaml.dump(compose_config, f, default_flow_style=False, indent=2)

            if self.verbose:
                print(f"Generated Docker Compose file: {self.compose_file}")
                print(f"Services included: {', '.join(service_names)}")

            return self.compose_file

        except Exception as e:
            raise DockerError(f"Failed to generate compose file: {e}")

    def _generate_compose_config(self, dependencies_config: Dict[str, Any], service_names: List[str]) -> Dict[str, Any]:
        """Generate Docker Compose configuration."""
        services_config = dependencies_config.get("services", {})

        compose_config = {
            "version": "3.8",
            "networks": {self.network_name: {"driver": "bridge", "name": self.network_name}},
            "volumes": {},
            "services": {},
        }

        # Add services
        for service_name in service_names:
            if service_name not in services_config:
                if self.verbose:
                    print(f"Warning: Service '{service_name}' not found in configuration")
                continue

            service_config = services_config[service_name]
            compose_service = self._convert_service_config(service_name, service_config)

            if compose_service:
                compose_config["services"][service_name] = compose_service

                # Add volumes if needed
                volumes = service_config.get("volumes", [])
                for volume in volumes:
                    if ":" in volume:
                        volume_name = volume.split(":")[0]
                        if not volume_name.startswith("./") and not volume_name.startswith("/"):
                            compose_config["volumes"][volume_name] = {}

        return compose_config

    def _convert_service_config(self, service_name: str, service_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert service configuration to Docker Compose format."""
        try:
            compose_service = {
                "container_name": service_config.get("container_name", f"coffeebreak-{service_name}"),
                "networks": [self.network_name],
                "restart": "unless-stopped",
            }

            # Add image or build configuration
            if "build" in service_config:
                compose_service["build"] = service_config["build"]
            elif "image" in service_config:
                compose_service["image"] = service_config["image"]
            else:
                raise KeyError("Either 'image' or 'build' must be specified")

            # Add environment variables
            if "environment" in service_config:
                compose_service["environment"] = service_config["environment"]

            # Add ports
            if "ports" in service_config:
                compose_service["ports"] = service_config["ports"]

            # Add volumes
            if "volumes" in service_config:
                compose_service["volumes"] = service_config["volumes"]

            # Add dependencies
            if "depends_on" in service_config:
                compose_service["depends_on"] = service_config["depends_on"]

            # Add health check
            if "healthcheck" in service_config:
                compose_service["healthcheck"] = service_config["healthcheck"]

            # Add command if specified
            if "command" in service_config:
                compose_service["command"] = service_config["command"]

            # Add working directory if specified
            if "working_dir" in service_config:
                compose_service["working_dir"] = service_config["working_dir"]

            return compose_service

        except KeyError as e:
            if self.verbose:
                print(f"Warning: Missing required field {e} for service {service_name}")
            return None

    def start_services(self, detach: bool = True) -> bool:
        """
        Start services using Docker Compose.

        Args:
            detach: Whether to run in detached mode

        Returns:
            bool: True if services started successfully
        """
        try:
            if not os.path.exists(self.compose_file):
                raise DockerError(f"Compose file not found: {self.compose_file}")

            cmd = ["docker-compose", "-f", self.compose_file, "up"]
            if detach:
                cmd.append("-d")

            if self.verbose:
                print(f"Starting services: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=not self.verbose,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if result.returncode == 0:
                if self.verbose:
                    print("Services started successfully")
                return True
            else:
                error_msg = f"Docker Compose failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise DockerError(error_msg)

        except subprocess.TimeoutExpired:
            raise DockerError("Docker Compose start timed out")
        except FileNotFoundError:
            raise DockerError("docker-compose command not found. Please install Docker Compose.")
        except Exception as e:
            raise DockerError(f"Failed to start services: {e}")

    def stop_services(self, service_names: Optional[List[str]] = None) -> bool:
        """
        Stop services using Docker Compose.

        Args:
            service_names: Optional list of specific services to stop (None for all)

        Returns:
            bool: True if services stopped successfully
        """
        try:
            if not os.path.exists(self.compose_file):
                if self.verbose:
                    print(f"Compose file not found: {self.compose_file}")
                return True  # Nothing to stop

            if service_names:
                # Stop specific services
                cmd = [
                    "docker-compose",
                    "-f",
                    self.compose_file,
                    "stop",
                ] + service_names
            else:
                # Stop all services
                cmd = ["docker-compose", "-f", self.compose_file, "down"]

            if self.verbose:
                print(f"Stopping services: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=not self.verbose, text=True, timeout=60)

            if result.returncode == 0:
                if self.verbose:
                    print("Services stopped successfully")
                return True
            else:
                error_msg = f"Docker Compose stop failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise DockerError(error_msg)

        except subprocess.TimeoutExpired:
            raise DockerError("Docker Compose stop timed out")
        except Exception as e:
            raise DockerError(f"Failed to stop services: {e}")

    def get_service_status(self) -> List[Dict[str, Any]]:
        """
        Get status of services managed by Docker Compose.

        Returns:
            List[Dict[str, Any]]: List of service status information
        """
        try:
            if not os.path.exists(self.compose_file):
                return []

            cmd = ["docker-compose", "-f", self.compose_file, "ps", "--format", "json"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON output
                import json

                services = []
                for line in result.stdout.strip().split("\\n"):
                    if line.strip():
                        try:
                            service_info = json.loads(line)
                            services.append(
                                {
                                    "name": service_info.get("Name", "unknown"),
                                    "status": service_info.get("State", "unknown"),
                                    "ports": service_info.get("Ports", ""),
                                    "image": service_info.get("Image", "unknown"),
                                }
                            )
                        except json.JSONDecodeError:
                            continue
                return services
            else:
                return []

        except subprocess.TimeoutExpired:
            if self.verbose:
                print("Docker Compose status check timed out")
            return []
        except Exception as e:
            if self.verbose:
                print(f"Failed to get service status: {e}")
            return []

    def get_service_logs(self, service_name: Optional[str] = None, tail: int = 100) -> str:
        """
        Get logs from services.

        Args:
            service_name: Specific service to get logs from (None for all)
            tail: Number of lines to tail

        Returns:
            str: Log output
        """
        try:
            if not os.path.exists(self.compose_file):
                return "No compose file found"

            cmd = [
                "docker-compose",
                "-f",
                self.compose_file,
                "logs",
                "--tail",
                str(tail),
            ]

            if service_name:
                cmd.append(service_name)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return result.stdout
            else:
                return f"Failed to get logs: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Log retrieval timed out"
        except Exception as e:
            return f"Error getting logs: {e}"

    def scale_service(self, service_name: str, replicas: int) -> bool:
        """
        Scale a service to specified number of replicas.

        Args:
            service_name: Name of service to scale
            replicas: Number of replicas

        Returns:
            bool: True if scaling successful
        """
        try:
            if not os.path.exists(self.compose_file):
                raise DockerError(f"Compose file not found: {self.compose_file}")

            cmd = [
                "docker-compose",
                "-f",
                self.compose_file,
                "up",
                "-d",
                "--scale",
                f"{service_name}={replicas}",
            ]

            if self.verbose:
                print(f"Scaling {service_name} to {replicas} replicas")

            result = subprocess.run(cmd, capture_output=not self.verbose, text=True, timeout=120)

            return result.returncode == 0

        except Exception as e:
            if self.verbose:
                print(f"Failed to scale service: {e}")
            return False

    def restart_service(self, service_name: str) -> bool:
        """
        Restart a specific service.

        Args:
            service_name: Name of service to restart

        Returns:
            bool: True if restart successful
        """
        try:
            if not os.path.exists(self.compose_file):
                raise DockerError(f"Compose file not found: {self.compose_file}")

            cmd = ["docker-compose", "-f", self.compose_file, "restart", service_name]

            if self.verbose:
                print(f"Restarting service: {service_name}")

            result = subprocess.run(cmd, capture_output=not self.verbose, text=True, timeout=60)

            return result.returncode == 0

        except Exception as e:
            if self.verbose:
                print(f"Failed to restart service: {e}")
            return False

    def exec_command(self, service_name: str, command: List[str]) -> str:
        """
        Execute a command in a running service container.

        Args:
            service_name: Name of service to execute command in
            command: Command to execute

        Returns:
            str: Command output
        """
        try:
            if not os.path.exists(self.compose_file):
                return "Compose file not found"

            cmd = [
                "docker-compose",
                "-f",
                self.compose_file,
                "exec",
                "-T",
                service_name,
            ] + command

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return result.stdout
            else:
                return f"Command failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Command execution timed out"
        except Exception as e:
            return f"Error executing command: {e}"

    def cleanup(self, remove_volumes: bool = False) -> bool:
        """
        Clean up Docker Compose resources.

        Args:
            remove_volumes: Whether to remove named volumes

        Returns:
            bool: True if cleanup successful
        """
        try:
            if not os.path.exists(self.compose_file):
                return True  # Nothing to clean up

            cmd = ["docker-compose", "-f", self.compose_file, "down"]

            if remove_volumes:
                cmd.extend(["--volumes", "--remove-orphans"])

            if self.verbose:
                print(f"Cleaning up: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=not self.verbose, text=True, timeout=60)

            # Remove compose file
            if os.path.exists(self.compose_file):
                os.remove(self.compose_file)
                if self.verbose:
                    print(f"Removed compose file: {self.compose_file}")

            return result.returncode == 0

        except Exception as e:
            if self.verbose:
                print(f"Failed to cleanup: {e}")
            return False

    def get_compose_file_path(self) -> str:
        """Get the path to the compose file."""
        return os.path.abspath(self.compose_file)

    def is_compose_available(self) -> bool:
        """Check if Docker Compose is available."""
        try:
            result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
