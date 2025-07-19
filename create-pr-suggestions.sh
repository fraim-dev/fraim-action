#!/bin/bash

set -e

SARIF_FILE="$1"

# Function to log messages
log() {
    echo "::debug::$1"
}

# Function to create a PR review comment with suggestion
create_suggestion() {
    local file="$1"
    local line="$2"
    local original_code="$3"
    local suggested_code="$4"
    local description="$5"
    
    # Escape special characters for JSON
    original_code=$(echo "$original_code" | jq -R .)
    suggested_code=$(echo "$suggested_code" | jq -R .)
    description=$(echo "$description" | jq -R .)
    
    # Create suggestion format
    local suggestion_body
    suggestion_body=$(cat << EOF
$description

\`\`\`suggestion
$suggested_code
\`\`\`
EOF
)
    
    # Create review comment via GitHub API
    local comment_data
    comment_data=$(jq -n \
        --arg body "$suggestion_body" \
        --arg path "$file" \
        --argjson line "$line" \
        '{
            body: $body,
            path: $path,
            line: $line
        }')
    
    log "Creating suggestion for $file:$line"
    
    curl -s -X POST \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/pulls/$PR_NUMBER/comments" \
        -d "$comment_data" || true
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
    python3 << 'EOF'
import json
import sys
import os

sarif_file = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SARIF_FILE')

try:
    with open(sarif_file, 'r') as f:
        sarif_data = json.load(f)
    
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
    if [ -z "$SARIF_FILE" ]; then
        log "No SARIF file provided"
        exit 1
    fi
    
    if [ -z "$GITHUB_TOKEN" ] || [ -z "$PR_NUMBER" ] || [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
        log "Missing required environment variables"
        exit 1
    fi
    
    log "Creating PR fix suggestions from SARIF file"
    
    # Process SARIF and create suggestions
    local output
    output=$(process_sarif "$SARIF_FILE" "$SARIF_FILE")
    
    local suggestions_count=0
    local current_file=""
    local current_line=""
    local current_description=""
    local current_code=""
    
    # Parse the output and create suggestions
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
                create_suggestion "$current_file" "$current_line" "" "$current_code" "$current_description"
                ((suggestions_count++))
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
    
    log "Created $suggestions_count PR review suggestions"
}

# Run main function
main "$@" 