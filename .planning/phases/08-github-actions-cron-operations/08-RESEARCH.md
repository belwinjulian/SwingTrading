# Phase 8: GitHub Actions Cron & Operations — Research

**Researched:** 2026-05-19
**Domain:** CI/CD automation — GitHub Actions scheduled workflows, caching, auto-commit, run-log observability
**Confidence:** HIGH

## Summary

Phase 8 productionalizes the local pipeline as a nightly GitHub Actions cron with three deliverables: (1) `refresh.yml` scheduled `30 22 * * 1-5` UTC, (2) `heartbeat.yml` weekly to defeat the 60-day idle disable, and (3) `data/runs.jsonl` append-only observability log. The work is heavily constrained by 11 locked decisions in CONTEXT.md (D-01..D-11). The hardest parts are NOT library research — they are mechanical YAML patterns: cache key + `restore-keys` syntax, the `if: success()` / `if: failure() || ...` step-conditional dance for the success-vs-failure commit paths, and `$GITHUB_STEP_SUMMARY` surface for OPS-05 SC#5.

The existing repo already establishes the action-pinning convention: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2` and `astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0`. Phase 8 should reuse those exact hashes for visual consistency (the verifier scans for `# vX.Y.Z` comment markers). Two new actions are needed: `actions/cache@v4` and `stefanzweifel/git-auto-commit-action@v5.2.0`.

**Primary recommendation:** Reuse the existing ci.yml step ordering (checkout -> setup-uv with `enable-cache: true` -> `uv python install` -> `uv sync --frozen --extra dev`). Insert `actions/cache` for `data/ohlcv|fundamentals|insider` between setup-uv and the pipeline run. Run the pipeline through a single Makefile-style chain (`make data && make rank && make report && uv run screener journal`) wrapped in `bash -e` so a non-zero exit aborts the chain. Use TWO separate auto-commit steps with mirrored-conditional guards: `if: success()` for full artifacts, `if: failure()` for the runs.jsonl-only failure record. Write the run log from inside `run_pipeline()` via a new `publishers/run_log.py` module (NOT a CLI subcommand — D-06 / D-24 lock).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Use `actions/cache` to persist OHLCV prices.parquet files between nightly runs.**
- `data/ohlcv/**/prices.parquet` is gitignored and must survive across workflow runs. 10GB free, 7-day expiry covers weekends.

**D-02: Cache key strategy — daily key with weekly fallback.**
- Primary key: daily; `restore-keys:` includes a weekly prefix so the most-recent week's cache is restored when today's miss.
- Planner decides exact key format; week number via `date +%Y-W%V` is the recommended basis.

**D-03: Cache scope — ohlcv + fundamentals + insider; NOT macro.**
- Include: `data/ohlcv/`, `data/fundamentals/`, `data/insider/`
- Exclude: `data/macro/` (only 5 tickers; re-fetched fresh every night so regime always sees the latest bar).

**D-04: Relocate `runs.jsonl` from repo root to `data/runs.jsonl`.**
- `.gitignore` currently has `/runs.jsonl` (root-level). Phase 8 removes that line and adds `!/data/runs.jsonl` inside the `/data/*` block.

**D-05: On health-check failure — commit `data/runs.jsonl` only.**
- Pipeline exits non-zero -> primary auto-commit (report/snapshot/journal) is skipped via `if: success()`.
- Separate step with `if: failure()` writes the failure record AND commits ONLY `data/runs.jsonl`.
- Failure record: `status: "failed"`, `start_time`, `duration_seconds`, `fetch_success_rate`, `error_reason`, `picks_count: null`, `regime_state: null`, `n_429_responses`.

**D-06: `runs.jsonl` is appended by Python, not bash YAML.**
- Module-internal call from `run_pipeline` or a `scripts/` helper. NO 10th typer subcommand (D-24 / Phase 6 CLI lock).

**D-07: Refresh workflow `timeout-minutes: 120`.**
- Warm cache: ~15-30 min. Cold cache: up to 90 min worst case.

**D-08: CI workflow timeout unchanged at 10 minutes per job.**

**D-09: Refresh job permissions `contents: write`; CI/heartbeat stay `contents: read` (heartbeat needs write too — see Open Question A).**

**D-10: Secrets required — `FINNHUB_API_KEY`, `EDGAR_IDENTITY` (FRED_API_KEY also needed per .env.example line 13).**

**D-11: Heartbeat — `0 9 * * 1` UTC weekly, commits `data/heartbeat.txt` with ISO timestamp.**
- `.gitignore` carve-out: `!/data/heartbeat.txt`.

### Claude's Discretion

- Exact `actions/cache` key format (recommendation in §Implementation Approach).
- How `data/runs.jsonl` is written: module-internal vs `scripts/` helper (recommendation: new `src/screener/publishers/run_log.py` — see §Integration Points).
- Heartbeat commit author: default `github-actions[bot]` is fine.

### Deferred Ideas (OUT OF SCOPE)

- Slack/Discord notification on nightly failure (v1.x scope creep).
- Per-ticker fetch timing stats in runs.jsonl (v1.x richer observability).
- Retry failed tickers in a second pass (v1 fails fast at 95% threshold).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | Workflow runs nightly at `30 22 * * 1-5` UTC, full pipeline | §Implementation Approach refresh.yml; cron syntax + `make data && make rank && make report && screener journal` step chain |
| OPS-02 | Commits report, journal updates, run log via stefanzweifel/git-auto-commit-action@v5 | §Pinned Action Hashes (v5.2.0 SHA); §Implementation Approach two-step commit pattern |
| OPS-03 | Weekly heartbeat prevents 60-day cron disable | §Pitfalls "60-day idle disable confirmed"; §Implementation Approach heartbeat.yml |
| OPS-04 | `workflow_dispatch` for manual re-runs | §Implementation Approach refresh.yml `on:` block |
| OPS-05 | Run log appends structured JSON to runs.jsonl | §Integration Points (run_log.py); §Standard Stack (Python stdlib json); §Pitfalls (flush + fsync); §Implementation Approach `$GITHUB_STEP_SUMMARY` for SC#5 |

## Project Constraints (from CLAUDE.md)

