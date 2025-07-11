"""Production configuration validation."""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from coffeebreak.secrets import SecretManager
from coffeebreak.ssl import SSLManager
from coffeebreak.utils.errors import ValidationError

from .health import HealthChecker
from .security import SecurityValidator


class ProductionValidator:
    """Validates production deployment configuration and readiness."""

    def __init__(self, deployment_type: str = "docker", verbose: bool = False):
        """
        Initialize production validator.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose

        # Initialize sub-validators
        self.health_checker = HealthChecker(verbose=verbose)
        self.security_validator = SecurityValidator(verbose=verbose)
        self.ssl_manager = SSLManager(verbose=verbose)
        self.secret_manager = SecretManager(
            deployment_type=deployment_type, verbose=verbose
        )

    def validate_production_readiness(
        self, domain: str, config_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive production readiness validation.

        Args:
            domain: Production domain
            config_path: Optional configuration file path

        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            if self.verbose:
                print(f"Validating production readiness for {domain}")

            validation_result = {
                "domain": domain,
                "deployment_type": self.deployment_type,
                "timestamp": datetime.now().isoformat(),
                "overall_status": "pending",
                "ready_for_production": False,
                "critical_issues": [],
                "warnings": [],
                "passed_checks": [],
                "validation_details": {},
            }

            # 1. Configuration validation
            config_validation = self._validate_configuration(config_path)
            validation_result["validation_details"]["configuration"] = config_validation

            # 2. Security validation
            security_validation = (
                self.security_validator.validate_security_configuration(
                    domain, self.deployment_type
                )
            )
            validation_result["validation_details"]["security"] = security_validation

            # 3. SSL certificate validation
            ssl_validation = self._validate_ssl_certificates(domain)
            validation_result["validation_details"]["ssl"] = ssl_validation

            # 4. Secrets validation
            secrets_validation = self.secret_manager.validate_secrets_deployment()
            validation_result["validation_details"]["secrets"] = secrets_validation

            # 5. Infrastructure validation
            infrastructure_validation = self._validate_infrastructure()
            validation_result["validation_details"]["infrastructure"] = (
                infrastructure_validation
            )

            # 6. Service validation
            service_validation = self._validate_services()
            validation_result["validation_details"]["services"] = service_validation

            # 7. Health checks
            health_validation = self.health_checker.comprehensive_health_check(domain)
            validation_result["validation_details"]["health"] = health_validation

            # 8. Performance validation
            performance_validation = self._validate_performance()
            validation_result["validation_details"]["performance"] = (
                performance_validation
            )

            # 9. Backup validation
            backup_validation = self._validate_backup_system()
            validation_result["validation_details"]["backup"] = backup_validation

            # 10. Monitoring validation
            monitoring_validation = self._validate_monitoring()
            validation_result["validation_details"]["monitoring"] = (
                monitoring_validation
            )

            # Aggregate results
            self._aggregate_validation_results(validation_result)

            if self.verbose:
                status = validation_result["overall_status"]
                issues = len(validation_result["critical_issues"])
                warnings = len(validation_result["warnings"])
                print(
                    f"Validation completed: {status} "
                    f"({issues} critical, {warnings} warnings)"
                )

            return validation_result

        except Exception as e:
            raise ValidationError(f"Production validation failed: {e}") from e

    def _validate_configuration(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Validate configuration files."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            # Check for required configuration files
            required_configs = self._get_required_config_files()

            for config_file in required_configs:
                if os.path.exists(config_file):
                    validation["checks"].append(f"Found required config: {config_file}")

                    # Validate file content
                    if config_file.endswith(".yml") or config_file.endswith(".yaml"):
                        try:
                            with open(config_file) as f:
                                yaml.safe_load(f)
                            validation["checks"].append(
                                f"Valid YAML syntax: {config_file}"
                            )
                        except yaml.YAMLError as e:
                            validation["issues"].append(
                                f"Invalid YAML in {config_file}: {e}"
                            )
                else:
                    validation["issues"].append(
                        f"Missing required config file: {config_file}"
                    )

            # Check environment files
            env_files = self._get_required_env_files()
            for env_file in env_files:
                if os.path.exists(env_file):
                    validation["checks"].append(f"Found environment file: {env_file}")

                    # Check for required environment variables
                    required_vars = self._get_required_env_vars()
                    missing_vars = []

                    with open(env_file) as f:
                        content = f.read()
                        for var in required_vars:
                            if f"{var}=" not in content:
                                missing_vars.append(var)

                    if missing_vars:
                        validation["warnings"].append(
                            f"Missing env vars in {env_file}: {missing_vars}"
                        )
                    else:
                        validation["checks"].append(
                            f"All required env vars present in {env_file}"
                        )
                else:
                    validation["warnings"].append(
                        f"Environment file not found: {env_file}"
                    )

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Configuration validation error: {e}")

        return validation

    def _validate_ssl_certificates(self, domain: str) -> Dict[str, Any]:
        """Validate SSL certificates."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            # Find SSL certificate files
            cert_paths = self._find_ssl_certificates(domain)

            if not cert_paths:
                validation["issues"].append("No SSL certificates found")
                validation["status"] = "failed"
                return validation

            for cert_info in cert_paths:
                cert_path = cert_info["cert_path"]
                key_path = cert_info["key_path"]

                # Validate certificate
                ssl_validation = self.ssl_manager.validate_certificate(
                    cert_path=cert_path, key_path=key_path, domain=domain
                )

                if ssl_validation["valid"]:
                    validation["checks"].append(f"Valid SSL certificate: {cert_path}")

                    # Check expiration
                    if ssl_validation["expires_in_days"] is not None:
                        days = ssl_validation["expires_in_days"]
                        if days < 30:
                            validation["warnings"].append(
                                f"Certificate expires in {days} days"
                            )
                        else:
                            validation["checks"].append(
                                f"Certificate valid for {days} days"
                            )
                else:
                    for error in ssl_validation["errors"]:
                        validation["issues"].append(f"SSL validation error: {error}")

                for warning in ssl_validation["warnings"]:
                    validation["warnings"].append(f"SSL warning: {warning}")

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"SSL validation error: {e}")

        return validation

    def _validate_infrastructure(self) -> Dict[str, Any]:
        """Validate infrastructure components."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            if self.deployment_type == "docker":
                # Docker validation
                self._validate_docker_infrastructure(validation)
            else:
                # Standalone validation
                self._validate_standalone_infrastructure(validation)

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Infrastructure validation error: {e}")

        return validation

    def _validate_docker_infrastructure(self, validation: Dict[str, Any]) -> None:
        """Validate Docker infrastructure."""
        # Check Docker availability
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                validation["checks"].append(
                    f"Docker available: {result.stdout.strip()}"
                )
            else:
                validation["issues"].append("Docker is not available")
        except FileNotFoundError:
            validation["issues"].append("Docker is not installed")

        # Check Docker Compose
        try:
            result = subprocess.run(
                ["docker-compose", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                validation["checks"].append(
                    f"Docker Compose available: {result.stdout.strip()}"
                )
            else:
                validation["issues"].append("Docker Compose is not available")
        except FileNotFoundError:
            validation["issues"].append("Docker Compose is not installed")

        # Check Docker daemon
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, text=True)
            if result.returncode == 0:
                validation["checks"].append("Docker daemon is running")
            else:
                validation["issues"].append("Docker daemon is not running")
        except Exception as e:
            validation["issues"].append(f"Cannot connect to Docker daemon: {e}")

        # Check docker-compose.yml
        if os.path.exists("docker-compose.yml"):
            validation["checks"].append("Found docker-compose.yml")

            # Validate compose file
            try:
                result = subprocess.run(
                    ["docker-compose", "config"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    validation["checks"].append("Valid docker-compose.yml syntax")
                else:
                    validation["issues"].append(
                        f"Invalid docker-compose.yml: {result.stderr}"
                    )
            except Exception as e:
                validation["warnings"].append(
                    f"Could not validate docker-compose.yml: {e}"
                )
        else:
            validation["issues"].append("Missing docker-compose.yml")

    def _validate_standalone_infrastructure(self, validation: Dict[str, Any]) -> None:
        """Validate standalone infrastructure."""
        # Check system services
        required_services = [
            "postgresql",
            "mongod",
            "rabbitmq-server",
            "redis-server",
            "nginx",
        ]

        for service in required_services:
            try:
                result = subprocess.run(
                    ["systemctl", "is-enabled", service], capture_output=True, text=True
                )
                if result.returncode == 0:
                    validation["checks"].append(f"Service enabled: {service}")
                else:
                    validation["warnings"].append(f"Service not enabled: {service}")
            except Exception:
                validation["warnings"].append(f"Could not check service: {service}")

        # Check CoffeeBreak services
        coffeebreak_services = [
            "coffeebreak-api",
            "coffeebreak-frontend",
            "coffeebreak-events",
        ]
        for service in coffeebreak_services:
            service_file = f"/etc/systemd/system/{service}.service"
            if os.path.exists(service_file):
                validation["checks"].append(f"Found service file: {service}")
            else:
                validation["issues"].append(f"Missing service file: {service}")

        # Check directories
        required_dirs = [
            "/opt/coffeebreak",
            "/var/lib/coffeebreak",
            "/var/log/coffeebreak",
        ]

        for directory in required_dirs:
            if os.path.exists(directory):
                validation["checks"].append(f"Directory exists: {directory}")
            else:
                validation["issues"].append(f"Missing directory: {directory}")

    def _validate_services(self) -> Dict[str, Any]:
        """Validate service configuration and status."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            if self.deployment_type == "docker":
                # Check Docker services
                if os.path.exists("docker-compose.yml"):
                    try:
                        result = subprocess.run(
                            ["docker-compose", "ps"], capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split("\n")[
                                2:
                            ]  # Skip headers
                            running_services = 0
                            total_services = 0

                            for line in lines:
                                if line.strip():
                                    total_services += 1
                                    if "Up" in line:
                                        running_services += 1
                                    else:
                                        service_name = line.split()[0]
                                        validation["issues"].append(
                                            f"Service not running: {service_name}"
                                        )

                            if (
                                running_services == total_services
                                and total_services > 0
                            ):
                                validation["checks"].append(
                                    f"All {total_services} Docker services running"
                                )
                            elif total_services == 0:
                                validation["warnings"].append(
                                    "No Docker services found"
                                )
                        else:
                            validation["warnings"].append(
                                "Could not check Docker services status"
                            )
                    except Exception as e:
                        validation["warnings"].append(
                            f"Error checking Docker services: {e}"
                        )
            else:
                # Check systemd services
                services_to_check = [
                    "postgresql",
                    "mongod",
                    "rabbitmq-server",
                    "redis-server",
                    "nginx",
                    "coffeebreak-api",
                    "coffeebreak-frontend",
                    "coffeebreak-events",
                ]

                for service in services_to_check:
                    try:
                        result = subprocess.run(
                            ["systemctl", "is-active", service],
                            capture_output=True,
                            text=True,
                        )
                        if result.stdout.strip() == "active":
                            validation["checks"].append(f"Service active: {service}")
                        else:
                            validation["issues"].append(
                                f"Service not active: {service}"
                            )
                    except Exception:
                        validation["warnings"].append(
                            f"Could not check service: {service}"
                        )

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Service validation error: {e}")

        return validation

    def _validate_performance(self) -> Dict[str, Any]:
        """Validate performance configuration."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            # Check system resources
            import psutil

            # Memory check
            memory = psutil.virtual_memory()
            if memory.total < 2 * 1024 * 1024 * 1024:  # 2GB
                validation["warnings"].append(
                    f"Low memory: {memory.total // (1024**3)}GB (recommended: 2GB+)"
                )
            else:
                validation["checks"].append(
                    f"Adequate memory: {memory.total // (1024**3)}GB"
                )

            # Disk space check
            disk = psutil.disk_usage("/")
            free_space_gb = disk.free // (1024**3)
            if free_space_gb < 10:
                validation["warnings"].append(
                    f"Low disk space: {free_space_gb}GB (recommended: 10GB+)"
                )
            else:
                validation["checks"].append(f"Adequate disk space: {free_space_gb}GB")

            # CPU check
            cpu_count = psutil.cpu_count()
            if cpu_count < 2:
                validation["warnings"].append(
                    f"Low CPU count: {cpu_count} (recommended: 2+)"
                )
            else:
                validation["checks"].append(f"Adequate CPU count: {cpu_count}")

            validation["status"] = "passed"

        except ImportError:
            validation["warnings"].append(
                "psutil not available - skipping resource checks"
            )
            validation["status"] = "warning"
        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Performance validation error: {e}")

        return validation

    def _validate_backup_system(self) -> Dict[str, Any]:
        """Validate backup system configuration."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            # Check backup directories
            backup_dirs = ["/opt/coffeebreak/backups", "./backups"]
            backup_dir_found = False

            for backup_dir in backup_dirs:
                if os.path.exists(backup_dir):
                    validation["checks"].append(
                        f"Backup directory exists: {backup_dir}"
                    )
                    backup_dir_found = True
                    break

            if not backup_dir_found:
                validation["warnings"].append("No backup directory found")

            # Check backup scripts
            backup_scripts = ["/opt/coffeebreak/bin/backup.sh", "./backup.sh"]
            backup_script_found = False

            for script in backup_scripts:
                if os.path.exists(script):
                    validation["checks"].append(f"Backup script exists: {script}")
                    backup_script_found = True
                    break

            if not backup_script_found:
                validation["warnings"].append("No backup script found")

            # Check cron jobs
            try:
                result = subprocess.run(
                    ["crontab", "-l"], capture_output=True, text=True
                )
                if result.returncode == 0 and "backup" in result.stdout.lower():
                    validation["checks"].append("Backup cron job configured")
                else:
                    validation["warnings"].append("No backup cron job found")
            except Exception:
                validation["warnings"].append("Could not check cron jobs")

            validation["status"] = "passed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Backup validation error: {e}")

        return validation

    def _validate_monitoring(self) -> Dict[str, Any]:
        """Validate monitoring configuration."""
        validation = {"status": "pending", "issues": [], "warnings": [], "checks": []}

        try:
            # Check log directories
            log_dirs = ["/var/log/coffeebreak", "./logs"]
            log_dir_found = False

            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    validation["checks"].append(f"Log directory exists: {log_dir}")
                    log_dir_found = True
                    break

            if not log_dir_found:
                validation["warnings"].append("No log directory found")

            # Check logrotate configuration
            if os.path.exists("/etc/logrotate.d/coffeebreak"):
                validation["checks"].append("Logrotate configuration exists")
            else:
                validation["warnings"].append("No logrotate configuration found")

            # Check for monitoring tools
            monitoring_tools = ["prometheus", "grafana", "node_exporter"]
            for tool in monitoring_tools:
                try:
                    result = subprocess.run(["which", tool], capture_output=True)
                    if result.returncode == 0:
                        validation["checks"].append(
                            f"Monitoring tool available: {tool}"
                        )
                except Exception:
                    pass

            validation["status"] = "passed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Monitoring validation error: {e}")

        return validation

    def _aggregate_validation_results(self, validation_result: Dict[str, Any]) -> None:
        """Aggregate all validation results."""
        critical_issues = []
        warnings = []
        passed_checks = []

        for category, details in validation_result["validation_details"].items():
            if details["status"] == "failed" or details["status"] == "error":
                critical_issues.extend(
                    [f"{category}: {issue}" for issue in details["issues"]]
                )

            warnings.extend(
                [f"{category}: {warning}" for warning in details["warnings"]]
            )
            passed_checks.extend(
                [f"{category}: {check}" for check in details["checks"]]
            )

        validation_result["critical_issues"] = critical_issues
        validation_result["warnings"] = warnings
        validation_result["passed_checks"] = passed_checks

        # Determine overall status
        if critical_issues:
            validation_result["overall_status"] = "failed"
            validation_result["ready_for_production"] = False
        elif warnings:
            validation_result["overall_status"] = "warning"
            validation_result["ready_for_production"] = True  # Can deploy with warnings
        else:
            validation_result["overall_status"] = "passed"
            validation_result["ready_for_production"] = True

    def _get_required_config_files(self) -> List[str]:
        """Get list of required configuration files."""
        if self.deployment_type == "docker":
            return ["docker-compose.yml", ".env.api", ".env.frontend", ".env.events"]
        else:
            return [
                "/etc/systemd/system/coffeebreak-api.service",
                "/etc/systemd/system/coffeebreak-frontend.service",
                "/etc/systemd/system/coffeebreak-events.service",
            ]

    def _get_required_env_files(self) -> List[str]:
        """Get list of required environment files."""
        if self.deployment_type == "docker":
            return [".env.api", ".env.frontend", ".env.events"]
        else:
            return [
                "/opt/coffeebreak/config/.env.api",
                "/opt/coffeebreak/config/.env.frontend",
                "/opt/coffeebreak/config/.env.events",
            ]

    def _get_required_env_vars(self) -> List[str]:
        """Get list of required environment variables."""
        return [
            "NODE_ENV",
            "DATABASE_URL",
            "MONGODB_URL",
            "RABBITMQ_URL",
            "SESSION_SECRET",
            "API_SECRET_KEY",
        ]

    def _find_ssl_certificates(self, domain: str) -> List[Dict[str, str]]:
        """Find SSL certificate files."""
        cert_paths = []

        # Common certificate locations
        locations = [
            f"/etc/letsencrypt/live/{domain}",
            f"/etc/ssl/certs/{domain}",
            "/opt/coffeebreak/ssl",
            "./ssl/certs",
            "./ssl",
        ]

        for location in locations:
            cert_path = os.path.join(location, "fullchain.pem")
            key_path = os.path.join(location, "privkey.pem")

            if os.path.exists(cert_path) and os.path.exists(key_path):
                cert_paths.append(
                    {"cert_path": cert_path, "key_path": key_path, "location": location}
                )

        return cert_paths
