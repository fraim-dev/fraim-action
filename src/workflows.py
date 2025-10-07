#!/usr/bin/env python3
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "PyGithub>=2.1.1",
# ]
# ///

import os
import sys
import json
from typing import List, Dict, Optional

from github_utils import create_status_check, get_github_client
from github.GithubException import GithubException

def log(message: str) -> None:
    """Log messages in GitHub Actions debug format."""
    print(f"::debug::{message}")


def minify_json(json_input: str) -> str:
    """Minify JSON to a single line."""
    if not json_input:
        return json_input
    
    try:
        # Parse and minify JSON
        if not isinstance(json_input, dict):
            json_input = json.loads(json_input)
        return json.dumps(json_input, separators=(',', ':'))
    except json.JSONDecodeError:
        return json_input


def add_global_args(workflow: str, args: Dict[str, str], github_repository: str) -> List[str]:
    """Prepare global Fraim arguments that come before the workflow subcommand.
    
    Args:
        workflow: The workflow type ('code', 'iac', 'risk_flagger', etc.)
        args: Dictionary of parsed workflow arguments
        github_repository: GitHub repository (e.g., 'owner/repo')
        
    Returns:
        List of global CLI arguments for Fraim
    """
    # Prepare global Fraim arguments (these must come BEFORE the workflow subcommand)
    if workflow in ['code', 'iac']:
        global_args = ['--output', 'fraim_outputs']
    else:
        global_args = []
    
    # Add confidence if specified
    confidence = args.get('confidence')
    if confidence:
        global_args.extend(['--confidence', confidence])
        
    # Add temperature if specified
    temperature = args.get('temperature')
    if temperature:
        global_args.extend(['--temperature', temperature])
    
    # Add model if specified
    input_model = os.environ.get('INPUT_MODEL', '')
    if input_model:
        global_args.extend(['--model', input_model])
        
    # Determine scan location and diff args
    global_args.extend(['--location', './'])
    diff_args = []
    
    github_event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    if github_event_name == "pull_request":
        print("Scanning PR diff using --diff mode...")
        
        # Verify we have the required SHAs
        github_base_sha = os.environ.get('GITHUB_BASE_SHA', '')
        github_sha = os.environ.get('GITHUB_SHA', '')
        
        if not github_base_sha or not github_sha:
            error_msg = f"Missing base or head SHA for PR diff scanning. GITHUB_BASE_SHA: {github_base_sha}, GITHUB_SHA: {github_sha}"
            print(f"ERROR: {error_msg}")
            
            # Create GitHub status check with error state
            create_status_check(
                state="error",
                description=error_msg,
                github_repository=github_repository,
                context=f"fraim/{workflow}"
            )
            sys.exit(1)
        
        print(f"Base SHA: {github_base_sha}")
        print(f"Head SHA: {github_sha}")
        
        # Use diff mode for PR scanning
        global_args.extend(['--diff', '--base', github_base_sha, '--head', github_sha])
    else:
        print("Scanning entire repository...")
        # No diff args needed for full repository scan
    
    return global_args


def add_risk_flagger_args(args: Dict[str, str], workflow_cli_args: List[str], github_repository: str, pr_number: Optional[int]) -> List[str]:
    """Add risk_flagger specific arguments to workflow CLI args.
    
    Args:
        args: Dictionary of parsed workflow arguments
        workflow_cli_args: List of CLI arguments being built
        github_repository: GitHub repository (e.g., 'owner/repo')
        pr_number: Pull request number (if applicable)
        
    Returns:
        Updated list of CLI arguments with risk_flagger specific args added
    """
    # Make a copy to avoid mutating the input list
    updated_args = workflow_cli_args.copy()
    
    custom_risk_list_json = args.get('custom-risk-list-json')
    print(f"Custom risk list JSON: {custom_risk_list_json}")
    
    if custom_risk_list_json:
        # Convert single quotes to double quotes
        
        # Minify JSON to ensure it's on a single line
        minified_json = minify_json(custom_risk_list_json)
        updated_args.extend(['--custom-risk-list-json', minified_json])
    
    custom_risk_list_filepath = args.get('custom-risk-list-filepath')
    if custom_risk_list_filepath:
        updated_args.extend(['--custom-risk-list-filepath', custom_risk_list_filepath])
    
    custom_risk_list_action = args.get('custom-risk-list-action')
    if custom_risk_list_action:
        updated_args.extend(['--custom-risk-list-action', custom_risk_list_action])
    
    approver = args.get('approver')
    if approver:
        updated_args.extend(['--approver', approver])
    
    # Add Slack webhook URL if provided in workflow args
    slack_webhook_url = args.get('slack-webhook-url')
    if slack_webhook_url:
        updated_args.extend(['--slack-webhook-url', slack_webhook_url])
        log(f"Adding Slack webhook URL for risk_flagger")
    
    # Add no-gh-comment flag if enabled in workflow args
    no_gh_comment = args.get('no-gh-comment')
    if no_gh_comment and str(no_gh_comment).lower() in ['true']:
        updated_args.append('--no-gh-comment')
        log(f"Adding --no-gh-comment flag for risk_flagger")

    # Add PR URL if this is a pull request event
    github_event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    if github_event_name in ["pull_request", "pull_request_review"] and pr_number and github_repository:
        pr_url = f"https://github.com/{github_repository}/pull/{pr_number}"
        updated_args.extend(['--pr-url', pr_url])
        log(f"Adding PR URL for risk_flagger: {pr_url}")

    return updated_args


