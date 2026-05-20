---
phase: 01-repo-skeleton-ci-hygiene
plan: 05
type: execute
wave: 4
depends_on: ["01-01", "01-02", "01-03", "01-04"]
files_modified:
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
  - docs/branch_protection.md
autonomous: false
requirements: [FND-03]
must_haves:
  truths:
    - "Opening any pull request triggers GitHub Actions CI with three parallel jobs: lint, typecheck, test"
    - "Push to main also triggers the CI workflow (D-06)"
    - "All three CI jobs use astral-sh/setup-uv@v6 with enable-cache: true keyed on uv.lock (D-09)"
    - "Each CI job runs `uv sync --frozen --extra dev` (D-09)"
    - "lint job runs ruff format --check and ruff check"
    - "typecheck job runs mypy (uses pyproject.toml [tool.mypy] config — strict scope on indicators/, signals/, regime, sizing per D-10)"
    - "test job runs pytest (with --cov-fail-under=80 from pyproject.toml; trivially satisfied at Phase 1)"
    - "Pre-commit hook config runs ruff format + ruff check + mypy on staged files; pytest is NOT in pre-commit (D-07)"
    - "Branch protection on main is documented and enforced; required status checks = lint, typecheck, test (D-08)"
  artifacts:
    - path: ".github/workflows/ci.yml"
      provides: "GitHub Actions CI with three parallel jobs (D-05, D-06, D-09)"
      contains: "astral-sh/setup-uv@v6"
    - path: ".pre-commit-config.yaml"
      provides: "Local pre-commit hooks: ruff format + ruff check + mypy (D-07)"
      contains: "ruff"
    - path: "docs/branch_protection.md"
      provides: "Documented procedure for the one-time admin action to apply branch protection on main (D-08)"
      contains: "lint"
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "uv.lock"
      via: "uv sync --frozen --extra dev (fails if lockfile drifts)"
      pattern: "uv sync --frozen"
    - from: ".github/workflows/ci.yml"
      to: "tests/test_architecture.py + tests/test_cli_smoke.py"
      via: "test job runs pytest, which exercises both"
      pattern: "uv run pytest"
    - from: "docs/branch_protection.md"
      to: ".github/workflows/ci.yml job names"
      via: "required status checks reference job names lint/typecheck/test"
      pattern: "(lint|typecheck|test)"
---

<objective>
Wire CI gates and the local pre-commit guard, then document branch protection (the one-time admin action). After this plan ships:
1. Every PR and push-to-main runs three parallel CI jobs (lint, typecheck, test).
2. Local commits run ruff + mypy via pre-commit; pytest stays CI-only to keep the local loop fast (D-07).
3. Branch protection on `main` is documented; the user runs the gh API command (or web UI click) to apply it (D-08).

Task 3 is non-autonomous: applying branch protection requires repo-admin GitHub privileges that Claude cannot perform. The plan ships clear instructions with the exact gh CLI invocation.

Purpose: FND-03 requires CI to run ruff + mypy --strict on the math modules + pytest on every PR. This plan delivers it.

Output: A repo where (a) CI catches lint/type/test failures pre-merge, (b) pre-commit catches lint/type failures pre-push, and (c) branch protection prevents direct-to-main pushes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md
@.planning/REQUIREMENTS.md
@CLAUDE.md
@pyproject.toml
@uv.lock
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author .github/workflows/ci.yml with three parallel jobs</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-05, D-06, D-09 — exact CI shape)
    - .planning/REQUIREMENTS.md (FND-03 — full requirement)
    - pyproject.toml (confirms python = "==3.11.*" and dev extra exists)
    - uv.lock (must exist before this plan runs)
  </read_first>
  <files>.github/workflows/ci.yml</files>
  <action>
Create `.github/workflows/ci.yml` with the EXACT content below.

Notes:
- Triggers: `pull_request` (any branch) + `push` to `main` (D-06).
- Three parallel jobs named `lint`, `typecheck`, `test` — these names are the contract for branch-protection required status checks (D-08).
- Each job uses `astral-sh/setup-uv@v6` with `enable-cache: true` (D-09); cache key is derived from `uv.lock`.
- Each job runs `uv sync --frozen --extra dev` (D-09 — `--frozen` fails if lockfile drifts from pyproject.toml).
- Python version comes from `pyproject.toml` (`requires-python = "==3.11.*"`); `uv python install` resolves it.
- A 10-minute job timeout protects against runaway runs.

