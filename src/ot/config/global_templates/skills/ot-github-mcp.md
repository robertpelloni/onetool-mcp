---
name: ot-github-mcp
description: GitHub MCP usage guide — official GitHub API integration for repository management, issues, and PRs
tags: [github, vcs, issues, prs]
---

# GitHub MCP Guide

## Toolsets

- **Repositories**: Browse code, search files, analyze commits, manage branches
- **Issues**: Create, update, list, search, and manage issues
- **Pull Requests**: Create PRs, review changes, merge, manage reviews
- **Actions**: Monitor workflows, analyze build failures, trigger runs
- **Code Security**: Review security findings, Dependabot alerts

## Setup

1. Create a GitHub Personal Access Token (PAT) at https://github.com/settings/tokens
2. Add to `~/.onetool/secrets.yaml`: `GITHUB_TOKEN: ghp_your_token_here`
3. Ensure the `github` server is in your servers.yaml and enabled

## Usage Patterns

- **Search before creating**: Use search tools to check for existing issues/PRs
- **Batch operations**: Use list tools to get multiple items at once
- **Code changes**: Create branch → make commits → create PR
- **Issue workflow**: `search_issues` → `get_issue` → `update_issue` or `create_issue_comment`

## Common Mistakes to Avoid

- Don't create duplicate issues — search first
- Don't forget to specify the repository (owner/repo format)
- Don't make multiple API calls when a single list/search call works
- Check PR status before attempting to merge

Full reference: https://onetool.beycom.online/reference/servers/github/
