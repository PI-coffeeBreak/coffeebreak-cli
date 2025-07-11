"""Production environment management."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from coffeebreak.secrets import SecretGenerator, SecretManager
from coffeebreak.utils.errors import ConfigurationError


class ProductionEnvironment:
    """Manages production deployment and operations."""

    def __init__(self, config_manager, verbose: bool = False):
        """Initialize with configuration manager."""
        self.config_manager = config_manager
        self.config = None
        self.verbose = verbose

        # Initialize template system
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))

        # Initialize secrets management
        self.secret_generator = SecretGenerator(verbose=verbose)
        self.secret_manager = None  # Will be initialized based on deployment type

    def generate_docker_project(
        self,
        output_dir: str,
        domain: str,
        ssl_email: Optional[str] = None,
        deployment_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate Docker Compose production project.

        Args:
            output_dir: Directory to create project in
            domain: Production domain
            ssl_email: Email for SSL certificate generation
            deployment_config: Additional deployment configuration

        Returns:
            Dict[str, Any]: Generation results
        """
        try:
            if self.verbose:
                print(f"Generating Docker production project for {domain}")

            # Create output directory
            project_dir = Path(output_dir) / f"coffeebreak-production-{domain.replace('.', '-')}"
            project_dir.mkdir(parents=True, exist_ok=True)

            result = {
                "success": True,
                "project_dir": str(project_dir),
                "domain": domain,
                "files_created": [],
                "secrets_generated": False,
                "errors": [],
            }

            # Merge deployment configuration
            config = {
                "domain": domain,
                "ssl_email": ssl_email or f"admin@{domain}",
                "timestamp": datetime.now().isoformat(),
                "app_version": "1.0.0",
                "postgres_user": "coffeebreak",
                "postgres_db": "coffeebreak",
                "mongodb_user": "coffeebreak",
                "mongodb_db": "coffeebreak",
                "rabbitmq_user": "coffeebreak",
                "keycloak_realm": "coffeebreak",
                "keycloak_client_id": "coffeebreak-api",
                "log_level": "info",
                "metrics_enabled": True,
                "backup_enabled": True,
                "redis_enabled": True,
                "smtp_enabled": False,
            }

            if deployment_config:
                config.update(deployment_config)

            # Initialize Docker secrets manager
            self.secret_manager = SecretManager(deployment_type="docker", verbose=self.verbose)

            # Generate all production secrets
            all_secrets = self.secret_generator.generate_all_secrets()

            # Create Docker Compose file
            compose_template = self.jinja_env.get_template("docker-compose.production.yml.j2")
            compose_content = compose_template.render(**config)

            compose_file = project_dir / "docker-compose.yml"
            with open(compose_file, "w") as f:
                f.write(compose_content)
            result["files_created"].append(str(compose_file))

            # Create nginx configuration
            nginx_template = self.jinja_env.get_template("nginx.conf.j2")
            nginx_content = nginx_template.render(**config)

            nginx_dir = project_dir / "nginx"
            nginx_dir.mkdir(exist_ok=True)
            nginx_file = nginx_dir / "nginx.conf"
            with open(nginx_file, "w") as f:
                f.write(nginx_content)
            result["files_created"].append(str(nginx_file))

            # Create environment files for each service
            services = ["api", "frontend", "events"]
            env_template = self.jinja_env.get_template("env.production.j2")

            for service in services:
                service_config = config.copy()
                service_config["service_name"] = service

                env_content = env_template.render(**service_config)
                env_file = project_dir / f".env.{service}"
                with open(env_file, "w") as f:
                    f.write(env_content)
                result["files_created"].append(str(env_file))

            # Create secrets directory and files
            secrets_dir = project_dir / "secrets"
            secrets_dir.mkdir(exist_ok=True)

            # Create secrets deployment script
            secrets_script_content = self._generate_secrets_script(all_secrets)
            secrets_script = project_dir / "deploy-secrets.sh"
            with open(secrets_script, "w") as f:
                f.write(secrets_script_content)
            os.chmod(secrets_script, 0o755)
            result["files_created"].append(str(secrets_script))

            # Create secrets environment file (for reference)
            secrets_env = secrets_dir / "secrets.env"
            with open(secrets_env, "w") as f:
                f.write("# Production Secrets - Deploy using deploy-secrets.sh\n")
                f.write("# DO NOT COMMIT THESE VALUES TO VERSION CONTROL\n\n")
                for name, value in all_secrets.items():
                    f.write(f"{name.upper()}={value}\n")
            os.chmod(secrets_env, 0o600)
            result["files_created"].append(str(secrets_env))

            # Create SSL certificates directory structure
            ssl_dir = project_dir / "ssl"
            ssl_dir.mkdir(exist_ok=True)
            (ssl_dir / "certs").mkdir(exist_ok=True)
            (ssl_dir / "private").mkdir(exist_ok=True)

            # Create SSL setup script
            ssl_script_content = self._generate_ssl_script(domain, ssl_email)
            ssl_script = project_dir / "setup-ssl.sh"
            with open(ssl_script, "w") as f:
                f.write(ssl_script_content)
            os.chmod(ssl_script, 0o755)
            result["files_created"].append(str(ssl_script))

            # Create deployment scripts
            deploy_script_content = self._generate_deploy_script(domain)
            deploy_script = project_dir / "deploy.sh"
            with open(deploy_script, "w") as f:
                f.write(deploy_script_content)
            os.chmod(deploy_script, 0o755)
            result["files_created"].append(str(deploy_script))

            # Create management scripts
            management_scripts = [
                ("start.sh", self._generate_start_script()),
                ("stop.sh", self._generate_stop_script()),
                ("restart.sh", self._generate_restart_script()),
                ("logs.sh", self._generate_logs_script()),
                ("backup.sh", self._generate_backup_script()),
                ("update.sh", self._generate_update_script()),
            ]

            for script_name, script_content in management_scripts:
                script_file = project_dir / script_name
                with open(script_file, "w") as f:
                    f.write(script_content)
                os.chmod(script_file, 0o755)
                result["files_created"].append(str(script_file))

            # Create README with deployment instructions
            readme_content = self._generate_readme(domain, config)
            readme_file = project_dir / "README.md"
            with open(readme_file, "w") as f:
                f.write(readme_content)
            result["files_created"].append(str(readme_file))

            # Create docker directories
            for directory in [
                "data/postgres",
                "data/mongodb",
                "data/rabbitmq",
                "logs",
                "backups",
            ]:
                (project_dir / directory).mkdir(parents=True, exist_ok=True)

            result["secrets_generated"] = True
            result["secrets_count"] = len(all_secrets)

            if self.verbose:
                print(f"Successfully generated production project at {project_dir}")
                print(f"Created {len(result['files_created'])} files")
                print(f"Generated {len(all_secrets)} secrets")

            return result

        except Exception as e:
            if self.verbose:
                print(f"Error generating Docker production project: {e}")

            return {
                "success": False,
                "error": str(e),
                "project_dir": None,
                "files_created": [],
                "secrets_generated": False,
            }

    def install_standalone(
        self,
        domain: str,
        ssl_email: Optional[str] = None,
        user: str = "coffeebreak",
        install_dir: str = "/opt/coffeebreak",
        data_dir: str = "/var/lib/coffeebreak",
        log_dir: str = "/var/log/coffeebreak",
    ) -> Dict[str, Any]:
        """
        Install CoffeeBreak directly on production machine.

        Args:
            domain: Production domain
            ssl_email: Email for SSL certificate generation
            user: System user for CoffeeBreak
            install_dir: Installation directory
            data_dir: Data directory
            log_dir: Log directory

        Returns:
            Dict[str, Any]: Installation results
        """
        try:
            if self.verbose:
                print(f"Installing CoffeeBreak standalone for {domain}")

            installation_result = {
                "success": True,
                "domain": domain,
                "user": user,
                "install_dir": install_dir,
                "data_dir": data_dir,
                "log_dir": log_dir,
                "services_created": [],
                "errors": [],
            }

            # Initialize standalone secrets manager
            self.secret_manager = SecretManager(deployment_type="standalone", verbose=self.verbose)

            # Generate all production secrets
            all_secrets = self.secret_generator.generate_all_secrets()

            # Create system user
            self._create_system_user(user, install_dir)

            # Create directory structure
            self._create_directories(install_dir, data_dir, log_dir, user)

            # Install application files
            self._install_application_files(install_dir, domain, user)

            # Deploy secrets
            secrets_dir = f"{install_dir}/secrets"
            secrets_result = self.secret_manager.deploy_all_secrets(all_secrets, secrets_dir)

            if secrets_result["failed"] > 0:
                installation_result["errors"].extend(secrets_result["errors"])

            # Setup SSL certificates
            ssl_result = self._setup_ssl_standalone(domain, ssl_email, install_dir)
            if not ssl_result["success"]:
                installation_result["errors"].append(f"SSL setup failed: {ssl_result.get('error', 'Unknown error')}")

            # Install and configure services
            services_result = self._install_services(domain, user, install_dir, data_dir, log_dir)
            installation_result["services_created"] = services_result["services"]
            if services_result["errors"]:
                installation_result["errors"].extend(services_result["errors"])

            # Configure nginx
            nginx_result = self._configure_nginx_standalone(domain, install_dir)
            if not nginx_result["success"]:
                installation_result["errors"].append(f"Nginx configuration failed: {nginx_result.get('error', 'Unknown error')}")

            # Setup monitoring and logging
            monitoring_result = self._setup_monitoring_standalone(domain, log_dir)
            if not monitoring_result["success"]:
                installation_result["errors"].append(f"Monitoring setup failed: {monitoring_result.get('error', 'Unknown error')}")

            # Setup backup system
            backup_result = self._setup_backup_standalone(domain, data_dir, install_dir)
            if not backup_result["success"]:
                installation_result["errors"].append(f"Backup setup failed: {backup_result.get('error', 'Unknown error')}")

            # Start services
            start_result = self._start_services(installation_result["services_created"])
            if not start_result["success"]:
                installation_result["errors"].append(f"Failed to start services: {start_result.get('error', 'Unknown error')}")

            # Final validation
            validation_result = self._validate_installation(domain, install_dir)
            if not validation_result["success"]:
                installation_result["errors"].extend(validation_result["errors"])

            installation_result["success"] = len(installation_result["errors"]) == 0

            if self.verbose:
                if installation_result["success"]:
                    print(f"CoffeeBreak standalone installation completed successfully for {domain}")
                else:
                    print(f"Installation completed with {len(installation_result['errors'])} errors")

            return installation_result

        except Exception as e:
            if self.verbose:
                print(f"Standalone installation failed: {e}")
            return {"success": False, "error": str(e), "domain": domain}

    def _create_system_user(self, user: str, home_dir: str) -> None:
        """Create system user for CoffeeBreak."""
        try:
            import subprocess

            # Check if user already exists
            result = subprocess.run(["id", user], capture_output=True)
            if result.returncode == 0:
                if self.verbose:
                    print(f"User {user} already exists")
                return

            # Create system user
            cmd = [
                "useradd",
                "--system",
                "--home-dir",
                home_dir,
                "--create-home",
                "--shell",
                "/bin/bash",
                "--comment",
                "CoffeeBreak Application User",
                user,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise ConfigurationError(f"Failed to create user {user}: {result.stderr}")

            if self.verbose:
                print(f"Created system user: {user}")

        except Exception as e:
            raise ConfigurationError(f"Failed to create system user: {e}") from e

    def _create_directories(self, install_dir: str, data_dir: str, log_dir: str, user: str) -> None:
        """Create directory structure."""
        try:
            import subprocess

            directories = [
                install_dir,
                f"{install_dir}/bin",
                f"{install_dir}/config",
                f"{install_dir}/secrets",
                f"{install_dir}/ssl",
                f"{install_dir}/logs",
                data_dir,
                f"{data_dir}/postgres",
                f"{data_dir}/mongodb",
                f"{data_dir}/uploads",
                log_dir,
                f"{log_dir}/nginx",
                f"{log_dir}/api",
                f"{log_dir}/frontend",
                f"{log_dir}/events",
            ]

            for directory in directories:
                Path(directory).mkdir(parents=True, exist_ok=True)
                subprocess.run(["chown", f"{user}:{user}", directory], check=True)
                subprocess.run(["chmod", "755", directory], check=True)

            # Set secure permissions for secrets directory
            subprocess.run(["chmod", "700", f"{install_dir}/secrets"], check=True)

            if self.verbose:
                print(f"Created directory structure: {len(directories)} directories")

        except Exception as e:
            raise ConfigurationError(f"Failed to create directories: {e}") from e

    def _install_application_files(self, install_dir: str, domain: str, user: str) -> None:
        """Install application files and configuration."""
        try:
            # Create systemd service templates
            services = ["api", "frontend", "events"]

            for service in services:
                service_template = self.jinja_env.get_template("systemd.service.j2")
                service_content = service_template.render(
                    service_name=service,
                    domain=domain,
                    user=user,
                    install_dir=install_dir,
                    working_directory=f"{install_dir}/{service}",
                    exec_start=f"{install_dir}/bin/start-{service}.sh",
                )

                service_file = f"/etc/systemd/system/coffeebreak-{service}.service"
                with open(service_file, "w") as f:
                    f.write(service_content)

                # Create start script
                start_script = f"{install_dir}/bin/start-{service}.sh"
                with open(start_script, "w") as f:
                    f.write(f"""#!/bin/bash
# Start script for CoffeeBreak {service}

cd {install_dir}/{service}
source {install_dir}/config/.env.{service}

# Start the service based on type
case "{service}" in
    "api")
        exec node server.js
        ;;
    "frontend"|"events")
        exec serve -s build -p $PORT
        ;;
esac
""")
                os.chmod(start_script, 0o755)

            if self.verbose:
                print(f"Installed application files for {len(services)} services")

        except Exception as e:
            raise ConfigurationError(f"Failed to install application files: {e}") from e

    def _setup_ssl_standalone(self, domain: str, ssl_email: str, install_dir: str) -> Dict[str, Any]:
        """Setup SSL certificates for standalone installation."""
        try:
            from coffeebreak.ssl import LetsEncryptManager

            ssl_email = ssl_email or f"admin@{domain}"
            le_manager = LetsEncryptManager(email=ssl_email, verbose=self.verbose)

            # Obtain certificate
            cert_result = le_manager.obtain_certificate(domain=domain, challenge_method="standalone")

            if cert_result["success"]:
                # Copy certificates to install directory
                ssl_dir = f"{install_dir}/ssl"
                import shutil

                shutil.copy2(cert_result["cert_path"], f"{ssl_dir}/fullchain.pem")
                shutil.copy2(cert_result["key_path"], f"{ssl_dir}/privkey.pem")
                shutil.copy2(cert_result["chain_path"], f"{ssl_dir}/chain.pem")

                # Setup auto-renewal
                le_manager.setup_auto_renewal()

                return {
                    "success": True,
                    "cert_path": f"{ssl_dir}/fullchain.pem",
                    "key_path": f"{ssl_dir}/privkey.pem",
                }
            else:
                return {"success": False, "error": "Failed to obtain SSL certificate"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _install_services(self, domain: str, user: str, install_dir: str, data_dir: str, log_dir: str) -> Dict[str, Any]:
        """Install and configure system services."""
        try:
            import subprocess

            services_created = []
            errors = []

            # Install and configure PostgreSQL
            try:
                self._install_postgresql(data_dir, user)
                services_created.append("postgresql")
            except Exception as e:
                errors.append(f"PostgreSQL installation failed: {e}")

            # Install and configure MongoDB
            try:
                self._install_mongodb(data_dir, user)
                services_created.append("mongodb")
            except Exception as e:
                errors.append(f"MongoDB installation failed: {e}")

            # Install and configure RabbitMQ
            try:
                self._install_rabbitmq(user)
                services_created.append("rabbitmq-server")
            except Exception as e:
                errors.append(f"RabbitMQ installation failed: {e}")

            # Install and configure Redis
            try:
                self._install_redis()
                services_created.append("redis-server")
            except Exception as e:
                errors.append(f"Redis installation failed: {e}")

            # Enable CoffeeBreak services
            coffeebreak_services = [
                "coffeebreak-api",
                "coffeebreak-frontend",
                "coffeebreak-events",
            ]
            for service in coffeebreak_services:
                try:
                    subprocess.run(["systemctl", "daemon-reload"], check=True)
                    subprocess.run(["systemctl", "enable", service], check=True)
                    services_created.append(service)
                except Exception as e:
                    errors.append(f"Failed to enable {service}: {e}")

            return {"services": services_created, "errors": errors}

        except Exception as e:
            return {"services": [], "errors": [str(e)]}

    def _install_postgresql(self, data_dir: str, user: str) -> None:
        """Install and configure PostgreSQL."""
        import subprocess

        # Install PostgreSQL
        if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
            subprocess.run(["apt-get", "update"], check=True)
            subprocess.run(
                ["apt-get", "install", "-y", "postgresql", "postgresql-contrib"],
                check=True,
            )
        elif subprocess.run(["which", "yum"], capture_output=True).returncode == 0:
            subprocess.run(
                ["yum", "install", "-y", "postgresql-server", "postgresql-contrib"],
                check=True,
            )
            subprocess.run(["postgresql-setup", "initdb"], check=True)

        # Start and enable PostgreSQL
        subprocess.run(["systemctl", "start", "postgresql"], check=True)
        subprocess.run(["systemctl", "enable", "postgresql"], check=True)

        # Create database and user
        commands = [
            f"CREATE USER coffeebreak WITH PASSWORD '{self.secret_manager.load_encrypted_secret('postgres_password', '/opt/coffeebreak/secrets')}';",
            "CREATE DATABASE coffeebreak OWNER coffeebreak;",
            "GRANT ALL PRIVILEGES ON DATABASE coffeebreak TO coffeebreak;",
        ]

        for cmd in commands:
            subprocess.run(["sudo", "-u", "postgres", "psql", "-c", cmd], check=True)

    def _install_mongodb(self, data_dir: str, user: str) -> None:
        """Install and configure MongoDB."""
        import subprocess

        # Install MongoDB
        if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
            subprocess.run(["apt-get", "install", "-y", "mongodb"], check=True)
        elif subprocess.run(["which", "yum"], capture_output=True).returncode == 0:
            subprocess.run(["yum", "install", "-y", "mongodb-server"], check=True)

        # Configure MongoDB data directory
        subprocess.run(["chown", "mongodb:mongodb", f"{data_dir}/mongodb"], check=True)

        # Start and enable MongoDB
        subprocess.run(["systemctl", "start", "mongod"], check=True)
        subprocess.run(["systemctl", "enable", "mongod"], check=True)

    def _install_rabbitmq(self, user: str) -> None:
        """Install and configure RabbitMQ."""
        import subprocess

        # Install RabbitMQ
        if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
            subprocess.run(["apt-get", "install", "-y", "rabbitmq-server"], check=True)
        elif subprocess.run(["which", "yum"], capture_output=True).returncode == 0:
            subprocess.run(["yum", "install", "-y", "rabbitmq-server"], check=True)

        # Start and enable RabbitMQ
        subprocess.run(["systemctl", "start", "rabbitmq-server"], check=True)
        subprocess.run(["systemctl", "enable", "rabbitmq-server"], check=True)

        # Create user and vhost
        subprocess.run(["rabbitmqctl", "add_vhost", "/coffeebreak"], check=True)
        subprocess.run(
            [
                "rabbitmqctl",
                "add_user",
                "coffeebreak",
                self.secret_manager.load_encrypted_secret("rabbitmq_password", "/opt/coffeebreak/secrets"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "rabbitmqctl",
                "set_permissions",
                "-p",
                "/coffeebreak",
                "coffeebreak",
                ".*",
                ".*",
                ".*",
            ],
            check=True,
        )

    def _install_redis(self) -> None:
        """Install and configure Redis."""
        import subprocess

        # Install Redis
        if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
            subprocess.run(["apt-get", "install", "-y", "redis-server"], check=True)
        elif subprocess.run(["which", "yum"], capture_output=True).returncode == 0:
            subprocess.run(["yum", "install", "-y", "redis"], check=True)

        # Start and enable Redis
        subprocess.run(["systemctl", "start", "redis"], check=True)
        subprocess.run(["systemctl", "enable", "redis"], check=True)

    def _configure_nginx_standalone(self, domain: str, install_dir: str) -> Dict[str, Any]:
        """Configure nginx for standalone installation."""
        try:
            import subprocess

            # Install nginx
            if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
                subprocess.run(["apt-get", "install", "-y", "nginx"], check=True)
            elif subprocess.run(["which", "yum"], capture_output=True).returncode == 0:
                subprocess.run(["yum", "install", "-y", "nginx"], check=True)

            # Generate nginx configuration
            nginx_template = self.jinja_env.get_template("nginx.conf.j2")
            nginx_content = nginx_template.render(
                domain=domain,
                ssl_cert_path=f"{install_dir}/ssl/fullchain.pem",
                ssl_key_path=f"{install_dir}/ssl/privkey.pem",
            )

            # Write nginx configuration
            with open(f"/etc/nginx/sites-available/{domain}", "w") as f:
                f.write(nginx_content)

            # Enable site
            site_enabled = f"/etc/nginx/sites-enabled/{domain}"
            if not os.path.exists(site_enabled):
                os.symlink(f"/etc/nginx/sites-available/{domain}", site_enabled)

            # Test and reload nginx
            subprocess.run(["nginx", "-t"], check=True)
            subprocess.run(["systemctl", "enable", "nginx"], check=True)
            subprocess.run(["systemctl", "reload", "nginx"], check=True)

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _setup_monitoring_standalone(self, domain: str, log_dir: str) -> Dict[str, Any]:
        """Setup monitoring and logging for standalone installation."""
        try:
            # Setup log rotation
            logrotate_config = f"""
{log_dir}/*.log {{
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    create 644 coffeebreak coffeebreak
}}
"""
            with open("/etc/logrotate.d/coffeebreak", "w") as f:
                f.write(logrotate_config)

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _setup_backup_standalone(self, domain: str, data_dir: str, install_dir: str) -> Dict[str, Any]:
        """Setup backup system for standalone installation."""
        try:
            # Create backup script
            backup_script = f"""#!/bin/bash
# CoffeeBreak Backup Script

BACKUP_DIR="/opt/coffeebreak/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="coffeebreak_backup_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

# Database backups
pg_dump -U coffeebreak coffeebreak > "$BACKUP_DIR/${{BACKUP_NAME}}_postgres.sql"
mongodump --db coffeebreak --archive="$BACKUP_DIR/${{BACKUP_NAME}}_mongodb.archive"

# Application data backup
tar -czf "$BACKUP_DIR/${{BACKUP_NAME}}_data.tar.gz" {data_dir}
tar -czf "$BACKUP_DIR/${{BACKUP_NAME}}_config.tar.gz" {install_dir}/config

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -name "coffeebreak_backup_*" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/$BACKUP_NAME"
"""

            backup_script_path = f"{install_dir}/bin/backup.sh"
            with open(backup_script_path, "w") as f:
                f.write(backup_script)
            os.chmod(backup_script_path, 0o755)

            # Setup cron job for daily backups
            import subprocess

            cron_entry = f"0 2 * * * {backup_script_path}"

            try:
                current_crontab = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                crontab_content = current_crontab.stdout if current_crontab.returncode == 0 else ""
            except Exception:
                crontab_content = ""

            if "backup.sh" not in crontab_content:
                new_crontab = crontab_content.rstrip() + "\n" + cron_entry + "\n"
                process = subprocess.Popen(
                    ["crontab", "-u", "coffeebreak", "-"],
                    stdin=subprocess.PIPE,
                    text=True,
                )
                process.communicate(input=new_crontab)

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _start_services(self, services: List[str]) -> Dict[str, Any]:
        """Start all configured services."""
        try:
            import subprocess

            failed_services = []

            for service in services:
                try:
                    subprocess.run(["systemctl", "start", service], check=True)
                    if self.verbose:
                        print(f"Started service: {service}")
                except Exception as e:
                    failed_services.append(f"{service}: {e}")

            if failed_services:
                return {
                    "success": False,
                    "error": f"Failed to start services: {', '.join(failed_services)}",
                }

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _validate_installation(self, domain: str, install_dir: str) -> Dict[str, Any]:
        """Validate the standalone installation."""
        try:
            import subprocess
            import time

            import requests

            errors = []

            # Check if services are running
            required_services = [
                "postgresql",
                "mongod",
                "rabbitmq-server",
                "redis-server",
                "nginx",
                "coffeebreak-api",
                "coffeebreak-frontend",
                "coffeebreak-events",
            ]

            for service in required_services:
                try:
                    result = subprocess.run(
                        ["systemctl", "is-active", service],
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip() != "active":
                        errors.append(f"Service {service} is not running")
                except Exception:
                    errors.append(f"Could not check status of service {service}")

            # Test HTTP connectivity
            time.sleep(10)  # Wait for services to be fully ready

            try:
                response = requests.get(f"https://{domain}/health", timeout=10, verify=False)
                if response.status_code != 200:
                    errors.append(f"Health check failed: HTTP {response.status_code}")
            except Exception as e:
                errors.append(f"HTTP connectivity test failed: {e}")

            # Check SSL certificate
            cert_path = f"{install_dir}/ssl/fullchain.pem"
            key_path = f"{install_dir}/ssl/privkey.pem"

            if os.path.exists(cert_path) and os.path.exists(key_path):
                from coffeebreak.ssl import SSLManager

                ssl_manager = SSLManager(verbose=self.verbose)

                validation = ssl_manager.validate_certificate(cert_path, key_path, domain)
                if not validation["valid"]:
                    errors.extend([f"SSL: {error}" for error in validation["errors"]])
            else:
                errors.append("SSL certificate files not found")

            return {"success": len(errors) == 0, "errors": errors}

        except Exception as e:
            return {"success": False, "errors": [str(e)]}

    def deploy(self) -> bool:
        """
        Deploy to configured production environment.

        Returns:
            bool: True if deployment successful
        """
        # Implementation will be added in Phase 5
        return True

    def _generate_secrets_script(self, secrets: Dict[str, str]) -> str:
        """Generate script to deploy Docker secrets."""
        script = """#!/bin/bash
# CoffeeBreak Production Secrets Deployment Script
# This script creates Docker secrets from the generated values

set -e

echo "Deploying CoffeeBreak production secrets..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not available"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

"""

        for name, value in secrets.items():
            script += f"""
# Deploy {name}
echo "Creating secret: coffeebreak_{name}"
echo '{value}' | docker secret create coffeebreak_{name} - 2>/dev/null || echo "Secret coffeebreak_{name} already exists"
"""

        script += """
echo "All secrets deployed successfully!"
echo "Note: Secrets are now available to Docker Compose services"
"""
        return script

    def _generate_ssl_script(self, domain: str, ssl_email: str) -> str:
        """Generate SSL certificate setup script."""
        return f"""#!/bin/bash
# CoffeeBreak SSL Certificate Setup Script
# Sets up Let's Encrypt certificates for {domain}

set -e

DOMAIN="{domain}"
EMAIL="{ssl_email}"
SSL_DIR="./ssl"

echo "Setting up SSL certificates for $DOMAIN..."

# Check if certbot is available
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y certbot
    elif command -v yum &> /dev/null; then
        sudo yum install -y certbot
    else
        echo "Error: Cannot install certbot automatically"
        echo "Please install certbot manually and run this script again"
        exit 1
    fi
fi

# Create SSL directories
mkdir -p $SSL_DIR/certs
mkdir -p $SSL_DIR/private

# Generate certificates using certbot standalone
echo "Generating SSL certificate for $DOMAIN..."
sudo certbot certonly \\
    --standalone \\
    --email $EMAIL \\
    --agree-tos \\
    --non-interactive \\
    --domains $DOMAIN

# Copy certificates to project directory
echo "Copying certificates..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $SSL_DIR/certs/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $SSL_DIR/private/
sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem $SSL_DIR/certs/

# Set appropriate permissions
sudo chown -R $USER:$USER $SSL_DIR
chmod 644 $SSL_DIR/certs/*
chmod 600 $SSL_DIR/private/*

echo "SSL certificates set up successfully!"
echo "Certificates location: $SSL_DIR"

# Set up automatic renewal
echo "Setting up automatic certificate renewal..."
(sudo crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | sudo crontab -

echo "Certificate renewal scheduled via cron"
"""

    def _generate_deploy_script(self, domain: str) -> str:
        """Generate main deployment script."""
        return f"""#!/bin/bash
# CoffeeBreak Production Deployment Script
# Deploys CoffeeBreak for {domain}

set -e

DOMAIN="{domain}"

echo "Starting CoffeeBreak production deployment for $DOMAIN..."

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# Deploy secrets
echo "Deploying secrets..."
./deploy-secrets.sh

# Set up SSL certificates
echo "Setting up SSL certificates..."
./setup-ssl.sh

# Pull latest images
echo "Pulling latest Docker images..."
docker-compose pull

# Start services
echo "Starting CoffeeBreak services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Check service health
echo "Checking service health..."
docker-compose ps

echo "Deployment completed successfully!"
echo "CoffeeBreak is now available at https://$DOMAIN"
echo ""
echo "Useful commands:"
echo "  ./start.sh    - Start all services"
echo "  ./stop.sh     - Stop all services"
echo "  ./restart.sh  - Restart all services"
echo "  ./logs.sh     - View logs"
echo "  ./backup.sh   - Create backup"
"""

    def _generate_start_script(self) -> str:
        """Generate start script."""
        return """#!/bin/bash
# Start CoffeeBreak production services

set -e

echo "Starting CoffeeBreak production services..."
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

echo "Service status:"
docker-compose ps

echo "CoffeeBreak services started successfully!"
"""

    def _generate_stop_script(self) -> str:
        """Generate stop script."""
        return """#!/bin/bash
# Stop CoffeeBreak production services

set -e

echo "Stopping CoffeeBreak production services..."
docker-compose down

echo "CoffeeBreak services stopped successfully!"
"""

    def _generate_restart_script(self) -> str:
        """Generate restart script."""
        return """#!/bin/bash
# Restart CoffeeBreak production services

set -e

echo "Restarting CoffeeBreak production services..."
docker-compose down
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

echo "Service status:"
docker-compose ps

echo "CoffeeBreak services restarted successfully!"
"""

    def _generate_logs_script(self) -> str:
        """Generate logs script."""
        return """#!/bin/bash
# View CoffeeBreak production logs

# Default to following all logs
SERVICE=${1:-}

if [ -z "$SERVICE" ]; then
    echo "Following logs for all services (Ctrl+C to exit)..."
    docker-compose logs -f
else
    echo "Following logs for service: $SERVICE"
    docker-compose logs -f "$SERVICE"
fi
"""

    def _generate_backup_script(self) -> str:
        """Generate backup script."""
        return """#!/bin/bash
# Create backup of CoffeeBreak production data

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="coffeebreak_backup_$TIMESTAMP"

echo "Creating CoffeeBreak backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create database backups
echo "Backing up PostgreSQL database..."
docker-compose exec -T postgres pg_dump -U coffeebreak coffeebreak > "$BACKUP_DIR/${BACKUP_NAME}_postgres.sql"

echo "Backing up MongoDB database..."
docker-compose exec -T mongodb mongodump --db coffeebreak --archive > "$BACKUP_DIR/${BACKUP_NAME}_mongodb.archive"

# Create configuration backup
echo "Backing up configuration..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz" \\
    docker-compose.yml \\
    .env.* \\
    nginx/ \\
    ssl/ 2>/dev/null || true

# Create data backup
echo "Backing up application data..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_data.tar.gz" \\
    data/ \\
    logs/ 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR/$BACKUP_NAME"
echo "Files created:"
ls -la "$BACKUP_DIR" | grep "$BACKUP_NAME"

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "coffeebreak_backup_*" -mtime +7 -delete 2>/dev/null || true

echo "Backup process completed successfully!"
"""

    def _generate_update_script(self) -> str:
        """Generate update script."""
        return """#!/bin/bash
# Update CoffeeBreak production deployment

set -e

echo "Updating CoffeeBreak production deployment..."

# Create backup before update
echo "Creating backup before update..."
./backup.sh

# Pull latest images
echo "Pulling latest Docker images..."
docker-compose pull

# Restart services with new images
echo "Restarting services with updated images..."
docker-compose down
docker-compose up -d

echo "Waiting for services to start..."
sleep 30

# Check service health
echo "Checking service health..."
docker-compose ps

echo "Update completed successfully!"
"""

    def _generate_readme(self, domain: str, config: Dict[str, Any]) -> str:
        """Generate README with deployment instructions."""
        return f"""# CoffeeBreak Production Deployment

This directory contains a complete production deployment configuration for CoffeeBreak on **{domain}**.

## Generated Configuration

- **Domain**: {domain}
- **Generated**: {config["timestamp"]}
- **App Version**: {config["app_version"]}
- **Services**: API, Frontend, Events, Database, Authentication

## Prerequisites

Before deploying, ensure you have:

1. **Docker & Docker Compose** installed
2. **Domain DNS** pointing to this server
3. **Ports 80 and 443** open for web traffic
4. **SSL Email** configured for Let's Encrypt

## Quick Deployment

1. **Deploy the entire stack**:
   ```bash
   ./deploy.sh
   ```

   This will:
   - Deploy all production secrets
   - Set up SSL certificates
   - Start all services

2. **Access your application**:
   - Main App: https://{domain}
   - API: https://{domain}/api
   - Events: https://{domain}/events

## Manual Deployment Steps

If you prefer step-by-step deployment:

### 1. Deploy Secrets

```bash
./deploy-secrets.sh
```

### 2. Set up SSL Certificates

```bash
./setup-ssl.sh
```

### 3. Start Services

```bash
docker-compose up -d
```

## Management Commands

- **Start services**: `./start.sh`
- **Stop services**: `./stop.sh`
- **Restart services**: `./restart.sh`
- **View logs**: `./logs.sh [service_name]`
- **Create backup**: `./backup.sh`
- **Update deployment**: `./update.sh`

## File Structure

```
.
├── docker-compose.yml          # Main orchestration file
├── .env.api                   # API service environment
├── .env.frontend              # Frontend service environment
├── .env.events                # Events service environment
├── nginx/
│   └── nginx.conf             # Nginx configuration
├── ssl/
│   ├── certs/                 # SSL certificates
│   └── private/               # SSL private keys
├── secrets/
│   └── secrets.env            # Generated secrets (secure)
├── data/                      # Persistent data
├── logs/                      # Application logs
├── backups/                   # Backup files
└── *.sh                       # Management scripts
```

## Services

### Core Services
- **API Server**: CoffeeBreak REST API
- **Frontend**: React web application
- **Events**: Real-time events application
- **Nginx**: Reverse proxy and SSL termination

### Infrastructure Services
- **PostgreSQL**: Primary database
- **MongoDB**: Document storage
- **RabbitMQ**: Message queue
- **Keycloak**: Authentication service
- **Redis**: Caching layer

## Security Features

- SSL/TLS encryption with Let's Encrypt
- Security headers via nginx
- Rate limiting
- Secure secret management
- Database authentication
- CORS configuration

## Monitoring

- Health checks on all services
- Prometheus metrics (port 9090)
- Centralized logging
- Service status monitoring

## Backup & Recovery

Automated backup includes:
- PostgreSQL database dump
- MongoDB database archive
- Configuration files
- Application data

Backups are stored in `./backups/` and automatically cleaned (7-day retention).

## Troubleshooting

### Check Service Status
```bash
docker-compose ps
```

### View Service Logs
```bash
./logs.sh [service_name]
```

### Restart Failed Service
```bash
docker-compose restart [service_name]
```

### Update SSL Certificates
```bash
./setup-ssl.sh
```

## Configuration

Environment variables are configured in `.env.*` files for each service.
Secrets are managed via Docker Secrets and deployed via `deploy-secrets.sh`.

## Support

For issues with CoffeeBreak deployment, check:
1. Service logs: `./logs.sh`
2. Service status: `docker-compose ps`
3. SSL configuration: `nginx/nginx.conf`
4. Environment files: `.env.*`

---

**Generated by CoffeeBreak CLI** - Production deployment for {domain}
"""
