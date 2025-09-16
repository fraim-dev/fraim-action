#!/usr/bin/env python3
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "PyGithub>=2.1.1",
# ]
# ///

import os
from typing import Optional

from github import Github
from github.GithubException import GithubException


def log(message: str) -> None:
    """Log messages in GitHub Actions debug format."""
    print(f"::debug::{message}")


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    github_token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not github_token:
        raise ValueError("No GitHub token available")
    
    return Github(github_token)


def create_status_check(state: str, description: str, github_repository: str, context: str = "fraim-security-scan") -> None:
    """Create a GitHub status check on the current commit.
    
    Args:
        state: Status state ('error', 'failure', 'pending', 'success')
        description: Description of the status
        github_repository: GitHub repository (e.g., 'owner/repo')
        context: Context/name for the status check
    """
    try:
        github_client = get_github_client()
        commit_sha = os.environ.get('GITHUB_SHA', '')
        
        if not github_repository or not commit_sha:
            log(f"Missing repository ({github_repository}) or commit SHA ({commit_sha})")
            return
        
        print(f"Creating status check: {github_repository} - {commit_sha} - {description} - {context}")

        repo = github_client.get_repo(github_repository)
        commit = repo.get_commit(commit_sha)
                
        commit.create_status(
            state=state,
            description=description,
            context=context
        )
        
        log(f"Created status check: {state} - {description}")
        
    except GithubException as e:
        log(f"Failed to create GitHub status check: {e}")
    except Exception as e:
        log(f"Error creating status check: {e}")