| Directive | How Phase 8 Honors It |
|-----------|-----------------------|
| No `print()` — use structlog | run_log.py uses both: structlog for the workflow log line AND `json.dump` for the on-disk record. Different sinks, both structured. |
| Python 3.11 | Workflow uses `uv python install` (reads pyproject `requires-python = "==3.11.*"`) |
| `uv add` over `pip install`, lockfile in git | Workflow uses `uv sync --frozen --extra dev` (identical to ci.yml) |
| Pure functions in signals/ and indicators/ | run_log.py is a publisher (in publishers/), NOT signals/ — D-23 architecture lock honored |
| No global mutable state | run_log.py functions are pure; the file is the side-effect target, not module state |
| `mypy --strict` on signals/ + indicators/ | run_log.py is in publishers/ (not strict-locked) but should be cleanly typed anyway |
| Every IO boundary validates with pandera | JSONL records are not DataFrames — pandera N/A. Use a `TypedDict` + a small runtime field-presence assertion for the record shape. |
| Signals execute at next-bar open | Not touched by Phase 8 (no signal logic changes) |
| FND-04 no-look-ahead gate | Phase 8 changes NOTHING in signals/ or backtest/; FND-04 gate is N/A but `<verify>` should still grep that no edits landed there |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Nightly scheduled execution | CI/CD (GitHub Actions) | — | Owned by the runner platform |
| Pipeline orchestration | CLI (typer) -> Makefile | publishers/pipeline.py | Existing pattern: workflow calls `make`, make calls the 9 locked typer subcommands |
| Data persistence between runs | actions/cache | git-committed artifacts | Large OHLCV blobs cached, small audit artifacts (snapshots, reports, splits) committed |
| Run log JSONL write | publishers/run_log.py | — | New module; placed in publishers/ alongside snapshot.py + report.py (D-23 allowed-import set) |
| Failure surfacing | GitHub Step Summary | structlog stderr | `$GITHUB_STEP_SUMMARY` markdown for OPS-05 SC#5; structlog JSON for log-grep |
| Secret injection | Workflow `env:` block | pydantic-settings | Settings class reads env vars as fallback when `.env` absent |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| GitHub Actions | n/a (platform) | Cron + CI/CD runner | Free public-repo minutes; native git integration |
| actions/checkout | v4.2.2 (existing in ci.yml) | Repo checkout in workflow | Pinned by SHA in current ci.yml; reuse identical pin |
| actions/cache | v4.3.0 | Persist `data/ohlcv|fundamentals|insider` between runs | 10GB free per repo, 7-day idle expiry |
| astral-sh/setup-uv | v6.8.0 (existing in ci.yml) | Install uv + cache uv's cache dir | Pinned by SHA in current ci.yml; reuse identical pin |
| stefanzweifel/git-auto-commit-action | v5.2.0 | Auto-commit + push back to main | Handles dirty-check, default `github-actions[bot]` author, no-op when working tree clean |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Python `json` (stdlib) | 3.11 | JSONL record serialization | Single-record `json.dumps(record) + '\n'` is sufficient; no external lib needed |
| structlog | 25.5.x (already in pyproject) | Log the workflow event in addition to writing the JSONL | Already configured in src/screener/obs.py:configure() |
| actionlint (optional) | latest stable | Static-check the new .yml files locally before commit | Catches schema typos and shellcheck issues. Recommendation: optional dev-only; do NOT add a workflow that runs it on PR (Phase 8 scope creep). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `stefanzweifel/git-auto-commit-action` | Raw `git config && git add && git commit && git push` | Hand-rolled saves one external dep but loses dirty-check + no-op-on-clean semantics; reinvents 30 lines of bash. Action is 50k+ usages — stable. |
| `actions/cache` for OHLCV | Git-committing OHLCV parquet | OHLCV refresh adds ~50 MB/day; would balloon repo size. D-01 chose cache for the right reasons. |
| Python helper for run log | `bash` heredoc emitting JSON | D-06 explicit: Python so the schema is typed. Bash JSON is fragile (quote escaping, time format drift). |
| New 10th typer subcommand `run-log` | Module-internal call | D-24 CLI surface lock (Phase 6); MUST use module-internal call. |
| `cancel-in-progress: true` | `cancel-in-progress: false` for refresh.yml | See §Pitfalls — refresh runs are expensive (up to 90 min cold); a manual `workflow_dispatch` while the nightly is still running should NOT cancel the nightly. Use `false`. |

**Verified action versions:**
- `actions/checkout` — v4.3.1 latest (Nov 2024); v4.2.2 already pinned in ci.yml — REUSE existing pin for consistency
- `actions/cache` — v4.3.0 latest (Sep 2024); SHA `0057852244b06bcd05d3c3a0a73e056f3a1e3f9c` (Note: short SHA seen in release page; verify with `git ls-remote https://github.com/actions/cache.git refs/tags/v4.3.0` before pinning)
- `astral-sh/setup-uv` — v6.8.0 already pinned in ci.yml — REUSE existing pin
- `stefanzweifel/git-auto-commit-action` — v5.2.0 latest in v5 line (Apr 2024); SHA `b863ae1933cb653a53c021fe36dbb774e1fb9403`

`[VERIFIED: github.com/actions/cache/releases, github.com/stefanzweifel/git-auto-commit-action/releases]`

## Pinned Action Hashes

The existing workflows pin every third-party action by full 40-char commit SHA with a trailing `# vX.Y.Z` comment marker. Phase 8 MUST follow the same convention.

| Action | Pin (40-char SHA + version comment) | Source |
|--------|-------------------------------------|--------|
| `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2` | REUSE existing pin from ci.yml line 22 | Verified: matches ci.yml |
| `astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0` | REUSE existing pin from ci.yml line 25 | Verified: matches ci.yml |
| `actions/cache@<resolve before commit>  # v4.3.0` | NEW. Planner MUST resolve the v4.3.0 full SHA via `git ls-remote https://github.com/actions/cache.git refs/tags/v4.3.0` immediately before writing the workflow. | `[VERIFIED: GitHub releases page shows v4.3.0 Sept 24 2024]` |
| `stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0` | NEW. Full SHA verified against release page. | `[VERIFIED: github.com/stefanzweifel/git-auto-commit-action/releases/tag/v5.2.0]` |

**Pinning verification command** (run once during plan execution, before workflow YAML is committed):
```bash
git ls-remote https://github.com/actions/cache.git refs/tags/v4.3.0
git ls-remote https://github.com/stefanzweifel/git-auto-commit-action.git refs/tags/v5.2.0
```
The SHAs printed by `ls-remote` are the canonical pin values. Hardcoded SHAs above are best-effort from documentation; the planner's task verification step should re-confirm them.

`[VERIFIED: actions pinning convention via ci.yml line 22, 25; no-lookahead-gate.yml line 33, 36]`

## Implementation Approach

### refresh.yml — Complete YAML Skeleton

```yaml
name: refresh

# OPS-01: nightly at 22:30 UTC weekdays (Mon-Fri).
# OPS-04: workflow_dispatch for manual re-runs.
on:
  schedule:
    - cron: "30 22 * * 1-5"
  workflow_dispatch:

# D-09: write permission scoped to this workflow only.
permissions:
  contents: write

# Don't cancel an in-progress nightly when a manual dispatch fires (long jobs).
# See §Pitfalls "concurrency cancel-in-progress: false for long cron".
concurrency:
  group: refresh-${{ github.ref }}
  cancel-in-progress: false

jobs:
  refresh:
    name: refresh
    runs-on: ubuntu-latest
    timeout-minutes: 120  # D-07
    env:
      # D-10: secrets injected as env vars; pydantic-settings reads them when .env is absent
      FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
      EDGAR_IDENTITY: ${{ secrets.EDGAR_IDENTITY }}
      FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev

      # D-02: compute cache keys (daily primary, weekly fallback via restore-keys).
      - name: Compute cache keys
        id: cache_keys
        run: |
          echo "daily=ohlcv-data-${{ runner.os }}-$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
          echo "weekly=ohlcv-data-${{ runner.os }}-$(date -u +%Y-W%V)" >> "$GITHUB_OUTPUT"

      # D-01 / D-03: cache OHLCV + fundamentals + insider (NOT macro).
      - name: Restore data caches
        id: cache_restore
        uses: actions/cache@<v4.3.0-sha>  # planner resolves at commit time
        with:
          path: |
            data/ohlcv
            data/fundamentals
            data/insider
          key: ${{ steps.cache_keys.outputs.daily }}
          restore-keys: |
            ${{ steps.cache_keys.outputs.weekly }}
            ohlcv-data-${{ runner.os }}-

      # OPS-01: the nightly DAG. `set -e` so any non-zero exit aborts the chain
      # and triggers the failure-commit path. `screener journal` is the 9th
      # locked subcommand from Phase 7.
      - name: Run nightly pipeline
        id: pipeline
        run: |
          set -e
          uv run screener refresh-universe
          uv run screener refresh-ohlcv
          uv run screener refresh-macro
          uv run screener refresh-fundamentals
          uv run screener score
          uv run screener report
          uv run screener journal

      # Success path: write success record then commit all artifacts.
      # `if: success()` is implicit on every step that lacks an `if:`, BUT
      # the run_log.py call here is the *success-record writer*; we want to
      # be explicit so the symmetry with the failure step below is obvious
      # to the reviewer.
      - name: Write success run-log record
        if: success()
        run: uv run python -m screener.publishers.run_log success

      # OPS-02: auto-commit the day's artifacts (success path).
      # file_pattern enumerates exactly what's allowed past .gitignore.
      - name: Auto-commit success artifacts
        if: success()
        uses: stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0
        with:
          commit_message: "chore(nightly): refresh ${{ github.run_number }}"
          file_pattern: |
            data/runs.jsonl
            data/snapshots/
            data/universe/
            data/journal.sqlite
            data/ohlcv/**/splits.parquet
            reports/

      # Failure path: write failure record, commit ONLY data/runs.jsonl,
      # surface the failure in the GitHub Actions summary tab (OPS-05 SC#5).
      - name: Write failure run-log record
        if: failure()
        run: |
          uv run python -m screener.publishers.run_log failure
          echo "## Nightly refresh FAILED" >> "$GITHUB_STEP_SUMMARY"
          echo "" >> "$GITHUB_STEP_SUMMARY"
          echo "See the pipeline step logs above for the error reason. The failure record is committed to \`data/runs.jsonl\`." >> "$GITHUB_STEP_SUMMARY"

      - name: Auto-commit failure run-log
        if: failure()
        uses: stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0
        with:
          commit_message: "chore(nightly): refresh ${{ github.run_number }} FAILED"
          file_pattern: data/runs.jsonl
```

