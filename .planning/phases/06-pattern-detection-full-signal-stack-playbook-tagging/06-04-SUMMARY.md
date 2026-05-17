---
phase: 06-pattern-detection-full-signal-stack-playbook-tagging
plan: 04
subsystem: signals/qullamaggie + signals/canslim + signals/composite
tags: [phase-6, signals, composite, playbook-tagger, qullamaggie, canslim, wave-2]
dependency_graph:
  requires: [06-01, 06-02, 06-03]
  provides: [passes_qullamaggie_setup_a, canslim_c_overlay, score_pattern_component, score_earnings_component, score_catalyst_component, tag_playbook, PHASE_4_ZEROED_empty, 5-Final-tiebreakerConstants]
  affects: [publishers/pipeline, publishers/snapshot, plan-06-05]
tech_stack:
  added: [numpy (np.select for D-14 cascade)]
  patterns: [Final-locked-constants, panel-in/panel-out, NaN-safe-graceful-degradation, np.select-precedence-encoding]
key_files:
  created:
    - src/screener/signals/qullamaggie.py
    - src/screener/signals/canslim.py
  modified:
    - src/screener/signals/composite.py
    - tests/test_qullamaggie.py
    - tests/test_canslim.py
    - tests/test_composite_full.py
    - tests/test_playbook_tagger.py
    - tests/test_signals_composite.py
    - tests/test_publishers_report.py
decisions:
  - "SIG-02 top-1-2% implemented as percentile rank >= 0.98 OR-gate over 1m/3m/6m (CONTEXT.md Discretion default)"
  - "score_pattern_component/score_earnings_component/score_catalyst_component gracefully return 0.0 when Phase 6 columns absent (legacy panel backward-compat)"
  - "D-14 tiebreaker encoded via np.select conditions=[qull_mask, mvp_mask, ldr_only] — qull_mask first so earlier condition wins (checker W8)"
  - "test_publishers_report.py test_per_pick_breakdown_format_d04 updated: PHASE_4_ZEROED now empty so no breakdown placeholders; hardcoded narrative (Phase 6) strings remain (Plan 05 responsibility)"
  - "test_signals_composite.py test_zeroed_components updated: asserts PHASE_4_ZEROED == frozenset() and graceful 0.0 degradation on minimal panels"
metrics:
  duration: "~25 minutes (2026-05-17T13:41:00Z to 2026-05-17T14:13:29Z)"
  completed: "2026-05-17T14:13:29Z"
  tasks_completed: 3
  files_modified: 9
---

# Phase 6 Plan 04: Full Signal Stack + Playbook Tagger Summary

**One-liner:** Two new pure-function signal modules (qullamaggie.py + canslim.py) + composite.py full activation with PHASE_4_ZEROED shrunk to frozenset(), 5 Final tie-breaker constants, 3 component helpers, and tag_playbook delivering D-14/D-15 playbook tagging, landing 15 new GREEN tests (4 + 3 + 3 + 5).

---

## What Was Delivered

### Task 1: signals/qullamaggie.py + 4 GREEN tests (commit bf81127)

`src/screener/signals/qullamaggie.py` created:

| Symbol | Value | Purpose |
|--------|-------|---------|
| `QULL_TOP_PCT_THRESHOLD` | 0.98 | Top 2% percentile cutoff for 1m/3m/6m return ranks |
| `QULL_MIN_DOLLAR_VOLUME` | 1_500_000.0 | Minimum 20-day average dollar volume |
| `QULL_MIN_ADR_PCT_SCAN` | 4.0 | Minimum ADR%(20) for scan gate |

**`passes_qullamaggie_setup_a(panel) -> pd.DataFrame`** per SIG-02:
- Gate 1: cross-sectional `pct_change(21/63/126).rank(pct=True) >= 0.98` (OR-gate over 3 windows)
- Gate 2: `(close * volume).rolling(20).mean() > $1.5M` (grouped by ticker to avoid index contamination)
- Gate 3: `adr_pct >= 4.0`
- All gates AND-ed with `.fillna(False)` NaN-safe coercion (per Pitfall 3 analog from minervini.py)
- Appends `qullamaggie_score: Int64 0/1`

**4 GREEN tests:**
- `test_setup_a_top_2pct_filter`: hero ticker with 60%+ 3m return passes; all others (tiny ADV) fail
- `test_setup_a_dollar_volume_filter`: dominant-return ticker with close×0.5 ADV fails liquidity gate
- `test_setup_a_adr_pct_filter`: dominant-return + high ADV ticker with ADR%=3.5 fails range gate
- `test_setup_a_combined_and_gate`: all-conditions-true → score=1; reset ADR% → 0; reset volume → 0

