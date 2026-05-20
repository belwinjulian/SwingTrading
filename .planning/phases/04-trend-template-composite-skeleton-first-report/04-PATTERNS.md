# Phase 4: Trend Template, Composite Skeleton & First Report - Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 22 (10 new files + 8 file extensions + 4 test/CI extensions)
**Analogs found:** 22 / 22 (100% have closest in-repo analogs)

## File Classification

### New files (Phase 4 creates from scratch)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/screener/signals/minervini.py` | signal (pure) | transform | `src/screener/indicators/relative_strength.py` | exact (panel-in/panel-out + per-ticker shift idiom) |
| `src/screener/signals/composite.py` | signal (pure, weights-dict scorer) | transform | `src/screener/regime.py::_regime_score` | role-match (vectorized weighted blend in [0,1]) |
| `src/screener/publishers/report.py` | publisher (Markdown writer) | file-I/O | `src/screener/persistence.py::write_universe_atomic` (atomic-write idiom) + `src/screener/regime.py::_classify_state` (Literal-state mapping) | role-match (no existing Markdown writer; pattern is composite of two analogs) |
| `src/screener/publishers/snapshot.py` | publisher (thin caller of persistence writer) | file-I/O | `src/screener/persistence.py::write_rs_snapshot_atomic` (lines 352–364) | exact (mirrors signature, validation, log event) |
| `src/screener/publishers/pipeline.py` | orchestrator (composes signals → gate → validate → publish) | event-driven | `src/screener/regime.py::compute_for_date` (multi-source orchestration) + `src/screener/cli.py::refresh_ohlcv` health-gate (lines 116–152) | role-match (orchestrator with typer.Exit gate) |
| `scripts/check_preregistration.py` | CI utility (stdlib-only Python script) | file-I/O (read) | None in-repo (`scripts/` dir does not exist yet) | NEW DIRECTORY — no analog. Use stdlib `re` + `importlib`. |
| `docs/strategy_v1_preregistration.md` | doc (fill placeholder TBDs) | doc | Existing template at same path with `TBD` placeholders | exact (extend in place) |
| `tests/test_signals_minervini.py` | test (unit, pure-function) | request-response | `tests/test_indicators_rs.py` (panel-in test pattern) | role-match |
| `tests/test_signals_composite.py` | test (unit + property test) | request-response | `tests/test_regime_score.py` (weighted-score range test) | role-match |
| `tests/test_publishers_pipeline.py` | test (unit, orchestrator gate) | request-response | `tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` (lines 109–137) | exact (typer.Exit assertion pattern) |
| `tests/test_publishers_report.py` | test (unit + integration, file written) | file-I/O | `tests/test_persistence.py` (write + assert file exists pattern) | role-match |
| `tests/test_publishers_snapshot.py` | test (integration, atomic write) | file-I/O | `tests/test_rs_snapshot.py::test_rs_snapshot_atomic_write` (lines 36–53) | exact (monkeypatch _dir + crash test) |
| `tests/test_preregistration_check.py` | test (CI script behavior) | request-response | None — but `tests/test_cli_smoke.py` (subprocess-free CliRunner pattern) is closest | role-match |

### Files to extend (additive, no breaking change)

| Existing File | Role | Data Flow | Extension Pattern | Match Quality |
|---------------|------|-----------|-------------------|---------------|
| `src/screener/indicators/trend.py` | indicator (pure) | transform | Mirror `sma_panel` (lines 31–48) — add `high_52w_panel` + `low_52w_panel` with `groupby(level="ticker").rolling(252).max()/.min()` | exact |
| `src/screener/indicators/__init__.py` | composer | request-response | Add `panel = high_52w_panel(...)` + `panel = low_52w_panel(...)` after `rs_panel(panel)` (line 36) | exact |
| `src/screener/persistence.py` | I/O + schemas | file-I/O | Add `RankingSnapshotSchema` (mirror `RsSnapshotSchema` lines 197–217) + `write_snapshot_atomic` (mirror `write_rs_snapshot_atomic` lines 352–364) + `_snapshot_dir()` (mirror `_rs_snapshot_dir` lines 298–301) | exact |
| `src/screener/config.py` | settings | config | Append three fields after Phase 3 block (line 59) — same pattern as Phase 3 D-12 additions | exact |
| `src/screener/cli.py` | CLI surface | request-response | Replace `_stub("score")` body (line 201) and `_stub("report")` body (line 207) with `publishers.pipeline.run_pipeline(...)` calls — mirror `refresh_macro` try/except pattern (lines 158–189) | exact |
| `tests/test_persistence.py` | test (extend) | request-response | Add 2 tests using existing helpers (e.g., `_make_panel`, monkeypatch dir override) | exact |
| `tests/test_cli_smoke.py` | test (extend) | request-response | Add 1 integration test mirroring `test_health_gate_below_95_fails_run` (lines 109–137) — assert exit_code != 0 + no report file | exact |
| `tests/conftest.py` | fixtures (extend) | config | Append session-scope fixtures after Phase 3 block (line 353) — synthetic_panel_for_trend_template, synthetic_scored_panel, synthetic_high_pass_rate_panel | exact |
| `.github/workflows/ci.yml` | CI config | file-I/O | Add `Preregistration consistency (FND-05)` step in `test` job after line 88 (`uv sync --frozen --extra dev`) | exact (mirror SMA-not-EMA gate at lines 42–47) |
| `Makefile` | build | request-response | NO CHANGE — `report:` target at lines 26–27 already calls `uv run screener report` | exact (already correct) |

## Pattern Assignments

### `src/screener/signals/minervini.py` (signal, transform)

**Analog:** `src/screener/indicators/relative_strength.py` (entire file 1–46) — exact match for panel-in/panel-out pure function with per-ticker shift idiom.

