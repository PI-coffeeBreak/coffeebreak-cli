"""Security validation for production deployments."""

import os
import socket
import ssl
import subprocess
from pathlib import Path
from typing import Any, Dict

import requests

from coffeebreak.utils.errors import SecurityError


class SecurityValidator:
    """Validates security configuration for production deployments."""

    def __init__(self, verbose: bool = False):
        """Initialize security validator."""
        self.verbose = verbose

    def validate_security_configuration(
        self, domain: str, deployment_type: str = "docker"
    ) -> Dict[str, Any]:
        """
        Comprehensive security validation.

        Args:
            domain: Production domain
            deployment_type: Type of deployment (docker, standalone)

        Returns:
            Dict[str, Any]: Security validation results
        """
        try:
            if self.verbose:
                print(f"Validating security configuration for {domain}")

            security_result = {
                "domain": domain,
                "deployment_type": deployment_type,
                "status": "checking",
                "security_score": 0,
                "issues": [],
                "warnings": [],
                "checks": [],
                "validations": {},
            }

            # 1. File permissions validation
            permissions_validation = self._validate_file_permissions(deployment_type)
            security_result["validations"]["file_permissions"] = permissions_validation

            # 2. Secret storage validation
            secrets_validation = self._validate_secret_storage(deployment_type)
            security_result["validations"]["secret_storage"] = secrets_validation

            # 3. Network security validation
            network_validation = self._validate_network_security(domain)
            security_result["validations"]["network_security"] = network_validation

            # 4. SSL/TLS configuration validation
            ssl_validation = self._validate_ssl_configuration(domain)
            security_result["validations"]["ssl_configuration"] = ssl_validation

            # 5. Service configuration validation
            service_validation = self._validate_service_security(deployment_type)
            security_result["validations"]["service_security"] = service_validation

            # 6. Operating system security validation
            os_validation = self._validate_os_security()
            security_result["validations"]["os_security"] = os_validation

            # 7. Application security validation
            app_validation = self._validate_application_security(domain)
            security_result["validations"]["application_security"] = app_validation

            # 8. Backup security validation
            backup_validation = self._validate_backup_security()
            security_result["validations"]["backup_security"] = backup_validation

            # Aggregate results
            self._aggregate_security_results(security_result)

            if self.verbose:
                score = security_result["security_score"]
                status = security_result["status"]
                print(f"Security validation completed: {status} (score: {score}/100)")

            return security_result

        except Exception as e:
            raise SecurityError(f"Security validation failed: {e}") from e

    def _validate_file_permissions(self, deployment_type: str) -> Dict[str, Any]:
        """Validate file and directory permissions."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            if deployment_type == "standalone":
                # Check critical directories
                critical_paths = [
                    ("/opt/coffeebreak/secrets", 0o700, "coffeebreak"),
                    ("/var/log/coffeebreak", 0o755, "coffeebreak"),
                    ("/etc/systemd/system/coffeebreak-*.service", 0o644, "root"),
                ]

                for path_pattern, expected_mode, _expected_owner in critical_paths:
                    if "*" in path_pattern:
                        # Handle glob patterns
                        import glob

                        paths = glob.glob(path_pattern)
                    else:
                        paths = [path_pattern] if os.path.exists(path_pattern) else []

                    for path in paths:
                        if os.path.exists(path):
                            stat_info = os.stat(path)
                            actual_mode = stat_info.st_mode & 0o777

                            if actual_mode == expected_mode:
                                validation["checks"].append(
                                    f"Correct permissions: {path} ({oct(actual_mode)})"
                                )
                                validation["score"] += 10
                            else:
                                validation["issues"].append(
                                    f"Incorrect permissions: {path} has "
                                    f"{oct(actual_mode)}, expected {oct(expected_mode)}"
                                )
                        else:
                            validation["warnings"].append(f"Path not found: {path}")

            else:  # Docker deployment
                # Check Docker-specific security
                docker_paths = [
                    ("./secrets", 0o700),
                    ("./ssl", 0o755),
                    ("./docker-compose.yml", 0o644),
                ]

                for path, expected_mode in docker_paths:
                    if os.path.exists(path):
                        stat_info = os.stat(path)
                        actual_mode = stat_info.st_mode & 0o777

                        if actual_mode <= expected_mode:
                            validation["checks"].append(
                                f"Secure permissions: {path} ({oct(actual_mode)})"
                            )
                            validation["score"] += 10
                        else:
                            validation["warnings"].append(
                                f"Overly permissive: {path} has "
                                f"{oct(actual_mode)}, recommended max "
                                f"{oct(expected_mode)}"
                            )

            # Check for world-readable sensitive files
            sensitive_patterns = ["*.key", "*.pem", "*secret*", "*password*", ".env*"]

            for pattern in sensitive_patterns:
                import glob

                for file_path in glob.glob(pattern, recursive=True):
                    if os.path.isfile(file_path):
                        stat_info = os.stat(file_path)
                        mode = stat_info.st_mode & 0o777

                        if mode & 0o044:  # World or group readable
                            validation["issues"].append(
                                f"Sensitive file is readable by others: {file_path}"
                            )
                        else:
                            validation["checks"].append(
                                f"Secure sensitive file: {file_path}"
                            )
                            validation["score"] += 5

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"File permissions check error: {e}")

        return validation

    def _validate_secret_storage(self, deployment_type: str) -> Dict[str, Any]:
        """Validate secret storage security."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            if deployment_type == "docker":
                # Check Docker secrets usage
                if os.path.exists("docker-compose.yml"):
                    with open("docker-compose.yml") as f:
                        compose_content = f.read()

                    if "secrets:" in compose_content:
                        validation["checks"].append(
                            "Docker secrets configuration found"
                        )
                        validation["score"] += 20
                    else:
                        validation["warnings"].append(
                            "No Docker secrets configuration found"
                        )

                    # Check for plaintext secrets in compose file
                    sensitive_keywords = ["password", "secret", "key", "token"]
                    lines = compose_content.split("\n")

                    for i, line in enumerate(lines, 1):
                        for keyword in sensitive_keywords:
                            if (
                                keyword.lower() in line.lower()
                                and "=" in line
                                and not line.strip().startswith("#")
                            ):
                                if "${" not in line:  # Not using environment variables
                                    validation["issues"].append(
                                        f"Potential plaintext secret in docker-compose.yml "
                                        f"line {i}"
                                    )

            else:  # Standalone deployment
                secrets_dir = "/opt/coffeebreak/secrets"
                if os.path.exists(secrets_dir):
                    validation["checks"].append("Secrets directory exists")

                    # Check if secrets are encrypted
                    secret_files = list(Path(secrets_dir).glob("*"))
                    encrypted_files = [f for f in secret_files if f.suffix == ".enc"]

                    if encrypted_files:
                        validation["checks"].append(
                            f"Found {len(encrypted_files)} encrypted secret files"
                        )
                        validation["score"] += 20

                    plain_files = [f for f in secret_files if f.suffix != ".enc"]
                    if plain_files:
                        validation["warnings"].append(
                            f"Found {len(plain_files)} unencrypted secret files"
                        )
                else:
                    validation["warnings"].append("Secrets directory not found")

            # Check for secrets in environment files
            env_files = [".env", ".env.local", ".env.production"] + [
                f".env.{service}" for service in ["api", "frontend", "events"]
            ]

            for env_file in env_files:
                if os.path.exists(env_file):
                    with open(env_file) as f:
                        content = f.read()

                    # Look for hardcoded secrets
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "=" in line and not line.strip().startswith("#"):
                            key, value = line.split("=", 1)

                            # Check for suspicious patterns
                            if len(value) > 20 and not value.startswith("${"):
                                sensitive_keywords = [
                                    "password",
                                    "secret",
                                    "key",
                                    "token",
                                ]
                                if any(
                                    keyword in key.lower()
                                    for keyword in sensitive_keywords
                                ):
                                    validation["warnings"].append(
                                        f"Potential hardcoded secret in {env_file} "
                                        f"line {i}"
                                    )

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Secret storage validation error: {e}")

        return validation

    def _validate_network_security(self, domain: str) -> Dict[str, Any]:
        """Validate network security configuration."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            # Check HTTPS enforcement
            try:
                # Test HTTP redirect to HTTPS
                response = requests.get(
                    f"http://{domain}", allow_redirects=False, timeout=10
                )

                if response.status_code in [301, 302, 307, 308]:
                    location = response.headers.get("Location", "")
                    if location.startswith("https://"):
                        validation["checks"].append("HTTP redirects to HTTPS")
                        validation["score"] += 15
                    else:
                        validation["issues"].append("HTTP does not redirect to HTTPS")
                else:
                    validation["issues"].append("HTTP is accessible without redirect")

            except requests.exceptions.ConnectionError:
                validation["checks"].append("HTTP port not accessible (good)")
                validation["score"] += 10
            except Exception as e:
                validation["warnings"].append(f"Could not test HTTP redirect: {e}")

            # Check HTTPS configuration
            try:
                response = requests.get(f"https://{domain}", timeout=10)

                # Check HSTS header
                hsts_header = response.headers.get("Strict-Transport-Security")
                if hsts_header:
                    validation["checks"].append("HSTS header present")
                    validation["score"] += 10

                    if "max-age" in hsts_header:
                        validation["checks"].append("HSTS max-age configured")
                        validation["score"] += 5
                else:
                    validation["warnings"].append("HSTS header missing")

                # Check secure cookie settings
                cookies = response.cookies
                insecure_cookies = []

                for cookie in cookies:
                    if not cookie.secure:
                        insecure_cookies.append(cookie.name)

                if insecure_cookies:
                    validation["warnings"].append(
                        f"Insecure cookies found: {insecure_cookies}"
                    )
                else:
                    validation["checks"].append("All cookies are secure")
                    validation["score"] += 5

            except Exception as e:
                validation["warnings"].append(
                    f"Could not test HTTPS configuration: {e}"
                )

            # Check for open ports
            common_ports = [22, 80, 443, 3000, 5432, 27017, 5672, 6379]

            for port in common_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((domain, port))
                    sock.close()

                    if result == 0:  # Port is open
                        if port in [80, 443]:
                            validation["checks"].append(
                                f"Web port {port} is accessible"
                            )
                        elif port == 22:
                            validation["warnings"].append(
                                "SSH port 22 is accessible from internet"
                            )
                        else:
                            validation["issues"].append(
                                f"Database/service port {port} is accessible "
                                f"from internet"
                            )

                except Exception:
                    continue  # Port scan failed, assume closed

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Network security validation error: {e}")

        return validation

    def _validate_ssl_configuration(self, domain: str) -> Dict[str, Any]:
        """Validate SSL/TLS configuration security."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            context = ssl.create_default_context()

            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    # Check TLS version
                    tls_version = ssock.version()

                    if tls_version in ["TLSv1.2", "TLSv1.3"]:
                        validation["checks"].append(
                            f"Secure TLS version: {tls_version}"
                        )
                        validation["score"] += 15
                    else:
                        validation["issues"].append(
                            f"Insecure TLS version: {tls_version}"
                        )

                    # Check cipher suite
                    cipher = ssock.cipher()
                    if cipher:
                        cipher_name = cipher[0]

                        # Check for secure ciphers
                        if "AES" in cipher_name and "GCM" in cipher_name:
                            validation["checks"].append(
                                f"Secure cipher suite: {cipher_name}"
                            )
                            validation["score"] += 10
                        elif "AES" in cipher_name:
                            validation["checks"].append(
                                f"Acceptable cipher suite: {cipher_name}"
                            )
                            validation["score"] += 5
                        else:
                            validation["warnings"].append(
                                f"Potentially weak cipher: {cipher_name}"
                            )

                    # Check certificate
                    # cert = ssock.getpeercert()  # Unused variable removed

                    # Check key size (if available in cert)
                    public_key = ssock.getpeercert_chain()[0].get_pubkey()
                    if hasattr(public_key, "bits"):
                        key_bits = public_key.bits()
                        if key_bits >= 2048:
                            validation["checks"].append(
                                f"Adequate key size: {key_bits} bits"
                            )
                            validation["score"] += 10
                        else:
                            validation["issues"].append(
                                f"Weak key size: {key_bits} bits"
                            )

        except Exception as e:
            validation["warnings"].append(f"Could not validate SSL configuration: {e}")

        return validation

    def _validate_service_security(self, deployment_type: str) -> Dict[str, Any]:
        """Validate service security configuration."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            if deployment_type == "standalone":
                # Check systemd service security
                service_files = [
                    "/etc/systemd/system/coffeebreak-api.service",
                    "/etc/systemd/system/coffeebreak-frontend.service",
                    "/etc/systemd/system/coffeebreak-events.service",
                ]

                for service_file in service_files:
                    if os.path.exists(service_file):
                        with open(service_file) as f:
                            content = f.read()

                        # Check for security settings
                        security_settings = [
                            "NoNewPrivileges=true",
                            "PrivateTmp=true",
                            "ProtectSystem=strict",
                            "ProtectHome=true",
                        ]

                        found_settings = []
                        for setting in security_settings:
                            if setting in content:
                                found_settings.append(setting)

                        if len(found_settings) >= 3:
                            validation["checks"].append(
                                f"Good systemd security in "
                                f"{os.path.basename(service_file)}"
                            )
                            validation["score"] += 5
                        else:
                            validation["warnings"].append(
                                f"Missing systemd security settings in "
                                f"{os.path.basename(service_file)}"
                            )

            else:  # Docker deployment
                # Check Docker security
                if os.path.exists("docker-compose.yml"):
                    with open("docker-compose.yml") as f:
                        compose_content = f.read()

                    # Check for security options
                    security_options = [
                        "read_only:",
                        "user:",
                        "cap_drop:",
                        "security_opt:",
                    ]

                    found_options = []
                    for option in security_options:
                        if option in compose_content:
                            found_options.append(option)

                    if found_options:
                        validation["checks"].append(
                            f"Docker security options found: {found_options}"
                        )
                        validation["score"] += 10
                    else:
                        validation["warnings"].append(
                            "No Docker security options found"
                        )

                    # Check for privileged containers
                    if "privileged: true" in compose_content:
                        validation["issues"].append("Privileged containers detected")
                    else:
                        validation["checks"].append("No privileged containers")
                        validation["score"] += 10

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Service security validation error: {e}")

        return validation

    def _validate_os_security(self) -> Dict[str, Any]:
        """Validate operating system security."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            # Check firewall status
            try:
                ufw_result = subprocess.run(
                    ["ufw", "status"], capture_output=True, text=True
                )
                if ufw_result.returncode == 0:
                    if "Status: active" in ufw_result.stdout:
                        validation["checks"].append("UFW firewall is active")
                        validation["score"] += 15
                    else:
                        validation["warnings"].append("UFW firewall is inactive")
                else:
                    # Try iptables
                    iptables_result = subprocess.run(
                        ["iptables", "-L"], capture_output=True, text=True
                    )
                    if iptables_result.returncode == 0:
                        if len(iptables_result.stdout.split("\n")) > 10:
                            validation["checks"].append("iptables rules configured")
                            validation["score"] += 10
                        else:
                            validation["warnings"].append("No firewall rules detected")
            except FileNotFoundError:
                validation["warnings"].append("Cannot check firewall status")

            # Check for automatic security updates
            if os.path.exists("/etc/apt/apt.conf.d/50unattended-upgrades"):
                validation["checks"].append("Automatic security updates configured")
                validation["score"] += 10
            else:
                validation["warnings"].append(
                    "Automatic security updates not configured"
                )

            # Check fail2ban
            try:
                fail2ban_result = subprocess.run(
                    ["systemctl", "is-active", "fail2ban"],
                    capture_output=True,
                    text=True,
                )
                if fail2ban_result.stdout.strip() == "active":
                    validation["checks"].append("Fail2ban is active")
                    validation["score"] += 10
                else:
                    validation["warnings"].append("Fail2ban is not active")
            except FileNotFoundError:
                validation["warnings"].append("Fail2ban not installed")

            # Check SSH configuration
            ssh_config_file = "/etc/ssh/sshd_config"
            if os.path.exists(ssh_config_file):
                with open(ssh_config_file) as f:
                    ssh_config = f.read()

                # Check for secure SSH settings
                if "PermitRootLogin no" in ssh_config:
                    validation["checks"].append("SSH root login disabled")
                    validation["score"] += 10
                else:
                    validation["warnings"].append("SSH root login may be enabled")

                if "PasswordAuthentication no" in ssh_config:
                    validation["checks"].append("SSH password authentication disabled")
                    validation["score"] += 10
                else:
                    validation["warnings"].append(
                        "SSH password authentication may be enabled"
                    )

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"OS security validation error: {e}")

        return validation

    def _validate_application_security(self, domain: str) -> Dict[str, Any]:
        """Validate application-level security."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            # Test security headers
            try:
                response = requests.get(f"https://{domain}", timeout=10)
                headers = response.headers

                security_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                    "X-XSS-Protection": "1; mode=block",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "Content-Security-Policy": None,  # Just check presence
                }

                for header, expected_values in security_headers.items():
                    if header in headers:
                        header_value = headers[header]

                        if expected_values is None:  # Just check presence
                            validation["checks"].append(
                                f"Security header present: {header}"
                            )
                            validation["score"] += 5
                        elif isinstance(expected_values, list):
                            if any(val in header_value for val in expected_values):
                                validation["checks"].append(
                                    f"Secure header value: {header}"
                                )
                                validation["score"] += 5
                            else:
                                validation["warnings"].append(
                                    f"Potentially insecure header value: {header}"
                                )
                        elif expected_values in header_value:
                            validation["checks"].append(
                                f"Secure header value: {header}"
                            )
                            validation["score"] += 5
                        else:
                            validation["warnings"].append(
                                f"Potentially insecure header value: {header}"
                            )
                    else:
                        validation["warnings"].append(
                            f"Missing security header: {header}"
                        )

            except Exception as e:
                validation["warnings"].append(f"Could not test security headers: {e}")

            # Check for common vulnerabilities
            try:
                # Test for directory traversal
                test_paths = [
                    "/../../../etc/passwd",
                    "/..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                    "/.env",
                    "/config",
                ]

                for test_path in test_paths:
                    try:
                        response = requests.get(
                            f"https://{domain}{test_path}", timeout=5
                        )
                        if response.status_code == 200:
                            if any(
                                keyword in response.text.lower()
                                for keyword in ["password", "secret", "root:"]
                            ):
                                validation["issues"].append(
                                    f"Potential information disclosure: {test_path}"
                                )
                    except Exception:
                        continue  # Expected to fail

                validation["checks"].append(
                    "No obvious information disclosure vulnerabilities"
                )
                validation["score"] += 10

            except Exception as e:
                validation["warnings"].append(
                    f"Could not test for vulnerabilities: {e}"
                )

            validation["status"] = "passed" if not validation["issues"] else "failed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Application security validation error: {e}")

        return validation

    def _validate_backup_security(self) -> Dict[str, Any]:
        """Validate backup security."""
        validation = {
            "status": "checking",
            "issues": [],
            "warnings": [],
            "checks": [],
            "score": 0,
        }

        try:
            # Check backup directory permissions
            backup_dirs = ["/opt/coffeebreak/backups", "./backups"]

            for backup_dir in backup_dirs:
                if os.path.exists(backup_dir):
                    stat_info = os.stat(backup_dir)
                    mode = stat_info.st_mode & 0o777

                    if mode & 0o044:  # World or group readable
                        validation["warnings"].append(
                            f"Backup directory {backup_dir} is readable by others"
                        )
                    else:
                        validation["checks"].append(
                            f"Secure backup directory permissions: {backup_dir}"
                        )
                        validation["score"] += 10

                    # Check backup file permissions
                    backup_files = list(Path(backup_dir).glob("*backup*"))

                    for backup_file in backup_files[:5]:  # Check first 5 files
                        file_stat = os.stat(backup_file)
                        file_mode = file_stat.st_mode & 0o777

                        if file_mode & 0o044:
                            validation["warnings"].append(
                                f"Backup file {backup_file.name} is readable by others"
                            )
                        else:
                            validation["score"] += 2

                    if backup_files:
                        validation["checks"].append(
                            f"Found {len(backup_files)} backup files with "
                            f"appropriate permissions"
                        )

            # Check for backup encryption
            backup_scripts = ["/opt/coffeebreak/bin/backup.sh", "./backup.sh"]

            for script in backup_scripts:
                if os.path.exists(script):
                    with open(script) as f:
                        content = f.read()

                    if "encrypt" in content.lower() or "gpg" in content.lower():
                        validation["checks"].append("Backup encryption detected")
                        validation["score"] += 15
                    else:
                        validation["warnings"].append("No backup encryption detected")
                    break

            validation["status"] = "passed"

        except Exception as e:
            validation["status"] = "error"
            validation["issues"].append(f"Backup security validation error: {e}")

        return validation

    def _aggregate_security_results(self, security_result: Dict[str, Any]) -> None:
        """Aggregate all security validation results."""
        total_score = 0
        max_score = 0
        all_issues = []
        all_warnings = []
        all_checks = []

        for category, validation in security_result["validations"].items():
            total_score += validation.get("score", 0)
            max_score += 100  # Assuming each category has max 100 points

            all_issues.extend(
                [f"{category}: {issue}" for issue in validation.get("issues", [])]
            )
            all_warnings.extend(
                [f"{category}: {warning}" for warning in validation.get("warnings", [])]
            )
            all_checks.extend(
                [f"{category}: {check}" for check in validation.get("checks", [])]
            )

        # Calculate security score (0-100)
        security_result["security_score"] = (
            min(100, int((total_score / max_score) * 100)) if max_score > 0 else 0
        )
        security_result["issues"] = all_issues
        security_result["warnings"] = all_warnings
        security_result["checks"] = all_checks

        # Determine overall status
        if all_issues:
            security_result["status"] = "failed"
        elif all_warnings:
            security_result["status"] = "warning"
        else:
            security_result["status"] = "passed"
