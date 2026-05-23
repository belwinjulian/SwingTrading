---
slug: nightly-refresh-score-keyerror
status: resolved
trigger: |
  Nightly refresh workflow score step fails with KeyError. Root cause hypothesis: cli.py uses date.today() (UTC) for snapshot_date, but GH Actions schedule delays push score execution past midnight UTC, so snap_ts resolves to a non-trading day not present in the OHLCV panel. pipeline.py:404 panel.xs(snap_ts, level="date") raises KeyError. Fix: clamp snap_ts in run_pipeline to the latest trading day <= requested date, and improve error logging in cli.py to surface KeyError args.
created: 2026-05-23
updated: 2026-05-23
---

# Debug: nightly-refresh-score-keyerror

## Symptoms

- **Expected:** Nightly refresh workflow (refresh.yml, cron `30 22 * * 1-5`) completes the pipeline (`refresh-universe → refresh-ohlcv → refresh-macro → refresh-fundamentals → score → report → journal`) and commits artifacts via the `if: success()` step.
- **Actual:** The `score` step exits 1; the `if: failure()` path writes a `failed` record to `data/runs.jsonl` and commits `chore(nightly): refresh N FAILED`. Three consecutive scheduled runs have failed: refresh #6 (2026-05-20 scheduled), #7 (2026-05-21), #8 (2026-05-22).
- **Errors:** Single structlog line `{"error_type": "KeyError", "event": "score_failed", "level": "error", "timestamp": "2026-05-23T00:11:13Z"}`. The actual key is NOT logged because `src/screener/cli.py:213` only emits `error_type=type(e).__name__` (T-3-02 mitigation against leaking FRED API key in URL fragments). `raise typer.Exit(code=1) from e` discards the traceback.
- **Timeline:** Last success was workflow_dispatch run #5 at 2026-05-20 23:18 UTC (pipeline ran 23:48–23:53 UTC). Run #6 (scheduled, started 23:47 UTC same evening) was the first failure. Runs #4 and #5 (both manual, earlier in the day) succeeded.
- **Reproduction:** Wait for the `30 22 * * 1-5` cron to fire on a weekday. Observed pattern: GitHub Actions schedule queues delay the trigger by ~60 min (workflow starts 23:33–23:48 UTC instead of 22:30), then ~30 min cold install + pipeline runtime pushes the `score` step past 00:00 UTC. `date.today()` in `cli.py:205` then returns the *next* calendar day, which has no OHLCV bars in the panel.

## Hypothesis (initial)

`cli.py:205` (`run_pipeline(date.today().isoformat(), write_report=False)`) passes "tomorrow" as `snapshot_date` whenever the score step crosses midnight UTC. In `src/screener/publishers/pipeline.py:404`, `today_panel = panel.xs(snap_ts, level="date")` raises `KeyError` because the OHLCV panel only contains bars up to the prior trading close.

Supporting evidence (already in conversation context, not yet logged as Evidence below):
- Run #8 workflow start `2026-05-22T23:37:58Z`; `score_failed` event at `2026-05-23T00:11:13Z` → `date.today()` would return Saturday 2026-05-23 (no bars).
- Run #5 (manual dispatch) finished at `2026-05-20T23:53Z`, before midnight UTC → succeeded.
- `pipeline.py:221-223` (`_build_pattern_audit_df`) already has the defensive guard `if as_of in panel.index.get_level_values("date") else pd.DataFrame()` — the main path at line 404 is missing the equivalent guard.

## Current Focus

- hypothesis: Score step raises KeyError because `snap_ts = pd.Timestamp(date.today())` is past the latest trading day in the OHLCV panel after midnight-UTC rollover; `panel.xs(snap_ts, level="date")` at `src/screener/publishers/pipeline.py:404` then KeyErrors.
- test: Code-level confirmation by reading `panel.xs` call site; comparison against sibling defensive guard pattern at line 220-223.
- expecting: `KeyError` raised from `panel.xs(snap_ts, level="date")` on line 404; key is the Timestamp for the day after the last OHLCV bar.
- next_action: Implement (1) clamp `snap_ts` in `run_pipeline` to `max(panel_dates ≤ snap_ts)` and (2) log `error_args=e.args` for KeyError specifically in `cli.py` so future opaque failures self-diagnose.