**Imports pattern** (mirror lines 1–18):
```python
"""minervini — Trend Template gate (8 SMA-based conditions; pass/fail + 0–8 score).

Per CLAUDE.md "Signal Formulas — Quick-Reference" — SMA only, never EMA.
The CI grep gate (IND-02) is scoped to this file specifically — must not
import EMA helpers.

Pitfalls handled:
- Per-ticker shift via groupby(level='ticker').shift() (Pitfall 8)
- nullable Int64 NaN propagation: cond.fillna(False).astype(bool) before AND
"""

from __future__ import annotations

import pandas as pd
```

**Per-ticker shift pattern** (lines 28–32 of analog):
```python
by_ticker = panel.groupby(level="ticker")["close"]
c_63 = by_ticker.shift(63)
c_126 = by_ticker.shift(126)
c_189 = by_ticker.shift(189)
c_252 = by_ticker.shift(252)
```

For Trend Template condition 3 (`SMA200 > SMA200[t-22]`):
```python
sma_200_22d_ago = panel["sma_200"].groupby(level="ticker").shift(22)
```

**Pure-function panel-in/panel-out signature** (lines 21–45 of analog — same shape):
```python
def passes_trend_template(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `passes_trend_template` (bool) and `trend_template_score` (Int64 0–8).

    `panel` MUST contain: close, sma_50, sma_150, sma_200, high_52w, low_52w, rs_rating.
    Tickers missing any input get NaN → False / 0.
    """
    out = panel.copy()
    # ... compute conds ...
    out["trend_template_score"] = score
    out["passes_trend_template"] = (score == 8).fillna(False).astype(bool)
    return out
```

**NaN-safe boolean handling (Pitfall 3 of RESEARCH.md):**
```python
# rs_rating is pd.Int64Dtype (nullable); >= 70 returns pd.NA on NaN.
# Must fillna before AND-ing.
bool_conds = [c.fillna(False).astype(bool) for c in conds]
score = sum(bool_conds[i].astype("Int64") for i in range(8))
```

---

### `src/screener/signals/composite.py` (signal, transform)

**Analog A (weighted blend):** `src/screener/regime.py::_regime_score` (lines 96–110) — exact match for vectorized weighted-component score in [0, 1].
**Analog B (Final-typed module constant):** No prior `Final[dict]` constant in repo, but `src/screener/persistence.py::GICS_SECTORS` (lines 56–70) is the closest — `frozenset` constant module-level for downstream consumption.

**Imports pattern:**
```python
"""composite — Pre-registered weighted composite scorer (D-12, D-13).

DEFAULT_WEIGHTS is a Final dict importable by scripts/check_preregistration.py
without instantiating any pandas frames. M2 extension seam (D-13): adding
"ml_probability" is a one-line append; iterators downstream remain unchanged.

Pure-function discipline (Phase 1 D-16): no I/O, no side effects.
"""

from __future__ import annotations

from typing import Final

import pandas as pd
```

**Final dict module constant (NEW pattern; closest analog `GICS_SECTORS`):**
```python
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,    # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,   # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,   # zeroed in Phase 4 (D-01); active in Phase 6
}

PHASE_4_ZEROED: Final[frozenset[str]] = frozenset({"pattern", "earnings", "catalyst"})
```

**Vectorized weighted-blend pattern** (mirror `_regime_score` lines 96–110 of `regime.py`):
```python
# In regime.py:
def _regime_score(df: pd.DataFrame) -> pd.Series:
    spy_component = df["spy_above_200d"].astype(float)
    breadth_norm = (df["breadth_pct"] / 100.0).clip(0.0, 1.0)
    dist_norm = (1.0 - df["distribution_days"] / 9.0).clip(0.0, 1.0)
    vix_norm = (1.0 - (df["vix_level"] - 15.0) / 25.0).clip(0.0, 1.0)
    return (
        0.30 * spy_component
        + 0.40 * breadth_norm
        + 0.20 * dist_norm
        + 0.10 * vix_norm
    )
```

For composite, the same vectorized blend but iterating `weights.items()` (D-13):
```python
def score(panel: pd.DataFrame, weights: dict[str, float] = DEFAULT_WEIGHTS) -> pd.DataFrame:
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown weight keys: {sorted(unknown)}")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0; got {sum(weights.values())}")
    out = panel.copy()
    out["rs_component"] = (panel["rs_rating"].astype("Float64") / 99.0).fillna(0.0)
    out["trend_component"] = (panel["trend_template_score"].astype("Float64") / 8.0).fillna(0.0)
    out["volume_component"] = (
        (1.0 - (panel["dryup_ratio"] - 0.5) / 1.5).clip(0.0, 1.0).fillna(0.0)
    )
    out["pattern_component"] = 0.0     # Phase 4 placeholder per D-01
    out["earnings_component"] = 0.0
    out["catalyst_component"] = 0.0
    composite = pd.Series(0.0, index=panel.index)
    for key, w in weights.items():
        composite += w * out[f"{key}_component"]
    out["composite_score"] = (composite * 100.0).astype(float)
    return out
```

**Error-raising pattern (no `typer.Exit` — pure function):** Plain `ValueError`. CLI/publisher layer translates to exit codes.

---

### `src/screener/publishers/snapshot.py` (publisher, file-I/O)

**Analog:** `src/screener/persistence.py::write_rs_snapshot_atomic` (lines 352–364) — exact mirror.

**Existing analog code (verbatim):**
```python
def write_rs_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write an RS snapshot to data/rs_snapshots/<date>.parquet.
    Eager validation (D-16): bad row aborts loud at the write boundary."""
    validated = validate_at_write(RsSnapshotSchema, df)
    target = _rs_snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info(
        "rs_snapshot_written",
        path=str(target),
        n_rows=len(validated),
        snapshot_date=snapshot_date,
    )
    return target
```

**Phase 4 implementation:** The `publishers/snapshot.py` is a THIN caller — the actual atomic-write function lives in `persistence.py` as `write_snapshot_atomic` (added in the persistence extension below). The publisher just orchestrates the call:
```python
"""snapshot — thin caller for the daily ranking-snapshot Parquet write.

The actual atomic-write helper lives in persistence.write_snapshot_atomic
(D-15/D-16 schema-at-IO contract). This publisher exists so the orchestrator
can compose snapshot + report uniformly under publishers/.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog

from screener.persistence import write_snapshot_atomic

log = structlog.get_logger(__name__)


def write_snapshot(scored_panel: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write the full ranked snapshot."""
    return write_snapshot_atomic(scored_panel, snapshot_date)
```

