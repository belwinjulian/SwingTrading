---
phase: 01-repo-skeleton-ci-hygiene
plan: 04
type: execute
wave: 3
depends_on: ["01-02"]
files_modified:
  - Makefile
  - docs/strategy_v1_preregistration.md
autonomous: true
requirements: [FND-02]
must_haves:
  truths:
    - "Running `make data && make rank && make report && make backtest` from a clean checkout (after `make setup`) exits zero"
    - "`make help` prints at least the targets data, rank, report, backtest, setup, help"
    - "Every Makefile target shells out to a real `screener` typer subcommand from D-14, logging a structured [stub] line"
    - "docs/strategy_v1_preregistration.md exists and contains the literal token `<weights frozen at Phase 4 completion>`"
    - "The pre-registration doc lists the 6 v1 composite components (RS, Trend, Pattern, Volume, Earnings, Catalyst) with TBD values"
  artifacts:
    - path: "Makefile"
      provides: "Self-documenting target dispatch wired to typer subcommands"
      contains: ".PHONY"
    - path: "docs/strategy_v1_preregistration.md"
      provides: "Pre-registration placeholder for Phase 4 weight freeze (FND-05)"
      contains: "<weights frozen at Phase 4 completion>"
  key_links:
    - from: "Makefile"
      to: "src/screener/cli.py"
      via: "make data → screener refresh-universe && screener refresh-ohlcv && screener refresh-macro && screener refresh-fundamentals"
      pattern: "screener refresh-(universe|ohlcv|macro|fundamentals)"
    - from: "docs/strategy_v1_preregistration.md"
      to: "Phase 4 weight-freeze CI gate (deferred per CONTEXT.md)"
      via: "literal token serves as the placeholder Phase 4 will replace"
      pattern: "<weights frozen at Phase 4 completion>"
---

<objective>
Wire the user-facing Makefile DAG to the typer CLI from Plan 02 and ship the pre-registration document placeholder for Phase 4 weight freeze.

Purpose:
- FND-02 requires `make data && make rank && make report && make backtest` to run end-to-end with no manual steps. In Phase 1 the targets shell out to no-op typer stubs; in Phase 2+ those stubs become real implementations without changing the Makefile contract.
- Phase 1 success criterion 4 requires `docs/strategy_v1_preregistration.md` to exist with the literal token `<weights frozen at Phase 4 completion>`. The Phase 4 CI grep that fails on token removal is deferred (per CONTEXT.md "Deferred Ideas") — Phase 1 only ships the placeholder.

Output: A Makefile that resolves the DAG and a pre-registration doc that locks the freeze-at-Phase-4 contract.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md
@.planning/STATE.md
@CLAUDE.md
@src/screener/cli.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author Makefile with self-documenting `help` target wired to typer subcommands</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-14 — full subcommand surface; Claude's Discretion — Makefile help target self-documenting pattern; setup target runs uv sync + pre-commit install)
    - src/screener/cli.py (Plan 02 — confirms D-14 subcommand names exist)
    - CLAUDE.md §10.3 (Tooling — Makefile is convention)
  </read_first>
  <files>Makefile</files>
  <action>
Create `Makefile` at the repo root with the EXACT content below. Notes:
- Tabs (not spaces) for recipe lines — Make will fail loudly if you use spaces.
- Every target is `.PHONY` — Phase 1 has no real file dependencies; targets dispatch unconditionally.
- The `help` target uses the standard self-documenting pattern: parse `## description` comments after target names with `awk`.
- The four user-facing targets (`data`, `rank`, `report`, `backtest`) shell out to D-14 typer subcommands via `uv run screener <name>` so the Makefile works without an active venv.
- `setup` runs `uv sync --extra dev` and `uvx pre-commit install`.
- `make data` runs the four refresh subcommands sequentially (matches the `refresh-*` group in D-14).
- `make rank` is the user-facing alias for `screener score` (FND-02 specifies the four targets `data`, `rank`, `report`, `backtest`, and `score` is the canonical CLI verb).

