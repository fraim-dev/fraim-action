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
import subprocess
import tempfile
import glob
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union

from workflows import add_global_args, add_risk_flagger_args, handle_pull_request_review, handle_pull_request_block, check_output_for_risk_findings

def log(message: str) -> None:
    """Log messages in GitHub Actions debug format."""
    print(f"::debug::{message}")

def set_output(name: str, value: str) -> None:
    """Set GitHub Actions output."""
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")


def parse_workflow_args() -> Dict[str, str]:
    """Parse workflow_args JSON and return dictionary with all arguments."""
    workflow_args = os.environ.get('WORKFLOW_ARGS', '')
    
    try:
        # Parse JSON and merge with defaults
        data = json.loads(workflow_args)
        return data
    except json.JSONDecodeError as e:
        log(f"JSON parsing error: {e}")
        raise e


def get_changed_files() -> str:
    """Get changed files for PR (kept for backward compatibility/debugging)."""
    github_base_sha = os.environ.get('GITHUB_BASE_SHA', '')
    github_sha = os.environ.get('GITHUB_SHA', '')
    
    if not github_base_sha or not github_sha:
        return ''
    
    try:
        result = subprocess.run([
            'git', 'diff', '--name-only', github_base_sha, github_sha
        ], capture_output=True, text=True, check=True)
        
        # Filter for specific file extensions
        extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', 
                     '.php', '.cs', '.cpp', '.c', '.h', '.yaml', '.yml', '.tf', 
                     '.tfvars', '.json']
        
        files = []
        for line in result.stdout.strip().split('\n'):
            if line and any(line.endswith(ext) for ext in extensions):
                files.append(line)
        
        return ' '.join(files)
    except subprocess.CalledProcessError:
        return ''


def get_github_context() -> Tuple[str, int]:
    """Get GitHub repository and PR number from environment."""
    github_repository = os.environ.get('GITHUB_REPOSITORY', '')
    github_event_path = os.environ.get('GITHUB_EVENT_PATH')
    
    if github_event_path and os.path.isfile(github_event_path):
        try:
            with open(github_event_path, 'r') as f:
                event_data = json.load(f)
                pr_number = event_data.get('pull_request', {}).get('number')
        except Exception as e:
            log(f"Error reading GitHub event: {e}")
    
    return github_repository, pr_number


