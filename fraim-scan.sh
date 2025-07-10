#!/bin/bash

set -e

# Function to log messages
log() {
    echo "::debug::$1"
}

# Function to set GitHub Actions output
set_output() {
    echo "$1=$2" >> $GITHUB_OUTPUT
}

# Function to get changed files for PR
get_changed_files() {
    git diff --name-only ${GITHUB_BASE_SHA} ${GITHUB_SHA} | \
    grep -E '\.(py|js|ts|jsx|tsx|java|go|rb|php|cs|cpp|c|h|yaml|yml|tf|tfvars|json)$' | \
    tr '\n' ' ' || true
}

# Main function
main() {
    log "Starting Fraim Security Scan"
    
    # Create output directory
    mkdir -p fraim_outputs
    
    # Prepare Fraim arguments
    FRAIM_ARGS="--output fraim_outputs"
    FRAIM_ARGS="$FRAIM_ARGS --model ${INPUT_MODEL:-gemini/gemini-2.5-flash}"
    FRAIM_ARGS="$FRAIM_ARGS --workflows $(echo "${INPUT_WORKFLOWS:-code}" | tr ',' ' ')"
    
    # Determine what to scan
    if [ "${GITHUB_EVENT_NAME}" = "pull_request" ]; then
        echo "Scanning changed files only..."
        
        # Get changed files with proper filtering
        CHANGED_FILES=$(get_changed_files)
        
        if [ -z "$CHANGED_FILES" ]; then
            echo "No relevant files changed in this PR"
            set_output "sarif-file" ""
            set_output "results-count" "0"
            exit 0
        fi
        
        echo "Changed files to scan: $CHANGED_FILES"
        
        # Use file patterns instead of copying files to preserve paths for PR annotations
        FRAIM_ARGS="$FRAIM_ARGS --path ."
        CHANGED_GLOBS=""
        for file in $CHANGED_FILES; do
            if [ -f "$file" ]; then
                CHANGED_GLOBS="$CHANGED_GLOBS $file"
            fi
        done
        
        if [ -n "$CHANGED_GLOBS" ]; then
            FRAIM_ARGS="$FRAIM_ARGS --globs $CHANGED_GLOBS"
        fi
    else
        echo "Scanning entire repository..."
        FRAIM_ARGS="$FRAIM_ARGS --path ."
    fi
    
    echo "Running: uv run fraim $FRAIM_ARGS"
    
    # Run Fraim
    uv run fraim $FRAIM_ARGS
    
    # Find the SARIF file
    SARIF_FILE=$(find fraim_outputs -name "*.sarif" -type f | head -1)
    
    if [ -n "$SARIF_FILE" ] && [ -f "$SARIF_FILE" ]; then
        echo "Found SARIF file: $SARIF_FILE"
        
        # Count results in SARIF file
        RESULTS_COUNT=$(python3 -c "import json; data=json.load(open('$SARIF_FILE')); print(sum(len(run.get('results', [])) for run in data.get('runs', [])))" 2>/dev/null || echo "0")
        
        set_output "sarif-file" "$SARIF_FILE"
        set_output "results-count" "$RESULTS_COUNT"
        echo "Found $RESULTS_COUNT security findings"
    else
        echo "No SARIF file generated"
        set_output "sarif-file" ""
        set_output "results-count" "0"
    fi
    
    log "Fraim Security Scan completed"
}

# Run main function
main "$@" 