Run `mkdir -p .github/workflows` first, then write the file with this content:

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

# Cancel superseded runs on the same branch.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  lint:
    name: lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev

      - name: ruff format --check
        run: uv run ruff format --check .

      - name: ruff check
        run: uv run ruff check .

  typecheck:
    name: typecheck
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev

      - name: mypy --strict (math modules; scope from pyproject.toml [tool.mypy])
        run: uv run mypy

  test:
    name: test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev

      - name: pytest (with coverage gate from pyproject.toml)
        run: uv run pytest -m "not slow" -v
```
  </action>
  <verify>
    <automated>test -f .github/workflows/ci.yml &amp;&amp; grep -F 'astral-sh/setup-uv@v6' .github/workflows/ci.yml &amp;&amp; grep -F 'uv sync --frozen --extra dev' .github/workflows/ci.yml &amp;&amp; grep -F 'enable-cache: true' .github/workflows/ci.yml &amp;&amp; grep -cE '^[[:space:]]+name: (lint|typecheck|test)$' .github/workflows/ci.yml | grep -qE '^[3-9]$'</automated>
  </verify>
  <acceptance_criteria>
    - `.github/workflows/ci.yml` exists
    - File contains the three job names `lint`, `typecheck`, `test` (verify with `grep -cE '^[[:space:]]+name: (lint|typecheck|test)$' .github/workflows/ci.yml` returns 3)
    - File contains `astral-sh/setup-uv@v6` (D-09)
    - File contains `enable-cache: true` and `cache-dependency-glob: "uv.lock"` (D-09)
    - File contains `uv sync --frozen --extra dev` (appears in all three jobs)
    - File contains `uv run ruff format --check .` (lint job)
    - File contains `uv run ruff check .` (lint job)
    - File contains `uv run mypy` (typecheck job)
    - File contains `uv run pytest` (test job)
    - Triggers section contains `pull_request` and `push:` with `branches: [main]` (D-06)
    - File is valid YAML (verify by parsing: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0)
  </acceptance_criteria>
  <done>CI workflow file shipped with three parallel jobs matching D-05/D-06/D-09. Every PR and push-to-main now runs lint, typecheck, and test in parallel.</done>
</task>

<task type="auto">
  <name>Task 2: Author .pre-commit-config.yaml with ruff + mypy hooks (no pytest per D-07)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-07 — pre-commit = ruff + mypy --quick; NO pytest)
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-10 — mypy strict scope)
    - pyproject.toml (confirms ruff and mypy are dev deps)
  </read_first>
  <files>.pre-commit-config.yaml</files>
  <action>
Create `.pre-commit-config.yaml` at the repo root with the EXACT content below.

Decisions:
- Use the official `astral-sh/ruff-pre-commit` and `pre-commit/mirrors-mypy` repos. Pin to versions matching the dev deps in pyproject.toml (`ruff>=0.15,<0.16`; `mypy>=1.20,<2`).
- ruff format runs first (auto-fixes), then ruff check (reports remaining issues), then mypy.
- mypy hook explicitly scoped to the strict-scope directories (D-10) so the pre-commit doesn't waste time on non-strict files. Pass `--no-incremental` per D-07 ("mypy --quick" — D-07 wording; this matches modern mypy's no-incremental flag intent: skip the cache to ensure fresh results on staged files).
- Pytest is intentionally NOT included (D-07: "Pytest is CI-only — keeps the local commit loop fast.").

```yaml
# Pre-commit hooks per D-07: ruff format + ruff check + mypy on staged files.
# Pytest is NOT here (CI-only) to keep the local commit loop fast.
#
# Install once: `uvx pre-commit install`
# Run manually:  `uvx pre-commit run --all-files`

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff-format
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.20.0
    hooks:
      - id: mypy
        name: mypy (math modules — strict scope per D-10)
        args:
          - --no-incremental
          - --config-file=pyproject.toml
        # mypy needs deps to resolve types; provide the runtime + dev set.
        additional_dependencies:
          - pandas>=2.2,<3
          - numpy>=2,<3
          - pydantic-settings>=2.14,<3
          - pandera>=0.31.1,<0.32
          - structlog>=25.5,<26
          - typer>=0.25,<0.26
          - pandas-stubs
          - types-requests
        # Restrict the hook to the strict-scope directories from D-10 so
        # pre-commit doesn't waste time on data/, publishers/, etc. (those
        # are loosened via [[tool.mypy.overrides]] anyway).
        files: ^src/screener/(indicators|signals|regime\.py|sizing\.py)
