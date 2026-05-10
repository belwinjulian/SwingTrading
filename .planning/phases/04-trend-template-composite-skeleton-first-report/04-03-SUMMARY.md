---
phase: "04"
plan: "03"
subsystem: signals
tags: [signals, composite, weights, SIG-04, FND-05, M2-extension-seam, tdd]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [DEFAULT_WEIGHTS Final dict, PHASE_4_ZEROED frozenset, score() pure function, 7 SIG-04 tests]
  affects: [04-04-publishers, 04-05-preregistration]
tech_stack:
  added: []
  patterns: [Final constant importable without pandas, weights-dict iteration seam (D-13), frozenset for Phase 4 placeholder tracking, Hypothesis property test for [0,100] range invariant]
key_files:
  created:
    - src/screener/signals/composite.py
    - tests/test_signals_composite.py
  modified: []
decisions:
  - "DEFAULT_WEIGHTS: Final[dict[str, float]] at module top-level — importable by scripts/check_preregistration.py without instantiating any pandas frame (D-13, FND-05)"
  - "PHASE_4_ZEROED: Final[frozenset[str]] = {pattern, earnings, catalyst} — report renderer iterates this to emit Phase 6 placeholder labels (D-01, D-04)"
  - "score() iterates weights.items() using f-string f'{key}_component' column lookup — no hardcoded column refs in scoring loop (D-13 M2 extension seam)"
  - "Docstring phrase 'remain unchanged' replaced with 'need no changes' to avoid false positive in grep -ilE 'ema' CI check"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 2
  files_changed: 2
---

# Phase 04 Plan 03: Composite Scorer (signals/composite.py) Summary

**One-liner:** Weights-dict composite scorer with DEFAULT_WEIGHTS Final dict (D-12 verbatim), PHASE_4_ZEROED frozenset (D-01 placeholder tracker), and weights.items() scoring loop (D-13 M2 extension seam) — 7 SIG-04 tests including Hypothesis property and M2 monkey-patch seam proof.

## What Was Built

### Task 1: src/screener/signals/composite.py

New pure-function module with three public names:

**DEFAULT_WEIGHTS** — `Final[dict[str, float]]` with the exact D-12 values:
```python
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,    # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,   # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,   # zeroed in Phase 4 (D-01); active in Phase 6
}
```
Sum = 1.00 exactly. Importable by `scripts/check_preregistration.py` without instantiating any pandas frame.

**PHASE_4_ZEROED** — `Final[frozenset[str]] = frozenset({"pattern", "earnings", "catalyst"})`. Report renderer (Plan 04-04) iterates this set to render `—(Phase 6)` labels per D-04. Removing a key in Phase 6 automatically removes the placeholder.

**score(panel, weights=DEFAULT_WEIGHTS)** — Pure function (D-16). Panel-in / panel-out with 7 new columns:
- `rs_component`: `rs_rating / 99.0`, NaN → 0.0
- `trend_component`: `trend_template_score / 8.0`, NaN → 0.0
- `volume_component`: `clip(1 - (dryup_ratio - 0.5) / 1.5, 0, 1)`, NaN → 0.0 (D-02 + Pitfall 4)
- `pattern_component`: 0.0 (Phase 4 placeholder, D-01)
- `earnings_component`: 0.0 (Phase 4 placeholder, D-01)
- `catalyst_component`: 0.0 (Phase 4 placeholder, D-01)
- `composite_score`: Σ weights[k] * <k>_component * 100, in [0, 55] for Phase 4 (sum of live weights = 0.55)

**D-13 iteration pattern (line 113):**
```python
for key, w in weights.items():
    composite = composite + w * out[f"{key}_component"]
```
No hardcoded column references inside the scoring loop. The f-string `f"{key}_component"` pattern means adding `"ml_probability"` to DEFAULT_WEIGHTS in M2 requires ZERO refactor of the loop body.

**Validation (lines 84-90):**
- Unknown keys: `set(weights) - set(DEFAULT_WEIGHTS)` → `ValueError("Unknown weight keys: {sorted(unknown)}")`
- Sum check: `abs(sum(weights.values()) - 1.0) > 1e-6` → `ValueError("Weights must sum to 1.0; got {sum}")`

Architecture compliance (D-16): imports only `from __future__ import annotations`, `from typing import Final`, `import pandas as pd`. No screener.* imports.

### Task 2: tests/test_signals_composite.py

7 SIG-04 tests, all passing:

| Test | Validates |
|------|-----------|
| `test_unknown_weight_key_raises` | T-4-08: unknown key rejected with sorted-keys message |
| `test_weight_sum_assertion` | T-4-09 + Pitfall 11: sum != 1.0 rejected |
| `test_zeroed_components` | D-01: pattern/earnings/catalyst = 0.0 in Phase 4 |
| `test_extension_seam` (line 72) | D-13: M2 monkey-patch proves loop needs no code change |
| `test_score_range_property` | Pitfall 11: Hypothesis property — composite_score in [0,100] for 50 random inputs |
| `test_score_emits_all_seven_new_columns` | SIG-04 output schema contract |
| `test_volume_component_d02_anchors` | D-02 formula: dryup=0.5→1.0, dryup=2.0→0.0, NaN→0.0 |