def get_team_members(github_repository: str, team_name: str) -> List[str]:
    """Get members of a GitHub team.
    
    Args:
        github_repository: GitHub repository (e.g., 'owner/repo')
        team_name: Team name (e.g., 'security-team')
        
    Returns:
        List of team member usernames
    """
    try:
        github_client = get_github_client()
        
        # Extract org name from repository
        org_name = github_repository.split('/')[0]
        
        # Get the organization and team
        org = github_client.get_organization(org_name)
        team = org.get_team_by_slug(team_name)
        
        # Get team members
        members = team.get_members()
        member_logins = [member.login for member in members]
        
        log(f"Team '{team_name}' has members: {member_logins}")
        return member_logins
        
    except Exception as e:
        log(f"Error getting team members for '{team_name}': {e}")
        return []


def is_team_approver(approver: str, github_repository: str) -> bool:
    """Check if the approver string represents a team by calling GitHub API.
    
    Args:
        approver: The approver string
        github_repository: GitHub repository (e.g., 'owner/repo') to extract org name
        
    Returns:
        True if this is a valid GitHub team, False if individual user or team doesn't exist
    """
    if not approver or not github_repository:
        return False
    
    try:
        github_client = get_github_client()
        
        # Extract org name from repository
        org_name = github_repository.split('/')[0]
        
        # Clean up the approver string
        team_name = approver.lstrip('@')
        if '/' in team_name:
            team_name = team_name.split('/')[-1]  # Get team part from org/team format
        
        # Try to get the team - this will throw an exception if team doesn't exist
        org = github_client.get_organization(org_name)
        team = org.get_team_by_slug(team_name)
        
        # If we get here without exception, it's a valid team
        log(f"'{approver}' is a valid team with ID: {team.id}")
        return True
        
    except GithubException as e:
        # 404 means team not found, so it's likely an individual user
        if e.status == 404:
            log(f"'{approver}' is not a team (404), treating as individual user")
            return False
        else:
            log(f"GitHub API error checking if '{approver}' is a team: {e}")
            return False
    except Exception as e:
        log(f"Error checking if '{approver}' is a team: {e}")
        return False


def check_approver_approval(approver: str, github_repository: str, pr_number: Optional[int]) -> bool:
    """Check if required approver has approved the PR.
    
    Supports both individual users and teams. For teams, checks if any team member approved.
    
    Args:
        approver: Username or team name of the required approver
        github_repository: GitHub repository (e.g., 'owner/repo')  
        pr_number: Pull request number
    """
    log(f"Checking if approver '{approver}' has approved PR #{pr_number}")
    
    if not approver:
        log("No approver specified")
        return False
    
    if not github_repository:
        log("Missing repository information")
        return False
    
    if not pr_number:
        log("Missing PR number")
        return False
    
    github_client = get_github_client()
    if not github_client:
        log("GitHub client not available, cannot check approvals")
        return False
    
    try:
        # Get repository and pull request
        repo = github_client.get_repo(github_repository)
        pr = repo.get_pull(pr_number)
        
        # Determine if this is a team or individual approver
        is_team = is_team_approver(approver, github_repository)
        
        if is_team:
            log(f"'{approver}' appears to be a team, checking team members")
            
            # Extract team name from approver string
            team_name = approver.lstrip('@')
            if '/' in team_name:
                team_name = team_name.split('/')[-1]  # Get team part from org/team format
            
            # Get team members
            team_members = get_team_members(github_repository, team_name)
            
            if not team_members:
                log(f"No team members found for team '{team_name}'")
                return False
            
            # Check if any team member has approved
            reviews = pr.get_reviews()
            for review in reviews:
                print(f"Review: {review.state} - {review.user.login}")
                if review.state == "APPROVED" and review.user.login in team_members:
                    log(f"PR approved by team member: {review.user.login}")
                    return True
            
            log(f"No approvals found from team '{team_name}' members")
            return False
        else:
            log(f"'{approver}' appears to be an individual user")
            
            # Check for individual user approval (existing logic)
            reviews = pr.get_reviews()
            for review in reviews:
                print(f"Review: {review.state} - {review.user.login}")
                if review.state == "APPROVED" and review.user.login == approver:
                    log(f"PR approved by user: {review.user.login}")
                    return True
            
            log(f"No approval found from user '{approver}'")
            return False
            
    except GithubException as e:
        log(f"GitHub API error checking approver approval: {e}")
        return False
    except Exception as e:
        log(f"Error checking approver approval: {e}")
        return False


