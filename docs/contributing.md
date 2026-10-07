# Contributing

## One-time setup

Install the backend and frontend dependencies as described in the project README, then install
the repository-level hooks:

```bash
npm install
```

The root install runs Husky's `prepare` script and configures the tracked hooks for this clone.

## Branch workflow

Create feature branches from an up-to-date `develop` branch:

```bash
git fetch origin
git switch develop
git pull --ff-only
git switch -c feature/short-description
```

Keep feature history linear. Update a branch with rebase, not merge:

```bash
git fetch origin
git rebase origin/develop
git push --force-with-lease
```

Do not use `git merge develop` or `git merge main` in a feature branch. The hooks reject outgoing
merge commits. A feature branch with unmerged commits older than three days is also rejected at
commit and push time. The age is based on commits unique to the branch because Git does not store
a portable branch-creation timestamp.

If a branch crosses that limit, refresh its commits before continuing:

```bash
git fetch origin
git rebase --force-rebase origin/develop
git push --force-with-lease
```

The policy uses the local `origin/develop` reference. Run `git fetch origin develop` before work
when that reference may be stale.

## Automated checks

Pre-commit runs:

- Ruff over the backend
- Biome over the frontend
- TypeScript type checking
- merge-history and three-day branch checks

Pre-push additionally runs:

- backend pytest tests
- the production web build
- branch-policy self-tests
- direct-`main`, already-integrated-branch, and merge-commit guards

Run the same full quality suite manually with:

```bash
npm run check
```

Hooks can be bypassed with `--no-verify`, so GitHub rules are the authoritative enforcement.

## Required GitHub rulesets

Create rulesets for `main` and `develop` in the repository settings:

1. Require a pull request before merging.
2. Require the `quality` status check.
3. Require at least one approval.
4. Require linear history.
5. Block force pushes and branch deletion.
6. Do not grant bypass permission to regular contributors.

Allow rebase merging or squash merging and disable merge commits. GitHub cannot enforce a useful
"branch older than three days" rule by itself; the local hook covers commit age, while repository
automation can later report inactive remote branches without blocking backups.