Architecture compliance: no `data/` imports (D-23); mypy --strict clean (no errors in qullamaggie.py).

### Task 2: signals/canslim.py + 3 GREEN tests (commit cbf3470)

`src/screener/signals/canslim.py` created:

| Symbol | Value | Purpose |
|--------|-------|---------|
| `CANSLIM_C_MIN_EPS_YOY` | 0.25 | Minimum quarterly EPS YoY growth for C component |

**`canslim_c_overlay(panel, fundamentals, as_of_date) -> pd.DataFrame`** per SIG-03 / D-18:
- Looks up most-recent `eps_yoy_growth` per ticker from `fundamentals` (already lag-filtered by caller)
- `canslim_c_passes = True` iff `eps_yoy_growth >= 0.25`
- Missing tickers or NaN eps → `False` (honest-failure per D-13b)
- Appends `canslim_c_passes: bool`

**D-18 de-dup (structural):** Source contains no references to `rs_rating` (L), `regime_state` (M), or `regime_score` (M) — verified by AST scan in `test_no_double_count`.

**3 GREEN tests:**
- `test_c_component_eps_yoy_25pct_passes`: AAPL with eps_yoy_growth=0.30 → canslim_c_passes=True
- `test_c_component_eps_yoy_below_25pct_fails`: eps_yoy_growth=0.10 → canslim_c_passes=False
- `test_no_double_count`: source scan confirms no rs_rating/regime_state/regime_score references

Architecture compliance: no `data/` imports (D-23); mypy --strict clean.

### Task 3: composite.py extension + 8 GREEN tests (commit 8ef7f25)

`src/screener/signals/composite.py` extended with surgical precision:

#### PHASE_4_ZEROED shrink (D-16)
```
PHASE_4_ZEROED: Final[frozenset[str]] = frozenset()
# was: frozenset({"pattern", "earnings", "catalyst"})
```
All six components are now live. Report breakdown placeholders (`Pattern=--(Phase 6)` etc.) auto-disappeared.

#### 5 Final tie-breaker constants (D-13)
```python
QULL_MAX_BARS: Final[int] = 25
QULL_MIN_ADR_PCT: Final[float] = 5.0
MINERVINI_MIN_BARS: Final[int] = 25
MINERVINI_MAX_FINAL_CONTRACTION_PCT: Final[float] = 8.0
LEADER_MIN_RS: Final[int] = 90
```

#### 3 component helpers (Phase 6 D-16 full activation)

**`score_pattern_component(panel)`** — D-17:
- Returns `breakout_strength` for VCP/flag picks (when `vcp_passes | flag_passes`), else `0.0`
- Graceful degradation: if columns absent → returns `pd.Series(0.0, index=panel.index)`

**`score_earnings_component(panel)`** — D-18:
- Returns `canslim_c_passes.astype(float)` (1.0 or 0.0)
- Graceful degradation: if column absent → returns `pd.Series(0.0, ...)`

**`score_catalyst_component(panel)`** — D-11:
- `(earnings_prox + crossed_52w + insider) / 3.0` clipped to [0, 1]
- Checker W5: `earnings_prox = 1 if 0 <= days_to_next_earnings <= 14` (negative days = stale)
- Graceful degradation: if all three columns absent → returns `pd.Series(0.0, ...)`

#### Scoring loop — Pitfall 6 protection (VERIFIED)

The loop body at lines 172-174 is **bytewise unchanged** from Phase 4:
```python
composite = pd.Series(0.0, index=panel.index)
for key, w in weights.items():
    composite = composite + w * out[f"{key}_component"]
out["composite_score"] = (composite * 100.0).astype(float)
```
Grep gate confirmed: `grep -F "for key, w in weights.items():"` and `grep -F 'composite = composite + w * out[f"{key}_component"]'` both match.

#### tag_playbook() function (CMP-02..04 / D-14 / D-15)

```python
def tag_playbook(panel: pd.DataFrame) -> pd.DataFrame:
```

Emits 4 new columns: `qullamaggie_score`, `minervini_score`, `leader_hold_score`, `playbook_tag`.

**D-14 tie-break (checker W8):**
```python
conditions = [qull_mask, mvp_mask, ldr_only]  # qull_mask FIRST = highest precedence
choices = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
out["playbook_tag"] = np.select(conditions, choices, default="none")
```
Earlier conditions win in `np.select` → Qullamaggie wins when both Qull and Minervini fire.

**D-15 leader_hold:** `passes_trend_template AND rs_rating >= 90 AND pattern_type == "none"`

