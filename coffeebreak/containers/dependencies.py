"""Dependency container management for CoffeeBreak CLI."""

import time
from typing import Dict, List, Optional, Any
from .manager import ContainerManager, ContainerManagerError
from .health import HealthChecker, HealthMonitor, HealthReporter
from .compose import DockerComposeOrchestrator


class DependencyManagerError(Exception):
    """Raised when dependency management operations fail."""
    pass


class DependencyManager:
    """Manages dependency containers for CoffeeBreak development."""
    
    def __init__(self, config_manager, verbose: bool = False):
        """
        Initialize dependency manager.
        
        Args:
            config_manager: Configuration manager instance
            verbose: Whether to enable verbose output
        """
        self.config_manager = config_manager
        self.verbose = verbose
        self.container_manager = ContainerManager(verbose=verbose)
        self.health_checker = HealthChecker(verbose=verbose)
        self.health_monitor = HealthMonitor(self.health_checker, verbose=verbose)
        self.health_reporter = HealthReporter(verbose=verbose)
        self.compose_orchestrator = DockerComposeOrchestrator(verbose=verbose)
        self.network_name = "coffeebreak-deps"
        self.use_compose = True  # Prefer Docker Compose when available
        
        # Setup health monitoring alerts
        self.health_monitor.add_alert_callback(self._handle_health_alert)
    
    def start_profile(self, profile_name: str) -> bool:
        """
        Start dependency containers for a specific profile.
        
        Args:
            profile_name: Name of the dependency profile to start
            
        Returns:
            bool: True if all services started successfully
            
        Raises:
            DependencyManagerError: If profile start fails
        """
        try:
            # Get dependency configuration
            deps_config = self.config_manager.get_dependencies_config()
            
            # Check if Docker Compose is available and preferred
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                return self._start_profile_with_compose(deps_config, profile_name)
            else:
                return self._start_profile_with_docker_api(deps_config, profile_name)
                
        except Exception as e:
            raise DependencyManagerError(f"Failed to start profile '{profile_name}': {e}")
    
    def _start_profile_with_compose(self, deps_config: Dict[str, Any], profile_name: str) -> bool:
        """Start profile using Docker Compose orchestration."""
        try:
            if self.verbose:
                print(f"Starting profile '{profile_name}' using Docker Compose")
            
            # Generate compose file for profile
            compose_file = self.compose_orchestrator.generate_compose_file(
                deps_config, 
                profile=profile_name
            )
            
            # Start services
            return self.compose_orchestrator.start_services(detach=True)
            
        except Exception as e:
            if self.verbose:
                print(f"Docker Compose start failed: {e}")
            # Fallback to Docker API
            return self._start_profile_with_docker_api(deps_config, profile_name)
    
    def _start_profile_with_docker_api(self, deps_config: Dict[str, Any], profile_name: str) -> bool:
        """Start profile using Docker API (fallback method)."""
        try:
            if self.verbose:
                print(f"Starting profile '{profile_name}' using Docker API")
            
            # Get services for profile
            profiles = deps_config.get('profiles', {})
            if profile_name not in profiles:
                raise DependencyManagerError(f"Profile '{profile_name}' not found")
            
            services_list = profiles[profile_name]
            services_config = deps_config.get('services', {})
            
            if self.verbose:
                print(f"Starting dependency profile '{profile_name}' with {len(services_list)} services")
            
            # Create network
            self.container_manager.create_network(self.network_name)

            existing_containers = self.container_manager.list_containers()
            if self.verbose:
                print(f"Found {len(existing_containers)} existing containers: ")
                for c in existing_containers:
                    print(f"- {c['name']} (status: {c['status']}, image: {c['image']})")
            
            # Start services in order
            started_services = []
            for service_name in services_list:
                if service_name not in services_config:
                    raise DependencyManagerError(f"Service '{service_name}' not configured")

                container_name = services_config[service_name].get('container_name')

                # Check if service is already running (skip if so)
                if any(c['name'] == container_name for c in existing_containers):
                    if self.verbose:
                        print(f"Service '{service_name}' is already running, skipping...")
                    continue
                
                service_config = services_config[service_name].copy()
                service_config['network'] = self.network_name
                
                if self.verbose:
                    print(f"Starting service '{service_name}'...")
                
                # Start container
                container_id = self.container_manager.start_container(service_config)
                started_services.append(service_name)
                
                # Wait for health check
                if self.verbose:
                    print(f"Waiting for '{service_name}' to become healthy...")
                
                self._wait_for_service_health(service_config['container_name'])
            
            if self.verbose:
                print(f"✓ Successfully started {len(started_services)} dependency services")
            
            return True
            
        except ContainerManagerError as e:
            raise DependencyManagerError(f"Container operation failed: {e}")
        except Exception as e:
            raise DependencyManagerError(f"Unexpected error starting profile: {e}")
    
    def start_services(self, service_names: List[str]) -> bool:
        """
        Start specific dependency services.
        
        Args:
            service_names: List of service names to start
            
        Returns:
            bool: True if all services started successfully
        """
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            if self.verbose:
                print(f"Starting {len(service_names)} specific services")
            
            # Create network
            self.container_manager.create_network(self.network_name)
            
            # Start services
            for service_name in service_names:
                if service_name not in services_config:
                    raise DependencyManagerError(f"Service '{service_name}' not configured")
                
                service_config = services_config[service_name].copy()
                service_config['network'] = self.network_name
                
                if self.verbose:
                    print(f"Starting service '{service_name}'...")
                
                self.container_manager.start_container(service_config)
                self._wait_for_service_health(service_config['container_name'])
            
            if self.verbose:
                print(f"✓ Successfully started {len(service_names)} services")
            
            return True
            
        except Exception as e:
            raise DependencyManagerError(f"Error starting services: {e}")
    
    def stop_all_services(self) -> bool:
        """
        Stop all dependency services.
        
        Returns:
            bool: True if all services stopped successfully
        """
        try:
            # Stop health monitoring first
            self.stop_health_monitoring()
            
            # Try Docker Compose first
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                if self.verbose:
                    print("Stopping all dependency services using Docker Compose...")
                return self.compose_orchestrator.stop_services()
            else:
                # Fallback to Docker API
                return self._stop_all_services_with_docker_api()
                
        except Exception as e:
            raise DependencyManagerError(f"Error stopping services: {e}")
    
    def _stop_all_services_with_docker_api(self) -> bool:
        """Stop all services using Docker API (fallback method)."""
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            if self.verbose:
                print("Stopping all dependency services using Docker API...")
            
            # Stop all configured services
            for service_name, service_config in services_config.items():
                container_name = service_config.get('container_name')
                if container_name:
                    if self.verbose:
                        print(f"Stopping service '{service_name}'...")
                    self.container_manager.stop_container(container_name)
            
            if self.verbose:
                print("All dependency services stopped")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"Error stopping services with Docker API: {e}")
            return False
    
    def clean_all_services(self) -> bool:
        """
        Stop and remove all dependency containers and network.
        
        Returns:
            bool: True if cleanup successful
        """
        try:
            # Stop health monitoring first
            self.stop_health_monitoring()
            
            # Try Docker Compose cleanup first
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                if self.verbose:
                    print("Cleaning up all dependency services using Docker Compose...")
                return self.compose_orchestrator.cleanup(remove_volumes=True)
            else:
                # Fallback to Docker API cleanup
                return self._clean_all_services_with_docker_api()
                
        except Exception as e:
            raise DependencyManagerError(f"Error cleaning up services: {e}")
    
    def _clean_all_services_with_docker_api(self) -> bool:
        """Clean up all services using Docker API (fallback method)."""
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            if self.verbose:
                print("Cleaning up all dependency services using Docker API...")
            
            # Remove all configured containers
            for service_name, service_config in services_config.items():
                container_name = service_config.get('container_name')
                if container_name:
                    if self.verbose:
                        print(f"Removing container '{container_name}'...")
                    self.container_manager.remove_container(container_name, force=True)
            
            # Remove network
            self.container_manager.remove_network(self.network_name)
            
            if self.verbose:
                print("✓ Dependency cleanup completed")
            
            return True
            
        except Exception as e:
            raise DependencyManagerError(f"Error during cleanup: {e}")
    
    def get_services_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all dependency services.
        
        Returns:
            Dict[str, Dict[str, Any]]: Status of each service
        """
        status = {}
        
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            for service_name, service_config in services_config.items():
                container_name = service_config.get('container_name')
                if container_name:
                    status[service_name] = self.container_manager.get_container_status(container_name)
                else:
                    status[service_name] = {
                        'status': 'not_configured',
                        'error': 'No container name specified'
                    }
        
        except Exception as e:
            status['error'] = str(e)
        
        return status
    
    def get_service_logs(self, service_name: str, tail: int = 100) -> str:
        """
        Get logs for a specific service.
        
        Args:
            service_name: Name of the service
            tail: Number of lines to return
            
        Returns:
            str: Service logs
        """
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            if service_name not in services_config:
                return f"Service '{service_name}' not found"
            
            container_name = services_config[service_name].get('container_name')
            if not container_name:
                return f"No container name configured for service '{service_name}'"
            
            return self.container_manager.get_container_logs(container_name, tail)
            
        except Exception as e:
            return f"Error getting logs for service '{service_name}': {e}"
    
    def start_service(self, service_name: str) -> bool:
        """
        Start a specific service.
        
        Args:
            service_name: Name of the service to start
            
        Returns:
            bool: True if service started successfully
        """
        try:
            # Try Docker Compose first
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                if self.verbose:
                    print(f"Starting service '{service_name}' using Docker Compose...")
                return self.compose_orchestrator.restart_service(service_name)
            else:
                # Fallback to individual service start
                return self.start_services([service_name])
                
        except Exception as e:
            raise DependencyManagerError(f"Error starting service '{service_name}': {e}")
    
    def restart_service(self, service_name: str) -> bool:
        """
        Restart a specific service.
        
        Args:
            service_name: Name of the service to restart
            
        Returns:
            bool: True if service restarted successfully
        """
        try:
            # Try Docker Compose first
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                if self.verbose:
                    print(f"Restarting service '{service_name}' using Docker Compose...")
                return self.compose_orchestrator.restart_service(service_name)
            else:
                # Fallback to Docker API restart
                return self._restart_service_with_docker_api(service_name)
                
        except Exception as e:
            raise DependencyManagerError(f"Error restarting service '{service_name}': {e}")
    
    def _restart_service_with_docker_api(self, service_name: str) -> bool:
        """Restart service using Docker API (fallback method)."""
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            if service_name not in services_config:
                raise DependencyManagerError(f"Service '{service_name}' not configured")
            
            service_config = services_config[service_name]
            container_name = service_config.get('container_name')
            
            if not container_name:
                raise DependencyManagerError(f"No container name configured for service '{service_name}'")
            
            if self.verbose:
                print(f"Restarting container '{container_name}' using Docker API...")
            
            # Stop and start the container
            self.container_manager.stop_container(container_name)
            time.sleep(2)  # Give it a moment to stop
            
            service_config_copy = service_config.copy()
            service_config_copy['network'] = self.network_name
            self.container_manager.start_container(service_config_copy)
            
            # Wait for health check
            self._wait_for_service_health(container_name)
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"Error restarting service with Docker API: {e}")
            return False
    
    def get_running_containers(self) -> List[Dict[str, Any]]:
        """
        Get list of running dependency containers.
        
        Returns:
            List[Dict[str, Any]]: List of running containers with their info
        """
        try:
            # Try Docker Compose first
            if self.use_compose and self.compose_orchestrator.is_compose_available():
                compose_services = self.compose_orchestrator.get_service_status()
                
                containers = []
                for service in compose_services:
                    containers.append({
                        'name': service['name'],
                        'status': service['status'],
                        'image': service['image'],
                        'healthy': service['status'] == 'running',
                        'ports': service.get('ports', '')
                    })
                
                return containers
            else:
                # Fallback to Docker API
                return self._get_running_containers_with_docker_api()
                
        except Exception as e:
            if self.verbose:
                print(f"Error getting running containers: {e}")
            return []
    
    def _get_running_containers_with_docker_api(self) -> List[Dict[str, Any]]:
        """Get running containers using Docker API (fallback method)."""
        try:
            deps_config = self.config_manager.get_dependencies_config()
            services_config = deps_config.get('services', {})
            
            containers = []
            for service_name, service_config in services_config.items():
                container_name = service_config.get('container_name')
                if container_name:
                    status = self.container_manager.get_container_status(container_name)
                    if status.get('status') == 'running':
                        containers.append({
                            'name': service_name,
                            'container_name': container_name,
                            'status': status.get('status'),
                            'healthy': status.get('healthy', True),
                            'ports': status.get('ports', {})
                        })
            
            return containers
            
        except Exception as e:
            if self.verbose:
                print(f"Error getting containers with Docker API: {e}")
            return []
    
    def get_network_info(self) -> Dict[str, Any]:
        """
        Get network information for dependency containers.
        
        Returns:
            Dict[str, Any]: Network information
        """
        try:
            # Try to get network info from Docker
            network_info = {
                'name': self.network_name,
                'driver': 'bridge',
                'containers': []
            }
            
            # Get running containers and their network info
            containers = self.get_running_containers()
            for container in containers:
                network_info['containers'].append({
                    'name': container['name'],
                    'status': container['status']
                })
            
            return network_info
            
        except Exception as e:
            return {
                'name': self.network_name,
                'error': str(e),
                'containers': []
            }
    
    def check_all_services_healthy(self) -> bool:
        """
        Check if all running services are healthy.
        
        Returns:
            bool: True if all services are healthy
        """
        try:
            containers = self.get_running_containers()
            if not containers:
                return False
            
            for container in containers:
                if not container.get('healthy', False):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def start_health_monitoring(self) -> bool:
        """
        Start continuous health monitoring for all running containers.
        
        Returns:
            bool: True if monitoring started successfully
        """
        try:
            # Get all running containers
            running_containers = self.get_running_containers()
            
            if not running_containers:
                if self.verbose:
                    print("No running containers found to monitor")
                return False
            
            # Add containers to monitor
            for container_info in running_containers:
                try:
                    container = self.container_manager.client.containers.get(
                        container_info.get('container_name', container_info['name'])
                    )
                    self.health_monitor.add_container(container)
                except Exception as e:
                    if self.verbose:
                        print(f"Could not add container {container_info['name']} to monitoring: {e}")
            
            # Start monitoring
            self.health_monitor.start_monitoring()
            
            if self.verbose:
                print(f"Started health monitoring for {len(running_containers)} containers")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"Failed to start health monitoring: {e}")
            return False
    
    def stop_health_monitoring(self) -> None:
        """Stop health monitoring."""
        self.health_monitor.stop_monitoring()
        if self.verbose:
            print("Stopped health monitoring")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all services.
        
        Returns:
            Dict[str, Any]: Detailed health information
        """
        try:
            # Get current health status
            current_status = self.health_monitor.get_current_status()
            
            # Add additional monitoring info
            current_status['monitoring_active'] = self.health_monitor._monitoring
            current_status['failure_counts'] = self.health_monitor.get_failure_counts()
            
            return current_status
            
        except Exception as e:
            return {
                'error': str(e),
                'monitoring_active': False,
                'overall_status': 'error'
            }
    
    def get_health_report(self) -> str:
        """
        Generate a formatted health status report.
        
        Returns:
            str: Formatted health report
        """
        try:
            health_status = self.get_health_status()
            return self.health_reporter.generate_status_report(health_status)
        except Exception as e:
            return f"Error generating health report: {e}"
    
    def get_health_history(self, limit: Optional[int] = 10) -> List[Dict[str, Any]]:
        """
        Get recent health check history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List[Dict[str, Any]]: Health check history
        """
        return self.health_monitor.get_health_history(limit)
    
    def _handle_health_alert(self, container_name: str, alert_data: Dict[str, Any]) -> None:
        """Handle health alert from monitoring system."""
        try:
            if self.verbose:
                alert_message = self.health_reporter.generate_failure_alert(container_name, alert_data)
                print(f"\n{alert_message}\n")
            else:
                print(f"Health Alert: Container '{container_name}' has failed health checks")
                
        except Exception as e:
            print(f"Error handling health alert: {e}")
    
    def generate_connection_info(self) -> Dict[str, str]:
        """
        Generate connection information for running services.
        
        Returns:
            Dict[str, str]: Connection strings and URLs for services
        """
        connection_info = {}
        
        try:
            status = self.get_services_status()
            
            for service_name, service_status in status.items():
                if service_status.get('status') == 'running':
                    ports = service_status.get('ports', {})
                    
                    # Generate service-specific connection info
                    if service_name == 'database':
                        if '5432/tcp' in ports:
                            host_port = ports['5432/tcp'].replace('localhost:', '')
                            connection_info['DATABASE_URL'] = f"postgresql://coffeebreak:dev_password@localhost:{host_port}/coffeebreak_dev"
                    
                    elif service_name == 'mongodb':
                        if '27017/tcp' in ports:
                            host_port = ports['27017/tcp'].replace('localhost:', '')
                            connection_info['MONGODB_URI'] = f"mongodb://coffeebreak:dev_password@localhost:{host_port}/coffeebreak_dev"
                    
                    elif service_name == 'rabbitmq':
                        if '5672/tcp' in ports:
                            host_port = ports['5672/tcp'].replace('localhost:', '')
                            connection_info['RABBITMQ_URL'] = f"amqp://coffeebreak:dev_password@localhost:{host_port}/"
                        if '15672/tcp' in ports:
                            mgmt_port = ports['15672/tcp'].replace('localhost:', '')
                            connection_info['RABBITMQ_MANAGEMENT_URL'] = f"http://localhost:{mgmt_port}"
                    
                    elif service_name == 'keycloak':
                        if '8080/tcp' in ports:
                            host_port = ports['8080/tcp'].replace('localhost:', '')
                            connection_info['KEYCLOAK_URL'] = f"http://localhost:{host_port}"
        
        except Exception as e:
            connection_info['error'] = str(e)
        
        return connection_info
    
    def _wait_for_service_health(self, container_name: str, max_wait: int = 60) -> bool:
        """Wait for a service to become healthy."""
        try:
            container = self.container_manager.client.containers.get(container_name)
            return self.health_checker.wait_for_healthy(container, max_wait)
        except Exception:
            return False
