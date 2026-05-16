# Phase 5 — Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 12 (10 NEW + 2 MODIFIED)
**Analogs found:** 12 / 12 (every file has an in-repo analog; mostly close-match)

---

## Architecture constraint reminder

`tests/test_architecture.py:30-44` says `ALLOWED["backtest"] = {"persistence"}` (D-16/D-17 verbatim). **All `src/screener/backtest/*.py` files MUST NOT import**:
- `screener.signals`, `screener.indicators`, `screener.regime`, `screener.sizing`, `screener.publishers`
- `screener.config` (forbids reaching API keys)
- `screener.obs` (forbids env-coupled logger)
- `screener.data` (forbids network)

**Allowed inside `backtest/`:** stdlib (`logging`, `os`, `pathlib`, `tempfile`, `datetime`, `subprocess` only via cli.py), third-party (`pandas`, `numpy`, `vectorbt`), and `screener.persistence` only.

There is also an explicit second test — `tests/test_architecture.py:136-161` `test_backtest_does_not_import_data_layer` — that scans `backtest/*.py` for any forbidden internal import and fails CI immediately. **Plan plans must include `import logging; log = logging.getLogger(__name__)` everywhere inside `backtest/`**, NOT structlog.

---

## File Classification

| New/Modified | Role | Data Flow | Closest Analog | Match Quality |
|--------------|------|-----------|----------------|---------------|
| `src/screener/backtest/vbt_runner.py` (NEW) | harness (compute → write) | batch transform | `src/screener/publishers/pipeline.py` | role-match (orchestration shape only; CANNOT inherit imports) |
| `src/screener/backtest/walkforward.py` (NEW) | utility (pure date arithmetic) | transform | RESEARCH §A Q3 verbatim block; no in-repo analog | **greenfield** — no rolling-window helper in repo |
| `src/screener/backtest/metrics.py` (NEW) | utility (cross-window aggregation) | transform | none — closest spirit is `src/screener/regime.py` (vector aggregate) | greenfield |
| `src/screener/backtest/report.py` (NEW) | report writer (markdown) | file-I/O | `src/screener/publishers/report.py` (write_report + atomic) | role-match (must NOT inherit structlog or config) |
| `scripts/backfill_snapshots.py` (NEW) | one-off script (argparse + sys.exit) | batch loop | `scripts/check_preregistration.py` | exact (script-shape match) |
| `tests/test_backtest_no_lookahead.py` (NEW) | integration test (CI gate) | request-response | `tests/test_preregistration_check.py` + `tests/test_publishers_snapshot.py` | role-match (parametrize + monkeypatch + tmp_path) |
| `tests/test_walkforward_windows.py` (NEW) | unit test (pure) | request-response | `tests/test_publishers_pipeline.py` (4-arg parametrized) | exact |
| `tests/test_slippage_tiers.py` (NEW) | unit test (pure panel) | transform | `tests/test_publishers_pipeline.py` (panel-in, value-out) | exact |
| `tests/test_backtest_audit.py` (NEW) | CLI test (CliRunner + tmp dirs) | request-response | `tests/test_cli_smoke.py` | exact |
| `.github/workflows/no-lookahead-gate.yml` (NEW) | CI workflow | event-driven | `.github/workflows/ci.yml` | role-match (split per RESEARCH §C Q8 Option A) |
| `src/screener/cli.py` (MODIFIED) | CLI composition root | request-response | existing `score` + `report` filled-stub pattern in same file (lines 198–229) | exact (in-file pattern) |
| `Makefile` (MODIFIED) | build target | event-driven | existing `backtest` / `backtest-audit` targets in same file (lines 31–35) | exact — only `backfill-snapshots` is genuinely new |
| `tests/conftest.py` (MODIFIED) | fixture | provider | existing `synthetic_multi_ticker_panel` (conftest.py:290-313) | exact (GBM panel shape) |

---

## Pattern Assignments

### `src/screener/backtest/vbt_runner.py` (NEW)

**Role:** Walk-forward harness; reads pre-computed snapshots + OHLCV; constructs entries/exits; applies `.shift(1)` (or bypasses it for `_lookahead=True`); calls `vbt.Portfolio.from_signals`; returns a `BacktestResult`.

**Closest analog:** `src/screener/publishers/pipeline.py` — same disk-read → compute → write orchestration shape.

