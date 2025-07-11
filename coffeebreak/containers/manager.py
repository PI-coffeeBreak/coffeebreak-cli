"""Docker container management for CoffeeBreak CLI."""

from typing import Any, Dict, List


# Lazy imports for docker to avoid import issues
def _get_docker_imports():
    """Get docker imports, importing them only when needed."""
    try:
        import docker
        from docker.errors import APIError, DockerException, NotFound

        return docker, APIError, DockerException, NotFound
    except ImportError:
        # Return dummy classes if docker is not available
        class DummyDockerClient:
            def __init__(self, *args, **kwargs):
                pass

            def ping(self):
                pass

            def networks(self):
                return DummyNetworks()

            def containers(self):
                return DummyContainers()

            @classmethod
            def from_env(cls):
                return cls()

        class DummyNetworks:
            def get(self, name):
                raise DummyNotFound()

            def create(self, name, driver):
                pass

        class DummyContainers:
            def get(self, name):
                raise DummyNotFound()

            def run(self, **kwargs):
                pass

        class DummyNotFound(Exception):
            pass

        class DummyAPIError(Exception):
            pass

        class DummyDockerException(Exception):
            pass

        return DummyDockerClient, DummyAPIError, DummyDockerException, DummyNotFound


docker, APIError, DockerException, NotFound = _get_docker_imports()  # noqa: E402

from .health import HealthChecker  # noqa: E402


class ContainerManagerError(Exception):
    """Raised when container operations fail."""

    pass


