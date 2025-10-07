#!/usr/bin/env python3
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "PyGithub>=2.1.1",
# ]
# ///

import json
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from github import Github
from github.GithubException import GithubException
from github_utils import get_github_client, log


class SarifResult:
    """Represents a single SARIF result/finding."""
    
    def __init__(self, result_data: Dict[str, Any], rule_data: Optional[Dict[str, Any]] = None):
        self.result_data = result_data
        self.rule_data = rule_data or {}
    
    @property
    def message(self) -> str:
        """Get the message text for this result."""
        message = self.result_data.get('message', {})
        return message.get('text', 'No message available')
    
    @property
    def level(self) -> str:
        """Get the severity level (error, warning, note)."""
        return self.result_data.get('level', 'warning')
    
    @property
    def locations(self) -> List[Dict[str, Any]]:
        """Get all locations for this result."""
        return self.result_data.get('locations', [])
    
    @property
    def primary_location(self) -> Optional[Dict[str, Any]]:
        """Get the primary location for this result."""
        locations = self.locations
        return locations[0] if locations else None
    
    @property
    def file_path(self) -> Optional[str]:
        """Get the file path for the primary location."""
        location = self.primary_location
        if not location:
            return None
            
        physical_location = location.get('physicalLocation', {})
        artifact_location = physical_location.get('artifactLocation', {})
        return artifact_location.get('uri')
    
    @property
    def start_line(self) -> Optional[int]:
        """Get the start line number for the primary location."""
        location = self.primary_location
        if not location:
            return None
            
        physical_location = location.get('physicalLocation', {})
        region = physical_location.get('region', {})
        return region.get('startLine')
    
    @property
    def end_line(self) -> Optional[int]:
        """Get the end line number for the primary location."""
        location = self.primary_location
        if not location:
            return None
            
        physical_location = location.get('physicalLocation', {})
        region = physical_location.get('region', {})
        return region.get('endLine', self.start_line)
    
    @property
    def start_column(self) -> Optional[int]:
        """Get the start column number for the primary location."""
        location = self.primary_location
        if not location:
            return None
            
        physical_location = location.get('physicalLocation', {})
        region = physical_location.get('region', {})
        return region.get('startColumn')
    
    @property
    def end_column(self) -> Optional[int]:
        """Get the end column number for the primary location."""
        location = self.primary_location
        if not location:
            return None
            
        physical_location = location.get('physicalLocation', {})
        region = physical_location.get('region', {})
        return region.get('endColumn', self.start_column)
    
    @property
    def help_text(self) -> str:
        """Get help text from the rule."""
        help_info = self.rule_data.get('help', {})
        return help_info.get('text', '')
    
    @property
    def rule_name(self) -> str:
        """Get the rule name/short description."""
        return self.rule_data.get('name', 'unknown-rule')
    
    @property
    def severity_emoji(self) -> str:
        """Get an emoji representing the severity level."""
        severity_map = {
            'error': '🚨',
            'warning': '⚠️',
            'note': 'ℹ️',
            'info': 'ℹ️'
        }
        return severity_map.get(self.level.lower(), '⚠️')


