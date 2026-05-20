# Phase 4: Trend Template, Composite Skeleton & First Report - Research

**Researched:** 2026-05-10
**Domain:** Pure-function signal layer + Markdown publisher + Parquet snapshot + CI preregistration gate
**Confidence:** HIGH

## Executive Summary

- **The indicator panel is missing two columns that Phase 4 requires.** `build_panel()` does NOT currently emit `high_52w` or `low_52w`. They must be added to `indicators/trend.py` (where SMAs already live) so Trend Template conditions 6 and 7 can compute. This is the single most consequential pre-flight finding. [VERIFIED: grep against `src/screener/indicators/*.py` — zero matches for `high_52w` / `low_52w` / `MAX(High` / `MIN(Low`]
- **The 9-subcommand CLI surface already includes `score` and `report`.** No new subcommand is needed and none is allowed (`tests/test_cli_smoke.py::D14_SUBCOMMANDS` is the lock). The cleanest wiring: `score` populates `data/snapshots/YYYY-MM-DD.parquet`, `report` reads the snapshot and writes `reports/YYYY-MM-DD.md`. The Makefile chains them via `make report: rank report-md` (or just teaches `report` to call `score` internally). [VERIFIED: `src/screener/cli.py` lines 198–214]
- **The composite weights dict belongs in `signals/composite.py` as a module-level `Final` constant.** Importable by both `composite.score()` and `scripts/check_preregistration.py` without pandas overhead (the script imports the constant only). Naming and key set MUST be locked at Phase 4 freeze: `{"rs", "trend", "pattern", "volume", "earnings", "catalyst"}`. M2 adds `"ml_probability"` as a 7th key without breaking the seam. [CITED: D-13, D-12, CONTEXT.md]
- **The soft regime gate is a separate `apply_regime_gate()` step, not embedded in `composite.score()`.** Embedding it makes Phase 7's hard-gate transition (REG-03 amendment, deferred section) a destructive change to a pure function with strict mypy, while a separate step swaps the gate function via dependency injection or a feature flag. Keeps `composite.score()` testable in isolation against deterministic inputs. [ASSUMED — design choice; alternative is acceptable but Phase 7 transition is harder]
- **Pass-rate hard-fail belongs in a dedicated `validate_run()` step in the publisher pipeline, not inside the composite scorer.** Composite stays pure (no `sys.exit`). The publisher orchestrator inspects `pass_rate` + `regime_state`, raises `typer.Exit(code=1)` on the data-quality combination, and never writes the report or snapshot when the gate fails. This mirrors the Phase 2 pattern for the 95% universe-coverage health gate (see `src/screener/cli.py` lines 130–144). [VERIFIED: existing CLI pattern]

**Primary recommendation:** Plan in 4 waves. Wave 0: add `high_52w`/`low_52w` to `indicators/trend.py` + extend `Settings` with three new fields (`REPORT_TOP_N`, `TREND_TEMPLATE_PASS_RATE_WARN`, `TREND_TEMPLATE_PASS_RATE_FAIL`). Wave 1: `signals/minervini.py` (pure) + `signals/composite.py` (pure, with `DEFAULT_WEIGHTS` Final dict). Wave 2: `publishers/report.py` + `publishers/snapshot.py` + extend `persistence.py` with `RankingSnapshotSchema` and `write_snapshot_atomic()`. Wave 3: wire `score` and `report` CLI bodies + `scripts/check_preregistration.py` + CI step + freeze the preregistration doc with the git hash.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 52w high/low computation | `indicators/` (trend.py) | — | Same per-ticker rolling pattern as SMAs; keeps consumed by both Trend Template (cond 6, 7) and pivot-zone annotation. Pure function. |
| Trend Template gate | `signals/` (minervini.py) | — | Pure function, panel-in / panel-out per architecture test. Reads only indicator panel columns. |
| Composite scoring | `signals/` (composite.py) | — | Pure function. M2 extension seam (D-13). Consumes minervini + RS columns + dryup_ratio. |
| Regime score multiplication (soft gate) | `publishers/` orchestrator | `signals/composite.py` (alternative) | Keeping it OUT of `composite.score()` preserves purity and lets Phase 7's hard-gate swap be additive. |
| Pivot-zone annotation | `publishers/` (report.py helper) | — | Display-only label derived from `(close - high_52w) / atr`. Not a signal. |
| Pass-rate sanity check | `publishers/` (validate_run) | — | Cross-cutting data-quality gate; combines composite output + regime state; can `typer.Exit(1)`. |
| Markdown report writing | `publishers/report.py` | — | I/O; writes `reports/YYYY-MM-DD.md`. |
| Snapshot Parquet writing | `persistence.py` (writer) + `publishers/snapshot.py` (caller) | — | Snapshot writer follows `write_rs_snapshot_atomic` pattern; publisher orchestrates the call. |
| Preregistration CI script | `scripts/check_preregistration.py` (NEW dir) | — | Pure preflight, runs in CI before tests. Must NOT import pandas — pure-stdlib script. |
| `make report` CLI wiring | `cli.py` (`score` + `report` subcommands) | — | Reuses the locked surface. No 10th subcommand. |

## Standard Stack

### Core (already locked from prior phases — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.2.x | DataFrame operations for the panel | Phase 1 stack lock |
| pandas-ta-classic | 0.4.47 | SMA/ATR (already used) — no new functions needed | Pure Python; verified live `import pandas_ta_classic as ta; ta.sma` exists |
| pandera | 0.31.1 | `RankingSnapshotSchema` for snapshot Parquet I/O | D-09 enforces pandera at every I/O boundary |
| pydantic-settings | 2.14.x | Three new Settings fields (additive extension per D-12 carry-forward) | Phase 1 D-15 + Phase 2 D-20 + Phase 3 D-12 precedent |
| structlog | 25.5.x | `trend_template_pass_rate_high`, `composite_scored`, `report_written`, `snapshot_written`, `preregistration_check_failed` events | Phase 1 D-15; CLAUDE.md "no print()" rule |
| typer | 0.25.x | `score` and `report` subcommand bodies (already stubbed) | Phase 1 D-14 surface |
| pyarrow | 17.x | Snapshot Parquet write | Phase 2 standard |

### New for Phase 4

**No new third-party deps.** Every Phase 4 capability is buildable from the existing `pyproject.toml` lock. This is a deliberate "code-only phase" — the hardest decisions are about API shape, not library selection.

### Verification

```bash
# Verified live 2026-05-10 in this research session:
$ uv run python -c "import pandas_ta_classic as ta; print('SMA available:', hasattr(ta, 'sma')); print('version:', ta.__version__)"
SMA available: True
version: 0.4.47
```
[VERIFIED: this session]

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Missing components contribute zero. Pattern (20%), Earnings (15%), Catalyst (10%) are zeroed in Phase 4. Phase 4 max composite is ~55/100. Phase 6 fills the gaps.
- **D-02:** Volume component is live in Phase 4 using `dryup_ratio`. Mapping: `dryup_ratio ≤ 0.5 → 1.0`, `dryup_ratio ≥ 2.0 → 0.0`, linear between. 10% weight. Concrete formula: `score = clip(1 - (dryup_ratio - 0.5) / 1.5, 0, 1)`.
- **D-03:** Regime gate is soft — `composite_score *= regime_score`. NOT a hard zero. Picks still appear in Correction; scores compress.
- **D-04:** Per-pick breakdown shows all six components with live vs `—(Phase 6)` placeholder labels. Format: `RS=92 | Trend=7/8 | Pattern=—(Phase 6) | Volume=0.7 | Earnings=—(Phase 6) | Catalyst=—(Phase 6)`.
- **D-05:** 52-week high (`MAX(High, 252)`) is the Phase 4 pivot proxy. Column label in report: `ATR from 52w high (Phase 4 proxy)`.
- **D-06:** In-zone vs chase: `≤ 1×ATR above 52w high → "in-zone"`, `> 1×ATR → "chase, skip"`. Column: `pivot_zone`.
- **D-07:** Alert dual-channel — structlog warning + report banner — when `pass_rate > 0.25`.
- **D-08:** Hard fail (`exit 1`, no report, no snapshot) when `pass_rate > 0.25 AND regime_state == "Correction"`.
- **D-09:** Weights consistency enforced by grep-diff CI script `scripts/check_preregistration.py`. Failure message format: `"Weight mismatch: composite.py rs=0.30 vs doc rs=0.25"`.
- **D-10:** Preregistration doc records git hash via `Frozen at commit: <sha>` line.
- **D-11:** SMA not EMA (already CI-enforced from Phase 3).
- **D-12:** Composite weights are RS 25 / Trend 20 / Pattern 20 / Volume 10 / Earnings 15 / Catalyst 10. Pre-registered, not backtested.
- **D-13:** `signals/composite.py` accepts a weights dict — not hardcoded column references.
- **D-14:** Signal execution at next-bar open (Phase 5 enforces).

### Claude's Discretion

- `make report` CLI wiring — planner picks (recommendation in section 10 below).
- Snapshot schema column set — minimum: ticker, composite_score, rank, passes_trend_template, trend_template_score, regime_score, regime_state, pivot_zone (full recommendation in section 8).
- Top-N default: N=15. Expose as `Settings.REPORT_TOP_N: int = 15`.
- Report Markdown structure (table vs sections, no emoji per CLAUDE.md).

### Deferred Ideas (OUT OF SCOPE)

- Full playbook tagging (Qullamaggie / Minervini VCP / leader-hold) — Phase 6.
- Catalyst flag annotations (insider buys, earnings proximity) — Phase 6.
- Hard regime gate (zero composite in Correction) — Phase 7 or post paper-trade.
- `make report` failure alerting via GitHub Actions — Phase 8.
- Per-regime / per-playbook report breakdowns — Phase 5/6.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-05 | Pre-registration doc + CI grep-diff gate | Section 9 (preregistration script design); section on `DEFAULT_WEIGHTS` Final constant in section 2 |
| SIG-01 | Trend Template — 8 conditions, pass/fail + 0–8 score | Sections 1, 11 (test design); column dependency on `high_52w`/`low_52w` from new `indicators/trend.py` additions |
| SIG-04 | Composite skeleton accepting weights dict | Section 2 (weights-dict API design); Section 12 (architecture test compliance) |
| OUT-01 | Daily Markdown report at `reports/YYYY-MM-DD.md` | Section 7 (Markdown layout prototype) |
| OUT-02 | Per-pick blocks with breakdown, ATR distance, in-zone/chase | Sections 5 (pivot proxy), 7 (per-pick block prototype) |
| OUT-03 | Full ranked snapshot at `data/snapshots/YYYY-MM-DD.parquet` | Section 8 (snapshot schema + atomic write) |

## Project Constraints (from CLAUDE.md)