**Architecture compliance:** `publishers/` is allowed to import `persistence`, `obs`, `config` per `tests/test_architecture.py::ALLOWED["publishers"]` (line 36 of `test_architecture.py`).

---

### `src/screener/publishers/report.py` (publisher, file-I/O)

**Analog A (atomic write to non-Parquet target):** `_write_parquet_atomic` (lines 236–258 of `persistence.py`) — adapt the tempfile + `os.replace` pattern for plain text.
**Analog B (Literal state mapping):** `_classify_state` (lines 64–88 of `regime.py`) for `pivot_zone` three-state Literal.

**Atomic write idiom (lines 236–258 of `persistence.py`):**
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Write `df` to `target` atomically (POSIX same-filesystem rename).
    The tempfile MUST be in the same directory as `target` so os.replace() is
    a same-filesystem rename, which is the only POSIX-atomic primitive
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.to_parquet(tmp_path, engine="pyarrow", index=True)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

For the Markdown report, swap `df.to_parquet(...)` for `Path.write_text(markdown_str, encoding="utf-8")`:
```python
def _write_text_atomic(content: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False, mode="w",
        encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)
    try:
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

**Pivot-zone Literal classifier (mirror `_classify_state` pattern lines 64–88 of `regime.py`):**
```python
PivotZone = Literal["in-zone", "chase, skip", "unknown"]

def _classify_pivot_zone(close: float, high_52w: float, atr: float) -> PivotZone:
    if pd.isna(high_52w) or pd.isna(atr) or atr == 0:
        return "unknown"
    distance = (close - high_52w) / atr
    return "in-zone" if distance <= 1.0 else "chase, skip"
```

**Markdown placeholder substitution from `PHASE_4_ZEROED`:**
```python
from screener.signals.composite import DEFAULT_WEIGHTS, PHASE_4_ZEROED

def _format_breakdown(row: pd.Series) -> str:
    parts = []
    for key in DEFAULT_WEIGHTS:
        if key in PHASE_4_ZEROED:
            parts.append(f"{key.capitalize()}=—(Phase 6)")
        elif key == "rs":
            parts.append(f"RS={int(row['rs_rating'])}")
        elif key == "trend":
            parts.append(f"Trend={int(row['trend_template_score'])}/8")
        elif key == "volume":
            parts.append(f"Volume={row['volume_component']:.2f}")
    return " | ".join(parts)
```

**No-emoji rule (CLAUDE.md, RESEARCH Pitfall 12):** Use plain ASCII `WARNING:` not `⚠`.

---

### `src/screener/publishers/pipeline.py` (orchestrator, event-driven)

**Analog A (gate + typer.Exit):** `src/screener/cli.py::refresh_ohlcv` health-gate (lines 130–144) — exact pattern.
**Analog B (multi-source orchestration):** `src/screener/regime.py::compute_for_date` (lines 118–187) — calls multiple data + indicator functions and returns a row.

**Health-gate pattern from `cli.py` lines 130–144 (verbatim):**
```python
yf_ok, stooq_ok, failed = run_with_breaker(tickers, today)
combined_ok = yf_ok + stooq_ok
ratio = combined_ok / n_universe if n_universe > 0 else 0.0
threshold = settings.UNIVERSE_HEALTH_THRESHOLD

if ratio < threshold:
    log.error(
        "health_check_failed",
        success_count=combined_ok,
        universe_size=n_universe,
        ratio=ratio,
        threshold=threshold,
        failed_tickers=failed[:20],
    )
    raise typer.Exit(code=1)

log.info(
    "health_check_passed",
    success_count=combined_ok,
    universe_size=n_universe,
    ratio=ratio,
    threshold=threshold,
)
```

For Phase 4 `validate_run()` (D-07/D-08 dual-channel alerting):
```python
import structlog
import typer

log = structlog.get_logger(__name__)

def validate_run(
    pass_rate: float,
    regime_state: str,
    warn_threshold: float,
    fail_threshold_with_correction: float,
) -> None:
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

**Soft regime gate pattern (NEW — separate function for Phase 7 hard-gate swappability per RESEARCH §4):**
```python
def apply_regime_gate(scored_panel: pd.DataFrame, regime_score: float) -> pd.DataFrame:
    """Soft gate: composite_score *= regime_score (D-03). Picks visible during
    Correction; scores compress. Phase 7 may swap to hard gate."""
    assert 0.0 <= regime_score <= 1.0, f"regime_score out of range: {regime_score}"
    out = scored_panel.copy()
    out["composite_score"] = out["composite_score"] * regime_score
    return out
```

**Orchestration pattern (mirror `compute_for_date` flow at lines 118–187 of `regime.py`):**
```python
def run_pipeline(snapshot_date: str, write_report: bool = True) -> None:
    """Compose: build_panel → minervini → composite → regime gate → validate → publish."""
    panel = build_panel(snapshot_date)
    panel = passes_trend_template(panel)
    panel = composite.score(panel, DEFAULT_WEIGHTS)

    today_panel = panel.xs(pd.Timestamp(snapshot_date), level="date")
    regime_row = regime.compute_for_date(pd.Timestamp(snapshot_date), panel)
    today_panel = apply_regime_gate(today_panel, float(regime_row["regime_score"]))

    pass_rate = float(today_panel["passes_trend_template"].mean())
    settings = get_settings()
    validate_run(
        pass_rate,
        str(regime_row["regime_state"]),
        settings.TREND_TEMPLATE_PASS_RATE_WARN,
        settings.TREND_TEMPLATE_PASS_RATE_HARD_FAIL,
    )

    write_snapshot(today_panel, snapshot_date)
    if write_report:
        write_report_markdown(today_panel, regime_row, snapshot_date, top_n=settings.REPORT_TOP_N)
```