**Pattern to replicate (orchestrator skeleton, pipeline.py:116-193):**
```python
def run_pipeline(snapshot_date: str, write_report: bool = True) -> None:
    settings = get_settings()
    # 1. Build the indicator panel for the snapshot date.
    panel = build_panel(snapshot_date)
    # 2. Compute Trend Template gate + score columns.
    panel = passes_trend_template(panel)
    ...
    # 8. Write the Parquet snapshot (always — used by Phase 5 backtest).
    from screener.publishers.snapshot import write_snapshot
    write_snapshot(today_panel, snapshot_date)
```

Replicate the **numbered-step docstring + stepwise compose pattern**, the typed signature, the explicit `Raises:` line, and the trailing `log.info("pipeline_complete", ...)` event with structured kwargs.

**Must diverge from analog (CRITICAL):**
- **Imports:** `import logging; log = logging.getLogger(__name__)` — NOT `import structlog; log = structlog.get_logger(__name__)`. The architecture test rejects `screener.obs` imports here (RESEARCH §E L12).
- **Settings:** Cannot call `get_settings()`. Either accept paths as args, or read `os.environ.get("SNAPSHOT_DIR", "data/snapshots")` via stdlib (RESEARCH §B Q7 bonus block).
- **No `build_panel`, `passes_trend_template`, `score`, `compute_for_date`:** read pre-computed columns from `data/snapshots/<date>.parquet` via stdlib `pd.read_parquet`. Use `persistence.read_panel()` ONLY for OHLCV (the only allowed `persistence` call).
- **Mutation surface:** RESEARCH §A Q2 (lines 180-194) is the canonical block — keep `if _lookahead: ... else: entries = entries_raw.shift(1, fill_value=False).astype(bool)` literally, so a future contributor reads exactly which line the no-look-ahead gate defends.
- **Hard-fail on empty snapshots dir:** RESEARCH §E L10 — `if len(list(Path("data/snapshots").glob("*.parquet"))) == 0: raise RuntimeError("No snapshots found. Run `make backfill-snapshots` first.")`. Mirror the defensive-raise pattern from `persistence.py:656`.

**from_signals call signature to use (verbatim from RESEARCH §A Q4):**
```python
return vbt.Portfolio.from_signals(
    close=close, entries=entries_exec, exits=exits_exec,
    price=open_, slippage=slippage_panel,
    direction='longonly', init_cash=100_000.0, cash_sharing=True,
    fees=0.0, size=0.05, size_type='value', freq='1D',
)
```

---

### `src/screener/backtest/walkforward.py` (NEW)

**Role:** Pure window-construction utility. Given `(start, end, is_years, oos_years, slide_years)`, return list of `(is_start, is_end, oos_start, oos_end)` tuples.

**Closest analog:** None in repo — this is greenfield. Closest spirit is `src/screener/regime.py:_compute_distribution_days()` (pure pandas time arithmetic, no I/O).

**Pattern to replicate (verbatim from RESEARCH §A Q3, lines 216-242):**
```python
def walk_forward_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    is_years: int = 3,
    oos_years: int = 1,
    slide_years: int = 1,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Yield (is_start, is_end, oos_start, oos_end) tuples."""
    windows = []
    window_start = start
    while True:
        is_end    = window_start + pd.DateOffset(years=is_years) - pd.Timedelta(days=1)
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end   = oos_start + pd.DateOffset(years=oos_years) - pd.Timedelta(days=1)
        if oos_end > end:
            break
        windows.append((window_start, is_end, oos_start, oos_end))
        window_start = window_start + pd.DateOffset(years=slide_years)
    return windows
```

**Pure-function discipline (mirrors `signals/composite.py:1-16` docstring):** "no I/O, no global state, panel-in / panel-out." Take this docstring sentence and adapt.

**Must diverge from analog:** stdlib `import logging` if any logging at all (the function is pure — probably none needed). RESEARCH §E L11 leap-year edge case (Feb 29) — add a docstring note.

---

### `src/screener/backtest/metrics.py` (NEW)

**Role:** Cross-window aggregation of `vbt.Portfolio` results — min/median/max OOS Sharpe, per-regime breakdown using `regime_state` from snapshots, per-playbook breakdown stubbed at `leader_hold` (D-12).