def main() -> None:
    """Main function."""
    log("Starting Fraim Security Scan")
    
    # Create output directory
    os.makedirs('fraim_outputs', exist_ok=True)
    
    # Parse workflow arguments once
    workflow_args_raw = os.environ.get('WORKFLOW_ARGS', '')
    print(f"Workflow args: {workflow_args_raw}")
    
    args = parse_workflow_args()
    
    print(f"Parsed Args: {args}")
    
    # Get GitHub context (repository and PR number) once
    github_repository, pr_number = get_github_context()
    log(f"GitHub context: repo={github_repository}, pr={pr_number}")
    
    # Handle pull request blocking logic for risk_flagger workflow
    should_block_pr = args.get('should-block-pull-request')
    workflow = os.environ.get('INPUT_WORKFLOW', '')
        
    # Get workflow from INPUT_WORKFLOW
    if not workflow:
        print("::error::No workflow specified")
        sys.exit(1)
        
    handle_pull_request_review(args, workflow, should_block_pr, github_repository, pr_number)
    
    # Prepare global Fraim arguments that are shared between workflows
    global_args = add_global_args(workflow, args, github_repository)
    workflow_cli_args = []
    
    # Add risk_flagger specific arguments
    if workflow == "risk_flagger":
        workflow_cli_args = add_risk_flagger_args(args, workflow_cli_args, github_repository, pr_number)
    
    # Run the single workflow
    print(f"Running workflow: {workflow}")

    # Build the complete command: uv run fraim run [workflow] [global_args] [workflow_args]
    cmd = ['uv', 'run', 'fraim', 'run', workflow] + global_args + workflow_cli_args

    print(f"Running: {' '.join(cmd)}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check environment variables
    print("=== Environment Check ===")
    api_keys = ['GEMINI_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY']
    for key in api_keys:
        value = os.environ.get(key, 'Not set')
        print(f"{key}: {'[REDACTED]' if value != 'Not set' else 'Not set'}")
    
    github_vars = ['GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_REPOSITORY', 'INPUT_WORKFLOW']
    for key in github_vars:
        value = os.environ.get(key, 'Not set')
        if key in ['GITHUB_TOKEN', 'GH_TOKEN']:
            print(f"{key}: {'[REDACTED]' if value != 'Not set' else 'Not set'}")
        else:
            print(f"{key}: {value}")
    print("=== End Environment Check ===")
    
    # Check if fraim is available and working
    print("=== Debugging fraim command ===")
    try:
        fraim_check = subprocess.run(['uv', 'run', 'fraim', '--version'], 
                                   capture_output=True, text=True, check=False, timeout=30)
        print(f"Fraim version check exit code: {fraim_check.returncode}")
        print(f"Fraim version stdout: {fraim_check.stdout}")
        if fraim_check.stderr:
            print(f"Fraim version stderr: {fraim_check.stderr}")
    except subprocess.TimeoutExpired:
        print("Fraim version check timed out")
    except Exception as e:
        print(f"Error checking fraim version: {e}")
    
    # Test a simple fraim command
    print("Testing fraim help command...")
    try:
        help_result = subprocess.run(['uv', 'run', 'fraim', '--help'], 
                                   capture_output=True, text=True, check=False, timeout=30)
        print(f"Fraim help exit code: {help_result.returncode}")
        if help_result.returncode != 0:
            print(f"Fraim help stdout: {help_result.stdout}")
            print(f"Fraim help stderr: {help_result.stderr}")
    except Exception as e:
        print(f"Error testing fraim help: {e}")
    
    print("=== End debugging ===")
    
    try:
        # Use a temporary file to capture both stdout and stderr
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_output_path = temp_file.name
            
        # Execute command and capture both exit code and output
        print("Executing fraim command...")
        with open(temp_output_path, 'w') as temp_file:
            result = subprocess.run(cmd, stdout=temp_file, stderr=subprocess.STDOUT, 
                                    text=True, check=False)
            fraim_exit_code = result.returncode
            
        print(f"Fraim command completed with exit code: {fraim_exit_code}")
            
        # Display the output first (for debugging)
        with open(temp_output_path, 'r') as temp_file:
            output_content = temp_file.read()
            print("=== Fraim Command Output ===")
            print(output_content, end='')
            print("=== End Fraim Output ===")

        # If the Fraim command failed, exit with failure
        if fraim_exit_code != 0:
            print(f"::error::Fraim workflow '{workflow}' failed with exit code {fraim_exit_code}")
            print(f"Command that failed: {' '.join(cmd)}")
            print(f"Output was: {output_content[:500]}{'...' if len(output_content) > 500 else ''}")
            raise Exception(f"Fraim workflow '{workflow}' failed with exit code {fraim_exit_code}")
    except Exception as e:
        print(f"::error::Error running Fraim command: {e}")
        raise e
    finally:
        # Clean up temp file
        os.unlink(temp_output_path)
        
    security_findings_found = check_output_for_risk_findings(output_content)
    handle_pull_request_block(args, workflow, should_block_pr, security_findings_found, github_repository)

    # Find the SARIF file
    sarif_files = glob.glob('fraim_outputs/*.sarif')
    sarif_file = sarif_files[0] if sarif_files else None

    if sarif_file and os.path.isfile(sarif_file):
        print(f"Found SARIF file: {sarif_file}")

        # Count results in SARIF file
        try:
            with open(sarif_file, 'r') as f:
                data = json.load(f)
                results_count = sum(len(run.get('results', [])) for run in data.get('runs', []))
        except Exception:
            results_count = 0

        set_output("sarif-file", sarif_file)
        set_output("results-count", str(results_count))
        print(f"Found {results_count} security findings")
    else:
        set_output("sarif-file", "")
        set_output("results-count", "0")
        results_count = 0

    # Determine if security findings were found (either via SARIF file or output string)
    findings_detected = results_count > 0 or security_findings_found
    
    # Log if security findings were detected
    if findings_detected:
        if results_count > 0:
            print(f"::error::Security findings detected! Found {results_count} security issue(s) in SARIF results.")
        if security_findings_found:
            print("::error::Security findings detected! The scan identified security risks that require review.")
    
    log("Fraim Security Scan completed")


if __name__ == "__main__":
    main()
