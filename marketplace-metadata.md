# GitHub Actions Marketplace Metadata

## Publishing Information

When publishing this action to the GitHub Actions Marketplace, use the following information:

### Repository Setup
- Repository name: `fraim-action`
- Description: "AI-powered security analysis for your code with SARIF output"
- Topics: `security`, `ai`, `static-analysis`, `sarif`, `vulnerability-scanning`, `github-actions`

### Release Process
1. Create a new repository for the action (separate from main fraim repo)
2. Copy contents of this `action/` folder to the root of the new repository
3. Create releases using semantic versioning (v1.0.0, v1.1.0, etc.)
4. Create major version tags (v1, v2) that point to latest minor/patch releases

### Action Marketplace Categories
- Primary category: **Security**
- Secondary categories: **Code Quality**, **Utilities**

### Keywords for Discovery
- `security-scanning`
- `vulnerability-analysis`
- `ai-powered`
- `sarif`
- `static-analysis`
- `code-security`
- `infrastructure-as-code`
- `gemini`
- `openai`

### Versioning Strategy
- v1.x.x: Initial stable release
- v2.x.x: Breaking changes (if needed)
- Use `v1` tag that always points to latest v1.x.x release

### Release Notes Template
```markdown
## What's Changed
- Feature/fix descriptions
- Breaking changes (if any)
- New configuration options

## Usage
```yaml
- uses: fraim-dev/fraim-action@v1
  with:
    gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

**Full Changelog**: https://github.com/fraim-dev/fraim-action/compare/v1.0.0...v1.1.0
``` 