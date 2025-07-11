"""Secure secret generation for CoffeeBreak production deployments."""

import base64
import secrets
import string
from typing import Any, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..utils.errors import SecurityError


class SecretGenerator:
    """Generates cryptographically secure secrets for production deployments."""

    def __init__(self, verbose: bool = False):
        """Initialize secret generator."""
        self.verbose = verbose
        self.alphabet_alphanumeric = string.ascii_letters + string.digits
        self.alphabet_safe = (
            string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"
        )
        self.alphabet_hex = string.hexdigits.lower()[:16]  # 0-9a-f

    def generate_password(
        self,
        length: int = 32,
        include_symbols: bool = True,
        exclude_ambiguous: bool = True,
    ) -> str:
        """
        Generate a secure password.

        Args:
            length: Password length
            include_symbols: Whether to include special symbols
            exclude_ambiguous: Whether to exclude ambiguous characters (0, O, l, 1, etc.)

        Returns:
            str: Secure password
        """
        try:
            if length < 8:
                raise SecurityError("Password length must be at least 8 characters")

            alphabet = self.alphabet_alphanumeric
            if include_symbols:
                alphabet = self.alphabet_safe

            if exclude_ambiguous:
                # Remove ambiguous characters
                ambiguous = "0O1lI"
                alphabet = "".join(c for c in alphabet if c not in ambiguous)

            # Ensure at least one character from each required category
            password = []

            # At least one lowercase letter
            password.append(secrets.choice(string.ascii_lowercase))

            # At least one uppercase letter
            password.append(secrets.choice(string.ascii_uppercase))

            # At least one digit
            password.append(secrets.choice(string.digits))

            if include_symbols:
                # At least one symbol
                symbols = "!@#$%^&*()-_=+[]{}|;:,.<>?"
                if exclude_ambiguous:
                    symbols = "".join(c for c in symbols if c not in ambiguous)
                password.append(secrets.choice(symbols))

            # Fill the rest randomly
            for _ in range(length - len(password)):
                password.append(secrets.choice(alphabet))

            # Shuffle the password
            secrets.SystemRandom().shuffle(password)

            return "".join(password)

        except Exception as e:
            raise SecurityError(f"Failed to generate password: {e}")

    def generate_api_key(self, length: int = 64) -> str:
        """
        Generate a secure API key.

        Args:
            length: Key length

        Returns:
            str: Secure API key
        """
        try:
            if length < 32:
                raise SecurityError("API key length must be at least 32 characters")

            # Generate random bytes and encode as URL-safe base64
            key_bytes = secrets.token_bytes(length // 2)
            api_key = base64.urlsafe_b64encode(key_bytes).decode("utf-8")

            # Ensure exact length
            if len(api_key) > length:
                api_key = api_key[:length]
            elif len(api_key) < length:
                # Pad with additional random characters
                additional = length - len(api_key)
                api_key += "".join(
                    secrets.choice(self.alphabet_alphanumeric)
                    for _ in range(additional)
                )

            return api_key

        except Exception as e:
            raise SecurityError(f"Failed to generate API key: {e}")

    def generate_secret_key(self, length: int = 128) -> str:
        """
        Generate a secure secret key for cryptographic operations.

        Args:
            length: Key length

        Returns:
            str: Secure secret key
        """
        try:
            if length < 64:
                raise SecurityError("Secret key length must be at least 64 characters")

            # Generate cryptographically secure random bytes
            key_bytes = secrets.token_bytes(length // 2)
            secret_key = key_bytes.hex()

            return secret_key

        except Exception as e:
            raise SecurityError(f"Failed to generate secret key: {e}")

    def generate_session_secret(self) -> str:
        """
        Generate a secure session secret for web applications.

        Returns:
            str: Secure session secret
        """
        try:
            # Generate 256-bit secret for session management
            return secrets.token_hex(32)

        except Exception as e:
            raise SecurityError(f"Failed to generate session secret: {e}")

    def generate_encryption_key(self) -> bytes:
        """
        Generate a Fernet encryption key.

        Returns:
            bytes: Fernet encryption key
        """
        try:
            return Fernet.generate_key()

        except Exception as e:
            raise SecurityError(f"Failed to generate encryption key: {e}")

    def generate_salt(self, length: int = 32) -> str:
        """
        Generate a cryptographic salt.

        Args:
            length: Salt length in bytes

        Returns:
            str: Hex-encoded salt
        """
        try:
            salt_bytes = secrets.token_bytes(length)
            return salt_bytes.hex()

        except Exception as e:
            raise SecurityError(f"Failed to generate salt: {e}")

    def generate_database_secrets(self) -> Dict[str, str]:
        """
        Generate all database-related secrets.

        Returns:
            Dict[str, str]: Database secrets
        """
        try:
            secrets_dict = {
                "postgres_password": self.generate_password(32, include_symbols=False),
                "mongodb_password": self.generate_password(32, include_symbols=False),
                "postgres_replication_password": self.generate_password(
                    32, include_symbols=False
                ),
                "mongodb_replica_key": self.generate_secret_key(64),
            }

            if self.verbose:
                print("Generated database secrets")

            return secrets_dict

        except Exception as e:
            raise SecurityError(f"Failed to generate database secrets: {e}")

    def generate_application_secrets(self) -> Dict[str, str]:
        """
        Generate all application-related secrets.

        Returns:
            Dict[str, str]: Application secrets
        """
        try:
            secrets_dict = {
                "api_secret_key": self.generate_secret_key(128),
                "session_secret": self.generate_session_secret(),
                "jwt_secret": self.generate_secret_key(64),
                "encryption_key": self.generate_encryption_key().decode("utf-8"),
                "csrf_secret": self.generate_secret_key(32),
                "webhook_secret": self.generate_secret_key(64),
            }

            if self.verbose:
                print("Generated application secrets")

            return secrets_dict

        except Exception as e:
            raise SecurityError(f"Failed to generate application secrets: {e}")

    def generate_service_secrets(self) -> Dict[str, str]:
        """
        Generate all service-related secrets.

        Returns:
            Dict[str, str]: Service secrets
        """
        try:
            secrets_dict = {
                "rabbitmq_password": self.generate_password(32, include_symbols=False),
                "keycloak_admin_password": self.generate_password(
                    24, include_symbols=False
                ),
                "keycloak_db_password": self.generate_password(
                    32, include_symbols=False
                ),
                "redis_password": self.generate_password(32, include_symbols=False),
                "monitoring_password": self.generate_password(
                    24, include_symbols=False
                ),
            }

            if self.verbose:
                print("Generated service secrets")

            return secrets_dict

        except Exception as e:
            raise SecurityError(f"Failed to generate service secrets: {e}")

    def generate_ssl_secrets(self) -> Dict[str, str]:
        """
        Generate SSL/TLS related secrets.

        Returns:
            Dict[str, str]: SSL secrets
        """
        try:
            secrets_dict = {
                "ssl_dhparam_bits": "4096",
                "ssl_session_ticket_key": self.generate_secret_key(96),  # 48 bytes hex
                "ssl_stapling_secret": self.generate_secret_key(32),
            }

            if self.verbose:
                print("Generated SSL secrets")

            return secrets_dict

        except Exception as e:
            raise SecurityError(f"Failed to generate SSL secrets: {e}")

    def generate_backup_secrets(self) -> Dict[str, str]:
        """
        Generate backup and recovery secrets.

        Returns:
            Dict[str, str]: Backup secrets
        """
        try:
            secrets_dict = {
                "backup_encryption_key": self.generate_encryption_key().decode("utf-8"),
                "backup_access_key": self.generate_api_key(40),
                "backup_secret_key": self.generate_secret_key(80),
            }

            if self.verbose:
                print("Generated backup secrets")

            return secrets_dict

        except Exception as e:
            raise SecurityError(f"Failed to generate backup secrets: {e}")

    def generate_all_secrets(self) -> Dict[str, str]:
        """
        Generate all production secrets.

        Returns:
            Dict[str, str]: All secrets
        """
        try:
            if self.verbose:
                print("Generating all production secrets...")

            all_secrets = {}

            # Generate all categories of secrets
            all_secrets.update(self.generate_database_secrets())
            all_secrets.update(self.generate_application_secrets())
            all_secrets.update(self.generate_service_secrets())
            all_secrets.update(self.generate_ssl_secrets())
            all_secrets.update(self.generate_backup_secrets())

            if self.verbose:
                print(f"Generated {len(all_secrets)} production secrets")

            return all_secrets

        except Exception as e:
            raise SecurityError(f"Failed to generate all secrets: {e}")

    def validate_secret_strength(
        self, secret: str, min_length: int = 16
    ) -> Dict[str, Any]:
        """
        Validate the strength of a secret.

        Args:
            secret: Secret to validate
            min_length: Minimum required length

        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            validation = {
                "valid": True,
                "score": 0,
                "issues": [],
                "recommendations": [],
            }

            # Length check
            if len(secret) < min_length:
                validation["valid"] = False
                validation["issues"].append(
                    f"Secret is too short (minimum: {min_length})"
                )
            else:
                validation["score"] += min(len(secret) * 2, 50)

            # Character diversity
            has_lower = any(c.islower() for c in secret)
            has_upper = any(c.isupper() for c in secret)
            has_digit = any(c.isdigit() for c in secret)
            has_symbol = any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in secret)

            char_types = sum([has_lower, has_upper, has_digit, has_symbol])
            validation["score"] += char_types * 10

            if char_types < 3:
                validation["issues"].append(
                    "Secret should contain at least 3 character types"
                )
                validation["recommendations"].append(
                    "Include uppercase, lowercase, digits, and symbols"
                )

            # Entropy check (simplified)
            unique_chars = len(set(secret))
            if unique_chars < len(secret) * 0.7:
                validation["issues"].append("Secret has low character diversity")
                validation["recommendations"].append("Avoid repeated characters")
            else:
                validation["score"] += 20

            # Common patterns check
            common_patterns = ["123", "abc", "password", "admin", "qwerty"]
            for pattern in common_patterns:
                if pattern.lower() in secret.lower():
                    validation["valid"] = False
                    validation["issues"].append(
                        f"Secret contains common pattern: {pattern}"
                    )

            # Final score adjustment
            if validation["valid"] and len(validation["issues"]) == 0:
                validation["score"] = min(validation["score"], 100)
            else:
                validation["score"] = max(validation["score"] - 30, 0)

            return validation

        except Exception as e:
            raise SecurityError(f"Failed to validate secret strength: {e}")

    def derive_key_from_password(
        self, password: str, salt: bytes, iterations: int = 100000
    ) -> bytes:
        """
        Derive a key from a password using PBKDF2.

        Args:
            password: Password to derive from
            salt: Salt bytes
            iterations: Number of iterations

        Returns:
            bytes: Derived key
        """
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key = kdf.derive(password.encode("utf-8"))
            return key

        except Exception as e:
            raise SecurityError(f"Failed to derive key from password: {e}")

    def generate_secure_filename(self, extension: str = "") -> str:
        """
        Generate a secure filename.

        Args:
            extension: File extension (with or without dot)

        Returns:
            str: Secure filename
        """
        try:
            # Generate 16 random bytes, encode as hex
            random_name = secrets.token_hex(16)

            if extension:
                if not extension.startswith("."):
                    extension = "." + extension
                return random_name + extension

            return random_name

        except Exception as e:
            raise SecurityError(f"Failed to generate secure filename: {e}")

    def generate_nonce(self, length: int = 16) -> str:
        """
        Generate a cryptographic nonce.

        Args:
            length: Nonce length in bytes

        Returns:
            str: Hex-encoded nonce
        """
        try:
            return secrets.token_hex(length)

        except Exception as e:
            raise SecurityError(f"Failed to generate nonce: {e}")