---

### `src/screener/indicators/trend.py` (extend — indicator, transform)

**Analog (in-file):** `sma_panel` (lines 31–48 of `trend.py`) — exact pattern for per-ticker rolling.

**Existing pattern (verbatim, lines 31–48):**
```python
def sma_panel(
    panel: pd.DataFrame,
    lengths: tuple[int, ...] = (10, 20, 50, 150, 200),
) -> pd.DataFrame:
    """Append sma_<length> columns to the panel, computed per-ticker.

    Pitfall 8: groupby(level='ticker') is required to prevent rolling-window
    bleed across tickers in the (ticker, date) MultiIndex.
    """
    out = panel.copy()
    for length in lengths:
        col = f"sma_{length}"

        def _apply_sma(c: pd.Series, n: int = length) -> pd.Series:
            return _safe_sma(c, n).reset_index(level=0, drop=True)

        out[col] = panel.groupby(level="ticker")["close"].apply(_apply_sma)
    return out
```

**Phase 4 additions (mirror the per-ticker rolling pattern; alternative form using `.rolling().max()` from `volume.py::dryup_ratio_panel` lines 42–52 also acceptable):**

The `volume.py::dryup_ratio_panel` analog (verbatim, lines 42–52) uses the simpler `groupby.rolling().droplevel(0)` idiom that fits high/low rolling more naturally than the `apply` form above:
```python
def dryup_ratio_panel(panel: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """D-09: dryup_ratio = volume / SMA(volume, length)."""
    out = panel.copy()
    sma_vol = (
        panel.groupby(level="ticker")["volume"]
        .rolling(length)
        .mean()
        .droplevel(0)
    )
    out["dryup_ratio"] = panel["volume"] / sma_vol
    return out
```

Apply this idiom for high_52w / low_52w:
```python
def high_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append high_52w — per-ticker rolling max of `high` over `length` bars.
    NaN warmup for the first `length-1` bars per ticker (Phase 3 D-08)."""
    out = panel.copy()
    out["high_52w"] = (
        panel.groupby(level="ticker")["high"]
        .rolling(length)
        .max()
        .droplevel(0)
    )
    return out

def low_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append low_52w — per-ticker rolling min of `low` over `length` bars."""
    out = panel.copy()
    out["low_52w"] = (
        panel.groupby(level="ticker")["low"]
        .rolling(length)
        .min()
        .droplevel(0)
    )
    return out
```

---

### `src/screener/indicators/__init__.py` (extend — composer)

**Analog (in-file):** `build_panel` (lines 22–37 of `__init__.py`).

**Existing wiring pattern (verbatim, lines 30–37):**
```python
def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    panel = read_panel(snapshot_date)
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))
    panel = atr_panel(panel, length=14)
    panel = adr_pct_panel(panel, length=20)
    panel = obv_panel(panel)
    panel = dryup_ratio_panel(panel, length=50)
    panel = rs_panel(panel)
    return panel
```

**Phase 4 extension (append two lines + import):**
```python
from screener.indicators.trend import sma_panel, high_52w_panel, low_52w_panel
# ... in build_panel:
panel = rs_panel(panel)
panel = high_52w_panel(panel, length=252)
panel = low_52w_panel(panel, length=252)
return panel
```

Update docstring `Columns added` list to include `high_52w, low_52w`.

---

### `src/screener/persistence.py` (extend — schemas + writer)

**Analog A (schema with nullable Int64):** `RsSnapshotSchema` (lines 197–217). Exact match.
**Analog B (atomic writer):** `write_rs_snapshot_atomic` (lines 352–364). Exact match.
**Analog C (dir helper):** `_rs_snapshot_dir` (lines 298–301). Exact match.

**RsSnapshotSchema verbatim (mirror this for `RankingSnapshotSchema`):**
```python
class RsSnapshotSchema(pa.DataFrameModel):
    """One row per ticker, taken on a single trading date.
    rs_rating is nullable Int64 — pd.Int64Dtype, NOT int (RESEARCH Pitfall 9).
    """
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rs_raw: Series[float] = pa.Field(nullable=True)
    rs_rating: Series[pd.Int64Dtype] = pa.Field(nullable=True)

    @pa.check("rs_rating", name="rs_rating_must_be_nullable_int64")
    @classmethod
    def _rs_rating_dtype(cls, series: pd.Series) -> bool:
        return series.dtype == pd.Int64Dtype()

    class Config:
        strict = True
        coerce = False
```

**Phase 4 schema (mirror; add isin checks for Literal columns following `MacroOhlcvSchema` line 144 / `NyadMacroSchema` line 187 patterns; also use `_rs_rating_dtype` custom check pattern for `trend_template_score`):**
```python
class RankingSnapshotSchema(pa.DataFrameModel):
    """Daily ranking snapshot — full universe with composite scores and ranks.
    Written by publishers/snapshot.py via persistence.write_snapshot_atomic.
    Used by Phase 5 backtest harness for no-look-ahead reproduction.
    """
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rank: Series[pd.Int64Dtype] = pa.Field(ge=1, nullable=True)
    composite_score: Series[float] = pa.Field(ge=0.0, le=110.0, nullable=True)
    rs_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    trend_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    volume_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    pattern_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
    earnings_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
    catalyst_component: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
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

**Dir helper (mirror lines 298–301 verbatim):**
```python
def _snapshot_dir() -> Path:
    """Resolve the daily ranking-snapshot directory, with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "SNAPSHOT_DIR", "data/snapshots"))
```

**Atomic writer (mirror lines 352–364 verbatim, plus security check from `_assert_safe_ticker` at lines 264–272):**
```python
import re

def _assert_safe_snapshot_date(snapshot_date: str) -> None:
    """Path-traversal defense: snapshot_date must match YYYY-MM-DD."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", snapshot_date):
        raise ValueError(f"Unsafe snapshot_date for path construction: {snapshot_date!r}")

