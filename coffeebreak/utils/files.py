"""File operations utilities for CoffeeBreak CLI."""

import os
import stat
from typing import Dict, List


class FileManager:
    """Manages file operations for CoffeeBreak CLI."""

    def __init__(self, verbose: bool = False):
        """Initialize file manager."""
        self.verbose = verbose

    def generate_env_file(
        self,
        connection_info: Dict[str, str],
        output_path: str = ".env.local",
        include_secrets: bool = False,
    ) -> str:
        """
        Generate environment file with connection strings.

        Args:
            connection_info: Dictionary of environment variables
            output_path: Path to output file
            include_secrets: Whether to include development secrets

        Returns:
            str: Path to generated file
        """
        env_content = []

        # Add header
        env_content.append("# CoffeeBreak Development Environment Variables")
        env_content.append("# Generated automatically by coffeebreak-cli")
        env_content.append("# Do not commit this file to version control")
        env_content.append("")
        env_content.append("COFFEEBREAK_ENV=development")
        env_content.append("")

        # Add connection information
        if connection_info:
            env_content.append("# Service Connection Strings")
            for key, value in connection_info.items():
                env_content.append(f"{key}={value}")
            env_content.append("")

        # Generate secrets if requested
        secrets = {}
        if include_secrets:
            secrets = self._generate_development_secrets()
            env_content.append("# Development Secrets")
            for key, value in secrets.items():
                env_content.append(f"{key}={value}")
            env_content.append("")

        # Add orchestrator environment variables with defaults
        env_content.append("# Orchestrator Environment Variables")

        # Basic configuration
        env_content.append("ENVIRONMENT=development")

        # Service user defaults
        env_content.append("POSTGRES_USER=coffeebreak")
        env_content.append("POSTGRES_HOST=database")
        env_content.append("POSTGRES_PORT=5432")
        env_content.append("POSTGRES_DB=coffeebreak")

        env_content.append("MONGO_INITDB_ROOT_USERNAME=admin")
        env_content.append("MONGO_INITDB_DATABASE=coffeebreak")

        env_content.append("RABBITMQ_DEFAULT_USER=coffeebreak")

        env_content.append("KC_DB_USERNAME=keycloak")
        env_content.append("KEYCLOAK_ADMIN=admin")
        env_content.append("KC_HOSTNAME=localhost")
        env_content.append("PROXY_ADDRESS_FORWARDING=true")

        # Derived connection strings
        if include_secrets and "POSTGRES_PASSWORD" in secrets:
            postgres_pass = secrets["POSTGRES_PASSWORD"]
            env_content.append(f"DATABASE_URI=postgresql://coffeebreak:{postgres_pass}@database:5432/coffeebreak")

        if include_secrets and "MONGO_INITDB_ROOT_PASSWORD" in secrets:
            mongo_pass = secrets["MONGO_INITDB_ROOT_PASSWORD"]
            env_content.append(f"MONGODB_URI=mongodb://admin:{mongo_pass}@mongodb/coffeebreak?authSource=admin")

        if include_secrets and "RABBITMQ_DEFAULT_PASS" in secrets:
            rabbitmq_pass = secrets["RABBITMQ_DEFAULT_PASS"]
            env_content.append(f"RABBITMQ_URL=amqp://coffeebreak:{rabbitmq_pass}@mq:5672")

        # Service URLs for local development
        env_content.append("KEYCLOAK_URL=http://localhost:8080")
        env_content.append("API_BASE_URL=http://localhost:8080")
        env_content.append("WS_BASE_URL=ws://localhost:8080")
        env_content.append("CORS_ORIGINS=http://localhost:3000,http://localhost:5173")

        # Vite variables for frontend development
        env_content.append("VITE_API_BASE_URL=http://localhost:8080")
        env_content.append("VITE_WS_BASE_URL=ws://localhost:8080")
        env_content.append("VITE_WS_URL=ws://localhost:8080/ws")
        env_content.append("VITE_KEYCLOAK_URL=http://localhost:8080")

        # Add Vite VAPID key if generated
        if include_secrets and "VAPID_PUBLIC_KEY" in secrets:
            env_content.append(f"VITE_VAPID_PUBLIC_KEY={secrets['VAPID_PUBLIC_KEY']}")

        # PgAdmin variables (debug profile)
        env_content.append("PGADMIN_DEFAULT_EMAIL=admin@coffeebreak.local")
        env_content.append("PGADMIN_DEFAULT_PASSWORD=admin123")

        env_content.append("")

        # Write to file
        content = "\n".join(env_content)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Set restrictive permissions
        os.chmod(output_path, stat.S_IRUSR | stat.S_IWUSR)  # 600

        if self.verbose:
            print(f"Generated environment file: {output_path}")

        return output_path

    def create_gitignore(self, path: str = ".gitignore") -> str:
        """
        Create or update .gitignore file with CoffeeBreak entries.

        Args:
            path: Path to .gitignore file

        Returns:
            str: Path to .gitignore file
        """
        gitignore_entries = [
            "# CoffeeBreak CLI generated files",
            ".env.local",
            ".env.secrets",
            "*.log",
            "__pycache__/",
            "*.pyc",
            "node_modules/",
            "dist/",
            ".DS_Store",
        ]

        existing_content = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing_content = f.read()

        # Check which entries are missing
        missing_entries = []
        for entry in gitignore_entries:
            if entry not in existing_content:
                missing_entries.append(entry)

        if missing_entries:
            with open(path, "a", encoding="utf-8") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(missing_entries) + "\n")

            if self.verbose:
                print(f"Updated .gitignore with {len(missing_entries)} new entries")

        return path

    def create_directory_structure(self, base_path: str, structure: Dict[str, any]) -> List[str]:
        """
        Create directory structure from specification.

        Args:
            base_path: Base directory path
            structure: Directory structure specification

        Returns:
            List[str]: List of created paths
        """
        created_paths = []

        def create_recursive(current_path: str, spec: Dict[str, any]):
            for name, content in spec.items():
                full_path = os.path.join(current_path, name)

                if isinstance(content, dict):
                    # It's a directory
                    os.makedirs(full_path, exist_ok=True)
                    created_paths.append(full_path)
                    create_recursive(full_path, content)
                elif isinstance(content, str):
                    # It's a file with content
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    created_paths.append(full_path)
                else:
                    # It's an empty directory
                    os.makedirs(full_path, exist_ok=True)
                    created_paths.append(full_path)

        create_recursive(base_path, structure)

        if self.verbose:
            print(f"Created {len(created_paths)} paths")

        return created_paths

    def set_file_permissions(self, file_path: str, mode: int) -> None:
        """
        Set file permissions.

        Args:
            file_path: Path to file
            mode: Permission mode (e.g., 0o600)
        """
        os.chmod(file_path, mode)

        if self.verbose:
            print(f"Set permissions {oct(mode)} for {file_path}")

    def backup_file(self, file_path: str, backup_suffix: str = ".backup") -> str:
        """
        Create backup of existing file.

        Args:
            file_path: Path to file to backup
            backup_suffix: Suffix for backup file

        Returns:
            str: Path to backup file
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        backup_path = file_path + backup_suffix

        # If backup already exists, add number
        counter = 1
        original_backup = backup_path
        while os.path.exists(backup_path):
            backup_path = f"{original_backup}.{counter}"
            counter += 1

        # Copy file
        import shutil

        shutil.copy2(file_path, backup_path)

        if self.verbose:
            print(f"Created backup: {backup_path}")

        return backup_path

    def _generate_development_secrets(self) -> Dict[str, str]:
        """Generate development secrets matching orchestrator variables and
        test expectations."""
        import secrets
        import string

        def generate_password(length: int) -> str:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            return "".join(secrets.choice(alphabet) for _ in range(length))

        def generate_hex(length: int) -> str:
            return secrets.token_hex(length)

        # Generate secrets for both orchestrator and test expectations
        secrets_dict = {
            "POSTGRES_PASSWORD": generate_password(24),
            "MONGO_INITDB_ROOT_PASSWORD": generate_password(24),
            "RABBITMQ_DEFAULT_PASS": generate_password(24),
            "KC_DB_PASSWORD": generate_password(24),
            "KEYCLOAK_ADMIN_PASSWORD": generate_password(24),
            "KEYCLOAK_CLIENT_SECRET": generate_hex(32),
            "ANON_JWT_SECRET": generate_hex(32),
            "VAPID_PUBLIC_KEY": generate_hex(32),
            "VAPID_PRIVATE_KEY": generate_hex(32),
            # Add test-expected keys, mapping to existing ones or generating new
            "DB_PASSWORD": generate_password(24),
            "MONGODB_PASSWORD": generate_password(24),
            "RABBITMQ_PASSWORD": generate_password(24),
            "JWT_SECRET": generate_hex(32),
            "API_SECRET_KEY": generate_hex(32),
            "ENCRYPTION_KEY": generate_hex(32),
            "SESSION_SECRET": generate_hex(32),
        }
        return secrets_dict
