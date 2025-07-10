"""Git repository validation for CoffeeBreak CLI."""

import re
import subprocess
from typing import List, Optional
from urllib.parse import urlparse


class GitValidator:
    """Validates Git repository URLs and access."""

    def __init__(self):
        """Initialize Git validator."""
        pass

    def validate_url_format(self, url: str) -> List[str]:
        """
        Validate Git URL format.

        Args:
            url: Git repository URL to validate

        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []

        if not url:
            errors.append("Repository URL cannot be empty")
            return errors

        # Check for supported URL formats
        https_pattern = r"^https://github\.com/[\w\-\.]+/[\w\-\.]+\.git$"
        ssh_pattern = r"^git@github\.com:[\w\-\.]+/[\w\-\.]+\.git$"

        if not (re.match(https_pattern, url) or re.match(ssh_pattern, url)):
            errors.append(f"Invalid repository URL format: {url}")
            errors.append(
                "Supported formats: https://github.com/user/repo.git or git@github.com:user/repo.git"
            )

        return errors

    def validate_access(self, url: str) -> List[str]:
        """
        Validate access to Git repository.

        Args:
            url: Git repository URL to check

        Returns:
            List[str]: List of access errors (empty if accessible)
        """
        errors = []

        # First validate URL format
        format_errors = self.validate_url_format(url)
        if format_errors:
            return format_errors

        try:
            # Use git ls-remote to check if repository is accessible
            result = subprocess.run(
                ["git", "ls-remote", "--heads", url],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                if "Authentication failed" in result.stderr:
                    errors.append(f"Authentication failed for repository: {url}")
                    errors.append("Please check your SSH keys or personal access token")
                elif "not found" in result.stderr.lower():
                    errors.append(f"Repository not found: {url}")
                    errors.append(
                        "Please check the repository URL and your access permissions"
                    )
                else:
                    errors.append(f"Cannot access repository {url}: {result.stderr}")

        except subprocess.TimeoutExpired:
            errors.append(f"Timeout while checking repository access: {url}")
        except FileNotFoundError:
            errors.append("Git is not installed or not available in PATH")
        except Exception as e:
            errors.append(f"Error checking repository access: {e}")

        return errors

    def validate_branch_exists(self, url: str, branch: str) -> List[str]:
        """
        Validate that a specific branch exists in the repository.

        Args:
            url: Git repository URL
            branch: Branch name to check

        Returns:
            List[str]: List of validation errors (empty if branch exists)
        """
        errors = []

        try:
            # Use git ls-remote to check if branch exists
            result = subprocess.run(
                ["git", "ls-remote", "--heads", url, f"refs/heads/{branch}"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                errors.append(
                    f"Error checking branch {branch} in repository {url}: {result.stderr}"
                )
            elif not result.stdout.strip():
                errors.append(f"Branch '{branch}' not found in repository {url}")

        except subprocess.TimeoutExpired:
            errors.append(
                f"Timeout while checking branch {branch} in repository: {url}"
            )
        except FileNotFoundError:
            errors.append("Git is not installed or not available in PATH")
        except Exception as e:
            errors.append(f"Error checking branch: {e}")

        return errors

    def get_default_branch(self, url: str) -> Optional[str]:
        """
        Get the default branch name for a repository.

        Args:
            url: Git repository URL

        Returns:
            Optional[str]: Default branch name or None if cannot determine
        """
        try:
            # Use git ls-remote to get HEAD reference
            result = subprocess.run(
                ["git", "ls-remote", "--symref", url, "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if line.startswith("ref: refs/heads/"):
                        return line.split("/")[-1]

            # Fallback: try common default branch names
            for branch in ["main", "master"]:
                branch_errors = self.validate_branch_exists(url, branch)
                if not branch_errors:
                    return branch

        except Exception:
            pass

        return None

    def extract_repo_info(self, url: str) -> Optional[dict]:
        """
        Extract repository information from URL.

        Args:
            url: Git repository URL

        Returns:
            Optional[dict]: Repository info (owner, name) or None if invalid
        """
        # HTTPS format: https://github.com/owner/repo.git
        https_match = re.match(
            r"^https://github\.com/([\w\-\.]+)/([\w\-\.]+)\.git$", url
        )
        if https_match:
            return {
                "owner": https_match.group(1),
                "name": https_match.group(2),
                "type": "https",
            }

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"^git@github\.com:([\w\-\.]+)/([\w\-\.]+)\.git$", url)
        if ssh_match:
            return {
                "owner": ssh_match.group(1),
                "name": ssh_match.group(2),
                "type": "ssh",
            }

        return None
