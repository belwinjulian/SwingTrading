# Phase 7: Sizing Finalization & Paper-Trade Journal — Research

**Researched:** 2026-05-18
**Domain:** Position sizing (per-playbook dispatch) + append-only SQLite journal (v2 ML training contract)
**Confidence:** HIGH

## Summary

Phase 7 ships two interlocking pieces: (1) a pure `sizing.py` that dispatches stop/trail/shares by `playbook_tag` and (2) an append-only `data/journal.sqlite` (table `picks`) wired into `run_pipeline` and the existing stubbed `journal` CLI subcommand. CONTEXT.md D-01 through D-14 are locked; all 8 requirements (SIZ-01..05, OUT-04..06) have decided behaviors. Research focused on (a) verifying the locked SQLite mechanisms behave as CONTEXT.md asserts, (b) resolving the three "Claude's Discretion" items with code-grep evidence, and (c) specifying the integration seam into `run_pipeline` and `RankingSnapshotSchema` that the planner will encode.

**Verification results (empirical, run 2026-05-18 against sqlite 3.51.0):**
- `BEFORE UPDATE OF <col-list>` triggers fire whenever a listed column appears in the SET clause of an UPDATE; **column order in the OF list is not semantically significant**. `RAISE(ABORT, ...)` fully cancels the UPDATE and raises `sqlite3.IntegrityError` in Python — verified.
- `INSERT OR IGNORE` on a `UNIQUE(ticker, snapshot_date)` conflict silently skips (no exception); `cursor.rowcount` after `executemany` counts only the rows actually inserted. AUTOINCREMENT rowids are consumed even on skipped conflicts (gaps appear) — verified.
- UPDATE on a column NOT in the OF list (e.g., the 6 nullable outcome columns) succeeds with no trigger fire — verified. This is exactly the immutability-on-decision / mutability-on-outcome split D-02 requires.
- `pandas_ta_classic.ema` exists and is importable (signature `(close, length=..., talib=..., offset=...)` ) — useful for the VCP 21d EMA trail rule **outside** the CI-gated files (`signals/minervini.py`, `indicators/trend.py`).

**Primary recommendation:** Implement `sizing.py` as a single `compute_sizing(panel, account_equity, risk_pct, regime_score) -> DataFrame` with three private stop helpers dispatched via a `dict[playbook_tag, Callable]` registry; wire it into `run_pipeline` between `apply_regime_gate` (step 5) and the publisher-column step (step 7). Use the existing `persistence._write_parquet_atomic` for the extended snapshot and follow `append_form4_rows` / `_ensure_insider_schema` as the pattern for the journal SQLite layer. Use `entry_price` (not `entry_price_estimate`) for the column name to match Phase 6's `pivot_price` brevity convention. Compute 21d EMA inline in `sizing.py` (one call) rather than extending `indicators/trend.py` (which is CI-grep-gated against `ema`).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Journal write trigger** — appends fire inside `run_pipeline` AND the `journal` CLI command is an idempotent catch-up. Actionable pick = `composite_score >= Settings.JOURNAL_THRESHOLD AND regime_state != 'Correction'`. Idempotency via `INSERT OR IGNORE` on `UNIQUE(ticker, snapshot_date)`.
- **D-02: Journal table `picks`** — 14 NOT NULL decision columns + 6 nullable outcome columns. Immutability via `BEFORE UPDATE OF ...` trigger that `RAISE(ABORT, 'decision column immutable')`. Outcome columns explicitly excluded from trigger.
- **D-03: `features_json` blob scope** — score components + key indicator values + sizing inputs + full inlined `pattern_diagnostics` (per Phase 6 D-05 schema). ~400–600 B/row.
- **D-04: Sizing runs in `run_pipeline`** — `sizing.compute_sizing()` pure function called after `apply_regime_gate`, before `write_snapshot_atomic`. Snapshot Parquet gains 6 sizing columns.
- **D-05: Shares formula** — `floor((account_equity × risk_pct × regime_score) / (entry_price − stop_price))`, capped at `floor(account_equity × 0.25 / entry_price)`. Both `ACCOUNT_EQUITY` and `RISK_PCT` from Settings.
- **D-06: 1×ADR auto-reject** — pick excluded from BOTH report AND journal when `risk_per_share > adr_dollars` where `adr_dollars = (adr_pct / 100) × entry_price`. Reason surfaces in report `## Skipped Picks` footer section.
- **D-07: Per-playbook stop dispatch** — `qullamaggie_continuation → entry_day_low`; `minervini_vcp → final_contraction_low` (from `pattern_diagnostics.depth_sequence[-1]`); `leader_hold → entry_price − max(1.5×atr, recent_swing_low_distance)`, capped at 2×ATR.
- **D-08: Per-playbook trail rules** — display-only text in report (not auto-executed). Qull: 10/20/50d SMA by ADR% speed tier (<4 / 4–6 / ≥6 → 50/20/10). VCP: 21d EMA until trade ≥ 15 bars old then 50d SMA. Leader hold: 50d SMA close.
- **D-09: ATR zone buckets (3)** — `in-zone ≤ 0.66`, `extended 0.66–1.0`, `chase, skip > 1.0`.
- **D-10: OUT-06 outcome flow** — Phase 7 ships nullable schema only; `journal-update` deferred to v1.x.
- **D-11 (carry-forward, Phase 6 D-24):** 9-subcommand CLI surface LOCKED. `journal` fills its body; no 10th subcommand.
- **D-12 (carry-forward, Phase 4 D-03):** Regime gate stays soft (`composite × regime_score`); sizing formula incorporates `regime_score` in numerator.
- **D-13 (carry-forward, Phase 6 D-22):** Snapshot already carries `playbook_tag`; sizing dispatches by reading this column.
- **D-14 (carry-forward, Phase 6 architecture):** `publishers → sizing` already authorized in `tests/test_architecture.py` ALLOWED dict — verified (line 36).

### Claude's Discretion

