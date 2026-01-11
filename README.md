# SPX GitHub Actions

Reusable GitHub Actions workflows for Claude Code integration.

## Available Workflows

| Workflow | Description |
|----------|-------------|
| `claude.yml` | Interactive Claude assistant triggered by `@claude` mentions |
| `claude-code-review.yml` | Automatic code review on pull requests |

## Quick Start

### 1. Set up secrets

Add `CLAUDE_CODE_OAUTH_TOKEN` to your repository secrets. See [Syncing Secrets](#syncing-secrets) below for an automated approach.

### 2. Create workflow files

**For `@claude` mentions** - create `.github/workflows/claude.yml`:

```yaml
name: Claude Code

on:
  issue_comment:
    types: [created, edited]
  pull_request_review_comment:
    types: [created, edited]
  issues:
    types: [opened, assigned]
  pull_request_review:
    types: [submitted]

jobs:
  claude:
    uses: simonheimlicher/spx-gh-actions/.github/workflows/claude.yml@main
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
    with:
      authorized_roles: '["OWNER", "MEMBER", "COLLABORATOR"]'
      mention_trigger: '@claude'
```

**For automatic PR reviews** - create `.github/workflows/claude-code-review.yml`:

```yaml
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    uses: simonheimlicher/spx-gh-actions/.github/workflows/claude-code-review.yml@main
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
    with:
      authorized_roles: '["OWNER", "MEMBER", "COLLABORATOR"]'
```

## Configuration

### claude.yml Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `authorized_roles` | `["OWNER", "MEMBER", "COLLABORATOR"]` | JSON array of GitHub author associations allowed to trigger |
| `mention_trigger` | `@claude` | Text that triggers the workflow |
| `concurrency_cancel` | `true` | Cancel in-progress runs on new mention |
| `allowed_tools` | (unrestricted) | Claude Code `--allowed-tools` argument |
| `custom_prompt` | (empty) | Override default behavior with custom prompt |

### claude-code-review.yml Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `authorized_roles` | `["OWNER", "MEMBER", "COLLABORATOR"]` | JSON array of GitHub author associations allowed |
| `concurrency_cancel` | `false` | Cancel in-progress reviews on new PR update |
| `allowed_tools` | (gh read/comment only) | Claude Code `--allowed-tools` argument |
| `custom_prompt` | (default review prompt) | Custom review instructions |

## Security

Both workflows include authorization checks. Only users with matching `author_association` can trigger Claude workflows.

**Best practices:**

- Never allow `CONTRIBUTOR` or `FIRST_TIME_CONTRIBUTOR` in production
- Restrict `allowed_tools` to minimum required
- Rotate tokens if compromise is suspected

## Syncing Secrets

Managing the same secret across multiple repositories is tedious. The `sync-secrets.py` script automates this by:

1. Reading the secret value from your **macOS Keychain** (no manual input needed)
2. Syncing it to all configured repositories via `gh secret set`

### Prerequisites

- macOS (for Keychain integration)
- `gh` CLI authenticated (`gh auth login`)
- `uv` for running the script

### Usage

```bash
# Check which repos have/need the secret
uv run scripts/sync-secrets.py list

# Preview what would be synced
uv run scripts/sync-secrets.py sync --dry-run --all

# Sync secrets (reads from Keychain automatically)
uv run scripts/sync-secrets.py sync --all
```

### Configuration

Edit `scripts/secrets.yaml` to define secrets and target repositories:

```yaml
secrets:
  CLAUDE_CODE_OAUTH_TOKEN:
    description: OAuth token for Claude Code GitHub Action
    keychain:
      service: Claude Code-credentials       # Keychain item name
      json_path: claudeAiOauth.accessToken   # JSON path to extract

repos:
  simonheimlicher/spx-gh-actions:
    secrets:
      - CLAUDE_CODE_OAUTH_TOKEN
  simonheimlicher/another-repo:
    secrets:
      - CLAUDE_CODE_OAUTH_TOKEN
```

### How Keychain Integration Works

The script uses macOS `security` CLI to read from your login keychain:

```bash
security find-generic-password -s "Claude Code-credentials" -a "$USER" -w
```

On first run, macOS will prompt you to allow access. Click "Always Allow" to avoid future prompts.

If the keychain lookup fails, the script falls back to prompting for the value.

## License

MIT
