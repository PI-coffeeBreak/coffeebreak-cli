"""Error handling utilities for CoffeeBreak CLI."""

import sys
import traceback
from typing import Optional

import click


class CoffeeBreakError(Exception):
    """Base exception for CoffeeBreak CLI errors."""

    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        suggestions: Optional[list] = None,
    ):
        self.message = message
        self.details = details
        self.suggestions = suggestions or []
        super().__init__(message)


class ConfigurationError(CoffeeBreakError):
    """Raised when configuration is invalid or missing."""

    pass


class CoffeeBreakEnvironmentError(CoffeeBreakError):
    """Raised when environment setup fails."""

    pass


# Legacy alias for compatibility
EnvironmentError = CoffeeBreakEnvironmentError


class DevelopmentEnvironmentError(CoffeeBreakEnvironmentError):
    """Raised when development environment setup fails."""

    pass


class PluginEnvironmentError(CoffeeBreakEnvironmentError):
    """Raised when plugin environment setup fails."""

    pass


class ProductionEnvironmentError(CoffeeBreakEnvironmentError):
    """Raised when production environment setup fails."""

    pass


class DockerError(CoffeeBreakError):
    """Raised when Docker operations fail."""

    pass


class GitError(CoffeeBreakError):
    """Raised when Git operations fail."""

    pass


class NetworkError(CoffeeBreakError):
    """Raised when network operations fail."""

    pass


class PluginError(CoffeeBreakError):
    """Raised when plugin operations fail."""

    pass


class ValidationError(CoffeeBreakError):
    """Raised when validation fails."""

    pass


class SecurityError(CoffeeBreakError):
    """Raised when security operations fail."""

    pass


class SSLError(CoffeeBreakError):
    """Raised when SSL certificate operations fail."""

    pass


class ErrorHandler:
    """Handles and formats errors for user-friendly display."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def handle_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Handle and display error with appropriate formatting.

        Args:
            error: Exception to handle
            context: Optional context about when/where error occurred
        """
        if isinstance(error, CoffeeBreakError):
            self._handle_coffeebreak_error(error, context)
        else:
            self._handle_generic_error(error, context)

    def _handle_coffeebreak_error(self, error: CoffeeBreakError, context: Optional[str]) -> None:
        """Handle CoffeeBreak-specific errors."""
        # Main error message
        click.echo(f"✗ {error.message}", err=True)

        # Add context if provided
        if context:
            click.echo(f"Context: {context}", err=True)

        # Add details if available
        if error.details:
            click.echo(f"Details: {error.details}", err=True)

        # Add suggestions if available
        if error.suggestions:
            click.echo("\nSuggestions:", err=True)
            for suggestion in error.suggestions:
                click.echo(f"  • {suggestion}", err=True)

        # Add verbose traceback if requested
        if self.verbose:
            click.echo("\nFull traceback:", err=True)
            traceback.print_exc()

    def _handle_generic_error(self, error: Exception, context: Optional[str]) -> None:
        """Handle generic Python exceptions."""
        error_type = type(error).__name__

        # Format error message based on type
        if isinstance(error, FileNotFoundError):
            message = f"File not found: {error}"
            suggestions = [
                "Check that the file path is correct",
                "Ensure the file exists and is readable",
            ]
        elif isinstance(error, PermissionError):
            message = f"Permission denied: {error}"
            suggestions = [
                "Check file/directory permissions",
                "Try running with appropriate privileges",
            ]
        elif isinstance(error, ConnectionError):
            message = f"Connection failed: {error}"
            suggestions = [
                "Check your internet connection",
                "Verify that the target service is running",
                "Check firewall settings",
            ]
        else:
            message = f"{error_type}: {error}"
            suggestions = []

        # Display error
        click.echo(f"✗ {message}", err=True)

        if context:
            click.echo(f"Context: {context}", err=True)

        if suggestions:
            click.echo("\nSuggestions:", err=True)
            for suggestion in suggestions:
                click.echo(f"  • {suggestion}", err=True)

        if self.verbose:
            click.echo("\nFull traceback:", err=True)
            traceback.print_exc()

    def exit_with_error(self, error: Exception, context: Optional[str] = None, exit_code: int = 1) -> None:
        """Handle error and exit with specified code."""
        self.handle_error(error, context)
        sys.exit(exit_code)


def create_error_suggestions(error_type: str, **kwargs) -> list:
    """
    Create contextual error suggestions based on error type and context.

    Args:
        error_type: Type of error
        **kwargs: Additional context information

    Returns:
        list: List of suggestion strings
    """
    suggestions = {
        "docker_not_running": [
            "Start Docker Desktop or Docker daemon",
            "Check that Docker is installed and accessible",
            "Verify Docker permissions for current user",
        ],
        "git_auth_failed": [
            "Check your SSH keys configuration",
            "Verify personal access token if using HTTPS",
            "Ensure you have access to the repository",
        ],
        "repository_not_found": [
            "Verify the repository URL is correct",
            "Check that the repository exists and is accessible",
            "Ensure you have read permissions for the repository",
        ],
        "network_unreachable": [
            "Check your internet connection",
            "Verify DNS settings",
            "Check if you're behind a proxy or firewall",
        ],
        "configuration_invalid": [
            "Check YAML syntax in configuration file",
            "Verify all required fields are present",
            "Validate configuration values are correct",
        ],
        "service_unhealthy": [
            "Check service logs for error messages",
            "Verify service configuration",
            "Ensure required ports are available",
        ],
    }

    return suggestions.get(error_type, [])


def format_validation_errors(errors: list) -> str:
    """
    Format validation errors for display.

    Args:
        errors: List of validation error messages

    Returns:
        str: Formatted error message
    """
    if not errors:
        return "No validation errors"

    if len(errors) == 1:
        return f"Validation error: {errors[0]}"

    formatted = "Validation errors:\n"
    for i, error in enumerate(errors, 1):
        formatted += f"  {i}. {error}\n"

    return formatted.strip()


def safe_operation(operation_name: str, verbose: bool = False):
    """
    Decorator for safely executing operations with error handling.

    Args:
        operation_name: Name of the operation for error context
        verbose: Whether to show verbose error information
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler = ErrorHandler(verbose=verbose)
                error_handler.exit_with_error(e, context=operation_name)

        return wrapper

    return decorator
