---
phase: 07-sizing-finalization-paper-trade-journal
plan: "05"
type: execute
wave: 3
depends_on: ["07-04"]
files_modified:
  - src/screener/cli.py
  - tests/test_cli_smoke.py
  - tests/test_journal.py
autonomous: true  # Plan-level autonomy; Task 3 is a checkpoint:human-verify gate (revision iter 1 Warning #8)
requirements: [OUT-04]
requirements_addressed: [OUT-04]
tags: [phase-7, cli, journal-body, stub-removal, surface-lock-defense, idempotent-catchup]

must_haves:
  truths:
    - "src/screener/cli.py `journal` command (lines 232-235) body filled — calls _build_journal_rows_df_from_snapshot + validate_at_write(PicksSchema) + append_picks_rows"
    - "cli.journal uses the SAME try/except idiom as cli.score (cli.py:198-214) — typer.Exit propagates; broad Exception caught with error_type-only logging"
    - "tests/test_cli_smoke.py: PHASE_1_STUBS list has `journal` REMOVED — list becomes empty (test_each_phase1_stub_exits_zero_with_stub_log loop becomes a no-op)"
    - "tests/test_cli_smoke.py: NEW test test_journal_subcommand_no_longer_stub added (mirror line-for-line of test_score_subcommand_no_longer_stub at lines 234-244)"
    - "tests/test_journal.py: test_journal_cli_idempotent skeleton from Plan 07-03 is FILLED with a real body"
    - "D-24 9-subcommand CLI surface UNCHANGED — D14_SUBCOMMANDS list at test_cli_smoke.py:20-30 untouched"
    - "test_subcommand_surface_locked at test_cli_smoke.py:292-316 still passes"
    - "FND-04 no-look-ahead mutation gate still passes"
  artifacts:
    - path: "src/screener/cli.py"
      provides: "real body for the `journal` typer command (replaces _stub call)"
      contains: "_build_journal_rows_df_from_snapshot"
    - path: "tests/test_cli_smoke.py"
      provides: "PHASE_1_STUBS now empty + test_journal_subcommand_no_longer_stub mirror test"
      contains: "test_journal_subcommand_no_longer_stub"
    - path: "tests/test_journal.py"
      provides: "test_journal_cli_idempotent real body (replaces Plan 07-03's deferred skip)"
      contains: "result2.exit_code"
  key_links:
    - from: "src/screener/cli.py journal()"
      to: "src/screener/publishers/pipeline._build_journal_rows_df_from_snapshot"
      via: "function import + call with date.today().isoformat()"
      pattern: "_build_journal_rows_df_from_snapshot"
    - from: "src/screener/cli.py journal()"
      to: "src/screener/persistence.append_picks_rows"
      via: "INSERT OR IGNORE — idempotent re-run"
      pattern: "append_picks_rows\\("

user_setup: []
---

<objective>
Wave 3 final integration: fill the `journal` typer command body in `src/screener/cli.py` (lines 232-235) using the `_build_journal_rows_df_from_snapshot` helper factored in Plan 07-04. Remove `"journal"` from `PHASE_1_STUBS` in `tests/test_cli_smoke.py` and add `test_journal_subcommand_no_longer_stub` (mirror of test_score_subcommand_no_longer_stub). Land the real body in the previously-deferred `test_journal_cli_idempotent` skeleton in `tests/test_journal.py`.

Purpose: This closes Phase 7. After this plan, the user can run `screener report` to produce both the markdown report AND the journal entry in one command, OR `screener journal` separately to catch-up the journal from an existing snapshot. The 9-subcommand surface (D-24) remains LOCKED — no 10th subcommand was added.

Output: Modified cli.py (one stub body filled), modified test_cli_smoke.py (stub list + 1 mirror test), modified test_journal.py (1 deferred test now real). Phase 7 complete.

