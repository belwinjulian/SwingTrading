---
phase: 07-sizing-finalization-paper-trade-journal
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - .env.example
  - .gitignore
  - src/screener/cli.py
  - src/screener/config.py
  - src/screener/persistence.py
  - src/screener/publishers/pipeline.py
  - src/screener/publishers/report.py
  - src/screener/sizing.py
  - tests/conftest.py
  - tests/test_architecture.py
  - tests/test_cli_smoke.py
  - tests/test_journal.py
  - tests/test_pipeline_journal.py
  - tests/test_publishers_report.py
  - tests/test_sizing.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-18T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 7 delivers sizing finalization (`sizing.py`), journal persistence (`persistence.py` `PicksSchema` / `_PICKS_DDL`), pipeline wiring (`publishers/pipeline.py`), report rendering (`publishers/report.py`), and the `journal` CLI subcommand (`cli.py`). The architecture is sound, the DAG is well-documented, and the journal's immutability trigger and idempotency contract are correctly implemented.

Two blockers were found. The more severe is a rendering bug in the `## Skipped Picks` report section: the live pipeline produces a skipped-picks DataFrame with an integer index (after `_add_publisher_columns` calls `reset_index()`), but `render_report` uses the index value as the ticker label — printing `"0"`, `"1"`, etc. instead of real ticker symbols. The test for this section passes only because it manufactures a ticker-named index directly. The second blocker is a correctness gate (`assert`) in `apply_regime_gate` that is silently disabled by `python -O`.

Four warnings cover a silent ADR-gate bypass for zero/NaN `adr_pct`, a misleading rejection-count log metric, the `screener score` command undocumented journal side-effect, and persistent `print()` calls in `cli.py` that violate the project convention.

---

## Critical Issues

### CR-01: Skipped Picks section renders integer index as ticker symbol

**File:** `src/screener/publishers/report.py:490`

**Issue:** `render_report` iterates over `skipped_picks` using `for ticker, srow in skipped_picks.iterrows()`. The `ticker` loop variable is the DataFrame's **index value**. In the live pipeline, `skipped_view` is sliced from `today_panel` after `_add_publisher_columns` has called `reset_index()` (line 133 of `report.py`). That reset gives `today_panel` an integer range index and promotes `ticker` to a column. `skipped_view` inherits this integer index, so `ticker` in the loop is `0`, `1`, `2`, ... and `ticker_str` becomes `"0"`, `"1"`, etc. instead of the actual ticker symbol.

The unit test `test_render_report_includes_sizing_fields_and_skipped_section` escapes this because it manually constructs `skipped` with `index=pd.Index(["BADTICK"], name="ticker")` — a ticker-named index — so the test passes while the live path is broken.

**Fix:** Use the `ticker` column from the row rather than the index:

```python
# In render_report, replace the iteration block:
for _, srow in skipped_picks.iterrows():
    ticker_str = (
        str(srow["ticker"])
        if "ticker" in srow.index
        else str(srow.name)
    )
    reason = str(srow.get("rejection_reason", ""))
    # ... rest unchanged
```

Alternatively, ensure `skipped_view` is ticker-indexed before being passed to `render_report`:

```python
# In run_pipeline, after building skipped_view:
skipped_view = today_panel[
    today_panel["adr_rejected"]
    & today_panel["playbook_tag"].isin(_valid_playbook_tags)
].copy()
if "ticker" in skipped_view.columns:
    skipped_view = skipped_view.set_index("ticker")
```

---

### CR-02: `assert` in `apply_regime_gate` silently removed by `python -O`

**File:** `src/screener/publishers/pipeline.py:68`

**Issue:** The range guard on `regime_score` is implemented as a Python `assert`:

```python
assert 0.0 <= regime_score <= 1.0, (
    f"regime_score out of range: {regime_score} ..."
)
```

Python's `-O` (optimize) flag strips all `assert` statements at bytecode compilation. If the production environment uses optimized bytecode (e.g. `PYTHONOPTIMIZE=1`, `python -O`, or a packaging step that strips asserts), this guard disappears. A `regime_score > 1.0` would then silently produce `composite_score` values above 100, corrupting the snapshot and the journal.

**Fix:** Replace the `assert` with an explicit `ValueError` raise:

```python
if not (0.0 <= regime_score <= 1.0):
    raise ValueError(
        f"regime_score out of range: {regime_score} (expected [0, 1])"
    )
```

---

## Warnings

### WR-01: `adr_pct=0` or `NaN` silently bypasses the ADR rejection guard

**File:** `src/screener/sizing.py:306-308`

**Issue:** The 1xADR auto-reject condition is:

```python
if rejection == "" and risk_per_share > adr_dollars and adr_dollars > 0:
    rejection = "adr_exceeded"
```

When `adr_pct` is `0.0` (missing data, zero-volatility sentinel) **or** `NaN` (indicator warmup period), `adr_dollars` becomes `0.0` or `NaN`. In both cases `adr_dollars > 0` evaluates to `False`, and the pick passes through with full position sizing. A stock with no meaningful ADR data receives a position sized as if the ADR guard passed.

**Fix:** Treat `adr_pct <= 0` or `NaN` as a rejection condition:

```python
adr_dollars = (adr_pct / 100.0) * close_price
if rejection == "" and (
    not (adr_dollars > 0) or risk_per_share > adr_dollars
):
    rejection = "adr_exceeded"
```

Or equivalently:

```python
if rejection == "":
    if not (adr_dollars > 0) or risk_per_share > adr_dollars:
        rejection = "adr_exceeded"
```

This ensures a missing or zero ADR measurement is treated as a hard reject rather than a silent pass.

---

### WR-02: `sizing_pipeline_full_frame` log's `n_rejected` counts ~95% universe as rejections

**File:** `src/screener/publishers/pipeline.py:420`

**Issue:** The log event `sizing_pipeline_full_frame` reports:

```python
n_rejected=int(today_panel["adr_rejected"].sum()),
```

`compute_sizing` runs on the **full** ~1000-row cross-section. Every row with `playbook_tag='none'` (~95% of universe) lands with `adr_rejected=True` and `rejection_reason='invalid_stop'` because its `stop_price == close_price` (risk=0). This means `n_rejected` will always be ~950+ regardless of whether real sizing candidates have ADR problems, making the metric useless for operators monitoring sizing quality.

**Fix:** Restrict the logged rejection count to rows with a valid playbook tag:

```python
_actionable_mask = today_panel["playbook_tag"].isin(_valid_playbook_tags)
n_rejected_actionable = int(
    (today_panel.loc[_actionable_mask, "adr_rejected"]).sum()
)
log.info(
    "sizing_pipeline_full_frame",
    snapshot_date=snapshot_date,
    n_universe=len(today_panel),
    n_actionable_tag=int(_is_actionable_tag.sum()),
    n_rejected_actionable=n_rejected_actionable,
)
```

---

### WR-03: `screener score` silently appends to the journal

**File:** `src/screener/cli.py:205`

**Issue:** `cli.score` calls:

```python
run_pipeline(date.today().isoformat(), write_report=False)
```

`run_pipeline`'s `write_journal` parameter defaults to `True`. Therefore, `screener score` (documented as "Compute composite scores; write snapshot Parquet") **also** appends actionable picks to `data/journal.sqlite` on every invocation — a side effect not mentioned in the command docstring. A developer running `screener score` to inspect the snapshot will pollute the paper-trade journal.

**Fix:** Either pass `write_journal=False` explicitly in `cli.score`, or update the docstring to disclose the journal side-effect, whichever matches the intended contract:

```python
# Option A: disable journal write in score (recommended)
run_pipeline(date.today().isoformat(), write_report=False, write_journal=False)

# Option B: document the side-effect
@app.command("score")
def score() -> None:
    """Compute composite scores; write snapshot Parquet + append journal rows."""
```

---

### WR-04: `cli.py` uses `print()` in three subcommand bodies

**File:** `src/screener/cli.py:303`, `309`, `457`, `459`

**Issue:** CLAUDE.md explicitly prohibits `print()` ("No `print()` anywhere — use `structlog`"). The `backtest` and `backtest-audit` subcommands emit several `print()` calls:

- `backtest`: two `print()` calls for the Sharpe summary and report path (lines 303-309)
- `backtest-audit`: two `print()` calls for `"AUDIT FAILED"` and `"AUDIT PASSED"` (lines 457, 459)

These bypass the structured-logging sink and will not appear in JSON log aggregators or be grep-able with the project's log-key pattern.

**Fix:** Replace each `print()` with `log.info(...)`:

