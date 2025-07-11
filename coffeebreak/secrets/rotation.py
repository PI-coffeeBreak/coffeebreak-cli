"""Secret rotation automation for CoffeeBreak production deployments."""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from coffeebreak.utils.errors import SecurityError

from .generator import SecretGenerator
from .manager import SecretManager


@dataclass
class RotationSchedule:
    """Represents a secret rotation schedule."""

    secret_name: str
    interval_days: int
    last_rotation: Optional[datetime] = None
    next_rotation: Optional[datetime] = None
    enabled: bool = True
    priority: str = "medium"  # low, medium, high, critical


class SecretRotationManager:
    """Manages automated secret rotation for production deployments."""

    def __init__(
        self,
        secret_manager: SecretManager,
        config_file: str = "/etc/coffeebreak/rotation.json",
        verbose: bool = False,
    ):
        """
        Initialize rotation manager.

        Args:
            secret_manager: Secret manager instance
            config_file: Path to rotation configuration file
            verbose: Enable verbose output
        """
        self.secret_manager = secret_manager
        self.config_file = config_file
        self.verbose = verbose
        self.generator = SecretGenerator(verbose=verbose)

        # Default rotation schedules
        self.default_schedules = {
            # Critical secrets - rotate more frequently
            "api_secret_key": RotationSchedule("api_secret_key", 30, priority="critical"),
            "session_secret": RotationSchedule("session_secret", 30, priority="critical"),
            "jwt_secret": RotationSchedule("jwt_secret", 30, priority="critical"),
            # High priority secrets
            "postgres_password": RotationSchedule("postgres_password", 90, priority="high"),
            "mongodb_password": RotationSchedule("mongodb_password", 90, priority="high"),
            "keycloak_admin_password": RotationSchedule("keycloak_admin_password", 90, priority="high"),
            # Medium priority secrets
            "rabbitmq_password": RotationSchedule("rabbitmq_password", 180, priority="medium"),
            "redis_password": RotationSchedule("redis_password", 180, priority="medium"),
            "backup_encryption_key": RotationSchedule("backup_encryption_key", 180, priority="medium"),
            # Lower priority secrets
            "monitoring_password": RotationSchedule("monitoring_password", 365, priority="low"),
            "ssl_session_ticket_key": RotationSchedule("ssl_session_ticket_key", 365, priority="low"),
        }

        # Load existing schedules
        self.schedules = self._load_schedules()

        # Rotation hooks
        self.pre_rotation_hooks: List[Callable] = []
        self.post_rotation_hooks: List[Callable] = []

    def _load_schedules(self) -> Dict[str, RotationSchedule]:
        """Load rotation schedules from configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    config_data = json.load(f)

                schedules = {}
                for name, data in config_data.get("schedules", {}).items():
                    schedule = RotationSchedule(
                        secret_name=data["secret_name"],
                        interval_days=data["interval_days"],
                        enabled=data.get("enabled", True),
                        priority=data.get("priority", "medium"),
                    )

                    # Parse datetime strings
                    if data.get("last_rotation"):
                        schedule.last_rotation = datetime.fromisoformat(data["last_rotation"])
                    if data.get("next_rotation"):
                        schedule.next_rotation = datetime.fromisoformat(data["next_rotation"])

                    schedules[name] = schedule

                # Merge with defaults for any missing schedules
                for name, default_schedule in self.default_schedules.items():
                    if name not in schedules:
                        schedules[name] = default_schedule

                return schedules

            else:
                # Return defaults and create config file
                self._save_schedules(self.default_schedules)
                return self.default_schedules.copy()

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not load rotation schedules: {e}")
            return self.default_schedules.copy()

    def _save_schedules(self, schedules: Dict[str, RotationSchedule]) -> None:
        """Save rotation schedules to configuration file."""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Convert schedules to serializable format
            config_data = {"schedules": {}, "last_updated": datetime.now().isoformat()}

            for name, schedule in schedules.items():
                config_data["schedules"][name] = {
                    "secret_name": schedule.secret_name,
                    "interval_days": schedule.interval_days,
                    "enabled": schedule.enabled,
                    "priority": schedule.priority,
                    "last_rotation": schedule.last_rotation.isoformat() if schedule.last_rotation else None,
                    "next_rotation": schedule.next_rotation.isoformat() if schedule.next_rotation else None,
                }

            # Write config file
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)

            # Set secure permissions
            os.chmod(self.config_file, 0o600)

        except Exception as e:
            raise SecurityError(f"Failed to save rotation schedules: {e}") from e

    def add_rotation_hook(self, hook: Callable, phase: str = "post") -> None:
        """
        Add a rotation hook function.

        Args:
            hook: Function to call during rotation
            phase: When to call (pre or post)
        """
        if phase == "pre":
            self.pre_rotation_hooks.append(hook)
        elif phase == "post":
            self.post_rotation_hooks.append(hook)
        else:
            raise ValueError("Phase must be 'pre' or 'post'")

    def calculate_next_rotation(self, schedule: RotationSchedule) -> datetime:
        """
        Calculate the next rotation time for a schedule.

        Args:
            schedule: Rotation schedule

        Returns:
            datetime: Next rotation time
        """
        if schedule.last_rotation:
            return schedule.last_rotation + timedelta(days=schedule.interval_days)
        else:
            # If never rotated, schedule for a random time within the interval
            # to avoid all secrets rotating at once
            import random

            days_offset = random.randint(1, schedule.interval_days)
            return datetime.now() + timedelta(days=days_offset)

    def update_schedule(self, secret_name: str, **kwargs) -> None:
        """
        Update a rotation schedule.

        Args:
            secret_name: Name of the secret
            **kwargs: Schedule parameters to update
        """
        try:
            if secret_name not in self.schedules:
                # Create new schedule
                self.schedules[secret_name] = RotationSchedule(
                    secret_name=secret_name,
                    interval_days=kwargs.get("interval_days", 180),
                )

            schedule = self.schedules[secret_name]

            # Update parameters
            for key, value in kwargs.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)

            # Recalculate next rotation if interval changed
            if "interval_days" in kwargs:
                schedule.next_rotation = self.calculate_next_rotation(schedule)

            # Save updated schedules
            self._save_schedules(self.schedules)

            if self.verbose:
                print(f"Updated rotation schedule for {secret_name}")

        except Exception as e:
            raise SecurityError(f"Failed to update rotation schedule for {secret_name}: {e}") from e

    def get_secrets_due_for_rotation(self) -> List[RotationSchedule]:
        """
        Get list of secrets that are due for rotation.

        Returns:
            List[RotationSchedule]: Secrets due for rotation
        """
        try:
            due_secrets = []
            current_time = datetime.now()

            for schedule in self.schedules.values():
                if not schedule.enabled:
                    continue

                # Calculate next rotation if not set
                if not schedule.next_rotation:
                    schedule.next_rotation = self.calculate_next_rotation(schedule)

                # Check if due
                if current_time >= schedule.next_rotation:
                    due_secrets.append(schedule)

            # Sort by priority and due date
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            due_secrets.sort(
                key=lambda s: (
                    priority_order.get(s.priority, 3),
                    s.next_rotation or datetime.min,
                )
            )

            return due_secrets

        except Exception as e:
            raise SecurityError(f"Failed to get secrets due for rotation: {e}") from e

    def rotate_secret(self, secret_name: str, force: bool = False) -> Dict[str, Any]:
        """
        Rotate a single secret.

        Args:
            secret_name: Name of the secret to rotate
            force: Force rotation even if not due

        Returns:
            Dict[str, Any]: Rotation results
        """
        try:
            if self.verbose:
                print(f"Rotating secret: {secret_name}")

            schedule = self.schedules.get(secret_name)
            if not schedule:
                raise SecurityError(f"No rotation schedule found for secret: {secret_name}")

            if not schedule.enabled and not force:
                raise SecurityError(f"Rotation is disabled for secret: {secret_name}")

            # Check if rotation is due (unless forced)
            if not force:
                if schedule.next_rotation and datetime.now() < schedule.next_rotation:
                    time_until_due = schedule.next_rotation - datetime.now()
                    raise SecurityError(f"Secret {secret_name} is not due for rotation (due in {time_until_due.days} days)")

            start_time = time.time()
            rotation_result = {
                "secret_name": secret_name,
                "start_time": datetime.now().isoformat(),
                "success": False,
                "error": None,
                "duration": 0,
                "old_value_length": 0,
                "new_value_length": 0,
            }

            try:
                # Execute pre-rotation hooks
                for hook in self.pre_rotation_hooks:
                    try:
                        hook(secret_name, "pre")
                    except Exception as e:
                        if self.verbose:
                            print(f"Pre-rotation hook failed: {e}")

                # Perform the rotation
                old_value = None
                try:
                    # Try to get old value for length comparison
                    if self.secret_manager.deployment_type == "standalone":
                        old_value = self.secret_manager.load_encrypted_secret(secret_name, "/etc/coffeebreak/secrets")
                        rotation_result["old_value_length"] = len(old_value)
                except Exception:
                    pass  # Old value not available, continue

                # Generate and deploy new secret
                new_value = self.secret_manager.rotate_secret(secret_name)
                rotation_result["new_value_length"] = len(new_value)

                # Update schedule
                schedule.last_rotation = datetime.now()
                schedule.next_rotation = self.calculate_next_rotation(schedule)

                # Execute post-rotation hooks
                for hook in self.post_rotation_hooks:
                    try:
                        hook(secret_name, "post", new_value)
                    except Exception as e:
                        if self.verbose:
                            print(f"Post-rotation hook failed: {e}")

                rotation_result["success"] = True

                if self.verbose:
                    print(f"Successfully rotated secret: {secret_name}")

            except Exception as e:
                rotation_result["error"] = str(e)
                raise

            finally:
                rotation_result["duration"] = time.time() - start_time
                rotation_result["end_time"] = datetime.now().isoformat()

                # Save updated schedules
                self._save_schedules(self.schedules)

            return rotation_result

        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            else:
                raise SecurityError(f"Failed to rotate secret {secret_name}: {e}") from e

    def rotate_due_secrets(self, max_rotations: int = 5) -> List[Dict[str, Any]]:
        """
        Rotate all secrets that are due for rotation.

        Args:
            max_rotations: Maximum number of secrets to rotate in one run

        Returns:
            List[Dict[str, Any]]: List of rotation results
        """
        try:
            due_secrets = self.get_secrets_due_for_rotation()

            if not due_secrets:
                if self.verbose:
                    print("No secrets are due for rotation")
                return []

            if self.verbose:
                print(f"Found {len(due_secrets)} secrets due for rotation")

            # Limit number of rotations
            secrets_to_rotate = due_secrets[:max_rotations]

            results = []
            for schedule in secrets_to_rotate:
                try:
                    result = self.rotate_secret(schedule.secret_name, force=True)
                    results.append(result)
                except Exception as e:
                    error_result = {
                        "secret_name": schedule.secret_name,
                        "success": False,
                        "error": str(e),
                        "start_time": datetime.now().isoformat(),
                    }
                    results.append(error_result)

                    if self.verbose:
                        print(f"Failed to rotate {schedule.secret_name}: {e}")

            if self.verbose:
                successful = sum(1 for r in results if r["success"])
                print(f"Completed rotation: {successful}/{len(results)} successful")

            return results

        except Exception as e:
            raise SecurityError(f"Failed to rotate due secrets: {e}") from e

    def emergency_rotation(self, secret_names: List[str], reason: str = "") -> List[Dict[str, Any]]:
        """
        Perform emergency rotation of specific secrets.

        Args:
            secret_names: List of secret names to rotate immediately
            reason: Reason for emergency rotation

        Returns:
            List[Dict[str, Any]]: List of rotation results
        """
        try:
            if self.verbose:
                print(f"Performing emergency rotation of {len(secret_names)} secrets")
                if reason:
                    print(f"Reason: {reason}")

            results = []

            for secret_name in secret_names:
                try:
                    result = self.rotate_secret(secret_name, force=True)
                    result["emergency"] = True
                    result["reason"] = reason
                    results.append(result)
                except Exception as e:
                    error_result = {
                        "secret_name": secret_name,
                        "success": False,
                        "error": str(e),
                        "emergency": True,
                        "reason": reason,
                        "start_time": datetime.now().isoformat(),
                    }
                    results.append(error_result)

            # Log emergency rotation
            self._log_emergency_rotation(secret_names, reason, results)

            return results

        except Exception as e:
            raise SecurityError(f"Failed to perform emergency rotation: {e}") from e

    def _log_emergency_rotation(self, secret_names: List[str], reason: str, results: List[Dict[str, Any]]) -> None:
        """Log emergency rotation event."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "emergency_rotation",
                "secret_names": secret_names,
                "reason": reason,
                "results": results,
                "successful_count": sum(1 for r in results if r["success"]),
                "failed_count": sum(1 for r in results if not r["success"]),
            }

            log_file = "/var/log/coffeebreak/rotation.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not log emergency rotation: {e}")

    def get_rotation_status(self) -> Dict[str, Any]:
        """
        Get comprehensive rotation status.

        Returns:
            Dict[str, Any]: Rotation status information
        """
        try:
            current_time = datetime.now()
            due_secrets = self.get_secrets_due_for_rotation()

            status = {
                "current_time": current_time.isoformat(),
                "total_secrets": len(self.schedules),
                "enabled_secrets": sum(1 for s in self.schedules.values() if s.enabled),
                "due_for_rotation": len(due_secrets),
                "schedules": {},
                "next_rotation": None,
                "overdue_secrets": [],
            }

            # Process each schedule
            next_rotation_time = None

            for name, schedule in self.schedules.items():
                if not schedule.next_rotation:
                    schedule.next_rotation = self.calculate_next_rotation(schedule)

                time_until_rotation = None
                if schedule.next_rotation:
                    time_until_rotation = (schedule.next_rotation - current_time).total_seconds()

                    if not next_rotation_time or schedule.next_rotation < next_rotation_time:
                        next_rotation_time = schedule.next_rotation

                schedule_info = {
                    "enabled": schedule.enabled,
                    "priority": schedule.priority,
                    "interval_days": schedule.interval_days,
                    "last_rotation": schedule.last_rotation.isoformat() if schedule.last_rotation else None,
                    "next_rotation": schedule.next_rotation.isoformat() if schedule.next_rotation else None,
                    "time_until_rotation_seconds": time_until_rotation,
                    "due_for_rotation": time_until_rotation is not None and time_until_rotation <= 0,
                }

                # Check if overdue (more than 7 days past due)
                if time_until_rotation is not None and time_until_rotation < -7 * 24 * 3600:
                    status["overdue_secrets"].append(name)

                status["schedules"][name] = schedule_info

            if next_rotation_time:
                status["next_rotation"] = next_rotation_time.isoformat()

            return status

        except Exception as e:
            raise SecurityError(f"Failed to get rotation status: {e}") from e

    def disable_rotation(self, secret_name: str) -> None:
        """
        Disable rotation for a specific secret.

        Args:
            secret_name: Name of the secret
        """
        try:
            if secret_name in self.schedules:
                self.schedules[secret_name].enabled = False
                self._save_schedules(self.schedules)

                if self.verbose:
                    print(f"Disabled rotation for secret: {secret_name}")
            else:
                raise SecurityError(f"Secret not found: {secret_name}")

        except Exception as e:
            raise SecurityError(f"Failed to disable rotation for {secret_name}: {e}") from e

    def enable_rotation(self, secret_name: str) -> None:
        """
        Enable rotation for a specific secret.

        Args:
            secret_name: Name of the secret
        """
        try:
            if secret_name in self.schedules:
                self.schedules[secret_name].enabled = True
                # Recalculate next rotation
                self.schedules[secret_name].next_rotation = self.calculate_next_rotation(self.schedules[secret_name])
                self._save_schedules(self.schedules)

                if self.verbose:
                    print(f"Enabled rotation for secret: {secret_name}")
            else:
                raise SecurityError(f"Secret not found: {secret_name}")

        except Exception as e:
            raise SecurityError(f"Failed to enable rotation for {secret_name}: {e}") from e
