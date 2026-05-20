# Phase 8: GitHub Actions Cron & Operations - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 productionalizes the already-working local pipeline by running it nightly on GitHub Actions. Three deliverables:

1. **Nightly refresh workflow** (`.github/workflows/refresh.yml`) — runs the full pipeline (universe → ohlcv → macro → fundamentals → score → report → journal) on schedule `30 22 * * 1-5` UTC, commits the day's artifacts via `stefanzweifel/git-auto-commit-action@v5`, and supports `workflow_dispatch` for manual re-runs.

2. **Heartbeat workflow** (`.github/workflows/heartbeat.yml`) — weekly job that commits a timestamp to `data/heartbeat.txt` to prevent GitHub from disabling the nightly cron after 60 days of no push activity.

3. **Observability log** (`data/runs.jsonl`) — append-only JSONL file committed alongside each run's artifacts, recording start time, duration, fetch success rate, regime state, picks count, and 429 count. Failure entries are committed even when the health check fails.

Requirements covered: **OPS-01..OPS-05**.

</domain>

<decisions>
## Implementation Decisions

### OHLCV and data cache persistence (OPS-01)

- **D-01: Use `actions/cache` to persist OHLCV prices.parquet files between nightly runs.**
  - `data/ohlcv/**/prices.parquet` is gitignored and must survive across workflow runs. `actions/cache` is the correct approach — keeps git history clean, up to 10GB free, 7-day expiry covers weekends.

- **D-02: Cache key strategy — daily key with weekly fallback.**
  - Primary key: `ohlcv-data-${{ runner.os }}-${{ github.run_number }}-${{ steps.date.outputs.date }}`
    (or simpler: `ohlcv-data-${{ env.WEEK_KEY }}` with date computed from `date +%Y-W%V`)
  - Planner decides exact key format, but the policy is: try today's cache first, fall back to most recent weekly cache.
  - `restore-keys:` should include `ohlcv-data-{year}-W` prefix to pick up the most recent week's cache.

- **D-03: Cache scope — ohlcv + fundamentals + insider; NOT macro.**
  - Include: `data/ohlcv/`, `data/fundamentals/`, `data/insider/`
  - Exclude: `data/macro/` — macro data (SPY/QQQ/^VIX/FRED) is re-fetched fresh every night. Only 5 tickers, fast, ensures regime detection always uses the latest bar.
  - Fundamentals and insider are rate-limited (Finnhub 60 calls/min, EDGAR) and update infrequently; caching them avoids wasteful API calls.

### Observability log — runs.jsonl (OPS-05)

- **D-04: Relocate `runs.jsonl` from repo root to `data/runs.jsonl`.**
  - Current `.gitignore` has `/runs.jsonl` (ignores root-level file). Phase 8 moves it to `data/` and adds a carve-out: `!/data/runs.jsonl` (consistent with existing `!/data/universe/` pattern).
  - The planner must update `.gitignore`: remove `/runs.jsonl`, add `!/data/runs.jsonl` inside the `/data/*` block.

- **D-05: On health-check failure — commit the failure entry to `data/runs.jsonl` only; no other artifacts.**
  - Failure path: pipeline exits non-zero, the auto-commit step for reports/snapshots/journal is skipped (guarded with `if: success()`), but a separate step writes the failure record to `data/runs.jsonl` and commits ONLY that file.
  - Failure record fields: `status: "failed"`, `start_time`, `duration_seconds`, `fetch_success_rate`, `error_reason`, `picks_count: null`, `regime_state: null`, `n_429_responses`.
  - Success record fields: `status: "success"`, `start_time`, `duration_seconds`, `fetch_success_rate`, `regime_state`, `picks_count`, `n_429_responses`.
  - This means OPS-05 is satisfied: partial artifacts (report, snapshot, journal) are NOT committed on failure, but the failure IS traceable in `data/runs.jsonl`.

- **D-06: `runs.jsonl` is appended by the Python pipeline (via `screener` CLI or a dedicated script), not by bash in the workflow YAML.**
  - The pipeline already has structured logging (structlog). The run log entry should be written by a Python helper so the schema stays typed and consistent. Planner decides whether this is a new `screener run-log` subcommand or a module called internally by `run_pipeline`.
  - **Do NOT add a 10th typer subcommand** — CLI surface is locked at 9 per D-24 from Phase 6. Use a module-internal call or a `scripts/` helper.

