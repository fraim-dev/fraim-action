# AI-powered Security Workflows

Fraim provides specialized AI-powered workflows for different types of security analysis. Each workflow is optimized for specific use cases and file types, allowing you to choose the right tool for your security needs.

## Available Workflows

### ⚠️ Risk Flagger
**Workflow ID**: `risk_flagger`

Identifies code changes that require security team review and investigation. Integrates with Github and allows you to loop in a reviewer and block a PR until that reviewer approves.

[Docs](https://docs.fraim.dev/workflows/risk_flagger#github-actions)

```bash
name: Risk Assessment
on:
  pull_request:
    branches: [dev]
  pull_request_review:
    types: [submitted]

jobs:
  risk-assessment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Run Fraim Risk Flagger Scan
        id: fraim-scan
        uses: fraim-dev/fraim-action@v0
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          workflow: risk_flagger
          workflow_args: |
            {
              "approver": "security",
              "should-block-pull-request": true,
              "custom-risk-list-json": {
                "Change Protection": "All changes to sensitive_data.py should be flagged.",
                "API Changes": "Any modifications to API endpoints require security review."
              },
              "custom-risk-list-action": "replace",
              "chunk-size": 5000,
              "confidence": 7
            }
          github-token: ${{ secrets.GH_TOKEN }}
```

### 🔍 Code Security Analysis
**Workflow ID**: `code`

Static analysis of application source code for security vulnerabilities.

[Docs](https://docs.fraim.dev/workflows/code#github-actions)

```bash
name: Code Security Analysis
on:
  pull_request:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Fraim Code Security Scan
        uses: fraim-dev/fraim-action@94198c06f33e74d44d94261c25423ca972b51031
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          workflow: code
```

### 🏗️ Infrastructure as Code Analysis
**Workflow ID**: `iac`

Security analysis of infrastructure configuration files and deployment manifests.

[Docs](https://docs.fraim.dev/workflows/iac#github-actions)

```bash
name: IaC Security
on:
  pull_request:
    branches: [main]

jobs:
  iac-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Fraim IaC Security Scan
        uses: fraim-dev/fraim-action@94198c06f33e74d44d94261c25423ca972b51031
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          workflow: iac
```

### 📋 System Analysis
**Workflow ID**: `system_analysis`

Extracts system purpose, users, and business context from codebases and documentation.

[Docs](https://docs.fraim.dev/workflows/system_analysis#github-actions)

```bash
name: System Analysis
on:
  workflow_dispatch:
    inputs:
      business_context:
        description: 'Business context for analysis'
        required: false
        default: 'Web application'

jobs:
  system-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Fraim System Analysis
        uses: fraim-dev/fraim-action@94198c06f33e74d44d94261c25423ca972b51031
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          workflow: system_analysis
          workflow_args: |
            {
              "business-context": "${{ github.event.inputs.business_context }}",
              "focus-areas": ["security", "authentication", "data_processing"]
            }
      
      - name: Upload Analysis
        uses: actions/upload-artifact@v3
        with:
          name: system-analysis
          path: fraim_output/system_analysis_*.json
```