**M2 Extension Seam Proof (test_extension_seam):** The test monkey-patches DEFAULT_WEIGHTS to include `"ml_probability"`, prepopulates `panel_with_ml["ml_probability_component"] = 0.5`, and calls `score(panel_with_ml, m2_weights)`. The scoring loop consumes `ml_probability_component` without any code change — proving the D-13 seam is real, not aspirational.

## Test Coverage

| Test | Result |
|------|--------|
| test_unknown_weight_key_raises | PASS |
| test_weight_sum_assertion | PASS |
| test_zeroed_components | PASS |
| test_extension_seam | PASS |
| test_score_range_property (Hypothesis, 50 examples) | PASS |
| test_score_emits_all_seven_new_columns | PASS |
| test_volume_component_d02_anchors | PASS |
| test_architecture.py (D-16 contract) | PASS (3 passed) |

Full suite with indicator tests: 27 passed, 98% coverage.

## CI Gate Status

| Gate | Result |
|------|--------|
| `grep -ilE "ema" src/screener/signals/composite.py` | PASS (0 matches) |
| `test_layer_import_contract` (D-16) | PASS |
| `uv run mypy src/screener/signals/composite.py` | PASS (clean, --strict) |
| `uv run ruff check src/screener/signals/composite.py` | PASS |
| `uv run ruff check tests/test_signals_composite.py` | PASS (3 auto-fixed: import sort, unused numpy, Yoda condition) |
| 7 tests in test_signals_composite.py | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring phrase "remain unchanged" contained "ema" substring**
- **Found during:** Task 1 acceptance criteria verification
- **Issue:** The docstring line `"over weights.items() remain unchanged"` triggered `grep -ilE "ema"` because "remain" contains the substring "ema" (r-e-m-a-i-n). The CI gate for composite.py would have false-positived.
- **Fix:** Changed to `"over weights.items() need no changes"` — preserves meaning, no ema substring.
- **Files modified:** `src/screener/signals/composite.py`
- **Commit:** dfe59f4

**2. [Rule 2 - Ruff Auto-fix] Test file had 3 fixable style issues**
- **Found during:** Task 2 verification
- **Issues:** unsorted imports, unused `numpy` import, Yoda condition in assert
- **Fix:** `ruff check --fix && ruff format` auto-resolved all 3
- **Files modified:** `tests/test_signals_composite.py`
- **Commit:** 7bda411

**3. [Pre-existing Plan Inconsistency - Documentation] Acceptance criteria says panel column grep count = 3, actual = 4**
- **Issue:** The plan's acceptance criteria says `grep -cE "panel[...]" composite.py` outputs `3`, but the plan's own template docstring contains an example usage `panel["rs_rating"]` (line 77 of composite.py). This makes the count 4 (1 docstring + 3 code), not 3.
- **Resolution:** The implementation correctly follows the plan template. The discrepancy is in the plan's acceptance criteria (the number should be 4). The important contract — that panel column references appear ONLY in the component-derivation section, not in the scoring loop — is verified and passing. No code change needed.

## Known Stubs

The following are intentional Phase 4 placeholders per D-01, tracked by `PHASE_4_ZEROED`:

| Component | File | Value | Phase that resolves |
|-----------|------|-------|---------------------|
| `pattern_component` | `src/screener/signals/composite.py:103` | `0.0` | Phase 6 |
| `earnings_component` | `src/screener/signals/composite.py:104` | `0.0` | Phase 6 |
| `catalyst_component` | `src/screener/signals/composite.py:105` | `0.0` | Phase 6 |

These placeholders are by design (D-01). The effective composite score range in Phase 4 is approximately [0, 55] since pattern (20%), earnings (15%), and catalyst (10%) are zeroed. Phase 6 removes these entries from `PHASE_4_ZEROED` and wires real values — the report renderer's placeholder labels disappear automatically.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The composite scorer is a pure-function module with no I/O.

STRIDE T-4-08 and T-4-09 mitigations are implemented:
- T-4-08 (unknown keys): explicit `set(weights) - set(DEFAULT_WEIGHTS)` check before any column lookup
- T-4-09 (weights sum != 1.0): explicit `abs(sum(weights.values()) - 1.0) > 1e-6` check before scoring

## Self-Check: PASSED

Verified files exist:
- `src/screener/signals/composite.py` contains `DEFAULT_WEIGHTS: Final[dict[str, float]]`, `PHASE_4_ZEROED: Final[frozenset[str]]`, `def score`, `for key, w in weights.items()`
- `tests/test_signals_composite.py` contains all 7 required test functions

Verified commits exist:
- `dfe59f4` — feat(04-03): add signals/composite.py
- `7bda411` — test(04-03): add test_signals_composite.py