class ContainerManager:
    """Manages Docker containers for CoffeeBreak CLI."""

    def __init__(self, verbose: bool = False):
        """
        Initialize container manager.

        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose
        self.health_checker = HealthChecker()
        self._client = None

    @property
    def client(self) -> Any:
        """Get Docker client, creating it if necessary."""
        if self._client is None:
            try:
                self._client = docker.from_env()
                # Test connection
                self._client.ping()
            except DockerException as e:
                raise ContainerManagerError(f"Cannot connect to Docker daemon: {e}") from e

        return self._client

    def create_network(self, name: str, driver: str = "bridge") -> bool:
        """
        Create Docker network if it doesn't exist.

        Args:
            name: Network name
            driver: Network driver (default: bridge)

        Returns:
            bool: True if network created or already exists

        Raises:
            ContainerManagerError: If network creation fails
        """
        try:
            # Check if network already exists
            try:
                self.client.networks.get(name)
                if self.verbose:
                    print(f"Network '{name}' already exists")
                return True
            except NotFound:
                pass

            # Create network
            self.client.networks.create(name, driver=driver)

            if self.verbose:
                print(f"Created network '{name}' with driver '{driver}'")

            return True

        except APIError as e:
            raise ContainerManagerError(f"Failed to create network '{name}': {e}") from e
        except Exception as e:
            raise ContainerManagerError(f"Unexpected error creating network: {e}") from e

    def remove_network(self, name: str) -> bool:
        """
        Remove Docker network.

        Args:
            name: Network name

        Returns:
            bool: True if network removed or doesn't exist
        """
        try:
            network = self.client.networks.get(name)
            network.remove()

            if self.verbose:
                print(f"Removed network '{name}'")

            return True

        except NotFound:
            if self.verbose:
                print(f"Network '{name}' not found (already removed)")
            return True
        except APIError as e:
            raise ContainerManagerError(f"Failed to remove network '{name}': {e}") from e

    def start_container(self, config: Dict[str, Any]) -> str:
        """
        Start a container with the given configuration.

        Args:
            config: Container configuration

        Returns:
            str: Container ID

        Raises:
            ContainerManagerError: If container start fails
        """
        container_name = config.get("container_name") or config.get("name")

        try:
            # Check if container already exists
            try:
                container = self.client.containers.get(container_name)

                if container.status == "running":
                    if self.verbose:
                        print(f"Container '{container_name}' is already running")
                    return container.id
                elif container.status in ["paused", "exited"]:
                    container.start()
                    if self.verbose:
                        print(f"Started existing container '{container_name}'")
                    return container.id

            except NotFound:
                pass

            # Handle image or build configuration
            if "build" in config:
                # Build image from context
                if container_name is None:
                    container_name = "default"
                image = self._build_image_from_context(config["build"], container_name)
            elif "image" in config:
                # Use pre-built image
                image = config["image"]
                self._pull_image_if_needed(image)
            else:
                raise ContainerManagerError("Either 'image' or 'build' must be specified in configuration")

            # Prepare container configuration with resolved image
            run_config = self._prepare_run_config(config, image)

            # Create and start container
            container = self.client.containers.run(**run_config)

            if self.verbose:
                print(f"Started new container '{container_name}' from image '{image}'")

            return container.id

        except APIError as e:
            raise ContainerManagerError(f"Failed to start container '{container_name}': {e}") from e
        except Exception as e:
            raise ContainerManagerError(f"Unexpected error starting container: {e}") from e

    def stop_container(self, name: str, timeout: int = 10) -> bool:
        """
        Stop a container.

        Args:
            name: Container name or ID
            timeout: Timeout in seconds

        Returns:
            bool: True if container stopped or doesn't exist
        """
        try:
            container = self.client.containers.get(name)

            if container.status == "running":
                container.stop(timeout=timeout)
                if self.verbose:
                    print(f"Stopped container '{name}'")
            else:
                if self.verbose:
                    print(f"Container '{name}' is not running")

            return True

        except NotFound:
            if self.verbose:
                print(f"Container '{name}' not found")
            return True
        except APIError as e:
            raise ContainerManagerError(f"Failed to stop container '{name}': {e}") from e

    def remove_container(self, name: str, force: bool = False) -> bool:
        """
        Remove a container.

        Args:
            name: Container name or ID
            force: Force removal of running container

        Returns:
            bool: True if container removed or doesn't exist
        """
        try:
            container = self.client.containers.get(name)
            container.remove(force=force)

            if self.verbose:
                print(f"Removed container '{name}'")

            return True

        except NotFound:
            if self.verbose:
                print(f"Container '{name}' not found")
            return True
        except APIError as e:
            raise ContainerManagerError(f"Failed to remove container '{name}': {e}") from e

    def get_container_status(self, name: str) -> Dict[str, Any]:
        """
        Get container status information.

        Args:
            name: Container name or ID

        Returns:
            Dict[str, Any]: Container status information
        """
        try:
            container = self.client.containers.get(name)

            status = {
                "name": container.name,
                "id": container.short_id,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else container.image.id,
                "created": container.attrs["Created"],
                "ports": self._extract_port_mappings(container),
                "networks": list(container.attrs["NetworkSettings"]["Networks"].keys()),
                "health": None,
            }

            # Check health if container has health check
            if container.status == "running":
                health_status = self.health_checker.check_container_health(container)
                status["health"] = health_status

            return status

        except NotFound:
            return {"name": name, "status": "not_found", "error": "Container not found"}
        except Exception as e:
            return {"name": name, "status": "error", "error": str(e)}

    def list_containers(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """
        List containers.

        Args:
            all_containers: Include stopped containers

        Returns:
            List[Dict[str, Any]]: List of container information
        """
        try:
            containers = self.client.containers.list(all=all_containers)

            container_list = []
            for container in containers:
                status = {
                    "name": container.name,
                    "id": container.short_id,
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else container.image.id,
                    "ports": self._extract_port_mappings(container),
                }
                container_list.append(status)

            return container_list

        except APIError as e:
            raise ContainerManagerError(f"Failed to list containers: {e}") from e

    def get_container_logs(self, name: str, tail: int = 100) -> str:
        """
        Get container logs.

        Args:
            name: Container name or ID
            tail: Number of lines to return

        Returns:
            str: Container logs
        """
        try:
            container = self.client.containers.get(name)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode("utf-8")

        except NotFound:
            return f"Container '{name}' not found"
        except Exception as e:
            return f"Error getting logs: {e}"

    def _pull_image_if_needed(self, image: str) -> None:
        """Pull Docker image if not present locally."""
        try:
            # Check if image exists locally
            self.client.images.get(image)
            if self.verbose:
                print(f"Image '{image}' already exists locally")
        except NotFound:
            if self.verbose:
                print(f"Pulling image '{image}'...")
            try:
                self.client.images.pull(image)
                if self.verbose:
                    print(f"Successfully pulled image '{image}'")
            except APIError as e:
                raise ContainerManagerError(f"Failed to pull image '{image}': {e}") from e

    def _prepare_run_config(self, config: Dict[str, Any], image: str) -> Dict[str, Any]:
        """Prepare container run configuration."""
        run_config = {
            "image": image,
            "detach": True,
            "name": config.get("container_name") or config.get("name"),
        }

        # Add optional configurations
        if "ports" in config:
            run_config["ports"] = self._parse_port_mappings(config["ports"])

        if "environment" in config:
            run_config["environment"] = config["environment"]

        if "volumes" in config:
            run_config["volumes"] = self._parse_volumes(config["volumes"])

        if "command" in config:
            run_config["command"] = config["command"]

        if "network" in config:
            run_config["network"] = config["network"]

        return run_config

    def _parse_port_mappings(self, ports: List[str]) -> Dict[str, int]:
        """Parse port mappings from string format."""
        port_map = {}
        for port in ports:
            if ":" in port:
                host_port, container_port = port.split(":", 1)
                port_map[container_port] = int(host_port)
            else:
                port_map[port] = int(port)
        return port_map

    def _parse_volumes(self, volumes: List[str]) -> Dict[str, Dict[str, str]]:
        """Parse volume mappings."""
        volume_map = {}
        for volume in volumes:
            if ":" in volume:
                parts = volume.split(":")
                if len(parts) == 2:
                    # host_path:container_path
                    host_path, container_path = parts
                    volume_map[host_path] = {"bind": container_path, "mode": "rw"}
                elif len(parts) == 3:
                    # host_path:container_path:mode
                    host_path, container_path, mode = parts
                    volume_map[host_path] = {"bind": container_path, "mode": mode}
                else:
                    # Fallback for complex volume specs
                    host_path = parts[0]
                    container_path = parts[1]
                    mode = parts[2] if len(parts) > 2 else "rw"
                    volume_map[host_path] = {"bind": container_path, "mode": mode}
            else:
                # Named volume
                volume_map[volume] = {"bind": volume, "mode": "rw"}
        return volume_map

    def _build_image_from_context(self, build_config: Dict[str, Any], container_name: str) -> str:
        """Build Docker image from build context."""
        context = build_config["context"]
        dockerfile = build_config.get("dockerfile", "Dockerfile")
        tag = f"coffeebreak-{container_name}:latest"

        try:
            if self.verbose:
                print(f"Building image '{tag}' from context '{context}' with dockerfile '{dockerfile}'")

            # Build image using Docker API
            image, build_logs = self.client.images.build(
                path=context,
                dockerfile=dockerfile,
                tag=tag,
                rm=True,  # Remove intermediate containers
            )

            if self.verbose:
                for log in build_logs:
                    if "stream" in log:
                        print(log["stream"].strip())

            if self.verbose:
                print(f"Successfully built image '{tag}'")

            return tag

        except APIError as e:
            raise ContainerManagerError(f"Failed to build image from context '{context}': {e}") from e
        except Exception as e:
            raise ContainerManagerError(f"Unexpected error building image: {e}") from e

    def _extract_port_mappings(self, container) -> Dict[str, str]:
        """Extract port mappings from container."""
        ports = {}
        port_info = container.attrs["NetworkSettings"]["Ports"]

        for container_port, host_info in port_info.items():
            if host_info:
                host_port = host_info[0]["HostPort"]
                ports[container_port] = f"localhost:{host_port}"

        return ports
