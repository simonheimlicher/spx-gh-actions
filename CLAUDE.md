# SPX GitHub Actions

Reusable GitHub Actions workflows for Claude Code integration.

## Repository Structure

```
spx-gh-actions/
├── .github/
│   └── workflows/
│       ├── claude.yml              # @claude mention handler
│       └── claude-code-review.yml  # Automatic PR review
├── examples/
│   └── caller-workflows/           # Example workflows for consuming repos
├── CLAUDE.md                       # This file
└── README.md                       # User documentation
```

## Workflow Design Principles

1. **Reusable via `workflow_call`** - All workflows are designed to be called from other repos
2. **Sensible defaults** - Work out of the box with minimal configuration
3. **Security first** - Authorization checks prevent unauthorized access
4. **Configurable** - All behavior can be customized via inputs

## Making Changes

### Testing Changes

1. Push changes to a branch
2. Update a test repo to use `@branch-name` instead of `@main`
3. Trigger the workflow and verify behavior
4. Merge to main when satisfied

### Versioning

Use tags for stable versions:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Consumers can then use `@v1` for the latest v1.x.x.

## Security Considerations

- `CLAUDE_CODE_OAUTH_TOKEN` is passed as a secret, never exposed in logs
- Authorization checks use `author_association` to limit who can trigger
- Tool restrictions limit what Claude can do in the repo