def write_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write a ranking snapshot to data/snapshots/<date>.parquet.
    Eager validation (D-16): bad row aborts loud at the write boundary."""
    _assert_safe_snapshot_date(snapshot_date)
    validated = validate_at_write(RankingSnapshotSchema, df)
    target = _snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info(
        "snapshot_written",
        path=str(target),
        n_rows=len(validated),
        snapshot_date=snapshot_date,
    )
    return target
```

---

### `src/screener/config.py` (extend — settings)

**Analog (in-file):** Phase 3 D-12 additive block (lines 51–59 of `config.py`).

**Existing additive pattern (verbatim, lines 51–59):**
```python
# Phase 3 (D-12) — macro + RS snapshot paths and regime thresholds
MACRO_CACHE_DIR: Path = Path("data/macro")
RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")
MACRO_BACKFILL_START: str = "2005-01-01"
REGIME_BREADTH_THRESHOLD: float = 0.60
REGIME_DIST_DAYS_PRESSURE: int = 5
REGIME_DIST_DAYS_CORRECTION: int = 9
REGIME_VIX_CORRECTION: float = 30.0
REGIME_VIX_CONFIRMED: float = 20.0
```

**Phase 4 extension (append after line 59):**
```python
# Phase 4 (D-07/D-08) — report + trend-template gate config
SNAPSHOT_DIR: Path = Path("data/snapshots")
REPORT_DIR: Path = Path("reports")
REPORT_TOP_N: int = 15
TREND_TEMPLATE_PASS_RATE_WARN: float = 0.25
TREND_TEMPLATE_PASS_RATE_HARD_FAIL: float = 0.25
```

---

### `src/screener/cli.py` (extend — fill `score` and `report` bodies)

**Analog (in-file):** `refresh_macro` (lines 158–189) — exact try/except + `typer.Exit` pattern with redacted error.

**Existing pattern (verbatim, lines 158–189):**
```python
@app.command("refresh-macro")
def refresh_macro(...) -> None:
    """Refresh macro inputs (SPY, QQQ, ^VIX, NYSE A/D, FRED yields). DAT-04."""
    configure_logging()
    today = date.today()
    try:
        from screener.data.macro import (
            refresh_nyad, refresh_qqq, refresh_spy, refresh_vix, refresh_yields,
        )
        refresh_spy(force=force, today=today)
        # ... etc ...
        log.info("refresh_macro_ok")
    except Exception as e:
        # T-3-02 mitigation: log only error_type (never error string).
        log.error("refresh_macro_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**Phase 4 replacement bodies (replace `_stub("score")` line 201 and `_stub("report")` line 207):**
```python
@app.command("score")
def score() -> None:
    """Compute composite scores; write data/snapshots/YYYY-MM-DD.parquet."""
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline
        run_pipeline(date.today().isoformat(), write_report=False)
    except typer.Exit:
        raise
    except Exception as e:
        log.error("score_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("report")
def report() -> None:
    """Render daily Markdown report (also computes scores + snapshot)."""
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline
        run_pipeline(date.today().isoformat(), write_report=True)
    except typer.Exit:
        raise
    except Exception as e:
        log.error("report_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**Critical:** The 9-subcommand surface lock (`tests/test_cli_smoke.py::D14_SUBCOMMANDS` lines 20–30) is preserved — bodies fill, decorators don't change. Also remove `score` and `report` from `PHASE_1_STUBS` (lines 34–41) since they no longer emit `[stub]`.

---

### `scripts/check_preregistration.py` (NEW — CI utility)

**Analog:** None in repo. `scripts/` directory does not exist. Use stdlib `re` + `importlib`.

**Reference implementation (RESEARCH §"Code Examples" lines 605–658):**
```python
"""Compares DEFAULT_WEIGHTS in signals/composite.py to the weights table in
docs/strategy_v1_preregistration.md. Fails CI on mismatch."""
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
        pattern = rf"\|\s*{re.escape(friendly)}.*?\|\s*\d+%\s*\|\s*(\d+(?:\.\d+)?)%\s*\|"
        m = re.search(pattern, text)
        if m is None:
            sys.exit(f"Preregistration doc missing frozen weight for: {friendly}")
        out[key] = float(m.group(1)) / 100.0
    return out

def main() -> int:
    from screener.signals.composite import DEFAULT_WEIGHTS
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

**Anti-patterns (per RESEARCH):** No `subprocess`, no `eval`, no pandas import. Stdlib only at the script top level (the `from screener.signals.composite import DEFAULT_WEIGHTS` line lives inside `main()` to defer the heavier import until needed).

---

### `tests/test_signals_minervini.py` (NEW)

**Analog:** `tests/test_indicators_rs.py` — panel-in test pattern using `synthetic_multi_ticker_panel` fixture.

**Pattern to mirror — fixture consumption + assertion on new column:**
```python
def test_eight_conditions_pass_for_strong_uptrend_ticker(
    synthetic_panel_for_trend_template: pd.DataFrame,
) -> None:
    out = passes_trend_template(synthetic_panel_for_trend_template)
    assert "passes_trend_template" in out.columns
    assert "trend_template_score" in out.columns
    assert out["trend_template_score"].dtype == pd.Int64Dtype()
```

**Short-history test pattern (mirror `test_indicators_panel.py::test_short_history_nan_warmup` lines 67–82):**
```python
def test_short_history_safe(synthetic_short_history_panel: pd.DataFrame) -> None:
    """50-bar ticker → all conditions False, score 0, no exception (Pitfall 3)."""
    panel = synthetic_short_history_panel  # missing high_52w/low_52w/sma_200/rs_rating
    # ... add the indicator columns first via build_panel-equivalent setup ...
    out = passes_trend_template(panel)
    assert (out["passes_trend_template"] == False).all()  # noqa: E712
    assert (out["trend_template_score"] == 0).all()
```

---

### `tests/test_signals_composite.py` (NEW)

**Analog:** `tests/test_regime_score.py` — weighted-score range tests + property tests.

**Patterns to mirror:**
1. `test_unknown_weight_key_raises` — `pytest.raises(ValueError)` on `score(panel, {"unknown": 1.0})`.
2. `test_weight_sum_assertion` — `pytest.raises(ValueError)` on `score(panel, {"rs": 0.5})` (sum != 1.0).
3. `test_score_range_property` — hypothesis test: composite_score in [0, 100] for any valid input.
4. `test_zeroed_components` — assert `out["pattern_component"]`, `out["earnings_component"]`, `out["catalyst_component"]` are all 0.0.
5. `test_extension_seam` — `score(panel, {**DEFAULT_WEIGHTS, "ml_probability": 0.0})` raises ValueError (unknown key — not in DEFAULT_WEIGHTS yet); per D-13 the API tolerates the addition once it lands. Test the seam with a future-key admission test.

---

### `tests/test_publishers_pipeline.py` (NEW)

**Analog:** `tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` (lines 109–137) — exact `typer.Exit` exit-code assertion pattern.

**Pattern to mirror — assert `typer.Exit` raised with non-zero code:**
```python
def test_pass_rate_warns(caplog: pytest.LogCaptureFixture) -> None:
    """D-07: pass_rate > 0.25 emits structlog warning (no exit)."""
    validate_run(pass_rate=0.30, regime_state="Confirmed Uptrend",
                 warn_threshold=0.25, fail_threshold_with_correction=0.25)
    # No exception raised; just a log event.
    # Assert the warning event in caplog or via structlog's CapLogger.

def test_data_quality_gate_failed_in_correction() -> None:
    """D-08: pass_rate > 0.25 AND Correction → typer.Exit(1)."""
    with pytest.raises(typer.Exit) as exc:
        validate_run(pass_rate=0.30, regime_state="Correction",
                     warn_threshold=0.25, fail_threshold_with_correction=0.25)
    assert exc.value.exit_code == 1

def test_soft_regime_gate_multiplies() -> None:
    """D-03 soft gate: composite_score *= regime_score."""
    panel = pd.DataFrame({"composite_score": [50.0, 80.0]}, index=["AAA", "BBB"])
    out = apply_regime_gate(panel, regime_score=0.5)
    assert out.loc["AAA", "composite_score"] == 25.0
    assert out.loc["BBB", "composite_score"] == 40.0
```

---

### `tests/test_publishers_report.py` (NEW)

**Analog A:** `tests/test_persistence.py` — write + assert file exists pattern.
**Analog B:** Existing test file pattern using `tmp_path` fixture.

**Pattern to mirror:**
```python
def test_report_file_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                             synthetic_scored_panel: pd.DataFrame) -> None:
    monkeypatch.setattr("screener.publishers.report._report_dir", lambda: tmp_path)
    write_report_markdown(synthetic_scored_panel, regime_row, "2026-05-10", top_n=15)
    assert (tmp_path / "2026-05-10.md").exists()

def test_report_sections_present(...) -> None:
    md = render_report(synthetic_scored_panel, regime_row, top_n=15)
    assert "## Regime" in md
    assert "## Top 15 Picks" in md
    assert "## Per-Pick Detail" in md
    assert "## Data Quality" in md

def test_per_pick_breakdown_format_with_phase_4_placeholders(...) -> None:
    md = render_report(...)
    assert "Pattern=—(Phase 6)" in md
    assert "Earnings=—(Phase 6)" in md
    assert "Catalyst=—(Phase 6)" in md
```

---

### `tests/test_publishers_snapshot.py` (NEW)

**Analog:** `tests/test_rs_snapshot.py::test_rs_snapshot_atomic_write` (lines 36–53) — exact pattern.

**Existing analog code (verbatim, lines 36–53 of `test_rs_snapshot.py`):**
```python
def test_rs_snapshot_atomic_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mid-write crash leaves no partial Parquet and no .tmp residue."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    df = _make_rs_snapshot_df()

    def _raise(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise)
    with pytest.raises(OSError):
        write_rs_snapshot_atomic(df, "2026-04-30")

    target = snapshot_dir / "2026-04-30.parquet"
    assert not target.exists(), "rs snapshot must not exist after a mid-write crash"
    leftover = list(snapshot_dir.glob(".2026-04-30.parquet.*.tmp"))
    assert leftover == [], f"No tmp residue should remain; found {leftover}"
```

For Phase 4 — same pattern, swap the dir helper and writer:
```python
def test_snapshot_written_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr("screener.persistence._snapshot_dir", lambda: snapshot_dir)
    df = _make_ranking_snapshot_df()
    write_snapshot_atomic(df, "2026-05-10")
    assert (snapshot_dir / "2026-05-10.parquet").exists()
```

---

### `tests/test_preregistration_check.py` (NEW)

**Analog:** No direct analog. Closest: `tests/test_cli_smoke.py` (subprocess-free pattern using `runpy` or direct function call).

**Pattern (NEW — invoke main() directly):**
```python
import sys
from pathlib import Path

def test_matching_weights_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "strategy_v1_preregistration.md").write_text(
        "| RS percentile (IBD) | 25% | 25% |\n"
        "| Trend Template | 20% | 20% |\n"
        # ... etc
    )
    from scripts.check_preregistration import main
    assert main() == 0
```

---

### `tests/test_persistence.py` (extend)

**Analog (in-file):** Existing test fixtures (`_make_panel`, `_make_universe_row`) and patterns at lines 34–62.

**Phase 4 additions:**
```python
def test_ranking_snapshot_schema_accepts_valid_frame() -> None:
    df = _make_ranking_snapshot_df()  # new helper
    validate_at_write(RankingSnapshotSchema, df)  # should not raise

def test_ranking_snapshot_rejects_bad_pivot_zone() -> None:
    df = _make_ranking_snapshot_df()
    df["pivot_zone"] = "BOGUS"
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(RankingSnapshotSchema, df)
```

---

### `tests/test_cli_smoke.py` (extend)

**Analog (in-file):** `test_health_gate_below_95_fails_run` (lines 109–137).

**Phase 4 addition (D-08 hard fail integration test):**
```python
def test_report_data_quality_gate(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-08: pass_rate > 0.25 AND Correction → exit 1 + no report file."""
    # Mock run_pipeline to invoke validate_run with the failure combo.
    def fake_pipeline(date_str: str, write_report: bool) -> None:
        from screener.publishers.pipeline import validate_run
        validate_run(0.30, "Correction", 0.25, 0.25)
    monkeypatch.setattr("screener.publishers.pipeline.run_pipeline", fake_pipeline)

    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    assert result.exit_code != 0
    events = _parse_json_events(result.stdout)
    failed = [ev for ev in events if ev.get("event") == "data_quality_gate_failed"]
    assert failed
