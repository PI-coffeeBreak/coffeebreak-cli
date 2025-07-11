"""Container health checking for CoffeeBreak CLI."""

import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    pass


class HealthChecker:
    """Checks health of Docker containers."""

    def __init__(self, timeout: int = 30, verbose: bool = False):
        """
        Initialize health checker.

        Args:
            timeout: Health check timeout in seconds
            verbose: Whether to enable verbose output
        """
        self.timeout = timeout
        self.verbose = verbose

    def check_container_health(self, container: Any) -> Dict[str, Any]:
        """
        Check health of a container.

        Args:
            container: Docker container object

        Returns:
            Dict[str, Any]: Health status information
        """
        # Check if container has built-in health check
        health_config = container.attrs.get("Config", {}).get("Healthcheck")
        if health_config:
            return self._check_builtin_health(container)

        # Use custom health checks based on container type
        image_name = container.image.tags[0] if container.image.tags else ""

        if "postgres" in image_name:
            return self._check_postgres_health(container)
        elif "mongo" in image_name:
            return self._check_mongo_health(container)
        elif "rabbitmq" in image_name:
            return self._check_rabbitmq_health(container)
        elif "keycloak" in image_name:
            return self._check_keycloak_health(container)
        else:
            return self._check_generic_health(container)

    def wait_for_healthy(self, container: Any, max_wait: int = 60) -> bool:
        """
        Wait for container to become healthy.

        Args:
            container: Docker container object
            max_wait: Maximum time to wait in seconds

        Returns:
            bool: True if container becomes healthy
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            health = self.check_container_health(container)

            if health["status"] == "healthy":
                return True
            elif health["status"] == "unhealthy":
                return False

            time.sleep(2)

        return False

    def _check_builtin_health(self, container: Any) -> Dict[str, Any]:
        """Check container's built-in health check."""
        try:
            # Reload container to get latest health status
            container.reload()

            health_status = container.attrs.get("State", {}).get("Health", {})
            status = health_status.get("Status", "unknown")

            # Map Docker health statuses
            status_mapping = {
                "healthy": "healthy",
                "unhealthy": "unhealthy",
                "starting": "starting",
                "none": "no_healthcheck",
            }

            return {
                "status": status_mapping.get(status, "unknown"),
                "method": "builtin",
                "details": health_status.get("Log", [])[-1]
                if health_status.get("Log")
                else None,
            }

        except Exception as e:
            return {"status": "error", "method": "builtin", "error": str(e)}

    def _check_postgres_health(self, container: Any) -> Dict[str, Any]:
        """Check PostgreSQL container health."""
        try:
            # Use pg_isready command
            exec_result = container.exec_run(["pg_isready", "-U", "postgres"])

            if exec_result.exit_code == 0:
                return {
                    "status": "healthy",
                    "method": "pg_isready",
                    "details": "PostgreSQL is ready for connections",
                }
            else:
                return {
                    "status": "unhealthy",
                    "method": "pg_isready",
                    "details": exec_result.output.decode("utf-8"),
                }

        except Exception as e:
            return {"status": "error", "method": "pg_isready", "error": str(e)}

    def _check_mongo_health(self, container: Any) -> Dict[str, Any]:
        """Check MongoDB container health."""
        try:
            # Use mongosh to ping
            exec_result = container.exec_run(
                ["mongosh", "--eval", 'db.runCommand("ping").ok', "--quiet"]
            )

            if exec_result.exit_code == 0 and b"1" in exec_result.output:
                return {
                    "status": "healthy",
                    "method": "mongosh_ping",
                    "details": "MongoDB is responding to ping",
                }
            else:
                return {
                    "status": "unhealthy",
                    "method": "mongosh_ping",
                    "details": exec_result.output.decode("utf-8"),
                }

        except Exception as e:
            return {"status": "error", "method": "mongosh_ping", "error": str(e)}

    def _check_rabbitmq_health(self, container: Any) -> Dict[str, Any]:
        """Check RabbitMQ container health."""
        try:
            # Use rabbitmq-diagnostics ping
            exec_result = container.exec_run(["rabbitmq-diagnostics", "ping"])

            if exec_result.exit_code == 0:
                return {
                    "status": "healthy",
                    "method": "rabbitmq_diagnostics",
                    "details": "RabbitMQ is responding to ping",
                }
            else:
                return {
                    "status": "unhealthy",
                    "method": "rabbitmq_diagnostics",
                    "details": exec_result.output.decode("utf-8"),
                }

        except Exception as e:
            return {
                "status": "error",
                "method": "rabbitmq_diagnostics",
                "error": str(e),
            }

    def _check_keycloak_health(self, container: Any) -> Dict[str, Any]:
        """Check Keycloak container health."""
        try:
            # Try to access health endpoint
            import requests

            # Get container port mapping for management interface (9000)
            ports = container.attrs["NetworkSettings"]["Ports"]
            port_info = ports.get("9000/tcp")

            if port_info and port_info[0]:
                host_port = port_info[0]["HostPort"]
                health_url = f"http://localhost:{host_port}/health"

                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "method": "http_health_check",
                        "details": "Keycloak health endpoint responding",
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "method": "http_health_check",
                        "details": f"Health endpoint returned {response.status_code}",
                    }
            else:
                return {
                    "status": "unknown",
                    "method": "http_health_check",
                    "details": "No port mapping found",
                }

        except Exception as e:
            return {"status": "error", "method": "http_health_check", "error": str(e)}

    def _check_generic_health(self, container: Any) -> Dict[str, Any]:
        """Generic health check for containers without specific checks."""
        try:
            # Simple check if container is running
            container.reload()

            if container.status == "running":
                # Try to execute a simple command
                exec_result = container.exec_run(["echo", "health_check"])

                if exec_result.exit_code == 0:
                    return {
                        "status": "healthy",
                        "method": "generic_exec",
                        "details": "Container is running and responsive",
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "method": "generic_exec",
                        "details": "Container not responding to commands",
                    }
            else:
                return {
                    "status": "unhealthy",
                    "method": "generic_status",
                    "details": f"Container status: {container.status}",
                }

        except Exception as e:
            return {"status": "error", "method": "generic_check", "error": str(e)}

    def get_health_summary(self, containers: List[Any]) -> Dict[str, Any]:
        """Get health summary for multiple containers."""
        summary = {
            "total_containers": len(containers),
            "healthy": 0,
            "unhealthy": 0,
            "starting": 0,
            "error": 0,
            "containers": {},
            "overall_status": "unknown",
            "timestamp": datetime.now().isoformat(),
        }

        for container in containers:
            try:
                health = self.check_container_health(container)
                container_name = container.name

                summary["containers"][container_name] = health

                # Count status types
                status = health["status"]
                if status == "healthy":
                    summary["healthy"] += 1
                elif status == "unhealthy":
                    summary["unhealthy"] += 1
                elif status == "starting":
                    summary["starting"] += 1
                else:
                    summary["error"] += 1

            except Exception as e:
                summary["containers"][f"unknown_{len(summary['containers'])}"] = {
                    "status": "error",
                    "error": str(e),
                }
                summary["error"] += 1

        # Determine overall status
        if summary["error"] > 0:
            summary["overall_status"] = "degraded"
        elif summary["unhealthy"] > 0:
            summary["overall_status"] = "unhealthy"
        elif summary["starting"] > 0:
            summary["overall_status"] = "starting"
        elif summary["healthy"] == summary["total_containers"]:
            summary["overall_status"] = "healthy"
        else:
            summary["overall_status"] = "unknown"

        return summary


