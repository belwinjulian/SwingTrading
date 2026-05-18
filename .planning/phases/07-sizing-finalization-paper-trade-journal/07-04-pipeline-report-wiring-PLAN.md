---
phase: 07-sizing-finalization-paper-trade-journal
plan: "04"
type: execute
wave: 2
depends_on: ["07-02", "07-03"]
files_modified:
  - src/screener/publishers/pipeline.py
  - src/screener/publishers/report.py
  - tests/test_pipeline_journal.py
  - tests/test_publishers_pipeline.py
  - tests/test_publishers_report.py
autonomous: true
requirements: [SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05, OUT-04, OUT-05]
requirements_addressed: [SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05, OUT-04, OUT-05]
tags: [phase-7, pipeline-wiring, report-rendering, sizing-injection, journal-append, skipped-picks-footer]

must_haves:
  truths:
    - "publishers/pipeline.run_pipeline signature gains write_journal: bool = True (CONTEXT D-01)"
    - "Sizing step injected between apply_regime_gate (step 5) and _add_publisher_columns (step 7) per RESEARCH §Pattern 4"
    - "compute_sizing runs on the FULL cross-section (every ticker, ~1000 rows) — does NOT filter or mutate the frame; rows with playbook_tag='none' (~95% of universe) naturally carry adr_rejected=True via the existing STOP_HELPERS.get(tag)=None → invalid_stop path (revision iteration 1 Blocker #1)"
    - "today_panel (the FULL frame, post-sizing) is what flows to validate_run, _add_publisher_columns, and write_snapshot — preserves OUT-03 (full ranked universe in snapshot) and Phase 5 backtest input contract"
    - "validate_run + pass_rate run against the FULL post-sizing frame BEFORE any actionable-pick derivation; pass_rate = today_panel['passes_trend_template'].mean() preserves D-07/D-08 gate semantics on the full universe (revision iteration 1 Blocker #3)"
    - "actionable_picks is a DERIVED VIEW (today_panel[(~adr_rejected) & (composite_score_raw >= JOURNAL_THRESHOLD) & (playbook_tag in {qullamaggie_continuation, minervini_vcp, leader_hold})]) used ONLY by the report top-N rendering and the journal append — NEVER assigned back to today_panel"
    - "Journal append (step 8.5) fires after write_snapshot when write_journal=True; emits journal_append_summary event"
    - "_build_journal_rows_df(actionable_view, regime_row, snapshot_date, settings) builds a DataFrame validated by PicksSchema BEFORE persistence.append_picks_rows"
    - "composite_score_raw is captured BEFORE apply_regime_gate AND lives as a real column on the snapshot — used by BOTH live + catch-up flows for the actionable threshold (revision iteration 1 Warning #6: no per-flow divergence)"
    - "features_json embeds: 13 score-component keys + 9 indicator values + 8 sizing-input keys + full pattern_diagnostics dict + features_json_version='v1.0'"
    - "_build_journal_rows_df_from_snapshot(snapshot_date) factored as a private module function in publishers/pipeline.py so cli.journal (Plan 07-05) reuses it; reads composite_score_raw directly from the snapshot column (no per-flow divergence)"
    - "publishers/report.render_report per-pick block gains Entry / Stop / Trail / Shares / Zone lines (CONTEXT <specifics>)"
    - "publishers/report.render_report adds ## Skipped Picks section AFTER per-pick blocks and BEFORE ## Data Quality footer when skipped_view is non-empty"
    - "render_report and write_report gain `skipped_picks: pd.DataFrame | None = None` kwarg (default None preserves backwards compat)"
    - "All 4 tests in tests/test_pipeline_journal.py pass — including a snapshot-row-count regression assertion (revision iteration 1 Warning #10) that locks Blocker #1 in place"
    - "Existing tests/test_publishers_pipeline.py and tests/test_publishers_report.py keep their original counts AND pass (regression-safe edits only — add tests, do not remove)"
  artifacts:
    - path: "src/screener/publishers/pipeline.py"
      provides: "run_pipeline(write_journal=True) + sizing step 5.5 (FULL frame) + journal append step 8.5 + _build_journal_rows_df + _build_journal_rows_df_from_snapshot"
      contains: "compute_sizing"
    - path: "src/screener/publishers/report.py"
      provides: "render_report with sizing per-pick block + ## Skipped Picks footer; write_report passes skipped_picks through"
      contains: "## Skipped Picks"
    - path: "tests/test_pipeline_journal.py"
      provides: "4 real test bodies (replaces Plan 07-01 skeletons)"
      contains: "test_pipeline_writes_journal"
  key_links:
    - from: "publishers/pipeline.run_pipeline"
      to: "screener.sizing.compute_sizing"
      via: "from screener.sizing import compute_sizing"
      pattern: "compute_sizing\\("
    - from: "publishers/pipeline.run_pipeline"
      to: "screener.persistence.append_picks_rows"
      via: "from screener.persistence import PicksSchema, append_picks_rows, validate_at_write"
      pattern: "append_picks_rows\\("
    - from: "publishers/report.render_report"
      to: "render report markdown"
      via: "skipped_picks kwarg → ## Skipped Picks section"
      pattern: "## Skipped Picks"

user_setup: []
---