```

Also: remove `"score"` and `"report"` from `PHASE_1_STUBS` (lines 34–41) — they're no longer stubs.

---

### `tests/conftest.py` (extend — fixtures)

**Analog (in-file):** Phase 3 fixtures (lines 261–353).

**Phase 4 additions (append after line 353):**
```python
# --- Phase 4 fixtures (Plans 04-01 through 04-05) ---------------------------

@pytest.fixture(scope="session")
def synthetic_panel_for_trend_template(synthetic_multi_ticker_panel: pd.DataFrame) -> pd.DataFrame:
    """Multi-ticker panel with all Trend Template input columns populated.
    Builds on the Phase 3 multi-ticker fixture; adds high_52w/low_52w/sma_*/rs_rating.
    """
    # ... call high_52w_panel, low_52w_panel, sma_panel, rs_panel ...

@pytest.fixture(scope="session")
def synthetic_scored_panel(...) -> pd.DataFrame:
    """Post-composite panel with composite_score, pivot_zone, regime_score columns
    — used by publisher tests."""
    ...

@pytest.fixture(scope="session")
def synthetic_high_pass_rate_panel(...) -> pd.DataFrame:
    """A 1000-ticker panel where ~30% pass the Trend Template — triggers D-08."""
    ...
```

---

### `.github/workflows/ci.yml` (extend)

**Analog (in-file):** SMA-not-EMA gate (lines 42–47) — exact pattern for inline shell + grep gate.

**Existing pattern (verbatim, lines 42–47):**
```yaml
- name: SMA-not-EMA gate (IND-02)
  run: |
    if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
      echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
      exit 1
    fi