**Closest analog:** None for metrics computation specifically. Closest is `src/screener/publishers/report.py:_add_publisher_columns()` (cross-section enrichment) for the "iterate rows, add derived columns" shape.

**Pattern to replicate (signature + return-frame shape from report.py:65-96):**
```python
def _add_publisher_columns(
    cross: pd.DataFrame, regime_row: pd.Series
) -> pd.DataFrame:
    """Add pivot_distance_atr, pivot_zone, regime_state, regime_score, rank
    columns to a cross-section frame. ..."""
    out = cross.copy()
    ...
    out["rank"] = pd.array(
        out["composite_score"].rank(ascending=False, method="dense", na_option="bottom").astype("Int64"),
        dtype=pd.Int64Dtype(),
    )
```

**Suggested API surface:**
```python
def oos_sharpe_distribution(window_portfolios: list[vbt.Portfolio]) -> dict[str, float]:
    """Return {'min': ..., 'median': ..., 'max': ..., 'n_zero_trade_windows': ...}."""

def per_regime_breakdown(trades: pd.DataFrame, regime_col: str = "regime_state") -> pd.DataFrame:
    """Group exit-date trades by regime_state; return rows for the 3 known states."""

def per_playbook_breakdown(trades: pd.DataFrame, playbook_col: str = "playbook_tag") -> pd.DataFrame:
    """Phase 5: only 'leader_hold' row. Phase 6 adds qullamaggie/vcp rows automatically."""
```

**Must diverge from analog (CRITICAL):**
- `import logging; log = logging.getLogger(__name__)` — NOT structlog.
- No `from screener.config import get_settings` — pass thresholds as args or use module-level constants.
- RESEARCH §E L16: filter NaN Sharpe (zero-trade windows) before computing min/median/max; report `n_zero_trade_windows` as a separate field, do not let NaN propagate.

---

### `src/screener/backtest/report.py` (NEW)

**Role:** Render `reports/backtest-YYYY-MM-DD.md` with YAML frontmatter disclosure header (BCK-06) + OOS Sharpe table + per-regime + per-playbook sections. Atomic write via stdlib tempfile + `os.replace`.

**Closest analog:** `src/screener/publishers/report.py` — exact role match (markdown rendering + atomic text write).

**Pattern to replicate — markdown atomic-write helper (publishers/report.py:126-169):**
```python
def _write_text_atomic(content: str, target: Path) -> None:
    """Markdown-text analog of persistence._write_parquet_atomic.

    Tempfile MUST be in the same directory as target so os.replace() is a
    same-filesystem rename (POSIX-atomic). ..."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=f".{target.name}.", suffix=".tmp",
            delete=False, mode="w", encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

**Copy this verbatim** (the consolidated write-inside-with form per REVIEW IN-01 iter 3 — strictest variant in the repo). It uses stdlib only — passes the architecture test.

**Pattern to replicate — render structure (publishers/report.py:175-298):** sectioned `lines: list[str] = []` then `"\n".join(lines)`. Same `## Section` markdown discipline. Same `WARNING:` ASCII-only convention (CLAUDE.md "Coding Conventions").

**Frontmatter template (verbatim from RESEARCH §D Q10, lines 690-723):** YAML block at top with `backtest_date`, `universe_source_date`, `survivorship_caveat`, `slippage_tiers`, `period_selection`, `regime_gate`, `playbook_attribution`, `preregistration` keys. Include Commons-Clause caveat per RESEARCH §E L3.

**Must diverge from analog (CRITICAL):**
- **No `from screener.config import get_settings`** — `publishers/report.py:42-43` does `s: Any = get_settings(); return Path(getattr(s, "REPORT_DIR", "reports"))`. In `backtest/report.py` you MUST hardcode `Path("reports")` or accept a path arg from the caller, OR read `os.environ.get("REPORT_DIR", "reports")`.
- `import logging; log = logging.getLogger(__name__)` — NOT structlog.
- No `from screener.signals.composite import DEFAULT_WEIGHTS, PHASE_4_ZEROED` (architecture violation). The frontmatter `preregistration.weights_hash` should be computed via stdlib `subprocess.run(["git", "log", "-1", "--format=%H", "docs/strategy_v1_preregistration.md"])` OR passed in by the caller.

---

### `scripts/backfill_snapshots.py` (NEW)

