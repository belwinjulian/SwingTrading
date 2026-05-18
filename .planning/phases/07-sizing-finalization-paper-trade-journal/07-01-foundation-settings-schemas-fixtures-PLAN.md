---
phase: 07-sizing-finalization-paper-trade-journal
plan: "01"
type: execute
wave: 0
depends_on: []
files_modified:
  - src/screener/config.py
  - .env.example
  - .gitignore
  - src/screener/persistence.py
  - tests/conftest.py
  - tests/test_sizing.py
  - tests/test_journal.py
  - tests/test_pipeline_journal.py
autonomous: true
requirements: [SIZ-01, SIZ-05, OUT-04, OUT-05, OUT-06]
requirements_addressed: [SIZ-01, SIZ-05, OUT-04, OUT-05, OUT-06]
tags: [phase-7, foundation, settings, schemas, fixtures, gitignore, conftest]

must_haves:
  truths:
    - "Settings carries RISK_PCT (0.01), JOURNAL_THRESHOLD (50.0), JOURNAL_DB_PATH (data/journal.sqlite) per D-05 / D-01"
    - "ACCOUNT_EQUITY at config.py:39 is untouched (already present); RISK_PCT_PER_TRADE at config.py:38 is untouched (deprecation buffer)"
    - "RankingSnapshotSchema carries 10 new sizing columns (all nullable to accommodate full-universe rows where playbook_tag='none'): stop_price, entry_price, shares, risk_per_share, atr_zone, pivot_distance_atr_breakout, trail_rule_label, composite_score_raw, adr_rejected, rejection_reason"
    - "atr_zone field includes 'not_applicable' sentinel for non-actionable rows (playbook_tag='none' / leader_hold without pivot) per revision iteration 1 Blocker #2"
    - ".gitignore allowlists data/journal.sqlite (commit policy per RESEARCH A4 — paper-trade history is the v1.x performance contract)"
    - "tests/conftest.py exposes sized_input_cross() fixture with all 13 columns sizing.compute_sizing() requires"
    - "tests/test_sizing.py, tests/test_journal.py, tests/test_pipeline_journal.py exist as named pytest.skip() skeletons covering every test in RESEARCH §Validation Architecture"
  artifacts:
    - path: "src/screener/config.py"
      provides: "Settings.RISK_PCT, Settings.JOURNAL_THRESHOLD, Settings.JOURNAL_DB_PATH"
      contains: "RISK_PCT: float = 0.01"
    - path: ".env.example"
      provides: "RISK_PCT and JOURNAL_THRESHOLD env template entries"
      contains: "RISK_PCT=0.01"
    - path: ".gitignore"
      provides: "data/journal.sqlite carve-out allowlist"
      contains: "!/data/journal.sqlite"
    - path: "src/screener/persistence.py"
      provides: "Extended RankingSnapshotSchema with 10 Phase 7 columns (sizing + composite_score_raw + adr_rejected + rejection_reason)"
      contains: "stop_price: Series[float]"
    - path: "tests/conftest.py"
      provides: "sized_input_cross() function-scope fixture"
      contains: "def sized_input_cross"
    - path: "tests/test_sizing.py"
      provides: "11 named pytest.skip skeletons for sizing module (SIZ-01..05)"
      contains: "def test_shares_formula"
    - path: "tests/test_journal.py"
      provides: "10 named pytest.skip skeletons for SQLite journal layer (OUT-04..06)"
      contains: "def test_immutability_trigger"
    - path: "tests/test_pipeline_journal.py"
      provides: "4 named pytest.skip skeletons for pipeline-journal integration"
      contains: "def test_pipeline_writes_journal"
  key_links:
    - from: "src/screener/config.py"
      to: "src/screener/sizing.py (Plan 07-02 reads RISK_PCT, ACCOUNT_EQUITY)"
      via: "get_settings().RISK_PCT"
      pattern: "RISK_PCT: float = 0\\.01"
    - from: "src/screener/persistence.py RankingSnapshotSchema"
      to: "publishers/pipeline.py write_snapshot path (Plan 07-04 populates sizing cols on FULL universe)"
      via: "validate_at_write(RankingSnapshotSchema, df)"
      pattern: "stop_price: Series\\[float\\]"
    - from: ".gitignore"
      to: "data/journal.sqlite (Plan 07-03 creates the SQLite file)"
      via: "allowlist (negative pattern)"
      pattern: "!/data/journal\\.sqlite"

user_setup: []
---

<objective>
Wave 0 foundation for Phase 7 — ship typed Settings extensions (D-05 / D-01), extend `RankingSnapshotSchema` with the ten new Phase 7 columns (7 sizing + composite_score_raw + adr_rejected + rejection_reason), allowlist `data/journal.sqlite` in `.gitignore` (commit policy resolved per RESEARCH A4), add the `sized_input_cross()` conftest fixture (mitigates RESEARCH Pitfall 7), and create three named-test skeleton files (`test_sizing.py`, `test_journal.py`, `test_pipeline_journal.py`) so Wave 1 plans 07-02 and 07-03 land green bodies inside pre-existing pytest stubs.

Purpose: Defend Pitfall 7 (Phase-4 fixtures lack Phase-6+7 columns), lock the Settings + schema seams before parallel Wave 1 implementation, and resolve the open `data/journal.sqlite` commit policy that has been deferred since STATE.md was initialized.

