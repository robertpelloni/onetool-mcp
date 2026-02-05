# Repository Rules

## Tag Naming

Version tags follow semantic versioning with `v` prefix:

| Pattern | Example | Description |
|---------|---------|-------------|
| `v{major}.{minor}.{patch}` | `v1.0.0` | Stable release |
| `v{major}.{minor}.{patch}rc{n}` | `v1.0.0rc3` | Release candidate |
| `v{major}.{minor}.{patch}b{n}` | `v1.0.0b1` | Beta release |
| `{descriptive-name}` | `pre-rebrand-merge` | Snapshot/milestone tag |

## Branch Naming

| Pattern | Example | Description |
|---------|---------|-------------|
| `main` | `main` | Main development branch |
| `feature/{name}` | `feature/config-refactor` | Feature branches |
| `fix/{name}` | `fix/auth-bug` | Bug fix branches |
| `release/{version}` | `release/1.0.0` | Release preparation branches |

## Merge Strategy

**Feature to Main:**
```bash
git checkout main
git pull origin main
git merge feature/branch-name --no-ff -m "Merge feature/branch-name for v1.0.0rc3"
```

Use `--no-ff` to create explicit merge commits for feature branches. This preserves the feature branch history in the commit graph.

**Fast-forward only:** Use `--ff-only` for simple updates where main hasn't diverged.

## Release Workflow

1. Ensure feature branch is clean (no uncommitted changes)
2. Merge feature branch to main with `--no-ff`
3. Tag the release: `git tag -a v1.0.0rc3 -m "Release candidate 3 for version 1.0.0"`
4. Push main and tags: `git push origin main && git push origin v1.0.0rc3`

**Tag format:**
- Use annotated tags (`-a`) for all version releases
- Use descriptive messages that include the release type
- Always push tags explicitly after pushing main

## Branch Hygiene

- Delete feature branches after merging to main
- Keep main clean and deployable at all times
- No force pushes to main
- Feature branches should be short-lived (days, not weeks)