**Role:** One-off batch loop over trading dates 2016-01-01..today; calls `publishers.pipeline.run_pipeline(date, write_report=False)`; idempotent (skip if `data/snapshots/<date>.parquet` exists). Lives OUTSIDE `backtest/` so it can import `publishers` freely (D-01).

**Closest analog:** `scripts/check_preregistration.py` — script shape (argparse-or-stdlib + `main() -> int` + `sys.exit(main())`).

**Pattern to replicate (check_preregistration.py:1-15 + 69-130):**
```python
"""Compares DEFAULT_WEIGHTS in signals/composite.py to the weights table in
docs/strategy_v1_preregistration.md. ...

Plain stdlib at module top; the heavier `from screener.signals.composite
import DEFAULT_WEIGHTS` lives inside main() so this script can be invoked
in any environment where pandas is not yet installed ...
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ... pure-stdlib helpers ...

def main() -> int:
    """... return 0 on match, 1 on mismatch."""
    # Lazy heavy import — module top is stdlib only (Pitfall 9).
    from screener.signals.composite import DEFAULT_WEIGHTS
    ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Replicate three discipline rules** (verbatim from this analog):
1. Module-top imports are stdlib only.
2. Heavy imports (`from screener.publishers.pipeline import run_pipeline`) live INSIDE `main()`.
3. `if __name__ == "__main__": sys.exit(main())` exit-code contract.

**Suggested body shape:**
```python
def main() -> int:
    from screener.publishers.pipeline import run_pipeline
    start = pd.Timestamp("2016-01-01")
    end = pd.Timestamp.today().normalize()
    snapshot_dir = Path("data/snapshots")
    for d in pd.bdate_range(start, end):
        target = snapshot_dir / f"{d.strftime('%Y-%m-%d')}.parquet"
        if target.exists():
            continue  # idempotent skip (D-01)
        try:
            run_pipeline(d.strftime("%Y-%m-%d"), write_report=False)
        except Exception as e:
            print(f"FAIL {d.date()}: {type(e).__name__}: {e}", file=sys.stderr)
            continue  # best-effort backfill — log + skip
    return 0
```

**Discretion (D-Discretion bullet 4):** Use plain `print()` for progress (acceptable per CONTEXT.md). Avoid `tqdm` to keep stdlib-only at module top.

**Must diverge from analog:** None — script-shape is identical. Just substitute the heavy import and the loop body.

---

### `tests/test_backtest_no_lookahead.py` (NEW)

**Role:** FND-04 integration test. Two parametrized calls to `vbt_runner.run(_lookahead=False)` and `(_lookahead=True)`. CI-blocking via `.github/workflows/no-lookahead-gate.yml`.

**Closest analogs:**
1. `tests/test_publishers_snapshot.py` — `tmp_path + monkeypatch.setattr("screener.persistence._snapshot_dir", lambda: snapshot_dir)` pattern.
2. `tests/test_publishers_pipeline.py` — multiple-call parametrize-by-narration shape; `pytest.raises(typer.Exit)` for the negative path.
3. `tests/test_preregistration_check.py` — `monkeypatch.chdir(tmp_path)` + writing a fixture file pattern.

**Pattern to replicate — monkeypatch-the-import-target (test_publishers_snapshot.py:37-50):**
```python
def test_snapshot_written_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr(
        "screener.persistence._snapshot_dir", lambda: snapshot_dir
    )
    from screener.publishers.snapshot import write_snapshot
    df = _make_ranking_snapshot_df()
    path = write_snapshot(df, "2026-05-10")
    assert path == snapshot_dir / "2026-05-10.parquet"
```

**Adapt:** monkeypatch `screener.backtest.vbt_runner.read_panel` (and any snapshot-reader helper) per RESEARCH §B Q7 (lines 472-500). Pin synthetic OHLCV to `seed=42` per RESEARCH §B Q5 + L14.

**Pattern to replicate — assertion structure (verbatim from RESEARCH §B Q5, lines 360-382):**
```python
LOOKAHEAD_FALSE_MAX_RETURN = 0.50   # 50% — correct path must stay near random
LOOKAHEAD_TRUE_MIN_RETURN  = 1.00   # 100% — mutation must produce wild outperformance