**Revision iteration 1 — Warnings addressed:**
- **#8:** Frontmatter changed from `autonomous: false` to `autonomous: true`. Only Task 3 requires human verification, and it carries `type="checkpoint:human-verify"` which already provides the gate semantics. The plan-level frontmatter flag was incorrectly conservative.
- **#9:** PHASE_1_STUBS emptiness check no longer uses the brittle `grep -A8 "^PHASE_1_STUBS"` line-window pattern (which silently misses reformatted multi-line lists). Replaced with a real Python import + `assert m.PHASE_1_STUBS == []` — survives any whitespace / comment / multi-line refactor.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-04-pipeline-report-wiring-PLAN.md
@CLAUDE.md
@src/screener/cli.py

<interfaces>
<!-- Key types and contracts extracted from the codebase. -->

Existing cli.journal stub (src/screener/cli.py:232-235) — the line numbers and EXACT content to replace:
```python
@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract)."""
    _stub("journal")
```

Closest analog — cli.score body (cli.py:198-214) — the EXACT shape to copy:
```python
@app.command("score")
def score() -> None:
    """Compute composite scores; write data/snapshots/YYYY-MM-DD.parquet."""
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline

        run_pipeline(date.today().isoformat(), write_report=False)
    except typer.Exit:
        # Pitfall 7: validate_run's typer.Exit MUST propagate to set
        # process exit code; do NOT catch in the broader Exception handler.
        raise
    except Exception as e:
        # T-3-02 mitigation carry-forward: log only error_type, never the
        # exception string (may contain FRED API key URL fragments etc.).
        log.error("score_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

Existing test_cli_smoke.py PHASE_1_STUBS list (lines 38-43):
```python
PHASE_1_STUBS = [
    # Phase 6 (Plan 06-01) removed `refresh-fundamentals` from this list — its
    # body is filled by Plan 06-05 (Wave 4); see test_refresh_fundamentals_
    # subcommand_no_longer_stub below.
    "journal",
]
```

Existing test_score_subcommand_no_longer_stub mirror (test_cli_smoke.py:234-244 — EXACT shape to copy):
```python
def test_score_subcommand_no_longer_stub() -> None:
    """Phase 4: `score` ships a real body — invoking it does NOT emit a
    '[stub] score not yet implemented' line. Real run will fail without
    data files, but the failure is from publishers.pipeline, not [stub]."""
    runner = CliRunner()
    result = runner.invoke(app, ["score"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events if ev.get("command") == "score" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener score` still emits a [stub] line: {stub_events!r}"
```

Existing D14_SUBCOMMANDS list (test_cli_smoke.py:20-30) — DO NOT TOUCH. Existing test_subcommand_surface_locked (test_cli_smoke.py:292-316) — DO NOT TOUCH.

CliRunner usage note (Phase 6 Plan 06-05 deviation): `CliRunner(mix_stderr=False)` is NOT supported by typer 0.25.x CliRunner — use `CliRunner()` without the kwarg.

_build_journal_rows_df_from_snapshot (Plan 07-04 Task 1):
- Signature: `_build_journal_rows_df_from_snapshot(snapshot_date: str) -> pd.DataFrame`
- Returns an empty DataFrame if the snapshot file is missing or no rows pass the threshold/regime filter
- Already handles the PicksSchema-shaped row build with features_json embedded

persistence imports (Plan 07-03):
- `PicksSchema` — pandera DataFrameModel
- `append_picks_rows(rows: list[dict], db_path=None) -> int`
- `validate_at_write(schema_cls, df) -> pd.DataFrame`
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fill cli.journal body + remove "journal" from PHASE_1_STUBS + add test_journal_subcommand_no_longer_stub</name>
  <files>src/screener/cli.py, tests/test_cli_smoke.py</files>
  <read_first>
    - src/screener/cli.py (lines 198-214 — `score` body, the analog to copy)
    - src/screener/cli.py (lines 232-235 — `journal` stub to replace)
    - src/screener/cli.py (top of file — imports: `date`, `typer`, `log`, `configure_logging`, `_stub`)
    - tests/test_cli_smoke.py (lines 20-30 — D14_SUBCOMMANDS lock; DO NOT touch)
    - tests/test_cli_smoke.py (lines 38-43 — PHASE_1_STUBS to modify)
    - tests/test_cli_smoke.py (lines 234-244 — test_score_subcommand_no_longer_stub mirror to copy)
    - tests/test_cli_smoke.py (lines 292-316 — test_subcommand_surface_locked; DO NOT touch)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/cli.py" (CLI body shape verbatim)
    - .planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-05-SUMMARY.md (Plan 06-05 deviation note about CliRunner mix_stderr=False)
  </read_first>
  <behavior>
    - `screener journal` no longer emits `[stub] journal not yet implemented` log message
    - `screener journal` body calls `_build_journal_rows_df_from_snapshot(date.today().isoformat())`
    - If the returned DataFrame is empty: emit `journal_catchup_empty` event and exit 0
    - If non-empty: validate via `validate_at_write(PicksSchema, df)`, convert to records, call `append_picks_rows(records)`, emit `journal_catchup_complete` event with n_attempted / n_inserted / n_idempotent_skip
    - typer.Exit propagates (Pitfall 7); broader Exception caught and logged with error_type only (T-3-02)
    - tests/test_cli_smoke.py: `PHASE_1_STUBS` becomes empty list (with comment noting Plan 07-05 removed `journal`)
    - tests/test_cli_smoke.py: new `test_journal_subcommand_no_longer_stub` placed BEFORE `test_subcommand_surface_locked` (so the surface-lock test stays at the bottom as the final guardrail)
    - D14_SUBCOMMANDS list and test_subcommand_surface_locked are byte-identical before and after this plan
  </behavior>
  <action>
**A. Replace the `journal` stub in `src/screener/cli.py` (lines 232-235)** with the following body. The existing 4-line stub (decorator + def + docstring + `_stub("journal")`) is REPLACED by this 30-line block:

```python
@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract).

    Idempotent catch-up: reads data/snapshots/<today>.parquet, filters to
    actionable picks (composite_score >= JOURNAL_THRESHOLD AND regime_state
    != 'Correction'), and re-appends via persistence.append_picks_rows.
    INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) makes re-runs zero-insert
    (CONTEXT D-01).
    """
    configure_logging()
    try:
        from screener.persistence import (
            PicksSchema,
            append_picks_rows,
            validate_at_write,
        )
        from screener.publishers.pipeline import _build_journal_rows_df_from_snapshot

        today_iso = date.today().isoformat()
        journal_rows_df = _build_journal_rows_df_from_snapshot(today_iso)
        if journal_rows_df.empty:
            log.info("journal_catchup_empty", snapshot_date=today_iso)
            return
        validated = validate_at_write(PicksSchema, journal_rows_df)
        n_inserted = append_picks_rows(validated.to_dict(orient="records"))
        log.info(
            "journal_catchup_complete",
            snapshot_date=today_iso,
            n_attempted=len(journal_rows_df),
            n_inserted=n_inserted,
            n_idempotent_skip=len(journal_rows_df) - n_inserted,
        )
    except typer.Exit:
        # Pitfall 7: typer.Exit from validate_at_write or append_picks_rows
        # MUST propagate to set process exit code.
        raise
    except Exception as e:
        # T-3-02 carry-forward: log only error_type, never str(e).
        log.error("journal_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

If the original file's `_stub` import is no longer used after this edit AND no other command still calls `_stub`, leave the import alone (other phases may add stubs later); only remove it if `grep -c "_stub(" src/screener/cli.py` returns 0 after the edit.

**B. Modify `tests/test_cli_smoke.py` PHASE_1_STUBS** (lines 38-43) — REPLACE the list with the empty list + Phase 7 comment:

```python
PHASE_1_STUBS: list[str] = [
    # Phase 6 (Plan 06-01) removed `refresh-fundamentals` from this list — its
    # body is filled by Plan 06-05 (Wave 4).
    # Phase 7 (Plan 07-05) removed `journal` from this list — its body is filled
    # by Plan 07-05; see test_journal_subcommand_no_longer_stub below.
    # The list is intentionally empty now; the iterator
    # test_each_phase1_stub_exits_zero_with_stub_log becomes a no-op (zero
    # iterations, zero assertions) — harmless.
]
```

**C. Add `test_journal_subcommand_no_longer_stub` to tests/test_cli_smoke.py** — INSERT it immediately BEFORE the `test_subcommand_surface_locked` function (search for `def test_subcommand_surface_locked` to find the right location; the new test goes on the line BEFORE that `def`):

```python


def test_journal_subcommand_no_longer_stub() -> None:
    """Phase 7 (Plan 07-05): `journal` ships a real body — invoking it does
    NOT emit a '[stub] journal not yet implemented' line. Real run will fail
    without data/snapshots/<today>.parquet (handled gracefully by
    _build_journal_rows_df_from_snapshot returning empty + emitting
    'journal_catchup_empty'), but the absence of [stub] is what this test
    asserts. Mirror line-for-line of test_score_subcommand_no_longer_stub.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["journal"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events if ev.get("command") == "journal" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener journal` still emits a [stub] line: {stub_events!r}"
```

Use `CliRunner()` WITHOUT the `mix_stderr` kwarg (Phase 6 Plan 06-05 deviation — typer 0.25.x compatibility).

DO NOT modify D14_SUBCOMMANDS (lines 20-30) or test_subcommand_surface_locked (lines 292-316). DO NOT add any new subcommand to the CLI surface.
  </action>
  <verify>
    <automated>uv run pytest tests/test_cli_smoke.py --no-cov -q 2>&1 | tail -5 && uv run python -c "from typer.testing import CliRunner; from screener.cli import app; result = CliRunner().invoke(app, ['journal']); assert '[stub] journal' not in result.stdout, f'still stub: {result.stdout}'; print('journal body OK, exit_code=', result.exit_code)"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "def journal\(\) -> None:" src/screener/cli.py` returns exactly one match
    - `grep -c "_stub(.journal.)" src/screener/cli.py` outputs `0` (stub call removed from journal body)
    - `grep -c "_build_journal_rows_df_from_snapshot" src/screener/cli.py` outputs `1`
    - `grep -c "from screener.persistence import" src/screener/cli.py` ≥ 1 with PicksSchema, append_picks_rows, validate_at_write (multiline allowed: `grep -c "PicksSchema\|append_picks_rows\|validate_at_write" src/screener/cli.py` ≥ 3)
    - `grep -c "journal_catchup_complete\|journal_catchup_empty\|journal_failed" src/screener/cli.py` ≥ 3
    - `grep -c "except typer\.Exit:" src/screener/cli.py` ≥ 2 (existing score + new journal — DO NOT count comments: actually `grep -v '^\s*#' src/screener/cli.py | grep -c "except typer\.Exit:"` ≥ 2)
    - `grep -c "^def test_journal_subcommand_no_longer_stub" tests/test_cli_smoke.py` outputs `1`
    - D14_SUBCOMMANDS list at test_cli_smoke.py:20-30 byte-identical before and after — verify by: `grep -A11 "^D14_SUBCOMMANDS" tests/test_cli_smoke.py | head -12` — output unchanged
    - PHASE_1_STUBS list contains zero string entries (only comments): `uv run python -c "import importlib, sys; sys.path.insert(0, 'tests'); m = importlib.import_module('test_cli_smoke'); assert m.PHASE_1_STUBS == [], f'PHASE_1_STUBS not empty: {m.PHASE_1_STUBS!r}'"` exits 0 (revision iter 1 Warning #9 — replaces the brittle `grep -A8` line-window gate with a real-import assertion that survives any whitespace / comment / multi-line reformatting)
    - `uv run pytest tests/test_cli_smoke.py --no-cov -q` shows all tests pass (including new test_journal_subcommand_no_longer_stub, test_subcommand_surface_locked, test_score_subcommand_no_longer_stub, test_refresh_fundamentals_subcommand_no_longer_stub)
    - cli.py uses no `print()`: `grep -c "^\s*print(" src/screener/cli.py` outputs `0`
  </acceptance_criteria>
  <done>
    cli.journal has a real body (~30 lines). PHASE_1_STUBS list is empty. test_journal_subcommand_no_longer_stub added. D-24 surface lock unchanged. All test_cli_smoke.py tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fill test_journal_cli_idempotent body in tests/test_journal.py (deferred from Plan 07-03)</name>
  <files>tests/test_journal.py</files>
  <read_first>
    - tests/test_journal.py (current file — test_journal_cli_idempotent remains pytest.skip('Plan 07-05') from Plan 07-03)
    - tests/test_journal.py existing tests for the `_make_row` helper and tmp_path + monkeypatch idiom (added in Plan 07-03 Task 2)
    - tests/test_cli_smoke.py (CliRunner pattern — same `runner.invoke(app, ["journal"])` idiom as test_journal_subcommand_no_longer_stub)
    - tests/test_pipeline_journal.py (Plan 07-04 — the `_make_synthetic_multiindex_panel` + `_install_pipeline_mocks` + `_setup_settings` helpers; this test reuses the same monkeypatch idiom)
  </read_first>
  <behavior>
    - test_journal_cli_idempotent: setup an empty SQLite at tmp_path, write a real data/snapshots/{today}.parquet that the CLI can read, invoke `screener journal` twice
    - Assert exit_code == 0 on both invocations
    - Assert the journal SQLite file exists after first invocation
    - Assert row count after first invocation == 1 (or more, depending on snapshot rows)
    - Assert row count after second invocation == row count after first (idempotent — INSERT OR IGNORE skipped duplicates)
    - Assert structlog events: first invocation emits `journal_catchup_complete` with n_inserted > 0; second invocation emits `journal_catchup_complete` with n_inserted == 0 AND n_idempotent_skip == n_attempted
  </behavior>
  <action>
**Replace the `test_journal_cli_idempotent` pytest.skip body in tests/test_journal.py** with a real implementation. Locate the existing skeleton (it currently reads `pytest.skip("Plan 07-05")`) and REPLACE the function body:

```python
def test_journal_cli_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows."""
    import json as _json
    from datetime import date

    from typer.testing import CliRunner

    # 1. Configure tmp paths for journal DB + snapshots dir.
    db_path = tmp_path / "journal.sqlite"
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JOURNAL_DB_PATH", str(db_path))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    monkeypatch.setenv("JOURNAL_THRESHOLD", "50.0")
    monkeypatch.setenv("RISK_PCT", "0.01")
    monkeypatch.setenv("ACCOUNT_EQUITY", "100000")
    from screener.config import get_settings
    get_settings.cache_clear()

    # 2. Write a real snapshot parquet that _build_journal_rows_df_from_snapshot
    # can read. Mirror the RankingSnapshotSchema-projected shape (only columns
    # that exist in the schema + the new Phase 7 sizing cols).
    today_iso = date.today().isoformat()
    snap_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "rank": 1,
                "composite_score": 75.0,
                "composite_score_raw": 75.0,  # pre-gate raw composite (Plan 07-04 Pitfall 3)
                "rs_component": 0.92, "trend_component": 1.0,
                "volume_component": 0.7, "pattern_component": 0.7,
                "earnings_component": 0.5, "catalyst_component": 0.3,
                "passes_trend_template": True, "trend_template_score": 8,
                "rs_rating": 92, "dryup_ratio": 0.85,
                "pivot_distance_atr": 0.5,  # Phase 4 sign convention
                "pivot_zone": "in-zone",
                "regime_state": "Confirmed Uptrend", "regime_score": 0.85,
                "playbook_tag": "minervini_vcp",
                "qullamaggie_score": 0, "minervini_score": 1, "leader_hold_score": 0,
                "pattern_diagnostics": (
                    '{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08,'
                    '"depth_sequence":[0.25,0.15,0.08],"n_contractions":3,'
                    '"first_leg_depth":0.25,"breakout_vol_multiple":1.7,'
                    '"breakout_strength":0.85,"days_in_consolidation":18}'
                ),
                "breakout_strength": 0.85,
                "days_to_next_earnings": None,
                "crossed_52w_high_within_60d": False,
                "insider_cluster_buy": False,
                "earnings_in_3d_warn": False,
                "eps_knowable_from": None,
                # Phase 7 sizing cols (Plan 07-04 step 5.5 populates these in the
                # live pipeline; here we mimic that for the catch-up path).
                "stop_price": 161.46, "entry_price": 180.0, "shares": 50,
                "risk_per_share": 18.54, "atr_zone": "in-zone",
                "pivot_distance_atr_breakout": 0.25,
                "trail_rule_label": "21d EMA (then 50d SMA after 15 bars)",
                # Phase 7 revision iter 1: adr_rejected + rejection_reason are real
                # snapshot columns (Plan 07-01 revised). Catch-up helper reads
                # adr_rejected directly — Warning #6 single-source-of-truth.
                "adr_rejected": False, "rejection_reason": "",
            },
        ]
    )
    snap_df.to_parquet(snap_dir / f"{today_iso}.parquet", index=False)

    # 3. First invocation — inserts 1 row.
    from screener.cli import app
    runner = CliRunner()
    result1 = runner.invoke(app, ["journal"])
    assert result1.exit_code == 0, f"first invoke failed: {result1.stdout}"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        count_after_first = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    assert count_after_first == 1, f"expected 1 row after first invoke, got {count_after_first}"

    # 4. Second invocation — INSERT OR IGNORE → zero inserts.
    result2 = runner.invoke(app, ["journal"])
    assert result2.exit_code == 0, f"second invoke failed: {result2.stdout}"
    with sqlite3.connect(db_path) as conn:
        count_after_second = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    assert count_after_second == count_after_first, (
        f"idempotency violated: {count_after_first} → {count_after_second}"
    )

    # 5. Structlog events sanity: second invocation should report
    # n_idempotent_skip == n_attempted (everything was a duplicate).
    events2 = [
        _json.loads(line) for line in result2.stdout.splitlines()
        if line.strip().startswith("{")
    ]
    catchup_events = [
        ev for ev in events2 if ev.get("event") == "journal_catchup_complete"
    ]
    assert catchup_events, f"expected journal_catchup_complete event; got events: {events2!r}"
    ev = catchup_events[-1]
    assert ev["n_inserted"] == 0, f"expected n_inserted=0; got {ev!r}"
    assert ev["n_idempotent_skip"] == ev["n_attempted"], f"expected full skip; got {ev!r}"
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_journal.py --no-cov -q 2>&1 | tail -3 | grep -E "10 passed"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "pytest\.skip" tests/test_journal.py` outputs `0` (all 10 tests now have real bodies)
    - `grep -c "^def test_" tests/test_journal.py` outputs `10`
    - `uv run pytest tests/test_journal.py --no-cov -q 2>&1 | tail -3` shows `10 passed` (zero skips, zero failures)
    - `uv run pytest tests/test_journal.py::test_journal_cli_idempotent -x --no-cov -q` passes
    - `uv run pytest tests/test_journal.py::test_idempotent_append -x --no-cov -q` STILL passes (regression check from Plan 07-03)
    - `uv run pytest tests/test_pipeline_journal.py --no-cov -q` passes (Plan 07-04 integration tests intact)
    - `uv run pytest tests/test_sizing.py --no-cov -q` passes (Plan 07-02 unit tests intact)
    - `uv run pytest tests/test_cli_smoke.py --no-cov -q` passes (Plan 07-05 Task 1 changes intact)
    - `uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q` passes (FND-04 mutation gate green)
    - `uv run pytest tests/test_architecture.py --no-cov -q` passes (D-23 unchanged)
  </acceptance_criteria>
  <done>
    test_journal_cli_idempotent has a real body. All 10 tests in test_journal.py pass. Idempotency proven via two-invocation pattern (RESEARCH §Code Examples Pattern 4 idiom applied to the CLI surface).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human verification — Phase 7 end-to-end smoke test</name>
  <what-built>
    Phase 7 complete. The full pipeline now supports:
    1. `screener score` writes data/snapshots/YYYY-MM-DD.parquet WITH the 7 new Phase 7 sizing columns AND appends actionable picks to data/journal.sqlite (composite_score_raw >= JOURNAL_THRESHOLD AND regime != Correction).
    2. `screener report` does the same PLUS writes reports/YYYY-MM-DD.md with the new Entry/Stop/Trail/Shares/Zone per-pick fields AND a `## Skipped Picks` footer section for any 1×ADR-rejected picks.
    3. `screener journal` performs idempotent catch-up: reads today's snapshot, re-builds journal rows, INSERT OR IGNORE'd into picks table. Safe to run multiple times.
    4. `data/journal.sqlite` is now git-tracked (per RESEARCH A4 — paper-trade history IS the v1.x performance contract).
    5. The 9-subcommand CLI surface (D-24) is UNCHANGED — `journal` filled its existing body; no 10th subcommand was added.
  </what-built>
  <how-to-verify>
    Run the full Phase 7 verification suite in a single command:
    ```bash
    uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py tests/test_publishers_pipeline.py tests/test_publishers_report.py tests/test_cli_smoke.py tests/test_architecture.py tests/test_backtest_no_lookahead.py tests/test_insider_io.py --no-cov -q
    ```
    Expected output:
    - All tests pass (no failures, no errors).
    - 10 tests in test_journal.py pass (Plan 07-03 9 + Plan 07-05 1 deferred).
    - 11 tests in test_sizing.py pass (Plan 07-02).
    - 4 tests in test_pipeline_journal.py pass (Plan 07-04).
    - All existing Phase 4/5/6 tests still green.
    - FND-04 no-look-ahead gate green.

    Then verify the SQLite file is git-trackable:
    ```bash
    git check-ignore data/journal.sqlite
    ```
    Expected: command returns NON-zero exit code (file is NOT ignored — the `!/data/journal.sqlite` allowlist is working).

    Then verify the CLI surface is locked:
    ```bash
    uv run screener --help | grep -E "^\s+(refresh-universe|refresh-ohlcv|refresh-macro|refresh-fundamentals|score|report|journal|backtest|backtest-audit)" | wc -l
    ```
    Expected: `9` (exactly 9 subcommands).

    Then verify the journal command body works end-to-end:
    ```bash
    # In a freshly cloned / clean repo (or after `git clean`):
    uv run screener journal 2>&1 | head -5
    ```
    Expected: structured JSON log emit with event=`journal_catchup_snapshot_missing` (today's snapshot doesn't exist) OR `journal_catchup_empty` — NOT `[stub] journal not yet implemented`. Exit code 0.

    Optionally, run a real `screener score` if there's recent OHLCV cache:
    ```bash
    uv run screener score
    ls -la data/journal.sqlite
    sqlite3 data/journal.sqlite "SELECT ticker, composite_score, playbook_tag, shares FROM picks ORDER BY composite_score DESC LIMIT 5;"
    ```
    Expected: a few rows visible with realistic tickers, composite scores in 50-100 range, playbook_tag in the locked enum, and shares > 0.
  </how-to-verify>
  <resume-signal>Type "approved" if all checks pass, or paste failing output to triage</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| typer CLI args (none) → journal body | journal command takes no args; the `today` date comes from system clock |