```

**Phase 4 addition (after line 88, in the `test` job after `Install dependencies (frozen)`):**
```yaml
- name: Preregistration consistency (FND-05)
  run: uv run python scripts/check_preregistration.py
```

This step shares the cached `uv sync` from the test job; minimal extra runtime cost (~0.5s).

---

## Shared Patterns

### Pure-function panel-in/panel-out (signals + indicators)
**Source:** `src/screener/indicators/relative_strength.py` lines 21–46
**Apply to:** `signals/minervini.py`, `signals/composite.py`
```python
def my_signal(panel: pd.DataFrame, ...) -> pd.DataFrame:
    out = panel.copy()
    # ... compute new columns ...
    out["new_col"] = ...
    return out
```
**Architecture compliance:** Enforced by `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` (lines 164–197) — no `requests`, `yfinance`, `sqlite3`, etc. imports.

### Per-ticker rolling/shift (avoid index bleed across tickers)
**Source:** `src/screener/indicators/relative_strength.py` lines 28–32; `src/screener/indicators/volume.py` lines 42–52
**Apply to:** All new per-ticker rolling / shift operations in `indicators/trend.py` (high_52w, low_52w) and `signals/minervini.py` (SMA200[t-22] shift)
```python
panel.groupby(level="ticker")["col"].rolling(N).max().droplevel(0)
panel.groupby(level="ticker")["col"].shift(N)
```
**Pitfall warning:** Naked `.shift(22)` or `.rolling(252)` on the (ticker, date) MultiIndex bleeds across tickers (RESEARCH Pitfalls 2 of `relative_strength.py` design).

### NaN-safe boolean handling for nullable Int64
**Source:** RESEARCH Pitfall 3 of Phase 4; `RsSnapshotSchema._rs_rating_dtype` enforcement (lines 209–213 of `persistence.py`)
**Apply to:** `signals/minervini.py` (rs_rating >= 70 condition), `signals/composite.py` (rs_rating consumption)
```python
# rs_rating dtype is pd.Int64Dtype (nullable). Comparisons may return pd.NA.
cond.fillna(False).astype(bool)  # before AND-ing with other conds
score = sum(bool_conds[i].astype("Int64") for i in range(8))
```

### Atomic file writes (D-11 / Phase 2 invariant)
**Source:** `src/screener/persistence.py::_write_parquet_atomic` lines 236–258
**Apply to:** `persistence.write_snapshot_atomic`, `publishers/report.py::_write_text_atomic`
```python
target.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as tmp:
    tmp_path = Path(tmp.name)
try:
    # write to tmp_path
    os.replace(tmp_path, target)