| Directive | Source | Enforcement Hook |
|-----------|--------|------------------|
| **Use SMA, not EMA** in Trend Template | CLAUDE.md §"Critical Pitfalls" #1; pitfall #4 → §"Signal Formulas" | CI grep gate (Phase 3 IND-02) on `signals/minervini.py` + `indicators/trend.py` |
| **Pure functions in `signals/` and `indicators/`** | CLAUDE.md §"Coding Conventions" | `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` |
| **No `print()` anywhere** — use `structlog` | CLAUDE.md §"Coding Conventions" | Code review |
| **mypy `--strict` on `indicators/` and `signals/`** | CLAUDE.md + `pyproject.toml [tool.mypy]` | CI typecheck job |
| **Type hints required in `signals/` and `indicators/`** | CLAUDE.md | mypy strict |
| **All external I/O in `data/`** | CLAUDE.md §"Architectural Rules" | Architecture test |
| **Every IO boundary validates with pandera** | CLAUDE.md §"Architectural Rules" | `RankingSnapshotSchema` at snapshot write boundary |
| **Signal execution at next-bar open** | CLAUDE.md §"Architectural Rules" | Phase 5 no-look-ahead test |
| **9-subcommand CLI surface LOCKED** | Phase 1 D-14 | `tests/test_cli_smoke.py::D14_SUBCOMMANDS` |
| **`signals/` imports only `indicators/` + `regime` + `persistence` + `config`** (+ `obs`) | Phase 1 D-16 | `tests/test_architecture.py::ALLOWED["signals"]` |
| **`publishers/` imports only `signals/` + `sizing/` + `regime` + `persistence` + `config`** (+ `obs`) | Phase 1 D-16 | `tests/test_architecture.py::ALLOWED["publishers"]` |

## Architecture Patterns

### System Architecture Diagram

```
                    Phase 4 Daily Pipeline (single user-facing entry point: `make report`)

   ┌─────────────────┐
   │ data/macro/*.pq │  (Phase 3)
   │ data/ohlcv/*.pq │
   │ data/universe/  │
   └────────┬────────┘
            │ persistence.read_*
            ▼
   ┌─────────────────────────────────────┐
   │  indicators.build_panel(date)       │  (Phase 3 + new high_52w/low_52w)
   │  → MultiIndex (ticker, date) panel  │
   │  with sma_*, atr_14, adr_pct, obv,  │
   │  dryup_ratio, rs_raw, rs_rating,    │
   │  high_52w, low_52w  (NEW Phase 4)   │
   └────────┬────────────────────────────┘
            │
            ▼
   ┌─────────────────────────────────────┐    ┌──────────────────────┐
   │ signals.minervini                   │    │ regime.compute_for_  │
   │   .passes_trend_template(panel)     │    │   date(date, panel)  │
   │ → adds: passes_trend_template,      │    │ → regime_state,      │
   │   trend_template_score              │    │   regime_score       │
   └────────┬────────────────────────────┘    └─────────┬────────────┘
            │                                            │
            └────────────────┬───────────────────────────┘
                             │
                             ▼
            ┌────────────────────────────────────────────┐
            │ signals.composite.score(panel, weights)    │
            │ → adds: rs_score, trend_score, vol_score,  │
            │   composite_score (raw, pre-regime)        │
            │ Pure function. weights = DEFAULT_WEIGHTS   │
            │ (Final dict importable by CI script)       │
            └────────────────────┬───────────────────────┘
                                 │
                                 ▼
            ┌────────────────────────────────────────────┐
            │ publishers.apply_regime_gate(scored,       │
            │   regime_score)                            │
            │ → composite_score *= regime_score (soft)   │
            └────────────────────┬───────────────────────┘
                                 │
                                 ▼
            ┌────────────────────────────────────────────┐
            │ publishers.validate_run(scored, regime)    │
            │  pass_rate > 0.25 AND state==Correction    │
            │  → typer.Exit(1) + structlog error         │
            │   (no report, no snapshot)                 │
            └────────────────────┬───────────────────────┘
                                 │
                ┌────────────────┴───────────────────┐
                ▼                                    ▼
   ┌────────────────────────┐         ┌─────────────────────────────┐
   │ publishers.report      │         │ publishers.snapshot         │
   │ → reports/YYYY-MM-DD.md│         │ → data/snapshots/YYYY-MM-DD │
   │   regime banner        │         │   .parquet (full ranked     │
   │   top-15 picks table   │         │   universe; via             │
   │   per-pick blocks      │         │   write_snapshot_atomic)    │
   │   data-quality footer  │         │                             │
   └────────────────────────┘         └─────────────────────────────┘

CI preflight (parallel to lint/typecheck/test jobs):
   ┌──────────────────────────────────────────────────────┐
   │ scripts/check_preregistration.py                     │
   │ — imports DEFAULT_WEIGHTS from signals.composite     │
   │ — parses weights table from                          │
   │   docs/strategy_v1_preregistration.md                │
   │ — fails with exit-1 + diff line on mismatch          │
   └──────────────────────────────────────────────────────┘
```

### Recommended Module Layout

```
src/screener/
├── indicators/
│   └── trend.py              # ADD: high_52w_panel(), low_52w_panel()
├── signals/
│   ├── __init__.py           # Re-export composite.score, minervini.passes_trend_template
│   ├── minervini.py          # NEW: passes_trend_template(panel) -> DataFrame
│   └── composite.py          # NEW: DEFAULT_WEIGHTS, score(panel, weights) -> DataFrame
├── publishers/
│   ├── __init__.py           # (existing stub — keep as docstring-only)
│   ├── report.py             # NEW: render_report(scored_panel, regime, top_n) -> str
│   ├── snapshot.py           # NEW: write_snapshot(scored_panel, date)
│   └── pipeline.py           # NEW: orchestrates score → regime gate → validate → write
├── persistence.py            # ADD: RankingSnapshotSchema + write_snapshot_atomic + read_snapshot
├── config.py                 # ADD: REPORT_TOP_N, TREND_TEMPLATE_PASS_RATE_WARN, TREND_TEMPLATE_PASS_RATE_FAIL
└── cli.py                    # FILL: score body + report body (no new subcommands)

scripts/
└── check_preregistration.py  # NEW (and create scripts/ dir)

docs/
└── strategy_v1_preregistration.md  # FILL TBDs + freeze hash

.github/workflows/
└── ci.yml                    # ADD: preregistration step
```

### Pattern 1: Pure-function signal that consumes a panel

Mirror Phase 3's `regime.py` style — typed, panel-in / panel-out, no I/O imports, vectorized over the MultiIndex.

```python
# Source: pattern derived from src/screener/regime.py and src/screener/indicators/relative_strength.py
# Target file: src/screener/signals/minervini.py

from __future__ import annotations

import pandas as pd

# All 8 Trend Template conditions as separate boolean Series; sum gives 0-8 score;
# AND of all gives passes_trend_template. Pure function — no I/O, no globals.

def passes_trend_template(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `passes_trend_template` (bool) and `trend_template_score` (Int64 0-8).

    `panel` MUST contain: close, sma_50, sma_150, sma_200, high_52w, low_52w,
    rs_rating. Tickers missing any input get NaN → False / 0.

    Per CLAUDE.md "Signal Formulas" — SMA only, never EMA.
    Conditions are pure column comparisons; no shifts (per-ticker SMA200[t-22]
    is via groupby(level='ticker').shift(22)).
    """
    out = panel.copy()
    close = panel["close"]
    sma_50 = panel["sma_50"]
    sma_150 = panel["sma_150"]
    sma_200 = panel["sma_200"]
    high_52w = panel["high_52w"]
    low_52w = panel["low_52w"]
    rs_rating = panel["rs_rating"]

    # Per-ticker shift for condition 3 (SMA200 trending up over ~22 bars).
    sma_200_22d_ago = sma_200.groupby(level="ticker").shift(22)

    cond1 = (close > sma_150) & (close > sma_200)
    cond2 = sma_150 > sma_200
    cond3 = sma_200 > sma_200_22d_ago
    cond4 = (sma_50 > sma_150) & (sma_50 > sma_200)
    cond5 = close > sma_50
    cond6 = close >= 1.30 * low_52w
    cond7 = close >= 0.75 * high_52w
    cond8 = rs_rating >= 70  # rs_rating is Int64 nullable; comparison with NaN -> NA

    # NaN handling: any NaN input must propagate to False (not pass).
    # Treat each condition as a NaN-safe bool.
    conds = [cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8]
    bool_conds = [c.fillna(False).astype(bool) for c in conds]

    score = sum(bool_conds[i].astype("Int64") for i in range(8))
    out["trend_template_score"] = score
    out["passes_trend_template"] = (score == 8).fillna(False).astype(bool)
    return out
```

[ASSUMED] The exact NaN-handling rule (NaN → False) follows Phase 3 D-08 ("Downstream signals treat NaN trend-template conditions as `False`"). Verified against CONTEXT.md.

### Pattern 2: Composite weights-dict API design

Use a module-level `Final[dict[str, float]]` constant. NOT a Pydantic model (pulls in pydantic for an internal-only contract), NOT a TypedDict (overkill — keys are runtime data, not types). The constant is importable by CI scripts without instantiating pandas.

```python
# Source: NEW file — design derived from D-13 + D-12
# Target file: src/screener/signals/composite.py

from __future__ import annotations

from typing import Final

import pandas as pd

# Pre-registered weights — CHANGING THESE WITHOUT UPDATING
# docs/strategy_v1_preregistration.md FAILS CI (FND-05, D-09).
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,    # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,   # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,   # zeroed in Phase 4 (D-01); active in Phase 6
}

# Components that are NOT computed in Phase 4. The composite scorer
# multiplies their weight by 0.0 — score moves to ~0-55 range. Phase 6
# removes entries here and the score returns to 0-100.
PHASE_4_ZEROED: Final[frozenset[str]] = frozenset({"pattern", "earnings", "catalyst"})


def score(
    panel: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """Compute composite_score per ticker.

    Live components (Phase 4): rs, trend, volume.
    Zeroed components (Phase 4): pattern, earnings, catalyst (D-01).

    Returns the panel with these new columns:
      rs_component       — rs_rating / 99.0
      trend_component    — trend_template_score / 8.0
      volume_component   — clip(1 - (dryup_ratio - 0.5)/1.5, 0, 1) per D-02
      pattern_component  — 0.0 (Phase 4 placeholder)
      earnings_component — 0.0 (Phase 4 placeholder)
      catalyst_component — 0.0 (Phase 4 placeholder)
      composite_score    — Σ weights[k] * component_k * 100  (0-100 scale,
                          capped at ~55/100 in Phase 4)

    `weights` keys MUST be a subset of DEFAULT_WEIGHTS keys; raises ValueError
    on unknown keys. Sum need NOT be 1.0 (M2 will add ml_probability and
    re-normalize the user's weights elsewhere).
    """
    ...
```