**D-15 none-tag:** Picks failing all three scores get `playbook_tag = "none"` (Plan 05 excludes from report).

**8 GREEN tests:**
- `test_phase_4_zeroed_empty`: `PHASE_4_ZEROED == frozenset()`
- `test_all_components_live`: all three Phase 6 components non-zero on full panel
- `test_weights_loop_unchanged`: source scan confirms verbatim loop body (Pitfall 6)
- `test_tag_values_valid`: all emitted tags in `{"qullamaggie_continuation","minervini_vcp","leader_hold","none"}`
- `test_d14_tiebreaker`: VCP bars=12 + adr_pct=6.0 + final_contraction=5% → qullamaggie_continuation AND minervini_score=1 (both fired; Qull wins)
- `test_d15_leader_hold`: passes_TT + rs=92 + type="none" → leader_hold
- `test_d15_none_tag_excluded_from_report`: failing-all-three → playbook_tag="none"
- `test_final_constants_locked`: all 5 D-13 constants at verbatim values with `Final[` annotation

---

## Preregistration CI Gate (CMP-01 / D-21)

`scripts/check_preregistration.py` result: **"Preregistration check passed."**

DEFAULT_WEIGHTS values unchanged:
```python
{"rs": 0.25, "trend": 0.20, "pattern": 0.20, "volume": 0.10, "earnings": 0.15, "catalyst": 0.10}
```

---

## Test Results Summary

| Category | Count | Status |
|----------|-------|--------|
| qullamaggie SIG-02 tests | 4 | GREEN |
| canslim C-only overlay tests | 3 | GREEN |
| composite full activation tests | 3 | GREEN |
| playbook tagger tests | 5 | GREEN |
| **New tests total** | **15** | **ALL GREEN** |
| Phase 4 composite regression (test_signals_composite.py) | 7 | GREEN |
| Minervini regression | 6 | GREEN |
| No-look-ahead gate (FND-04) | 2 | GREEN |
| Full suite | 188 passed, 4 skipped | CLEAN |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Graceful degradation for missing Phase 6 columns**
- **Found during:** Task 3 regression testing
- **Issue:** `score_pattern_component`, `score_earnings_component`, `score_catalyst_component` raised `KeyError` when called with Phase-4-era minimal panels (only `rs_rating`, `trend_template_score`, `dryup_ratio`). This broke 5 existing `test_signals_composite.py` tests.
- **Fix:** Added column-existence guards in each of the three helpers; missing columns return `pd.Series(0.0, index=panel.index)`. Pipeline.py (Plan 05) will always provide all columns; the graceful fallback defends legacy/test panels without changing behavior on full panels.
- **Files modified:** `src/screener/signals/composite.py`
- **Commit:** 8ef7f25

**2. [Rule 1 - Bug] test_signals_composite.py::test_zeroed_components asserted old PHASE_4_ZEROED value**
- **Found during:** Task 3 regression testing
- **Issue:** Test asserted `PHASE_4_ZEROED == frozenset({"pattern","earnings","catalyst"})` — the Phase 4 value. After D-16, `PHASE_4_ZEROED == frozenset()`.
- **Fix:** Updated assertion to `PHASE_4_ZEROED == frozenset()` and updated docstring to reflect Phase 6 behavior.
- **Files modified:** `tests/test_signals_composite.py`
- **Commit:** 8ef7f25

**3. [Rule 1 - Bug] test_publishers_report.py::test_per_pick_breakdown_format_d04 asserted Phase 4 placeholder behavior**
- **Found during:** Post-task full suite run
- **Issue:** Test asserted `"Pattern=" in md and "(Phase 6)" in md` (Phase 4 placeholder presence). After D-16 empties PHASE_4_ZEROED, `_format_breakdown` no longer emits those placeholder strings in the breakdown code block.
- **Fix:** Updated test to assert Phase-4-live components present AND no `Pattern=--(Phase 6)` in breakdown. Acknowledged that hardcoded narrative `(Phase 6)` strings in the report (playbook/catalysts stubs, footer) are Plan 05 responsibilities.
- **Files modified:** `tests/test_publishers_report.py`
- **Commit:** 3b7ec8d

**4. [Rule 2 - Missing Critical Functionality] test_canslim.py AST path used relative path**
- **Found during:** Task 2 test execution
- **Issue:** `Path("src/screener/signals/canslim.py").read_text()` used a relative path; tests run from the main repo dir (not the worktree), causing FileNotFoundError.
- **Fix:** Changed to `Path(__file__).resolve().parent.parent / "src" / "screener" / "signals" / "canslim.py"` (absolute path relative to test file).
- **Files modified:** `tests/test_canslim.py`
- **Commit:** cbf3470

