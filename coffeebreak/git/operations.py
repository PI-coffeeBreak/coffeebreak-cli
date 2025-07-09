"""Git operations for CoffeeBreak CLI."""

import os
import shutil
from typing import List, Optional, Dict, Any
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from .validation import GitValidator


class GitOperationError(Exception):
    """Raised when Git operations fail."""
    pass


class GitOperations:
    """Handles Git repository operations for CoffeeBreak CLI."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize Git operations.
        
        Args:
            verbose: Whether to enable verbose output
        """
        self.verbose = verbose
        self.validator = GitValidator()
    
    def clone_repository(self,
                        url: str,
                        local_path: str,
                        branch: Optional[str] = None,
                        depth: Optional[int] = None) -> git.Repo:
        """
        Clone a Git repository.
        
        Args:
            url: Repository URL to clone
            local_path: Local path to clone to
            branch: Specific branch to clone (optional)
            depth: Clone depth for shallow clone (optional)
            
        Returns:
            git.Repo: The cloned repository object
            
        Raises:
            GitOperationError: If cloning fails
        """
        # Validate URL first
        url_errors = self.validator.validate_url_format(url)
        if url_errors:
            raise GitOperationError(f"Invalid URL: {'; '.join(url_errors)}")
        
        # Check if target directory already exists
        if os.path.exists(local_path):
            if os.path.isdir(local_path) and os.listdir(local_path):
                raise GitOperationError(f"Directory {local_path} already exists and is not empty")
            elif os.path.isfile(local_path):
                raise GitOperationError(f"File exists at {local_path}, cannot create directory")
        
        try:
            # Prepare clone options
            clone_kwargs = {
                'to_path': local_path,
                'branch': branch,
                'depth': depth
            }
            
            # Remove None values
            clone_kwargs = {k: v for k, v in clone_kwargs.items() if v is not None}
            
            if self.verbose:
                print(f"Cloning repository {url} to {local_path}")
                if branch:
                    print(f"Using branch: {branch}")
                if depth:
                    print(f"Using depth: {depth}")
            
            # Clone the repository
            repo = git.Repo.clone_from(url, **clone_kwargs)
            
            if self.verbose:
                print(f"Successfully cloned repository to {local_path}")
            
            return repo
            
        except GitCommandError as e:
            error_msg = f"Failed to clone repository {url}: {e}"
            
            # Provide more specific error messages
            if 'Authentication failed' in str(e):
                error_msg += "\nPlease check your SSH keys or personal access token"
            elif 'not found' in str(e).lower():
                error_msg += "\nRepository not found. Please check the URL and your access permissions"
            elif branch and 'does not exist' in str(e):
                error_msg += f"\nBranch '{branch}' does not exist in the repository"
            
            # Clean up partial clone if it exists
            if os.path.exists(local_path):
                try:
                    shutil.rmtree(local_path)
                except Exception:
                    pass
            
            raise GitOperationError(error_msg)
        
        except Exception as e:
            # Clean up partial clone if it exists
            if os.path.exists(local_path):
                try:
                    shutil.rmtree(local_path)
                except Exception:
                    pass
            
            raise GitOperationError(f"Unexpected error cloning repository: {e}")
    
    def clone_multiple_repositories(self, 
                                  repositories: List[Dict[str, Any]]) -> Dict[str, git.Repo]:
        """
        Clone multiple repositories.
        
        Args:
            repositories: List of repository configurations
            
        Returns:
            Dict[str, git.Repo]: Mapping of repository names to repo objects
            
        Raises:
            GitOperationError: If any repository fails to clone
        """
        cloned_repos = {}
        failed_repos = []
        
        for repo_config in repositories:
            name = repo_config.get('name')
            url = repo_config.get('url')
            path = repo_config.get('path')
            branch = repo_config.get('branch')
            
            if not all([name, url, path]):
                failed_repos.append(f"{name}: Missing required configuration")
                continue
            
            try:
                repo = self.clone_repository(url, path, branch)
                cloned_repos[name] = repo
                
                if self.verbose:
                    print(f"✓ Successfully cloned {name}")
                    
            except GitOperationError as e:
                failed_repos.append(f"{name}: {e}")
                
                # Clean up any partially cloned repositories
                for cloned_name, cloned_repo in cloned_repos.items():
                    try:
                        shutil.rmtree(cloned_repo.working_dir)
                    except Exception:
                        pass
                
                break
        
        if failed_repos:
            error_msg = "Failed to clone repositories:\n" + "\n".join(failed_repos)
            raise GitOperationError(error_msg)
        
        return cloned_repos
    
    def check_repository_status(self, repo_path: str) -> Dict[str, Any]:
        """
        Check the status of a Git repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dict[str, Any]: Repository status information
            
        Raises:
            GitOperationError: If repository check fails
        """
        try:
            repo = git.Repo(repo_path)
            
            status = {
                'path': repo_path,
                'exists': True,
                'is_valid': True,
                'current_branch': repo.active_branch.name,
                'remote_url': None,
                'has_uncommitted_changes': repo.is_dirty(),
                'untracked_files': len(repo.untracked_files) > 0,
                'ahead_behind': None
            }
            
            # Get remote URL
            if repo.remotes:
                origin = repo.remotes.origin
                status['remote_url'] = list(origin.urls)[0]
                
                # Check ahead/behind status
                try:
                    commits_ahead = list(repo.iter_commits(f'origin/{repo.active_branch.name}..HEAD'))
                    commits_behind = list(repo.iter_commits(f'HEAD..origin/{repo.active_branch.name}'))
                    status['ahead_behind'] = {
                        'ahead': len(commits_ahead),
                        'behind': len(commits_behind)
                    }
                except Exception:
                    # Remote branch might not exist
                    pass
            
            return status
            
        except InvalidGitRepositoryError:
            return {
                'path': repo_path,
                'exists': os.path.exists(repo_path),
                'is_valid': False,
                'error': 'Not a valid Git repository'
            }
        except Exception as e:
            return {
                'path': repo_path,
                'exists': os.path.exists(repo_path),
                'is_valid': False,
                'error': str(e)
            }
    
    def pull_repository(self, repo_path: str) -> bool:
        """
        Pull latest changes from remote repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            bool: True if pull successful
            
        Raises:
            GitOperationError: If pull fails
        """
        try:
            repo = git.Repo(repo_path)
            
            if repo.is_dirty():
                raise GitOperationError(f"Repository {repo_path} has uncommitted changes")
            
            if not repo.remotes:
                raise GitOperationError(f"Repository {repo_path} has no remote configured")
            
            origin = repo.remotes.origin
            origin.pull()
            
            if self.verbose:
                print(f"✓ Successfully pulled latest changes for {repo_path}")
            
            return True
            
        except InvalidGitRepositoryError:
            raise GitOperationError(f"Not a valid Git repository: {repo_path}")
        except GitCommandError as e:
            raise GitOperationError(f"Failed to pull repository {repo_path}: {e}")
        except Exception as e:
            raise GitOperationError(f"Unexpected error pulling repository: {e}")
    
    def validate_repository_access(self, url: str) -> bool:
        """
        Validate that a repository URL is accessible.
        
        Args:
            url: Repository URL to validate
            
        Returns:
            bool: True if repository is accessible
            
        Raises:
            GitOperationError: If repository is not accessible
        """
        errors = self.validator.validate_access(url)
        if errors:
            raise GitOperationError(f"Repository access validation failed: {'; '.join(errors)}")
        
        return True