<objective>
Wave 2 integration: extend `publishers/pipeline.run_pipeline` to call `sizing.compute_sizing()` on the FULL cross-section (revision iteration 1 Blocker #1 — do NOT filter `today_panel` by `adr_rejected` before snapshot write), inject the journal append step after snapshot write (CONTEXT D-01), factor `_build_journal_rows_df` and `_build_journal_rows_df_from_snapshot` private helpers so cli.journal can reuse the second one (Plan 07-05). Extend `publishers/report.render_report` with sizing per-pick block (Entry / Stop / Trail / Shares / Zone — CONTEXT <specifics>) and the `## Skipped Picks` footer section (D-06 rejection surface). Land real bodies in all 4 tests/test_pipeline_journal.py skeletons.

**Revision iteration 1 — root-cause fix for all 4 BLOCKERS (one structural change resolves all):**
1. **Blocker #1 — snapshot truncation:** Sizing runs on the FULL cross-section; the snapshot writer receives the FULL frame (~1000 rows). The actionable-pick filter is a DERIVED VIEW used only by the report top-N rendering and the journal-append helper — never assigned back to `today_panel`. This preserves Phase 4 OUT-03 (full ranked universe in snapshot) and the Phase 5 backtest reader `vbt_runner._read_snapshot`.
2. **Blocker #2 — schema nullability:** Already fixed in Plan 07-01 (revised): all Phase 7 sizing cols are `nullable=True` and `atr_zone` accepts a `"not_applicable"` sentinel. This plan must populate `atr_zone="not_applicable"` (NOT NaN) for rows where playbook_tag='none' so the isin enum still validates.
3. **Blocker #3 — pass_rate / validate_run semantics:** `pass_rate = today_panel["passes_trend_template"].mean()` runs against the FULL post-sizing frame (sizing adds columns but does NOT filter rows, so the universe count is preserved). validate_run executes BEFORE any actionable-view derivation. D-07/D-08 gate semantics are preserved on the full universe.
4. **Blocker #4 — integration test stubbing:** Tests do NOT use `try/except AttributeError` around monkeypatches (Phase 7 already depends on Phase 6 — fail loud if symbols missing). Tests do NOT stub `write_snapshot` — let pandera validate the real frame so future schema breaks surface immediately. Temp data dir keeps the write safe.

**Revision iteration 1 — Warnings addressed:**
- **#5:** `pivot_distance_atr` → `pivot_distance_atr_breakout` rename in INSERT row builder (matches Plan 07-03 revised schema column name).
- **#6:** Both live AND catch-up flows use `composite_score_raw >= JOURNAL_THRESHOLD` (no per-flow divergence). The catch-up helper reads `composite_score_raw` directly from the snapshot column.
- **#10:** New regression assertion in test_pipeline_journal.py: `len(snapshot_df_written) == len(today_panel_pre_sizing)`. Locks Blocker #1 in place.
- **#11:** Scope check — revisions tighten the plan (one structural shift, no new tasks). Plan stays as 07-04 (no split).

Purpose: This is the integration that turns Wave 1's sizing.py + persistence journal layer into a working pipeline. After this plan, `screener report` produces a markdown report with concrete trade plans AND `data/journal.sqlite` accumulates one row per actionable pick per day, while the snapshot Parquet retains the FULL universe for Phase 5 backtest reproduction.

Output: Modified pipeline.py (~80 lines added), modified report.py (~50 lines added), 4 passing integration tests, ZERO regressions in existing pipeline / report tests.
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
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-01-foundation-settings-schemas-fixtures-PLAN.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-02-sizing-module-PLAN.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-03-journal-persistence-PLAN.md
@.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-05-SUMMARY.md
@CLAUDE.md
@src/screener/publishers/pipeline.py
@src/screener/publishers/report.py

<interfaces>
<!-- Key types and contracts extracted from the codebase. -->

Existing publishers/pipeline.run_pipeline (lines 116-193) — current 9-step DAG:
```python
def run_pipeline(snapshot_date: str, write_report: bool = True) -> None:
    settings = get_settings()
    panel = build_panel(snapshot_date)
    panel = passes_trend_template(panel)
    panel = score(panel, DEFAULT_WEIGHTS)
    # Phase 6 (Plan 06-05) adds:
    #   panel = passes_qullamaggie_setup_a(panel)
    #   fundamentals = persistence.read_fundamentals(snap_ts)  # D-13b lag applied here
    #   panel = canslim_c_overlay(panel, fundamentals, snap_ts)
    #   panel = _add_catalyst_columns(panel, fundamentals, snap_ts)
    #   panel = tag_playbook(panel)
    snap_ts = pd.Timestamp(snapshot_date)
    today_panel = panel.xs(snap_ts, level="date")
    regime_row = compute_for_date(snap_ts, panel)
    regime_score_value = float(regime_row["regime_score"])
    regime_state_value = str(regime_row["regime_state"])
    today_panel = apply_regime_gate(today_panel, regime_score_value)  # composite_score *= regime_score
    pass_rate = float(today_panel["passes_trend_template"].mean())
    validate_run(pass_rate, regime_state_value, ...)
    # Phase 6 Plan 06-05 W-Plan05-1 projection:
    today_panel = _add_publisher_columns(today_panel, regime_row)
    snapshot_cols = [c for c in RankingSnapshotSchema.to_schema().columns if c in today_panel.columns]
    snapshot_df = today_panel[snapshot_cols]
    write_snapshot(snapshot_df, snapshot_date)  # NOT today_panel — projected
    # Phase 6 step 10: write_pattern_audit_atomic
    if write_report:
        write_report_md(today_panel, regime_row, snapshot_date, top_n=..., pass_rate=...)
    log.info("pipeline_complete", ...)
```

Existing apply_regime_gate (publishers/pipeline.py, line 40) — Phase 4 D-03:
- Mutates composite_score in place: `composite_score *= regime_score` on the cross-section.
- This means the **post-gate** composite_score is what reaches sizing and downstream steps.
- For PRE-gate semantics in the journal threshold (RESEARCH Pitfall 3), Plan 07-04 must:
  - **Chosen approach:** capture `composite_score_raw` BEFORE apply_regime_gate (preserves the existing soft-gate ranking semantics that already drive _add_publisher_columns); composite_score_raw is also added to the snapshot schema (Plan 07-01 revised) so the catch-up flow reads it directly.

Existing render_report (publishers/report.py, line 200+) — Phase 6 D-19 format:
- Per-pick block at lines 286-307 (the loop): emits ticker headline, score breakdown via `_format_breakdown(row)`, Pivot zone line, Playbook line, Catalysts line.
- Phase 6 Plan 06-05 added a "Currently Held / Leaders" section AND modified to filter playbook_tag in {qullamaggie_continuation, minervini_vcp} → top-N; playbook_tag == leader_hold → separate section.
- Data Quality footer at lines 312-334.

Existing write_report (publishers/report.py): wraps render_report with `_write_text_atomic`. Both functions need new `skipped_picks` kwarg with default None.

screener.sizing (from Plan 07-02):
- `compute_sizing(cross, panel, account_equity, risk_pct, regime_score) -> pd.DataFrame`
- Returns cross + 9 new cols including: stop_price, entry_price, shares, risk_per_share, atr_zone, pivot_distance_atr_breakout, trail_rule_label, adr_rejected (bool), rejection_reason (str)
- Rows with playbook_tag NOT in STOP_HELPERS (e.g. 'none') get `STOP_HELPERS.get(tag)=None` → stop=close → risk=0 → rejection='invalid_stop' → adr_rejected=True. The function does NOT raise; it gracefully marks those rows as rejected.

screener.persistence (from Plan 07-03 revised):
- `PicksSchema` — 13-field pandera schema; column is `pivot_distance_atr_breakout` (renamed in revision iteration 1)
- `append_picks_rows(rows: list[dict], db_path=None) -> int` — INSERT OR IGNORE; returns rowcount
- `read_picks_for_date(snapshot_date: str, db_path=None) -> pd.DataFrame`
- `validate_at_write(schema_cls, df) -> pd.DataFrame` — eager pandera validation (already exists at line 356)

Snapshot path resolver (already in persistence.py):
- `_snapshot_dir() -> Path` returning the snapshots dir from Settings; or compute manually `Path(get_settings().SNAPSHOT_DIR) / f"{snapshot_date}.parquet"` if that helper isn't named that way.

Phase 6 architecture note (06-05-SUMMARY decision 1): publishers/report.py uses inline `_decode_diag()` rather than importing indicators.patterns. This is structural — publishers/ MUST NOT import indicators/ per ALLOWED dict. Plan 07-04's report changes must NOT add any indicators imports.

ALLOWED dict (tests/test_architecture.py:36 — line as-of-Phase-6):
```python
"publishers": {"signals", "sizing", "regime", "persistence", "config", "obs"},
```
Already permits both sizing and persistence. Plan 07-04 needs ZERO ALLOWED-dict changes.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend publishers/pipeline.py with FULL-frame sizing injection + actionable-view derivation + journal append + _build_journal_rows_df helpers</name>
  <files>src/screener/publishers/pipeline.py</files>
  <read_first>
    - src/screener/publishers/pipeline.py (full file — current run_pipeline at lines 116-193 + Phase 6 Plan 06-05 additions)
    - src/screener/sizing.py (Plan 07-02 — compute_sizing signature and the 9 output columns)
    - src/screener/persistence.py (Plan 07-03 revised — PicksSchema with `pivot_distance_atr_breakout`, append_picks_rows, read_picks_for_date, validate_at_write)
    - src/screener/persistence.py RankingSnapshotSchema (Plan 07-01 revised — `composite_score_raw`, `adr_rejected`, `rejection_reason`, all 7 sizing cols nullable=True, `atr_zone` accepts `"not_applicable"`)
    - src/screener/signals/composite.py:261 (the `playbook_tag = "none"` default branch — explains why FULL-frame sizing is required)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Architecture Patterns" Pattern 4 (pipeline integration seam — verbatim)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Common Pitfalls" 3 (pre-gate composite threshold)
    - .planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-05-SUMMARY.md (W-Plan05-1 projection idiom — Plan 07-04 must preserve it AND apply it to the FULL post-sizing frame)
  </read_first>
  <behavior>
    - run_pipeline signature: `run_pipeline(snapshot_date: str, write_report: bool = True, write_journal: bool = True) -> None`
    - composite_score_raw captured BEFORE apply_regime_gate (for D-01 threshold check + Pitfall 3 + Warning #6 single-source-of-truth)
    - Sizing step injected AFTER apply_regime_gate: `today_panel = compute_sizing(today_panel, panel, account_equity=settings.ACCOUNT_EQUITY, risk_pct=settings.RISK_PCT, regime_score=regime_score_value)`
    - **FULL-FRAME PRESERVATION (Blocker #1):** `today_panel` is NEVER filtered or split after sizing. The full ~1000-row frame flows to validate_run, _add_publisher_columns, snapshot projection, and write_snapshot.
    - **atr_zone sentinel patch (Blocker #2 followup):** Immediately after compute_sizing, replace NaN atr_zone values (rows with no breakout pivot) with the string `"not_applicable"` so the snapshot schema's `isin` enum validates. Same for rejected rows where atr_zone was computed but should be sentinel-marked when playbook_tag='none' (use `atr_zone.fillna('not_applicable')` plus `.where(playbook_tag.isin(VALID_PLAYBOOK_TAGS), 'not_applicable')`).
    - **validate_run runs on the FULL post-sizing frame (Blocker #3):** `pass_rate = float(today_panel["passes_trend_template"].mean())` — full universe pass rate, NOT actionable-only. Sizing adds columns but does NOT remove rows, so pass_rate semantics are identical to Phase 4.
    - **Actionable view (Blocker #1 derivative):** Build `actionable_view = today_panel[(~today_panel["adr_rejected"]) & (today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD) & (today_panel["playbook_tag"].isin(["qullamaggie_continuation", "minervini_vcp", "leader_hold"]))]` AFTER validate_run + snapshot write. This view is consumed by the report top-N renderer AND the journal-append helper. The view is NEVER assigned back to `today_panel`.
    - **Skipped view (for report footer):** Build `skipped_view = today_panel[today_panel["adr_rejected"] & today_panel["playbook_tag"].isin(["qullamaggie_continuation", "minervini_vcp", "leader_hold"])].copy()` — only rejected rows that WOULD have been actionable. Excludes the ~95% playbook_tag='none' rows from the skipped section (they were never candidates).
    - When write_journal=True: build journal rows DataFrame via `_build_journal_rows_df(actionable_view, ...)`, validate via `validate_at_write(PicksSchema, ...)`, call `append_picks_rows(records)`, log `journal_append_summary` event
    - When write_journal=False: log `journal_skipped` event with snapshot_date and reason
    - When write_report=True: pass `skipped_picks=skipped_view` to `write_report_md`
    - _build_journal_rows_df filters rows where `composite_score_raw >= settings.JOURNAL_THRESHOLD AND regime_state != 'Correction' AND playbook_tag in VALID_PLAYBOOK_TAGS` (D-01 + Pitfall 3 + Warning #6)
    - _build_journal_rows_df_from_snapshot reads `data/snapshots/{snapshot_date}.parquet` via pd.read_parquet, then applies the SAME `composite_score_raw >= threshold` filter (Warning #6 — no per-flow divergence) by reading the `composite_score_raw` column directly from the snapshot
    - INSERT row builder uses `pivot_distance_atr_breakout` as the dict key (Warning #5 rename in Plan 07-03)
  </behavior>
  <action>
**A. Modify `run_pipeline` in `src/screener/publishers/pipeline.py`** (do NOT rewrite the file — make targeted edits):

1. **Add `write_journal: bool = True` parameter** to `run_pipeline`. Update the docstring to mention CONTEXT D-01 and the FULL-frame snapshot contract (revision iteration 1 Blocker #1).

2. **Capture pre-gate composite score** — BEFORE `today_panel = apply_regime_gate(...)`, add:
```python
    # Phase 7 D-01 / Pitfall 3 / Warning #6 (revision iter 1): capture the
    # PRE-gate raw composite_score so the journal threshold doesn't shift with
    # the regime (D-03 soft-gate would otherwise systematically under-sample
    # mid-quality picks during pressure regimes). composite_score_raw is also
    # added to RankingSnapshotSchema (Plan 07-01 revised) and feeds BOTH the
    # live actionable-view derivation AND the catch-up helper in cli.journal —
    # single source of truth, no per-flow divergence (Warning #6).
    today_panel = today_panel.assign(composite_score_raw=today_panel["composite_score"])
```

3. **Inject Phase 7 step 5.5 — sizing on the FULL cross-section** — between `apply_regime_gate(...)` and `pass_rate = ...`:

```python

    # === Phase 7 step 5.5: SIZ-01..05 dispatch (CONTEXT D-04) ===
    # === REVISION ITERATION 1 BLOCKER #1: FULL-FRAME SIZING ===
    # compute_sizing runs on the FULL cross-section. Rows with playbook_tag NOT
    # in STOP_HELPERS (~95% of universe per signals/composite.py:261 default
    # branch) gracefully land with adr_rejected=True / rejection_reason=
    # 'invalid_stop' / NaN-able sizing columns. The snapshot writer (step 8
    # below) receives this FULL frame — preserving OUT-03 (full ranked universe
    # in snapshot) and the Phase 5 backtest reader contract.
    # The actionable-pick filter is a DERIVED VIEW (built AFTER snapshot write)
    # used ONLY by the report renderer + journal-append helper. NEVER assigned
    # back to today_panel.
    from screener.sizing import compute_sizing

    today_panel = compute_sizing(
        today_panel,
        panel,
        account_equity=settings.ACCOUNT_EQUITY,
        risk_pct=settings.RISK_PCT,
        regime_score=regime_score_value,
    )

    # Sentinel patch for atr_zone (Blocker #2 followup): the snapshot schema
    # accepts "not_applicable" for rows where playbook_tag='none' or no breakout
    # pivot exists. compute_sizing emits real zone labels for actionable rows;
    # for non-actionable rows we replace with the sentinel so the isin enum on
    # RankingSnapshotSchema.atr_zone validates at write time.
    _valid_playbook_tags = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    _is_actionable_tag = today_panel["playbook_tag"].isin(_valid_playbook_tags)
    today_panel["atr_zone"] = today_panel["atr_zone"].where(
        _is_actionable_tag & ~today_panel["adr_rejected"], "not_applicable"
    )

    log.info(
        "sizing_pipeline_full_frame",
        snapshot_date=snapshot_date,
        n_universe=len(today_panel),
        n_rejected=int(today_panel["adr_rejected"].sum()),
        n_actionable_tag=int(_is_actionable_tag.sum()),
    )
    # === END Phase 7 step 5.5 ===
```

4. **Preserve validate_run on the FULL frame (Blocker #3):** the existing `pass_rate = float(today_panel["passes_trend_template"].mean())` and `validate_run(...)` lines run AS-IS on the FULL post-sizing frame. Sizing added columns but did NOT remove rows, so the pass-rate calculation is identical to Phase 4/6. DO NOT modify those lines. DO NOT comment them. DO NOT introduce any actionable-only pass_rate variant.

5. **W-Plan05-1 projection preserved + write_snapshot on FULL frame:** The existing W-Plan05-1 projection runs on `today_panel` (the FULL post-sizing frame). Because Plan 07-01 (revised) extended RankingSnapshotSchema with 10 new nullable columns (7 sizing + composite_score_raw + adr_rejected + rejection_reason), the projection automatically picks them up. write_snapshot receives ~1000 rows, NOT a filtered subset.

6. **Inject Phase 7 step 8.5 — actionable view derivation + journal append** — AFTER `write_snapshot(snapshot_df, snapshot_date)` and BEFORE the `if write_report:` block:

```python

    # === Phase 7 step 8.5: actionable view + journal append (D-01 / OUT-04) ===
    # The actionable view is a DERIVED frame: today_panel filtered by
    # ~adr_rejected & composite_score_raw >= JOURNAL_THRESHOLD & playbook_tag
    # in VALID_PLAYBOOK_TAGS. It is consumed by the report renderer AND the
    # journal-append helper. Never assigned back to today_panel (Blocker #1).
    actionable_view = today_panel[
        (~today_panel["adr_rejected"])
        & (today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD)
        & (today_panel["playbook_tag"].isin(_valid_playbook_tags))
    ]
    # Skipped view = rows that WOULD have been actionable but were rejected by
    # sizing (1xADR fail / invalid stop / missing diagnostics). Excludes the
    # ~95% playbook_tag='none' rows (they were never candidates).
    skipped_view = today_panel[
        today_panel["adr_rejected"]
        & today_panel["playbook_tag"].isin(_valid_playbook_tags)
    ].copy()

    if write_journal:
        from screener.persistence import (
            PicksSchema,
            append_picks_rows,
            validate_at_write,
        )

        journal_rows_df = _build_journal_rows_df(
            actionable_view, regime_row, snapshot_date, settings,
        )
        if not journal_rows_df.empty:
            validated = validate_at_write(PicksSchema, journal_rows_df)
            n_inserted = append_picks_rows(validated.to_dict(orient="records"))
            log.info(
                "journal_append_summary",
                snapshot_date=snapshot_date,
                n_attempted=len(validated),
                n_inserted=n_inserted,
                n_idempotent_skip=len(validated) - n_inserted,
            )
        else:
            log.info(
                "journal_append_summary",
                snapshot_date=snapshot_date,
                n_attempted=0, n_inserted=0, n_idempotent_skip=0,
                reason="no_actionable_picks_above_threshold",
            )
    else:
        log.info("journal_skipped", snapshot_date=snapshot_date, reason="write_journal=False")
    # === END Phase 7 step 8.5 ===
```

7. **Pass `skipped_picks=skipped_view`** to `write_report_md` inside the `if write_report:` block (the report renderer also reads `actionable_view` if it needs to filter to top-N — but the current write_report_md signature takes the full panel and filters internally, so we pass the full panel + the skipped view; the renderer's existing internal top-N selection logic combined with Plan 07-04 Task 2's per-pick block changes will surface sizing fields only on rows that have them):

```python
        write_report_md(
            today_panel,
            regime_row,
            snapshot_date,
            top_n=settings.REPORT_TOP_N,
            pass_rate=pass_rate,
            skipped_picks=skipped_view,  # NEW Phase 7 kwarg
        )
```

**B. Append two new private helpers at module level** (after `apply_regime_gate` and `validate_run` — placement is anywhere in pipeline.py, but conventionally after the `run_pipeline` function):

```python


def _build_journal_rows_df(
    actionable_view: "pd.DataFrame",
    regime_row: "pd.Series",
    snapshot_date: str,
    settings: "Settings",
) -> "pd.DataFrame":
    """Build the PicksSchema-shaped DataFrame for journal append (CONTEXT D-01 / D-03).

    Input is the actionable VIEW (revision iteration 1 Blocker #1) — already
    pre-filtered upstream by ~adr_rejected & composite_score_raw >= threshold &
    valid playbook_tag. The only remaining filter here is regime_state !=
    'Correction' (CONTEXT D-01 actionable-pick gate).

    Returns an empty DataFrame (with PicksSchema columns) when no rows qualify.

    Warning #5 (revision iter 1): the INSERT row builder uses key
    `pivot_distance_atr_breakout` (matches Plan 07-03 revised PicksSchema
    column name).
    """
    import json as _json
    from datetime import datetime, timezone

    regime_state = str(regime_row["regime_state"])
    schema_cols = [
        "ticker", "snapshot_date", "playbook_tag", "composite_score",
        "regime_state", "entry_price", "stop_price", "shares",
        "risk_per_share", "atr_zone", "pivot_distance_atr_breakout",
        "features_json", "ingested_at",
    ]
    if regime_state == "Correction" or actionable_view.empty:
        return pd.DataFrame(columns=schema_cols)

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows = []
    for ticker, row in actionable_view.iterrows():
        # CONTEXT D-03 features_json: score components + indicators + sizing inputs + diagnostics.
        features = {
            "features_json_version": "v1.0",
            # Score components (Phase 4/6 composite layer).
            "rs_rating": _safe_int(row.get("rs_rating")),
            "trend_template_score": _safe_int(row.get("trend_template_score")),
            "pattern_component": _safe_float(row.get("pattern_component")),
            "volume_component": _safe_float(row.get("volume_component")),
            "earnings_component": _safe_float(row.get("earnings_component")),
            "catalyst_component": _safe_float(row.get("catalyst_component")),
            "composite_score": float(row["composite_score"]),
            "composite_score_raw": float(row.get("composite_score_raw", row["composite_score"])),
            "regime_score": float(row.get("regime_score", regime_row["regime_score"])),
            "regime_state": regime_state,
            "playbook_tag": str(row["playbook_tag"]),
            "qullamaggie_score": _safe_int(row.get("qullamaggie_score")),
            "minervini_score": _safe_int(row.get("minervini_score")),
            "leader_hold_score": _safe_int(row.get("leader_hold_score")),
            # Indicator values at signal time.
            "atr_14": _safe_float(row.get("atr_14")),
            "adr_pct": _safe_float(row.get("adr_pct")),
            "dryup_ratio": _safe_float(row.get("dryup_ratio")),
            "breakout_strength": _safe_float(row.get("breakout_strength")),
            "sma_50": _safe_float(row.get("sma_50")),
            "sma_150": _safe_float(row.get("sma_150")),
            "sma_200": _safe_float(row.get("sma_200")),
            "high_52w": _safe_float(row.get("high_52w")),
            "low_52w": _safe_float(row.get("low_52w")),
            # Sizing inputs.
            "entry_price": float(row["entry_price"]),
            "stop_price": float(row["stop_price"]),
            "shares": int(row["shares"]),
            "risk_per_share": float(row["risk_per_share"]),
            "atr_zone": str(row["atr_zone"]),
            "pivot_distance_atr": _safe_float(row.get("pivot_distance_atr")),  # Phase 4 col
            "pivot_distance_atr_breakout": _safe_float(row.get("pivot_distance_atr_breakout")),
            "account_equity_used": float(settings.ACCOUNT_EQUITY),
            "risk_pct_used": float(settings.RISK_PCT),
            "entry_price_semantics": "close_as_next_open_estimate",
            # Full inline pattern_diagnostics (Phase 6 D-05 schema dict).
            "pattern_diagnostics": _safe_decode_json(row.get("pattern_diagnostics", '{"type":"none"}')),
        }
        rows.append({
            "ticker": str(ticker),
            "snapshot_date": str(snapshot_date),
            "playbook_tag": str(row["playbook_tag"]),
            "composite_score": float(row["composite_score"]),
            "regime_state": regime_state,
            "entry_price": float(row["entry_price"]),
            "stop_price": float(row["stop_price"]),
            "shares": int(row["shares"]),
            "risk_per_share": float(row["risk_per_share"]),
            "atr_zone": str(row["atr_zone"]),
            # Warning #5 (revision iter 1): use the renamed PicksSchema column.
            # Nullable in the schema; coerce NaN → None so pandera + sqlite3 see
            # a real NULL rather than a float('nan').
            "pivot_distance_atr_breakout": (
                None
                if pd.isna(row.get("pivot_distance_atr_breakout"))
                else float(row["pivot_distance_atr_breakout"])
            ),
            "features_json": _json.dumps(features, default=str, sort_keys=True),
            "ingested_at": now_iso,
        })

    return pd.DataFrame(rows)


def _build_journal_rows_df_from_snapshot(snapshot_date: str) -> "pd.DataFrame":
    """Read data/snapshots/<snapshot_date>.parquet and rebuild the journal-rows
    DataFrame for cli.journal catch-up (CONTEXT D-01).

    The snapshot Parquet has all sizing columns (Plan 07-04 step 5.5 populates
    them; W-Plan05-1 projection writes them through to the snapshot). It ALSO
    has `composite_score_raw` (Plan 07-01 revised + Warning #6) — meaning the
    catch-up flow uses the SAME pre-gate threshold semantics as the live
    pipeline. No per-flow divergence.
    """
    settings = get_settings()
    snap_dir = Path(getattr(settings, "SNAPSHOT_DIR", "data/snapshots"))
    snap_path = snap_dir / f"{snapshot_date}.parquet"
    if not snap_path.exists():
        log.info("journal_catchup_snapshot_missing", path=str(snap_path))
        return pd.DataFrame()

    snap = pd.read_parquet(snap_path)
    if snap.empty:
        return pd.DataFrame()

    regime_state = str(snap["regime_state"].iloc[0])
    regime_row = pd.Series({
        "regime_state": regime_state,
        "regime_score": float(snap["regime_score"].iloc[0]),
    })

    # Re-derive the actionable view from the snapshot. Same predicate as the
    # live pipeline (Warning #6 single-source-of-truth).
    valid_playbook_tags = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    # composite_score_raw is a real column on the snapshot (Plan 07-01 revised);
    # fall back to composite_score only if a legacy snapshot lacks it.
    raw_col = (
        snap["composite_score_raw"]
        if "composite_score_raw" in snap.columns
        else snap["composite_score"]
    )
    threshold = float(settings.JOURNAL_THRESHOLD)
    # adr_rejected is also a real column on the snapshot (Plan 07-01 revised);
    # fall back to False (all-actionable) only if a legacy snapshot lacks it.
    rejected_col = (
        snap["adr_rejected"]
        if "adr_rejected" in snap.columns
        else pd.Series(False, index=snap.index)
    )
    mask = (
        (~rejected_col.fillna(False))
        & (raw_col >= threshold)
        & (snap["playbook_tag"].isin(valid_playbook_tags))
    )
    actionable_view = snap.loc[mask].copy()
    if "ticker" in actionable_view.columns:
        actionable_view = actionable_view.set_index("ticker")

    return _build_journal_rows_df(actionable_view, regime_row, snapshot_date, settings)


# --- private safe-coerce helpers (defensive against NaN / None / Int64NA) -

def _safe_int(v: "Any") -> "int | None":
    if v is None or pd.isna(v):
        return None
    return int(v)


def _safe_float(v: "Any") -> "float | None":
    if v is None or pd.isna(v):
        return None
    return float(v)


def _safe_decode_json(v: "Any") -> "dict":
    import json as _json
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return {"type": "none"}
    try:
        return _json.loads(str(v))
    except (ValueError, TypeError):
        return {"type": "none"}
```

If `Settings` and `pd`, `Path`, `get_settings` are not already imported in pipeline.py, add the imports. (They should be — the existing file uses them.)
  </action>
  <verify>
    <automated>uv run python -c "import inspect; from screener.publishers.pipeline import run_pipeline, _build_journal_rows_df, _build_journal_rows_df_from_snapshot; sig = inspect.signature(run_pipeline); assert 'write_journal' in sig.parameters; assert sig.parameters['write_journal'].default is True; print('pipeline signature OK:', list(sig.parameters.keys()))"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "def run_pipeline\(.*write_journal: bool = True" src/screener/publishers/pipeline.py` returns at least one match (signature may span lines — also accept `grep -A3 "def run_pipeline" src/screener/publishers/pipeline.py | grep -c "write_journal: bool = True"` ≥ 1)
    - `grep -cE "^def _build_journal_rows_df\(" src/screener/publishers/pipeline.py` outputs `1`
    - `grep -cE "^def _build_journal_rows_df_from_snapshot\(" src/screener/publishers/pipeline.py` outputs `1`
    - `grep -c "from screener.sizing import compute_sizing" src/screener/publishers/pipeline.py` outputs `1`
    - `grep -c "composite_score_raw" src/screener/publishers/pipeline.py` ≥ 3 (assignment + actionable-view filter + helper threshold read)
    - **Blocker #1 verification:** `today_panel` is NEVER filtered by `adr_rejected` BEFORE write_snapshot. Confirm by inspecting Pre-snapshot lines: `grep -B1 -A1 "today_panel = today_panel\[" src/screener/publishers/pipeline.py | grep -c "adr_rejected"` outputs `0`. (The string `adr_rejected` should appear only in the actionable_view/skipped_view derivations placed AFTER write_snapshot, and inside the atr_zone sentinel patch which uses `.where(...)` not row filtering.)
    - **Blocker #3 verification:** validate_run + pass_rate are called BEFORE the actionable_view derivation. Confirm by checking that `validate_run(` precedes `actionable_view =` in the file: `awk '/validate_run\(/{a=NR} /actionable_view *=/{b=NR} END{print (a && b && a<b) ? "OK" : "FAIL"}' src/screener/publishers/pipeline.py` outputs `OK`.
    - **Warning #5 verification:** INSERT row builder uses the renamed column: `grep -c "pivot_distance_atr_breakout" src/screener/publishers/pipeline.py` ≥ 3 (features dict + INSERT row dict + helper read in _build_journal_rows_df_from_snapshot)
    - **Warning #6 verification:** _build_journal_rows_df_from_snapshot reads composite_score_raw directly: `grep -A20 "_build_journal_rows_df_from_snapshot" src/screener/publishers/pipeline.py | grep -c "composite_score_raw"` ≥ 1
    - `grep -c "actionable_view" src/screener/publishers/pipeline.py` ≥ 3 (derivation + journal helper call + report renderer hint)
    - `grep -c "skipped_picks=skipped_view" src/screener/publishers/pipeline.py` outputs `1`
    - `grep -c "features_json_version" src/screener/publishers/pipeline.py` outputs `1`
    - `grep -c "not_applicable" src/screener/publishers/pipeline.py` ≥ 1 (atr_zone sentinel patch — Blocker #2 followup)
    - pipeline.py uses no `print()`: `grep -c "^\s*print(" src/screener/publishers/pipeline.py` outputs `0`
    - `uv run pytest tests/test_publishers_pipeline.py -x --no-cov` passes — existing Phase 6 tests still green; Phase 7 additions don't regress them (the snapshot still has the FULL universe — Phase 5 backtest reader contract preserved)
    - `uv run pytest tests/test_architecture.py -x --no-cov` passes — D-23 ALLOWED dict unchanged (publishers may already import sizing + persistence)
  </acceptance_criteria>
  <done>
    pipeline.run_pipeline runs compute_sizing on the FULL cross-section (~1000 rows); validate_run + pass_rate run on the FULL post-sizing frame; snapshot writes the FULL frame; actionable_view + skipped_view are DERIVED, never assigned back to today_panel. Journal append uses pre-gate composite_score_raw threshold in both live + catch-up flows (Warning #6). INSERT row builder uses pivot_distance_atr_breakout (Warning #5). W-Plan05-1 projection preserved; Phase 5 backtest reader contract intact.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend publishers/report.py per-pick block with Entry/Stop/Trail/Shares/Zone + ## Skipped Picks footer</name>
  <files>src/screener/publishers/report.py, tests/test_publishers_report.py</files>
  <read_first>
    - src/screener/publishers/report.py (full file — current render_report at line 200+; per-pick block at lines 286-307; Data Quality footer at lines 312-334)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/publishers/report.py" (sizing per-pick block + ## Skipped Picks footer patterns verbatim)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md <specifics> (Trail / Stop / Zone format)
    - .planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-05-SUMMARY.md (Phase 6 D-19 format + Currently Held / Leaders section already lives here)
    - tests/test_publishers_report.py (existing tests — Plan 07-04 ADDS one new test, does not modify existing)
  </read_first>
  <behavior>
    - `render_report` and `write_report` accept a new keyword arg `skipped_picks: pd.DataFrame | None = None` (default None)
    - When skipped_picks is None or empty, the rendered markdown does NOT contain a `## Skipped Picks` section (backwards compat with all existing Phase 4/5/6 tests)
    - When skipped_picks is non-empty, the rendered markdown contains `## Skipped Picks` AFTER the per-pick blocks (and after "Currently Held / Leaders" if present) and BEFORE `## Data Quality`
    - Each per-pick block (Qull + VCP) gains 4 NEW lines after the existing Playbook / Catalysts lines: `**Entry:** $...`, `**Stop:** $... (label)   **Trail:** ...`, `**Shares:** ...`, `**Zone:** ... (...×ATR above pivot)`
    - The per-pick block guards on `pd.notna(row.get("stop_price"))` so universe rows where sizing is NaN (playbook_tag='none' rows that the report should never render anyway) silently skip the sizing block.
    - One new test in tests/test_publishers_report.py: `test_render_report_includes_sizing_fields_and_skipped_section` validates BOTH features in one render call
    - All existing test_publishers_report.py tests STILL pass (zero regressions)
  </behavior>
  <action>
**A. Modify `src/screener/publishers/report.py`** — three targeted edits:

1. **Update `render_report` signature** — add `skipped_picks: pd.DataFrame | None = None` parameter at the end of the signature. Update the docstring to mention the new kwarg and the `## Skipped Picks` section semantics.

2. **Update `write_report` signature** identically — forward `skipped_picks` to `render_report`.

3. **Add sizing per-pick lines** — locate the per-pick loop (around line 286-307; specifically AFTER the existing `Pivot zone` / `Playbook` / `Catalysts` lines). Append these lines INSIDE the same loop:

```python
        # Phase 7 sizing per-pick block (CONTEXT <specifics> — D-04..D-09).
        # Guard on stop_price notna so non-actionable rows (playbook_tag='none'
        # in the snapshot — Plan 07-04 revised writes the FULL universe) skip
        # this block silently. Actionable rows have sizing populated.
        if "stop_price" in row.index and pd.notna(row.get("stop_price")):
            stop = float(row["stop_price"])
            entry = float(row["entry_price"])
            shares_v = int(row["shares"])
            zone = str(row.get("atr_zone", "unknown"))
            pdist_b = row.get("pivot_distance_atr_breakout")
            pdist_str = "?" if pd.isna(pdist_b) else f"{float(pdist_b):.2f}"
            trail = str(row.get("trail_rule_label", ""))
            playbook = str(row.get("playbook_tag", "none"))
            # D-07 stop-source label per playbook.
            stop_label = {
                "qullamaggie_continuation": "low-of-entry-day",
                "minervini_vcp": "final-contraction-low",
                "leader_hold": "max(1.5xATR, recent swing low)",
            }.get(playbook, "")
            lines.append(f"- **Entry:** ${entry:.2f}")
            lines.append(f"- **Stop:** ${stop:.2f} ({stop_label})   **Trail:** {trail}")
            lines.append(f"- **Shares:** {shares_v}")
            lines.append(f"- **Zone:** {zone} ({pdist_str}xATR above pivot)")
            lines.append("")
```

This block runs inside BOTH the top-N (actionable) loop AND the "Currently Held / Leaders" loop — if the existing code has two separate per-pick loops (Phase 6 Plan 06-05), duplicate the block in both. If the loops share a helper, add the block to the helper.

4. **Add `## Skipped Picks` section** — AFTER the per-pick blocks AND after the "Currently Held / Leaders" section (if present), BEFORE the `## Data Quality` line. Search for the line that emits `"## Data Quality"` (around line 312) and insert the following INSIDE render_report immediately before it:

```python
    # --- Phase 7 Skipped Picks section (CONTEXT D-06 / Pitfall 6) ----
    if skipped_picks is not None and len(skipped_picks) > 0:
        lines.append("## Skipped Picks")
        lines.append("")
        lines.append(
            "Picks excluded by the SIZ-02 1xADR auto-reject (or Pitfall 6 "
            "invalid stop / Pitfall 5 missing diagnostics). Excluded from "
            "both the report top-N AND the journal."
        )
        lines.append("")
        for ticker, srow in skipped_picks.iterrows():
            ticker_str = str(ticker) if not isinstance(ticker, str) else ticker
            reason = str(srow.get("rejection_reason", ""))
            risk = float(srow.get("risk_per_share", 0.0)) if pd.notna(srow.get("risk_per_share")) else 0.0
            adr_pct = float(srow.get("adr_pct", 0.0)) if pd.notna(srow.get("adr_pct")) else 0.0
            entry = float(srow.get("entry_price", srow.get("close", 0.0)))
            adr_dollars = (adr_pct / 100.0) * entry if entry > 0 else 0.0
            multiple = (risk / adr_dollars) if adr_dollars > 0 else 0.0
            if reason == "adr_exceeded":
                lines.append(
                    f"- **{ticker_str}** -- skipped: R/R broken, risk = {multiple:.2f}xADR"
                )
            elif reason == "invalid_stop":
                lines.append(
                    f"- **{ticker_str}** -- skipped: invalid stop (entry <= stop_price)"
                )
            elif reason == "missing_diagnostics":
                lines.append(
                    f"- **{ticker_str}** -- skipped: missing pattern diagnostics"
                )
            else:
                lines.append(f"- **{ticker_str}** -- skipped: {reason}")
        lines.append("")
        lines.append("---")
        lines.append("")
```

DO NOT use `→` (Unicode arrow), emoji, or any non-ASCII glyph — Phase 6 Plan 06-05 Pitfall 12 (ASCII only).

**B. Add ONE new test to `tests/test_publishers_report.py`** — append at the end of the file, DO NOT modify any existing test:

```python


def test_render_report_includes_sizing_fields_and_skipped_section() -> None:
    """Plan 07-04: render_report emits Entry/Stop/Trail/Shares/Zone per pick AND
    ## Skipped Picks section when skipped_picks is non-empty."""
    import pandas as pd
    from screener.publishers.report import render_report

    actionable = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "composite_score": [85.0], "rs_rating": [92], "trend_template_score": [8],
            "volume_component": [0.7],
            "pivot_distance_atr": [0.5], "pivot_zone": ["in-zone"],
            "playbook_tag": ["minervini_vcp"],
            "pattern_diagnostics": ['{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08}'],
            "qullamaggie_score": [0], "minervini_score": [1], "leader_hold_score": [0],
            "breakout_strength": [0.85],
            "days_to_next_earnings": [pd.NA], "crossed_52w_high_within_60d": [False],
            "insider_cluster_buy": [False], "earnings_in_3d_warn": [False],
            "eps_knowable_from": [None], "rank": pd.array([1], dtype=pd.Int64Dtype()),
            "regime_state": ["Confirmed Uptrend"], "regime_score": [0.82],
            # Phase 7 sizing cols populated by Plan 07-04 step 5.5.
            "stop_price": [161.46],   # 175.5 * (1 - 0.08)
            "entry_price": [180.0],
            "shares": pd.array([50], dtype=pd.Int64Dtype()),
            "risk_per_share": [18.54],
            "atr_zone": ["in-zone"],
            "pivot_distance_atr_breakout": [0.25],
            "trail_rule_label": ["21d EMA (then 50d SMA after 15 bars)"],
            "adr_rejected": [False], "rejection_reason": [""],
        }
    )
    skipped = pd.DataFrame(
        {
            "rejection_reason": ["adr_exceeded"],
            "risk_per_share": [1.4], "adr_pct": [1.0], "entry_price": [100.0],
            "close": [100.0],
        },
        index=pd.Index(["BADTICK"], name="ticker"),
    )
    regime_row = pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82})

    md = render_report(
        actionable, regime_row, snapshot_date="2026-05-18",
        top_n=15, pass_rate=0.10, skipped_picks=skipped,
    )

    # Sizing per-pick fields present.
    assert "**Entry:** $180.00" in md
    assert "**Stop:** $161.46" in md
    assert "**Trail:** 21d EMA" in md
    assert "**Shares:** 50" in md
    assert "**Zone:** in-zone" in md
    # ## Skipped Picks section rendered.
    assert "## Skipped Picks" in md
    assert "BADTICK" in md
    assert "R/R broken" in md
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_publishers_report.py --no-cov -q 2>&1 | tail -3 | grep -E "passed" && uv run python -c "import inspect; from screener.publishers.report import render_report, write_report; assert 'skipped_picks' in inspect.signature(render_report).parameters; assert 'skipped_picks' in inspect.signature(write_report).parameters; print('report signatures OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "skipped_picks: " src/screener/publishers/report.py` ≥ 2 (render_report signature + write_report signature)
    - `grep -c "## Skipped Picks" src/screener/publishers/report.py` ≥ 1
    - `grep -c "low-of-entry-day\|final-contraction-low\|recent swing low" src/screener/publishers/report.py` ≥ 3 (all three D-07 labels present)
    - `grep -c "\*\*Entry:\*\*\|\*\*Stop:\*\*\|\*\*Trail:\*\*\|\*\*Shares:\*\*\|\*\*Zone:\*\*" src/screener/publishers/report.py` ≥ 5
    - report.py has zero non-ASCII characters in the new section: `grep -Pn "[^\x00-\x7F]" src/screener/publishers/report.py | grep -E "Skipped|Entry|Stop|Trail|Zone|Shares"` returns no matches (the file may have legacy non-ASCII elsewhere from Phase 6, which is acceptable; new additions must be ASCII)
    - report.py uses no `print()`: `grep -c "^\s*print(" src/screener/publishers/report.py` outputs `0`
    - `grep -c "^def test_render_report_includes_sizing_fields_and_skipped_section" tests/test_publishers_report.py` outputs `1`
    - `uv run pytest tests/test_publishers_report.py --no-cov -q` shows zero failures (existing test count preserved + 1 new test added; all pass)
    - `uv run pytest tests/test_publishers_pipeline.py --no-cov -q` passes
  </acceptance_criteria>
  <done>
    render_report and write_report accept skipped_picks kwarg with backwards-compatible default. Per-pick block has 4 new sizing lines (guarded on stop_price notna so non-actionable rows skip silently). `## Skipped Picks` section appears only when skipped_picks is non-empty. New regression test passes; all existing report tests still pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Land bodies in all 4 tests/test_pipeline_journal.py skeletons (integration tests with strict monkeypatches + snapshot-row-count regression assertion)</name>
  <files>tests/test_pipeline_journal.py, tests/test_publishers_pipeline.py</files>
  <read_first>
    - tests/test_pipeline_journal.py (4 pytest.skip skeletons from Plan 07-01 Task 3)
    - tests/test_publishers_pipeline.py (existing pipeline test patterns — fake_pipeline / monkeypatch idiom)
    - tests/test_cli_smoke.py::test_report_data_quality_gate_d08 (CliRunner + monkeypatch pattern)
    - src/screener/publishers/pipeline.py (file after Tasks 1+2 — run_pipeline + _build_journal_rows_df)
    - tests/conftest.py (sized_input_cross() fixture from Plan 07-01)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"tests/test_pipeline_journal.py"
  </read_first>
  <behavior>
    - test_pipeline_writes_journal: monkeypatch JOURNAL_DB_PATH + SNAPSHOT_DIR to tmp_path; install a minimal panel that includes all sizing-required columns; invoke run_pipeline; assert data/journal.sqlite has rows
    - test_journal_disabled: same setup; invoke run_pipeline(..., write_journal=False); assert journal.sqlite has 0 rows (or doesn't exist); assert `journal_skipped` event in structlog output
    - test_rejected_picks_not_in_journal: include a row with adr_pct=0.3 (auto-reject); assert that ticker is NOT in journal AND the snapshot DOES contain it (because the snapshot retains the FULL universe — revision iteration 1 Blocker #1)
    - test_golden_pipeline_journal: full integration with deterministic seeded panel; assert exact row count, features_json structure (keys present), PicksSchema validation passes, AND snapshot row count == input universe row count (Warning #10 regression assertion locking Blocker #1 in place)
    - **Revision iteration 1 Blocker #4 corrections:**
      a. NO `try/except AttributeError` around monkeypatches — fail loud if Phase 6 symbol missing.
      b. DO NOT monkeypatch `screener.publishers.snapshot.write_snapshot` — let pandera validate the FULL real frame at the write boundary so a future Phase-7 schema break surfaces immediately. Use a temp data dir (already configured via SNAPSHOT_DIR env) so the write is safe.
  </behavior>
  <action>
**Replace all 4 pytest.skip skeletons in tests/test_pipeline_journal.py with real bodies.** Mock `build_panel`, `passes_trend_template`, `score`, `compute_for_date`, `read_fundamentals`, `canslim_c_overlay`, `passes_qullamaggie_setup_a`, `_add_catalyst_columns`, `tag_playbook` — but do NOT mock `write_snapshot` (Blocker #4 fix) and do NOT wrap monkeypatches in `try/except AttributeError` (Blocker #4 fix). If a symbol is missing, fail loud — Phase 7 depends on Phase 6.

Below is the COMPLETE replacement file:

```python
"""tests/test_pipeline_journal.py — Phase 7 pipeline + journal integration (Plan 07-04 bodies)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest


def _make_synthetic_multiindex_panel(
    snapshot_date: str = "2026-05-18",
) -> pd.DataFrame:
    """Build a small MultiIndex(ticker, date) panel with all columns the
    Phase 6 pipeline reads — enough for run_pipeline to chain build_panel →
    score → tag_playbook → apply_regime_gate → compute_sizing without an
    actual OHLCV cache."""
    snap_ts = pd.Timestamp(snapshot_date)
    tickers = ["AAPL", "MSFT", "NVDA", "REJC"]
    idx = pd.MultiIndex.from_product([tickers, [snap_ts]], names=["ticker", "date"])
    return pd.DataFrame(
        {
            "close": [180.0, 380.0, 950.0, 80.0],
            "low": [178.0, 378.0, 940.0, 79.5],
            "high": [182.0, 382.0, 960.0, 80.5],
            "atr_14": [3.5, 5.0, 22.0, 0.5],
            "adr_pct": [4.2, 3.8, 5.5, 0.3],   # REJC adr_pct=0.3 → reject
            "rs_rating": pd.array([92, 88, 95, 82], dtype=pd.Int64Dtype()),
            "trend_template_score": pd.array([8, 7, 8, 6], dtype=pd.Int64Dtype()),
            "volume_component": [0.7, 0.6, 0.8, 0.3],
            "pattern_component": [0.7, 0.5, 0.85, 0.3],
            "earnings_component": [0.6, 0.4, 0.7, 0.2],
            "catalyst_component": [0.5, 0.3, 0.6, 0.2],
            "composite_score": [85.0, 70.0, 88.0, 55.0],
            "passes_trend_template": [True, True, True, True],
            "high_52w": [185.0, 385.0, 970.0, 82.0],
            "low_52w": [140.0, 320.0, 700.0, 65.0],
            "sma_50": [175.0, 370.0, 920.0, 78.0],
            "sma_150": [170.0, 365.0, 880.0, 76.0],
            "sma_200": [165.0, 360.0, 850.0, 74.0],
            "dryup_ratio": [0.85, 0.75, 0.90, 0.60],
            "playbook_tag": ["minervini_vcp", "qullamaggie_continuation", "minervini_vcp", "qullamaggie_continuation"],
            "qullamaggie_score": pd.array([0, 1, 0, 1], dtype=pd.Int64Dtype()),
            "minervini_score": pd.array([1, 0, 1, 0], dtype=pd.Int64Dtype()),
            "leader_hold_score": pd.array([0, 0, 0, 0], dtype=pd.Int64Dtype()),
            "pattern_diagnostics": [
                '{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08,"depth_sequence":[0.25,0.15,0.08],"n_contractions":3,"first_leg_depth":0.25,"breakout_vol_multiple":1.7,"breakout_strength":0.85,"days_in_consolidation":18}',
                '{"type":"flag","pivot_price":378.0,"final_contraction_depth":0.0,"depth_sequence":[],"n_contractions":0,"first_leg_depth":0.0,"breakout_vol_multiple":1.6,"breakout_strength":0.72,"days_in_consolidation":12}',
                '{"type":"vcp","pivot_price":940.0,"final_contraction_depth":0.10,"depth_sequence":[0.30,0.18,0.10],"n_contractions":3,"first_leg_depth":0.30,"breakout_vol_multiple":1.8,"breakout_strength":0.92,"days_in_consolidation":22}',
                '{"type":"flag","pivot_price":79.0,"final_contraction_depth":0.0,"depth_sequence":[],"n_contractions":0,"first_leg_depth":0.0,"breakout_vol_multiple":1.5,"breakout_strength":0.65,"days_in_consolidation":10}',
            ],
            "breakout_strength": [0.85, 0.72, 0.92, 0.65],
            "days_to_next_earnings": pd.array([pd.NA] * 4, dtype=pd.Int64Dtype()),
            "crossed_52w_high_within_60d": [False, False, True, False],
            "insider_cluster_buy": [False, False, False, False],
            "earnings_in_3d_warn": [False, False, False, False],
            "eps_knowable_from": pd.array([None] * 4, dtype=object),
        },
        index=idx,
    )


def _install_pipeline_mocks(monkeypatch: pytest.MonkeyPatch, panel: pd.DataFrame) -> None:
    """Patch out every external dependency of run_pipeline so it walks the DAG
    using the synthetic panel only.

    Revision iteration 1 Blocker #4 fix: NO try/except AttributeError around
    these monkeypatches. Phase 7 already depends on Phase 6 — if any of these
    symbols are missing from publishers/pipeline.py, the test MUST fail loud
    so the breakage is visible immediately.

    Revision iteration 1 Blocker #4 fix: DO NOT monkeypatch write_snapshot.
    We want pandera to validate the real FULL frame at the write boundary so
    any future Phase-7 schema break surfaces here.
    """
    monkeypatch.setattr("screener.publishers.pipeline.build_panel", lambda d: panel)
    monkeypatch.setattr("screener.publishers.pipeline.passes_trend_template", lambda p: p)
    monkeypatch.setattr("screener.publishers.pipeline.score", lambda p, w: p)
    monkeypatch.setattr("screener.publishers.pipeline.passes_qullamaggie_setup_a", lambda p: p)
    monkeypatch.setattr("screener.publishers.pipeline.canslim_c_overlay", lambda p, f, ts: p)
    monkeypatch.setattr("screener.publishers.pipeline.tag_playbook", lambda p: p)
    monkeypatch.setattr(
        "screener.publishers.pipeline._add_catalyst_columns", lambda p, f, ts: p
    )
    monkeypatch.setattr(
        "screener.persistence.read_fundamentals", lambda ts: pd.DataFrame()
    )
    monkeypatch.setattr(
        "screener.publishers.pipeline.compute_for_date",
        lambda ts, p: pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82}),
    )
    monkeypatch.setattr(
        "screener.publishers.pipeline.validate_run",
        lambda *a, **kw: None,
    )
    # Pattern audit writer can be safely stubbed — it's a Phase 6 side effect
    # orthogonal to the Phase 7 journal + sizing surface under test here.
    monkeypatch.setattr(
        "screener.persistence.write_pattern_audit_atomic",
        lambda df, d: None,
    )
    # NOTE: write_snapshot is INTENTIONALLY NOT mocked. SNAPSHOT_DIR is pointed
    # at tmp_path by _setup_settings so the write is safe; we want pandera to
    # validate the real FULL frame (Blocker #4 fix + Warning #10 lock).


def _setup_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point JOURNAL_DB_PATH + SNAPSHOT_DIR at tmp_path; clear Settings cache."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JOURNAL_DB_PATH", str(tmp_path / "journal.sqlite"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    monkeypatch.setenv("JOURNAL_THRESHOLD", "50.0")
    monkeypatch.setenv("RISK_PCT", "0.01")
    monkeypatch.setenv("ACCOUNT_EQUITY", "100000")
    from screener.config import get_settings
    get_settings.cache_clear()


def test_pipeline_writes_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OUT-04: run_pipeline(..., write_journal=True) appends rows to data/journal.sqlite."""
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    db = tmp_path / "journal.sqlite"
    assert db.exists()
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT ticker, composite_score FROM picks").fetchall()
    tickers = sorted(r[0] for r in rows)
    # AAPL (85), MSFT (70), NVDA (88) all >= 50; REJC (55) >= 50 but adr-rejected.
    assert "AAPL" in tickers and "NVDA" in tickers, tickers
    assert "REJC" not in tickers, "REJC should be ADR-rejected, not in journal"


def test_journal_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-01: run_pipeline(..., write_journal=False) writes ZERO journal rows."""
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=False)

    db = tmp_path / "journal.sqlite"
    # The contract is: zero rows in the picks table, NOT no file. (The file
    # may or may not exist depending on whether _ensure_picks_schema ran.)
    if db.exists():
        with sqlite3.connect(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        assert count == 0, f"write_journal=False should not append; got {count} rows"


def test_rejected_picks_not_in_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SIZ-02 / D-06: ADR-rejected picks excluded from journal BUT present in snapshot.

    Revision iteration 1 Blocker #1 regression check: the snapshot retains the
    FULL universe (including rejected picks); only the journal/report top-N
    filters them out.
    """
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    # Journal: REJC must NOT appear.
    db = tmp_path / "journal.sqlite"
    with sqlite3.connect(db) as conn:
        journal_tickers = [r[0] for r in conn.execute("SELECT ticker FROM picks").fetchall()]
    assert "REJC" not in journal_tickers
    assert len(journal_tickers) >= 1

    # Snapshot: REJC MUST appear (full universe preserved — Blocker #1).
    snap_path = tmp_path / "snapshots" / "2026-05-18.parquet"
    assert snap_path.exists(), f"snapshot not written: {snap_path}"
    snap_df = pd.read_parquet(snap_path)
    snap_tickers = set(snap_df["ticker"]) if "ticker" in snap_df.columns else set(snap_df.index)
    assert "REJC" in snap_tickers, (
        f"Blocker #1 regression: REJC missing from snapshot (snap has: {snap_tickers})"
    )


def test_golden_pipeline_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-1 + Warning #10: full integration round-trip — deterministic row count +
    features_json structure + snapshot-row-count regression assertion.

    The snapshot row count MUST equal the input universe row count (4 here).
    This locks revision iteration 1 Blocker #1 in place: any future regression
    that filters today_panel by adr_rejected before write_snapshot will fail
    here loudly.
    """
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    # 1. Snapshot row-count regression (Warning #10 / Blocker #1 lock).
    snap_path = tmp_path / "snapshots" / "2026-05-18.parquet"
    snap_df = pd.read_parquet(snap_path)
    universe_size = len(_make_synthetic_multiindex_panel())  # 4 tickers
    assert len(snap_df) == universe_size, (
        f"Blocker #1 regression: snapshot has {len(snap_df)} rows; "
        f"expected {universe_size} (full universe). "
        f"Did today_panel get filtered by adr_rejected before write_snapshot?"
    )

    # 2. Journal row-count + features_json structure.
    db = tmp_path / "journal.sqlite"
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT ticker, features_json FROM picks ORDER BY ticker"
        ).fetchall()
    # Exact count: 3 actionable tickers (AAPL, MSFT, NVDA — composite ≥ 50, not rejected).
    assert len(rows) == 3, [r[0] for r in rows]
    # features_json structure check on the first row.
    feat = json.loads(rows[0][1])
    required_top_keys = {
        "features_json_version", "rs_rating", "trend_template_score",
        "composite_score", "composite_score_raw", "regime_score", "regime_state",
        "playbook_tag", "atr_14", "adr_pct", "entry_price", "stop_price",
        "shares", "risk_per_share", "atr_zone", "pattern_diagnostics",
        "account_equity_used", "risk_pct_used", "entry_price_semantics",
        "pivot_distance_atr_breakout",  # Warning #5 — renamed column present
    }
    missing = required_top_keys - set(feat.keys())
    assert not missing, f"features_json missing keys: {missing}"
    assert feat["features_json_version"] == "v1.0"
    # pattern_diagnostics is inlined as a dict (not a string).
    assert isinstance(feat["pattern_diagnostics"], dict)
    assert "type" in feat["pattern_diagnostics"]
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_pipeline_journal.py --no-cov -q 2>&1 | tail -3 | grep -E "4 passed" && uv run pytest tests/test_publishers_pipeline.py tests/test_publishers_report.py --no-cov -q && uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q && uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def test_" tests/test_pipeline_journal.py` outputs `4`
    - `grep -c "pytest\.skip" tests/test_pipeline_journal.py` outputs `0`
    - **Blocker #4 verification:** `grep -c "try:" tests/test_pipeline_journal.py` outputs `0` (no try/except AttributeError around monkeypatches)
    - **Blocker #4 verification:** `grep -c "monkeypatch.setattr.*write_snapshot" tests/test_pipeline_journal.py` outputs `0` (write_snapshot NOT mocked)
    - **Warning #10 verification:** `grep -c "Blocker #1" tests/test_pipeline_journal.py` ≥ 1 (snapshot row-count assertion present and labeled)
    - **Warning #10 verification:** `grep -c "len(snap_df) == universe_size" tests/test_pipeline_journal.py` ≥ 1
    - `uv run pytest tests/test_pipeline_journal.py --no-cov -q 2>&1 | tail -3` shows `4 passed` (zero failures, zero skips)
    - `uv run pytest tests/test_publishers_pipeline.py --no-cov -q` passes (no regression in existing Phase 6 W-Plan05-1 tests)
    - `uv run pytest tests/test_publishers_report.py --no-cov -q` passes (Plan 07-04 Task 2 added 1 test; all existing pass)
    - `uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q` passes (FND-04 mutation gate green)
    - `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov -q` passes (D-24 lock intact)
  </acceptance_criteria>
  <done>
    All 4 tests in test_pipeline_journal.py pass with real bodies. NO try/except AttributeError around monkeypatches (fail loud — Blocker #4). write_snapshot NOT mocked (lets pandera validate real FULL frame — Blocker #4). New snapshot-row-count regression assertion in test_golden_pipeline_journal locks Blocker #1 in place (Warning #10). FND-04, D-23, D-24 all green.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| run_pipeline cross-section → journal write | Sized + filtered picks become permanent journal rows; bad threshold or filter logic poisons the v2 ML training contract |
| run_pipeline FULL cross-section → snapshot Parquet | Sizing populates 10 new schema cols on every row of the universe; bad nullability/sentinel handling fails pandera at write time |
| _build_journal_rows_df_from_snapshot → cli.journal | Reads on-disk Parquet (potentially adversarial after machine restore); pandera + PicksSchema validate before insert |
| skipped_picks → report markdown | Untrusted rejection_reason string would render verbatim — but it's enum-bounded by sizing.py |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-17 | Tampering | Pipeline pre-gate vs post-gate composite threshold mismatch (Pitfall 3 / Warning #6) | mitigate | `composite_score_raw` captured BEFORE apply_regime_gate; persisted to snapshot via RankingSnapshotSchema (Plan 07-01 revised); BOTH live `_build_journal_rows_df` and catch-up `_build_journal_rows_df_from_snapshot` filter on the raw value. Tested via test_golden_pipeline_journal asserting `composite_score_raw` appears in features_json. |
| T-07-18 | Information disclosure | features_json embedded in journal | accept | Same rationale as T-07-14 (Plan 07-03) — composite scores and indicator values are public-data derivatives. features_json_version='v1.0' supports future redaction. |
| T-07-19 | Process integrity | run_pipeline failure between write_snapshot and append_picks_rows | mitigate | Snapshot is the SOURCE OF TRUTH and is written BEFORE the journal append (revised step order). cli.journal catch-up flow (Plan 07-05) reads the snapshot — which now retains composite_score_raw + adr_rejected as real columns — and re-builds journal rows using the IDENTICAL filter predicate as the live pipeline (Warning #6). Failure mode is fully recoverable: re-run `screener journal` after fixing the underlying issue. |
| T-07-20 | Spoofing | Untrusted ticker symbol in snapshot Parquet | mitigate | PicksSchema regex `^[A-Z][A-Z0-9\-]{0,9}$` rejects malformed tickers before INSERT (defense-in-depth on top of build_panel's existing ticker validation). |
| T-07-21 | Repudiation | structlog `journal_append_summary` event audit trail | accept | Event payload includes n_attempted / n_inserted / n_idempotent_skip — sufficient for forensic reconciliation when paired with the snapshot Parquet (which now retains the FULL universe including rejected picks per Blocker #1 revision). |
| T-07-27 | Tampering | Snapshot truncation via accidental adr_rejected filtering before write (revision iter 1 Blocker #1) | mitigate | test_golden_pipeline_journal contains a hard assertion: `len(snap_df) == universe_size`. Any future regression that filters today_panel by adr_rejected before write_snapshot will fail this test loudly. test_publishers_pipeline.py W-Plan05-1 projection tests provide a second line of defense. |

ASVS L1 applicable: V5.1.3 (input validation — PicksSchema at write boundary), V13.1.4 (schema-validated APIs). No high-risk threats.
</threat_model>

<verification>
```bash
# Phase 7 Plan 04 verification suite (~20s)
uv run pytest tests/test_pipeline_journal.py --no-cov -q        # 4 passed
uv run pytest tests/test_sizing.py --no-cov -q                  # Plan 07-02 still green
uv run pytest tests/test_journal.py --no-cov -q                 # Plan 07-03 still green
uv run pytest tests/test_publishers_pipeline.py --no-cov -q     # Phase 4/5/6 + Plan 07-04 additions
uv run pytest tests/test_publishers_report.py --no-cov -q       # Phase 4/5/6 + Plan 07-04 Task 2
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q   # FND-04 mutation gate
uv run pytest tests/test_architecture.py --no-cov -q            # D-23
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q  # D-24

uv run ruff check src/screener/publishers/pipeline.py src/screener/publishers/report.py
```
</verification>

<success_criteria>
- publishers/pipeline.run_pipeline signature includes `write_journal: bool = True`.
- composite_score_raw captured BEFORE apply_regime_gate (Pitfall 3 mitigation + Warning #6 single-source-of-truth).
- compute_sizing called on the FULL cross-section between apply_regime_gate and snapshot write (Blocker #1).
- today_panel is NEVER filtered by adr_rejected before write_snapshot (Blocker #1).
- validate_run + pass_rate run on the FULL post-sizing frame (Blocker #3).
- atr_zone sentinel patch in place: non-actionable rows get "not_applicable" (Blocker #2 followup).
- actionable_view + skipped_view are DERIVED frames, never assigned back to today_panel.
- Journal append fires after write_snapshot when write_journal=True; emits journal_append_summary event.
- When write_journal=False, emits journal_skipped event and no rows are inserted.
- _build_journal_rows_df filters by composite_score_raw >= JOURNAL_THRESHOLD AND regime_state != 'Correction'.
- _build_journal_rows_df_from_snapshot reads composite_score_raw directly from the snapshot (Warning #6 — no per-flow divergence).
- INSERT row builder uses key `pivot_distance_atr_breakout` (Warning #5).
- features_json contains 13+ score-component / 9+ indicator / 8+ sizing-input keys + inline pattern_diagnostics + features_json_version='v1.0' + pivot_distance_atr_breakout.
- render_report and write_report accept skipped_picks kwarg (default None, backwards-compat).
- Per-pick block has Entry / Stop / Trail / Shares / Zone lines (guarded on stop_price notna).
- `## Skipped Picks` section appears after per-pick blocks and before Data Quality footer when skipped_picks is non-empty.
- All 4 tests in test_pipeline_journal.py pass with real bodies; NO try/except AttributeError; write_snapshot NOT mocked (Blocker #4).
- New snapshot-row-count regression assertion in test_golden_pipeline_journal (Warning #10) locks Blocker #1.
- Existing test_publishers_pipeline.py, test_publishers_report.py, test_sizing.py, test_journal.py all still green.
- FND-04, D-23, D-24 unchanged.
</success_criteria>

<output>
After completion, create `.planning/phases/07-sizing-finalization-paper-trade-journal/07-04-SUMMARY.md` per the standard template.
</output>
</content>
</invoke>