**Why a `Final` dict (not TypedDict, not Pydantic, not dataclass):**
- The CI script `scripts/check_preregistration.py` needs to read the constant via `ast.parse` of the module file (does NOT execute the file — pandas not installed in lightest CI mode) OR via `importlib.import_module` after pandas is installed. Either works with a plain `Final` dict.
- `Final` (from `typing`) signals immutability to mypy strict, prevents accidental rebinding. Verified against `pyproject.toml` mypy config (`strict = true`).
- Future M2 `"ml_probability": 0.20` add is one line. Zero downstream refactor needed because `composite.score()` iterates `weights.items()`.
- The component-name → weight-key mapping is explicit. Any breakage in renaming is caught by mypy + the unit test.

### Pattern 3: Soft regime gate as a separate publisher step

```python
# Source: NEW file — design rationale below
# Target: src/screener/publishers/pipeline.py

import pandas as pd

def apply_regime_gate(scored_panel: pd.DataFrame, regime_score: float) -> pd.DataFrame:
    """Apply soft regime multiplier to composite_score (D-03).

    Soft gate: composite_score *= regime_score (a float in [0, 1] from the
    Phase 3 regime module). Picks still appear in Correction; scores compress.

    Phase 7 may swap to a hard gate (zero composite when state==Correction);
    keeping this as a separate function makes that swap a 5-line change instead
    of editing composite.score() (which is pure-function strict-mypy locked).
    """
    out = scored_panel.copy()
    out["composite_score"] = out["composite_score"] * regime_score
    return out
```

**Pros (separate step):** composite.score() stays pure and deterministic for unit tests; Phase 7 hard-gate swap is non-destructive; gate-on/gate-off feature flag is trivial.
**Cons:** Two function calls in the orchestrator instead of one.

The pros dominate. Phase 7 will appreciate this.

### Pattern 4: Validation gate (data-quality hard fail)

```python
# Source: pattern from src/screener/cli.py refresh-ohlcv health gate (lines 130-144)
# Target: src/screener/publishers/pipeline.py

import structlog
import typer

log = structlog.get_logger(__name__)

def validate_run(
    pass_rate: float,
    regime_state: str,
    warn_threshold: float,
    fail_threshold_with_correction: float,
) -> None:
    """D-07 + D-08 dual-channel alerting.

    D-07: pass_rate > warn_threshold (0.25) → structlog warning.
    D-08: pass_rate > fail_threshold_with_correction AND regime_state ==
          "Correction" → typer.Exit(1) — no report, no snapshot.

    Caller is the publisher orchestrator BEFORE writing report or snapshot.
    """
    if pass_rate > warn_threshold:
        log.warning(
            "trend_template_pass_rate_high",
            pass_rate=pass_rate,
            expected_range="0.05-0.15",
            warn_threshold=warn_threshold,
        )
        if regime_state == "Correction" and pass_rate > fail_threshold_with_correction:
            log.error(
                "data_quality_gate_failed",
                pass_rate=pass_rate,
                regime_state=regime_state,
                message=(
                    f"Pass rate {pass_rate*100:.1f}% in Correction regime — "
                    f"data quality gate failed"
                ),
            )
            raise typer.Exit(code=1)
```

Pattern mirrors `src/screener/cli.py` lines 130–144 (universe-coverage health gate).

### Anti-Patterns to Avoid

- **Hardcoded column references in `composite.score()`** — defeats D-13 weights-dict seam. Iterate `weights.items()`; the column for component `k` is `f"{k}_component"`.
- **Embedding `regime_score` multiplication inside `composite.score()`** — couples pure scoring to live state and breaks D-03 soft/hard-gate flexibility.
- **Calling `sys.exit()` or `typer.Exit()` from `signals/`** — violates pure-function rule. All exit logic lives in `publishers/` or `cli.py`.
- **Using EMA anywhere in `signals/minervini.py` or `indicators/trend.py`** — CI grep gate fails the build (Phase 3 IND-02). The CI step is `grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` (verified in `.github/workflows/ci.yml` line 42–47).
- **Adding a 10th typer subcommand** — `tests/test_cli_smoke.py::D14_SUBCOMMANDS` is the lock. The 9 stay; bodies fill in.
- **Writing the snapshot Parquet without the atomic-write helper** — must reuse `_write_parquet_atomic()` per Phase 2 D-11. A naked `df.to_parquet(target)` is forbidden by precedent.
- **Importing pandas in `scripts/check_preregistration.py`** — keeps the script lightweight + lets it run in a minimal CI shell BEFORE the full `uv sync`. Plain stdlib (`re` for table parsing, `ast` for reading the constant).
- **Hardcoding "—(Phase 6)" placeholder string in the report template** — derive it from `PHASE_4_ZEROED` so Phase 6 deletion of an entry automatically removes the placeholder from the report.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 52-week rolling high/low | A custom NumPy windowed loop | `panel.groupby(level="ticker")["high"].rolling(252).max()` (and `.min()` for low) | pandas rolling handles NaN warmup correctly; per-ticker groupby prevents index bleed (Phase 3 Pitfall 8). |
| Boolean condition aggregation for Trend Template score | A Python `for` loop summing booleans | `sum(cond_i.astype("Int64") for i in range(8))` | Vectorized; nullable Int64 propagates NaN cleanly; same pattern Phase 3 used for `rs_rating`. |
| Markdown table formatting | A custom string-builder | f-string templates with explicit column-width padding OR a tiny inline `format_table(rows, headers) -> str` helper (10 lines) | Tabulate / rich would be a new dependency; report is small + structured; inline is fine. |
| Atomic file write | `df.to_parquet(target)` directly | `_write_parquet_atomic(df, target)` from `persistence.py` | Phase 2 D-11; crash-safe; same-filesystem rename. |
| Schema validation at I/O | Hand-rolled `assert df.columns == [...]` | `pandera.DataFrameModel` subclass + `validate_at_write()` | Phase 2 D-15/D-16 — pandera is the standard. |
| CI preregistration parsing | Regex on the YAML block | Plain regex on the Markdown table — but make it strict (anchored, fail-loud) | The doc has no YAML frontmatter; the table IS the source of truth. |
| Loading `DEFAULT_WEIGHTS` in CI without pandas | Subprocess call to `python -c "import ..."` | Either `ast.literal_eval` on the module text, or `importlib.import_module` once `uv sync` has run | Both work; pick `importlib` — `pyproject.toml` has pandas in core deps so `uv sync --frozen` already installs it before the gate runs. |

**Key insight:** This is a code-shape phase, not a library-selection phase. Every capability is one of: (a) panel-in/panel-out pure function (mirror Phase 3), (b) atomic-write Parquet (mirror Phase 2), (c) typer subcommand body (mirror Phase 2 cli.py). No new dependencies. Don't invent new patterns where the existing patterns work.

## Common Pitfalls

### Pitfall 1: Forgetting to add `high_52w` / `low_52w` to the indicator panel
**What goes wrong:** `signals/minervini.passes_trend_template()` raises `KeyError: 'high_52w'` at runtime; or worse, NaN-propagates silently and every ticker's conditions 6–7 evaluate False (cascading 0% pass rate).
**Why it happens:** `build_panel()` ships 11 columns today (sma_10/20/50/150/200, atr_14, adr_pct, obv, dryup_ratio, rs_raw, rs_rating). 52-week high and low are NOT among them — verified by grep against `src/screener/indicators/*.py` (zero matches for `high_52w` / `low_52w` / `MAX(High` / `MIN(Low`).
**How to avoid:** Wave 0 task: add `high_52w_panel(panel, length=252)` and `low_52w_panel(panel, length=252)` to `indicators/trend.py`; wire into `indicators/__init__.py` `build_panel()`. Update the indicator-panel test (`tests/test_indicators_panel.py::REQUIRED_NEW_COLS`) to include both.
**Warning signs:** Test failure on `test_build_panel_returns_10_new_cols` after Phase 4 Wave 0.

### Pitfall 2: SMA200[t-22] computed across tickers (index bleed)
**What goes wrong:** Trend Template condition 3 uses `SMA200 > SMA200[t-22]`. A naked `.shift(22)` on a (ticker, date) MultiIndex panel shifts ACROSS tickers — Ticker B's first 22 bars get values from Ticker A's last 22 bars.
**Why it happens:** pandas `.shift()` operates on the row order, not the index level.
**How to avoid:** Always `panel["sma_200"].groupby(level="ticker").shift(22)`. This is the same pitfall Phase 3 documented as "Pitfall 8" in `relative_strength.py`.
**Warning signs:** A short-history ticker passes condition 3 (rising SMA200) when it shouldn't, OR a long-history ticker spuriously fails it.

### Pitfall 3: `rs_rating` is nullable Int64, NOT int64 — comparison semantics
**What goes wrong:** `rs_rating >= 70` returns `pd.NA` (not `False`) for tickers with insufficient history. A subsequent `& other_cond` propagates NA. Trend Template's `passes_trend_template` becomes NA → casting to bool may raise `TypeError: boolean value of NA is ambiguous`.
**Why it happens:** Phase 3 D-08 explicitly chose nullable Int64 (Pitfall 9 in Phase 3 RESEARCH); Trend Template integrates these without a NaN policy.
**How to avoid:** `cond.fillna(False).astype(bool)` for every condition before AND-ing them. Document this as the Trend Template NaN convention. Add a unit test: short-history ticker → `passes_trend_template == False`, `trend_template_score == 0` (no exception).
**Warning signs:** `pytest tests/test_signals_minervini.py` errors with "boolean value of NA is ambiguous".

### Pitfall 4: `dryup_ratio` is NaN for tickers with < 50 bars
**What goes wrong:** Volume component formula `clip(1 - (dryup_ratio - 0.5) / 1.5, 0, 1)` produces NaN for warmup period. Multiplied by weight 0.10, the composite_score becomes NaN for those tickers — they sort to the wrong end of the ranking and the snapshot Parquet has NaN in `composite_score`.
**Why it happens:** Phase 3 D-09 dryup_ratio is `volume / SMA(volume, 50)`; SMA(volume, 50) is NaN before bar 50.
**How to avoid:** In the volume-component computation, fillna(0.0) — interpret missing dryup as "no volume confirmation, score 0". Document this.
**Warning signs:** Snapshot Parquet has NaN composite_scores; report top-15 contains a ticker with NaN score (string formatting renders as `nan`).

### Pitfall 5: Pivot zone NaN cases — ATR is 0 or NaN
**What goes wrong:** `(close - high_52w) / atr` divides by zero (synthetic data, halted ticker) or by NaN (warmup). `pivot_zone` becomes "in-zone" or "chase, skip" via undefined comparison.
**Why it happens:** ATR is NaN for first 14 bars; can be 0 for synthetic test data with high == low.
**How to avoid:** Compute `pivot_distance_atr = (close - high_52w) / atr.replace(0, pd.NA)`. Then: `"in-zone"` if `pivot_distance_atr <= 1.0` else `"chase, skip"` else (NaN) `"unknown"`. Document the "unknown" third state.
**Warning signs:** Report shows `pivot_zone=nan` or `pivot_zone=inf` for any ticker.

