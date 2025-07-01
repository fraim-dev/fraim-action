# Fraim Security Scan GitHub Action

A GitHub Action that runs [Fraim](https://github.com/fraim-dev/fraim) AI-powered security analysis on your code and automatically uploads the results to GitHub's Security tab using SARIF format.

## Features

- 🤖 **AI-Powered Analysis**: Uses advanced language models to detect security vulnerabilities
- 🎯 **Smart Scanning**: Option to scan only changed files in PRs for faster feedback
- 📊 **GitHub Integration**: Automatically uploads results to GitHub Security tab with annotations
- 💬 **Automatic PR Comments**: Adds detailed comments to PRs with scan results and links
- 🔧 **Configurable Workflows**: Supports code security analysis and Infrastructure as Code (IaC) scanning
- 📈 **Multiple AI Providers**: Support for Google Gemini and OpenAI models
- 🎨 **Rich Reporting**: Generates both SARIF and HTML reports

## Usage

### Basic Usage

Add this action to your workflow file (e.g., `.github/workflows/security.yml`):

```yaml
name: Security Scan

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write  # Required for uploading SARIF
      pull-requests: write    # Required for PR comments and annotations
    
    steps:
      - name: Run Fraim Security Scan
        uses: ./action  # Replace with actual action reference when published
        with:
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
          workflows: 'code'
          scan-changed-files-only: 'true'
```

### Advanced Configuration

```yaml
name: Comprehensive Security Scan

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly full scan

jobs:
  security-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      pull-requests: write
    
    steps:
      - name: Run Fraim Security Scan
        uses: ./action  # Replace with actual action reference when published
        with:
          # API Configuration
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
          model: 'gemini/gemini-2.5-flash'
          
          # Scan Configuration
          workflows: 'code,iac'
          confidence: '7'
          scan-changed-files-only: ${{ github.event_name == 'pull_request' }}
          file-patterns: '*.py *.js *.ts *.yaml *.yml *.tf'
          
          # PR Integration
          comment-pr: 'true'
          
          # Version
          fraim-version: 'latest'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `workflows` | Workflows to run (comma-separated). Available: `code`, `iac`, `all` | No | `all` |
| `gemini-api-key` | Google Gemini API key for AI analysis | No | - |
| `openai-api-key` | OpenAI API key (alternative to Gemini) | No | - |
| `model` | AI model to use for analysis | No | `gemini/gemini-2.5-flash` |
| `confidence` | Minimum confidence threshold (1-10) for filtering findings | No | `7` |
| `scan-changed-files-only` | Only scan files changed in the PR (`true`/`false`) | No | `true` |
| `file-patterns` | File patterns to scan (space-separated globs) | No | Uses workflow defaults |
| `fraim-version` | Version of Fraim to install | No | `latest` |
| `comment-pr` | Add a comment to the PR with scan results (`true`/`false`) | No | `true` |

## Outputs

| Output | Description |
|--------|-------------|
| `sarif-file` | Path to the generated SARIF file |
| `results-count` | Number of security findings detected |

## API Key Setup

### Google Gemini (Recommended)

1. Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Add it as a repository secret named `GEMINI_API_KEY`
3. Reference it in your workflow: `gemini-api-key: ${{ secrets.GEMINI_API_KEY }}`

### OpenAI (Alternative)

1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add it as a repository secret named `OPENAI_API_KEY`
3. Reference it in your workflow: `openai-api-key: ${{ secrets.OPENAI_API_KEY }}`
4. Set the model: `model: 'gpt-4'`

## Workflows

### Code Security Analysis (`code`)
Analyzes source code for security vulnerabilities including:
- SQL injection
- Cross-site scripting (XSS)
- Authentication issues
- Input validation problems
- And many more security patterns

### Infrastructure as Code Analysis (`iac`)
Scans infrastructure configuration files for:
- Cloud security misconfigurations
- Compliance violations
- Best practice deviations
- Resource security settings

### All Workflows (`all`)
Runs all available workflows for comprehensive security coverage.

## File Pattern Examples

You can customize which files to scan using the `file-patterns` input:

```yaml
# Scan only Python and JavaScript files
file-patterns: '*.py *.js *.ts'

# Scan configuration files
file-patterns: '*.yaml *.yml *.json *.tf *.tfvars'

# Scan everything (default behavior when not specified)
file-patterns: ''
```

## Permissions Required

Your workflow needs the following permissions:

```yaml
permissions:
  contents: read          # To checkout code
  security-events: write  # To upload SARIF to Security tab
  pull-requests: write    # To add PR comments and annotations
```

## PR Annotations and Comments

The action provides two types of PR feedback:

1. **SARIF Annotations**: Automatically created by GitHub when SARIF is uploaded - these appear as inline comments on specific lines of code
2. **PR Comments**: A summary comment showing scan results, configuration, and links to detailed findings

### Example PR Comment

When the action runs on a PR, it will automatically add a comment like:

```
🛡️ Fraim Security Scan Results

Workflows: code,iac
Model: gemini/gemini-2.5-flash
Confidence threshold: 7

⚠️ 3 security findings detected

Fraim found 3 potential security issues. Please review the Security tab for details.

📊 View detailed SARIF results

---
Scan scope: Changed files only
File patterns: *.py *.js *.ts

🤖 Powered by Fraim | Documentation | Report an issue
```

### Disable PR Comments

If you want to keep SARIF annotations but disable the summary comments:

```yaml
- uses: ./action
  with:
    gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
    comment-pr: 'false'
```

## Examples

### PR-Only Scanning

Scan only on pull requests and only changed files:

```yaml
name: PR Security Check

on:
  pull_request:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      pull-requests: write
    
    steps:
      - name: Security Scan
        uses: ./action
        with:
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
          workflows: 'code'
          scan-changed-files-only: 'true'
```

### Full Repository Scan

Comprehensive scan of the entire repository:

```yaml
name: Full Security Audit

on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday at 6 AM

jobs:
  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    
    steps:
      - name: Full Security Scan
        uses: ./action
        with:
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
          workflows: 'all'
          scan-changed-files-only: 'false'
          confidence: '6'  # Lower threshold for comprehensive audit
```

### Multi-Model Comparison

Run scans with different models for comparison:

```yaml
name: Multi-Model Security Scan

on:
  workflow_dispatch:  # Manual trigger

jobs:
  gemini-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - name: Gemini Security Scan
        uses: ./action
        with:
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
          model: 'gemini/gemini-2.5-flash'
          workflows: 'code'

  openai-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - name: OpenAI Security Scan
        uses: ./action
        with:
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
          model: 'gpt-4'
          workflows: 'code'
```

## Troubleshooting

### Common Issues

1. **No API Key**: Make sure you've set up either `GEMINI_API_KEY` or `OPENAI_API_KEY` in your repository secrets.

2. **Permission Denied**: Ensure your workflow has the required permissions (`security-events: write`).

3. **No Files Found**: Check your `file-patterns` input and make sure the files you want to scan match the patterns.

4. **Rate Limiting**: If you hit API rate limits, consider:
   - Using a lower confidence threshold
   - Scanning only changed files in PRs
   - Adding delays between workflow runs

### Debug Mode

To enable debug logging, you can modify the action to include debug flags. The action will output detailed information about what files are being scanned and any errors encountered.

## Security Considerations

- API keys are handled securely through GitHub Secrets
- SARIF files may contain code snippets - review artifact retention policies
- Consider using branch protection rules to require security scans to pass

## Support

- **Documentation**: [docs.fraim.dev](https://docs.fraim.dev)
- **Issues**: Report bugs via GitHub Issues
- **Community**: [Join the Slack community](https://join.slack.com/t/fraimworkspace/shared_invite/zt-38cunxtki-B80QAlLj7k8JoPaaYWUKNA)

## License

This action is provided under the MIT License. See the [LICENSE](../LICENSE) file for details. 