### Workflow timeout (OPS-01)

- **D-07: Nightly refresh workflow `timeout-minutes: 120`.**
  - Warm cache (incremental ohlcv append): ~15–30 minutes typical.
  - Cold cache (full history re-download): up to 90 minutes worst case.
  - 120 minutes provides headroom for cold cache + transient yfinance slowness, while still killing runaway jobs.
  - At 120 min × 22 weekday runs/month = 2,640 min/month worst case. Public repos have unlimited minutes; private repos have 2,000 free — if the repo is private, warm-cache typical usage (~30 min × 22 = 660 min/month) stays well within budget.

- **D-08: CI workflow (`ci.yml`) timeout unchanged at 10 minutes per job.**
  - CI must be fast. If Phase 6 tests go over 10 minutes, that's a test performance issue to fix, not a timeout to raise.

### Workflow permissions and secrets

- **D-09: Refresh workflow uses `permissions: contents: write` for the auto-commit step; all other jobs (CI, heartbeat) use `contents: read`.**
  - `stefanzweifel/git-auto-commit-action@v5` requires write permission. Scoped only to the refresh workflow job.
  - Use the built-in `GITHUB_TOKEN` — no PAT needed for same-repo commits.

- **D-10: GitHub Secrets required for the nightly workflow:**
  - `FINNHUB_API_KEY` — already in `.env.example`
  - `EDGAR_IDENTITY` — already in `.env.example` (format: `"Name <email>"`)
  - No yfinance key needed.
  - These are injected via `env:` block in the workflow job. The pydantic-settings `Settings` class already reads from env vars as fallback when `.env` is absent.

### Heartbeat workflow (OPS-03)

- **D-11: Heartbeat workflow commits a timestamp to `data/heartbeat.txt` weekly.**
  - Runs on `0 9 * * 1` (Monday 09:00 UTC — before any market action).
  - Commits `data/heartbeat.txt` with ISO timestamp (`echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > data/heartbeat.txt`).
  - Uses `stefanzweifel/git-auto-commit-action@v5` with `commit_message: "chore: weekly heartbeat"`.
  - `data/heartbeat.txt` must be added to `.gitignore` carve-out: `!/data/heartbeat.txt`.

### Claude's Discretion

- **Exact `actions/cache` key format** — planner decides the precise YAML expression for the daily + weekly-fallback key. Week number via `date +%Y-W%V` is the recommended basis.
- **How `data/runs.jsonl` is written** — module-internal call from `run_pipeline` vs. a `scripts/write_run_log.py` helper. Either is fine; planner decides what integrates cleanest with the existing pipeline structure.
- **Heartbeat commit author** — default GitHub Actions bot `github-actions[bot]` is fine.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 8: GitHub Actions Cron & Operations" — goal, 5 success criteria (OPS-01..OPS-05), exact cron schedule, artifact list
- `.planning/REQUIREMENTS.md` §Operations (OPS-01..OPS-05) — atomic requirements for nightly workflow, auto-commit, heartbeat, workflow_dispatch, runs.jsonl

### Existing workflow patterns to follow
- `.github/workflows/ci.yml` — existing uv + Python setup pattern (`astral-sh/setup-uv`, `uv sync --frozen --extra dev`); use identical pinned action hashes for consistency
- `.github/workflows/no-lookahead-gate.yml` — path-filtered workflow pattern; shows `concurrency` + `permissions` boilerplate already in use

### Data persistence and gitignore
- `.gitignore` — lines 42–52: current data/ carve-out block; Phase 8 must update: remove `/runs.jsonl`, add `!/data/runs.jsonl` and `!/data/heartbeat.txt` carve-outs
- `.env.example` — secrets template; `FINNHUB_API_KEY` and `EDGAR_IDENTITY` are the secrets needed in GitHub repository settings

### Pipeline and CLI
- `src/screener/cli.py` — 9-subcommand surface locked (D-24 from Phase 6); do NOT add a 10th subcommand for run logging
- `src/screener/publishers/pipeline.py` — `run_pipeline()` is the integration point; run log entry should be written here or called from here
- `Makefile` — `all: data rank report` is the existing daily DAG; the nightly workflow runs this sequence with `journal` appended

