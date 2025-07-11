"""Health checking system for production deployments."""

import subprocess
import time
from datetime import datetime
from typing import Any, Dict

import requests

from coffeebreak.utils.errors import ValidationError


class HealthChecker:
    """Comprehensive health checking for production deployments."""

    def __init__(self, verbose: bool = False):
        """Initialize health checker."""
        self.verbose = verbose

    def comprehensive_health_check(
        self, domain: str, timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Args:
            domain: Domain to check
            timeout: Request timeout in seconds

        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            if self.verbose:
                print(f"Performing comprehensive health check for {domain}")

            health_result = {
                "domain": domain,
                "timestamp": datetime.now().isoformat(),
                "overall_status": "checking",
                "healthy": False,
                "response_time_ms": None,
                "checks": {},
            }

            # 1. HTTP/HTTPS connectivity
            http_check = self._check_http_connectivity(domain, timeout)
            health_result["checks"]["http"] = http_check

            # 2. SSL/TLS check
            ssl_check = self._check_ssl_health(domain, timeout)
            health_result["checks"]["ssl"] = ssl_check

            # 3. Application health endpoints
            app_health_check = self._check_application_health(domain, timeout)
            health_result["checks"]["application"] = app_health_check

            # 4. Database connectivity
            db_check = self._check_database_health()
            health_result["checks"]["database"] = db_check

            # 5. Service health
            service_check = self._check_service_health()
            health_result["checks"]["services"] = service_check

            # 6. Performance metrics
            performance_check = self._check_performance_metrics(domain, timeout)
            health_result["checks"]["performance"] = performance_check

            # 7. Security headers
            security_check = self._check_security_headers(domain, timeout)
            health_result["checks"]["security"] = security_check

            # Aggregate results
            self._aggregate_health_results(health_result)

            if self.verbose:
                status = health_result["overall_status"]
                print(f"Health check completed: {status}")

            return health_result

        except Exception as e:
            raise ValidationError(f"Health check failed: {e}") from e

    def _check_http_connectivity(self, domain: str, timeout: int) -> Dict[str, Any]:
        """Check HTTP/HTTPS connectivity."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            # Test HTTPS first
            start_time = time.time()

            try:
                response = requests.get(
                    f"https://{domain}",
                    timeout=timeout,
                    verify=True,
                    allow_redirects=True,
                )

                response_time = (time.time() - start_time) * 1000
                check_result["metrics"]["response_time_ms"] = response_time
                check_result["details"]["status_code"] = response.status_code
                check_result["details"]["content_length"] = len(response.content)
                check_result["details"]["headers"] = dict(response.headers)

                if response.status_code == 200:
                    check_result["status"] = "healthy"
                    check_result["details"]["message"] = "HTTPS connectivity successful"
                elif response.status_code in [301, 302, 307, 308]:
                    check_result["status"] = "healthy"
                    check_result["details"]["message"] = (
                        f"HTTPS redirect: {response.status_code}"
                    )
                else:
                    check_result["status"] = "unhealthy"
                    check_result["issues"].append(
                        f"HTTP {response.status_code} response"
                    )

            except requests.exceptions.SSLError as e:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(f"SSL error: {e}")

                # Try HTTP as fallback
                try:
                    response = requests.get(f"http://{domain}", timeout=timeout)
                    if response.status_code == 200:
                        check_result["details"]["fallback"] = (
                            "HTTP accessible but SSL issues"
                        )
                except Exception:
                    check_result["issues"].append("HTTP also inaccessible")

            except requests.exceptions.ConnectionError as e:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(f"Connection error: {e}")

            except requests.exceptions.Timeout as e:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(f"Request timeout: {e}")

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"HTTP check error: {e}")

        return check_result

    def _check_ssl_health(self, domain: str, timeout: int) -> Dict[str, Any]:
        """Check SSL/TLS health."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            import socket
            import ssl

            # Create SSL context
            context = ssl.create_default_context()

            # Connect and get certificate info
            with socket.create_connection((domain, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()

                    check_result["details"]["certificate"] = {
                        "subject": dict(x[0] for x in cert["subject"]),
                        "issuer": dict(x[0] for x in cert["issuer"]),
                        "version": cert["version"],
                        "serial_number": cert["serialNumber"],
                        "not_before": cert["notBefore"],
                        "not_after": cert["notAfter"],
                    }

                    # Check certificate validity
                    import datetime

                    not_after = datetime.datetime.strptime(
                        cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                    )
                    days_until_expiry = (not_after - datetime.datetime.now()).days

                    check_result["metrics"]["days_until_expiry"] = days_until_expiry

                    if days_until_expiry > 30:
                        check_result["status"] = "healthy"
                        check_result["details"]["message"] = (
                            f"SSL certificate valid for {days_until_expiry} days"
                        )
                    elif days_until_expiry > 0:
                        check_result["status"] = "warning"
                        check_result["issues"].append(
                            f"SSL certificate expires in {days_until_expiry} days"
                        )
                    else:
                        check_result["status"] = "unhealthy"
                        check_result["issues"].append("SSL certificate has expired")

                    # Check cipher suite
                    cipher = ssock.cipher()
                    if cipher:
                        check_result["details"]["cipher_suite"] = {
                            "name": cipher[0],
                            "protocol": cipher[1],
                            "bits": cipher[2],
                        }

        except socket.timeout:
            check_result["status"] = "unhealthy"
            check_result["issues"].append("SSL connection timeout")
        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"SSL check error: {e}")

        return check_result

    def _check_application_health(self, domain: str, timeout: int) -> Dict[str, Any]:
        """Check application-specific health endpoints."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            # Standard health endpoints to check
            health_endpoints = [
                "/health",
                "/api/health",
                "/healthz",
                "/status",
                "/ping",
            ]

            successful_endpoints = []

            for endpoint in health_endpoints:
                try:
                    start_time = time.time()
                    response = requests.get(
                        f"https://{domain}{endpoint}",
                        timeout=timeout,
                        verify=False,  # SSL already checked separately
                    )
                    response_time = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        successful_endpoints.append(
                            {
                                "endpoint": endpoint,
                                "response_time_ms": response_time,
                                "status_code": response.status_code,
                            }
                        )

                        # Try to parse JSON response for additional info
                        try:
                            health_data = response.json()
                            successful_endpoints[-1]["health_data"] = health_data
                        except (ValueError, KeyError):
                            successful_endpoints[-1]["content"] = response.text[:200]

                except requests.exceptions.RequestException:
                    continue  # Try next endpoint

            if successful_endpoints:
                check_result["status"] = "healthy"
                check_result["details"]["endpoints"] = successful_endpoints
                check_result["details"]["message"] = (
                    f"Found {len(successful_endpoints)} health endpoints"
                )
            else:
                check_result["status"] = "warning"
                check_result["issues"].append("No standard health endpoints responding")

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"Application health check error: {e}")

        return check_result

    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and health."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            database_checks = {}

            # PostgreSQL check
            try:
                result = subprocess.run(
                    ["pg_isready", "-h", "localhost", "-p", "5432"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    database_checks["postgresql"] = {
                        "status": "healthy",
                        "message": "PostgreSQL accepting connections",
                    }
                else:
                    database_checks["postgresql"] = {
                        "status": "unhealthy",
                        "message": f"PostgreSQL not ready: {result.stderr}",
                    }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                database_checks["postgresql"] = {
                    "status": "unknown",
                    "message": "Cannot check PostgreSQL (pg_isready not available)",
                }

            # MongoDB check
            try:
                result = subprocess.run(
                    ["mongo", "--eval", 'db.adminCommand("ismaster")', "--quiet"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    database_checks["mongodb"] = {
                        "status": "healthy",
                        "message": "MongoDB responding",
                    }
                else:
                    database_checks["mongodb"] = {
                        "status": "unhealthy",
                        "message": f"MongoDB not responding: {result.stderr}",
                    }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                database_checks["mongodb"] = {
                    "status": "unknown",
                    "message": "Cannot check MongoDB (mongo client not available)",
                }

            # Redis check
            try:
                result = subprocess.run(
                    ["redis-cli", "ping"], capture_output=True, text=True, timeout=10
                )

                if result.returncode == 0 and "PONG" in result.stdout:
                    database_checks["redis"] = {
                        "status": "healthy",
                        "message": "Redis responding",
                    }
                else:
                    database_checks["redis"] = {
                        "status": "unhealthy",
                        "message": f"Redis not responding: {result.stderr}",
                    }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                database_checks["redis"] = {
                    "status": "unknown",
                    "message": "Cannot check Redis (redis-cli not available)",
                }

            check_result["details"]["databases"] = database_checks

            # Determine overall database health
            healthy_dbs = sum(
                1 for db in database_checks.values() if db["status"] == "healthy"
            )
            unhealthy_dbs = sum(
                1 for db in database_checks.values() if db["status"] == "unhealthy"
            )

            if unhealthy_dbs > 0:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(f"{unhealthy_dbs} database(s) unhealthy")
            elif healthy_dbs > 0:
                check_result["status"] = "healthy"
                check_result["details"]["message"] = (
                    f"{healthy_dbs} database(s) healthy"
                )
            else:
                check_result["status"] = "warning"
                check_result["issues"].append("Cannot verify database health")

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"Database health check error: {e}")

        return check_result

    def _check_service_health(self) -> Dict[str, Any]:
        """Check system service health."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            services_to_check = [
                "nginx",
                "postgresql",
                "mongod",
                "rabbitmq-server",
                "redis-server",
                "coffeebreak-api",
                "coffeebreak-frontend",
                "coffeebreak-events",
            ]

            service_statuses = {}

            for service in services_to_check:
                try:
                    result = subprocess.run(
                        ["systemctl", "is-active", service],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    status = result.stdout.strip()
                    service_statuses[service] = {
                        "status": status,
                        "healthy": status == "active",
                    }

                    # Get additional service info
                    try:
                        status_result = subprocess.run(
                            ["systemctl", "status", service, "--no-pager", "-l"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        # Extract key information
                        lines = status_result.stdout.split("\n")
                        for line in lines:
                            if "Active:" in line:
                                service_statuses[service]["active_info"] = line.strip()
                            elif "Main PID:" in line:
                                service_statuses[service]["pid_info"] = line.strip()
                    except Exception:
                        pass  # Additional info is optional

                except Exception as e:
                    service_statuses[service] = {
                        "status": "unknown",
                        "healthy": False,
                        "error": str(e),
                    }

            check_result["details"]["services"] = service_statuses

            # Determine overall service health
            total_services = len(service_statuses)
            healthy_services = sum(1 for s in service_statuses.values() if s["healthy"])
            unhealthy_services = total_services - healthy_services

            if unhealthy_services == 0:
                check_result["status"] = "healthy"
                check_result["details"]["message"] = (
                    f"All {total_services} services healthy"
                )
            elif unhealthy_services <= 2:
                check_result["status"] = "warning"
                check_result["issues"].append(
                    f"{unhealthy_services} service(s) unhealthy"
                )
            else:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(
                    f"{unhealthy_services} service(s) unhealthy"
                )

            check_result["metrics"]["healthy_services"] = healthy_services
            check_result["metrics"]["total_services"] = total_services

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"Service health check error: {e}")

        return check_result

    def _check_performance_metrics(self, domain: str, timeout: int) -> Dict[str, Any]:
        """Check performance metrics."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            # Response time test
            response_times = []

            for _ in range(3):  # Test 3 times
                try:
                    start_time = time.time()
                    requests.get(
                        f"https://{domain}", timeout=timeout, verify=False
                    )
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)
                except Exception:
                    continue

            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                check_result["metrics"]["avg_response_time_ms"] = avg_response_time
                check_result["metrics"]["response_times"] = response_times

                if avg_response_time < 1000:  # Under 1 second
                    check_result["status"] = "healthy"
                    check_result["details"]["message"] = (
                        f"Good response time: {avg_response_time:.0f}ms"
                    )
                elif avg_response_time < 3000:  # Under 3 seconds
                    check_result["status"] = "warning"
                    check_result["issues"].append(
                        f"Slow response time: {avg_response_time:.0f}ms"
                    )
                else:
                    check_result["status"] = "unhealthy"
                    check_result["issues"].append(
                        f"Very slow response time: {avg_response_time:.0f}ms"
                    )
            else:
                check_result["status"] = "unhealthy"
                check_result["issues"].append("Could not measure response time")

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"Performance check error: {e}")

        return check_result

    def _check_security_headers(self, domain: str, timeout: int) -> Dict[str, Any]:
        """Check security headers."""
        check_result = {
            "status": "checking",
            "details": {},
            "issues": [],
            "metrics": {},
        }

        try:
            response = requests.get(f"https://{domain}", timeout=timeout, verify=False)

            headers = response.headers
            security_headers = {
                "Strict-Transport-Security": "HSTS",
                "X-Content-Type-Options": "Content Type Options",
                "X-Frame-Options": "Frame Options",
                "X-XSS-Protection": "XSS Protection",
                "Content-Security-Policy": "CSP",
                "Referrer-Policy": "Referrer Policy",
            }

            present_headers = {}
            missing_headers = []

            for header, description in security_headers.items():
                if header in headers:
                    present_headers[header] = headers[header]
                else:
                    missing_headers.append(description)

            check_result["details"]["present_headers"] = present_headers
            check_result["details"]["missing_headers"] = missing_headers

            # Determine security status
            header_score = len(present_headers) / len(security_headers)

            if header_score >= 0.8:  # 80% or more headers present
                check_result["status"] = "healthy"
                check_result["details"]["message"] = (
                    f"Good security headers: {len(present_headers)}/"
                    f"{len(security_headers)}"
                )
            elif header_score >= 0.5:  # 50% or more headers present
                check_result["status"] = "warning"
                check_result["issues"].append(
                    f"Some security headers missing: {len(missing_headers)}"
                )
            else:
                check_result["status"] = "unhealthy"
                check_result["issues"].append(
                    f"Many security headers missing: {len(missing_headers)}"
                )

            check_result["metrics"]["security_score"] = header_score

        except Exception as e:
            check_result["status"] = "error"
            check_result["issues"].append(f"Security headers check error: {e}")

        return check_result

    def _aggregate_health_results(self, health_result: Dict[str, Any]) -> None:
        """Aggregate all health check results."""
        all_checks = health_result["checks"].values()

        # Count status types
        warning_count = sum(1 for check in all_checks if check["status"] == "warning")
        unhealthy_count = sum(
            1 for check in all_checks if check["status"] == "unhealthy"
        )
        error_count = sum(1 for check in all_checks if check["status"] == "error")

        # Determine overall status
        if error_count > 0 or unhealthy_count > 0:
            health_result["overall_status"] = "unhealthy"
            health_result["healthy"] = False
        elif warning_count > 0:
            health_result["overall_status"] = "warning"
            health_result["healthy"] = True  # Operational with warnings
        else:
            health_result["overall_status"] = "healthy"
            health_result["healthy"] = True

        # Calculate average response time if available
        response_times = []
        for check in all_checks:
            if "metrics" in check and "response_time_ms" in check["metrics"]:
                response_times.append(check["metrics"]["response_time_ms"])

        if response_times:
            health_result["response_time_ms"] = sum(response_times) / len(
                response_times
            )