def test_no_lookahead_correct_path(synthetic_panel_writer, monkeypatch):
    result = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=False)
    assert abs(result.total_return) < LOOKAHEAD_FALSE_MAX_RETURN, ...

def test_no_lookahead_mutation_detected(synthetic_panel_writer, monkeypatch):
    result = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=True)
    assert result.total_return > LOOKAHEAD_TRUE_MIN_RETURN, ...
```

**These thresholds (0.50 / 1.00) supersede D-07's "≤ 2× BH"** — see CONTEXT.md D-07 REVISED 2026-05-16 + RESEARCH §B Q5 (10-seed Monte Carlo proof).

**Must diverge from analog:** None — analog patterns compose cleanly.

---

### `tests/test_walkforward_windows.py` (NEW)

**Role:** Unit test for `backtest.walkforward.walk_forward_windows` (BCK-01). Verifies 7 complete windows for `start=2016-01-01, end=2025-12-31`, IS=3yr, OOS=1yr, slide=1yr.

**Closest analog:** `tests/test_publishers_pipeline.py:55-66` — pure-function assertion pattern.

**Pattern to replicate (test_publishers_pipeline.py:12-23):**
```python
def test_soft_regime_gate_multiplies() -> None:
    """D-03: composite_score *= regime_score on the cross-section frame."""
    panel = pd.DataFrame(
        {"composite_score": [50.0, 80.0, 30.0]},
        index=pd.Index(["AAA", "BBB", "CCC"], name="ticker"),
    )
    out = apply_regime_gate(panel, regime_score=0.5)
    assert out.loc["AAA", "composite_score"] == 25.0
```

**Required assertions (from CONTEXT.md "Specifics" + RESEARCH §A Q3):**
- Length == 7 windows for the canonical 2016-01-01..2025-12-31 range.
- First window: IS 2016-01-01..2018-12-31 | OOS 2019-01-01..2019-12-31.
- Last window: IS 2022-01-01..2024-12-31 | OOS 2025-01-01..2025-12-31.
- All `is_end < oos_start` (no overlap).
- Empty list if `end - start < is_years + oos_years`.
- Optional leap-year regression: `start=2020-02-29` (RESEARCH §E L11).

---

### `tests/test_slippage_tiers.py` (NEW)

**Role:** Unit test for the per-ticker ADV-tiered slippage panel builder inside `vbt_runner.py` (BCK-03). Verifies tier boundaries and NaN-fill default.

**Closest analog:** `tests/test_publishers_pipeline.py` (panel-in, value-out unit tests).

**Pattern to replicate (use direct value asserts; mirror the apply_regime_gate test shape):**
```python
def test_adv_above_50m_gets_5bps() -> None:
    panel = _make_ohlcv_panel(close=100.0, volume=600_000)  # $60M ADV
    slip = _build_slippage_panel(panel)
    assert (slip.iloc[20:] == 0.0005).all().all()  # post-warmup all 5 bps

def test_adv_below_5m_gets_30bps() -> None:
    panel = _make_ohlcv_panel(close=100.0, volume=40_000)  # $4M ADV
    slip = _build_slippage_panel(panel)
    assert (slip.iloc[20:] == 0.0030).all().all()

def test_warmup_nan_filled_with_worst_tier() -> None:
    panel = _make_ohlcv_panel(close=100.0, volume=600_000)
    slip = _build_slippage_panel(panel)
    assert (slip.iloc[:19] == 0.0030).all().all()  # NaN ADV -> 30 bps default (L1)
```

**Implementation source:** RESEARCH §A Q4 (lines 266-293) is the canonical `_build_slippage_panel` body. Tiers verbatim from D-11.

**Must diverge from analog:** None.

---

### `tests/test_backtest_audit.py` (NEW)

**Role:** Test the 4-check forensic audit CLI (BCK-07). Asserts non-zero exit when any check fails; structured-log events emitted per check.

**Closest analog:** `tests/test_cli_smoke.py:61-87` — `CliRunner` + `_parse_json_events` pattern.

**Pattern to replicate (test_cli_smoke.py:42-87):**
```python
from typer.testing import CliRunner
from screener.cli import app

