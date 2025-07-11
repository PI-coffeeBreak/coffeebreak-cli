"""Tests for error handling system."""

from unittest.mock import patch

import click
from click.testing import CliRunner

from coffeebreak.utils.errors import (
    CoffeeBreakError,
    ConfigurationError,
    DockerError,
    ErrorHandler,
    GitError,
    create_error_suggestions,
    format_validation_errors,
    safe_operation,
)


class TestCoffeeBreakError:
    """Test custom error classes."""

    def test_coffeebreak_error_basic(self):
        """Test basic CoffeeBreakError functionality."""
        error = CoffeeBreakError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details is None
        assert error.suggestions == []

    def test_coffeebreak_error_with_details(self):
        """Test CoffeeBreakError with details and suggestions."""
        suggestions = ["Try this", "Or try that"]
        error = CoffeeBreakError(
            "Test error", details="Detailed explanation", suggestions=suggestions
        )

        assert error.message == "Test error"
        assert error.details == "Detailed explanation"
        assert error.suggestions == suggestions

    def test_specific_error_types(self):
        """Test specific error type inheritance."""
        config_error = ConfigurationError("Config error")
        git_error = GitError("Git error")
        docker_error = DockerError("Docker error")

        assert isinstance(config_error, CoffeeBreakError)
        assert isinstance(git_error, CoffeeBreakError)
        assert isinstance(docker_error, CoffeeBreakError)


class TestErrorHandler:
    """Test error handler functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = ErrorHandler(verbose=False)
        self.verbose_handler = ErrorHandler(verbose=True)

    def test_handle_coffeebreak_error(self):
        """Test handling CoffeeBreak-specific errors."""
        error = CoffeeBreakError(
            "Test error message",
            details="Error details",
            suggestions=["Suggestion 1", "Suggestion 2"],
        )

        with patch("click.echo") as mock_echo:
            self.handler.handle_error(error, "Test context")

            # Verify error message was displayed
            assert mock_echo.call_count >= 4  # Error, context, details, suggestions

            # Check that error symbol and message appear
            error_calls = [
                call for call in mock_echo.call_args_list if "✗" in str(call)
            ]
            assert len(error_calls) > 0

    def test_handle_generic_error_file_not_found(self):
        """Test handling FileNotFoundError."""
        error = FileNotFoundError("test.txt not found")

        with patch("click.echo") as mock_echo:
            self.handler.handle_error(error)

            # Should display formatted error message
            assert mock_echo.called
            error_message = str(mock_echo.call_args_list[0])
            assert "File not found" in error_message

    def test_handle_generic_error_permission_denied(self):
        """Test handling PermissionError."""
        error = PermissionError("Permission denied for file")

        with patch("click.echo") as mock_echo:
            self.handler.handle_error(error)

            assert mock_echo.called
            error_message = str(mock_echo.call_args_list[0])
            assert "Permission denied" in error_message

    def test_handle_error_with_verbose(self):
        """Test error handling with verbose output."""
        error = CoffeeBreakError("Test error")

        with patch("click.echo") as mock_echo:
            with patch("traceback.print_exc") as mock_traceback:
                self.verbose_handler.handle_error(error)

                # Should print traceback in verbose mode
                mock_traceback.assert_called_once()

    def test_exit_with_error(self):
        """Test exit_with_error functionality."""
        error = CoffeeBreakError("Fatal error")

        with patch("click.echo"):
            with patch("sys.exit") as mock_exit:
                self.handler.exit_with_error(error, exit_code=2)

                mock_exit.assert_called_once_with(2)


class TestErrorUtilities:
    """Test error utility functions."""

    def test_create_error_suggestions_docker(self):
        """Test Docker error suggestions."""
        suggestions = create_error_suggestions("docker_not_running")

        assert len(suggestions) > 0
        assert any("Docker" in suggestion for suggestion in suggestions)

    def test_create_error_suggestions_git(self):
        """Test Git error suggestions."""
        suggestions = create_error_suggestions("git_auth_failed")

        assert len(suggestions) > 0
        assert any(
            "SSH" in suggestion or "token" in suggestion for suggestion in suggestions
        )

    def test_create_error_suggestions_unknown(self):
        """Test suggestions for unknown error type."""
        suggestions = create_error_suggestions("unknown_error_type")

        assert suggestions == []

    def test_format_validation_errors_single(self):
        """Test formatting single validation error."""
        errors = ["Field 'name' is required"]

        result = format_validation_errors(errors)

        assert "Validation error:" in result
        assert "Field 'name' is required" in result

    def test_format_validation_errors_multiple(self):
        """Test formatting multiple validation errors."""
        errors = [
            "Field 'name' is required",
            "Field 'version' must be a string",
            "Invalid URL format",
        ]

        result = format_validation_errors(errors)

        assert "Validation errors:" in result
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_format_validation_errors_empty(self):
        """Test formatting empty validation errors."""
        errors = []

        result = format_validation_errors(errors)

        assert result == "No validation errors"

    def test_safe_operation_decorator_success(self):
        """Test safe_operation decorator with successful operation."""

        @safe_operation("test operation")
        def successful_operation():
            return "success"

        result = successful_operation()
        assert result == "success"

    def test_safe_operation_decorator_failure(self):
        """Test safe_operation decorator with failing operation."""

        @safe_operation("test operation")
        def failing_operation():
            raise ValueError("Test error")

        with patch("sys.exit") as mock_exit:
            with patch("click.echo"):
                failing_operation()

                mock_exit.assert_called_once_with(1)


class TestClickIntegration:
    """Test error handling integration with Click commands."""

    def test_cli_error_handling(self):
        """Test error handling in Click command context."""

        @click.command()
        def test_command():
            raise ConfigurationError("Test config error")

        runner = CliRunner()
        result = runner.invoke(test_command)

        # The command should exit with non-zero code when exception occurs
        assert result.exit_code != 0