### Pitfall 6: `composite_score` exceeds 100 if `regime_score > 1.0`
**What goes wrong:** Per CONTEXT D-03, `composite_score *= regime_score`. If regime_score is supposed to be in [0, 1] but a bug allows > 1.0, the score blows past 100.
**Why it happens:** Phase 3 D-03 documents `regime_score` as in [0, 1] via `clip(0, 1)` on each component. But the formula `0.30 * spy + 0.40 * breadth + 0.20 * dist + 0.10 * vix` with all clipped components in [0, 1] sums to AT MOST 1.0 — verified by inspection of `src/screener/regime.py` lines 96–110.
**How to avoid:** Add a defensive `assert 0 <= regime_score <= 1.0` in `apply_regime_gate()` (or use a debug log). And add a unit test: `composite_score` after regime gate is in `[0, 100]` for every ticker.
**Warning signs:** Report shows a composite_score > 100.

### Pitfall 7: `make report` writes report but exits 0 on data-quality failure
**What goes wrong:** Report shows the warning banner but CI / nightly cron treats the run as success.
**Why it happens:** `typer.Exit(code=1)` works only if raised IN the typer-command function; raised in a deeply-nested helper, it propagates correctly only if not caught.
**How to avoid:** `validate_run()` raises `typer.Exit(1)` BEFORE `render_report()` and `write_snapshot()` run. Test: invoke `screener report` with a fixture that triggers D-08 → assert exit code != 0 AND `reports/<date>.md` does NOT exist AND `data/snapshots/<date>.parquet` does NOT exist.
**Warning signs:** Production reports include the data-quality warning footer (means the gate is too soft, or the gate triggers but doesn't exit).

### Pitfall 8: Splits in 52-week high/low (CLAUDE.md pitfall #8 — flag for Phase 4)
**What goes wrong:** `MAX(high, 252)` over a window that includes a pre-split high creates an artificially high pivot. Stock looks like it's still 30% below pivot when it's actually ATH.
**Why it happens:** yfinance auto-adjusts close prices for splits but high/low may need verification.
**How to avoid:** yfinance `auto_adjust=True` (Phase 2 default) adjusts ALL OHLC for splits. Verify Phase 2 fetcher uses this. Document that Phase 4's pivot proxy is split-aware via the underlying OHLCV adjustment. Phase 6's real pivot detection (PAT-05) re-derives pivots on every run regardless.
**Warning signs:** A ticker that recently split shows a `pivot_zone=chase, skip` despite obvious price action.

### Pitfall 9: Preregistration script imports pandas — slows CI
**What goes wrong:** CI step "Check preregistration" takes 30s to spin up pandas just to read a dict.
**Why it happens:** Naive `from screener.signals.composite import DEFAULT_WEIGHTS` triggers the package init which transitively imports pandas + pandas-ta-classic + numpy.
**How to avoid:** Either (a) the CI step runs AFTER `uv sync --frozen` (the dependencies are installed anyway, no extra cost); or (b) the script uses `ast.parse` to extract the literal dict from the module text without executing it. Option (a) is simpler and matches CI flow.
**Warning signs:** CI duration jumps noticeably after adding the gate.

### Pitfall 10: Snapshot Parquet committed to git accidentally
**What goes wrong:** `data/snapshots/2026-05-10.parquet` lands in the commit; repo bloats.
**Why it happens:** The Phase 2 .gitignore carve-out (D-19 amendment) was specific: `data/ohlcv/*/prices.parquet` ignored, splits + universe committed. The snapshot dir wasn't part of that decision.
**How to avoid:** Add `data/snapshots/` to .gitignore (with .gitkeep anchor for the dir) in Wave 0. Same policy as `data/rs_snapshots/` (Phase 3 D-11).
**Warning signs:** First commit on Phase 4 includes a Parquet artifact.

### Pitfall 11: `weights.values()` summing to a number ≠ 100 / 1.0 — silent score drift
**What goes wrong:** A future contributor edits `DEFAULT_WEIGHTS` and the sum becomes 1.05 instead of 1.0. composite_score now exceeds 100.
**Why it happens:** Pre-registration doc may not catch this (CI gate compares per-component, not total).
**How to avoid:** Add an assertion in `composite.score()`: `assert abs(sum(weights.values()) - 1.0) < 1e-6`. Cheap. Also enforce in the preregistration script: parsed weights must sum to 100 ± 0.5%.
**Warning signs:** CI preregistration check passes but unit test for "composite_score in [0, 100]" fails.

### Pitfall 12: ASCII formatting clashes with no-emoji rule
**What goes wrong:** A drafter uses ⚠ (U+26A0) for the warning banner. CLAUDE.md says "Avoid using emojis." Code review pushback.
**Why it happens:** D-07's example uses `⚠ Pass rate: 31% ...`.
**How to avoid:** Use plain ASCII: `WARNING: Pass rate 31% (expected 5-15% — verify data quality)` or `[!] Pass rate ...`. Document the convention in the publisher module.
**Warning signs:** Lint passes (lint isn't checking emoji); reviewer flags it.

## Code Examples

### Add 52-week high / 52-week low to `indicators/trend.py`

```python
# Source: derived from existing src/screener/indicators/trend.py sma_panel pattern
# Target: append to src/screener/indicators/trend.py

def high_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append high_52w column — per-ticker rolling max of `high` over `length` bars.
    NaN warmup for the first `length-1` bars per ticker (D-08 from Phase 3).
    """
    out = panel.copy()
    out["high_52w"] = (
        panel.groupby(level="ticker")["high"]
        .rolling(length)
        .max()
        .droplevel(0)
    )
    return out


def low_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append low_52w column — per-ticker rolling min of `low` over `length` bars."""
    out = panel.copy()
    out["low_52w"] = (
        panel.groupby(level="ticker")["low"]
        .rolling(length)
        .min()
        .droplevel(0)
    )
    return out
```

Wire in `indicators/__init__.py`:

```python
# Append after rs_panel(panel) call:
panel = high_52w_panel(panel, length=252)
panel = low_52w_panel(panel, length=252)
```

Update `tests/test_indicators_panel.py::REQUIRED_NEW_COLS` to include `"high_52w"` and `"low_52w"`.

### Composite scorer body

```python
# Target: src/screener/signals/composite.py

def score(
    panel: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """See module docstring."""
    # Validate weights keys
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown weight keys: {sorted(unknown)}")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0; got {sum(weights.values())}")

    out = panel.copy()

    # Component computations (each in [0, 1])
    out["rs_component"] = (panel["rs_rating"].astype("Float64") / 99.0).fillna(0.0)
    out["trend_component"] = (panel["trend_template_score"].astype("Float64") / 8.0).fillna(0.0)
    out["volume_component"] = (
        (1.0 - (panel["dryup_ratio"] - 0.5) / 1.5).clip(0.0, 1.0).fillna(0.0)
    )
    # Phase 4 placeholders — D-01
    out["pattern_component"] = 0.0
    out["earnings_component"] = 0.0
    out["catalyst_component"] = 0.0

    # Weighted sum, scale to 0-100
    composite = pd.Series(0.0, index=panel.index)
    for key, w in weights.items():
        composite += w * out[f"{key}_component"]
    out["composite_score"] = (composite * 100.0).astype(float)
    return out
```

### Preregistration CI script (sketch)

```python
# Target: scripts/check_preregistration.py
# Plain stdlib. Runs in CI after uv sync.
"""Compares DEFAULT_WEIGHTS in signals/composite.py to the weights table in
docs/strategy_v1_preregistration.md. Fails CI on mismatch.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOC = Path("docs/strategy_v1_preregistration.md")
NAME_TO_KEY = {
    "RS percentile": "rs",
    "Trend Template": "trend",
    "Pattern": "pattern",
    "Volume confirmation": "volume",
    "Earnings momentum": "earnings",
    "Catalyst presence": "catalyst",
}

def parse_doc_weights() -> dict[str, float]:
    text = DOC.read_text()
    out: dict[str, float] = {}
    for friendly, key in NAME_TO_KEY.items():
        # Match a row like "| RS percentile (IBD-style) | 25% | 25% |"
        # Frozen weight is the LAST percentage on the line.
        pattern = rf"\|\s*{re.escape(friendly)}.*?\|\s*\d+%\s*\|\s*(\d+(?:\.\d+)?)%\s*\|"
        m = re.search(pattern, text)
        if m is None:
            sys.exit(f"Preregistration doc missing frozen weight for: {friendly}")
        out[key] = float(m.group(1)) / 100.0
    return out

def main() -> int:
    from screener.signals.composite import DEFAULT_WEIGHTS  # heavy import; ok in CI
    doc_weights = parse_doc_weights()
    diffs = []
    for k, w in DEFAULT_WEIGHTS.items():
        dw = doc_weights.get(k)
        if dw is None or abs(w - dw) > 1e-3:
            diffs.append(f"composite.py {k}={w:.2f} vs doc {k}={dw}")
    if diffs:
        print("Weight mismatch:\n  " + "\n  ".join(diffs), file=sys.stderr)
        return 1
    print("Preregistration check passed.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

CI step (add to `.github/workflows/ci.yml`, after `uv sync --frozen --extra dev` in the test job — keeps cache hot):

```yaml
- name: Preregistration consistency (FND-05)
  run: uv run python scripts/check_preregistration.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded composite formula in scorer | Weights dict (D-13) | Phase 1 architecture lock | Allows M2 ML weight addition without refactor |
| Hard regime gate (zero in Correction) | Soft multiplication by regime_score (D-03) | Phase 4 CONTEXT decision | Picks visible during Correction; user decides; revisitable Phase 7 |
| Pivot from VCP detection | 52w high proxy (D-05) | Phase 4 staging — full VCP in Phase 6 | Keeps Phase 4 shippable end-to-end; Phase 6 swap is column-stable |
| EMA-based moving averages (common in many TA libraries) | SMA only (D-11; CI-enforced) | Phase 3 IND-02 | Aligns with Minervini's published methodology; pitfall #1 prevented |

**Deprecated/outdated:**
- `pandas-ta` (PyPI, beta, changed maintainer) — replaced by `pandas-ta-classic` since Phase 1.
- `signals/` doing I/O — was never the design; architecture test catches it.

## Section 1 — Trend Template Implementation Specifics

**SMA usage:** pandas-ta-classic 0.4.47 has `ta.sma(series, length=N)` — verified live in this session. Phase 3 already uses it via `_safe_sma()` helper in `indicators/trend.py` lines 18–28 with NaN-fill-on-None safety. Reuse this helper or reuse the existing `sma_panel()` output directly (already in build_panel).

**Column dependencies:**
- `close` — present (OhlcvPanelSchema)
- `sma_50`, `sma_150`, `sma_200` — present (build_panel adds these)
- `rs_rating` — present (build_panel adds this; nullable Int64)
- `high_52w`, `low_52w` — **MISSING — must add to indicators/trend.py in Wave 0**

**The 8 conditions, exact pandas expression (target file: signals/minervini.py):**

```
1. Close > SMA150 AND Close > SMA200
   → (panel["close"] > panel["sma_150"]) & (panel["close"] > panel["sma_200"])
2. SMA150 > SMA200
   → panel["sma_150"] > panel["sma_200"]
3. SMA200 > SMA200[t-22]   (rising at least 1 month, per-ticker shift)
   → panel["sma_200"] > panel["sma_200"].groupby(level="ticker").shift(22)
4. SMA50 > SMA150 AND SMA50 > SMA200
   → (panel["sma_50"] > panel["sma_150"]) & (panel["sma_50"] > panel["sma_200"])
5. Close > SMA50
   → panel["close"] > panel["sma_50"]
6. Close >= 1.30 * MIN(Low, 252)   (30% above 52w low)
   → panel["close"] >= 1.30 * panel["low_52w"]
7. Close >= 0.75 * MAX(High, 252)  (within 25% of 52w high)
   → panel["close"] >= 0.75 * panel["high_52w"]
8. RS_Rating >= 70
   → panel["rs_rating"] >= 70
```

**NaN handling on first 252 rows:**
- Conditions 6, 7 depend on `low_52w`, `high_52w` — NaN until bar 252. Conditions evaluate to NA → `.fillna(False)` → ticker fails.
- Condition 3 depends on `sma_200.shift(22)` — NaN until bar 222 (200 for SMA + 22 for shift).
- Condition 8 depends on `rs_rating` — NaN until bar 252.

For tickers with < 252 bars: ALL pass conditions are False, `trend_template_score` is at most `cond1+cond2+cond4+cond5` (and even those are False for the first 200 bars).

**Look-ahead avoidance:**
- All conditions use the same row's data — no `.shift(-N)` (forward shift) anywhere.
- Condition 3 uses `.shift(22)` (backward shift, looks 22 bars into the past) — historically sound.
- The 52w high/low are computed via `rolling(252).max()` / `.min()` — these include the current bar (correct for "highest of trailing 252 days").
- Phase 5's no-look-ahead test will validate that signals consumed at bar t execute at open of bar t+1, but Trend Template itself has no shift-into-the-future risk.

[VERIFIED: pattern matches existing Phase 3 `relative_strength.py` per-ticker shift idiom (lines 28–32)]

## Section 2 — Composite Weights-Dict API Design

See "Pattern 2" above for the full code. Key design points:

**`Final[dict[str, float]]` is the right Python primitive** because:
1. Mypy strict treats it as immutable — accidental mutation caught at type-check time.
2. The CI script imports the constant by name (`from screener.signals.composite import DEFAULT_WEIGHTS`) — no parsing logic needed.
3. Adding `"ml_probability": 0.20` for M2 is a one-line append that downstream consumers iterate over without changes.
4. Plain dict (no Pydantic) keeps `signals/` import-light (architecture test allows it but pure-function discipline favors fewer imports).

**TypedDict considered, rejected:** TypedDict types `dict[str, float]` more precisely but adds no runtime value here. Keys are string literals; mypy already catches typos via the `Final` annotation if the keys are accessed by literal string. Not worth the syntactic noise.

**Pydantic model considered, rejected:** Would let us validate weight sums and ranges at construction time, but `composite.score()` already does both (assertion). And Pydantic adds a transitive import.

**Alternative that's also acceptable:** module-level `WEIGHT_KEYS: Final[tuple[str, ...]]` + `WEIGHT_VALUES: Final[tuple[float, ...]]` with `DEFAULT_WEIGHTS = dict(zip(WEIGHT_KEYS, WEIGHT_VALUES))`. Slightly more ceremonial; same behavior. Pick the dict; it's idiomatic.

**For "—(Phase 6)" placeholder rendering:** The report template iterates over `DEFAULT_WEIGHTS.keys()` and checks `if key in PHASE_4_ZEROED: render "—(Phase 6)" else render f"{component:.1f}"`. When Phase 6 removes entries from `PHASE_4_ZEROED`, the placeholder vanishes automatically. Single source of truth.

## Section 3 — Volume Component Mapping

**Formula validation:** `score = clip(1 - (dryup_ratio - 0.5) / 1.5, 0, 1)`.

| dryup_ratio | score |
|-------------|-------|
| 0.0 (impossible — volume is always ≥ 0) | 1.0 (clipped) |
| 0.5 | 1.0 (anchor — tight contraction = bullish) |
| 1.0 (volume = 50d avg) | 0.667 |
| 1.5 | 0.333 |
| 2.0 | 0.0 (anchor — high relative volume = no dryup) |
| 5.0 | 0.0 (clipped) |

Verified by hand: at `dryup_ratio = 0.5`: `1 - (0.5-0.5)/1.5 = 1.0`. At `2.0`: `1 - (2.0-0.5)/1.5 = 1 - 1.0 = 0.0`. Correct.

**Edge cases:**
- `dryup_ratio` is NaN (insufficient history, < 50 bars) → fillna(0.0). Interpretation: no volume confirmation possible, score = 0. Document this convention.
- `dryup_ratio` is exactly 0.0 (volume = 0, halt or holiday): `1 - (0-0.5)/1.5 = 1 - (-0.333) = 1.333` → clipped to 1.0. Correct: a halted ticker shouldn't score "max bullish", but volume=0 is so rare it's not worth a special case.
- `dryup_ratio` is inf (SMA(volume, 50) = 0 — universally 0 volume for 50 bars): division yields inf, formula yields -inf, clipped to 0.0. Correct.

**Anchor literature:** The 0.5 / 2.0 anchors are from the Qullamaggie-style methodology referenced in Phase 3 D-09 ("Values < 0.5 indicate significant volume contraction"). They're heuristic, not derived from a published paper. The CONTEXT.md decision lists "Phase 6 can refine the mapping without changing the API" — confirming these are placeholders pending validation. [ASSUMED; CITED: `src/screener/indicators/volume.py` docstring lines 3–5 for the 0.5 anchor]

## Section 4 — Soft Regime Gate Design

**Recommendation: separate `apply_regime_gate()` step in publisher orchestrator.**

```python
# In publishers/pipeline.py (orchestrator)

def run_pipeline(snapshot_date: str) -> None:
    panel = build_panel(snapshot_date)
    panel = passes_trend_template(panel)
    panel = composite.score(panel, DEFAULT_WEIGHTS)

    today_panel = panel.xs(pd.Timestamp(snapshot_date), level="date")  # cross-section
    regime = regime_module.compute_for_date(pd.Timestamp(snapshot_date), panel)
    today_panel = apply_regime_gate(today_panel, regime["regime_score"])

    pass_rate = today_panel["passes_trend_template"].mean()
    validate_run(pass_rate, regime["regime_state"], 0.25, 0.25)

    write_snapshot(today_panel, snapshot_date)
    write_report(today_panel, regime, snapshot_date)
```

**Pros:**
- `composite.score()` stays pure (deterministic given inputs; trivial unit tests).
- Phase 7 hard-gate transition is one function swap: `apply_hard_regime_gate(panel, regime_score, regime_state)` — zeros composite when state == "Correction".
- Easy to feature-flag during paper-trade validation: `if Settings.HARD_REGIME_GATE: ...`.
- Easy to test the gate in isolation: feed a known scored panel + regime_score, assert multiplication.

**Cons:**
- One extra function in the orchestrator chain (negligible).

**Alternative (rejected): embed in `composite.score()`.**
- Would require passing `regime_score` as a parameter to `score()`, breaking the "pure scoring of indicator panel" contract.
- Phase 7 hard-gate transition becomes a destructive edit to a strict-mypy-locked pure function.

## Section 5 — Pivot Proxy + Zone Annotation

**Formula:** `pivot_distance_atr = (close - high_52w) / atr_14`. Then:
- `pivot_zone = "in-zone"` if `pivot_distance_atr <= 1.0`
- `pivot_zone = "chase, skip"` if `pivot_distance_atr > 1.0`
- `pivot_zone = "unknown"` if either operand is NaN or atr_14 is 0.

**Edge cases:**
- ATR is 0: synthetic data with high == low for 14 bars (test fixtures!) produces ATR=0. Division by zero raises in pandas → use `atr_14.replace(0, pd.NA)` first.
- ATR is NaN: warmup period (< 14 bars). Same fix.
- high_52w is NaN: < 252 bars. Same fix; pivot_zone = "unknown".
- Distance is negative (close BELOW high_52w): pivot_distance_atr is negative, ≤ 1.0, classified "in-zone". Documented behavior — picks below their 52w high are still "in-zone" by this proxy. Phase 6 with the real VCP pivot will tighten this.

**Column label discipline:** Two columns to expose in the snapshot:
- `pivot_distance_atr` — float (or NaN), the raw distance metric.
- `pivot_zone` — str ∈ {"in-zone", "chase, skip", "unknown"}.

Report template renders the column header as `ATR from 52w high (Phase 4 proxy)` per D-05. The PROXY label in the column header is critical — it tells the reader this isn't the real pivot. Phase 6 swap: keep the column name `pivot_distance_atr`, change the source value (real VCP pivot replaces high_52w), and edit the report header to drop the "(Phase 4 proxy)" suffix.

## Section 6 — Pass-Rate Alerting

**Code pattern (D-07 + D-08):** See "Pattern 4" above — `validate_run()` raises `typer.Exit(1)` on the data-quality combination. Mirror the existing `cli.py` health-gate pattern (lines 130–144).

**Where the gate lives:**
- NOT in `signals/composite.py` (pure-function rule; can't `sys.exit`).
- NOT in `cli.py` directly (publisher logic doesn't belong there per architecture test).
- IN `publishers/pipeline.py` as `validate_run()`. The `cli.py` `report` subcommand body invokes the orchestrator via `publishers.pipeline.run_pipeline(today)` and any `typer.Exit` propagates naturally.

**Exit-code propagation:**
```python
# cli.py report body (sketch)
@app.command("report")
def report() -> None:
    configure_logging()
    try:
        publishers.pipeline.run_pipeline(date.today())
    except typer.Exit:
        raise  # propagate the validate_run exit
    except Exception as e:
        log.error("report_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

`typer.Exit` is just a controlled exception. As long as nothing catches it in the publisher chain, it bubbles to typer's main, which sets the process exit code.

**Test pattern:** Same as `tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` — use `CliRunner`, mock the panel + regime to produce pass_rate=0.30 with state=Correction, assert `result.exit_code != 0` AND no report file written.

## Section 7 — Markdown Report Layout

**Markdown best practices for this report:**
- Tables for the structured top-N picks list — readers can scan composite scores quickly.
- Sections (`## Per-Pick Detail`) for the breakdown blocks — easier to copy a single pick to a chat.
- Code blocks (triple-backtick) for the score breakdown line — monospace alignment of `RS=92 | Trend=7/8 | ...`.
- No emoji per CLAUDE.md "Coding Conventions" note. Use `WARNING:`, `[!]`, `(proxy)` text labels.
- ASCII tables with explicit column widths — avoid `|`-only tables that some Markdown renderers break.

**Concrete prototype matching SC1 (regime banner → top-N picks → per-pick blocks → footer):**

```markdown
# Daily Picks — 2026-05-10

## Regime

**State:** Confirmed Uptrend
**Score:** 0.82
**Components:** SPY > 200d: yes | Breadth: 67% | Distribution days: 2 | VIX: 16.4

---

## Top 15 Picks

| Rank | Ticker | Composite | Trend Template | RS  | Volume | Pivot Zone   | ATR from 52w high (Phase 4 proxy) |
|-----:|--------|----------:|---------------:|----:|-------:|:-------------|----------------------------------:|
|    1 | NVDA   |      48.7 |            8/8 |  98 |   0.91 | in-zone      |                              0.42 |
|    2 | META   |      46.2 |            8/8 |  94 |   0.78 | in-zone      |                              0.71 |
|    3 | AVGO   |      45.9 |            7/8 |  96 |   0.85 | in-zone      |                              0.88 |
|  ... | ...    |      ...  |           ...  | ... |    ... | ...          |                              ...  |

---

## Per-Pick Detail

### 1. NVDA — Composite 48.7

```
RS=98 | Trend=8/8 | Pattern=—(Phase 6) | Volume=0.91 | Earnings=—(Phase 6) | Catalyst=—(Phase 6)
```

- **Pivot zone:** in-zone (0.42 ATR from 52w high; proxy — Phase 6 will use real VCP pivot)
- **Playbook:** —(Phase 6)
- **Catalysts:** —(Phase 6)

### 2. META — Composite 46.2

```
RS=94 | Trend=8/8 | Pattern=—(Phase 6) | Volume=0.78 | Earnings=—(Phase 6) | Catalyst=—(Phase 6)
```

- **Pivot zone:** in-zone (0.71 ATR from 52w high)
- **Playbook:** —(Phase 6)
- **Catalysts:** —(Phase 6)

[... 13 more ...]

---

## Data Quality

| Metric                     | Value                |
|----------------------------|----------------------|
| Universe size              | 1003                 |
| Trend Template pass rate   | 8.4% (expected 5–15%) |
| Scan duration              | 2m 14s               |
| OHLCV last refresh         | 2026-05-10 22:35 UTC |
| Fetch success rate         | 99.4% (997/1003)     |
| Snapshot                   | data/snapshots/2026-05-10.parquet |

*Composite score is capped at ~55/100 in Phase 4 — Pattern, Earnings, and Catalyst components ship in Phase 6.*
```

**With the data-quality warning when D-07 fires:**

```markdown
## Data Quality

**WARNING: Pass rate 31.2% (expected 5-15% — verify data quality)**

| Metric ... |
```

**With the D-08 hard fail:** The report file is NEVER written. Only the structlog error event and exit-1 are produced. The cron / make-report consumer treats this as a failed run.

## Section 8 — Snapshot Writing

**Reuse `_write_parquet_atomic()` from persistence.py** — same module, new helper `write_snapshot_atomic()` mirroring `write_rs_snapshot_atomic()` (`src/screener/persistence.py` lines 352–364).

**Recommended snapshot schema:**

```python
class RankingSnapshotSchema(pa.DataFrameModel):
    """Daily ranking snapshot — full universe with composite scores and ranks.
    Written by publishers/snapshot.py via persistence.write_snapshot_atomic().
    Used by Phase 5 backtest harness for no-look-ahead reproduction.
    """
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rank: Series[pd.Int64Dtype] = pa.Field(ge=1, nullable=True)  # NaN tickers have no rank
    composite_score: Series[float] = pa.Field(ge=0.0, le=110.0, nullable=True)
        # le=110.0 to allow tiny float drift past 100; tighten in Phase 7
    rs_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    trend_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    volume_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    pattern_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)  # always 0 in Phase 4
    earnings_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)  # always 0 in Phase 4
    catalyst_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)  # always 0 in Phase 4
    passes_trend_template: Series[bool] = pa.Field(nullable=False)
    trend_template_score: Series[pd.Int64Dtype] = pa.Field(ge=0, le=8, nullable=True)
    rs_rating: Series[pd.Int64Dtype] = pa.Field(ge=1, le=99, nullable=True)
    dryup_ratio: Series[float] = pa.Field(nullable=True)
    pivot_distance_atr: Series[float] = pa.Field(nullable=True)
    pivot_zone: Series[str] = pa.Field(isin=["in-zone", "chase, skip", "unknown"], nullable=False)
    regime_state: Series[str] = pa.Field(
        isin=["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"],
        nullable=False,
    )
    regime_score: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)

    class Config:
        strict = True
        coerce = False
```

**Partitioning decision:** Single Parquet per day (NOT partitioned by ticker). Reasons:
- Day-grain partitioning matches the read pattern (Phase 5 backtest reads one day at a time).
- ~1000 rows × ~16 columns ≈ tiny file (~50KB). Partitioning would create overhead.
- Same pattern as `data/rs_snapshots/YYYY-MM-DD.parquet` (Phase 3 D-10/D-11) — keeps the cache pattern consistent.

**Why NOT partition by ticker:** OHLCV is partitioned by ticker because the access pattern is "all dates for one ticker" (per-ticker indicator computation). Snapshots have the opposite pattern: "all tickers for one date" (cross-sectional ranking).

**Atomic writer:**
```python
def write_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Mirror of write_rs_snapshot_atomic. D-11 atomic write contract."""
    validated = validate_at_write(RankingSnapshotSchema, df)
    target = _snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("snapshot_written", path=str(target), n_rows=len(validated))
    return target
```

Add `Settings.SNAPSHOT_DIR: Path = Path("data/snapshots")` and `_snapshot_dir()` helper following the `_rs_snapshot_dir()` pattern (lines 298–301).

## Section 9 — Preregistration CI Gate

**Design (concrete, see code in "Code Examples" above):**

1. **Location:** `scripts/check_preregistration.py` (new dir; create `scripts/.gitkeep` if needed).
2. **What it imports:** `screener.signals.composite.DEFAULT_WEIGHTS` after `uv sync --frozen`. Pandas import cost is paid once for the test job; the preregistration step adds ~0.5s. Acceptable.
3. **What it parses:** The Markdown table in `docs/strategy_v1_preregistration.md`. The "Frozen Weight" column (rightmost) is the source of truth. Friendly-name → key mapping is hardcoded in the script (six entries; matches the doc exactly).
4. **Failure message format (per D-09):** `"Weight mismatch: composite.py rs=0.30 vs doc rs=0.25"` — line per disagreeing key. Exit code 1.
5. **Where in CI:** Add as a step in the `test` job (or its own job — preference: own job, runs in parallel with lint/typecheck/test). Fits AFTER `uv sync --frozen --extra dev`.

**Doc parsing strategy:**
- Per-row regex: `r"\|\s*{friendly}.*?\|\s*\d+%\s*\|\s*(\d+(?:\.\d+)?)%\s*\|"` captures the frozen weight.
- Tolerance: 1e-3 (0.1%) — accommodates rounding (25.0% vs 25%).
- Sum check: parsed weights must sum to 1.0 ± 0.005 (0.5%). Fail loud.

**Markdown vs YAML frontmatter:** Use the existing Markdown table. Adding YAML frontmatter would require also amending the doc, which already has the table format Phase 1 shipped. The table IS the source of truth (D-09 says "parses the weights table from docs/...").

**Tamper-evident registration commit (D-10):**
- Workflow: edit `docs/strategy_v1_preregistration.md` to fill TBDs → commit → `git rev-parse HEAD` → amend the doc with `Frozen at commit: <sha>` → second commit.
- The second commit references the first commit's hash. Chain of two commits is the registration event.
- Phase 4 verifier checks: the doc contains a 40-char hex SHA after `Frozen at commit:`, and that SHA matches an actual commit in the history.

## Section 10 — `make report` CLI Wiring

**The 9-subcommand surface (verified in `tests/test_cli_smoke.py::D14_SUBCOMMANDS` lines 21–30):**
```
refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals,
score, report, journal, backtest, backtest-audit
```

`score` and `report` are BOTH already in the surface. Cleanest wiring:

**Recommended: `report` orchestrates the full pipeline (score + render + snapshot + validate). `score` is the orchestrator-without-render.**

```python
# cli.py
@app.command("score")
def score() -> None:
    """Compute composite scores; write data/snapshots/YYYY-MM-DD.parquet (no Markdown)."""
    configure_logging()
    try:
        publishers.pipeline.run_pipeline(date.today(), write_report=False)
    except typer.Exit:
        raise
    except Exception as e:
        log.error("score_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e

@app.command("report")
def report() -> None:
    """Render the daily Markdown report (also computes scores + snapshot)."""
    configure_logging()
    try:
        publishers.pipeline.run_pipeline(date.today(), write_report=True)
    except typer.Exit:
        raise
    except Exception as e:
        log.error("report_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**Makefile (`make report` already calls `screener report`):** No Makefile change needed — the existing target `report: uv run screener report` works as-is.

**Why this beats the alternatives:**
- `make report` works with one CLI invocation. No piping.
- `make rank` (which today calls `screener score`) writes only the snapshot, not the report. Useful for backtest-rebuild scenarios.
- Both subcommands stay in the locked surface; no 10th added.
- The orchestrator `publishers.pipeline.run_pipeline(date, write_report: bool)` is the single seam for future additions (e.g., journal write in Phase 7 — just add `write_journal: bool` parameter).

**Alternative (rejected): `make report` chains `screener score` then a separate publisher call.** This requires either piping a Parquet through stdin (awkward) or two filesystem hops (snapshot → re-read). The single-orchestrator approach is cleaner.

## Section 11 — Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + hypothesis 6.x (pinned in pyproject.toml dev extra) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (slow / integration markers; `pytest-cov` gate `>=80%` on `src/screener/signals` and `src/screener/indicators`) |
| Quick run command | `pytest -m "not slow and not integration" -x` |
| Full suite command | `pytest` (CI runs `pytest -m "not slow" -v`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-05 | Preregistration script catches weight mismatch | unit | `pytest tests/test_preregistration_check.py -x` | ❌ Wave 0 |
| FND-05 | CI runs preregistration step on every PR | integration (CI YAML inspection) | grep `.github/workflows/ci.yml` for the step name | covered by `.github/workflows/ci.yml` edit |
| SIG-01 | All 8 conditions evaluate correctly on synthetic ticker | unit | `pytest tests/test_signals_minervini.py -k "test_eight_conditions" -x` | ❌ Wave 0 |
| SIG-01 | Trend template score is 0–8 Int64 | unit | `pytest tests/test_signals_minervini.py -k "test_score_dtype_and_range" -x` | ❌ Wave 0 |
| SIG-01 | Tickers with insufficient history fail without exception (NaN-safe) | unit | `pytest tests/test_signals_minervini.py -k "test_short_history_safe" -x` | ❌ Wave 0 |
| SIG-01 | Pass rate on synthetic universe is in expected range | unit (smoke) | `pytest tests/test_signals_minervini.py -k "test_pass_rate_smoke" -x` | ❌ Wave 0 |
| SIG-01 | EMA grep gate still passes after adding minervini.py | CI step (already exists) | `.github/workflows/ci.yml` SMA-not-EMA gate runs on every PR | covered by Phase 3 ci.yml |
| SIG-04 | Composite scorer rejects unknown weight keys | unit | `pytest tests/test_signals_composite.py -k "test_unknown_weight_key_raises" -x` | ❌ Wave 0 |
| SIG-04 | Composite scorer requires weights to sum to 1.0 | unit | `pytest tests/test_signals_composite.py -k "test_weight_sum_assertion" -x` | ❌ Wave 0 |
| SIG-04 | Composite_score is in [0, 100] post regime gate | property test (hypothesis) | `pytest tests/test_signals_composite.py -k "test_score_range_property" -x` | ❌ Wave 0 |
| SIG-04 | Phase-4-zeroed components contribute 0 to score | unit | `pytest tests/test_signals_composite.py -k "test_zeroed_components" -x` | ❌ Wave 0 |
| SIG-04 | M2 extension seam: adding `ml_probability` key works | unit | `pytest tests/test_signals_composite.py -k "test_extension_seam" -x` | ❌ Wave 0 |
| SIG-04 | Soft regime gate multiplies composite_score | unit | `pytest tests/test_publishers_pipeline.py -k "test_soft_regime_gate" -x` | ❌ Wave 0 |
| OUT-01 | `make report` produces a Markdown file at the expected path | integration | `pytest tests/test_publishers_report.py -k "test_report_file_written" -x` | ❌ Wave 0 |
| OUT-01 | Report contains all required sections (regime banner, top-N, per-pick, footer) | unit (string match) | `pytest tests/test_publishers_report.py -k "test_report_sections_present" -x` | ❌ Wave 0 |
| OUT-02 | Per-pick block contains the 6-component breakdown with placeholders | unit | `pytest tests/test_publishers_report.py -k "test_per_pick_breakdown_format" -x` | ❌ Wave 0 |
| OUT-02 | Pivot zone shows "in-zone" or "chase, skip" or "unknown" | unit | `pytest tests/test_publishers_report.py -k "test_pivot_zone_labels" -x` | ❌ Wave 0 |
| OUT-03 | Snapshot Parquet is written at expected path with required columns | integration | `pytest tests/test_publishers_snapshot.py -k "test_snapshot_written_atomic" -x` | ❌ Wave 0 |
| OUT-03 | RankingSnapshotSchema validates a well-formed snapshot | unit | `pytest tests/test_persistence.py -k "test_ranking_snapshot_schema" -x` | extend existing file |
| OUT-03 | Snapshot rejects malformed frame (missing column) | unit | `pytest tests/test_persistence.py -k "test_ranking_snapshot_rejects_bad_shape" -x` | extend existing file |
| D-07 | Pass rate > 0.25 emits structlog warning | unit | `pytest tests/test_publishers_pipeline.py -k "test_pass_rate_warns" -x` | ❌ Wave 0 |
| D-08 | Pass rate > 0.25 AND Correction → exit 1, no report, no snapshot | integration (CliRunner) | `pytest tests/test_cli_smoke.py -k "test_report_data_quality_gate"` | extend existing file |
| Architecture | `signals/composite.py` only imports allowed peers | architecture | already covered by `tests/test_architecture.py` | covered |
| Architecture | `publishers/report.py` only imports allowed peers | architecture | already covered by `tests/test_architecture.py` | covered |

### Sampling Rate
- **Per task commit:** `pytest tests/test_signals_minervini.py tests/test_signals_composite.py tests/test_publishers_pipeline.py -x` (~3s).
- **Per wave merge:** `pytest -m "not slow"` (~12s based on Phase 3 baseline).
- **Phase gate:** `pytest && uv run mypy && uv run ruff check && uv run python scripts/check_preregistration.py` — all green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_signals_minervini.py` — 4 tests for SIG-01 (8-condition behavior, score dtype, short-history safety, pass-rate smoke)
- [ ] `tests/test_signals_composite.py` — 5 tests for SIG-04 (unknown key, sum assertion, range property, zeroed components, extension seam)
- [ ] `tests/test_publishers_pipeline.py` — 3 tests (soft regime gate, pass-rate warning, data-quality hard fail at unit level)
- [ ] `tests/test_publishers_report.py` — 4 tests for OUT-01/02 (file written, sections present, per-pick format, pivot-zone labels)
- [ ] `tests/test_publishers_snapshot.py` — 2 tests for OUT-03 (atomic write integration; full-pipeline snapshot)
- [ ] `tests/test_preregistration_check.py` — 3 tests for FND-05 (matching weights pass, mismatched fail with formatted message, missing weight in doc fails)
- [ ] `tests/test_cli_smoke.py` — extend with 1 integration test for D-08 hard fail
- [ ] `tests/test_persistence.py` — extend with 2 tests for `RankingSnapshotSchema` + `write_snapshot_atomic`
- [ ] `tests/conftest.py` — add fixtures: `synthetic_panel_for_trend_template` (with high_52w/low_52w columns), `synthetic_scored_panel` (post-composite, for publisher tests), `synthetic_high_pass_rate_panel` (for D-08 trigger)
- [ ] Framework install: NONE — pytest already installed, fixtures pattern already exists.

## Section 12 — Existing Patterns to Mirror

| Need | Closest analog | File | Key lines |
|------|----------------|------|-----------|
| Pure-function signal that consumes panel | `relative_strength.rs_panel` | `src/screener/indicators/relative_strength.py` | 21–46 (per-ticker shift via groupby; nullable Int64 dtype) |
| Pure-function with grouped rolling | `volume.dryup_ratio_panel` | `src/screener/indicators/volume.py` | 42–52 |
| Three-state classifier returning Series | `regime._classify_state` | `src/screener/regime.py` | 64–88 (returns RegimeState Literal — same pattern fits `pivot_zone`) |
| Vectorized score in [0, 1] | `regime._regime_score` | `src/screener/regime.py` | 96–110 |
| Compute-for-date row API | `regime.compute_for_date` | `src/screener/regime.py` | 118–187 |
| Pandera schema with nullable Int64 | `RsSnapshotSchema` | `src/screener/persistence.py` | 197–217 |
| Atomic Parquet writer | `write_rs_snapshot_atomic` | `src/screener/persistence.py` | 352–364 |
| Health-gate exit pattern | `cli.refresh_ohlcv` | `src/screener/cli.py` | 130–144 |
| Subcommand-with-typer.Exit | `cli.refresh_macro` | `src/screener/cli.py` | 158–189 |
| CliRunner integration test | `test_cli_smoke.test_health_gate_below_95_fails_run` | `tests/test_cli_smoke.py` | 109–137 |
| Settings additive extension | Phase 3 D-12 fields | `src/screener/config.py` | 51–59 |

**There is NO existing `scripts/` dir** — Phase 4 creates it. No precedent for CI-side preflight scripts in this repo. The CI YAML's existing SMA-not-EMA grep step (`.github/workflows/ci.yml` lines 42–47) is inline in YAML; the preregistration check is more complex and benefits from being a Python file.

## Section 13 — Pitfalls Specific to This Phase

Already enumerated in "Common Pitfalls" above (Pitfalls 1–12). Quick mapping to the focus areas in the prompt:

| Focus area pitfall | Section/Pitfall in this doc |
|--------------------|----------------------------|
| EMA-vs-SMA bug (CLAUDE.md #1) | Anti-Patterns + verified by CI grep gate (Phase 3 IND-02); will trigger if `ema` appears anywhere in `signals/minervini.py` or `indicators/trend.py`. |
| Pass-rate explosion symptoms (CLAUDE.md #4) | Pitfalls 1, 4 (NaN-cascade); plus D-07/D-08 alerting design |
| Hardcoded column references defeating weights dict seam (D-13) | Anti-Patterns + Pattern 2 |
| Forgetting splits in pivot detection (CLAUDE.md #8) | Pitfall 8 — yfinance auto_adjust=True (Phase 2 default) handles it; verify Phase 6 for the full VCP layer. |
| Composite > 100 from regime_score > 1.0 | Pitfall 6 + assertion in `apply_regime_gate()` |

## Runtime State Inventory

> Phase 4 is a code-only phase — no rename / refactor / migration. This section omitted per workflow rule.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas-ta-classic | SMA computation (already in build_panel) | ✓ | 0.4.47 | — |
| pandera | RankingSnapshotSchema | ✓ | 0.31.1 | — |
| pyarrow | Snapshot Parquet write | ✓ | 17.x | — |
| pydantic-settings | Settings extension | ✓ | 2.14.x | — |
| structlog | Event logging | ✓ | 25.5.x | — |
| typer | CLI subcommand bodies | ✓ | 0.25.x | — |
| Phase 3 indicator panel (build_panel) | Trend Template input | ✓ | — | — |
| Phase 3 regime module (compute_for_date) | Regime banner + soft gate | ✓ | — | — |
| Phase 2 atomic-write helper | Snapshot writer reuses | ✓ | — | — |
| `data/macro/spy.parquet`, `data/macro/vix.parquet` | regime.compute_for_date reads these | ✓ (created by Phase 3 `make macro`) | — | If absent: regime returns NaN → composite multiplied by NaN → gate triggers; document in user-facing failure |
| `data/ohlcv/*/prices.parquet` | build_panel input | ✓ (Phase 2 `make ohlcv`) | — | If absent: read_panel logs warning + skips ticker; if zero tickers, panel is empty and report is meaningless — pipeline should fail loud |

**Missing dependencies with no fallback:** None. All deps shipped by Phase 1–3.
**Missing dependencies with fallback:** None.

## Security Domain

Per `.planning/config.json` `security_enforcement: true`, ASVS Level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 4 has no user auth surface |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Local CLI; no multi-user |
| V5 Input Validation | yes | Pandera schemas at all I/O boundaries (existing pattern). Scripts/preregistration parses Markdown — but the Markdown is in-repo (no external untrusted input). |
| V6 Cryptography | no | No crypto in this phase |
| V7 Error Handling | yes | Structlog never logs API keys (Phase 3 D-04 amendment via `error_type` only); Phase 4 follows the same convention |
| V12 File / Resources | yes | Path-traversal — `_assert_safe_ticker` (already exists). Snapshot writer should also assert safe `snapshot_date` (no path injection) — pattern: validate as `YYYY-MM-DD` regex before path construction |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path injection via `snapshot_date` parameter | Tampering | Validate `snapshot_date` matches `^\d{4}-\d{2}-\d{2}$` regex before constructing the file path |
| Arbitrary Markdown injection from a ticker name into the report | XSS-like (rendered downstream in HTML viewers) | Escape pipe characters and angle brackets in ticker / company name fields when rendering the table; UniverseSchema's `str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$"` already constrains tickers |
| Logging sensitive data | Information Disclosure | structlog's existing pattern of `error_type` only (no `error.args`) for any failure paths. Composite scoring has no secrets, but the validate_run gate failure shouldn't dump the full DataFrame to logs |
| CI script reads arbitrary file in repo | Tampering | `scripts/check_preregistration.py` reads only `docs/strategy_v1_preregistration.md` and imports `screener.signals.composite` — both are in-repo trusted sources |

### Phase 4 Security Tasks

- [ ] Add `snapshot_date` regex validation in `write_snapshot_atomic` before path construction (mirror `_assert_safe_ticker`).
- [ ] Verify the report renderer escapes any ticker/name fields with pandas `.replace()` or explicit escaping for `|` and backticks (low risk — universe is GICS-scoped — but defense in depth).
- [ ] Confirm `scripts/check_preregistration.py` uses no `subprocess` or `eval` — pure file read + import.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Soft regime gate as a separate `apply_regime_gate()` step is preferred over embedding in `composite.score()` | Section 4, Pattern 3 | Low — alternative is also acceptable; planner can choose. Phase 7 hard-gate transition is harder if embedded. |
| A2 | Volume component anchors (0.5 → 1.0, 2.0 → 0.0) are heuristic placeholders with no published derivation | Section 3 | Low — D-02 is locked; mapping refinement is explicitly Phase 6 territory |
| A3 | NaN inputs to Trend Template conditions should fillna(False) → ticker fails the gate | Section 1, Pattern 1 | Low — aligns with Phase 3 D-08 ("NaN trend-template conditions as False"). |
| A4 | Snapshot is one Parquet per day, not partitioned by ticker | Section 8 | Low — matches Phase 3 RS snapshot precedent (D-10/D-11). |
| A5 | The 9-subcommand surface lock means `make report` orchestrates the full pipeline via the existing `report` command | Section 10 | Low — this is the only path that doesn't add a 10th subcommand. |
| A6 | Markdown report renderer should not use emoji per CLAUDE.md "Coding Conventions" (the tool-call no-emoji rule) and to keep readability across Markdown viewers | Section 7, Pitfall 12 | Low — D-07 example used `⚠`; recommended swap to `WARNING:` is mechanical. |
| A7 | `dryup_ratio` NaN should fillna(0.0) in volume component (no volume confirmation possible) | Pitfall 4 | Low — alternative (skip-and-rank) is awkward. Document the convention. |
| A8 | Preregistration script imports `screener.signals.composite` after `uv sync` rather than parsing the Python source | Section 9, Pitfall 9 | Low — both work; the import path is simpler and CI dep cost is already paid. |
| A9 | Pivot zone third state "unknown" for NaN inputs is the right choice (vs always defaulting to "chase, skip") | Section 5, Pitfall 5 | Low — surfacing data quality issues in the report is preferable to false confidence. |
| A10 | Phase 4's pivot proxy is split-aware because Phase 2 yfinance fetcher uses `auto_adjust=True` — to be VERIFIED in implementation by inspecting `data/ohlcv.py` | Pitfall 8 | Medium — if Phase 2 doesn't auto-adjust, pivots will be skewed across recent split events. **Action:** verify `auto_adjust=True` in Wave 0; if false, document and defer until Phase 6 PAT-05 fully addresses it. |

**Total assumptions:** 10. None block Phase 4; all are flagged for confirmation during planning or implementation.

## Open Questions (RESOLVED)

> All four open questions were resolved before plan finalization. Dispositions
> below reflect what shipped in plans 04-01 through 04-05 (or, for Q3, what was
> explicitly deferred). Resolved 2026-05-10 alongside plan generation.

1. **Should `Settings.TREND_TEMPLATE_PASS_RATE_FAIL` be separate from `TREND_TEMPLATE_PASS_RATE_WARN`?** D-07/D-08 both use 0.25 today. Recommend two separate Settings fields with the same default (0.25) — leaves room for tuning during paper-trade validation without redeploying.
   - What we know: D-07 (warn) and D-08 (hard fail) both fire at > 0.25; D-08 ANDs with regime_state == Correction.
   - What's unclear: Will the user want to warn at 0.20 and fail at 0.30 later? Plausible.
   - Recommendation: ship two fields, both default 0.25.
   - **RESOLVED: ADOPTED.** Plan 04-01 ships both `TREND_TEMPLATE_PASS_RATE_WARN: float = 0.25` and `TREND_TEMPLATE_PASS_RATE_HARD_FAIL: float = 0.25` on `Settings`. Tunable independently in `.env` without redeploy.

2. **Does `data/snapshots/` need a .gitkeep anchor and a .gitignore line?** Phase 3 used the pattern `data/rs_snapshots/` is gitignored; same policy almost certainly applies.
   - What we know: D-11 from Phase 3 — RS snapshots gitignored. Phase 2 D-19 amendment carved out specific paths.
   - What's unclear: Does the user want one snapshot per day committed to git for portfolio purposes (a la nightly reports)?
   - Recommendation: gitignore `data/snapshots/` for Phase 4; revisit in Phase 8 if nightly cron commits selected reports.
   - **RESOLVED: ADOPTED.** Plan 04-01 adds `data/snapshots/.gitkeep` and a `data/snapshots/*.parquet` line to `.gitignore`. Phase 8 may carve out specific dates if the cron commits selected reports.

3. **Should the report include a section for "how many tickers were dropped from ranking due to NaN composite_score"?** Useful data-quality signal.
   - What we know: data-quality footer per OUT-02; warn-on-pass-rate per D-07.
   - What's unclear: NaN-composite-count isn't explicitly required.
   - Recommendation: add it to the data-quality footer as a single line — cheap, informative, and aids debugging when pass rate looks weird.
   - **RESOLVED: DEFERRED to Phase 6.** Plan 04-04 Task 3 ships the data-quality footer with the four ROADMAP-SC1-required fields only (universe size, scan time, fetch success rate, last yfinance refresh) plus the conditional pass-rate banner from D-07. The NaN-composite-count line is non-required by SC1 and adds a column the planner would need to plumb through `_add_publisher_columns`. Adding it now risks breaking the OUT-01 string-match tests for marginal benefit. Phase 6 (when Pattern/Earnings/Catalyst components go live and NaN sources multiply) is the natural place to add it. Tracked as a Phase 6 follow-up, not as a Phase 4 deferred-decision in CONTEXT.md.

4. **Should `signals/__init__.py` re-export `passes_trend_template` and `score`?** Phase 1 D-13 said modules ship docstring-only. But end-of-Phase 4 there ARE real functions to expose.
   - What we know: D-13 was a Phase 1 scaffolding rule; Phase 3 onward populates real bodies.
   - What's unclear: Is the convention to re-export from `__init__.py` or to import from the submodule directly?
   - Recommendation: keep `signals/__init__.py` as docstring-only (matches `indicators/__init__.py` which DOES export — but `indicators` has a single primary entry point `build_panel`; signals has multiple, so per-submodule import is cleaner). Publishers pipeline imports `from screener.signals.minervini import passes_trend_template`.
   - **RESOLVED: ADOPTED.** Plan 04-04 imports `from screener.signals.minervini import passes_trend_template` and `from screener.signals.composite import score, DEFAULT_WEIGHTS, PHASE_4_ZEROED` directly — no `signals/__init__.py` re-exports. Mirrors the existing import style for `regime` and `persistence`.

## Sources

### Primary (HIGH confidence)
- **In-repo source files (verified live in this session):**
  - `src/screener/cli.py` — locked subcommand surface (lines 198–214 confirm `score` and `report` exist as stubs)
  - `src/screener/persistence.py` — atomic-write pattern (lines 236–258), schema patterns (lines 76–217), snapshot writer template (lines 352–364)
  - `src/screener/regime.py` — regime score range, soft-gate input shape, Literal pattern
  - `src/screener/indicators/__init__.py` — confirms 11 columns currently in `build_panel()` output; high_52w / low_52w NOT present
  - `src/screener/indicators/trend.py` — SMA pattern to mirror for high_52w / low_52w
  - `src/screener/indicators/relative_strength.py` — per-ticker shift idiom for condition 3
  - `src/screener/indicators/volume.py` — dryup_ratio definition
  - `src/screener/config.py` — Settings additive extension pattern
  - `tests/test_cli_smoke.py` — D14_SUBCOMMANDS lock + health-gate test pattern
  - `tests/test_architecture.py` — ALLOWED layer-import contract for `signals/` and `publishers/`
  - `tests/test_indicators_panel.py` — REQUIRED_NEW_COLS pattern for extending the panel test
  - `tests/conftest.py` — fixture pattern (`synthetic_multi_ticker_panel`)
  - `.github/workflows/ci.yml` — existing CI structure for adding the preregistration step
  - `Makefile` — existing `report` target wiring
  - `pyproject.toml` — confirmed deps (no new install needed)
  - `docs/strategy_v1_preregistration.md` — table format for preregistration parser
  - `docs/methodology.md` lines 1–22 — Trend Template authoritative formulation
  - `.planning/phases/04-trend-template-composite-skeleton-first-report/04-CONTEXT.md` — D-01 through D-14
  - `.planning/phases/03-indicator-panel-regime/03-CONTEXT.md` — Phase 3 carry-forward (D-08 NaN policy, D-09 dryup formula, D-12 Settings pattern)
  - `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` — D-13/D-14/D-15/D-16 architecture invariants
- **Live runtime check:** `import pandas_ta_classic as ta; hasattr(ta, 'sma')` → True; version 0.4.47 (verified this session)

### Secondary (MEDIUM confidence)
- CLAUDE.md §"Signal Formulas — Quick-Reference" — Trend Template formulas, ADR%, RS — cross-references the methodology doc
- CLAUDE.md §"Critical Pitfalls" — pitfalls 1, 3, 4, 8 (the four directly relevant to Phase 4)
- pandas 2.2 documentation (training data) — `groupby(level=...).rolling().min()/max()` is canonical for per-ticker rolling

### Tertiary (LOW confidence)
- Volume-component anchor values (0.5 / 2.0) — heuristic, no published derivation found in repo. Documented in A2 as "to refine in Phase 6".
- Markdown rendering specifics across viewers (GitHub, VS Code, Obsidian) — assumed reasonable cross-viewer support for ASCII tables; no explicit verification.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dependency already locked, verified live this session.
- Architecture patterns: HIGH — every recommended pattern has an existing in-repo precedent (cited above).
- Composite weights-dict design: HIGH — D-13 locks the API; `Final` dict is idiomatic Python; verified mypy-strict compatibility.
- Soft regime gate placement: MEDIUM — preference for separate `apply_regime_gate()` is design judgment (A1); alternative is acceptable.
- Pivot zone semantics (especially "unknown" third state): MEDIUM — D-06 doesn't enumerate the NaN case; A9 documents the recommendation.
- Markdown report layout: MEDIUM — concrete prototype provided; user (or planner) may prefer a different visual structure.
- Preregistration parser: HIGH — concrete code with explicit regex; the doc's table is fixed-format.
- Pass-rate gate design: HIGH — directly mirrors Phase 2's universe-coverage health gate.
- Pitfall coverage: HIGH — every pitfall has either a code-level or test-level mitigation.

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (30 days — phase scope is well-defined and dependencies are stable)

## RESEARCH COMPLETE