| system clock → snapshot filename → file system | `date.today().isoformat()` produces a YYYY-MM-DD string that becomes a Parquet filename; path traversal not possible (no user input) |
| stub-removal → CI surface lock | PHASE_1_STUBS list shrinks; D14_SUBCOMMANDS list MUST remain bytewise unchanged |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-22 | Spoofing | system clock manipulation → wrong snapshot date | accept | Same risk applies to every other date-based CLI command (score, report, backtest); no new attack surface introduced. The user-controlled system clock is the established trust boundary. |
| T-07-23 | Tampering | manual edits to data/snapshots/YYYY-MM-DD.parquet between snapshot write and journal append | mitigate | PicksSchema validates the rebuilt journal rows; pandera errors fail-loud. The catch-up path is strictly additive (INSERT OR IGNORE) so existing rows are never overwritten even if the snapshot is tampered with. |
| T-07-24 | Information disclosure | `result.stdout` in tests captures structlog JSON | accept | Test fixtures use synthetic ticker symbols (AAPL/MSFT/NVDA — public). No real account equity (test sets ACCOUNT_EQUITY=100000 paper default). No secrets in log payloads (T-3-02 enforcement at exception level). |
| T-07-25 | Repudiation | journal_failed event vs typer.Exit propagation | mitigate | typer.Exit propagates so process exit code reflects the failure. The `journal_failed` event with error_type-only logging provides forensic data without leaking exception strings (which could contain file paths or other sensitive fragments per the T-3-02 pattern). Tested implicitly by the existing PHASE_1_STUBS no-stub-emission assertion in test_journal_subcommand_no_longer_stub. |
| T-07-26 | Elevation of privilege | D-24 surface lock bypass — adding `journal-update` subcommand | accept | OUT-06 deferred per CONTEXT D-10; v1.x explicitly ships `scripts/journal_update.py` (NOT a typer subcommand) for the outcome-update flow. The 9-subcommand surface is bytewise locked. Tested via test_subcommand_surface_locked (unchanged from Phase 1/4/6). |