except Exception:
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    raise
```
**Pitfall:** Tempfile MUST be in same directory as target so `os.replace()` is a same-filesystem rename (POSIX-atomic).

### Pandera schema at every I/O boundary (D-15)
**Source:** All schemas at `src/screener/persistence.py` lines 76–217
**Apply to:** `persistence.RankingSnapshotSchema` for `data/snapshots/*.parquet`
```python
class MySchema(pa.DataFrameModel):
    col: Series[type] = pa.Field(...)
    class Config:
        strict = True
        coerce = False

# Eager validation at write boundary:
validated = validate_at_write(MySchema, df)
```

### Settings additive extension (carry-forward from Phase 1, 2, 3)
**Source:** `src/screener/config.py` lines 51–59 (Phase 3 D-12 block)
**Apply to:** `config.py` Phase 4 block (SNAPSHOT_DIR, REPORT_DIR, REPORT_TOP_N, TREND_TEMPLATE_PASS_RATE_WARN, TREND_TEMPLATE_PASS_RATE_HARD_FAIL)
```python
# Phase N (D-XX) — <one-line description>
NEW_FIELD: Type = default_value
```
Never modify existing fields; only append.

### Structured logging (no print)
**Source:** `src/screener/regime.py` lines 36, 170–175; `src/screener/persistence.py` lines 39, 358–363
**Apply to:** All Phase 4 modules that emit log events
```python
import structlog
log = structlog.get_logger(__name__)

log.info("event_name", key1=value1, key2=value2)
log.warning("trend_template_pass_rate_high", pass_rate=0.31, ...)
log.error("data_quality_gate_failed", pass_rate=..., regime_state=...)
```
**Anti-pattern (Phase 3 T-3-02 mitigation, applied in `cli.py::refresh_macro` lines 184–188):** Never log `error=str(e)` for FRED-related paths (URL with API key may leak). Use `error_type=type(e).__name__` only.

### typer.Exit gate pattern
**Source:** `src/screener/cli.py::refresh_ohlcv` lines 130–144
**Apply to:** `publishers/pipeline.py::validate_run` and CLI bodies for `score`/`report`
```python
if condition_failed:
    log.error("event_failed", ...details...)
    raise typer.Exit(code=1)
```
**Critical:** `typer.Exit` is a controlled exception; must NOT be caught silently in helpers. CLI body uses `except typer.Exit: raise` to ensure propagation (RESEARCH §6).

### Literal-state classifier (small enum-like states)
**Source:** `src/screener/regime.py` lines 38, 64–88 (`RegimeState`, `_classify_state`)
**Apply to:** `publishers/report.py::PivotZone` Literal + `_classify_pivot_zone` helper
```python
from typing import Literal
PivotZone = Literal["in-zone", "chase, skip", "unknown"]

def _classify_pivot_zone(...) -> PivotZone:
    if nan_or_zero:
        return "unknown"
    return "in-zone" if distance <= 1.0 else "chase, skip"
```
**Pandera validation:** Mirror `MacroOhlcvSchema`/`NyadMacroSchema` `isin=[...]` pattern at line 161 of `persistence.py` (used in VixSchema, etc.) — `pivot_zone: Series[str] = pa.Field(isin=["in-zone", "chase, skip", "unknown"])`.

### CliRunner integration test
**Source:** `tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` lines 109–137
**Apply to:** `tests/test_cli_smoke.py::test_report_data_quality_gate` (Phase 4 addition)
```python
runner = CliRunner()
result = runner.invoke(app, ["<subcommand>"])
assert result.exit_code != 0
events = _parse_json_events(result.stdout)
failed = [ev for ev in events if ev.get("event") == "<expected_event>"]
assert failed, f"Expected '<event>' event; got: {events!r}"
```

### Path-traversal defense (security V12)
**Source:** `src/screener/persistence.py::_assert_safe_ticker` lines 264–272
**Apply to:** `persistence._assert_safe_snapshot_date` (validate ISO date regex before path construction)
```python
def _assert_safe_X(value: str) -> None:
    if not re.match(r"^valid_pattern$", value):
        raise ValueError(f"Unsafe X for path construction: {value!r}")
```

---

## No Analog Found

| File | Role | Data Flow | Reason | Mitigation |
|------|------|-----------|--------|------------|
| `scripts/check_preregistration.py` | CI utility | file-I/O (read) | `scripts/` directory does not exist; no in-repo precedent for stdlib-only Python preflight scripts | Use the verified RESEARCH §"Code Examples" template (lines 605–658). Pure stdlib (`re`, `sys`, `pathlib`); defer `from screener.signals.composite import DEFAULT_WEIGHTS` to inside `main()`. |
| `src/screener/publishers/report.py` (Markdown writer) | publisher | file-I/O | No in-repo Markdown writer; no Phase 3 publisher with file output. The atomic-write idiom must be adapted from `_write_parquet_atomic` (Parquet) to text. | Compose two analogs: (1) `_write_parquet_atomic` (lines 236–258 of `persistence.py`) for the tempfile + `os.replace` pattern, swapping `df.to_parquet(...)` → `tmp.write(content)`; (2) `_classify_state` (regime.py lines 64–88) for the `PivotZone` Literal classifier helper. |
| `tests/test_preregistration_check.py` | test (CI script) | request-response | No prior tests of stdlib-only utility scripts in the repo | Use `monkeypatch.chdir(tmp_path)` + write a fixture preregistration doc; import `scripts.check_preregistration.main` and assert return code (0 or 1). Mirror the in-process invocation style of CliRunner — but for plain `main()` not typer. |

---

## Metadata

**Analog search scope:**
- `src/screener/signals/` (1 file: `__init__.py` — empty stub; new files have no in-`signals/` analogs)
- `src/screener/indicators/` (5 files: `__init__.py`, `trend.py`, `relative_strength.py`, `volume.py`, `volatility.py`)
- `src/screener/publishers/` (1 file: `__init__.py` — empty stub)
- `src/screener/` top-level (`cli.py`, `config.py`, `persistence.py`, `regime.py`, `obs.py`)
- `tests/` (16 test files including `test_persistence.py`, `test_cli_smoke.py`, `test_rs_snapshot.py`, `test_indicators_panel.py`, `test_architecture.py`, `test_regime_score.py`)
- `.github/workflows/ci.yml` (1 file)
- `Makefile` (1 file — verified `report:` target already correct, no change needed)
- `docs/strategy_v1_preregistration.md` (1 file — existing template, fill TBDs in place)

**Files scanned:** 26 source/test/config files

**Pattern extraction date:** 2026-05-10

**Key insight:** Phase 4 is a "code-shape" phase — every needed pattern has an in-repo precedent (cited above with file + line numbers). The ONLY genuinely new pattern is the stdlib-only CI script in `scripts/`, which has a verified template in RESEARCH.md. No new third-party libraries; no new architectural concepts. Planner should reference these analogs directly in plan action descriptions to avoid pattern drift.

## PATTERN MAPPING COMPLETE