```makefile
# Makefile — Momentum Swing Screener
#
# Every target is .PHONY; recipes shell out to the `screener` typer CLI.
# Phase 1: every command logs a structured [stub] line and exits 0.
# Later phases fill in the bodies without changing this contract (FND-02).

.PHONY: help setup data rank report backtest backtest-audit journal lint typecheck test all clean

help:  ## List available targets with descriptions
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup:  ## Install dependencies (uv sync --extra dev) and pre-commit hooks
	uv sync --extra dev
	uvx pre-commit install

data:  ## Refresh universe, OHLCV, macro, and fundamentals (Phase 1: stub no-ops)
	uv run screener refresh-universe
	uv run screener refresh-ohlcv
	uv run screener refresh-macro
	uv run screener refresh-fundamentals

rank:  ## Compute composite scores + playbook tags over the universe (Phase 1: stub)
	uv run screener score

report:  ## Render the daily Markdown report (Phase 1: stub)
	uv run screener report

backtest:  ## Run vectorbt walk-forward backtest (Phase 1: stub)
	uv run screener backtest

backtest-audit:  ## Run the forensic checklist (no-look-ahead, weight-pre-reg hash, universe date)
	uv run screener backtest-audit

journal:  ## Append actionable picks to data/journal.sqlite (Phase 1: stub)
	uv run screener journal

lint:  ## Run ruff format --check and ruff check
	uv run ruff format --check .
	uv run ruff check .

typecheck:  ## Run mypy --strict on the math modules (signals/, indicators/, regime, sizing)
	uv run mypy

test:  ## Run pytest (with coverage gate from pyproject.toml)
	uv run pytest

all: data rank report  ## Run the daily DAG (data -> rank -> report)

clean:  ## Remove caches and build artifacts (does NOT remove uv.lock or data/)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```
  </action>
  <verify>
    <automated>test -f Makefile &amp;&amp; make help | grep -E "^[[:space:]]+(data|rank|report|backtest|setup|help)" | wc -l | grep -qE '^[[:space:]]*[6-9]$|^[[:space:]]*1[0-9]$' &amp;&amp; make data &amp;&amp; make rank &amp;&amp; make report &amp;&amp; make backtest</automated>
  </verify>
  <acceptance_criteria>
    - `Makefile` exists at the repo root
    - `make help` prints at least targets `data`, `rank`, `report`, `backtest`, `setup`, `help` (verifiable via `make help | grep -E "(data|rank|report|backtest|setup|help)" | wc -l` ≥ 6)
    - `grep -F '.PHONY' Makefile` matches
    - `grep -E '^data:.*##' Makefile` matches (target has `##` doc comment)
    - `make data` exits 0 and emits 4 stub log lines (one per refresh-* subcommand)
    - `make rank` exits 0 and emits a stub log line for `score`
    - `make report` exits 0 and emits a stub log line for `report`
    - `make backtest` exits 0 and emits a stub log line for `backtest`
    - `make data && make rank && make report && make backtest` (sequential) exits 0 from a clean checkout (after `uv sync --extra dev`)
    - Recipe lines use TAB indentation (verifiable via `grep -P '^\t' Makefile | head -n 1` matches at least one TAB-indented line)
  </acceptance_criteria>
  <done>The Makefile DAG resolves end-to-end via the typer CLI; FND-02 is satisfied; future phases extend bodies without touching the Makefile contract.</done>
</task>