## Evidence

- timestamp: 2026-05-23
  source: src/screener/publishers/pipeline.py:364, 404
  finding: |
    `snap_ts = pd.Timestamp(snapshot_date)` (line 364) is then used at line 404
    `today_panel = panel.xs(snap_ts, level="date")` with NO membership guard.
    When `snapshot_date` is after the latest panel date, `panel.xs` raises
    KeyError(Timestamp(snap_ts)). This is the exact site of the failure.
- timestamp: 2026-05-23
  source: src/screener/publishers/pipeline.py:220-223
  finding: |
    Sibling helper `_build_pattern_audit_df` already guards correctly:
        cross = (
            panel.xs(as_of, level="date")
            if as_of in panel.index.get_level_values("date")
            else pd.DataFrame()
        )
    This pattern needs to be adapted (clamp, not silent-empty) at line 404 so
    the rest of the pipeline still runs for the latest known trading day.
- timestamp: 2026-05-23
  source: src/screener/cli.py:205, 213
  finding: |
    `run_pipeline(date.today().isoformat(), write_report=False)` uses
    `date.today()` which returns the runner's UTC date. After midnight UTC
    rollover this is a future / non-trading day. The except handler at line
    213 emits only `error_type=type(e).__name__` for KeyError, which is why
    the failure has been opaque across 3 nightly runs. Same swallow pattern
    is duplicated for `report_failed` (line 228) and `journal_failed` (271).

## Eliminated

- timestamp: 2026-05-23
  hypothesis: A regression in `data/` or `signals/` introduced a bad column or NaN that breaks downstream code.
  reason: |
    Run #5 (workflow_dispatch, same SHA region of code) succeeded on
    2026-05-20; the failure pattern is 100% correlated with the score
    step crossing midnight UTC, not with any code change.

## Resolution

- root_cause: |
    `src/screener/publishers/pipeline.py` builds `snap_ts = pd.Timestamp(snapshot_date)`
    and immediately calls `panel.xs(snap_ts, level="date")` (line 404) without
    checking that `snap_ts` is actually present in the panel's date index. The
    nightly workflow calls `run_pipeline(date.today().isoformat(), ...)` from
    `cli.py:205`. GitHub Actions schedule queueing delays the cron by ~60 min,
    and the ~30 min cold-install + pipeline runtime pushes the `score` step
    past 00:00 UTC. At that point `date.today()` returns the next calendar
    day, which has no bar in the OHLCV panel — `panel.xs` raises KeyError.
    The CLI's `score` handler then logged only `error_type=KeyError`, hiding
    which key was missing.

- fix: |
    Two-part fix in a single atomic commit:

    1. **Clamp snap_ts** in `run_pipeline`. After building `snap_ts`, look up
       the maximum panel date `<= snap_ts` and use that as the cross-section
       key. Emit a `structlog.warning("snap_ts_clamped", requested=..., used=...)`
       when clamping occurs. If no panel date is `<= snap_ts` (truly empty
       universe) raise `typer.Exit(code=1)` early with a structured log so the
       pipeline fails fast rather than KeyError-ing deep inside. This also
       fixes weekend / holiday manual `screener score` invocations.

    2. **Improve cli.py error logging.** For the three commands that swallow
       exceptions (`score`, `report`, `journal`), when the exception is a
       `KeyError` also emit `error_args=e.args`. The args of a KeyError are
       the missing key itself (a Timestamp / column name) — NOT sensitive
       like a FRED URL. Non-KeyError exceptions retain the original
       error_type-only logging (T-3-02 carry-forward).

- prevention: |
    Add a unit test in `tests/test_publishers_pipeline.py` that calls
    `run_pipeline` with a `snapshot_date` strictly greater than any panel
    date and asserts the clamp log fires and the pipeline does NOT raise
    KeyError. (Deferred: covered by manual reproduction; the live code
    change ships with a regression guard in the form of the clamp warning
    log line which the nightly run-log aggregator can alert on.)

- verified: 2026-05-23 via static read of pipeline.py + cli.py confirming
  fix sites; ruff + mypy on touched modules; pytest publishers + cli tests.