**Revision iteration 1 change (Blocker #2):** All Phase 7 sizing columns are `nullable=True` because Plan 07-04 (revised) writes the FULL universe to the snapshot — ~95% of rows have `playbook_tag='none'` and therefore no meaningful sizing data. `atr_zone` includes a `"not_applicable"` sentinel for the same reason. Two NEW columns (`composite_score_raw`, `adr_rejected`, `rejection_reason`) are also added to the schema to support the actionable-pick derivation in Plan 07-04 + Plan 07-05.

Output: 8 modified files; 3 new test files with named skeletons; one new conftest fixture; zero behavioral logic — purely seam wiring.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md
@.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-05-SUMMARY.md
@.planning/phases/02-data-foundation/02-CONTEXT.md
@CLAUDE.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase.
     Executor should use these directly — no codebase exploration needed. -->

Existing `Settings` field locations (src/screener/config.py):
- line 38: `RISK_PCT_PER_TRADE: float = 0.0075`  ← LEAVE UNTOUCHED (deprecation buffer per RESEARCH §config.py recommendation)
- line 39: `ACCOUNT_EQUITY: float = 100_000.0`   ← LEAVE UNTOUCHED (already correct per D-05)

Existing `.env.example` field locations:
- line 25: `RISK_PCT_PER_TRADE=0.0075`
- line 28: `ACCOUNT_EQUITY=100000`

Existing `.gitignore` carve-out idiom (lines 38–66, Phase 2 D-20 + Phase 6 D-08):
```
data/...                       (broad ignore at top of file)
!/data/universe/
!/data/universe/.gitkeep
!/data/ohlcv/
!/data/ohlcv/**/splits.parquet
!/data/ohlcv/**/.gitkeep
!/data/snapshots/
!/data/snapshots/.gitkeep
!/data/fundamentals/
!/data/fundamentals/.gitkeep
!/data/insider/
!/data/insider/.gitkeep
!/data/pattern_audit/
!/data/pattern_audit/.gitkeep
```

Existing `RankingSnapshotSchema` (src/screener/persistence.py:222–273) — 26 columns total:
- ticker, rank, composite_score, rs_component, trend_component, volume_component,
  pattern_component, earnings_component, catalyst_component,
  passes_trend_template, trend_template_score, rs_rating, dryup_ratio,
- line 243: `pivot_distance_atr: Series[float] = pa.Field(nullable=True)`   ← Phase 4 sign convention (high_52w - close)/atr; DO NOT change semantics
- pivot_zone (Phase 4: 2-state isin), regime_state, regime_score,
- Phase 6 cols: playbook_tag, qullamaggie_score, minervini_score, leader_hold_score, pattern_diagnostics, breakout_strength, days_to_next_earnings, crossed_52w_high_within_60d, insider_cluster_buy, earnings_in_3d_warn, eps_knowable_from
- `class Config: strict = True; coerce = False`

Phase 6 W-Plan05-1 snapshot projection in `publishers/pipeline.py` (Plan 06-05 SUMMARY):
- snapshot writer projects `today_panel[[c for c in schema_cols if c in today_panel.columns]]` BEFORE `write_snapshot`
- Means: extra Phase 7 columns added to `RankingSnapshotSchema` will be picked up by this projection automatically; pipeline.py needs only to populate them upstream (Plan 07-04).

**Why Phase 7 sizing columns MUST be nullable=True (revision iteration 1 Blocker #2):**
- composite scoring assigns `playbook_tag = "none"` (signals/composite.py:261 default branch) to ~95% of the universe (rows that don't match qullamaggie/minervini/leader)
- Plan 07-02 sizing dispatch returns `STOP_HELPERS.get("none") = None` for those rows → falls back to `stop_price = close_price` → `risk_per_share = 0` → `rejection = "invalid_stop"` → `adr_rejected = True`
- Plan 07-04 (revised) writes the FULL universe to the snapshot (OUT-03 + Phase 5 backtest input contract); only the actionable-pick VIEW filters by `adr_rejected==False`
- Therefore: most rows in the snapshot have NaN sizing → `nullable=True` is mandatory
- `atr_zone` gets a `"not_applicable"` sentinel for those rows (rather than NaN) to preserve `isin` integrity

Existing test skeleton idiom (Plan 06-01 used this — every skeleton is `pytest.skip("Plan 06-XX")`):
```python
def test_<descriptive_name>() -> None:
    """<one-line behavior description tying to req ID>."""
    pytest.skip("Plan 07-02")  # or 07-03 / 07-04 — whichever wave-1 plan fills it
```

Existing `synthetic_scored_panel` fixture in tests/conftest.py:443-473 — the analog for `sized_input_cross`. Function-scope (NOT session-scope) so tests may mutate the frame.

Pattern_diagnostics encoder/decoder (src/screener/indicators/patterns.py:120-134) — already exists:
- `encode_pattern_diagnostics(d: dict) -> str` returns JSON string for the snapshot column
- `decode_pattern_diagnostics(raw: str) -> dict` returns dict, falls back to `{"type": "none"}` on malformed input
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend Settings with RISK_PCT, JOURNAL_THRESHOLD, JOURNAL_DB_PATH and mirror to .env.example</name>
  <files>src/screener/config.py, .env.example</files>
  <read_first>
    - src/screener/config.py (current Settings class body — see existing fields at lines 36-75)
    - .env.example (current env template — see existing fields at lines 25, 28)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/config.py (Settings additive extension)"
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md §"Settings extensions"
  </read_first>
  <action>
Append a Phase 7 section to the Settings class body in `src/screener/config.py`, mirroring the Phase 6 idiom at the end of the class (after the existing Phase 6 paths block; before any `model_config` / `Config` block if present):

```python
    # Phase 7 — sizing finalization + journal (D-05 / D-01 / OUT-04).
    # ACCOUNT_EQUITY already declared at line 39; do NOT duplicate.
    # RISK_PCT_PER_TRADE (line 38, default 0.0075) is the EXISTING Phase 4 field; per D-05
    # the Phase 7 sizing formula reads a NEW field `RISK_PCT` with default 0.01 (1%).
    # The legacy RISK_PCT_PER_TRADE field is preserved as a deprecation buffer.
    RISK_PCT: float = 0.01
    JOURNAL_THRESHOLD: float = 50.0
    JOURNAL_DB_PATH: Path = Path("data/journal.sqlite")
```

Append a matching block to `.env.example` (after the existing Phase 6 paths block at end-of-file):

```
# Phase 7 — sizing + journal (D-05 / OUT-04 / D-01).
# ACCOUNT_EQUITY already declared above (line 28); do NOT duplicate.
# RISK_PCT_PER_TRADE (line 25, 0.0075) is the legacy Phase 4 field; Phase 7 reads RISK_PCT below.
RISK_PCT=0.01
JOURNAL_THRESHOLD=50.0
# JOURNAL_DB_PATH=data/journal.sqlite
```

CRITICAL VALUES:
- `RISK_PCT=0.01` (1% per trade — D-05 verbatim; the CONTEXT comment `default 0.01 = 1%` resolves the apparent CONTEXT line 149 typo)
- `JOURNAL_THRESHOLD=50.0` NOT `0.5` — composite_score is bounded `ge=0.0, le=100.0` per RankingSnapshotSchema:232; CONTEXT line 30 said `0.5` using the wrong scale (caught by RESEARCH Open Question 1 + PATTERNS.md §config.py "Threshold value" note). The correct numeric scale is the 0–100 raw composite_score.
- `JOURNAL_DB_PATH=data/journal.sqlite` (mirrors `INSIDER_CACHE_PATH=data/insider/form4.sqlite` idiom from Phase 6)

DO NOT modify `RISK_PCT_PER_TRADE` (line 38) or `ACCOUNT_EQUITY` (line 39). DO NOT remove either from `.env.example`.
  </action>
  <verify>
    <automated>uv run python -c "from screener.config import Settings; s = Settings(); assert s.RISK_PCT == 0.01, f'RISK_PCT={s.RISK_PCT}'; assert s.JOURNAL_THRESHOLD == 50.0, f'JOURNAL_THRESHOLD={s.JOURNAL_THRESHOLD}'; assert str(s.JOURNAL_DB_PATH) == 'data/journal.sqlite'; assert s.ACCOUNT_EQUITY == 100_000.0, 'ACCOUNT_EQUITY MUST be untouched'; assert s.RISK_PCT_PER_TRADE == 0.0075, 'RISK_PCT_PER_TRADE MUST be untouched (deprecation buffer)'; print('Settings OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^\s*RISK_PCT: float = 0\.01" src/screener/config.py` returns exactly one match
    - `grep -nE "^\s*JOURNAL_THRESHOLD: float = 50\.0" src/screener/config.py` returns exactly one match
    - `grep -nE "^\s*JOURNAL_DB_PATH: Path = Path\(.data/journal\.sqlite.\)" src/screener/config.py` returns exactly one match
    - `grep -nE "^\s*RISK_PCT_PER_TRADE: float = 0\.0075" src/screener/config.py` STILL returns exactly one match (untouched)
    - `grep -nE "^\s*ACCOUNT_EQUITY: float = 100_000\.0" src/screener/config.py` STILL returns exactly one match (untouched)
    - `grep -cE "^RISK_PCT=0\.01$" .env.example` outputs `1`
    - `grep -cE "^JOURNAL_THRESHOLD=50\.0$" .env.example` outputs `1`
    - `grep -cE "^RISK_PCT_PER_TRADE=0\.0075$" .env.example` STILL outputs `1` (untouched)
    - `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov` passes (D-24 surface lock unchanged)
  </acceptance_criteria>
  <done>
    Settings carries RISK_PCT (0.01), JOURNAL_THRESHOLD (50.0), JOURNAL_DB_PATH (data/journal.sqlite). `.env.example` mirrors the three new fields. Legacy RISK_PCT_PER_TRADE and ACCOUNT_EQUITY untouched. Python import succeeds; no other test regressions.
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend RankingSnapshotSchema with 10 Phase 7 columns (nullable=True) + .gitignore carve-out for data/journal.sqlite</name>
  <files>src/screener/persistence.py, .gitignore</files>
  <read_first>
    - src/screener/persistence.py (RankingSnapshotSchema at lines 222-273 — see existing 26-col definition + Phase 6 extension block at lines 253-269)
    - src/screener/publishers/report.py (lines 65-90 — `_add_publisher_columns` computes `pivot_distance_atr` as `(high_52w - close) / atr` per Phase 4 sign convention; DO NOT change)
    - src/screener/signals/composite.py (line 261 — `playbook_tag = "none"` default branch; ~95% of universe lands here, explaining why Phase 7 sizing cols MUST be nullable)
    - .gitignore (lines 38-66 — existing `!/data/...` allowlist carve-out idiom for Phase 2 D-20 + Phase 6 D-08)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/persistence.py — RankingSnapshotSchema extension"
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Architecture Patterns" Open Question 3 + Assumption A3 (pivot_distance_atr sign convention)
  </read_first>
  <action>
**A. Extend RankingSnapshotSchema** in `src/screener/persistence.py` — append TEN Phase 7 columns AFTER the existing `eps_knowable_from` line (line 269), BEFORE the `class Config:` line (line 271).

**Critical nullability decision (revision iteration 1 Blocker #2):** ALL Phase 7 sizing columns are `nullable=True` because Plan 07-04 (revised) writes the FULL universe (~1000 rows) to the snapshot. The composite scorer (`signals/composite.py:261`) assigns `playbook_tag = "none"` to ~95% of rows; those rows have no meaningful sizing data. The `atr_zone` field accepts a `"not_applicable"` sentinel string for those rows (selected over `nullable=True` so the `isin` constraint still enforces value integrity on actionable rows). Rationale: per the revision instructions, "compute_sizing runs on the FULL cross-section ... NaN where playbook_tag == 'none' or rejection fires; nullable schema accepts this."

```python

    # Phase 7 extension (CONTEXT.md D-04 / D-09 / SIZ-01..05) — sizing columns
    # populated by sizing.compute_sizing() in Plan 07-02 and projected to the
    # snapshot at the write boundary by publishers/pipeline.py (Plan 07-04
    # extends the existing W-Plan05-1 projection from Phase 6 Plan 06-05).
    #
    # NULLABILITY (revision iteration 1 Blocker #2 fix): compute_sizing runs on
    # the FULL universe in pipeline.py. Rows where playbook_tag='none' (~95% of
    # universe per signals/composite.py:261 default branch) have no actionable
    # sizing — those columns land as NaN. The snapshot MUST retain the full row
    # set to preserve OUT-03 (full ranked universe in snapshot) and the Phase 5
    # backtest reader contract. Therefore: nullable=True on all 7 sizing cols.
    #
    # pivot_distance_atr (line 243 above) keeps the Phase 4 sign convention
    # `(high_52w - close)/atr` (positive when close is BELOW 52w high) — this
    # is the "distance from 52w high" measurement used by Phase 4's pivot_zone.
    # Phase 7 introduces a NEW column `pivot_distance_atr_breakout` with sign
    # `(close - pivot_price)/atr` (positive when close is ABOVE breakout pivot),
    # which feeds the D-09 3-bucket atr_zone classifier (RESEARCH Assumption
    # A3 / Open Question 3).
    #
    # atr_zone: `"not_applicable"` sentinel (vs nullable=True) — chosen so the
    # `isin` enum still enforces value integrity on actionable rows; rows with
    # playbook_tag='none' or no breakout pivot receive the sentinel.
    stop_price: Series[float] = pa.Field(gt=0.0, nullable=True)
    entry_price: Series[float] = pa.Field(gt=0.0, nullable=True)
    shares: Series[pd.Int64Dtype] = pa.Field(ge=0, nullable=True)
    risk_per_share: Series[float] = pa.Field(ge=0.0, nullable=True)
    atr_zone: Series[str] = pa.Field(
        isin=["in-zone", "extended", "chase, skip", "not_applicable"], nullable=True,
    )
    pivot_distance_atr_breakout: Series[float] = pa.Field(nullable=True)
    trail_rule_label: Series[str] = pa.Field(nullable=True)

    # Phase 7 revision iteration 1 Blocker #2 / Warning #6: composite_score_raw
    # is the PRE-regime-gate composite score. Captured BEFORE apply_regime_gate
    # in run_pipeline (Plan 07-04 Task 1) and used as the SINGLE SOURCE OF TRUTH
    # for the JOURNAL_THRESHOLD filter in BOTH the live pipeline AND the catch-up
    # flow (cli.journal — Plan 07-05). Eliminates the per-flow divergence flagged
    # by revision Warning #6.
    composite_score_raw: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=True)

    # Phase 7 revision iteration 1 Blocker #1: actionable-pick derivation moved
    # out of pipeline.py mutation and into a derived VIEW. The snapshot retains
    # these two columns so cli.journal (Plan 07-05) can re-derive the actionable
    # set from the snapshot alone (no need to re-run sizing).
    adr_rejected: Series[bool] = pa.Field(nullable=True)
    rejection_reason: Series[str] = pa.Field(
        isin=["", "adr_exceeded", "invalid_stop", "missing_diagnostics"], nullable=True,
    )
```

DO NOT alter `pivot_distance_atr` at line 243. DO NOT alter `pivot_zone` at line 244-246 (Phase 4's 2-state field stays — Phase 7's `atr_zone` is the new 3-state-plus-sentinel field per D-09 + Blocker #2; both coexist).

**B. Allowlist `data/journal.sqlite` in `.gitignore`** — append two lines AT THE BOTTOM of the existing `!/data/...` carve-out block (after the Phase 6 `!/data/pattern_audit/.gitkeep` line at line 66):

```
# Phase 7 (RESEARCH A4 — paper-trade history IS the v1.x performance contract;
# commit the SQLite file, mirror the splits.parquet allowlist idiom).
!/data/journal.sqlite
```

Resolves the open todo from STATE.md ("Decide whether to commit `journal.sqlite` to repo (recommended yes for paper-trade history) — defer to Phase 7 planning").
  </action>
  <verify>
    <automated>uv run python -c "from screener.persistence import RankingSnapshotSchema; cols = RankingSnapshotSchema.to_schema().columns; required = {'stop_price','entry_price','shares','risk_per_share','atr_zone','pivot_distance_atr_breakout','trail_rule_label','composite_score_raw','adr_rejected','rejection_reason'}; missing = required - set(cols.keys()); assert not missing, f'Missing Phase 7 cols: {missing}'; assert 'pivot_distance_atr' in cols, 'Phase 4 pivot_distance_atr column removed in error'; assert 'pivot_zone' in cols, 'Phase 4 pivot_zone column removed in error'; assert cols['stop_price'].nullable is True, 'stop_price MUST be nullable (Blocker #2)'; assert cols['composite_score_raw'].nullable is True, 'composite_score_raw MUST be nullable'; print('RankingSnapshotSchema OK')" && grep -cE "^!/data/journal\.sqlite$" .gitignore</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^\s*stop_price: Series\[float\] = pa\.Field\(gt=0\.0, nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*entry_price: Series\[float\] = pa\.Field\(gt=0\.0, nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*shares: Series\[pd\.Int64Dtype\] = pa\.Field\(ge=0, nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*atr_zone: Series\[str\]" src/screener/persistence.py` returns exactly one match AND the `isin=["in-zone", "extended", "chase, skip", "not_applicable"]` literal appears on the following 1-2 lines
    - `grep -nE "^\s*pivot_distance_atr_breakout: Series\[float\] = pa\.Field\(nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*trail_rule_label: Series\[str\] = pa\.Field\(nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*composite_score_raw: Series\[float\] = pa\.Field\(ge=0\.0, le=100\.0, nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*adr_rejected: Series\[bool\] = pa\.Field\(nullable=True\)" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*rejection_reason: Series\[str\]" src/screener/persistence.py` returns exactly one match
    - `grep -nE "^\s*pivot_distance_atr: Series\[float\] = pa\.Field\(nullable=True\)" src/screener/persistence.py` STILL returns exactly one match (Phase 4 column untouched)
    - `grep -cE "^!/data/journal\.sqlite$" .gitignore` outputs `1`
    - `uv run pytest tests/test_architecture.py -x --no-cov` passes (no import contract breaks)
    - `uv run pytest tests/test_publishers_pipeline.py -x --no-cov` passes (Phase 6 W-Plan05-1 projection test must still pass with the 10 new columns added — projection picks them up automatically when columns exist on `today_panel`)
  </acceptance_criteria>
  <done>
    RankingSnapshotSchema has 36 columns (26 existing + 10 new Phase 7 cols, ALL nullable=True). pivot_distance_atr (Phase 4 sign convention) and pivot_zone (2-state) untouched. atr_zone gains "not_applicable" sentinel. `.gitignore` allowlists `data/journal.sqlite`. No existing test regressions.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add sized_input_cross() fixture + 3 named-test skeleton files (test_sizing/test_journal/test_pipeline_journal)</name>
  <files>tests/conftest.py, tests/test_sizing.py, tests/test_journal.py, tests/test_pipeline_journal.py</files>
  <read_first>
    - tests/conftest.py (lines 443-473 — `synthetic_scored_panel` analog with same cross-section shape; copy fixture pattern)
    - src/screener/indicators/patterns.py (lines 120-134 — `encode_pattern_diagnostics` / `decode_pattern_diagnostics` for the JSON column)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"tests/conftest.py (add sized_input_cross() fixture)"
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Validation Architecture" (the Phase Requirements → Test Map table with all 23 test names)
  </read_first>
  <action>
**A. Append `sized_input_cross()` fixture to `tests/conftest.py`** (after the existing `synthetic_scored_panel` fixture at line 473):

```python


@pytest.fixture(scope="function")
def sized_input_cross() -> pd.DataFrame:
    """5-ticker cross-section with ALL columns sizing.compute_sizing() requires.

    Mitigates RESEARCH §Pitfall 7 (Phase-4 fixtures lack Phase-6+7 columns).
    Function-scope: tests MAY mutate this frame.

    Ticker layout (covers every dispatch branch in Plan 07-02):
      - QULL  → qullamaggie_continuation; ADR%=5.5 (medium tier → 20d SMA trail)
      - VCP1  → minervini_vcp with full depth_sequence diagnostics
      - LEAD  → leader_hold (no pattern; sizing falls back to 1.5×ATR / swing-low)
      - REJC  → qullamaggie_continuation with adr_pct=0.3 → triggers D-06 reject
      - INVS  → leader_hold; tail-risk close==low (Pitfall 6: entry==stop guard)

    Returns a DataFrame indexed by 'ticker' with these columns:
      close, low, high, atr_14, adr_pct, playbook_tag, pattern_diagnostics,
      composite_score, regime_state, regime_score, passes_trend_template,
      rs_rating, trend_template_score, volume_component.
    """
    from screener.indicators.patterns import encode_pattern_diagnostics

    vcp_diag = encode_pattern_diagnostics({
        "type": "vcp",
        "n_contractions": 3,
        "depth_sequence": [0.25, 0.15, 0.08],
        "first_leg_depth": 0.25,
        "final_contraction_depth": 0.08,
        "breakout_vol_multiple": 1.7,
        "breakout_strength": 0.85,
        "pivot_price": 100.0,
        "days_in_consolidation": 18,
    })
    none_diag = encode_pattern_diagnostics({"type": "none"})
    flag_diag = encode_pattern_diagnostics({
        "type": "flag",
        "n_contractions": 0,
        "depth_sequence": [],
        "first_leg_depth": 0.0,
        "final_contraction_depth": 0.0,
        "breakout_vol_multiple": 1.6,
        "breakout_strength": 0.72,
        "pivot_price": 120.0,
        "days_in_consolidation": 12,
    })

    df = pd.DataFrame(
        {
            "ticker": ["QULL", "VCP1", "LEAD", "REJC", "INVS"],
            "close":  [120.0, 100.0, 200.0,  80.0, 50.0],
            "low":    [118.0,  99.0, 198.0,  79.5, 50.0],  # INVS close==low → Pitfall 6
            "high":   [121.5, 101.0, 202.0,  80.5, 50.5],
            "atr_14": [  2.0,   1.5,   4.0,   0.5,  1.0],
            "adr_pct":[  5.5,   4.2,   2.1,   0.3,  3.0],  # REJC adr_pct=0.3 → reject
            "playbook_tag": [
                "qullamaggie_continuation",
                "minervini_vcp",
                "leader_hold",
                "qullamaggie_continuation",
                "leader_hold",
            ],
            "pattern_diagnostics": [flag_diag, vcp_diag, none_diag, flag_diag, none_diag],
            "composite_score": [72.0, 68.5, 65.0, 55.0, 51.0],
            "regime_state": ["Confirmed Uptrend"] * 5,
            "regime_score": [0.85] * 5,
            "passes_trend_template": [True, True, True, True, True],
            "rs_rating": pd.array([92, 88, 95, 82, 80], dtype=pd.Int64Dtype()),
            "trend_template_score": pd.array([8, 7, 8, 6, 6], dtype=pd.Int64Dtype()),
            "volume_component": [0.7, 0.6, 0.5, 0.3, 0.4],
        }
    ).set_index("ticker")
    return df
```

**B. Create `tests/test_sizing.py`** — 11 named pytest.skip skeletons (one per test in RESEARCH §Validation Architecture). EXACT shape:

```python
"""tests/test_sizing.py — Phase 7 SIZ-01..05 unit tests.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-02 (Wave 1).
Every test name comes from RESEARCH §Validation Architecture Test Map verbatim.
"""
from __future__ import annotations

import pytest


def test_shares_formula() -> None:
    """SIZ-01: shares = floor((eq × risk_pct × regime_score) / (entry − stop)), capped at 25% equity."""
    pytest.skip("Plan 07-02")


def test_zero_regime_score_zero_shares() -> None:
    """SIZ-01 / Pitfall 6: regime_score=0 → shares=0 (no div-by-zero)."""
    pytest.skip("Plan 07-02")


def test_shares_nonneg_property() -> None:
    """Property: shares ≥ 0 for any valid input (hypothesis-driven)."""
    pytest.skip("Plan 07-02")


def test_adr_reject_boundary() -> None:
    """SIZ-02: adr_rejected when risk_per_share > adr_dollars (boundary semantics)."""
    pytest.skip("Plan 07-02")


def test_stop_dispatch_per_playbook() -> None:
    """SIZ-03 / SC-2: STOP_HELPERS[tag] is the correct private helper for each playbook tag."""
    pytest.skip("Plan 07-02")


def test_leader_swing_fallback() -> None:
    """SIZ-03: leader_hold falls back to 2×ATR when find_pivots returns empty."""
    pytest.skip("Plan 07-02")


def test_vcp_stop_from_diagnostics() -> None:
    """SIZ-03: minervini_vcp stop = pivot_price × (1 - final_contraction_depth) from pattern_diagnostics."""
    pytest.skip("Plan 07-02")


def test_trail_label_dispatch() -> None:
    """SIZ-04 / D-08: trail label per playbook tag (Qull / VCP / leader)."""
    pytest.skip("Plan 07-02")


def test_qull_trail_speed_tiers() -> None:
    """SIZ-04: Qullamaggie ADR%<4 → 50d SMA, 4–6 → 20d SMA, ≥6 → 10d SMA (boundaries inclusive at 4 and 6)."""
    pytest.skip("Plan 07-02")


def test_atr_zone_boundaries() -> None:
    """SIZ-05 / D-09: pivot_distance_atr=0.66 → in-zone; =1.0 → extended; >1.0 → chase, skip."""
    pytest.skip("Plan 07-02")


def test_pure_function_no_input_mutation() -> None:
    """compute_sizing returns a NEW DataFrame; input is untouched (CLAUDE.md pure-fn rule)."""
    pytest.skip("Plan 07-02")
```

**C. Create `tests/test_journal.py`** — 10 named pytest.skip skeletons:

```python
"""tests/test_journal.py — Phase 7 OUT-04..06 SQLite + trigger tests.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-03 (Wave 1).
"""
from __future__ import annotations

import pytest


def test_immutability_trigger() -> None:
    """OUT-05: UPDATE on any decision column raises sqlite3.IntegrityError with 'decision column immutable'."""
    pytest.skip("Plan 07-03")


def test_outcome_col_not_in_trigger() -> None:
    """OUT-06: UPDATE on exit_price (and other 5 outcome cols) does NOT fire the trigger."""
    pytest.skip("Plan 07-03")


def test_outcome_column_updatable() -> None:
    """OUT-06: the 6 outcome cols (entry_filled, exit_price, exit_date, hold_days, mfe, mae) are nullable and updatable."""
    pytest.skip("Plan 07-03")


def test_idempotent_append() -> None:
    """OUT-04: INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) — mixed insert+duplicate batch → cur.rowcount == inserts only."""
    pytest.skip("Plan 07-03")


def test_features_json_roundtrip() -> None:
    """OUT-05: features_json column round-trips cleanly via json.loads."""
    pytest.skip("Plan 07-03")


def test_features_json_includes_diagnostics() -> None:
    """OUT-05 / D-03: features_json embeds full pattern_diagnostics dict (Phase 6 D-05 keys)."""
    pytest.skip("Plan 07-03")


def test_schema_idempotent_recreates_trigger() -> None:
    """RESEARCH Pitfall 1: DROP TABLE picks + re-call _ensure_picks_schema → trigger STILL fires on UPDATE."""
    pytest.skip("Plan 07-03")


def test_picks_schema_rejects_invalid_playbook_tag() -> None:
    """PicksSchema isin enum rejects 'none' or any tag not in {qullamaggie_continuation, minervini_vcp, leader_hold}."""
    pytest.skip("Plan 07-03")


def test_picks_schema_rejects_invalid_atr_zone() -> None:
    """PicksSchema isin enum rejects atr_zone not in {in-zone, extended, chase, skip}."""
    pytest.skip("Plan 07-03")


def test_journal_cli_idempotent() -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows (filled by Plan 07-05)."""
    pytest.skip("Plan 07-05")
```

**D. Create `tests/test_pipeline_journal.py`** — 4 named pytest.skip skeletons:

```python
"""tests/test_pipeline_journal.py — Phase 7 pipeline + journal integration.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-04 (Wave 2).
"""
from __future__ import annotations

import pytest


def test_pipeline_writes_journal() -> None:
    """OUT-04: run_pipeline(..., write_journal=True) appends rows to data/journal.sqlite."""
    pytest.skip("Plan 07-04")


def test_journal_disabled() -> None:
    """D-01: run_pipeline(..., write_journal=False) emits 'journal_skipped' event, writes zero rows."""
    pytest.skip("Plan 07-04")


def test_rejected_picks_not_in_journal() -> None:
    """SIZ-02 / D-06: ADR-rejected picks excluded from BOTH the snapshot top-N AND the journal."""
    pytest.skip("Plan 07-04")


def test_golden_pipeline_journal() -> None:
    """SC-1: full pipeline run produces deterministic row count + features_json shape."""
    pytest.skip("Plan 07-04")
```

**E. Verify pytest discovery** (this is part of the action, not separate verification):
```bash
uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --collect-only -q 2>&1 | tail -10
```
All 25 tests (11 + 10 + 4) must be collected and skipped (none erroring).
  </action>
  <verify>
    <automated>uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --no-cov -q 2>&1 | tail -5 | grep -E "25 skipped"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE "^def test_" tests/test_sizing.py` outputs `11`
    - `grep -cE "^def test_" tests/test_journal.py` outputs `10`
    - `grep -cE "^def test_" tests/test_pipeline_journal.py` outputs `4`
    - `grep -cE "pytest\.skip\(" tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py | awk -F: '{s+=$2}END{print s}'` outputs `25`
    - `grep -nE "^def sized_input_cross" tests/conftest.py` returns exactly one match
    - `grep -nE "@pytest\.fixture\(scope=.function.\)" tests/conftest.py` returns at least one match on the line immediately preceding `sized_input_cross`
    - `uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --no-cov -q` reports `25 skipped` and zero errors
    - The conftest fixture body includes `encode_pattern_diagnostics` for the VCP, none, and flag rows: `grep -c "encode_pattern_diagnostics" tests/conftest.py` ≥ 1
    - Every test function name from RESEARCH §Validation Architecture Test Map appears verbatim in one of the three files (spot-check: `grep "test_immutability_trigger\|test_stop_dispatch_per_playbook\|test_atr_zone_boundaries\|test_pipeline_writes_journal" tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py` returns 4 matches across the three files)
  </acceptance_criteria>
  <done>
    sized_input_cross fixture added with 5 tickers + 14 columns. Three test files created with 25 named pytest.skip skeletons. pytest collects all 25 without error. Wave 1 plans 07-02 and 07-03 can land bodies in-place.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .env → Settings | User-supplied environment values become typed Python attributes (Pydantic validates type only — semantic bounds are the planner's responsibility) |
| pandera schema → write boundary | New Phase 7 columns become a hard contract; mismatched dtypes from Plan 07-02 / 07-04 will fail loud at write time |
| .gitignore allowlist → repo | `data/journal.sqlite` becomes tracked; future paper-trade rows are committed alongside reports |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-01 | Information disclosure | `data/journal.sqlite` (now committed) | accept | Journal contains synthetic / paper-trade data only — no PII, no API keys, no real account balances (ACCOUNT_EQUITY default is 100_000.0 paper account). User overrides via `.env` if going live; `.env` is gitignored. Documented in commit policy comment in `.gitignore`. |
| T-07-02 | Tampering | RankingSnapshotSchema → snapshot Parquet | mitigate | `strict=True; coerce=False` rejects extra columns AND wrong dtypes at write boundary; pandera errors fail-loud. Phase 6 W-Plan05-1 projection already runs `df[[c for c in schema_cols if c in df.columns]]` so missing Phase 7 cols (during Wave 1 transition) will fail validation cleanly rather than corrupt the snapshot. Nullable=True on sizing cols is intentional (full-universe snapshot per Blocker #1 revision); the `atr_zone` "not_applicable" sentinel preserves isin integrity. |
| T-07-03 | Denial of service | conftest fixture (session leak) | accept | sized_input_cross is function-scope — each test gets a fresh frame; no shared-state contamination across tests. |
| T-07-04 | Repudiation | Settings.JOURNAL_THRESHOLD env override | mitigate | Default 50.0 ships in code; .env.example documents the value; `RankingSnapshotSchema.composite_score_raw: ge=0.0, le=100.0` makes any out-of-range threshold (e.g., 0.5 typo or 500 typo) impossible to satisfy / always satisfied — surfaces in journal row counts immediately. |
| T-07-05 | Elevation of privilege | New pivot_distance_atr_breakout column (computed from `close` and `pattern_diagnostics.pivot_price`) | accept | Pivot price originates from the pure-function patterns layer (Phase 6); no external input feeds it. The new column is read-only output, never an authorization grant. |

ASVS L1 applicable controls: V5.1.4 (output encoding — pandera enum constraints serve this), V8.3.1 (sensitive data inventory — addressed by T-07-01 mitigation). No high-risk threats.
</threat_model>

<verification>
After all three tasks land:

```bash
# Full Phase 7 Wave 0 surface (5 commands; ~10s total)
uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --no-cov -q
uv run pytest tests/test_publishers_pipeline.py --no-cov -q  # Phase 6 regression (W-Plan05-1 projection still works)
uv run pytest tests/test_architecture.py --no-cov -q          # D-23 ALLOWED dict unchanged
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q  # D-24 9-subcommand lock
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q  # FND-04 mutation gate (Phase 6 cross-cutting constraint)

# Settings + .env sanity
uv run python -c "from screener.config import Settings; s = Settings(); print(f'RISK_PCT={s.RISK_PCT}, JOURNAL_THRESHOLD={s.JOURNAL_THRESHOLD}, JOURNAL_DB_PATH={s.JOURNAL_DB_PATH}')"

# Schema sanity
uv run python -c "from screener.persistence import RankingSnapshotSchema; print(len(RankingSnapshotSchema.to_schema().columns), 'columns')"
# Expected: 36 columns
```
</verification>

<success_criteria>
- Settings has RISK_PCT (0.01), JOURNAL_THRESHOLD (50.0), JOURNAL_DB_PATH (data/journal.sqlite).
- ACCOUNT_EQUITY and RISK_PCT_PER_TRADE untouched.
- .env.example mirrors the three new fields without removing the legacy ones.
- RankingSnapshotSchema has 36 columns (was 26; +10 Phase 7 cols: 7 sizing + composite_score_raw + adr_rejected + rejection_reason — ALL nullable=True).
- atr_zone enum includes "not_applicable" sentinel (revision Blocker #2).
- pivot_distance_atr (Phase 4) and pivot_zone (Phase 4) untouched.
- .gitignore allowlists data/journal.sqlite.
- tests/conftest.py exposes sized_input_cross() function-scope fixture with 14 columns × 5 tickers.
- tests/test_sizing.py, tests/test_journal.py, tests/test_pipeline_journal.py exist with 11+10+4 named pytest.skip skeletons.
- All 25 new skeleton tests are collected and report `skipped` (zero errors).
- Phase 6 W-Plan05-1 projection regression test (tests/test_publishers_pipeline.py) still passes.
- D-23 architecture lock unchanged; D-24 CLI surface lock unchanged.
- FND-04 no-look-ahead mutation gate still green.
</success_criteria>

<output>
After completion, create `.planning/phases/07-sizing-finalization-paper-trade-journal/07-01-SUMMARY.md` per the standard template (frontmatter + Tasks Completed + Files Created/Modified + Deviations + Next Plan).
</output>
</content>
</invoke>