<task type="auto">
  <name>Task 2: Author docs/strategy_v1_preregistration.md placeholder</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (Claude's Discretion — pre-registration doc scaffold; literal token must appear verbatim; CI grep gate deferred to Phase 4)
    - .planning/STATE.md (Composite Score Weights table — RS 25, Trend 20, Pattern 20, Volume 10, Earnings 15, Catalyst 10)
    - .planning/REQUIREMENTS.md (FND-05 — full requirement that Phase 4 will satisfy)
  </read_first>
  <files>docs/strategy_v1_preregistration.md</files>
  <action>
Create `docs/strategy_v1_preregistration.md` with the EXACT content below. The literal token `<weights frozen at Phase 4 completion>` MUST appear verbatim — Phase 4 will replace it with the actual frozen weights and a git hash, and the CI grep that gates this token (per Phase 4's FND-05) will check for either the literal token (Phase 1 placeholder state) or a non-zero numeric weight + commit hash (Phase 4 frozen state).

The TBD weights table mirrors the values in STATE.md "Composite Score Weights (Pre-Registration Targets)" — these are the *targets* that Phase 4 will commit to.

```markdown
# Strategy v1 Pre-Registration

**Status:** Placeholder — weights frozen at Phase 4 completion

**Frozen at git hash:** <to be filled at Phase 4 completion>

This document pre-registers the v1 composite-score weights BEFORE any backtest result is reported. Pre-registration is a discipline against the canonical pitfall of in-sample weight optimization (PITFALLS.md #5) and multiple-testing blindness (#13). Once frozen, the weights below cannot be tuned against backtest data; v2 ML weight tuning waits for the paper-trade journal (Phase 7).

## Status Token

The literal string below is the placeholder Phase 4 will replace:

`<weights frozen at Phase 4 completion>`

A CI grep gate (deferred to Phase 4 per FND-05) will fail any change to this file that drops the token without simultaneously committing concrete numeric weights and a git hash.

## v1 Composite Weights (TBD — frozen at Phase 4)

The composite confidence score (0–100) is a weighted sum of six components. Targets below from `.planning/STATE.md`:

| Component                              | Target Weight | Frozen Weight |
|----------------------------------------|---------------|---------------|
| RS percentile (IBD-style)              | 25%           | TBD           |
| Trend Template (0–8 normalized)        | 20%           | TBD           |
| Pattern (VCP/flag tightness)           | 20%           | TBD           |
| Volume confirmation                    | 10%           | TBD           |
| Earnings momentum (CANSLIM C+A)        | 15%           | TBD           |
| Catalyst presence                      | 10%           | TBD           |

**Total:** 100% (target). Frozen weights must also sum to 100% within rounding tolerance.

## Methodology Summary

The v1 composite is rules-based and authoritative — the M2 ML probability score will add a single weight key (`ml_probability`) to this dict without refactoring the scorer. The composite combines:

- **RS percentile (25%)** — IBD-style quarter-weighted relative strength, percentile-ranked daily across the Russell 1000 universe (1–99 integer rating). Formula: `RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`, then percentile-rank.
- **Trend Template (20%)** — Minervini's 8 SMA-based conditions; emits both a boolean gate and a 0–8 partial-match score (the score, normalized to 0–100, feeds the composite). SMAs (NOT EMAs) per CLAUDE.md §13.6 pitfall #4.
- **Pattern (20%)** — VCP contraction tightness or continuation-flag fitness, computed from the indicator panel's pivot-detection output (Phase 6).
- **Volume confirmation (10%)** — 50-day up/down volume ratio plus pocket-pivot flag plus dryup detection.
- **Earnings momentum (15%)** — CANSLIM C (recent quarterly EPS YoY ≥ 25%) + A (3-yr annual EPS growth ≥ 25%) score, lagged 45 days post-quarter-end (PITFALLS.md #2).
- **Catalyst presence (10%)** — flags for `days_to_next_earnings`, `crossed_52w_high_within_60d`, `insider_cluster_buy` (Phase 6 catalyst pipeline).

## Freeze Procedure (Phase 4)

When Phase 4 completes:
1. Replace `TBD` in the table above with concrete numeric weights (one decimal place precision sufficient).
2. Replace the literal token `<weights frozen at Phase 4 completion>` with the date, e.g., `Frozen on 2026-MM-DD`.
3. Replace `<to be filled at Phase 4 completion>` with the actual `git rev-parse HEAD` of the freeze commit.
4. Commit the file as the FINAL action of Phase 4, so the freeze commit's hash is the one referenced (chicken-and-egg: commit, then amend the hash field in a follow-up commit, OR use a placeholder like `[freeze-commit]` and resolve in CI).

## References

- `.planning/REQUIREMENTS.md` FND-05 (Phase 4 ships the freeze; Phase 1 ships this placeholder)
- `.planning/STATE.md` "Composite Score Weights (Pre-Registration Targets)"
- `.planning/research/PITFALLS.md` #5 (in-sample weight overfit), #13 (multiple-testing blindness)
- `CLAUDE.md` §2.7 (Composite Scoring)
```
  </action>
  <verify>
    <automated>test -f docs/strategy_v1_preregistration.md &amp;&amp; grep -F '&lt;weights frozen at Phase 4 completion&gt;' docs/strategy_v1_preregistration.md &amp;&amp; grep -F '&lt;to be filled at Phase 4 completion&gt;' docs/strategy_v1_preregistration.md &amp;&amp; grep -E "RS percentile.*25%" docs/strategy_v1_preregistration.md &amp;&amp; grep -E "Trend Template.*20%" docs/strategy_v1_preregistration.md</automated>
  </verify>
  <acceptance_criteria>
    - `docs/strategy_v1_preregistration.md` exists
    - The literal string `<weights frozen at Phase 4 completion>` appears verbatim (verify with `grep -F '<weights frozen at Phase 4 completion>' docs/strategy_v1_preregistration.md`)
    - The literal string `<to be filled at Phase 4 completion>` appears verbatim
    - All 6 weight components appear with their target percentages: RS 25%, Trend 20%, Pattern 20%, Volume 10%, Earnings 15%, Catalyst 10%
    - File contains a "TBD" cell in the Frozen Weight column for each row (Phase 4 replaces these)
    - File references PITFALLS.md #5 and #13
  </acceptance_criteria>
  <done>Pre-registration placeholder in place; the literal token Phase 4's CI grep will check for is locked; the table structure is ready for Phase 4 to fill in concrete weights and a git hash.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user-shell ↔ Makefile | User invokes `make data && make rank && ...`; recipes spawn subprocesses |
| Makefile recipes ↔ uv run screener | Subprocess execution of typer CLI |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01 | Tampering | Makefile recipe drift | mitigate | Plan 03's `tests/test_cli_smoke.py` locks the D-14 subcommand surface; if a subcommand is renamed, the Makefile recipe break is detected by `make data && make rank && ...` integration smoke (a CI smoke job in Plan 05 may exercise this) |
| T-04-02 | Tampering | Pre-registration token removed | mitigate | Phase 4 will ship a CI grep gate (deferred per CONTEXT.md). Phase 1 ships the placeholder; the deferral is documented in this plan and in CONTEXT.md "Deferred Ideas" |
| T-04-03 | Information Disclosure | Make recipe echoes secrets | accept | Phase 1 stubs do not access `.env` values, so recipes echo only command names and stub log lines. Phase 2+ may need to revisit (e.g., do not `echo $FINNHUB_API_KEY` in any recipe) |
| T-04-04 | Denial of Service | Recipe runs forever | mitigate | Phase 1 stubs are 2-line no-ops; each `uv run screener <cmd>` returns within seconds. Plan 05 CI sets a job timeout |

</threat_model>

<verification>
After both tasks complete:
1. `make help` lists at least `data`, `rank`, `report`, `backtest`, `setup`, `help` targets
2. `make data && make rank && make report && make backtest` exits 0 (FND-02 success criterion)
3. `make setup` runs `uv sync --extra dev` and `uvx pre-commit install`
4. `grep -F '<weights frozen at Phase 4 completion>' docs/strategy_v1_preregistration.md` matches
5. `grep -F 'pyproject.toml' docs/strategy_v1_preregistration.md` does NOT need to match (irrelevant); but the 6 component rows DO need to match the STATE.md target weights
</verification>

<success_criteria>
- Makefile DAG resolves end-to-end via the typer CLI from Plan 02 (FND-02 met)
- Every Makefile target shells out to a real D-14 subcommand
- The pre-registration doc placeholder ships with the literal token `<weights frozen at Phase 4 completion>` (Phase 1 success criterion 4)
- The 6 v1 composite components appear with their STATE.md target weights
- The CI grep gate for the token is deferred to Phase 4 (per CONTEXT.md "Deferred Ideas")
</success_criteria>

<output>
After completion, create `.planning/phases/01-repo-skeleton-ci-hygiene/01-04-SUMMARY.md` with:
- Files created (Makefile, docs/strategy_v1_preregistration.md)
- Output of `make help` (target list)
- Confirmation that `make data && make rank && make report && make backtest` exits 0
- Confirmation that the literal token is present
</output>
