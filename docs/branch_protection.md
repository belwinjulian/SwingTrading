# Branch Protection on `main` (D-08)

This repo's `main` branch is protected. Direct pushes are blocked; every change goes through a pull request that must pass three CI status checks before it can merge.

## Required Status Checks

| Check       | What it runs                                                                                |
|-------------|---------------------------------------------------------------------------------------------|
| `lint`      | `ruff format --check .` and `ruff check .`                                                  |
| `typecheck` | `mypy` (strict scope on `src/screener/{indicators,signals,regime.py,sizing.py}` per D-10)   |
| `test`      | `uv run pytest -m "not slow"` (with `--cov-fail-under=80` from pyproject.toml)              |

These match the job names in `.github/workflows/ci.yml`.

## Settings (D-08)

- Require a pull request before merging: **ON**
- Required approvals: 0 (solo developer; this is `Require pull request` without reviewer enforcement)
- Require status checks to pass before merging: **ON**
- Required status checks: `lint`, `typecheck`, `test`
- Require branches to be up to date before merging: **ON** (forces rebase on stale PRs)
- Allow force pushes: **OFF**
- Allow deletions: **OFF**
- Linear history: **OFF** (squash-merge OR merge-commit both allowed)
- Restrict who can push to matching branches: not configured (admin override remains available — solo developer)

## Apply via gh CLI (preferred)

Run from the repo root after authenticating (`gh auth login`):

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/:owner/:repo/branches/main/protection \
  -F "required_status_checks[strict]=true" \
  -F "required_status_checks[contexts][]=lint" \
  -F "required_status_checks[contexts][]=typecheck" \
  -F "required_status_checks[contexts][]=test" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews[required_approving_review_count]=0" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=false" \
  -F "required_pull_request_reviews[require_code_owner_reviews]=false" \
  -F "restrictions=" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false" \
  -F "required_linear_history=false"
```

Replace `:owner/:repo` with the actual GitHub repo path (gh CLI substitutes when called from a clone with origin set).

## Apply via web UI (fallback)

1. Navigate to https://github.com/<owner>/<repo>/settings/branches
2. Click "Add branch protection rule"
3. Branch name pattern: `main`
4. Check "Require a pull request before merging"
5. Check "Require status checks to pass before merging"
   - Search for and add: `lint`, `typecheck`, `test`
   - Check "Require branches to be up to date before merging"
6. Uncheck "Allow force pushes"
7. Uncheck "Allow deletions"
8. Click "Create" / "Save changes"

## Verify

After applying:

```bash
gh api /repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts'
# Expected output: ["lint", "typecheck", "test"]
```

A subsequent PR with a deliberately-broken lint or test should be unmergeable until the issue is fixed.

## Why

D-08 in `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md`: "Required status checks = lint, typecheck, test. Require PR before merge. No force-push. ... One-time admin click; locks the gate forever."

This is the gate that turns CI from advisory ("the workflow ran and failed") into binding ("this PR cannot merge until lint/typecheck/test all pass"). Without it, FND-03 reduces to "CI runs" rather than "CI gates merges."
