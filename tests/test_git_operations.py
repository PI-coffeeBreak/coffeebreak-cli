"""Tests for Git operations."""

import tempfile
from unittest.mock import MagicMock, patch

import git
import pytest

from coffeebreak.git.operations import GitOperationError, GitOperations


class TestGitOperations:
    """Test Git operations functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.git_operations = GitOperations()
        self.temp_dir = tempfile.mkdtemp()

    def test_clone_repository_success(self):
        """Test successful repository cloning."""
        mock_repo = MagicMock()

        with patch("git.Repo.clone_from", return_value=mock_repo):
            repo = self.git_operations.clone_repository(
                "https://github.com/test/repo.git", self.temp_dir
            )

            assert repo == mock_repo
            git.Repo.clone_from.assert_called_once_with(
                "https://github.com/test/repo.git", to_path=self.temp_dir
            )

    def test_clone_repository_auth_failure(self):
        """Test repository cloning with authentication failure."""
        with patch(
            "git.Repo.clone_from", side_effect=git.exc.GitCommandError("clone", 128)
        ):
            with pytest.raises(GitOperationError) as exc_info:
                self.git_operations.clone_repository(
                    "https://github.com/test/private-repo.git", self.temp_dir
                )

            assert "Failed to clone repository" in str(exc_info.value)

    def test_clone_repository_network_error(self):
        """Test repository cloning with network error."""
        with patch(
            "git.Repo.clone_from", side_effect=git.exc.GitError("Network error")
        ):
            with pytest.raises(GitOperationError) as exc_info:
                self.git_operations.clone_repository(
                    "https://github.com/test/repo.git", self.temp_dir
                )

            assert "Unexpected error cloning repository" in str(exc_info.value)

    def test_clone_multiple_repositories_success(self):
        """Test cloning multiple repositories successfully."""
        repositories = [
            {"name": "core", "url": "https://github.com/test/core.git"},
            {"name": "frontend", "url": "https://github.com/test/frontend.git"},
        ]

        mock_repos = {"core": MagicMock(), "frontend": MagicMock()}

        with patch.object(self.git_operations, "clone_repository") as mock_clone:
            mock_clone.side_effect = lambda url, path, branch=None: mock_repos[
                path.split("/")[-1]
            ]

            # For this test, we'll prepare repository configs with 'path' attribute
            repos_with_paths = []
            for repo in repositories:
                repo_with_path = repo.copy()
                repo_with_path["path"] = f"/base/{repo['name']}"
                repos_with_paths.append(repo_with_path)

            result = self.git_operations.clone_multiple_repositories(repos_with_paths)

            assert len(result) == 2
            assert "core" in result
            assert "frontend" in result
            assert mock_clone.call_count == 2

    def test_clone_multiple_repositories_partial_failure(self):
        """Test cloning multiple repositories with partial failure."""
        repositories = [
            {"name": "core", "url": "https://github.com/test/core.git"},
            {"name": "frontend", "url": "https://github.com/test/frontend.git"},
        ]

        mock_repo = MagicMock()

        def clone_side_effect(url, path, branch=None):
            if "core" in path:
                return mock_repo
            else:
                raise GitOperationError("Failed to clone frontend")

        with patch.object(
            self.git_operations, "clone_repository", side_effect=clone_side_effect
        ):
            # For this test, we'll prepare repository configs with 'path' attribute
            repos_with_paths = []
            for repo in repositories:
                repo_with_path = repo.copy()
                repo_with_path["path"] = f"/base/{repo['name']}"
                repos_with_paths.append(repo_with_path)

            # Should raise exception on any failure
            with pytest.raises(GitOperationError) as exc_info:
                self.git_operations.clone_multiple_repositories(repos_with_paths)

            assert "Failed to clone repositories" in str(exc_info.value)
            assert "frontend: Failed to clone frontend" in str(exc_info.value)

    def test_validate_repository_access(self):
        """Test repository access validation."""
        with patch.object(
            self.git_operations.validator, "validate_access", return_value=[]
        ):
            result = self.git_operations.validate_repository_access(
                "https://github.com/test/repo.git"
            )
            assert result == True

    def test_validate_repository_access_failure(self):
        """Test repository access validation with failure."""
        with patch.object(
            self.git_operations.validator,
            "validate_access",
            return_value=["Access denied"],
        ):
            with pytest.raises(GitOperationError) as exc_info:
                self.git_operations.validate_repository_access(
                    "https://github.com/test/repo.git"
                )

            assert "Repository access validation failed" in str(exc_info.value)

    def test_check_repository_status_valid_repo(self):
        """Test checking status of valid repository."""
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        mock_repo.remotes = []

        with patch("git.Repo", return_value=mock_repo):
            status = self.git_operations.check_repository_status("/test/repo")

            assert status["exists"] == True
            assert status["is_valid"] == True
            assert status["current_branch"] == "main"
            assert status["has_uncommitted_changes"] == False

    def test_check_repository_status_invalid_repo(self):
        """Test checking status of invalid repository."""
        with patch("git.Repo", side_effect=git.exc.InvalidGitRepositoryError):
            with patch("os.path.exists", return_value=True):
                status = self.git_operations.check_repository_status("/test/not-repo")

                assert status["exists"] == True
                assert status["is_valid"] == False
                assert "error" in status

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