def handle_pull_request_review(args: Dict[str, str], workflow: str, should_block_pr: bool, github_repository: str, pr_number: Optional[int]) -> None:
    """Handle pull request blocking logic for risk_flagger workflow.
    
    Args:
        args: Dictionary of parsed workflow arguments
        workflow: The workflow type
        should_block_pr: Whether to block PR based on security findings
        github_repository: GitHub repository (e.g., 'owner/repo')
        pr_number: Pull request number
    """
    github_event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    
    # A pull request review simply checks if the approver approved, if they did
    # it updates the PR status to approved
    if github_event_name == "pull_request_review":
        if should_block_pr == True and workflow == "risk_flagger":
            print("Pull request blocking is enabled for risk_flagger workflow")
            
            # First check if there was actually a security risk (by looking for the comment)
            if check_security_risk_comment(github_repository, pr_number):
                print("Security risk comment found, checking for approver approval")
                
                approver = args.get('approver')
                if approver and check_approver_approval(approver, github_repository, pr_number):
                    print(f"::notice::Security review completed. PR approved by {approver}.")
                    create_status_check(
                        state="success",
                        description=f"Security review completed. PR approved by {approver}.",
                        github_repository=github_repository,
                        context=f"fraim/{workflow}",
                    )
                else:
                    approver_text = approver if approver else '[not specified]'
                    print(f"::error::Security risks detected! Waiting for approval from {approver_text}.")
                    create_status_check(
                        state="failure",
                        description=f"Security risks detected! Waiting for approval from {approver_text}.",
                        github_repository=github_repository,
                        context=f"fraim/{workflow}",
                    )
                    
            else:
                print("::notice::No security risks detected in this PR.")

        # Exit early for this event since we've handled it.
        sys.exit(0)
                
def handle_pull_request_block(args: Dict[str, str], workflow: str, should_block_pr: bool, security_findings_found: bool, github_repository: str, pr_number: int) -> None:
    """Handle pull request blocking logic for risk_flagger workflow.
    
    Args:
        args: Dictionary of parsed workflow arguments
        workflow: The workflow type
        should_block_pr: Whether to block PR based on security findings
        security_findings_found: Whether security findings were detected
        github_repository: GitHub repository (e.g., 'owner/repo')
    """
        
    github_event_name = os.environ.get('GITHUB_EVENT_NAME', '')

    if github_event_name == "pull_request":
        if should_block_pr == True and workflow == "risk_flagger":            
            if security_findings_found:
                approver = args.get('approver')
                
                is_approved = check_approver_approval(approver, github_repository, pr_number)

                if is_approved:
                    print(f"Found security risks, but approver {approver} has approved the PR")
                    create_status_check(
                        state="success",
                        description=f"Security review completed. PR approved by {approver}.",
                        github_repository=github_repository,
                        context=f"fraim/{workflow}",
                    )
                    return

                approver_text = approver if approver else '[not specified]'
                print("::error::Security risks detected! This pull request is blocked pending security team approval.")
                print(f"::notice::@{approver_text} must review and approve this PR.")
                create_status_check(
                    state="failure",
                    description=f"Security risks detected! Waiting for approval from {approver_text}.",
                    github_repository=github_repository,
                    context=f"fraim/{workflow}"
                )
            else:
                print("No security risks found, allowing PR to proceed")

def check_output_for_risk_findings(output_content: str) -> bool:
    """Check the output for security findings."""
    # Variable to track if security findings were found in command output
    security_findings_found = False
   
    # Check output for security findings string regardless of exit code
    if "The following security risks have been identified and require review" in output_content:
        log(f"Security risks detected")
        security_findings_found = True

    return security_findings_found

def check_security_risk_comment(github_repository: str, pr_number: int) -> bool:
    """Check if a comment with specific text exists on the latest commit.
    
    Args:
        github_repository: GitHub repository (e.g., 'owner/repo')
    """
    commit_sha = os.environ.get('GITHUB_SHA', '')
    
    log(f"Checking for security risk comment on commit: {commit_sha}")
    
    if not commit_sha or not github_repository:
        log("Missing commit SHA or repository information")
        return False
    
    github_client = get_github_client()
    if not github_client:
        log("GitHub client not available, cannot check for security risk comment")
        return False
    
    try:
        # Get repository and commit
        repo = github_client.get_repo(github_repository)
        pr = repo.get_pull(pr_number)
        comments = pr.get_issue_comments()
        
        for comment in comments:
            if "Security Risk Review Required" in comment.body:
                return True
        
        return False
    except GithubException as e:
        log(f"GitHub API error checking security risk comment: {e}")
        return False
    except Exception as e:
        log(f"Error checking security risk comment: {e}")
        return False