class SarifParser:
    """Parser for SARIF (Static Analysis Results Interchange Format) files."""
    
    def __init__(self, sarif_file_path: str):
        self.sarif_file_path = sarif_file_path
        self.sarif_data = self._load_sarif_file()
        
    def _load_sarif_file(self) -> Dict[str, Any]:
        """Load and parse the SARIF file."""
        try:
            with open(self.sarif_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading SARIF file {self.sarif_file_path}: {e}")
            raise
    
    def get_results(self) -> List[SarifResult]:
        """Extract all results from the SARIF file."""
        all_results = []
        
        for run in self.sarif_data.get('runs', []):
            # Build a map of rule ID to rule data for this run
            rules_map = {}
            tool = run.get('tool', {})
            driver = tool.get('driver', {})
            rules = driver.get('rules', [])
            
            for rule in rules:
                rule_name = rule.get('name')
                if rule_name:
                    rules_map[rule_name] = rule
            
            # Process each result in this run
            results = run.get('results', [])
            for result_data in results:
                rule_name = result_data.get('ruleName')
                rule_data = rules_map.get(rule_name) if rule_name else None
                all_results.append(SarifResult(result_data, rule_data))
        
        return all_results
    
    def get_tool_info(self) -> Tuple[str, str]:
        """Get tool name and version from the SARIF file."""
        runs = self.sarif_data.get('runs', [])
        if not runs:
            return "Unknown Tool", "Unknown Version"
        
        tool = runs[0].get('tool', {})
        driver = tool.get('driver', {})
        
        name = driver.get('name', 'Unknown Tool')
        version = driver.get('version', 'Unknown Version')
        
        return name, version


class SarifToCommentProcessor:
    """Processes SARIF files and creates PR comments and annotations."""
    
    def __init__(self, sarif_file_path: str, repository: str, pr_number: int, title: str = "Security Findings"):
        self.sarif_file_path = sarif_file_path
        self.repository = repository
        self.pr_number = pr_number
        self.title = title
        self.parser = SarifParser(sarif_file_path)
        
    def create_pr_comment(self, dry_run: bool = False) -> None:
        """Create a PR comment with all security findings."""
        results = self.parser.get_results()
        
        if not results:
            log("No security findings to report")
            return
        
        comment_body = self._build_comment_body(results)
        
        if dry_run:
            print("DRY RUN - Would post the following PR comment:")
            print(comment_body)
            return
        
        try:
            github_client = get_github_client()
            repo = github_client.get_repo(self.repository)
            pr = repo.get_pull(self.pr_number)
            
            # Check if we already have a comment with our title
            existing_comment = None
            for comment in pr.get_issue_comments():
                if comment.body.startswith(f"## {self.title}"):
                    existing_comment = comment
                    break
            
            if existing_comment:
                log(f"Updating existing PR comment {existing_comment.id}")
                existing_comment.edit(comment_body)
            else:
                log("Creating new PR comment")
                pr.create_issue_comment(comment_body)
                
        except GithubException as e:
            log(f"Failed to create PR comment: {e}")
            raise
        except Exception as e:
            log(f"Error creating PR comment: {e}")
            raise
    
    def create_annotations(self, dry_run: bool = False) -> None:
        """Create GitHub annotations for security findings."""
        results = self.parser.get_results()
        
        if not results:
            log("No security findings to annotate")
            return
        
        annotations_created = 0
        
        for result in results:
            if not result.file_path or not result.start_line:
                log(f"Skipping annotation for result without file/line: {result.rule_name}")
                continue
                
            annotation_level = self._map_level_to_annotation(result.level)
            message = f"{result.rule_name}: {result.message}"
            
            if dry_run:
                print(f"DRY RUN - Would create annotation:")
                print(f"  File: {result.file_path}")
                print(f"  Line: {result.start_line}")
                print(f"  Level: {annotation_level}")
                print(f"  Message: {message}")
                continue
            
            try:
                # Use GitHub Actions annotation format
                file_path = result.file_path
                line = result.start_line
                col = result.start_column or 1
                
                annotation = f"::{annotation_level} file={file_path},line={line},col={col}::{message}"
                print(annotation)
                
                annotations_created += 1
                
            except Exception as e:
                log(f"Error creating annotation for {result.rule_name}: {e}")
        
        log(f"Created {annotations_created} annotations")
    
    def _build_comment_body(self, results: List[SarifResult]) -> str:
        """Build the PR comment body with all findings."""
        tool_name, tool_version = self.parser.get_tool_info()
        
        # Group results by severity
        errors = [r for r in results if r.level.lower() == 'error']
        warnings = [r for r in results if r.level.lower() == 'warning']
        notes = [r for r in results if r.level.lower() in ['note', 'info']]
        
        # Build the comment
        lines = []
        lines.append(f"## {self.title}")
        lines.append("")
        lines.append(f"**Tool:** {tool_name} {tool_version}")
        lines.append(f"**Total Findings:** {len(results)}")
        
        if errors:
            lines.append(f"🚨 **Errors:** {len(errors)}")
        if warnings:
            lines.append(f"⚠️ **Warnings:** {len(warnings)}")
        if notes:
            lines.append(f"ℹ️ **Notes:** {len(notes)}")
        
        lines.append("")
        
        if not results:
            lines.append("✅ No security issues found!")
            return "\n".join(lines)
        
        # Add summary by file
        files_with_issues = {}
        for result in results:
            file_path = result.file_path or "Unknown file"
            if file_path not in files_with_issues:
                files_with_issues[file_path] = []
            files_with_issues[file_path].append(result)
        
        lines.append("### 📁 Files with Issues")
        lines.append("")
        
        for file_path, file_results in sorted(files_with_issues.items()):
            lines.append(f"**{file_path}** ({len(file_results)} issue{'s' if len(file_results) != 1 else ''})")
            
            for result in file_results:
                line_info = f"Line {result.start_line}" if result.start_line else "Unknown location"
                lines.append(f"- {result.severity_emoji} **{result.rule_name}** ({line_info})")
                lines.append(f"  {result.message}")
                
                if result.help_text:
                    lines.append(f"  💡 {result.help_text}")
                
            lines.append("")
        
        # Add detailed findings section
        lines.append("### 🔍 Detailed Findings")
        lines.append("")
        
        for i, result in enumerate(results, 1):
            lines.append(f"#### {i}. {result.severity_emoji} {result.rule_name}")
            lines.append("")
            lines.append(f"**File:** `{result.file_path or 'Unknown'}`")
            
            if result.start_line:
                if result.end_line and result.end_line != result.start_line:
                    lines.append(f"**Lines:** {result.start_line}-{result.end_line}")
                else:
                    lines.append(f"**Line:** {result.start_line}")
            
            lines.append(f"**Severity:** {result.level.title()}")
            lines.append(f"**Rule Name:** `{result.rule_name}`")
            lines.append("")
            lines.append(f"**Description:** {result.message}")
            
            if result.help_text:
                lines.append("")
                lines.append(f"**Help:** {result.help_text}")
            
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def _map_level_to_annotation(self, level: str) -> str:
        """Map SARIF level to GitHub Actions annotation level."""
        level_map = {
            'error': 'error',
            'warning': 'warning', 
            'note': 'notice',
            'info': 'notice'
        }
        return level_map.get(level.lower(), 'notice')


def process_sarif_file(sarif_file_path: str, repository: str, pr_number: int, 
                      title: str = "Fraim Security Alert", dry_run: bool = False) -> None:
    """Main function to process a SARIF file and create PR comments/annotations."""
    
    if not os.path.exists(sarif_file_path):
        log(f"SARIF file not found: {sarif_file_path}")
        return
    
    log(f"Processing SARIF file: {sarif_file_path}")
    log(f"Repository: {repository}")
    log(f"PR Number: {pr_number}")
    log(f"Dry Run: {dry_run}")
    
    processor = SarifToCommentProcessor(sarif_file_path, repository, pr_number, title)
    
    try:
        # Create PR comment with findings
        processor.create_pr_comment(dry_run)
        
        # Create annotations for code locations
        processor.create_annotations(dry_run)
        
        log("SARIF processing completed successfully")
        
    except Exception as e:
        log(f"Error processing SARIF file: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process SARIF file and create PR comments")
    parser.add_argument("--sarif-file", required=True, help="Path to SARIF file")
    parser.add_argument("--repository", required=True, help="GitHub repository (owner/repo)")
    parser.add_argument("--pr-number", type=int, required=True, help="Pull request number")
    parser.add_argument("--title", default="Fraim Security Alert", help="Title for the PR comment")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode - don't actually post comments")
    
    args = parser.parse_args()
    
    process_sarif_file(
        sarif_file_path=args.sarif_file,
        repository=args.repository,
        pr_number=args.pr_number,
        title=args.title,
        dry_run=args.dry_run
    )
