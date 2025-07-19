#!/bin/bash

set -e

# Enable debug mode for more verbose output
set -x

SARIF_FILE="$1"

# Function to log messages
log() {
    echo "::debug::$1"
}

# Array to store all suggestions for batch review
declare -a SUGGESTIONS=()

# Function to add a suggestion to the batch
add_suggestion() {
    local file="$1"
    local line="$2"
    local original_code="$3"
    local suggested_code="$4"
    local description="$5"
    
    # Create suggestion format
    local suggestion_body
    suggestion_body=$(cat << EOF
$description

\`\`\`suggestion
$suggested_code
\`\`\`
EOF
)
    
    # Add to suggestions array
    local suggestion_json
    suggestion_json=$(jq -n \
        --arg body "$suggestion_body" \
        --arg path "$file" \
        --argjson line "$line" \
        '{
            body: $body,
            path: $path,
            line: $line
        }')
    
    SUGGESTIONS+=("$suggestion_json")
    log "Added suggestion for $file:$line"
}

# Function to create a PR review with all suggestions
create_review_with_suggestions() {
    # Temporarily disable exit on error for this function
    set +e
    
    if [ ${#SUGGESTIONS[@]} -eq 0 ]; then
        log "No suggestions to create"
        set -e
        return 0
    fi
    
    log "Creating PR review with ${#SUGGESTIONS[@]} suggestions"
    
    # Build the comments array for the review
    local comments_json="["
    local first=true
    for suggestion in "${SUGGESTIONS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            comments_json="$comments_json,"
        fi
        comments_json="$comments_json$suggestion"
    done
    comments_json="$comments_json]"
    
    # Create the review
    local review_data
    review_data=$(jq -n \
        --arg commit_id "$GITHUB_SHA" \
        --arg body "🔒 **Fraim Security Review**\n\nI've found some security issues with suggested fixes. Please review the suggestions below:" \
        --arg event "COMMENT" \
        --argjson comments "$comments_json" \
        '{
            commit_id: $commit_id,
            body: $body,
            event: $event,
            comments: $comments
        }')
    
    echo "Debug: About to create review with data:"
    echo "$review_data" | jq .
    
    local response
    response=$(curl -s -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/pulls/$PR_NUMBER/reviews" \
        -d "$review_data")
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    echo "Debug: API response code: $http_code"
    echo "Debug: API response body: $body"
    
    if [ "$http_code" -ge 400 ]; then
        echo "Error: GitHub API call failed with status $http_code"
        echo "Response: $body"
        set -e
        return 1
    fi
    
    set -e
    return 0
}

# Function to process SARIF file
process_sarif() {
    local sarif_file="$1"
    
    if [ ! -f "$sarif_file" ]; then
        log "SARIF file not found: $sarif_file"
        return 1
    fi
    
    log "Processing SARIF file: $sarif_file"
    
    # Use Python to parse SARIF and extract fixes
    SARIF_FILE="$sarif_file" python3 << 'EOF'
import json
import sys
import os

sarif_file = os.environ.get('SARIF_FILE')

print(f"Debug: Processing SARIF file: {sarif_file}", file=sys.stderr)

if not sarif_file:
    print("Error: No SARIF file path provided", file=sys.stderr)
    sys.exit(1)

try:
    with open(sarif_file, 'r') as f:
        sarif_data = json.load(f)
    
    print(f"Debug: Successfully loaded SARIF file", file=sys.stderr)
    print(f"Debug: Found {len(sarif_data.get('runs', []))} runs", file=sys.stderr)
    
    suggestions_created = 0
    
    for run in sarif_data.get('runs', []):
        for result in run.get('results', []):
            # Check if result has fixes
            fixes = result.get('fixes', [])
            if not fixes:
                continue
                
            # Get the primary location for context
            locations = result.get('locations', [])
            if not locations:
                continue
                
            primary_location = locations[0]
            physical_location = primary_location.get('physicalLocation', {})
            artifact_location = physical_location.get('artifactLocation', {})
            region = physical_location.get('region', {})
            
            file_path = artifact_location.get('uri', '')
            start_line = region.get('startLine', 1)
            
            # Process each fix
            for fix in fixes:
                description = fix.get('description', {}).get('text', 'Suggested fix')
                artifact_changes = fix.get('artifactChanges', [])
                
                for change in artifact_changes:
                    change_location = change.get('artifactLocation', {})
                    change_file = change_location.get('uri', file_path)
                    
                    replacements = change.get('replacements', [])
                    for replacement in replacements:
                        deleted_region = replacement.get('deletedRegion', {})
                        inserted_content = replacement.get('insertedContent', {}).get('text', '')
                        
                        # Get the line number for the suggestion
                        suggestion_line = deleted_region.get('startLine', start_line)
                        
                        # Create environment variables for bash to pick up
                        print(f"FILE={change_file}")
                        print(f"LINE={suggestion_line}")  
                        print(f"DESCRIPTION={description}")
                        print(f"SUGGESTED_CODE={inserted_content}")
                        print("---SUGGESTION---")
                        
                        suggestions_created += 1
    
    print(f"TOTAL_SUGGESTIONS={suggestions_created}")
        
except Exception as e:
    print(f"Error processing SARIF: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Main function
main() {
    echo "Debug: Starting main function"
    echo "Debug: SARIF_FILE=$SARIF_FILE"
    echo "Debug: GITHUB_TOKEN is $([ -n "$GITHUB_TOKEN" ] && echo "set" || echo "not set")"
    echo "Debug: PR_NUMBER=$PR_NUMBER"
    echo "Debug: REPO_OWNER=$REPO_OWNER"
    echo "Debug: REPO_NAME=$REPO_NAME"
    echo "Debug: GITHUB_SHA=$GITHUB_SHA"
    
    # Check for required tools
    if ! command -v jq >/dev/null 2>&1; then
        echo "Error: jq is not installed"
        exit 1
    fi
    
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Error: python3 is not installed"
        exit 1
    fi
    
    if [ -z "$SARIF_FILE" ]; then
        log "No SARIF file provided"
        exit 1
    fi
    
    if [ -z "$GITHUB_TOKEN" ] || [ -z "$PR_NUMBER" ] || [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ] || [ -z "$GITHUB_SHA" ]; then
        log "Missing required environment variables"
        echo "GITHUB_TOKEN: $([ -n "$GITHUB_TOKEN" ] && echo "set" || echo "not set")"
        echo "PR_NUMBER: $PR_NUMBER"
        echo "REPO_OWNER: $REPO_OWNER" 
        echo "REPO_NAME: $REPO_NAME"
        echo "GITHUB_SHA: $GITHUB_SHA"
        exit 1
    fi
    
    log "Creating PR fix suggestions from SARIF file"
    
    # Process SARIF and create suggestions
    echo "Debug: About to process SARIF file: $SARIF_FILE"
    if [ ! -f "$SARIF_FILE" ]; then
        echo "Error: SARIF file does not exist: $SARIF_FILE"
        exit 1
    fi
    
    echo "Debug: SARIF file exists, size: $(wc -c < "$SARIF_FILE") bytes"
    
    local output
    output=$(process_sarif "$SARIF_FILE" "$SARIF_FILE")
    local process_exit_code=$?
    
    if [ $process_exit_code -ne 0 ]; then
        echo "Error: Failed to process SARIF file (exit code: $process_exit_code)"
        echo "Output: $output"
        exit 1
    fi
    
    echo "Debug: SARIF processing output:"
    echo "$output"
    
    local suggestions_count=0
    local current_file=""
    local current_line=""
    local current_description=""
    local current_code=""
    
    # Parse the output and create suggestions
    # Temporarily disable exit on error for the read loop
    set +e
    while IFS= read -r line; do
        if [[ $line == FILE=* ]]; then
            current_file="${line#FILE=}"
        elif [[ $line == LINE=* ]]; then
            current_line="${line#LINE=}"
        elif [[ $line == DESCRIPTION=* ]]; then
            current_description="${line#DESCRIPTION=}"
        elif [[ $line == SUGGESTED_CODE=* ]]; then
            current_code="${line#SUGGESTED_CODE=}"
        elif [[ $line == "---SUGGESTION---" ]]; then
            if [ -n "$current_file" ] && [ -n "$current_line" ] && [ -n "$current_code" ]; then
                add_suggestion "$current_file" "$current_line" "" "$current_code" "$current_description"
                suggestions_count=$((suggestions_count + 1))
            fi
            # Reset variables
            current_file=""
            current_line=""
            current_description=""
            current_code=""
        elif [[ $line == TOTAL_SUGGESTIONS=* ]]; then
            log "Found ${line#TOTAL_SUGGESTIONS=} potential fixes in SARIF"
        fi
    done <<< "$output"
    # Re-enable exit on error
    set -e
    
    # Create the review with all collected suggestions
    if [ $suggestions_count -gt 0 ]; then
        if create_review_with_suggestions; then
            log "Successfully created PR review with $suggestions_count suggestions"
        else
            echo "Warning: Failed to create PR review, but continuing..."
        fi
    else
        echo "Debug: No suggestions found, skipping review creation"
        log "No suggestions found in SARIF file"
    fi
}

# Run main function
main "$@" 