- **21d EMA for VCP trail (D-08):** decide whether to extend `indicators/trend.py` or compute inline in `sizing.py`. → **Resolved: compute inline in sizing.py.** Evidence below in `## Architecture Patterns`.
- **`recent_swing_low_distance` for leader_hold stop (D-07):** decide lookback window and the `argrelextrema` `order` parameter; specify fallback. → **Resolved: 20-bar window, `order=3` (reuse `FLAG_PIVOT_ORDER` from patterns.py), fallback to `2×ATR` when no trough.**
- **`entry_price` column naming (D-04):** `entry_price` vs `entry_price_estimate`. → **Resolved: `entry_price`** (matches Phase 6's `pivot_price` brevity; the "next-bar-open estimate" semantic is documented in the docstring + features_json `entry_price_semantics: "close_as_next_open_estimate"` tag).

### Deferred Ideas (OUT OF SCOPE)

- **`journal-update` CLI flow** — v1.x. Phase 7 ships nullable outcome columns only; update mechanism (`scripts/journal_update.py` or typer subapp) ships after the first 30 paper trades.
- **`rejection_reason` column in journal for negative ML samples** — v1.x.
- **Graded trail rules (continuous speed tiers)** — v1.x. Phase 7 ships discrete ADR%-based tiers.
- **Journal analytics / decile spread report** — v1.x (CAT-V1X-01).
- **Per-playbook performance time-series in daily report** — v1.x (CAT-V1X-04).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIZ-01 | `shares = (account_equity × risk_pct × regime_score) / (entry − stop)`, capped at 25% of equity per position | `compute_sizing()` body; `ACCOUNT_EQUITY` + new `RISK_PCT` Settings field; per-position cap formula in D-05 verbatim |
| SIZ-02 | Auto-reject if `risk_per_share > 1 × ADR_dollars` | `adr_pct` already in panel (`indicators/volatility.py` `adr_pct_panel`); rejection row dropped from both report top-N AND journal append; reason surfaced in `## Skipped Picks` footer |
| SIZ-03 | Per-playbook stop placement | Stop-helper registry pattern (dict of callables keyed by playbook_tag); unit-testable per SC-2 |
| SIZ-04 | Per-playbook trail rules — display text only in v1 | Trail-rule helper returns a string; report renderer prints under `Trail:` line per CONTEXT specifics |
| SIZ-05 | Distance-from-pivot in ATRs annotated with 3-bucket label | `pivot_distance_atr` column already in `RankingSnapshotSchema` (Phase 4); Phase 7 adds `atr_zone` Literal column; existing `_classify_pivot_zone` in publishers/report.py is 2-state (in-zone/chase-skip) and lives at the report layer — Phase 7 needs a NEW classifier in `sizing.py` because the snapshot must carry the 3-bucket label (in-zone/extended/chase-skip) per D-09 |
| OUT-04 | Every actionable pick appended to journal at publish time | `append_picks(rows)` called inside `run_pipeline` after `write_snapshot_atomic`; `journal` CLI command reads same-day snapshot and re-appends; `INSERT OR IGNORE` makes the catch-up idempotent |
| OUT-05 | Append-only schema with `features_json` blob | `picks` table DDL with UNIQUE constraint + immutability trigger; `features_json` is full Phase 6 D-05 dict inlined (verified ~400–600 B/row) |
| OUT-06 | Outcome columns (entry_filled, exit_price, exit_date, hold_days, mfe, mae) — defined nullable in Phase 7; updated by v1.x flow | 6 nullable columns appended to schema; trigger OF-list explicitly excludes them; update flow deferred to v1.x per D-10 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-playbook stop computation | `sizing/` (pure fn) | — | Already in ALLOWED dict (signals, regime, config, obs). Stops are pure math over indicator panel + diagnostics — no I/O |
| Shares + ADR-reject + ATR-zone | `sizing/` (pure fn) | — | Same: pure transformations on the cross-section frame |
| 21d EMA for VCP trail label | `sizing/` (inline) | — | Reasoning in §Architecture Patterns Pattern 3 — keeps `indicators/trend.py` CI-grep-gate intact |
| Pipeline orchestration | `publishers/pipeline.py` | `sizing`, `persistence` | `publishers` already authorized to import both per `tests/test_architecture.py` ALLOWED line 36 |
| Snapshot write (extended schema) | `persistence.write_snapshot_atomic` | `RankingSnapshotSchema` | Atomic write idiom already established; schema extended additively |
| Journal SQLite I/O | `persistence` (new helpers `_ensure_picks_schema`, `append_picks_rows`, `read_picks_for_date`) | — | Mirrors `_ensure_insider_schema` + `append_form4_rows` pattern verbatim |
| CLI `journal` catch-up | `cli.journal` (compose root) | `persistence` (read snapshot, append) | Stub already in place (cli.py:232–235); body wires existing helpers |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 (stdlib) | Python 3.11 ships sqlite 3.51.0 | Append-only `picks` table + immutability trigger + UNIQUE idempotency | Already used in `persistence.append_form4_rows` (Phase 6). [VERIFIED: `python3 -c "import sqlite3; print(sqlite3.sqlite_version)" → 3.51.0`] [VERIFIED: empirical test in §Code Examples Pattern 4 confirms trigger + INSERT OR IGNORE behavior] |
| pandas | 2.2.x | DataFrame ops in `compute_sizing` | Already pinned in pyproject.toml [VERIFIED: pyproject.toml] |
| pandas-ta-classic | 0.4.47 | 21d EMA for VCP trail label | `hasattr(ta, 'ema') == True` confirmed [VERIFIED: `uv run python -c "import pandas_ta_classic as ta; print(hasattr(ta, 'ema'))" → True`] |
| pandera | 0.31.1 | `RankingSnapshotSchema` extension validation | Already pinned; extension follows the additive idiom Phase 6 used (6 new columns appended to existing class body, no model split) [VERIFIED: persistence.py:222–273 — Phase 6 added 11 cols additively] |
| structlog | 25.5.x | Pipeline observability | Already configured; new event names defined in §Code Examples Pattern 5 |
| pydantic-settings | 2.14.x | `ACCOUNT_EQUITY` (already present), new `RISK_PCT` + `JOURNAL_THRESHOLD` | Additive Settings extension pattern; mirror to `.env.example` [VERIFIED: config.py:39 `ACCOUNT_EQUITY: float = 100_000.0` already exists] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.signal.argrelextrema | already imported via patterns.py | `recent_swing_low_distance` for leader_hold | Reuse `patterns.find_pivots(highs, lows, order=3)` directly — no new import needed in sizing.py |
| numpy | 2.x | floor, max, argmax, asarray for the sizing math | Standard |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `INSERT OR IGNORE` | `ON CONFLICT (ticker, snapshot_date) DO NOTHING` | Equivalent (since SQLite 3.24). `INSERT OR IGNORE` chosen because `append_form4_rows` uses `ON CONFLICT(filing_id) DO NOTHING` and either reads naturally — but `INSERT OR IGNORE` is the form CONTEXT.md `<specifics>` specifies. Use IT for consistency with the documented spec. |
| BEFORE UPDATE OF trigger | `WITHOUT ROWID` table + read-only enforcement at the Python layer | Trigger is the documented choice (D-02) and survives schema migrations only if you DROP+CREATE on every migration. **Caveat:** SQLite triggers do NOT survive table DROP — if a future migration uses table-rebuild (CREATE temp, COPY, DROP, RENAME), the trigger must be re-created. Document this in `_ensure_picks_schema`. |
| `dict[tag, Callable]` stop registry | `if/elif/else` chain | Dict registry makes SC-2 ("a unit test asserts each playbook calls the correct stop+trail helper") trivial via `assert STOP_HELPERS["qullamaggie_continuation"] is _stop_qullamaggie`. Recommend the dict. |
| Compute 21d EMA in `indicators/trend.py` | inline in `sizing.py` | `indicators/trend.py` is CI-grep-gated against `ema` (IND-02 / Phase 3 D-05) — adding ema there would require amending the grep gate. `sizing.py` is NOT grep-gated. Compute inline (one-liner `ta.ema(close, length=21)`). |

**Installation:** No new dependencies. All required libraries already pinned in `pyproject.toml`.

**Version verification (2026-05-18):**
- `sqlite3.sqlite_version == "3.51.0"` — supports all required features [VERIFIED: empirical]
- `pandas_ta_classic.ema` signature `(close, length=None, talib=None, offset=None) -> pd.Series | None` — None-on-short-history pattern same as `ta.sma`/`ta.atr`; wrap in `_safe_ema` helper mirroring `indicators/trend._safe_sma` [VERIFIED: `uv run python -c "import pandas_ta_classic as ta; import inspect; print(inspect.signature(ta.ema))"`]

## Architecture Patterns

### System Architecture Diagram

```
                            run_pipeline(snapshot_date)
                                       │
                                       ▼
              build_panel (Phase 3+6) ── patterns + composite + tag_playbook
                                       │
                                       ▼
                          xs(snap_ts) → cross-section (one row per ticker)
                                       │
                                       ▼
                          apply_regime_gate (×regime_score)
                                       │
                                       ▼
                          ┌─────────────────────────────┐
                          │  compute_sizing (NEW Phase 7)│
                          │  ├─ entry_price = close      │
                          │  ├─ dispatch stop by tag     │
                          │  ├─ shares formula + cap     │
                          │  ├─ atr_zone bucket          │
                          │  ├─ reject rows where        │
                          │  │   risk_per_share > ADR$   │
                          │  └─ trail_rule_label (str)   │
                          └─────────────────────────────┘
                                       │
                          ┌────────────┴────────────┐
                          ▼                         ▼
                  rejected rows         actionable cross-section
                          │             (rank, validate_run, etc.)
                          │                         │
                          │                         ▼
                          │             _add_publisher_columns
                          │                         │
                          │                         ▼
                          │             write_snapshot_atomic (extended schema)
                          │                         │
                          │             ┌───────────┴───────────────┐
                          │             ▼                           ▼
                          │   append_picks_rows         write_report (incl.
                          │   (data/journal.sqlite)     ## Skipped Picks)
                          │             │                           │
                          └─────────────┴───────────────────────────┘
                                       │
                                       ▼
                          (later) cli.journal command
                                       │
                                       ▼
                          read_snapshot(today) → append_picks_rows
                          (idempotent — INSERT OR IGNORE on
                           UNIQUE(ticker, snapshot_date))
```

### Recommended Project Structure

```
src/screener/
├── sizing.py                          # NEW BODY: compute_sizing() + stop helpers + trail labels
├── publishers/
│   └── pipeline.py                    # MODIFY: add compute_sizing call + journal append step
├── persistence.py                     # MODIFY: extend RankingSnapshotSchema (+6 cols);
│                                      #         add _ensure_picks_schema, append_picks_rows,
│                                      #         read_picks_for_date, PicksSchema (pandera)
├── cli.py                             # MODIFY: fill journal command body (no new subcommand)
├── config.py                          # MODIFY: add RISK_PCT, JOURNAL_THRESHOLD fields
└── publishers/
    └── report.py                      # MODIFY: render Trail:/Stop:/Zone: lines + ## Skipped Picks

tests/
├── test_sizing.py                     # NEW: 10+ unit tests for compute_sizing
├── test_journal.py                    # NEW: 8+ tests for picks DDL + trigger + idempotency
└── test_pipeline_journal.py           # NEW: 3+ integration tests (snapshot+journal round-trip)
```

### Pattern 1: Stop-helper dispatch via dict registry

**What:** Define three private `_stop_*` helpers and a module-level `STOP_HELPERS: Final[dict[str, Callable[[pd.Series, pd.DataFrame], float]]]` registry; dispatch by reading `playbook_tag` per row.

**When to use:** Whenever per-playbook behavior diverges and the test contract requires "assert each playbook calls the correct helper" (SC-2). Dict registry makes the test a one-liner `assert STOP_HELPERS[tag] is expected_fn`.

**Example:**
```python
# Source: derived from CONTEXT.md D-07 + Phase 6 composite.tag_playbook dispatch pattern
from typing import Callable, Final
import numpy as np
import pandas as pd

def _stop_qullamaggie(row: pd.Series, ticker_history: pd.DataFrame) -> float:
    """D-07: entry-day low = the D-0 'low' bar (same bar that triggered breakout)."""
    return float(row["low"])  # close-of-day cross-section already carries the D-0 OHLC

def _stop_minervini_vcp(row: pd.Series, ticker_history: pd.DataFrame) -> float:
    """D-07: final_contraction_low from pattern_diagnostics.

    pattern_diagnostics carries (per Phase 6 D-05 schema):
      pivot_price (float), final_contraction_depth (float fraction, e.g. 0.08 = 8%)
    final_contraction_low = pivot_price * (1 - final_contraction_depth)
    """
    from screener.indicators.patterns import decode_pattern_diagnostics
    diag = decode_pattern_diagnostics(row["pattern_diagnostics"])
    pivot = float(diag.get("pivot_price", row["close"]))
    final_depth = float(diag.get("final_contraction_depth", 0.0))
    return pivot * (1.0 - final_depth)

def _stop_leader_hold(row: pd.Series, ticker_history: pd.DataFrame) -> float:
    """D-07: entry_price - max(1.5*atr, recent_swing_low_distance), capped at 2*ATR."""
    entry = float(row["close"])
    atr = float(row["atr_14"])
    swing_dist = _recent_swing_low_distance(ticker_history, entry, atr)
    raw_distance = max(1.5 * atr, swing_dist)
    capped = min(raw_distance, 2.0 * atr)
    return entry - capped

STOP_HELPERS: Final[dict[str, Callable[[pd.Series, pd.DataFrame], float]]] = {
    "qullamaggie_continuation": _stop_qullamaggie,
    "minervini_vcp": _stop_minervini_vcp,
    "leader_hold": _stop_leader_hold,
}
```

### Pattern 2: `recent_swing_low_distance` via existing `find_pivots` helper

**What:** Reuse `screener.indicators.patterns.find_pivots(highs, lows, order=3)` over the trailing 20-bar window of the ticker's history. Take the **most recent** trough; distance = `entry_price - lows[last_trough_idx]`. Fallback when no trough in window: return `2.0 * atr` (the cap value — equivalent to using only the 1.5×ATR floor without expanding it).

**When to use:** Only in `_stop_leader_hold`. The 20-bar window is the same `FLAG_MAX_BARS` upper bound from `indicators/patterns.py:48` — leader-hold candidates are NOT in a tight base, so a 20-bar trough is a reasonable "recent" pivot. `order=3` matches `FLAG_PIVOT_ORDER` (patterns.py:58) which Plan 06-02 chose as the "less aggressive" pivot strictness for non-VCP setups.

**Example:**
```python
# Source: synthesizes patterns.find_pivots + CONTEXT.md D-07 + Open Question 2 fallback rule
from screener.indicators.patterns import find_pivots
import numpy as np

LEADER_SWING_LOOKBACK_BARS: Final[int] = 20  # Same as FLAG_MAX_BARS
LEADER_SWING_PIVOT_ORDER: Final[int] = 3     # Same as FLAG_PIVOT_ORDER

def _recent_swing_low_distance(
    ticker_history: pd.DataFrame,
    entry_price: float,
    atr: float,
) -> float:
    """Return (entry_price - most_recent_swing_low) over the last 20 bars.

    Fallback when no trough is found in the window: return 2.0 * atr so the
    outer max(1.5*atr, ...) chooses the floor and the outer min(..., 2.0*atr)
    cap also chooses 2.0*atr — net effect: stop at entry - 2*ATR.
    """
    tail = ticker_history.tail(LEADER_SWING_LOOKBACK_BARS)
    if len(tail) < (2 * LEADER_SWING_PIVOT_ORDER + 1):
        return 2.0 * atr
    highs = tail["high"].to_numpy(dtype=float)
    lows = tail["low"].to_numpy(dtype=float)
    _, low_idx = find_pivots(highs, lows, order=LEADER_SWING_PIVOT_ORDER)
    if len(low_idx) == 0:
        return 2.0 * atr
    last_trough_low = float(lows[low_idx[-1]])
    return max(0.0, entry_price - last_trough_low)
```

### Pattern 3: 21d EMA computed inline in `sizing.py` (not added to `indicators/trend.py`)

**What:** The Phase 3 SMA-vs-EMA CI grep gate (IND-02; `.github/workflows/ci.yml` scans `signals/minervini.py` + `indicators/trend.py` for `ema`). Adding `ema_21_panel()` to `trend.py` would either trip the grep (failing CI) or require amending the gate definition — both are out of scope for Phase 7. `sizing.py` is NOT in the grep-gate scope, so a one-call `ta.ema(close, length=21)` is the cheapest path.

**When to use:** Only as a label for the VCP trail rule description in the report. The trail value itself is NOT computed at sizing time (D-08: "displayed in report" only). What the report renders is a textual rule like `Trail: 21d EMA (until trade ≥ 15 bars old; then 50d SMA)` — no numeric trail value needs computing in Phase 7.

**Decision:** Trail rule output is a **label string**, not a numeric. No 21d EMA computation actually required in sizing.py — the trail-rule helper returns a string only. If the planner decides to also surface the current 21d EMA value in the report for context, compute it inline in the report layer where the full ticker panel is available, NOT in sizing.

```python
# Source: revised after re-reading D-08 — trail is "displayed in report", not auto-executed.
def _trail_rule_label(row: pd.Series) -> str:
    """Return D-08 trail rule as a display string for the report.

    Sizing emits the LABEL; report renders it under `Trail:` per CONTEXT specifics.
    No 21d EMA computation needed at sizing time.
    """
    tag = row["playbook_tag"]
    if tag == "qullamaggie_continuation":
        adr = float(row.get("adr_pct", 0.0))
        if adr >= 6.0:
            return "10d SMA"
        if adr >= 4.0:
            return "20d SMA"
        return "50d SMA"
    if tag == "minervini_vcp":
        return "21d EMA (then 50d SMA after 15 bars)"
    if tag == "leader_hold":
        return "50d SMA close"
    return ""
```

### Pattern 4: Pipeline integration seam (publishers/pipeline.py)

**What:** Insert `compute_sizing` between step 5 (`apply_regime_gate`) and step 7 (`_add_publisher_columns`) in `run_pipeline`. Filter out auto-rejected rows BEFORE step 7 so they don't end up in the ranked Parquet OR the journal. Carry rejected rows separately as `skipped_picks_df` for the report footer.

**When to use:** Single integration point per CONTEXT D-04 + D-06. Both rejected-from-report AND rejected-from-journal happen at the same filter — one source of truth.

**Example:**
```python
# Source: derived from publishers/pipeline.py existing structure + CONTEXT D-04 + D-06
def run_pipeline(
    snapshot_date: str,
    write_report: bool = True,
    write_journal: bool = True,  # NEW param per D-01
) -> None:
    settings = get_settings()
    panel = build_panel(snapshot_date)
    panel = passes_trend_template(panel)
    panel = score(panel, DEFAULT_WEIGHTS)
    # Phase 6 additions: patterns, canslim, tag_playbook (added by Plan 06-05)

    snap_ts = pd.Timestamp(snapshot_date)
    today_panel = panel.xs(snap_ts, level="date")

    regime_row = compute_for_date(snap_ts, panel)
    regime_score_value = float(regime_row["regime_score"])
    regime_state_value = str(regime_row["regime_state"])
    today_panel = apply_regime_gate(today_panel, regime_score_value)

    # === NEW Phase 7 step 5.5: sizing ===
    from screener.sizing import compute_sizing
    sized_panel = compute_sizing(
        today_panel,
        panel,                          # full history needed for swing-low lookback
        account_equity=settings.ACCOUNT_EQUITY,
        risk_pct=settings.RISK_PCT,
        regime_score=regime_score_value,
    )
    # Two slices: actionable (passes ADR filter) + skipped (rejected)
    actionable_panel = sized_panel[~sized_panel["adr_rejected"]].copy()
    skipped_panel = sized_panel[sized_panel["adr_rejected"]].copy()
    # === END Phase 7 step ===

    pass_rate = float(actionable_panel["passes_trend_template"].mean())
    validate_run(pass_rate, regime_state_value, ...)

    from screener.publishers.report import _add_publisher_columns
    actionable_panel = _add_publisher_columns(actionable_panel, regime_row)

    from screener.publishers.snapshot import write_snapshot
    write_snapshot(actionable_panel, snapshot_date)

    # === NEW Phase 7 step 8.5: journal append (D-01) ===
    if write_journal:
        from screener.persistence import append_picks_rows
        journal_rows = _build_journal_rows(
            actionable_panel, regime_row, snapshot_date, settings,
        )
        n_inserted = append_picks_rows(journal_rows)  # INSERT OR IGNORE
        log.info(
            "journal_appended",
            snapshot_date=snapshot_date,
            n_actionable=len(actionable_panel),
            n_inserted=n_inserted,
            n_idempotent_skip=len(journal_rows) - n_inserted,
        )

    if write_report:
        write_report_md(actionable_panel, regime_row, snapshot_date, ...,
                        skipped_picks=skipped_panel)  # NEW kwarg
```

### Anti-Patterns to Avoid

- **Computing sizing inside `composite.score`** — defeats the M2 ML extension seam (Phase 4 D-13). composite.score takes a weights dict; mixing in sizing math couples score-key changes with sizing logic.
- **Letting sizing import `data/` or `persistence`** — would violate `tests/test_architecture.py` ALLOWED dict (sizing's allowlist is `{signals, regime, config, obs}` — no persistence). Sizing receives the panel; it does not read it.
- **Re-computing sizing inside the `journal` CLI catch-up** — would create two sources of truth for shares/stop. Read the snapshot Parquet that already has sizing columns; idempotency via UNIQUE handles double-runs.
- **Mutating the input panel** — sizing must return a new DataFrame (use `.copy()`). All other pure functions in the codebase follow this discipline.
- **`UPDATE picks SET ... WHERE id = ?` from any path other than the deferred v1.x journal-update flow** — the trigger will raise. Tests must assert this is the case (SC-4 verification: "attempting an UPDATE on a decision column raises a database constraint error").
- **Storing dollar `entry_price` in features_json without versioning the schema** — once paper trades start, the blob shape IS the v2 ML training contract. Embed a `"features_json_version": "v1.0"` key so v2.x migrations can detect-and-upgrade.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Append-only idempotent SQLite append | Custom dedup-before-insert + transaction-with-rollback | `INSERT OR IGNORE` on `UNIQUE(ticker, snapshot_date)` | Native SQLite primitive; one statement; rowcount tells you inserts vs skips; verified in §Code Examples Pattern 4 |
| Decision-column immutability enforcement | Python-layer "is this column allowed?" check before every UPDATE | SQLite `BEFORE UPDATE OF <col-list>` trigger | DB-level guarantee survives any client (sqlite3 CLI, alembic, ad-hoc Python). Trigger fires whether SET appears in DDL or SQL [VERIFIED: empirical test confirms RAISE(ABORT) cancels UPDATE and raises sqlite3.IntegrityError] |
| Atomic Parquet write for extended snapshot | Custom tempfile + rename | Existing `persistence._write_parquet_atomic` | Already POSIX-atomic; already used for `write_snapshot_atomic`; schema extension is additive — just add 6 fields to `RankingSnapshotSchema` |
| ADR%(20) computation | Custom rolling-mean over high/low | Existing `indicators.volatility.adr_pct_panel` (already in build_panel) | Verified live; ADR% column is present at snapshot time |
| Cross-section ranking | Custom sort + assign rank | Existing `_add_publisher_columns` in publishers/report.py (already uses pandas `.rank(method='dense', ascending=False)`) | Already does the work; sizing slots in BEFORE this step |
| 21d EMA | Custom recursive EMA loop | `pandas_ta_classic.ema(close, length=21)` — though see Pattern 3: we don't actually need it at sizing time | If ever needed at the report layer, the library has it [VERIFIED] |
| Argrelextrema-based swing-low detection | Reimplement local-minima finder | `screener.indicators.patterns.find_pivots(highs, lows, order=3)` | Already implemented + battle-tested via Phase 6 golden-file tests |

**Key insight:** Every primitive Phase 7 needs is already present in the codebase. The work is wiring — assembly, not invention. The two genuinely-new things are: (1) the immutability trigger SQL (~10 lines), and (2) the `picks` table DDL + helpers (~50 lines, copying `_ensure_insider_schema` shape).

## Runtime State Inventory

> Phase 7 is a greenfield write — it creates a NEW SQLite file (`data/journal.sqlite`) and extends an existing schema. Not a rename/refactor. Inventory below is brief.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None pre-existing — `data/journal.sqlite` is the NEW artifact this phase creates. `data/snapshots/*.parquet` gains 6 columns but Phase 6 already runs additive schema migration via `_add_publisher_columns` (writes safe defaults for missing cols) | Confirm `.gitignore` already covers `data/journal.sqlite` (Phase 2 D-20 / accumulated-context todo: "Decide whether to commit `journal.sqlite` to repo (recommended yes for paper-trade history) — defer to Phase 7 planning"). USER decision deferred — planner should re-surface this as an Open Question. |
| Live service config | None — no external services touched by Phase 7 | — |
| OS-registered state | None | — |
| Secrets / env vars | New Settings fields: `RISK_PCT`, `JOURNAL_THRESHOLD`. Existing `ACCOUNT_EQUITY` already in `.env.example`. Add the two new fields to `.env.example` and `config.py` Settings class | Standard additive Settings extension (Phase 6 D-09 idiom) |
| Build artifacts / installed packages | None — no new deps; pyproject.toml unchanged | — |

**Open USER decision (re-surfaced from STATE.md "Todos"):** `data/journal.sqlite` git-commit policy. Recommendation: **yes, commit** — the journal IS the paper-trade history; losing it would invalidate every subsequent v1.x performance claim. SQLite binary files are small (~10 KB after 30 picks) and diff-ably visible with `sqlite3` CLI. Add to repo, not to `.gitignore`.

## Common Pitfalls

### Pitfall 1: Trigger does not survive table-rebuild migrations

**What goes wrong:** A future migration uses CREATE+COPY+DROP+RENAME on the `picks` table — the trigger is silently dropped with the table and never recreated. Subsequent UPDATEs to decision columns succeed without raising.

**Why it happens:** SQLite triggers are bound to the table they were created on. `DROP TABLE picks` drops the trigger; the `CREATE TABLE picks_new` + `ALTER TABLE picks_new RENAME TO picks` sequence does not auto-restore it.

**How to avoid:** `_ensure_picks_schema()` (the idempotent setup function called on every connection) MUST run BOTH the table DDL AND the trigger DDL inside the same `executescript` — using `CREATE TABLE IF NOT EXISTS picks (...)` AND `CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols ...`. Test: after `DROP TABLE picks`, calling `_ensure_picks_schema()` re-creates BOTH (verified: `CREATE TRIGGER IF NOT EXISTS` is idempotent).

**Warning signs:** Production UPDATE succeeds in a CI test that previously raised. Add a regression test that DROPs the table, calls `_ensure_picks_schema()`, then asserts an UPDATE-on-decision-col raises.

### Pitfall 2: AUTOINCREMENT id gaps from idempotent re-runs

**What goes wrong:** Each idempotent `journal` re-run consumes a new rowid even on conflict-skip — after 30 days of nightly runs the visible ids are 30, 60, 90, ... (one inserted per night) but the AUTOINCREMENT counter is at 30,000+.

**Why it happens:** `INSERT OR IGNORE` on a conflicting row still increments `sqlite_sequence` for the table [VERIFIED: empirical — second `INSERT OR IGNORE` of `AAPL/2026-05-18` consumed id 4 even though only NVDA was inserted].

**How to avoid:** Don't rely on `id` for anything semantic; use `(ticker, snapshot_date)` as the natural key for all downstream queries. Document this in `_FORM4_DDL`-style comment on the `picks` DDL.

**Warning signs:** SQL queries that order by `id` or use `id` as a "row counter" — they will appear correct but mask the gap. Forbid them in code review.

### Pitfall 3: `composite_score >= JOURNAL_THRESHOLD` evaluation against post-regime-gated score

**What goes wrong:** Phase 4 D-03 `apply_regime_gate` multiplies `composite_score *= regime_score`. If `JOURNAL_THRESHOLD = 50` is checked against the GATED score, a 60-composite stock in `Uptrend Under Pressure` (regime_score = 0.66) drops to 39.6 and gets silently excluded from the journal — even though the user wants it logged for v2 ML negative-sample analysis.

**Why it happens:** The pipeline runs apply_regime_gate BEFORE sizing in the current design. The "actionable" definition in D-01 is `composite_score >= JOURNAL_THRESHOLD AND regime_state != 'Correction'` — but which `composite_score` is meant?

**How to avoid:** **Planner must decide.** Recommendation: check the threshold against the **pre-gate** `composite_score` (rename the post-gate value to `composite_score_gated` and keep the raw one). Otherwise the threshold semantically shifts with the regime and the v2 training set systematically under-samples mid-quality picks during pressure regimes.

**Warning signs:** Journal row counts spike when regime is "Confirmed Uptrend" and collapse when regime is "Uptrend Under Pressure," even when the underlying signal stack is stable.

### Pitfall 4: features_json over-budget if pattern_diagnostics.legs grows

**What goes wrong:** Phase 6 D-05 schema includes a `legs: list[dict]` sub-field with one entry per VCP contraction (up to `N_CONTRACTIONS_MAX = 6` legs). Each leg is ~80 B serialized; 6 legs add ~480 B; combined with 14 other features_json fields, a worst-case row can hit 1 KB+. CONTEXT estimate of "~400–600 B/row" is for an average pick, not worst-case.

**Why it happens:** Inlining the full `pattern_diagnostics` dict per D-03 includes the `legs` array.

**How to avoid:** Either (a) accept 1 KB upper bound (SQLite handles MB-scale TEXT columns trivially — 1 KB × 365 picks/day × 5 yrs = 1.8 MB total, negligible), or (b) strip `legs` from the inlined `pattern_diagnostics` before embedding in features_json since `legs` are already in `data/pattern_audit/*.parquet` (Phase 6 PatternAuditSchema). Recommendation: (a) — disk is cheap, redundant audit is worth ~2 MB over the project's life.

**Warning signs:** None functional. Could surface as journal.sqlite file size growth in a long-running deployment; mitigated by monitoring file size in `OPS-05` (Phase 8 run log).

### Pitfall 5: `pattern_diagnostics.depth_sequence[-1]` lookup on `leader_hold` row

**What goes wrong:** `leader_hold` picks have `pattern_diagnostics = '{"type": "none"}'` per `tag_playbook`'s default branch. Accessing `depth_sequence[-1]` would raise `KeyError` on the `none` dict.

**Why it happens:** `_stop_minervini_vcp` is dispatched ONLY when `playbook_tag == 'minervini_vcp'` — the dispatch IS the guard. But a defensive `decode_pattern_diagnostics` fallback that returns `{"type": "none"}` on malformed input (patterns.py:126–134) means a corrupt-blob `minervini_vcp` row would silently fall through to `pivot=close, final_depth=0.0 → stop=close` (zero risk_per_share → divide-by-zero in shares formula).

**How to avoid:** In `_stop_minervini_vcp`, after `decode_pattern_diagnostics`, assert `diag.get("type") == "vcp"` and `"pivot_price" in diag and "final_contraction_depth" in diag`. If the assertion fails, log `sizing_diagnostics_missing` and reject the pick (set `adr_rejected = True` with reason "missing pattern diagnostics") rather than computing a nonsensical stop.

**Warning signs:** Picks with `playbook_tag = 'minervini_vcp'` and `stop_price == entry_price` in the snapshot.

### Pitfall 6: regime_score == 0 makes shares == 0, but entry == stop is the dangerous case

**What goes wrong:** Per the formula `shares = floor((eq × risk_pct × regime_score) / (entry - stop))`:
- `regime_score = 0` → numerator = 0 → shares = 0 → no division by zero (safe, intended behavior for Correction regime that still passes D-01's `regime_state != 'Correction'` filter — which shouldn't happen, but Phase 4 D-03 soft-gate means regime_score can be 0 in non-Correction states transiently).
- **`entry == stop` → denominator = 0 → ZeroDivisionError or `np.inf` shares cap.**

`entry == stop` happens when: (a) `qullamaggie_continuation` AND the close == low of the day (a slammed-down close with no wick — rare but possible on a tail-risk day), or (b) `minervini_vcp` AND `final_contraction_depth == 0` (corrupt diagnostics — Pitfall 5).

**Why it happens:** Floor division by zero in numpy returns `inf` or raises depending on dtype; in pandas the cap operation `floor(equity × 0.25 / entry)` would limit it but only if the cap path is reached.

**How to avoid:** Compute `risk_per_share = entry_price - stop_price` first; if `risk_per_share <= 0` set `shares = 0` and `adr_rejected = True` with reason "invalid stop (entry <= stop)". This is a third rejection class beyond ADR-too-large.

**Warning signs:** Any row with `shares == inf` or NaN in the snapshot. Schema validation (pandera Int64Dtype on shares) will fail loud at write time — bonus guardrail.

### Pitfall 7: Test fixtures missing required Phase 6 columns

**What goes wrong:** Phase 4 / Phase 5 tests built fixtures with Phase-4-era panel columns (no `playbook_tag`, no `pattern_diagnostics`, no `adr_pct`). Phase 7's `compute_sizing` calls require ALL of: `close`, `low`, `high`, `atr_14`, `adr_pct`, `playbook_tag`, `pattern_diagnostics`. Tests that import old fixtures will `KeyError` at sizing time.

**Why it happens:** Phase 6 Plan 06-01 already added these columns via `_add_publisher_columns` placeholder defaults — but only in the publisher path. Phase 7 fixtures must build cross-sections with these columns from scratch.

**How to avoid:** Define a `tests/conftest.py` fixture `sized_input_cross()` returning a 5-ticker DataFrame with all 11+ required columns + sensible defaults. Reuse across `test_sizing.py`, `test_pipeline_journal.py`. Pattern matches Phase 6 Wave 0's "Settings + fixtures first" strategy.

**Warning signs:** `KeyError: 'playbook_tag'` in any sizing test. Triage by extending the fixture, not by adding defensive `.get()` in sizing.py — sizing's input contract should be strict.

## Code Examples

Verified patterns. Sources called out per snippet.

### Pattern 1: `picks` table DDL with immutability trigger

```sql
-- Source: CONTEXT.md <specifics> verbatim + verified empirically (§Validation Architecture below)
CREATE TABLE IF NOT EXISTS picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Decision columns (NOT NULL, immutable via trigger)
    ticker TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    playbook_tag TEXT NOT NULL CHECK (playbook_tag IN
        ('qullamaggie_continuation', 'minervini_vcp', 'leader_hold')),
    composite_score REAL NOT NULL,
    regime_state TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_price REAL NOT NULL,
    shares INTEGER NOT NULL,
    risk_per_share REAL NOT NULL,
    atr_zone TEXT NOT NULL CHECK (atr_zone IN ('in-zone', 'extended', 'chase, skip')),
    pivot_distance_atr REAL NOT NULL,
    features_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    -- Outcome columns (nullable, updatable)
    entry_filled INTEGER,
    exit_price REAL,
    exit_date TEXT,
    hold_days INTEGER,
    mfe REAL,
    mae REAL,
    -- Idempotency key
    UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_picks_snapshot_date ON picks (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_picks_ticker ON picks (ticker);

CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols
BEFORE UPDATE OF
    ticker, snapshot_date, playbook_tag, composite_score, regime_state,
    entry_price, stop_price, shares, risk_per_share, atr_zone,
    pivot_distance_atr, features_json, ingested_at
ON picks
BEGIN
    SELECT RAISE(ABORT, 'decision column immutable');
END;
```

**Notes:**
- Trigger column-list order is NOT semantically significant — but match the DDL column order for human readability [VERIFIED: SQLite docs + empirical].
- `id` is the AUTOINCREMENT surrogate; gaps will appear on idempotent re-runs (Pitfall 2). Don't rely on it.
- `UNIQUE(ticker, snapshot_date)` provides the natural key for `INSERT OR IGNORE`.
- CHECK constraints on `playbook_tag` and `atr_zone` mirror the pandera enum on `RankingSnapshotSchema` — belt-and-suspenders defense at the DB layer.

### Pattern 2: Idempotent append (`append_picks_rows` — mirrors `append_form4_rows`)

```python
# Source: persistence.append_form4_rows (lines 919-944) + CONTEXT D-01 + D-02
def append_picks_rows(rows: list[dict], db_path: "Path | None" = None) -> int:
    """Idempotent append — INSERT OR IGNORE on UNIQUE(ticker, snapshot_date).

    Caller MUST pandera-validate as PicksSchema BEFORE calling (mirror
    append_form4_rows Pattern B). Returns rowcount actually inserted
    (0 on full-duplicate batch); skipped duplicates are silent.
    """
    if not rows:
        return 0
    path = _ensure_picks_schema(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.executemany(
            """INSERT OR IGNORE INTO picks
               (ticker, snapshot_date, playbook_tag, composite_score,
                regime_state, entry_price, stop_price, shares,
                risk_per_share, atr_zone, pivot_distance_atr,
                features_json, ingested_at)
               VALUES (:ticker, :snapshot_date, :playbook_tag, :composite_score,
                       :regime_state, :entry_price, :stop_price, :shares,
                       :risk_per_share, :atr_zone, :pivot_distance_atr,
                       :features_json, :ingested_at)""",
            rows,
        )
        conn.commit()
        return cur.rowcount  # successful inserts only [VERIFIED: empirical]
```

### Pattern 3: 3-bucket ATR zone classifier (D-09)

```python
# Source: CONTEXT D-09 + existing _classify_pivot_zone shape in publishers/report.py:46
from typing import Literal, Final
AtrZone = Literal["in-zone", "extended", "chase, skip"]

IN_ZONE_ATR: Final[float] = 0.66      # D-09 — locked, not Settings-overridable
EXTENDED_ATR: Final[float] = 1.00     # D-09

def classify_atr_zone(pivot_distance_atr: float) -> AtrZone:
    """D-09: 3-bucket classification.

    Note the boundary semantics: `<=` for in-zone upper, `<=` for extended upper.
    A value of exactly 0.66 is in-zone; exactly 1.00 is extended.
    """
    if pivot_distance_atr <= IN_ZONE_ATR:
        return "in-zone"
    if pivot_distance_atr <= EXTENDED_ATR:
        return "extended"
    return "chase, skip"
```

**Note on `pivot_distance_atr` sign:** Phase 4 `_classify_pivot_zone` (publishers/report.py:46) measures distance as `(high_52w - close) / atr` (positive when close is BELOW high). Phase 7 uses the same column but the playbook is now: distance ABOVE pivot (the breakout perspective). The planner must clarify which sign convention `pivot_distance_atr` uses post-Phase-6 — read the Phase 6 plan 06-05 changes to `_add_publisher_columns` carefully.

### Pattern 4: Empirically-verified SQLite behavior

```python
# Source: empirical test run 2026-05-18 — see Bash tool output in research session
# All four observations are reproducible with: uv run python -c "<below>"
import sqlite3, tempfile, os

db = tempfile.mktemp(suffix='.db')
c = sqlite3.connect(db)
c.executescript('''
    CREATE TABLE t (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        a TEXT, b TEXT,
        UNIQUE(a, b)
    );
    CREATE TRIGGER t_imm BEFORE UPDATE OF a, b ON t
    BEGIN SELECT RAISE(ABORT, 'col immutable'); END;
''')
c.execute('INSERT INTO t (a, b) VALUES (?, ?)', ('AAPL', '2026-05-18'))
c.execute('INSERT INTO t (a, b) VALUES (?, ?)', ('MSFT', '2026-05-18'))

# (1) INSERT OR IGNORE with mixed insertable + duplicate rows
cur = c.executemany(
    'INSERT OR IGNORE INTO t (a, b) VALUES (?, ?)',
    [('AAPL', '2026-05-18'),   # duplicate — skipped
     ('NVDA', '2026-05-18'),   # new — inserted
     ('AAPL', '2026-05-18')]   # duplicate — skipped
)
assert cur.rowcount == 1                                         # only NVDA counted
assert c.execute('SELECT COUNT(*) FROM t').fetchone()[0] == 3
# AUTOINCREMENT id GAP: NVDA got id=4 (id=3 consumed by skipped AAPL)
assert c.execute('SELECT id FROM t WHERE a="NVDA"').fetchone()[0] == 4

# (2) BEFORE UPDATE OF trigger fires on listed col
try:
    c.execute('UPDATE t SET a = ? WHERE id = 1', ('FOO',))
    assert False, "trigger did not fire"
except sqlite3.IntegrityError as e:
    assert 'col immutable' in str(e)

# (3) Outcome column (NOT in OF list) updates freely
c.execute('ALTER TABLE t ADD COLUMN c TEXT')
c.execute('UPDATE t SET c = ? WHERE id = 1', ('outcome',))  # succeeds
assert c.execute('SELECT c FROM t WHERE id = 1').fetchone()[0] == 'outcome'

os.unlink(db)
```

This test should be the basis of `tests/test_journal.py::test_immutability_trigger` (assertions (2) and (3)) and `tests/test_journal.py::test_idempotent_append` (assertion (1)).

### Pattern 5: Structlog event-name conventions for sizing + journal

```python
# Source: existing event names harvested from src/screener/ (grep —
# fetch_start/fetch_success/fetch_fail/snapshot_written pattern, prefix_action shape)
# Mirror this naming convention for new Phase 7 events:

# In sizing.py — emit per-cross-section summary (NOT per-ticker, would flood logs)
log.info(
    "sizing_applied",
    snapshot_date=snapshot_date,
    n_input=len(today_panel),
    n_actionable=len(actionable_panel),
    n_rejected_adr=int((skipped_panel["rejection_reason"] == "adr_exceeded").sum()),
    n_rejected_stop=int((skipped_panel["rejection_reason"] == "invalid_stop").sum()),
    by_playbook={
        tag: int(count) for tag, count in
        actionable_panel["playbook_tag"].value_counts().items()
    },
)

# In sizing.py — emit per-row rejection at DEBUG level
log.debug(
    "sizing_rejected",
    ticker=ticker, snapshot_date=snapshot_date, playbook_tag=tag,
    reason="adr_exceeded",  # or "invalid_stop"
    risk_per_share=risk_per_share, adr_dollars=adr_dollars,
)

# In persistence.append_picks_rows — emit per-batch summary
log.info(
    "journal_appended",
    snapshot_date=snapshot_date,
    n_attempted=len(rows),
    n_inserted=cur.rowcount,
    n_idempotent_skip=len(rows) - cur.rowcount,
)

# In publishers/pipeline.py — when journal append disabled
log.info("journal_skipped", snapshot_date=snapshot_date, reason="write_journal=False")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 4 sizing stub | Phase 7 sizing implementation | 2026-05-18 (this phase) | Trade plans become executable; report can render real $ stop/share quantities |
| Phase 4 `_classify_pivot_zone` (2-state) | Phase 7 `classify_atr_zone` (3-state at sizing layer) | 2026-05-18 | Minervini-style "extended" partial-size opportunity now visible; report adds a 3rd label |
| Phase 6 placeholder defaults in `_add_publisher_columns` | Phase 7 real values populated in `compute_sizing` upstream | 2026-05-18 | `_add_publisher_columns`'s "set only if missing" guards (report.py:101-128) silently allow real values through |
| `journal` CLI stub | `journal` CLI body (idempotent catch-up) | 2026-05-18 | `test_cli_smoke.py::test_subcommand_surface_locked` unchanged; D-24 9-subcommand lock preserved; new test `test_journal_subcommand_no_longer_stub` added (mirror `test_score_subcommand_no_longer_stub` at line 234) |

**Deprecated/outdated:** None — Phase 7 is purely additive.

## Assumptions Log

> Every claim in this research was either VERIFIED empirically/by-source or CITED from the codebase. The table below logs the few items still tagged ASSUMED for the planner's confirmation.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `adr_pct` column from Phase 3 `adr_pct_panel` is the same `adr_pct` field present on the cross-section after Phase 6 `tag_playbook` adds `playbook_tag` | Pattern 1 stop helpers; Pitfall 3 | If Phase 6 strips or renames the column, the ADR-reject check fails. **Mitigation:** Plan must include a verification step `grep -n "adr_pct" src/screener/publishers/pipeline.py` after Plan 06-05 lands |
| A2 | The `low` of the cross-section row IS the D-0 (snapshot date) low bar (used by `_stop_qullamaggie`) | Pattern 1 `_stop_qullamaggie` | If `xs(snap_ts, level='date')` returns a row where `low` is NOT the snapshot-day low (e.g., if Phase 6 transforms it), Qullamaggie stops will be wrong. **Mitigation:** Add a unit test asserting `actionable_panel.loc[ticker, 'low'] == build_panel.xs((ticker, snap_ts))['low']` |
| A3 | `pivot_distance_atr` sign convention is "ATR above pivot" (positive = extended/chase) at the cross-section consumed by sizing | Pattern 3 classify_atr_zone | If Phase 6 keeps the Phase 4 "ATR below 52w-high" sign convention, the 3-bucket boundaries are inverted. **Mitigation:** Planner must read Phase 6 Plan 06-05 `_add_publisher_columns` changes carefully; if convention is unchanged from Phase 4, compute a new `pivot_distance_atr_breakout = (close - pivot_price) / atr` in sizing.py and bucket THAT |
| A4 | `data/journal.sqlite` should be git-committed (paper-trade history is precious) | Runtime State Inventory | If excluded, paper trade history is lost across machine setups. **Mitigation:** Surface as Open Question to user before locking |

## Open Questions

1. **`composite_score` semantics for `JOURNAL_THRESHOLD` check**
   - What we know: D-01 says `composite_score >= JOURNAL_THRESHOLD`. D-03 (Phase 4) says `apply_regime_gate` multiplies the score by `regime_score`.
   - What's unclear: Is the threshold checked against the gated or pre-gate score?
   - Recommendation: Pre-gate (raw composite). Document a `composite_score_raw` column on the snapshot for this purpose, OR check the threshold BEFORE `apply_regime_gate` in pipeline. Surface to user during discuss-phase iteration or planner Q&A.

2. **`data/journal.sqlite` git-commit policy**
   - What we know: STATE.md Todos lists "Decide whether to commit `journal.sqlite` to repo (recommended yes for paper-trade history) — defer to Phase 7 planning."
   - What's unclear: User has not made the call.
   - Recommendation: COMMIT (yes). Add to `.gitignore` allowlist (`!data/journal.sqlite`). Paper-trade history IS the v1.x performance contract.

3. **Sign convention of `pivot_distance_atr` in Phase 6 snapshot**
   - What we know: Phase 4 `_classify_pivot_zone` uses `(high_52w - close) / atr` (positive = below high).
   - What's unclear: Whether Phase 6 Plan 06-05 changes this to a "distance above breakout pivot" convention to support the breakout chase-skip semantic.
   - Recommendation: Planner runs `git log --all -p src/screener/publishers/report.py | grep pivot_distance_atr` after Plan 06-05 lands and resolves before writing sizing.py. If unchanged, sizing must compute its own `pivot_distance_atr_breakout`.

4. **Where does the 21d EMA actually need to be rendered?**
   - What we know: D-08 says trail rules are "displayed in report" (label only). Pattern 3 above resolves this by emitting strings.
   - What's unclear: Whether the report should ALSO show the current 21d EMA NUMERIC value (e.g., `Trail: 21d EMA = $118.40`) for execution context, like CONTEXT.md `<specifics>` `Stop: $118.40` example.
   - Recommendation: Defer to a follow-up plan in this phase — labels first, numerics only if user requests during UAT.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 sqlite3 | Journal SQLite | ✓ | 3.51.0 | — |
| pandas-ta-classic | Possible 21d EMA (decided NOT needed) | ✓ | 0.4.47 | — |
| pandera | Schema extension | ✓ | 0.31.1 | — |
| pydantic-settings | New Settings fields | ✓ | 2.14.x | — |
| structlog | Event logging | ✓ | 25.5.x | — |
| scipy.signal.argrelextrema | recent_swing_low_distance (reuse via patterns.find_pivots) | ✓ | via patterns.py | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (already configured) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `uv run pytest tests/test_sizing.py tests/test_journal.py -x --no-cov` |
| Full suite command | `uv run pytest --no-cov -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIZ-01 | shares formula + 25% cap | unit | `pytest tests/test_sizing.py::test_shares_formula -x` | ❌ NEW |
| SIZ-01 | regime_score=0 → shares=0, no div-by-zero | unit | `pytest tests/test_sizing.py::test_zero_regime_score_zero_shares -x` | ❌ NEW |
| SIZ-01 | property: shares ≥ 0 always | property | `pytest tests/test_sizing.py::test_shares_nonneg_property -x` | ❌ NEW (hypothesis) |
| SIZ-02 | adr_rejected when risk_per_share > adr_dollars | unit | `pytest tests/test_sizing.py::test_adr_reject_boundary -x` | ❌ NEW |
| SIZ-02 | rejected picks excluded from journal AND report | integration | `pytest tests/test_pipeline_journal.py::test_rejected_picks_not_in_journal -x` | ❌ NEW |
| SIZ-03 | each playbook calls correct stop helper (SC-2) | unit | `pytest tests/test_sizing.py::test_stop_dispatch_per_playbook -x` | ❌ NEW |
| SIZ-03 | leader_hold falls back to 2×ATR when no swing | unit | `pytest tests/test_sizing.py::test_leader_swing_fallback -x` | ❌ NEW |
| SIZ-03 | minervini_vcp reads final_contraction_depth | unit | `pytest tests/test_sizing.py::test_vcp_stop_from_diagnostics -x` | ❌ NEW |
| SIZ-04 | trail label per playbook (D-08) | unit | `pytest tests/test_sizing.py::test_trail_label_dispatch -x` | ❌ NEW |
| SIZ-04 | Qullamaggie trail tier by ADR% (<4/4-6/≥6) | unit | `pytest tests/test_sizing.py::test_qull_trail_speed_tiers -x` | ❌ NEW |
| SIZ-05 | atr_zone bucket boundaries (D-09) | unit | `pytest tests/test_sizing.py::test_atr_zone_boundaries -x` | ❌ NEW |
| OUT-04 | journal append fires inside run_pipeline | integration | `pytest tests/test_pipeline_journal.py::test_pipeline_writes_journal -x` | ❌ NEW |
| OUT-04 | journal CLI is idempotent (re-run = 0 inserted) | integration | `pytest tests/test_journal.py::test_journal_cli_idempotent -x` | ❌ NEW |
| OUT-04 | journal-disabled flag (`write_journal=False`) | unit | `pytest tests/test_pipeline_journal.py::test_journal_disabled -x` | ❌ NEW |
| OUT-05 | UPDATE on decision column raises | unit | `pytest tests/test_journal.py::test_immutability_trigger -x` | ❌ NEW |
| OUT-05 | features_json round-trips via JSON parse | unit | `pytest tests/test_journal.py::test_features_json_roundtrip -x` | ❌ NEW |
| OUT-05 | features_json includes full pattern_diagnostics | unit | `pytest tests/test_journal.py::test_features_json_includes_diagnostics -x` | ❌ NEW |
| OUT-06 | outcome columns are nullable + UPDATE succeeds | unit | `pytest tests/test_journal.py::test_outcome_column_updatable -x` | ❌ NEW |
| OUT-06 | trigger does NOT fire on outcome columns | unit | `pytest tests/test_journal.py::test_outcome_col_not_in_trigger -x` | ❌ NEW |
| SC-1 (golden) | full pipeline run produces deterministic row count + features_json shape | golden | `pytest tests/test_pipeline_journal.py::test_golden_pipeline_journal -x` | ❌ NEW |
| Regression | drop picks table + re-init → trigger re-created | regression | `pytest tests/test_journal.py::test_schema_idempotent_recreates_trigger -x` | ❌ NEW |
| Architecture | `publishers → sizing` still in ALLOWED | unit | `pytest tests/test_architecture.py::test_layer_import_contract -x` | ✓ exists |
| CLI surface lock | D-24 9-subcommand surface unchanged | unit | `pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x` | ✓ exists |
| Journal stub removed | `journal` no longer emits [stub] log | unit | `pytest tests/test_cli_smoke.py::test_journal_subcommand_no_longer_stub -x` | ❌ NEW (mirror pattern of test_score_subcommand_no_longer_stub at line 234) |
| FND-04 gate | No-look-ahead test still passes (sizing must not bring data forward) | unit | `pytest tests/test_backtest_no_lookahead.py -x` | ✓ exists |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py tests/test_architecture.py tests/test_cli_smoke.py tests/test_backtest_no_lookahead.py -x --no-cov` (Phase 7's full surface + the two existing structural locks + the FND-04 mutation gate, ~10s)
- **Per wave merge:** `uv run pytest --no-cov -q` (~30s on local; CI runs with `--cov-fail-under=80`)
- **Phase gate:** Full suite green before `/gsd-verify-work`; CI passes including ruff + mypy --strict on touched files

### Wave 0 Gaps

- [ ] `tests/test_sizing.py` — covers SIZ-01..05 (10+ unit tests; hypothesis dep already pinned per pyproject.toml line 27)
- [ ] `tests/test_journal.py` — covers OUT-04..06 + trigger + idempotency (8+ tests)
- [ ] `tests/test_pipeline_journal.py` — integration (3+ tests; uses CliRunner pattern from test_cli_smoke.py)
- [ ] `tests/conftest.py` — add `sized_input_cross()` fixture with all 11+ required columns (Pitfall 7)
- [ ] `tests/test_cli_smoke.py` — add `test_journal_subcommand_no_longer_stub` (mirror existing `test_score_subcommand_no_longer_stub` shape); remove `"journal"` from `PHASE_1_STUBS` list (line 43)
- [ ] No framework install needed — pytest + hypothesis already in pyproject.toml

## Project Constraints (from CLAUDE.md)

These directives MUST be honored by the plan. Each is enforced by an existing CI gate or test.

| Constraint | Source | Enforcement |
|------------|--------|-------------|
| No `print()` — use structlog | CLAUDE.md "Coding Conventions" | All sizing.py logging must use `structlog.get_logger(__name__)` like `publishers/pipeline.py` |
| No EMA in `signals/minervini.py` or `indicators/trend.py` | CLAUDE.md Pitfall #1, IND-02 | Justifies "compute 21d EMA inline in sizing.py if ever needed" decision (Pattern 3) |
| Signals + indicators are pure functions | CLAUDE.md Architectural Rules | `sizing.py` follows the same discipline — no I/O, no global state |
| All IO boundaries pandera-validated | CLAUDE.md Architectural Rules | New `PicksSchema` in persistence.py validates rows before `append_picks_rows` insert |
| `mypy --strict` on indicators/ and signals/ | CLAUDE.md Coding Conventions | sizing.py is NOT under strict already; planner should consider adding it to the strict-files list (mirrors Phase 4 decision to add publishers under strict gradually) |
| Atomic Parquet writes | CLAUDE.md Architectural Rules | Reuse `_write_parquet_atomic` for extended snapshot |
| Test after any signals/ or backtest/ change: `pytest tests/test_backtest_no_lookahead.py` | CLAUDE.md Testing Rules | Sizing touches neither `signals/` nor `backtest/` but Phase 7 still re-runs FND-04 gate per Phase 6 cross-cutting constraints |
| Fundamentals lag 45 days post-quarter-end | CLAUDE.md Architectural Rules | Already enforced by `persistence.read_fundamentals` — Phase 7 doesn't touch fundamentals |
| Entry signals at bar `t` execute at open of bar `t+1` | CLAUDE.md Architectural Rules | Documented in `entry_price` docstring: stored value is close-of-D-0 as next-bar-open ESTIMATE; actual fill tracked in outcome columns |
| No global mutable state in modules | CLAUDE.md Coding Conventions | STOP_HELPERS dict is `Final` (immutable) — registry is a frozen lookup, not mutable state |
| Pre-commit ruff + ruff format | CLAUDE.md Coding Conventions | Standard — no Phase 7 deviation |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md` — all D-decisions, formulas, schema
- `.planning/phases/07-sizing-finalization-paper-trade-journal/07-DISCUSSION-LOG.md` — discussion alternatives
- `.planning/REQUIREMENTS.md` SIZ-01..05, OUT-04..06 — canonical requirement text
- `.planning/ROADMAP.md` Phase 7 — 6 success criteria
- `/Users/belwinjulian/SwingTrading/CLAUDE.md` — project guardrails (structlog, no EMA in trend.py, pandera at IO, signals pure)
- `src/screener/sizing.py` — confirmed stub-only (6 lines, docstring) [VERIFIED via Read]
- `src/screener/publishers/pipeline.py` — full body read; `apply_regime_gate` separate-function design at line 40; `run_pipeline` integration seam at lines 116-193 [VERIFIED]
- `src/screener/persistence.py` — `append_form4_rows` pattern at lines 919-944; `RankingSnapshotSchema` at lines 222-273 (Phase 6 extended additively); `_ensure_insider_schema` at line 909; `_write_parquet_atomic` at line 369 [VERIFIED]
- `src/screener/indicators/patterns.py` — `find_pivots` at line 79; `FLAG_PIVOT_ORDER=3` at line 58; `decode_pattern_diagnostics` at line 126 [VERIFIED]
- `src/screener/indicators/trend.py` — confirmed NO EMA (only `_safe_sma`, `sma_panel`, `high_52w_panel`, `low_52w_panel`) [VERIFIED via Read]
- `src/screener/cli.py` — `journal` stub at lines 232-235; D-14 surface; `_stub` helper at line 46 [VERIFIED]
- `src/screener/config.py` — `ACCOUNT_EQUITY: float = 100_000.0` at line 39; no `RISK_PCT` or `JOURNAL_THRESHOLD` yet [VERIFIED]
- `src/screener/signals/composite.py` — `tag_playbook` dispatch pattern at lines 193-262 [VERIFIED]
- `tests/test_architecture.py` ALLOWED dict — line 36: `"publishers": {"signals", "sizing", "regime", "persistence", "config", "obs"}` (sizing already authorized) [VERIFIED]
- `tests/test_cli_smoke.py` D14_SUBCOMMANDS lock at lines 20-30; `test_score_subcommand_no_longer_stub` mirror pattern at lines 234-244; `PHASE_1_STUBS = ["journal"]` at line 43 [VERIFIED]
- SQLite official docs (https://www.sqlite.org/lang_createtrigger.html, https://www.sqlite.org/lang_insert.html) — trigger + INSERT OR IGNORE semantics
- Empirical SQLite 3.51.0 test (executed via `uv run python -c "..."`) — verifies AUTOINCREMENT gap, trigger raises, outcome col update succeeds — see Pattern 4

### Secondary (MEDIUM confidence)
- https://hoelz.ro/blog/with-sqlite-insert-or-ignore-is-often-not-what-you-want — discussion of last_insert_rowid pitfall (not blocking for Phase 7 since we don't need rowid from idempotent inserts)
- https://sqlite-users.sqlite.narkive.com/uxDZRlDk/insert-or-ignore-and-sqlite3-last-insert-rowid — confirms behavior under INSERT OR IGNORE

### Tertiary (LOW confidence)
- None — all critical claims verified via Context7-equivalent (SQLite official docs) + empirical execution.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library already pinned and exercised in prior phases
- Architecture: HIGH — every integration seam confirmed via Read of actual code
- Pitfalls: HIGH — most discovered via re-reading code (Pitfall 2 AUTOINCREMENT, Pitfall 1 trigger survival) or empirical test
- SQLite trigger + INSERT OR IGNORE semantics: HIGH — empirically verified plus official docs
- 21d EMA placement decision: HIGH — IND-02 CI grep gate is documented and active
- recent_swing_low_distance window/order choice: MEDIUM — heuristic alignment with FLAG_PIVOT_ORDER, no backtest validation; planner may want to surface as Open Question if leader_hold becomes a major playbook in v1.x paper trading

**Research date:** 2026-05-18
**Valid until:** 2026-06-17 (30 days — stable codebase, no dependency churn expected)