def _parse_json_events(stdout: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out

def test_each_phase1_stub_exits_zero_with_stub_log() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    assert result.exit_code == 0, ...
    events = _parse_json_events(result.stdout)
    ...
```

**Required scenarios (from D-16 + RESEARCH §D Q9):**
1. All 4 checks pass → exit 0; 4 structured `audit_check` events with `result="PASS"`.
2. Preregistration mismatch (write a bad doc into `tmp_path / "docs"`) → exit 1; 3 PASS + 1 FAIL.
3. Empty `data/snapshots/` → exit 1 with FAIL on "≥ 2 complete OOS windows".
4. Empty `data/universe/` → exit 1 with FAIL on universe-snapshot check.

**Must diverge from analog:** Will need to monkeypatch / chdir into `tmp_path` so the audit's `Path("data/snapshots")` and `Path("data/universe")` lookups resolve to fixture dirs.

---

### `.github/workflows/no-lookahead-gate.yml` (NEW)

**Role:** Separate CI job with `paths:` filter for `signals/**` and `backtest/**`. Runs `pytest tests/test_backtest_no_lookahead.py -v --tb=short`. Required-check in branch protection (D-09).

**Closest analog:** `.github/workflows/ci.yml` — single existing workflow with `lint` / `typecheck` / `test` jobs.

**Pattern to replicate (ci.yml:71-95 — the `test` job):**
```yaml
  test:
    name: test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Set up Python from pyproject
        run: uv python install
      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev
      - name: pytest (with coverage gate from pyproject.toml)
        run: uv run pytest -m "not slow" -v
```

**Adapt per RESEARCH §C Q8 (lines 552-580):**
- New workflow file (not added to `ci.yml`) — recommended for branch-protection independence (per research recommendation).
- Top-level `on.pull_request.paths: ['src/screener/signals/**', 'src/screener/backtest/**', 'tests/test_backtest_no_lookahead.py']` filter (NOT job-level `if:`, since this is a single-purpose workflow).
- Pin SHA-pinned actions (verbatim SHAs from ci.yml above for `actions/checkout` and `astral-sh/setup-uv`).
- Final step: `uv run pytest tests/test_backtest_no_lookahead.py -v --tb=short`.
- Top-level `name: no-lookahead-gate` so branch protection can require this specific check.

**Concurrency block to copy (ci.yml:9-11):**
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Must diverge from analog:** No `lint` or `typecheck` jobs (out of scope for this gate); workflow has exactly one job.

---

### `src/screener/cli.py` (MODIFIED — fill `backtest` and `backtest-audit` bodies)

**Role:** Composition root — replaces the existing `_stub("backtest")` and `_stub("backtest-audit")` calls (cli.py:238-247) with real bodies. No new subcommands (D-18 — 9-subcommand surface locked).

**Closest analog:** The `score` and `report` subcommands in the same file (cli.py:198-229), filled in Phase 4 from the same `_stub()` shape.

**Pattern to replicate (cli.py:198-214 — `score` body):**
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
        log.error("score_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**Copy four discipline rules verbatim:**
1. `configure_logging()` at top of body.
2. Heavy import (`from screener.backtest.vbt_runner import run`) **inside** the body (lazy — same as `score` does for `run_pipeline`).
3. `except typer.Exit: raise` BEFORE the broader `except Exception` (Pitfall 7).
4. `error_type=type(e).__name__` ONLY, never `error=str(e)` (T-3-02 mitigation — prevents API-key leakage to logs).

**For `backtest_audit()` body:** RESEARCH §D Q9 (lines 599-671) is the canonical body — copy the `_audit_*` helpers + the main loop pattern. Note: `cli.py` is the composition root (per `ALLOWED` dict comment in `test_architecture.py:43`), so it CAN import `from screener.backtest.walkforward import walk_forward_windows` and call `subprocess.run([...check_preregistration.py])` — no architecture-test risk.

**Must diverge from analog:** None — this is an exact in-file pattern copy.

---

### `Makefile` (MODIFIED — add `backfill-snapshots` target)

**Role:** Three targets potentially in scope: `backtest`, `backtest-audit`, `backfill-snapshots`. The first two ALREADY EXIST (Makefile:31-35) and shell out to `uv run screener backtest` / `backtest-audit` — no edit needed unless the comment text wants updating from "Phase 1: stub" to current behavior.

**Closest analog:** Existing `backtest:` and `backtest-audit:` targets in the same file (Makefile:31-35).

**Pattern to replicate (Makefile:31-35):**
```make
backtest:  ## Run vectorbt walk-forward backtest (Phase 1: stub)
	uv run screener backtest

backtest-audit:  ## Run the forensic checklist (no-look-ahead, weight-pre-reg hash, universe date)
	uv run screener backtest-audit
```

**Adapt — add ONE new target (D-02 — separate from `backtest`):**
```make
backfill-snapshots:  ## Backfill historical snapshots 2016-01-01..today (one-off; see D-01)
	uv run python scripts/backfill_snapshots.py
```

**Update `.PHONY` line** (Makefile:7) to add `backfill-snapshots`.

**Must diverge from analog:** `backfill-snapshots` is NOT a `screener` subcommand (D-02 / D-18 — 9-subcommand lock). Shell out to `python scripts/...` directly. Do NOT add it to the `all:` target (D-02 — never auto-runs as part of `make backtest`).

---

### `tests/conftest.py` (MODIFIED — add `synthetic_ohlcv_panel(seed=42, n_bars=250)` fixture)

**Role:** Shared session-scope fixture producing a deterministic GBM OHLCV panel in the schema `read_panel()` returns (MultiIndex `(ticker, date)`, lowercase columns).

**Closest analog:** `synthetic_multi_ticker_panel` (conftest.py:290-313) — same panel shape, similar deterministic-RNG approach.

**Pattern to replicate (conftest.py:290-313):**
```python
@pytest.fixture(scope="session")
def synthetic_multi_ticker_panel() -> pd.DataFrame:
    """5 tickers x 260 business days (>252d so RS rating is defined for all)."""
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    n = 260
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    frames = []
    for i, t in enumerate(tickers):
        drift = 0.001 * (i + 1)
        close = 100.0 * np.cumprod(1.0 + np.full(n, drift))
        idx = pd.MultiIndex.from_product([[t], dates], names=["ticker", "date"])
        frames.append(pd.DataFrame(
            {"open": close, "high": close * 1.01, "low": close * 0.99,
             "close": close, "volume": np.full(n, 1_000_000, dtype="int64")},
            index=idx,
        ))
    return pd.concat(frames).sort_index()
```

**Adapt — use RESEARCH §B Q6 verbatim GBM construction (lines 420-449):**
```python
@pytest.fixture(scope="session")
def synthetic_ohlcv_panel() -> pd.DataFrame:
    """250 bars of single-ticker mean-zero GBM OHLCV in the panel shape
    read_panel() returns. Pinned seed=42 satisfies the no-look-ahead test
    thresholds with margin (10-seed verification — RESEARCH §B Q5)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-01", periods=250)
    log_returns = rng.normal(loc=0.0, scale=0.012, size=250)
    close = 100.0 * np.exp(np.cumsum(log_returns))
    open_  = close * (1 + rng.normal(0, 0.002, 250))
    high   = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, 250)))
    low    = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, 250)))
    volume = rng.integers(500_000, 2_000_000, 250, dtype="int64")
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "date"
    df["ticker"] = "SYNTH"
    return df.set_index("ticker", append=True).reorder_levels(["ticker", "date"])
```

**Must diverge from analog:** Mean-zero drift (loc=0.0), NOT the analog's `drift = 0.001 * (i + 1)`. Per RESEARCH §B Q5 Q6 table, ANY drift defeats the no-look-ahead threshold separation.

---

## Reusable Helpers Already in Codebase

| Helper | Location | Use in Phase 5 |
|--------|----------|-----------------|
| `persistence.read_panel(snapshot_date)` | `src/screener/persistence.py:601-673` | **ONLY** allowed internal call from `vbt_runner.py`. Returns OHLCV MultiIndex panel. |
| `persistence._write_parquet_atomic(df, target)` | `src/screener/persistence.py:273-295` | Use for any backfill writes (though `run_pipeline` already invokes it via `write_snapshot_atomic`). |
| `publishers.pipeline.run_pipeline(date, write_report=False)` | `src/screener/publishers/pipeline.py:116-193` | The backfill script's primary reuse point (D-01). |
| `scripts/check_preregistration.py` + `main()` | `scripts/check_preregistration.py:69-130` | Forensic audit invokes via `subprocess.run(["uv", "run", "python", "scripts/check_preregistration.py"])`. **Do NOT reimplement.** |
| `_write_text_atomic` from `publishers/report.py:126-169` | `src/screener/publishers/report.py:126-169` | **Inline copy** into `backtest/report.py` (cannot import publishers — architecture violation). The pattern is stdlib-only so the copy passes the architecture test. |
| `RankingSnapshotSchema` columns | `src/screener/persistence.py:221-254` | Reference for the columns `vbt_runner.py` reads: `passes_trend_template`, `composite_score`, `regime_state`, `regime_score`, `rank`. |
| `obs.configure()` | `src/screener/obs.py:14-39` | Called from `cli.py` only (composition root). NEVER from inside `backtest/`. |

---

## Anti-Patterns to Avoid (Architecture Footguns)

| Anti-pattern | Why it fails | Correct alternative |
|--------------|--------------|---------------------|
| `from screener.obs import configure as configure_logging` inside `backtest/*.py` | `tests/test_architecture.py::test_backtest_does_not_import_data_layer` fails (RESEARCH §E L12). | `import logging; log = logging.getLogger(__name__)`. `cli.py` configures structlog at startup; stdlib log records flow to the same root logger. |
| `from screener.config import get_settings` inside `backtest/*.py` | Same architecture test fails (D-17). | Hardcode `Path("data/snapshots")` or read `os.environ.get("SNAPSHOT_DIR", "data/snapshots")` via stdlib. |
| `from screener.signals.composite import DEFAULT_WEIGHTS` inside `backtest/report.py` | Architecture test fails. | Compute the preregistration git-hash via `subprocess.run(["git", "log", "-1", ...])`, OR have `cli.py` resolve it and pass it as an arg. |
| Re-running signal computation in `vbt_runner.py` | D-04 violation; defeats point-in-time integrity; risks look-ahead. | Read `passes_trend_template`, `composite_score`, etc. from `data/snapshots/<date>.parquet`. |
| Manual same-bar execution (passing `entries` directly without `.shift(1)`) | D-19 / FND-04 violation; no-look-ahead test will catch in CI. | `entries.shift(1, fill_value=False).astype(bool)` with `price=open_` panel (RESEARCH §A Q2). |
| Using `.iloc[start_idx:end_idx]` to slice OOS windows | RESEARCH §E L4 — positional slicing mis-aligns sparse tickers; silent look-ahead. | Always slice by `.loc[is_start:is_end]` with `pd.Timestamp`. |
| `vbt.RollingSplitter` for walk-forward windows | RESEARCH §A Q3 — slides by 1 bar, produces 1,602 windows instead of 7. | Manual `pd.DateOffset(years=1)` arithmetic per the verbatim block in walkforward.py section above. |
| Adding a 10th subcommand to `cli.py` (e.g., `screener backfill-snapshots`) | D-18 / `tests/test_cli_smoke.py::D14_SUBCOMMANDS` locks the 9-subcommand surface. | `scripts/backfill_snapshots.py` invoked via `make backfill-snapshots`. |
| `cat << 'EOF'` heredoc creation for new files | Project convention; tool harness expects `Write` tool. | Use `Write` tool only. |
| `print()` anywhere in `src/screener/**` | CLAUDE.md "Coding Conventions" — no `print()`, only `structlog`. | stdlib `logging` inside `backtest/` (flows to root logger configured by structlog in `cli.py`). `print()` IS OK in `scripts/backfill_snapshots.py` (CLAUDE.md "scripts" Discretion bullet 4). |
| NaN in `slippage` panel passed to `from_signals` | RESEARCH §E L1 — vbt silently produces zero positions OR cryptic numba error. | `slippage_panel.where(adv_20d.notna(), 0.0030)` — fill NaN warmup with worst tier. |
| Auto-committing the backtest report | D-15 — user commits manually (same as Phase 4 `make report`). | `make backtest` writes the file; user runs `git add` + `git commit`. |

---

## PATTERN MAPPING COMPLETE

Phase 5 has strong in-repo analogs for every file: `publishers/pipeline.py` for harness orchestration (with structlog/config divergence), `publishers/report.py` for atomic markdown writes, `scripts/check_preregistration.py` for the backfill script shape, `tests/test_publishers_*.py` for the test scaffolding, and `cli.py`'s own Phase-4-filled `score`/`report` bodies for the CLI stub-fill pattern.