### Prior phase decisions
- `.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md` §D-24 — 9-subcommand CLI surface locked; runs.jsonl write must NOT be a new subcommand
- `.planning/phases/02-data-foundation/02-CONTEXT.md` §D-19 — data/ gitignore carve-out policy (atomic writes, allowlist pattern)

### stefanzweifel auto-commit action
- Action: `stefanzweifel/git-auto-commit-action@v5` — used in both refresh and heartbeat workflows; requires `permissions: contents: write`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` — pinned `astral-sh/setup-uv` hash + `uv sync --frozen --extra dev` install pattern; copy verbatim into refresh workflow for consistency
- `src/screener/publishers/pipeline.py` `run_pipeline()` — the single orchestration point; run log entry written here (start timer at top, write record at bottom)
- `src/screener/persistence.py` — `_write_parquet_atomic` and SQLite append pattern; run log uses `open(path, 'a')` + `json.dumps(record) + '\n'` (no pandera schema needed for JSONL)

### Established Patterns
- **`concurrency` group + `cancel-in-progress: true`** — both existing workflows use this; refresh workflow should too (prevents overlapping nightly runs if a previous one is still running)
- **Pinned action hashes** — both existing workflows pin `actions/checkout` and `astral-sh/setup-uv` to exact commit hashes for supply-chain security; refresh workflow must follow the same pattern
- **`env:` secrets injection** — pydantic-settings reads env vars as fallback when `.env` is absent; inject `FINNHUB_API_KEY` and `EDGAR_IDENTITY` via `env:` block at job level

### Integration Points
- **cache step placement** — `actions/cache` restore step must come BEFORE the `uv run screener refresh-ohlcv` step, and the cache save (post-job) happens automatically after the job completes
- **auto-commit scope** — the auto-commit action's `file_pattern` should list `data/runs.jsonl data/snapshots/ data/universe/ data/journal.sqlite reports/ data/ohlcv/**/splits.parquet`; exclude `data/ohlcv/**/prices.parquet` (cached, not committed)
- **failure path commit** — a second, separate auto-commit step guarded with `if: failure() || (steps.health_check.outcome == 'failure')` commits only `data/runs.jsonl` on failure

</code_context>

<specifics>
## Specific Ideas

- **runs.jsonl schema (from OPS-05 + discussion):**
  ```json
  {
    "status": "success|failed",
    "start_time": "2026-05-19T22:30:05Z",
    "duration_seconds": 1847,
    "fetch_success_rate": 0.982,
    "regime_state": "Confirmed Uptrend",
    "picks_count": 7,
    "n_429_responses": 3,
    "error_reason": null
  }
  ```
  On failure: `regime_state`, `picks_count` are `null`; `error_reason` contains the failure message (e.g., `"universe coverage 91.2% < 95% threshold"`).

- **`data/heartbeat.txt` content:** single ISO timestamp line, e.g., `2026-05-19T09:00:00Z`. Overwritten each week (not appended).

- **Refresh workflow job name:** `refresh` (matches the workflow filename). Single job, sequential steps.

- **Heartbeat workflow:** separate file `.github/workflows/heartbeat.yml`. Minimal — just checkout, write timestamp, auto-commit.

- **`workflow_dispatch` on refresh workflow** — no inputs needed; the user triggers it from the Actions tab with default behavior (runs the same pipeline as the scheduled run).

</specifics>

<deferred>
## Deferred Ideas

- **Slack/Discord notification on nightly failure** — mentioned as a possible addition; deferred as scope creep. The GitHub Actions default email notification is sufficient for v1. Can be added in v1.x via a `slackapi/slack-github-action` step.
- **Per-ticker fetch timing stats in runs.jsonl** — richer observability (slowest tickers, distribution of fetch times); deferred to v1.x. OPS-05 schema is sufficient for v1.
- **Retry failed tickers in a second pass** — on partial health check (e.g., 93% success rate), retry only the failed tickers before giving up; deferred. v1 fails fast at the 95% threshold.

</deferred>

---

*Phase: 8-GitHub Actions Cron & Operations*
*Context gathered: 2026-05-19*