ASVS L1 applicable: V12.3.1 (file path traversal — system-generated date string can't traverse), V13.1.4 (PicksSchema at write boundary). No high-risk threats.
</threat_model>

<verification>
```bash
# Phase 7 Plan 05 + full-phase verification suite (~30s)
uv run pytest tests/test_cli_smoke.py --no-cov -q                # All CLI smoke tests + new test_journal_subcommand_no_longer_stub
uv run pytest tests/test_journal.py --no-cov -q                  # 10 passed (was 9 + 1 skipped)
uv run pytest tests/test_pipeline_journal.py --no-cov -q         # 4 passed (Plan 07-04)
uv run pytest tests/test_sizing.py --no-cov -q                   # 11 passed (Plan 07-02)
uv run pytest tests/test_publishers_pipeline.py --no-cov -q      # Phase 6 + Plan 07-04 additions
uv run pytest tests/test_publishers_report.py --no-cov -q        # Phase 4/5/6 + Plan 07-04 Task 2
uv run pytest tests/test_architecture.py --no-cov -q             # D-23 (with sizing → indicators Plan 07-02 extension)
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q    # FND-04 mutation gate
uv run pytest tests/test_insider_io.py --no-cov -q               # Phase 6 SQLite regression check

# Full suite (Phase 7 phase gate)
uv run pytest --no-cov -q

# Structural locks
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q
uv run pytest tests/test_architecture.py::test_layer_import_contract --no-cov -q  # or equivalent test name
```
</verification>

<success_criteria>
- src/screener/cli.py `journal` command has a real body (no _stub call); uses the cli.score try/except idiom (Pitfall 7 typer.Exit propagation + T-3-02 error_type-only logging).
- src/screener/cli.py imports PicksSchema, append_picks_rows, validate_at_write, _build_journal_rows_df_from_snapshot.
- tests/test_cli_smoke.py PHASE_1_STUBS list is empty (only comments remain).
- tests/test_cli_smoke.py has new test_journal_subcommand_no_longer_stub function placed before test_subcommand_surface_locked.
- D14_SUBCOMMANDS list and test_subcommand_surface_locked are byte-identical (D-24 9-subcommand lock).
- tests/test_journal.py test_journal_cli_idempotent has a real body invoking `screener journal` twice and asserting idempotency.
- All 10 tests in tests/test_journal.py pass (no remaining pytest.skip).
- All 4 tests in tests/test_pipeline_journal.py pass.
- All 11 tests in tests/test_sizing.py pass.
- FND-04 no-look-ahead mutation gate green.
- D-23 architecture ALLOWED dict permits sizing → indicators (set in Plan 07-02), unchanged in Plan 07-05.
- D-24 9-subcommand CLI surface locked and verified.
- Human checkpoint Task 3: developer runs the smoke suite + sqlite query and confirms end-to-end behavior.
- Phase 7 SUCCESS CRITERIA from ROADMAP all satisfied:
  - SC-1 (shares formula + 25% cap + 1×ADR reject) — Plan 07-02
  - SC-2 (per-playbook stop dispatch unit test) — Plan 07-02 + STOP_HELPERS identity check
  - SC-3 (distance-from-pivot ATR + 3-bucket annotation) — Plan 07-02 + Plan 07-04 report layer
  - SC-4 (every actionable pick appended at publish time) — Plan 07-04 + Plan 07-05
  - SC-5 (features_json blob with full snapshot) — Plan 07-04 _build_journal_rows_df
  - SC-6 (nullable outcome columns) — Plan 07-03 schema
</success_criteria>

<output>
After completion, create `.planning/phases/07-sizing-finalization-paper-trade-journal/07-05-SUMMARY.md` per the standard template. Also update STATE.md to mark Phase 7 as complete (5/5 plans) and Phase 8 as the next phase.
</output>