```python
# In backtest, replace print() calls:
log.info(
    "backtest_summary",
    sharpe_min=result.sharpe_min,
    sharpe_median=result.sharpe_median,
    sharpe_max=result.sharpe_max,
    n_windows=len(result.windows),
    n_zero_trade_windows=result.n_zero_trade_windows,
)
log.info("backtest_report_written", report=str(report_path))

# In backtest-audit:
log.info("audit_result", result="AUDIT PASSED" if failures == 0 else f"AUDIT FAILED ({failures} checks failed)")
```

---

## Info

### IN-01: `sized_input_cross` fixture `INVS` row comment is misleading

**File:** `tests/conftest.py:577`, `614`

**Issue:** The `INVS` row is documented as "tail-risk close==low (Pitfall 6: entry==stop guard)" but `INVS` uses `playbook_tag='leader_hold'`. The `leader_hold` stop helper computes `entry_price - clamp(max(1.5×ATR, swing_dist), max=2×ATR)` — it never sets `stop = low`. With `atr_14=1.0`, `adr_pct=3.0`, `close=50`, and the fallback `swing_dist=2×ATR=2.0`, the computed stop is `48.0` and `risk_per_share=2.0 > adr_dollars=1.5`, so `INVS` gets `adr_exceeded` rejection — **not** an `invalid_stop` rejection as the comment implies. No test directly asserts the `INVS` rejection reason, so the misleading comment goes undetected.

**Fix:** Update the fixture docstring to reflect the actual behavior and add an assertion:

```python
# In conftest.py fixture docstring:
#   - INVS  → leader_hold; adr_pct=3.0 low enough that risk > 1xADR → adr_exceeded
#     (close==low is incidental; Pitfall 6 invalid_stop is NOT triggered for leader_hold)
```

---

### IN-02: `test_report_data_quality_gate_d08` fake pipeline signature missing `write_journal` kwarg

**File:** `tests/test_cli_smoke.py:217`

**Issue:** The fake pipeline used by `test_report_data_quality_gate_d08` has signature:

```python
def fake_pipeline(snapshot_date: str, write_report: bool = True) -> None:
```

`cli.report` calls `run_pipeline(date.today().isoformat(), write_report=True)` without explicitly passing `write_journal`, so the current default matches. However, if `cli.report` is ever updated to pass `write_journal=True` explicitly (which it arguably should, per WR-03), this test would fail with `TypeError: unexpected keyword argument`. The fake pipeline's missing kwarg makes it a fragile regression target.

**Fix:** Add `write_journal: bool = True` to the fake pipeline signature to future-proof it:

```python
def fake_pipeline(
    snapshot_date: str,
    write_report: bool = True,
    write_journal: bool = True,
) -> None:
    from screener.publishers.pipeline import validate_run
    validate_run(0.30, "Correction", 0.25, 0.25)
```

---

### IN-03: `_write_parquet_atomic` has a narrow empty-temp-file orphan window

**File:** `src/screener/persistence.py:481-494`

**Issue:** The `NamedTemporaryFile` context manager exits (closing the file) **before** `df.to_parquet(tmp_path, ...)` writes any content. If the process is killed in the narrow window between the `with` block exit and the `to_parquet` call, an empty `.tmp` file is left on disk. The `report.py` comment (`IN-01`, iter 3) explicitly acknowledges this disparity versus the consolidated `write-inside-with` structure used in `_write_text_atomic`, but marks it as a "follow-up."

This is a correctness gap (orphan temp files accumulate on hard kills), not a data-corruption risk (the actual target file is never touched). It is already documented in the codebase as a known follow-up item.

**Fix:** Consolidate the write inside the `with` block, mirroring `_write_text_atomic`:

```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            # Write inside the with-block so the file handle is still open.
            # Pyarrow accepts a Path; the file object is flushed on context exit.
        df.to_parquet(tmp_path, engine="pyarrow", index=True)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

Note: `pyarrow` writes to the path, not the file object, so the write must remain after the `with` block. The complete fix requires using a different approach (e.g., write to a `BytesIO` buffer and then `tmp.write(buf.getvalue())` inside the `with` block), or accept the narrow window as a known limitation. At minimum, the comment should be updated to track this as an open issue with an assigned plan.

---

_Reviewed: 2026-05-18T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