### heartbeat.yml — Complete YAML Skeleton

```yaml
name: heartbeat

# OPS-03 / D-11: weekly Monday 09:00 UTC, before any market action.
on:
  schedule:
    - cron: "0 9 * * 1"
  workflow_dispatch:

# Needs write to commit data/heartbeat.txt.
permissions:
  contents: write

concurrency:
  group: heartbeat-${{ github.ref }}
  cancel-in-progress: true

jobs:
  heartbeat:
    name: heartbeat
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Write heartbeat timestamp
        run: |
          mkdir -p data
          date -u +%Y-%m-%dT%H:%M:%SZ > data/heartbeat.txt

      - name: Auto-commit heartbeat
        uses: stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0
        with:
          commit_message: "chore: weekly heartbeat"
          file_pattern: data/heartbeat.txt
```

Note D-09 says heartbeat is `contents: read`, but the heartbeat MUST commit a file. That's a contradiction in CONTEXT.md — see Open Question A. Plan should use `contents: write` for heartbeat (necessary correction).

### .gitignore Diff (D-04 + D-11)

```diff
 /data/snapshots/*.parquet
 !/data/snapshots/.gitkeep
 /reports/
-/runs.jsonl
+!/data/runs.jsonl
+!/data/heartbeat.txt
```

Two additions inside the `/data/*` carve-out block. `/runs.jsonl` line (line 48) is removed because the file relocates to `data/runs.jsonl`.

`reports/` line stays as-is — it's anchored at repo root, so `/reports/` ignores the root-level reports dir BUT the auto-commit step's `file_pattern: reports/` will still pick up the dir at root because GA `git add reports/` traverses through `.gitignore` only when files are NEW (and `git-auto-commit-action` runs `git add` with default options which honor `.gitignore`). The pipeline writes to `reports/YYYY-MM-DD.md` — that file IS gitignored, so the commit step won't pick it up.

**Critical gitignore fix:** The current `/reports/` line at .gitignore:47 SILENTLY breaks OPS-02. Phase 8 MUST add `!/reports/` and `!/reports/*.md` carve-outs (mirror the data/universe/ idiom), OR pass `add_options: "-f"` to the auto-commit action. Recommendation: carve-out, NOT `-f` — keeps the gitignore explicit about what's committed.

```diff
-/reports/
+!/reports/
+!/reports/*.md
```

### Run-log Python Module (D-06 — module-internal call)

New file `src/screener/publishers/run_log.py`:

```python
"""publishers.run_log — JSONL observability log for the nightly pipeline.

Writes one record per pipeline invocation to data/runs.jsonl. Called from
TWO sites in run_pipeline-aware code:
  1. publishers.pipeline.run_pipeline (success path — end of run)
  2. python -m screener.publishers.run_log <status> (failure path — invoked
     from the workflow YAML when an earlier step failed)

D-06: NOT a typer subcommand. Module-internal call OR `python -m`. The
9-subcommand surface is locked by tests/test_cli_smoke.py (D-24).

OPS-05 schema (success):
    status, start_time, duration_seconds, fetch_success_rate, regime_state,
    picks_count, n_429_responses, error_reason (null)

OPS-05 schema (failure):
    status, start_time, duration_seconds, fetch_success_rate, regime_state,
    picks_count (null), n_429_responses, error_reason (str)

Crash-safety: open(path, 'a') + json.dumps + flush + fsync. JSONL records
are newline-terminated so a partial-write tail leaves the file recoverable
(jq --slurp tolerates trailing blank lines but a truncated JSON tail is
fatal; fsync ensures the newline lands).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import structlog

log = structlog.get_logger(__name__)


class RunLogRecord(TypedDict, total=False):
    status: str  # "success" | "failed"
    start_time: str  # ISO 8601 UTC
    duration_seconds: float
    fetch_success_rate: float
    regime_state: str | None
    picks_count: int | None
    n_429_responses: int
    error_reason: str | None


_RUNS_PATH = Path("data/runs.jsonl")


def append_record(record: RunLogRecord) -> None:
    """Append one record to data/runs.jsonl with flush + fsync (crash-safe).

    The caller (run_pipeline) constructs the dict with all required fields.
    This function ONLY writes; it does not collect metrics.
    """
    _RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    with open(_RUNS_PATH, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())  # force OS write — critical for the failure path
    log.info("run_log_appended", status=record.get("status"), path=str(_RUNS_PATH))


def _cli_failure_entry(status: str) -> None:
    """`python -m screener.publishers.run_log failure` entrypoint.

    Reads minimal metrics from environment (set by the workflow):
      RUN_START_TIME — ISO timestamp from the workflow step
      RUN_ERROR_REASON — optional; defaults to "pipeline step failed"

    The success path is NOT invoked via this CLI — run_pipeline writes its
    own record directly via append_record(...).
    """
    start_time = os.environ.get("RUN_START_TIME", datetime.now(UTC).isoformat())
    # Calculate duration approximately; the workflow tracks the real one.
    record: RunLogRecord = {
        "status": status,
        "start_time": start_time,
        "duration_seconds": 0.0,  # unknown at this point — workflow can override
        "fetch_success_rate": 0.0,
        "regime_state": None,
        "picks_count": None,
        "n_429_responses": 0,
        "error_reason": os.environ.get("RUN_ERROR_REASON", "pipeline step failed"),
    }
    append_record(record)


if __name__ == "__main__":
    # Entry: python -m screener.publishers.run_log {success|failure}
    if len(sys.argv) != 2 or sys.argv[1] not in ("success", "failure"):
        print("usage: python -m screener.publishers.run_log {success|failure}", file=sys.stderr)
        raise SystemExit(2)
    _cli_failure_entry("failed" if sys.argv[1] == "failure" else "success")
```

**Why a `__main__` entrypoint and not a CLI subcommand:** D-06 explicit + D-24 lock. `python -m screener.publishers.run_log failure` is invoked from the workflow YAML in the failure path; it does NOT register a typer command. test_cli_smoke.py D14_SUBCOMMANDS stays bytewise unchanged.

## Integration Points

### `src/screener/publishers/pipeline.py` — `run_pipeline()` modifications

Insert a `time.perf_counter()` capture at the top and an `append_record(...)` call at the bottom (after the existing `log.info("pipeline_complete", ...)` line at pipeline.py:541-550).

```python
# At the top of run_pipeline (line ~326, after settings = get_settings()):
from screener.publishers.run_log import append_record
import time as _time
_t_start = _time.perf_counter()
_start_iso = datetime.now(UTC).isoformat(timespec="seconds")
_n_429 = 0  # workflow may inject this from a counter; v1 = 0 placeholder

# At the very end of run_pipeline (after the existing log.info(pipeline_complete...)):
append_record({
    "status": "success",
    "start_time": _start_iso,
    "duration_seconds": round(_time.perf_counter() - _t_start, 2),
    "fetch_success_rate": float(len(today_panel) / max(1, len(panel.index.get_level_values("ticker").unique()))),
    "regime_state": regime_state_value,
    "picks_count": int((today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD).sum()),
    "n_429_responses": _n_429,
    "error_reason": None,
})
```

**Why end-of-run (not start-of-run with mutation):** A single append at the end is atomic on disk. Writing twice (start + final-update) requires reading the JSONL back, finding the matching record, rewriting — fragile and not worth it for v1.