---

## Architecture Compliance

- `tests/test_architecture.py::test_signals_indicators_cannot_import_data` — PASSED (D-23 intact)
- `tests/test_backtest_no_lookahead.py` — PASSED (FND-04 gate preserved)
- mypy --strict on signals/: No issues in 5 source files (pre-existing persistence.py error is out of scope)
- No `print()` calls in any new module
- No `data/` imports in `signals/qullamaggie.py` or `signals/canslim.py`
- D-18 de-dup: `canslim.py` source confirmed free of `rs_rating`, `regime_state`, `regime_score`

---

## Key Links Implemented

| Link | Pattern | Status |
|------|---------|--------|
| `composite.py::PHASE_4_ZEROED` → `scripts/check_preregistration.py` | `PHASE_4_ZEROED.*frozenset\(\)` | VERIFIED |
| `composite.py::tag_playbook` → `publishers/snapshot.py` | `playbook_tag` column | READY for Plan 05 |
| `canslim.py` → `screener.data` | MUST NOT import (D-23) | ENFORCED |
| `composite.py` scoring loop | `for key, w in weights.items():` | BYTEWISE UNCHANGED |

---

## Per-Task Verification Map (06-VALIDATION.md update)

| Task ID | Test | Status | Commit |
|---------|------|--------|--------|
| 06-04-1-1 | test_setup_a_top_2pct_filter | PASS | bf81127 |
| 06-04-1-2 | test_setup_a_dollar_volume_filter | PASS | bf81127 |
| 06-04-1-3 | test_setup_a_adr_pct_filter | PASS | bf81127 |
| 06-04-1-4 | test_setup_a_combined_and_gate | PASS | bf81127 |
| 06-04-2-1 | test_c_component_eps_yoy_25pct_passes | PASS | cbf3470 |
| 06-04-2-2 | test_c_component_eps_yoy_below_25pct_fails | PASS | cbf3470 |
| 06-04-2-3 | test_no_double_count | PASS | cbf3470 |
| 06-04-3-1 | test_phase_4_zeroed_empty | PASS | 8ef7f25 |
| 06-04-3-2 | test_all_components_live | PASS | 8ef7f25 |
| 06-04-3-3 | test_weights_loop_unchanged | PASS | 8ef7f25 |
| 06-04-3-4 | test_tag_values_valid | PASS | 8ef7f25 |
| 06-04-3-5 | test_d14_tiebreaker | PASS | 8ef7f25 |
| 06-04-3-6 | test_d15_leader_hold | PASS | 8ef7f25 |
| 06-04-3-7 | test_d15_none_tag_excluded_from_report | PASS | 8ef7f25 |
| 06-04-3-8 | test_final_constants_locked | PASS | 8ef7f25 |

---

## Known Stubs

None. All signal modules deliver real computation. The `score_pattern_component`, `score_earnings_component`, `score_catalyst_component` helpers return 0.0 when Phase 6 columns are absent — this is graceful degradation, not a stub. The real values flow through when pipeline.py (Plan 05) provides all columns.

The `tag_playbook` function emits `playbook_tag = "none"` for picks with no matching playbook criteria — this is the correct behavior per D-15 (these picks are excluded from the report by Plan 05's filter).

---

## Threat Flags

None. No new network endpoints, auth paths, or schema changes at trust boundaries. The five `Final[...]` tie-breaker constants address T-06-18 (in-sample tuning defense) as planned.

---

## Self-Check: PASSED

Files verified:
- `src/screener/signals/qullamaggie.py` — FOUND
- `src/screener/signals/canslim.py` — FOUND
- `src/screener/signals/composite.py` — FOUND (extended)
- `tests/test_qullamaggie.py` — FOUND
- `tests/test_canslim.py` — FOUND
- `tests/test_composite_full.py` — FOUND
- `tests/test_playbook_tagger.py` — FOUND

Commits verified:
- bf81127 feat(06-04): signals/qullamaggie.py + 4 GREEN tests — FOUND
- cbf3470 feat(06-04): signals/canslim.py + 3 GREEN tests — FOUND
- 8ef7f25 feat(06-04): composite.py extension + 8 GREEN tests — FOUND
- 3b7ec8d fix(06-04): update test_publishers_report — FOUND

Tests: 188 passed, 4 skipped — VERIFIED
Preregistration CI: PASSED
FND-04 no-look-ahead: PASSED
Architecture D-23: PASSED
mypy --strict signals/: PASSED