```

Notes for the executor:
- The pinned `ruff-pre-commit` rev `v0.15.12` matches the dev-deps range `ruff>=0.15,<0.16` in pyproject.toml. If a newer `0.15.x` patch is released by execution time, bumping the rev is acceptable.
- Same pattern for `mirrors-mypy` rev — match the major+minor of the pyproject pin.
- Do NOT add a `pytest` hook (D-07). If a contributor later wants pytest on push, they can add a custom hook locally; the committed config keeps the loop fast.
  </action>
  <verify>
    <automated>test -f .pre-commit-config.yaml &amp;&amp; grep -F 'ruff-pre-commit' .pre-commit-config.yaml &amp;&amp; grep -F 'mirrors-mypy' .pre-commit-config.yaml &amp;&amp; ! grep -E '(pytest|^[[:space:]]+- id: pytest)' .pre-commit-config.yaml &amp;&amp; uv run python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"</automated>
  </verify>
  <acceptance_criteria>
    - `.pre-commit-config.yaml` exists
    - File contains `astral-sh/ruff-pre-commit` (ruff hook)
    - File contains `pre-commit/mirrors-mypy` (mypy hook)
    - File contains hook ids `ruff-format`, `ruff`, `mypy`
    - File does NOT contain `pytest` (D-07: CI-only)
    - File is valid YAML (`uv run python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"` exits 0)
    - mypy hook's `files:` regex restricts scope to `src/screener/(indicators|signals|regime\.py|sizing\.py)` per D-10
    - `uvx pre-commit install` succeeds (smoke check; user runs locally)
  </acceptance_criteria>
  <done>Pre-commit hooks shipped: ruff (format + check) and mypy run on staged files; pytest stays CI-only per D-07.</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 3: Apply branch protection to main (one-time admin action — D-08)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-08 — full branch-protection contract)
    - .github/workflows/ci.yml (just authored — confirms job names lint/typecheck/test)
  </read_first>
  <files>docs/branch_protection.md</files>
  <action>
Step 1 (autonomous): Create `docs/branch_protection.md` with the EXACT content below. This documents the one-time admin action so the user (or a future contributor) can re-apply it on a fork.

Step 2 (NON-AUTONOMOUS — user runs): The user (Belwin) executes the `gh` CLI command (or clicks through the GitHub web UI) to apply branch protection. Claude cannot do this — it requires repo-admin OAuth scope on GitHub that the local CLI session does not have.

**`docs/branch_protection.md`** content:

```markdown
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
```

After writing the doc, **STOP** and surface this checkpoint to the user. The user must run the gh command (or click through the web UI) before this task is complete.
  </action>
  <what-built>
- `docs/branch_protection.md` documenting the exact branch-protection contract from D-08, including a copy-paste-ready `gh api` invocation and a web-UI fallback procedure.
  </what-built>
  <how-to-verify>
After Claude writes `docs/branch_protection.md`, the user (Belwin) must run the gh CLI command from the doc OR click through the web UI:

1. Run `gh auth status` to confirm gh is authenticated with sufficient scope (admin:repo or fine-grained PAT with branch-protection write).
2. Copy the `gh api ... /repos/:owner/:repo/branches/main/protection ...` command from `docs/branch_protection.md`.
3. Run it from the repo root.
4. Verify with: `gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'` — expected output: `["lint","typecheck","test"]`.
5. As a sanity check, attempt a direct push to main from a non-protected source — it should be rejected.

If gh CLI is not installed or the user prefers the web UI:
1. Open https://github.com/<owner>/<repo>/settings/branches
2. Follow the "Apply via web UI (fallback)" steps in `docs/branch_protection.md`.
3. Confirm the rule appears in the branch-protection list with `lint`, `typecheck`, `test` as required checks.
  </how-to-verify>
  <resume-signal>Reply with "branch protection applied" (and ideally paste the verify-command output) once the rule is live on main.</resume-signal>
  <acceptance_criteria>
    - `docs/branch_protection.md` exists at the documented path
    - File contains the literal job names `lint`, `typecheck`, `test`
    - File contains the gh CLI invocation as a runnable code block
    - File contains a web-UI fallback procedure
    - User confirms branch protection is applied on main (resume signal: "branch protection applied")
    - Post-confirmation: `gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'` returns `["lint","typecheck","test"]` (or equivalent — order may vary)
  </acceptance_criteria>
  <done>docs/branch_protection.md committed AND branch protection live on main with the three required status checks.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub-PR ↔ main-branch | The gate that prevents direct merges of unverified code; bypassing it breaks every other Phase 1 invariant |
