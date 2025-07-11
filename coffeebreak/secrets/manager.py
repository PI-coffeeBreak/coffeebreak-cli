"""Secure secret management for CoffeeBreak production deployments."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet

from ..utils.errors import SecurityError
from .generator import SecretGenerator


class SecretManager:
    """Manages secrets for production deployments using Docker Secrets or encrypted files."""

    def __init__(
        self,
        deployment_type: str = "docker",
        encryption_key: Optional[bytes] = None,
        verbose: bool = False,
    ):
        """
        Initialize secret manager.

        Args:
            deployment_type: Type of deployment (docker, standalone)
            encryption_key: Key for encrypting secrets (if not using Docker Secrets)
            verbose: Enable verbose output
        """
        self.deployment_type = deployment_type
        self.verbose = verbose
        self.generator = SecretGenerator(verbose=verbose)

        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            self.cipher = None

    def create_docker_secret(self, name: str, value: str) -> bool:
        """
        Create a Docker secret.

        Args:
            name: Secret name
            value: Secret value

        Returns:
            bool: True if created successfully
        """
        try:
            if self.verbose:
                print(f"Creating Docker secret: {name}")

            # Create temporary file with secret value
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
                tmp_file.write(value)
                tmp_file_path = tmp_file.name

            try:
                # Create Docker secret
                result = subprocess.run(
                    ["docker", "secret", "create", name, tmp_file_path],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    if self.verbose:
                        print(f"Successfully created Docker secret: {name}")
                    return True
                else:
                    # Check if secret already exists
                    if "already exists" in result.stderr:
                        if self.verbose:
                            print(f"Docker secret already exists: {name}")
                        return True
                    else:
                        raise SecurityError(
                            f"Failed to create Docker secret {name}: {result.stderr}"
                        )

            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)

        except subprocess.FileNotFoundError:
            raise SecurityError("Docker is not available for secret management")
        except Exception as e:
            raise SecurityError(f"Failed to create Docker secret {name}: {e}")

    def update_docker_secret(self, name: str, value: str) -> bool:
        """
        Update a Docker secret by removing and recreating it.

        Args:
            name: Secret name
            value: New secret value

        Returns:
            bool: True if updated successfully
        """
        try:
            if self.verbose:
                print(f"Updating Docker secret: {name}")

            # Remove existing secret
            subprocess.run(
                ["docker", "secret", "rm", name], capture_output=True, text=True
            )

            # Create new secret
            return self.create_docker_secret(name, value)

        except Exception as e:
            raise SecurityError(f"Failed to update Docker secret {name}: {e}")

    def remove_docker_secret(self, name: str) -> bool:
        """
        Remove a Docker secret.

        Args:
            name: Secret name

        Returns:
            bool: True if removed successfully
        """
        try:
            if self.verbose:
                print(f"Removing Docker secret: {name}")

            result = subprocess.run(
                ["docker", "secret", "rm", name], capture_output=True, text=True
            )

            if result.returncode == 0:
                if self.verbose:
                    print(f"Successfully removed Docker secret: {name}")
                return True
            else:
                if "not found" in result.stderr:
                    if self.verbose:
                        print(f"Docker secret not found: {name}")
                    return True
                else:
                    raise SecurityError(
                        f"Failed to remove Docker secret {name}: {result.stderr}"
                    )

        except Exception as e:
            raise SecurityError(f"Failed to remove Docker secret {name}: {e}")

    def list_docker_secrets(self) -> List[str]:
        """
        List all Docker secrets.

        Returns:
            List[str]: List of secret names
        """
        try:
            result = subprocess.run(
                ["docker", "secret", "ls", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                secrets = [
                    line.strip() for line in result.stdout.split("\n") if line.strip()
                ]
                return secrets
            else:
                raise SecurityError(f"Failed to list Docker secrets: {result.stderr}")

        except subprocess.FileNotFoundError:
            raise SecurityError("Docker is not available for secret management")
        except Exception as e:
            raise SecurityError(f"Failed to list Docker secrets: {e}")

    def save_encrypted_secret(self, name: str, value: str, secrets_dir: str) -> str:
        """
        Save a secret as an encrypted file.

        Args:
            name: Secret name
            value: Secret value
            secrets_dir: Directory to save secrets

        Returns:
            str: Path to encrypted secret file
        """
        try:
            if not self.cipher:
                raise SecurityError("No encryption key provided for file-based secrets")

            if self.verbose:
                print(f"Saving encrypted secret: {name}")

            # Ensure secrets directory exists
            Path(secrets_dir).mkdir(parents=True, exist_ok=True)

            # Encrypt the secret value
            encrypted_value = self.cipher.encrypt(value.encode("utf-8"))

            # Save to file
            secret_file = os.path.join(secrets_dir, f"{name}.enc")
            with open(secret_file, "wb") as f:
                f.write(encrypted_value)

            # Set secure file permissions (owner read/write only)
            os.chmod(secret_file, 0o600)

            if self.verbose:
                print(f"Saved encrypted secret to: {secret_file}")

            return secret_file

        except Exception as e:
            raise SecurityError(f"Failed to save encrypted secret {name}: {e}")

    def load_encrypted_secret(self, name: str, secrets_dir: str) -> str:
        """
        Load and decrypt a secret from file.

        Args:
            name: Secret name
            secrets_dir: Directory containing secrets

        Returns:
            str: Decrypted secret value
        """
        try:
            if not self.cipher:
                raise SecurityError("No encryption key provided for file-based secrets")

            secret_file = os.path.join(secrets_dir, f"{name}.enc")

            if not os.path.exists(secret_file):
                raise SecurityError(f"Secret file not found: {secret_file}")

            # Read encrypted secret
            with open(secret_file, "rb") as f:
                encrypted_value = f.read()

            # Decrypt the secret
            decrypted_value = self.cipher.decrypt(encrypted_value)

            return decrypted_value.decode("utf-8")

        except Exception as e:
            raise SecurityError(f"Failed to load encrypted secret {name}: {e}")

    def save_plain_secret(self, name: str, value: str, secrets_dir: str) -> str:
        """
        Save a secret as a plain text file (for systemd services).

        Args:
            name: Secret name
            value: Secret value
            secrets_dir: Directory to save secrets

        Returns:
            str: Path to secret file
        """
        try:
            if self.verbose:
                print(f"Saving plain secret: {name}")

            # Ensure secrets directory exists
            Path(secrets_dir).mkdir(parents=True, exist_ok=True)

            # Save to file
            secret_file = os.path.join(secrets_dir, name)
            with open(secret_file, "w") as f:
                f.write(value)

            # Set secure file permissions (owner read only)
            os.chmod(secret_file, 0o400)

            if self.verbose:
                print(f"Saved plain secret to: {secret_file}")

            return secret_file

        except Exception as e:
            raise SecurityError(f"Failed to save plain secret {name}: {e}")

    def deploy_all_secrets(
        self, secrets: Dict[str, str], secrets_dir: str = "/etc/coffeebreak/secrets"
    ) -> Dict[str, Any]:
        """
        Deploy all secrets using the appropriate method for the deployment type.

        Args:
            secrets: Dictionary of secret names and values
            secrets_dir: Directory for file-based secrets

        Returns:
            Dict[str, Any]: Deployment results
        """
        try:
            if self.verbose:
                print(
                    f"Deploying {len(secrets)} secrets for {self.deployment_type} deployment"
                )

            results = {
                "deployment_type": self.deployment_type,
                "total_secrets": len(secrets),
                "successful": 0,
                "failed": 0,
                "errors": [],
            }

            for name, value in secrets.items():
                try:
                    if self.deployment_type == "docker":
                        # Use Docker secrets
                        if self.create_docker_secret(f"coffeebreak_{name}", value):
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(
                                f"Failed to create Docker secret: {name}"
                            )

                    elif self.deployment_type == "standalone":
                        # Use file-based secrets
                        if self.cipher:
                            # Encrypted files
                            self.save_encrypted_secret(name, value, secrets_dir)
                        else:
                            # Plain text files (less secure but compatible with systemd)
                            self.save_plain_secret(name, value, secrets_dir)

                        results["successful"] += 1

                    else:
                        raise SecurityError(
                            f"Unknown deployment type: {self.deployment_type}"
                        )

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to deploy secret {name}: {e}")

            if self.verbose:
                print(
                    f"Successfully deployed {results['successful']}/{results['total_secrets']} secrets"
                )
                if results["failed"] > 0:
                    print(f"Failed to deploy {results['failed']} secrets")

            return results

        except Exception as e:
            raise SecurityError(f"Failed to deploy secrets: {e}")

    def rotate_secret(
        self, name: str, secrets_dir: str = "/etc/coffeebreak/secrets"
    ) -> str:
        """
        Rotate a single secret by generating a new value.

        Args:
            name: Secret name
            secrets_dir: Directory for file-based secrets

        Returns:
            str: New secret value
        """
        try:
            if self.verbose:
                print(f"Rotating secret: {name}")

            # Generate new secret value based on type
            if "password" in name.lower():
                new_value = self.generator.generate_password(32, include_symbols=False)
            elif "key" in name.lower() or "secret" in name.lower():
                new_value = self.generator.generate_secret_key(128)
            elif "session" in name.lower():
                new_value = self.generator.generate_session_secret()
            else:
                # Default to secure password
                new_value = self.generator.generate_password(32)

            # Deploy the new secret
            if self.deployment_type == "docker":
                self.update_docker_secret(f"coffeebreak_{name}", new_value)
            elif self.deployment_type == "standalone":
                if self.cipher:
                    self.save_encrypted_secret(name, new_value, secrets_dir)
                else:
                    self.save_plain_secret(name, new_value, secrets_dir)

            if self.verbose:
                print(f"Successfully rotated secret: {name}")

            return new_value

        except Exception as e:
            raise SecurityError(f"Failed to rotate secret {name}: {e}")

    def rotate_all_secrets(
        self, secret_names: List[str], secrets_dir: str = "/etc/coffeebreak/secrets"
    ) -> Dict[str, str]:
        """
        Rotate multiple secrets.

        Args:
            secret_names: List of secret names to rotate
            secrets_dir: Directory for file-based secrets

        Returns:
            Dict[str, str]: New secret values
        """
        try:
            if self.verbose:
                print(f"Rotating {len(secret_names)} secrets")

            new_secrets = {}

            for name in secret_names:
                try:
                    new_value = self.rotate_secret(name, secrets_dir)
                    new_secrets[name] = new_value
                except Exception as e:
                    if self.verbose:
                        print(f"Failed to rotate secret {name}: {e}")
                    continue

            if self.verbose:
                print(
                    f"Successfully rotated {len(new_secrets)}/{len(secret_names)} secrets"
                )

            return new_secrets

        except Exception as e:
            raise SecurityError(f"Failed to rotate secrets: {e}")

    def backup_secrets(
        self,
        secrets_dir: str = "/etc/coffeebreak/secrets",
        backup_path: str = "/opt/coffeebreak/backups/secrets",
    ) -> str:
        """
        Create a backup of all secrets.

        Args:
            secrets_dir: Directory containing secrets
            backup_path: Path for backup file

        Returns:
            str: Path to backup file
        """
        try:
            if self.verbose:
                print("Creating secrets backup")

            # Ensure backup directory exists
            Path(os.path.dirname(backup_path)).mkdir(parents=True, exist_ok=True)

            if self.deployment_type == "docker":
                # For Docker secrets, we can't extract values, so just backup the names
                secret_names = self.list_docker_secrets()
                backup_data = {
                    "type": "docker_secrets",
                    "secret_names": secret_names,
                    "timestamp": subprocess.run(
                        ["date", "-Iseconds"], capture_output=True, text=True
                    ).stdout.strip(),
                }

                backup_file = f"{backup_path}_names.json"
                with open(backup_file, "w") as f:
                    json.dump(backup_data, f, indent=2)

            elif self.deployment_type == "standalone":
                # For file-based secrets, create encrypted archive
                import tarfile

                backup_file = f"{backup_path}.tar.gz"

                with tarfile.open(backup_file, "w:gz") as tar:
                    tar.add(secrets_dir, arcname="secrets")

            # Set secure permissions on backup
            os.chmod(backup_file, 0o600)

            if self.verbose:
                print(f"Created secrets backup: {backup_file}")

            return backup_file

        except Exception as e:
            raise SecurityError(f"Failed to backup secrets: {e}")

    def validate_secrets_deployment(
        self, secrets_dir: str = "/etc/coffeebreak/secrets"
    ) -> Dict[str, Any]:
        """
        Validate that all required secrets are properly deployed.

        Args:
            secrets_dir: Directory containing secrets

        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            if self.verbose:
                print("Validating secrets deployment")

            # Required secrets for production
            required_secrets = [
                "postgres_password",
                "mongodb_password",
                "rabbitmq_password",
                "keycloak_admin_password",
                "api_secret_key",
                "session_secret",
            ]

            validation = {
                "valid": True,
                "total_required": len(required_secrets),
                "found": 0,
                "missing": [],
                "errors": [],
            }

            for secret_name in required_secrets:
                try:
                    if self.deployment_type == "docker":
                        # Check if Docker secret exists
                        docker_secret_name = f"coffeebreak_{secret_name}"
                        all_secrets = self.list_docker_secrets()
                        if docker_secret_name in all_secrets:
                            validation["found"] += 1
                        else:
                            validation["missing"].append(secret_name)
                            validation["valid"] = False

                    elif self.deployment_type == "standalone":
                        # Check if secret file exists
                        if self.cipher:
                            secret_file = os.path.join(
                                secrets_dir, f"{secret_name}.enc"
                            )
                        else:
                            secret_file = os.path.join(secrets_dir, secret_name)

                        if os.path.exists(secret_file):
                            validation["found"] += 1
                        else:
                            validation["missing"].append(secret_name)
                            validation["valid"] = False

                except Exception as e:
                    validation["errors"].append(
                        f"Error checking secret {secret_name}: {e}"
                    )
                    validation["valid"] = False

            if self.verbose:
                print(
                    f"Found {validation['found']}/{validation['total_required']} required secrets"
                )
                if validation["missing"]:
                    print(f"Missing secrets: {validation['missing']}")

            return validation

        except Exception as e:
            raise SecurityError(f"Failed to validate secrets deployment: {e}")