**Why the success path doesn't go through `python -m` like failure:** When `run_pipeline` itself succeeds, it owns the metrics (`regime_state_value`, `today_panel`, etc.). The failure path is invoked from BASH after `run_pipeline` already raised — so the metrics are lost and we can only record a minimal failure stub.

### `src/screener/persistence.py` — no changes needed for OPS-05

JSONL is not a DataFrame; no pandera schema fits. `run_log.py` lives in `publishers/`, not `persistence/`, because:
1. The architecture test ALLOWED dict (D-23) keeps persistence.py at "stdlib + pandas + pandera + sqlite3 + config" — adding `os.fsync` and a TypedDict record schema bloats it.
2. Publishers already own the "write side-effects with structlog" pattern (snapshot.py, report.py, pattern audit). run_log.py fits the same shape.

### `data/.gitkeep` — exists already

Verified by reading the gitignore — `!/data/universe/.gitkeep` carve-out is the established pattern. `data/runs.jsonl` and `data/heartbeat.txt` do NOT need a .gitkeep (they're files, not dirs, and the files themselves are committed once created).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auto-commit + push from a workflow step | Raw `git config user.name && git add && git commit && git push` shell block | `stefanzweifel/git-auto-commit-action@v5.2.0` | Handles dirty-check (no empty commits), default `github-actions[bot]` identity, no-op-on-clean. 30+ lines saved per workflow. |
| Defeat 60-day idle disable | A cron that runs `git commit --allow-empty` | A real heartbeat that commits a timestamp to a tracked file | Empty commits violate the "real activity" rule per [community discussion 57858](https://github.com/orgs/community/discussions/57858). Only commits to the default branch count. |
| JSONL write with concurrency safety | `fcntl.flock(...)` or a SQLite-backed log | `open('a')` + flush + fsync | Phase 8 has ONE writer (the nightly job). No concurrent writes. Flock is unnecessary overhead. |
| Track workflow-step success/failure for the second commit step | A bash variable file + read-back | `if: success()` / `if: failure()` step conditionals | GitHub Actions built-in. The two conditionals are exclusive: a step with `if: success()` runs ONLY when every prior step passed; `if: failure()` runs ONLY when at least one prior step failed. |
| Surface failure in the Actions summary | Custom annotation extraction from logs | `echo "..." >> $GITHUB_STEP_SUMMARY` | Native markdown summary tab, max 1 MiB per step, multiple appends auto-newlined. |

**Key insight:** Phase 8's tight constraints (D-01..D-11) mean almost every decision is already made. The risk is NOT "did we pick the right library" — it's "did we get the YAML conditional dance exactly right." Hand-rolling shell scripts where actions exist is the dominant failure mode here.

## Architecture Patterns

### System Architecture Diagram

```
                       ┌──────────────────────────┐
                       │  GitHub Actions Cron     │
                       │  schedule: 30 22 * * 1-5 │
                       │  + workflow_dispatch     │
                       └──────────┬───────────────┘
                                  │
                                  v
              ┌───────────────────────────────────────────┐
              │  refresh.yml: jobs.refresh                │
              │  permissions: contents: write             │
              │  timeout-minutes: 120                     │
              │  concurrency: cancel-in-progress: false   │
              └─────┬─────────────────────────────────────┘
                    │
                    v
   ┌────────────────────────────────────────────────────┐
   │  Step 1: checkout (full repo, default depth)       │
   │  Step 2: setup-uv (enable-cache: true on uv.lock)  │
   │  Step 3: uv python install                         │
   │  Step 4: uv sync --frozen --extra dev              │
   │  Step 5: compute cache keys (daily + weekly)       │
   │  Step 6: actions/cache restore                     │
   │          paths: data/ohlcv/                        │
   │                 data/fundamentals/                 │
   │                 data/insider/                      │
   │          key: ohlcv-data-{os}-{YYYY-MM-DD}         │
   │          restore-keys: ohlcv-data-{os}-{YYYY-Wxx}  │
   └────────────────────┬───────────────────────────────┘
                        │
                        v
   ┌────────────────────────────────────────────────────┐
   │  Step 7: nightly pipeline (bash -e chain)          │
   │    screener refresh-universe                       │
   │    screener refresh-ohlcv (writes data/ohlcv/)     │
   │    screener refresh-macro (writes data/macro/)     │
   │    screener refresh-fundamentals                   │
   │    screener score                                  │
   │    screener report (run_pipeline appends           │
   │      success record to data/runs.jsonl)            │
   │    screener journal                                │
   └────────┬──────────────────────────────┬────────────┘
            │                              │
       success path                  failure path
            │                              │
            v                              v
  ┌────────────────────┐        ┌──────────────────────────┐
  │ if: success()      │        │ if: failure()            │
  │   (no extra        │        │   python -m              │
  │   run-log write —  │        │     screener.publishers  │
  │   pipeline already │        │     .run_log failure     │
  │   wrote it)        │        │   echo "..." >> SUMMARY  │
  └─────────┬──────────┘        └────────────┬─────────────┘
            │                                │
            v                                v
  ┌──────────────────────┐        ┌──────────────────────┐
  │ git-auto-commit v5   │        │ git-auto-commit v5   │
  │ file_pattern:        │        │ file_pattern:        │
  │   data/runs.jsonl    │        │   data/runs.jsonl    │
  │   data/snapshots/    │        │  (FAILURE record only)│
  │   data/universe/     │        └──────────────────────┘
  │   data/journal.sqlite│
  │   data/ohlcv/**/     │
  │     splits.parquet   │
  │   reports/           │
  └──────────────────────┘

                       ┌──────────────────────────┐
                       │  heartbeat.yml           │
                       │  cron: 0 9 * * 1         │
                       └──────────┬───────────────┘
                                  v
                       ┌──────────────────────────┐
                       │  date > data/heartbeat   │
                       │  git-auto-commit v5      │
                       │  (defeats 60-day disable)│
                       └──────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Refresh workflow | `.github/workflows/refresh.yml` | Cron trigger; orchestrate cache + pipeline + dual-commit |
| Heartbeat workflow | `.github/workflows/heartbeat.yml` | Weekly write to `data/heartbeat.txt` + commit |
| Run-log writer | `src/screener/publishers/run_log.py` | JSONL append (success path module-internal; failure path `python -m`) |
| Pipeline integration | `src/screener/publishers/pipeline.py` | Add `append_record(...)` at end of `run_pipeline()` |
| Gitignore carve-outs | `.gitignore` | Allow `data/runs.jsonl`, `data/heartbeat.txt`, `reports/*.md` past `/data/*` and `/reports/` blocks |

### Pattern 1: Two-step Commit with Mutually Exclusive Conditionals

**What:** Two `stefanzweifel/git-auto-commit-action@v5` steps, guarded by `if: success()` and `if: failure()`. The conditionals are mutually exclusive — exactly one runs in any given workflow execution.

**When to use:** Whenever the artifact set differs between success and failure paths.

**Why the conditionals don't conflict:** GitHub Actions evaluates `if:` against the cumulative job state.
- `if: success()` — true iff every prior step succeeded.
- `if: failure()` — true iff at least one prior step failed.
- The default `if:` (when omitted) is implicitly `success()`.

The dichotomy is GUARANTEED — one and only one fires.

**Example:**
```yaml
- name: Pipeline (may fail)
  run: uv run screener refresh-ohlcv && uv run screener report

- name: Commit success artifacts
  if: success()
  uses: stefanzweifel/git-auto-commit-action@<v5.2.0-sha>
  with:
    file_pattern: data/snapshots/ reports/ data/runs.jsonl

- name: Write failure record + commit only runs.jsonl
  if: failure()
  run: |
    uv run python -m screener.publishers.run_log failure
    echo "## FAILED" >> "$GITHUB_STEP_SUMMARY"
- name: Commit failure artifact
  if: failure()
  uses: stefanzweifel/git-auto-commit-action@<v5.2.0-sha>
  with:
    file_pattern: data/runs.jsonl
```

**Source:** `[CITED: docs.github.com/en/actions/learn-github-actions/expressions#status-check-functions]`

### Pattern 2: Cache Key with restore-keys Fallback Chain

**What:** Primary cache key includes today's date; `restore-keys:` lists multiple prefixes from most-specific to least-specific. On a miss for the primary key, GitHub walks the restore-keys list and uses the first prefix match (most recent timestamp wins among matching keys).

**Example:**
```yaml
- name: Cache OHLCV
  uses: actions/cache@<v4.3.0-sha>
  with:
    path: |
      data/ohlcv
      data/fundamentals
      data/insider
    key: ohlcv-data-${{ runner.os }}-2026-05-19  # today (miss on first run of the day)
    restore-keys: |
      ohlcv-data-${{ runner.os }}-2026-W20       # this week (matches Mon-Fri of W20)
      ohlcv-data-${{ runner.os }}-               # any cache for this OS (last-resort)
```

**Bash compatibility for `date +%Y-W%V`:** Ubuntu's `coreutils` `date` supports both `%Y-%m-%d` and `%Y-W%V` (ISO 8601 week). `runner.os` evaluates to `Linux` on `ubuntu-latest`. No bashism issues. `[VERIFIED: date(1) Ubuntu 22.04 manpage; W%V is ISO 8601 week 01-53]`

### Anti-Patterns to Avoid

- **`add_options: "-f"` to bypass gitignore:** Don't. If a file should be committed, put a carve-out in `.gitignore`. The `-f` flag works but hides what's actually committed — a reviewer reading the YAML can't tell which gitignore rules are being violated.
- **Empty commits as heartbeat (`git commit --allow-empty`):** Per [community discussion 57858](https://github.com/orgs/community/discussions/57858), empty commits and tags do NOT count as repository activity for the 60-day rule. Only normal commits to the default branch count. Heartbeat MUST commit a real file change.
- **`cancel-in-progress: true` on a 120-minute job:** A manual `workflow_dispatch` while the nightly is running would kill 90 minutes of OHLCV fetches. Use `false`.
- **Writing runs.jsonl from bash YAML:** D-06 explicit prohibition. Python ensures the schema stays typed.
- **Adding a 10th typer subcommand:** D-24 / Phase 6 lock. Use `python -m screener.publishers.run_log` instead.

## Runtime State Inventory

Phase 8 is a productionalization phase (workflows + observability), not a refactor. There IS one runtime state migration:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `runs.jsonl` at repo root (per current `.gitignore` line 48) | The file does NOT exist yet (never written by current code). NO data migration needed — Phase 8 just creates `data/runs.jsonl` fresh. |
| Live service config | NONE — no external service is configured with the old `runs.jsonl` path | None — verified by grep. |
| OS-registered state | NONE — no Task Scheduler / launchd / pm2 registrations reference runs.jsonl | None — verified by grep. |
| Secrets / env vars | `FINNHUB_API_KEY`, `EDGAR_IDENTITY`, `FRED_API_KEY` already in `.env.example` | USER ACTION: add these as GitHub Secrets in repository settings (Settings -> Secrets and variables -> Actions). NOT a code change. Document in PLAN as a checkpoint:human-verify task. |
| Build artifacts | NONE — no compiled/packaged artifacts reference runs.jsonl | None. |

**Verification commands run during research:**
```bash
grep -rn "runs.jsonl" /Users/belwinjulian/SwingTrading/src/ /Users/belwinjulian/SwingTrading/tests/ /Users/belwinjulian/SwingTrading/scripts/
# Output: only matches in .gitignore and .planning/ — no code references yet
```

The relocation from `/runs.jsonl` to `/data/runs.jsonl` is a pure gitignore edit + new code that targets the new path. There is no existing `runs.jsonl` file to migrate.

## Common Pitfalls

### Pitfall 1: GitHub Actions 60-day idle disable — confirmed still active

**What goes wrong:** Public repos with scheduled workflows but no commits for 60 days see this banner: "This scheduled workflow is disabled because there hasn't been activity in this repository for at least 60 days."

**Why it happens:** GitHub policy to free up runner pool from abandoned repos.

**How to avoid:** Weekly heartbeat workflow that commits a real file (D-11 `data/heartbeat.txt`). Confirmed by [community discussion 57858 (Oct 2024)](https://github.com/orgs/community/discussions/57858) — "Currently only new commits qualify as activity" — and is still current per the official [docs.github.com disabling-and-enabling-a-workflow](https://docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow) page (no version-of date but content is unchanged).

**Warning signs:** Workflow runs stop happening without a config change.

`[VERIFIED: docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow; community.github.com discussions 32197, 57858]`

### Pitfall 2: `if: success()` is the implicit default — be explicit on the success-side commit

**What goes wrong:** Reviewer reads two commit steps, sees only `if: failure()` on the second one, wonders what guards the first one.

**Why it happens:** GitHub Actions evaluates `if:` against cumulative job state. `if: success()` is implicit when omitted, but the symmetry with the failure step is lost.

**How to avoid:** Add `if: success()` explicitly on the success-path commit step (even though it's redundant). The symmetry makes the dichotomy obvious to anyone reviewing the workflow.

**Warning signs:** A reviewer flagging "what stops this step from running on failure?" — they shouldn't have to ask.

### Pitfall 3: `cancel-in-progress: true` on refresh.yml kills 90-min cold-cache runs

**What goes wrong:** Manual `workflow_dispatch` while a scheduled nightly is still running cancels the nightly. 60-90 minutes of OHLCV refresh is lost.

**Why it happens:** `cancel-in-progress: true` semantics — newer run cancels older same-group run.

**How to avoid:** Set `cancel-in-progress: false` on refresh.yml. The newer run will queue and start after the current one finishes (or after `timeout-minutes: 120` kills it).

**Trade-off:** If the running job is genuinely stuck and the user manually re-triggers, they'd have to cancel the old run from the Actions UI first. The 120-min timeout caps the worst case.

**Warning signs:** Reports missing for a day even though the workflow "succeeded" — actually got cancelled mid-run.

`[VERIFIED: docs.github.com/en/actions/.../control-the-concurrency-of-workflows-and-jobs; community discussions 5435, 53506]`

### Pitfall 4: `/reports/` gitignore line breaks OPS-02

**What goes wrong:** `.gitignore` line 47 has `/reports/` which gitignores every file under reports/. The auto-commit step's `file_pattern: reports/` runs `git add reports/` which silently does nothing because of the gitignore.

**Why it happens:** Phase 1 set up `/reports/` as gitignored when reports were not yet committed-to-repo. Phase 4 started writing real reports. The gitignore was never updated.

**How to avoid:** Add a carve-out in .gitignore (Phase 8 should do this):
```diff
-/reports/
+!/reports/
+!/reports/*.md
```
Mirror the `data/universe/` carve-out idiom. Or use `add_options: "-f"` — discouraged (hides the policy from reviewers).

**Warning signs:** OPS-02 SC#1 fails: the nightly "succeeds" but no report files are committed.

### Pitfall 5: JSONL append without `fsync` loses the last record on container kill

**What goes wrong:** Python `open('a')` buffers writes; `f.write(...)` returns without the data actually hitting disk. If the workflow runner is killed (timeout, OOM), the last record(s) are lost.

**Why it happens:** OS buffering + Python's text-mode buffering.

**How to avoid:** After `f.write(line)`, call `f.flush()` to push Python's buffer to the OS, then `os.fsync(f.fileno())` to force the OS to write to physical storage. Both are needed; `flush` alone doesn't fsync.

**Warning signs:** Run logs show pipeline completed (structlog `pipeline_complete` event) but `data/runs.jsonl` is missing the corresponding line.

`[CITED: https://docs.python.org/3/library/os.html#os.fsync; reinforced by deepeval issue #2322 search result]`

### Pitfall 6: `date +%Y-W%V` returns ISO 8601 week number — verify Mon-Fri alignment

**What goes wrong:** A nightly run on Saturday (manual dispatch) would compute a different `%V` than the previous Friday's nightly — same calendar week but `%V` is ISO 8601 which starts on Monday. On a Sunday `workflow_dispatch`, the week number could roll to the NEXT week (depending on year-end boundary).

**Why it happens:** `%V` is ISO 8601 week, which starts Monday. A run scheduled `30 22 * * 1-5` always fires Mon-Fri UTC — same `%V` for the whole week. Manual dispatch on weekends MAY produce a different `%V` near year boundary.

**How to avoid:** This is fine for the weekly-fallback semantics — even if Saturday's dispatch gets a different `%V`, the `restore-keys:` chain falls back further to `ohlcv-data-${{ runner.os }}-` which matches any prefix. Worst case: full cold-cache re-fetch. Best case: warm cache. No data loss.

**Warning signs:** None — this is a graceful degradation.

### Pitfall 7: stefanzweifel auto-commit handles "nothing to commit" gracefully (no-op, returns success)

**What goes wrong:** Worry: if the success-path commit runs but ALL files in `file_pattern` are unchanged, does the step fail?

**Why it doesn't:** The action runs a `git diff --quiet` dirty-check first. If nothing changed, it logs "Working tree clean. Nothing to commit." and exits 0. Output `changes_detected` is `"false"`. No commit is created.

**How to verify:** This is documented behavior. Test: comment-out the pipeline steps so nothing writes; confirm the auto-commit step exits 0.

`[VERIFIED: github.com/stefanzweifel/git-auto-commit-action README — "no commit if working tree clean"]`

### Pitfall 8: Heartbeat workflow needs `contents: write` (D-09 says `contents: read`)

**What goes wrong:** D-09 in CONTEXT.md states "CI and heartbeat use `contents: read`." But the heartbeat MUST `git push` `data/heartbeat.txt`, which requires write.

**Why it happens:** Likely a CONTEXT.md slip — the discuss session conflated "heartbeat doesn't need broad repo access" with "heartbeat is read-only."

**How to avoid:** Heartbeat workflow MUST use `permissions: contents: write` to commit the timestamp file. Phase 8 plan should explicitly correct this and flag it in the SUMMARY for human review.

**Warning signs:** Heartbeat job fails at the push step with "Permission denied to github-actions[bot]."

### Pitfall 9: Workflow YAML changes don't trigger CI — landing refresh.yml without testing it is risky

**What goes wrong:** The first time refresh.yml runs is at 22:30 UTC the night after the PR merges. If there's a YAML typo, the workflow fails silently (or, worse, the user doesn't notice for days).

**How to avoid:**
1. Add `workflow_dispatch:` (already in OPS-04) so the user can manually trigger immediately after merge to verify.
2. Run `actionlint` locally before commit: `brew install actionlint && actionlint .github/workflows/refresh.yml`.
3. Plan should include a checkpoint:human-verify task: "Manually trigger refresh.yml from the Actions tab and confirm green run."

## Code Examples

### Example 1: Compute daily + weekly cache keys (D-02)

```yaml
- name: Compute cache keys
  id: cache_keys
  run: |
    echo "daily=ohlcv-data-${{ runner.os }}-$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"
    echo "weekly=ohlcv-data-${{ runner.os }}-$(date -u +%Y-W%V)" >> "$GITHUB_OUTPUT"

- name: Restore data caches
  uses: actions/cache@<v4.3.0-sha>
  with:
    path: |
      data/ohlcv
      data/fundamentals
      data/insider
    key: ${{ steps.cache_keys.outputs.daily }}
    restore-keys: |
      ${{ steps.cache_keys.outputs.weekly }}
      ohlcv-data-${{ runner.os }}-
```

`[CITED: docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows]`

### Example 2: Run-log append with flush + fsync (Pitfall 5)

```python
import json, os
from pathlib import Path

def append_record(record: dict) -> None:
    path = Path("data/runs.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())  # CRITICAL: forces OS to write to disk
```

`[CITED: docs.python.org/3/library/os.html#os.fsync]`

### Example 3: GitHub Step Summary for OPS-05 SC#5

```yaml
- name: Surface failure in Actions summary
  if: failure()
  run: |
    {
      echo "## Nightly refresh FAILED"
      echo ""
      echo "**Run number:** ${{ github.run_number }}"
      echo "**UTC time:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo ""
      echo "See the pipeline step logs above for the error reason."
      echo "The failure record is committed to \`data/runs.jsonl\`."
    } >> "$GITHUB_STEP_SUMMARY"
```

`[CITED: docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#adding-a-job-summary]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `actions/cache@v2` (uploaded via tar.gz) | `actions/cache@v4` (zstd compression, 70% faster) | Feb 2024 (v4.0) | Use v4. v2/v3 still work but slower; v4 is the active major. |
| `actions/setup-python@v4` + pip cache | `astral-sh/setup-uv` with `enable-cache: true` | uv 0.4+ (Sep 2024) | Already adopted in ci.yml. Phase 8 reuses. |
| `git-auto-commit-action@v4` | `git-auto-commit-action@v5` (Node 20 runtime) | Oct 2023 (v5.0.0) | Use v5. v4 still works but Node 16 deprecation warnings. |
| Self-hosted heartbeat scripts | `gautamkrishnar/keepalive-workflow` action / manual heartbeat | 2022 | Both viable; D-11 chose the manual approach for transparency. |
| Empty-commit heartbeat | Real-file heartbeat | Always — empty commits don't count per GitHub policy | Use real-file (D-11). |

**Deprecated/outdated:**
- Node 16-runtime actions (warned since Oct 2024). All actions in Phase 8 are Node 20.
- `set-output` workflow command (replaced by `$GITHUB_OUTPUT` since 2022). Phase 8 uses `$GITHUB_OUTPUT`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `data/heartbeat.txt` is the right place for the heartbeat artifact (vs `.github/heartbeat`) | §Implementation Approach heartbeat.yml | LOW — D-11 specifies `data/heartbeat.txt` verbatim. |
| A2 | `actions/cache@v4.3.0` is the right minor version (latest stable v4) | §Pinned Action Hashes | LOW — verified against release page Sep 2024. Resolve full SHA at commit time. |
| A3 | Heartbeat needs `contents: write` despite CONTEXT.md D-09 saying `contents: read` | §Pitfalls #8 | MEDIUM — CONTEXT.md slip; human should confirm. Without write, heartbeat can't commit. Surfaced as Open Question A. |
| A4 | The `/reports/` gitignore line silently breaks OPS-02 and needs a carve-out | §Pitfalls #4 | MEDIUM — verified by reading .gitignore line 47. Plan MUST fix this. |
| A5 | `n_429_responses` is captured by counting structlog `fetch_429` events in `data/ohlcv.py`; v1 placeholder = 0 | §Integration Points | LOW — the field is required by OPS-05; ideally we plumb the count through pipeline state. v1 placeholder is acceptable since D-15 of CONTEXT.md (the schema example shows `n_429_responses: 3`) but no counter currently exists. Flag as Open Question B. |
| A6 | `python -m screener.publishers.run_log failure` works because publishers/ is in the import path | §Run-log Module | LOW — publishers/ is a real package with `__init__.py`; verified by Phase 4 imports. |
| A7 | `data/runs.jsonl` parent dir `data/` exists at workflow runtime (already committed via .gitkeep idiom) | §Run-log Module | LOW — Phase 1 + 2 established `data/.gitkeep` carve-outs. run_log.py also does `mkdir(parents=True, exist_ok=True)` defensively. |
| A8 | `bash -e` (`set -e`) chain in step 7 aborts on first non-zero exit, marking the job FAILED so `if: failure()` fires | §Implementation Approach | HIGH — central to the design. CONFIRMED: a non-zero exit from any step (including a `run:` chain with `set -e`) marks the step failed, which marks the job failed, which makes `success()` false and `failure()` true. `[VERIFIED: docs.github.com/en/actions/.../workflow-syntax-for-github-actions]` |
| A9 | The `picks_count` for the success record is `(composite_score_raw >= JOURNAL_THRESHOLD).sum()` — same threshold the journal uses | §Integration Points | LOW — Phase 7 establishes JOURNAL_THRESHOLD as the actionable cutoff; reusing it keeps the run-log semantics consistent with what the report shows. |

## Open Questions (RESOLVED)

> All questions in this section were resolved by the planner during plan creation. Each item below begins with `RESOLVED:` stating the adopted answer, followed by the original analysis for traceability.

1. **CONTEXT.md D-09 conflict: heartbeat permissions.** D-09 says "CI and heartbeat stay `contents: read`" — but heartbeat MUST commit. Plan should USE `contents: write` for heartbeat.yml and surface this in the SUMMARY as a CONTEXT.md correction. (Pitfall #8)

   **RESOLVED:** heartbeat.yml uses `permissions: contents: write`; deviation documented in `08-04-PLAN.md` `must_haves.truths` and will be re-surfaced in `08-04-SUMMARY.md` for human ratification. D-09 is treated as a slip (empty/tag commits don't count toward GitHub's 60-day idle rule, so a real-file commit — which requires write — is the only mitigation that works).

2. **`n_429_responses` plumbing — placeholder vs real count.** OPS-05 SC requires the field; CONTEXT D-05 example shows `n_429_responses: 3` (non-zero). The current codebase doesn't have a counter. Options:
   - (a) **Placeholder** = 0 in v1 — minimal scope; ship Phase 8 and add the counter in v1.x.
   - (b) **Plumb the count** via a shared counter in `data/ohlcv.py` (structlog `fetch_429` event) — adds touch points in data/ which Phase 8 ideally doesn't touch.
   - **Recommendation:** (a). Phase 8 scope creep risk is real; v1.x can add the proper count once the rate-limit-burst pattern is observable.

   **RESOLVED:** v1 ships `n_429_responses=0` placeholder per option (a); real counter deferred to v1.x. The field name is preserved in the OPS-05 schema, the `RunLogRecord` TypedDict, and the integration tests, so the observability surface remains correct and v1.x can add the real counter without touching the JSONL consumers. The `0` literal in `publishers/pipeline.py` carries an inline comment pointing back to this resolution.

3. **Are `splits.parquet` files actually being written?** The success commit's `file_pattern` includes `data/ohlcv/**/splits.parquet` (per CONTEXT.md "auto-commit scope"). Phase 2 DAT-08 says yes; but planner should verify via `ls data/ohlcv/*/splits.parquet | head` before assuming. If empty, drop from `file_pattern`.

   **RESOLVED:** Keep `data/ohlcv/**/splits.parquet` in the success-path `file_pattern`. Phase 2 DAT-08 produces these files; on any given run where no splits exist, `stefanzweifel/git-auto-commit-action` safely no-ops on the unmatched glob (`skip_dirty_check: false` default — the missing/empty match contributes nothing to the staged diff). No code change needed.

4. **Should the auto-commit step push to a branch or directly to main?** Default for `stefanzweifel/git-auto-commit-action@v5` is the current branch (which on a `schedule` trigger is the default branch = `main`). No PR flow. This is appropriate for a nightly artifact-only commit; CI on `main` only runs `push: branches: [main]` workflows which DO NOT include refresh.yml (no recursion risk). Confirm with planner.

   **RESOLVED:** Push directly to `main` via the default `stefanzweifel/git-auto-commit-action@v5.2.0` behavior. No PR flow in v1. Recursion is prevented by Phase 8's `on: schedule + workflow_dispatch` (no `push:` trigger on refresh.yml or heartbeat.yml). `T-08-commit-loop` regression-guarded by `test_refresh_no_github_event_interpolation_in_run_blocks` siblings + the `grep -c "push:"` assertions in Plans 08-04 / 08-06.

5. **Branch-protection interaction.** From STATE.md Phase 1 todos: "Apply branch protection on `main` via `gh api`..." — if branch protection requires status checks on every push to main, the auto-commit will FAIL because the bot's push won't pass CI. Mitigations:
   - (a) Exempt `github-actions[bot]` from branch protection.
   - (b) Have the workflow open a PR instead of pushing directly.
   - **Recommendation:** Defer to user. The Phase 1 todo about branch protection is still pending (per STATE.md). If branch protection IS applied, the auto-commit path needs PR-creation instead. This is a checkpoint:human-verify task for the plan.

   **RESOLVED:** Deferred to Plan 08-06 Task 3 (`checkpoint:human-verify`). The checkpoint script explicitly instructs the user to either (a) exempt `github-actions[bot]` from branch protection via the repo Settings -> Branches "Allow specified actors to bypass" UI, OR (b) defer the PR-based commit flow to a v1.x phase. The decision lives with the human at verification time because the branch-protection state isn't observable from the planner's vantage point.

6. **Cache eviction policy for the 10GB limit.** Russell 1000 OHLCV at ~50KB/ticker × 1000 = ~50MB per cache, well under 10GB. But the cache is keyed daily; over a week we accumulate 5 daily caches (~250MB) plus 1 weekly fallback (~50MB). GitHub auto-evicts least-recently-used. Worth a comment in the workflow YAML but no plan task needed.

   **RESOLVED:** No code change needed. GitHub `actions/cache@v4` 7-day idle eviction is acceptable given the daily key + weekly fallback key (`year-Wxx`) restore-keys chain in `refresh.yml`. Worst case: cold-cache full refresh (~90 min) on the first run after a long idle, well within the 120-minute `timeout-minutes` headroom (D-07). Inline comment in `refresh.yml` documents the design intent.

## Environment Availability

Phase 8 runs on GitHub-hosted `ubuntu-latest`. The runner provides everything; no local environment audit needed for the workflows themselves.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GitHub Actions runner | scheduled execution | ✓ (managed) | ubuntu-22.04+ | none |
| `bash` | step chain `set -e` | ✓ | 5.x | none |
| `date` (coreutils) | cache key computation | ✓ | 9.x with %V support | none |
| `git` | auto-commit action internals | ✓ | 2.40+ | none |
| `python` (installed by setup-uv + `uv python install`) | pipeline | ✓ | 3.11.x from pyproject | none |
| `uv` | dep install | ✓ via setup-uv | 0.11+ | none |
| `actionlint` (optional, local) | YAML lint | depends on dev machine | latest | skip — workflow_dispatch tests post-merge instead |

For local development: `brew install actionlint` is the recommended local lint check; the plan can document this as an optional pre-commit step but should NOT add a workflow that enforces it (scope creep).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (existing) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (existing) |
| Quick run command | `uv run pytest -m "not slow" -v` (matches ci.yml) |
| Full suite command | `uv run pytest -v` |
| Phase gate | All `tests/test_run_log*.py` + `tests/test_phase8_gitignore.py` pass, FND-04 still green |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | refresh.yml YAML is valid and schedules cron 30 22 * * 1-5 | static / actionlint | `actionlint .github/workflows/refresh.yml` (or manual visual review in PR) | ❌ Wave 0 |
| OPS-02 | Auto-commit action is pinned and configured with the correct file_pattern | static / unit | `pytest tests/test_phase8_workflow_static.py::test_refresh_workflow_pins_actions` | ❌ Wave 0 |
| OPS-03 | heartbeat.yml exists with correct cron + auto-commit | static | `pytest tests/test_phase8_workflow_static.py::test_heartbeat_workflow_exists_and_pinned` | ❌ Wave 0 |
| OPS-04 | workflow_dispatch is on refresh.yml | static | `pytest tests/test_phase8_workflow_static.py::test_refresh_has_workflow_dispatch` | ❌ Wave 0 |
| OPS-05 | run_log.append_record writes a valid JSONL line with all required fields, flushed + fsynced | unit | `pytest tests/test_run_log.py::test_append_record_writes_valid_jsonl_with_fsync` | ❌ Wave 0 |
| OPS-05 | runs.jsonl is NOT gitignored (carve-out works) | unit | `pytest tests/test_phase8_gitignore.py::test_runs_jsonl_not_ignored` | ❌ Wave 0 |
| OPS-05 | heartbeat.txt is NOT gitignored | unit | `pytest tests/test_phase8_gitignore.py::test_heartbeat_txt_not_ignored` | ❌ Wave 0 |
| OPS-05 | reports/*.md is NOT gitignored after Phase 8 carve-out | unit | `pytest tests/test_phase8_gitignore.py::test_reports_md_not_ignored` | ❌ Wave 0 |
| OPS-05 SC#5 | Failure path writes a record with `status: "failed"` and `error_reason != null` | unit | `pytest tests/test_run_log.py::test_cli_failure_entry_writes_failure_record` | ❌ Wave 0 |
| D-06 | No new typer subcommand (D-24 lock) | unit (existing) | `pytest tests/test_cli_smoke.py::test_subcommand_surface_locked` | ✅ exists |
| FND-04 (regression) | No-look-ahead test still passes | unit (existing) | `pytest tests/test_backtest_no_lookahead.py` | ✅ exists |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_run_log.py tests/test_phase8_*.py -v` (~5s — pure-Python unit tests)
- **Per wave merge:** `uv run pytest -m "not slow" -v` (matches ci.yml; ~30s)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus a checkpoint:human-verify task to manually trigger refresh.yml from the Actions tab post-merge.

### Wave 0 Gaps

- [ ] `tests/test_run_log.py` — covers OPS-05 schema, fsync, success vs failure records. NEW FILE.
- [ ] `tests/test_phase8_gitignore.py` — asserts gitignore carve-outs. Pattern: use `subprocess.run(["git", "check-ignore", "-v", "data/runs.jsonl"])` and assert exit code 1 (not ignored). NEW FILE.
- [ ] `tests/test_phase8_workflow_static.py` — parses the YAML files, asserts pinned action SHAs, cron schedules, conditional structure. NEW FILE. (Use `pyyaml` already in deps.)
- [ ] `tests/test_pipeline_emits_run_log.py` — integration test that `run_pipeline(snapshot_date)` writes a record to `data/runs.jsonl` in `tmp_path`. NEW FILE.
- [ ] `src/screener/publishers/run_log.py` — new module (the writer). NEW FILE.
- [ ] No new fixtures needed (use `tmp_path` + monkeypatch on `_RUNS_PATH`).

**actionlint as optional local tool:** Document in plan as "recommended pre-commit local check" but do NOT add as a CI job (scope creep). The static unit tests above cover the structural assertions actionlint would catch (pins, conditionals, file_pattern presence).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (limited) | GitHub Secrets for `FINNHUB_API_KEY`, `EDGAR_IDENTITY`, `FRED_API_KEY`. Injected as env vars at job level (not step level), scoped to the refresh job only. |
| V3 Session Management | no | No user sessions in scope. |
| V4 Access Control | yes | `permissions: contents: write` scoped per-workflow (D-09). Refresh job has write; ci.yml + no-lookahead-gate.yml stay read. Heartbeat needs write (Pitfall #8 / Open Question A). |
| V5 Input Validation | yes (limited) | run_log.py receives no untrusted input. The workflow YAML interpolates `${{ github.run_number }}` (a GitHub-provided integer) into commit messages — safe. NO use of `${{ github.event.* }}` interpolation in `run:` blocks (would be a script-injection vector). |
| V6 Cryptography | no | No cryptographic operations in Phase 8 scope. |
| V14 Configuration | yes | Pinned action SHAs (40-char) for every third-party action (supply-chain defense per Phase 1 / D-05 of ci.yml convention). |

### Known Threat Patterns for GitHub Actions + auto-commit

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted PR triggers nightly workflow | Tampering | refresh.yml is `schedule` + `workflow_dispatch` ONLY — no `pull_request` trigger. PRs can't run it. |
| Script injection via untrusted context | Tampering / Elevation | NO `${{ github.event.* }}` interpolation in `run:` blocks. The only interpolations are `${{ runner.os }}`, `${{ secrets.* }}`, `${{ github.run_number }}` — all GitHub-controlled. |
| Action supply-chain attack (malicious tag re-pointed at evil commit) | Tampering | Pin every action by 40-char commit SHA. Existing ci.yml convention; Phase 8 follows it. |
| Secret leak via `set -x` or echo | Information Disclosure | Don't `echo $FINNHUB_API_KEY`. GitHub Actions auto-masks values from `secrets.*` in logs, but `set -x` in the pipeline step could still leak. Mitigation: don't enable `set -x`; only `set -e`. |
| Commit-loop (commit triggers itself via `push` workflow) | DoS | refresh.yml uses `schedule` + `workflow_dispatch` only — does NOT trigger on `push`. No loop. heartbeat.yml ditto. ci.yml has `push: branches: [main]` — when refresh.yml commits to main, ci.yml WILL run. That's intended (validates the auto-commit didn't break tests) and is bounded (one ci.yml run per nightly). |
| Permissions over-scope | Elevation | `permissions: contents: write` scoped at workflow file level, not at the repo or PAT level. Default `GITHUB_TOKEN` cannot push to protected branches or modify branch-protection rules. |
| Cache poisoning across PRs | Tampering | `actions/cache` keys include `${{ runner.os }}` and date — PR-scoped caches don't collide with main-branch caches. Phase 8 is `schedule` + `workflow_dispatch` only; no PR participation. |

## Sources

### Primary (HIGH confidence)
- `.github/workflows/ci.yml` (this repo) — pinning convention, setup-uv pattern, concurrency boilerplate
- `.github/workflows/no-lookahead-gate.yml` (this repo) — path-filtered workflow pattern for reference
- `.gitignore` (this repo) — current carve-out idiom
- `src/screener/publishers/pipeline.py` (this repo) — `run_pipeline()` integration point
- `src/screener/persistence.py` (this repo) — atomic-write patterns (informs JSONL pattern by contrast — JSONL append is simpler)
- `src/screener/cli.py` (this repo) — 9-subcommand surface
- [docs.github.com — Disabling and enabling a workflow](https://docs.github.com/en/actions/managing-workflow-runs/disabling-and-enabling-a-workflow) — 60-day rule
- [docs.github.com — workflow-commands-for-github-actions](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions) — `$GITHUB_STEP_SUMMARY` syntax, 1 MiB limit
- [docs.github.com — Control the concurrency of workflows and jobs](https://docs.github.com/en/actions/using-workflows/control-the-concurrency-of-workflows-and-jobs) — `cancel-in-progress` semantics
- [docs.python.org — os.fsync](https://docs.python.org/3/library/os.html#os.fsync) — fsync semantics for JSONL crash-safety
- [github.com/stefanzweifel/git-auto-commit-action releases](https://github.com/stefanzweifel/git-auto-commit-action/releases) — v5.2.0 SHA confirmed
- [github.com/actions/cache releases](https://github.com/actions/cache/releases) — v4.3.0 latest (Sep 2024)
- [github.com/actions/checkout releases](https://github.com/actions/checkout/releases) — v4.2.2 / v4.3.1 SHAs

### Secondary (MEDIUM confidence)
- [community discussion #57858](https://github.com/orgs/community/discussions/57858) — confirms tags/empty commits don't count for the 60-day rule
- [community discussion #32197](https://github.com/orgs/community/discussions/32197) — 60-day rule semantics
- [community discussion #53506](https://github.com/orgs/community/discussions/53506) — `cancel-in-progress: false` behavior with queued runs
- [dev.to article — preventing 60-day disable](https://dev.to/gautamkrishnar/how-to-prevent-github-from-suspending-your-cronjob-based-triggers-knf) — heartbeat patterns
- [github.com/rhysd/actionlint](https://github.com/rhysd/actionlint) — local YAML lint tool

### Tertiary (LOW confidence — informational)
- General "Pattern: two-step success/failure commit" — synthesized from search results + GitHub docs, not from a single canonical source. Verified by reading the workflow-syntax-for-github-actions docs page on `if:` conditionals.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every action is pinned to a verified release in 2024; existing ci.yml already uses two of them.
- Architecture: HIGH — 11 locked decisions leave little discretion; integration points are concrete.
- Pitfalls: HIGH — all 9 pitfalls verified via official docs + community discussion + direct repo file reads.
- Validation: HIGH — pytest patterns established; new tests are pure-Python unit tests.
- Security: MEDIUM-HIGH — standard GitHub Actions hardening (pinned SHAs, scoped permissions, no untrusted interpolation); supply-chain risk acknowledged via SHA pinning.

**Research date:** 2026-05-19
**Valid until:** 2026-08-19 (90 days — GitHub Actions ecosystem is moderately stable; major API changes telegraphed months in advance)
