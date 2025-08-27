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

# Function to get changed files for PR (kept for backward compatibility/debugging)
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
    
    # Prepare global Fraim arguments (these must come BEFORE the workflow subcommand)
    GLOBAL_ARGS="--output fraim_outputs"
    
    # Add confidence if specified
    if [ -n "${INPUT_CONFIDENCE}" ]; then
        GLOBAL_ARGS="$GLOBAL_ARGS --confidence ${INPUT_CONFIDENCE}"
    fi
    
    # Add model if specified
    if [ -n "${INPUT_MODEL}" ]; then
        GLOBAL_ARGS="$GLOBAL_ARGS --model ${INPUT_MODEL}"
    fi
    
    # Parse workflows (comma-separated list)
    WORKFLOWS=$(echo "${INPUT_WORKFLOWS:-code}" | tr ',' ' ')
    
    # Determine scan location and diff args
    LOCATION_ARGS="--location ."
    DIFF_ARGS=""
    
    if [ "${GITHUB_EVENT_NAME}" = "pull_request" ]; then
        echo "Scanning PR diff using --diff mode..."
        
        # Verify we have the required SHAs
        if [ -z "$GITHUB_BASE_SHA" ] || [ -z "$GITHUB_SHA" ]; then
            echo "ERROR: Missing base or head SHA for PR diff scanning"
            echo "GITHUB_BASE_SHA: $GITHUB_BASE_SHA"
            echo "GITHUB_SHA: $GITHUB_SHA"
            exit 1
        fi
        
        echo "Base SHA: $GITHUB_BASE_SHA"
        echo "Head SHA: $GITHUB_SHA"
        
        # Use diff mode for PR scanning
        DIFF_ARGS="--diff true --base $GITHUB_BASE_SHA --head $GITHUB_SHA"
    else
        echo "Scanning entire repository..."
        # No diff args needed for full repository scan
    fi
    
    # Run Fraim for each workflow
    for workflow in $WORKFLOWS; do
        echo "Running workflow: $workflow"
        
        # Build workflow-specific arguments (these come AFTER the workflow subcommand)
        WORKFLOW_ARGS="$LOCATION_ARGS"
        
        # Add diff arguments if this is a PR scan
        if [ -n "$DIFF_ARGS" ]; then
            WORKFLOW_ARGS="$WORKFLOW_ARGS $DIFF_ARGS"
        fi
        
        # Build the complete command: fraim [global_args] [workflow] [workflow_args]
        CMD="uv tool run fraim $GLOBAL_ARGS $workflow $WORKFLOW_ARGS"
        
        echo "Running: $CMD"
        
        # Run the specific workflow
        $CMD
    done
    
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