class HealthMonitor:
    """Continuous health monitoring for containers."""

    def __init__(
        self,
        health_checker: HealthChecker,
        check_interval: int = 30,
        alert_threshold: int = 3,
        verbose: bool = False,
    ):
        """
        Initialize health monitor.

        Args:
            health_checker: HealthChecker instance
            check_interval: Seconds between health checks
            alert_threshold: Number of consecutive failures before alert
            verbose: Whether to enable verbose output
        """
        self.health_checker = health_checker
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        self.verbose = verbose

        self._monitoring = False
        self._monitor_thread = None
        self._containers = []
        self._failure_counts = {}
        self._alert_callbacks = []
        self._health_history = []
        self._max_history = 100

    def add_container(self, container: Any) -> None:
        """Add container to monitoring."""
        if container not in self._containers:
            self._containers.append(container)
            self._failure_counts[container.name] = 0

            if self.verbose:
                print(f"Added container '{container.name}' to monitoring")

    def remove_container(self, container: Any) -> None:
        """Remove container from monitoring."""
        if container in self._containers:
            self._containers.remove(container)
            self._failure_counts.pop(container.name, None)

            if self.verbose:
                print(f"Removed container '{container.name}' from monitoring")

    def add_alert_callback(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> None:
        """Add callback function to be called on health alerts."""
        self._alert_callbacks.append(callback)

    def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        if self.verbose:
            print(f"Started health monitoring with {len(self._containers)} containers")

    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        if self.verbose:
            print("Stopped health monitoring")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current health status of all monitored containers."""
        return self.health_checker.get_health_summary(self._containers)

    def get_health_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get health check history."""
        if limit:
            return self._health_history[-limit:]
        return self._health_history.copy()

    def get_failure_counts(self) -> Dict[str, int]:
        """Get current failure counts for all containers."""
        return self._failure_counts.copy()

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                if self._containers:
                    health_summary = self.health_checker.get_health_summary(
                        self._containers
                    )

                    # Store in history
                    self._health_history.append(health_summary)
                    if len(self._health_history) > self._max_history:
                        self._health_history.pop(0)

                    # Check for alerts
                    self._check_for_alerts(health_summary)

                    if self.verbose:
                        overall_status = health_summary["overall_status"]
                        healthy_count = health_summary["healthy"]
                        total_count = health_summary["total_containers"]
                        print(
                            f"Health check: {overall_status} ({healthy_count}/{total_count} healthy)"
                        )

                time.sleep(self.check_interval)

            except Exception as e:
                if self.verbose:
                    print(f"Error in health monitoring loop: {e}")
                time.sleep(self.check_interval)

    def _check_for_alerts(self, health_summary: Dict[str, Any]) -> None:
        """Check for alert conditions and trigger callbacks."""
        for container_name, health_info in health_summary["containers"].items():
            status = health_info["status"]

            if status in ["unhealthy", "error"]:
                self._failure_counts[container_name] = (
                    self._failure_counts.get(container_name, 0) + 1
                )

                # Trigger alert if threshold reached
                if self._failure_counts[container_name] >= self.alert_threshold:
                    self._trigger_alert(container_name, health_info)
                    # Reset counter after alerting
                    self._failure_counts[container_name] = 0
            else:
                # Reset failure count on success
                self._failure_counts[container_name] = 0

    def _trigger_alert(self, container_name: str, health_info: Dict[str, Any]) -> None:
        """Trigger alert callbacks."""
        alert_data = {
            "container_name": container_name,
            "health_info": health_info,
            "failure_count": self._failure_counts.get(container_name, 0),
            "timestamp": datetime.now().isoformat(),
            "alert_type": "health_failure",
        }

        for callback in self._alert_callbacks:
            try:
                callback(container_name, alert_data)
            except Exception as e:
                if self.verbose:
                    print(f"Error in alert callback: {e}")


class HealthReporter:
    """Generates health reports and status summaries."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def generate_status_report(self, health_summary: Dict[str, Any]) -> str:
        """Generate a formatted health status report."""
        report = []
        report.append("CoffeeBreak Container Health Report")
        report.append("=" * 40)
        report.append(f"Timestamp: {health_summary['timestamp']}")
        report.append(f"Overall Status: {health_summary['overall_status'].upper()}")
        report.append("")

        # Summary stats
        total = health_summary["total_containers"]
        healthy = health_summary["healthy"]
        unhealthy = health_summary["unhealthy"]
        starting = health_summary["starting"]
        error = health_summary["error"]

        report.append(f"Container Summary: {healthy}/{total} healthy")
        if unhealthy > 0:
            report.append(f"  Unhealthy: {unhealthy}")
        if starting > 0:
            report.append(f"  Starting: {starting}")
        if error > 0:
            report.append(f"  Errors: {error}")
        report.append("")

        # Individual container status
        report.append("Container Details:")
        for container_name, health_info in health_summary["containers"].items():
            status = health_info["status"]
            method = health_info.get("method", "unknown")

            status_icon = {
                "healthy": "OK",
                "unhealthy": "FAIL",
                "starting": "WAIT",
                "error": "ERR",
            }.get(status, "???")

            report.append(f"  [{status_icon}] {container_name}: {status} ({method})")

            if "details" in health_info:
                report.append(f"      Details: {health_info['details']}")
            elif "error" in health_info:
                report.append(f"      Error: {health_info['error']}")

        return "\n".join(report)

    def generate_failure_alert(
        self, container_name: str, alert_data: Dict[str, Any]
    ) -> str:
        """Generate a formatted failure alert message."""
        health_info = alert_data["health_info"]
        failure_count = alert_data["failure_count"]
        timestamp = alert_data["timestamp"]

        alert = []
        alert.append("HEALTH ALERT: Container Failure Detected")
        alert.append("=" * 45)
        alert.append(f"Container: {container_name}")
        alert.append(f"Status: {health_info['status']}")
        alert.append(f"Consecutive Failures: {failure_count}")
        alert.append(f"Timestamp: {timestamp}")
        alert.append("")

        if "details" in health_info:
            alert.append(f"Details: {health_info['details']}")
        if "error" in health_info:
            alert.append(f"Error: {health_info['error']}")

        alert.append("")
        alert.append("Recommended Actions:")
        alert.append("  1. Check container logs: coffeebreak deps logs")
        alert.append("  2. Restart the container if needed")
        alert.append("  3. Verify service configuration")

        return "\n".join(alert)