| GitHub-Actions runner ↔ external-pypi | uv sync pulls third-party packages on every CI run |
| pre-commit hooks ↔ developer commit | Local guardrail; can be bypassed with `git commit --no-verify` (acceptable; CI is the binding gate) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01 | Tampering | Direct push to main | mitigate | Branch protection (Task 3) requires PR + passing status checks (lint/typecheck/test) before merge; force-push disabled; deletion disabled (D-08) |
| T-05-02 | Tampering | uv.lock drift in CI | mitigate | All three jobs use `uv sync --frozen --extra dev` (D-09); `--frozen` fails the run if lockfile and pyproject.toml have drifted, preventing silent dependency upgrades |
| T-05-03 | Spoofing | Forked-PR pulling secrets | mitigate | `permissions: contents: read` at workflow level; no secrets used in any CI step at Phase 1 (no API calls in stubs); GitHub default policy already restricts secrets exposure to forks |
| T-05-04 | Tampering | astral-sh/setup-uv@v6 supply chain | accept | setup-uv is Astral's official action, widely used; pinned to major version v6; risk acceptable for personal-trading repo within $0 budget. SHA-pin upgrade path available if needed in M2 |
| T-05-05 | Tampering | actions/checkout@v4 supply chain | accept | actions/checkout is GitHub's official action; same risk profile as setup-uv |
| T-05-06 | Elevation of Privilege | pre-commit bypass via --no-verify | accept | Local hooks are advisory; CI is the binding gate. Branch protection means a developer cannot land --no-verify code without CI catching the violation in the PR |
| T-05-07 | Information Disclosure | CI logs leak secrets | mitigate | Phase 1 jobs reference no secrets. Phase 2+ (when API keys land in CI) MUST use GitHub's `secrets:` syntax and never `echo` them. This concern is escalated to Phase 8 ops planning |
| T-05-08 | Denial of Service | Runaway CI job | mitigate | Each job has `timeout-minutes: 10`; concurrency cancels superseded runs on the same branch |

</threat_model>

<verification>
After Tasks 1 and 2 complete (autonomous):
1. `.github/workflows/ci.yml` exists and is valid YAML
2. `.pre-commit-config.yaml` exists and is valid YAML
3. `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.pre-commit-config.yaml'))"` exits 0
4. `grep -E '^[[:space:]]+name: (lint|typecheck|test)$' .github/workflows/ci.yml` returns 3 matches
5. `grep -F 'pytest' .pre-commit-config.yaml` returns NO matches (D-07)
6. `uvx pre-commit install` exits 0 (smoke check)
7. `uvx pre-commit run --all-files` exits 0 against the Phase 1 source tree (no lint/type errors in the scaffolded code)

After Task 3 (non-autonomous, user-run):
8. `docs/branch_protection.md` exists
9. User confirms `gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'` returns `["lint","typecheck","test"]` (order-insensitive)
10. End-to-end gate validation: opening a PR that fails any of the three checks cannot be merged

End-to-end FND-03 validation (after Task 3):
- Open a PR. CI runs three jobs. All pass (Phase 1 source tree is clean). PR is mergeable.
- Force-push to main is rejected.
- Direct push to main is rejected.
</verification>

<success_criteria>
- `.github/workflows/ci.yml` ships three parallel jobs (lint, typecheck, test) per D-05/D-06/D-09 (FND-03 met for the CI-runs portion)
- `.pre-commit-config.yaml` ships ruff + mypy hooks; pytest is intentionally absent per D-07
- `docs/branch_protection.md` documents the one-time admin action with both gh CLI and web UI procedures
- After user runs the gh command (or web UI click), branch protection is live on main with `lint`, `typecheck`, `test` as required status checks (D-08)
- Phase 1 success criterion 3 met: opening any PR triggers CI; all three checks must pass to merge
</success_criteria>

<output>
After completion, create `.planning/phases/01-repo-skeleton-ci-hygiene/01-05-SUMMARY.md` with:
- Files created (.github/workflows/ci.yml, .pre-commit-config.yaml, docs/branch_protection.md)
- Pre-commit smoke output (uvx pre-commit run --all-files)
- Status of branch protection (applied / pending user action)
- Note for Phase 2: when API keys are needed in CI, add them as GitHub Actions `secrets:` and reference via `${{ secrets.X }}` — never echo
</output>
