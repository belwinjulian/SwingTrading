# Phase 7: Sizing Finalization & Paper-Trade Journal — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 13 (5 source modules, 4 new tests, 1 modified test, 1 fixture extension, 1 `.env.example`, 1 sizing stub)
**Analogs found:** 13 / 13 (100% — every new/modified file maps to a strong in-repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/screener/sizing.py` (fill stub) | pure-function module (signals/indicators tier) | transform (panel-in/panel-out) | `src/screener/signals/composite.py` | exact (role + flow + Final-constants idiom) |
| `src/screener/config.py` (extend Settings) | config | env-driven typed settings | `src/screener/config.py` itself (additive Phase-4/Phase-6 extensions) | exact (in-place additive idiom) |
| `src/screener/persistence.py` (extend `RankingSnapshotSchema`) | model (pandera DataFrameModel) | schema | `RankingSnapshotSchema` Phase-6 additive block (`persistence.py:253-269`) | exact |
| `src/screener/persistence.py` (add `_ensure_picks_schema` + `append_picks_rows` + `read_picks_for_date` + `PicksSchema`) | I/O helper (SQLite append-only) | append-only (INSERT OR IGNORE) | `_ensure_insider_schema` + `append_form4_rows` (`persistence.py:909-944`) + `InsiderSchema` (`persistence.py:306-326`) | exact (role + data flow) |
| `src/screener/publishers/pipeline.py` (modify `run_pipeline`) | orchestrator (publisher tier) | request-response (DAG composition) | `run_pipeline` itself (`pipeline.py:116-193`) — extend in place between step 5 & 7 | exact |
| `src/screener/publishers/report.py` (per-pick block fields + `## Skipped Picks` footer) | publisher (Markdown renderer) | transform (frame → text) | `render_report` per-pick block (`report.py:286-307`) + `## Data Quality` footer (`report.py:312-334`) | exact |
| `src/screener/cli.py` (fill `journal` command body, lines 232-235) | controller (typer composition root) | request-response (CLI body) | `score` command body (`cli.py:198-214`) — calls `run_pipeline`; same error-handling shape | exact (role + flow); also `backtest` (`cli.py:238-286`) for read-snapshot+process idiom |
| `.env.example` (add `RISK_PCT`, `JOURNAL_THRESHOLD`) | config | env template mirror | `.env.example` existing fields | exact (in-place additive mirror) |
| `tests/test_sizing.py` (NEW) | test (unit, pure-function math) | unit | `tests/test_publishers_pipeline.py` (pure-function `apply_regime_gate`/`validate_run` tests) | exact (role + flow) |
| `tests/test_journal.py` (NEW) | test (SQLite I/O + trigger semantics) | unit / integration | `tests/test_insider_io.py` (SQLite append-only + pandera-before-insert + `_ensure_*_schema` + monkeypatch + tmp_path) | exact (role + flow) |
| `tests/test_pipeline_journal.py` (NEW — integration) | test (pipeline integration) | integration | `tests/test_publishers_pipeline.py` (validates `run_pipeline` building blocks) + `tests/test_cli_smoke.py::test_report_data_quality_gate_d08` (monkeypatched fake_pipeline → CliRunner) | strong (combines two existing idioms) |
| `tests/conftest.py` (add `sized_input_cross()` fixture) | test fixture | fixture | `synthetic_scored_panel` (`conftest.py:443-473`) — same cross-section shape with `_add_publisher_columns` applied | exact |
| `tests/test_cli_smoke.py` (remove `"journal"` from `PHASE_1_STUBS` + add `test_journal_subcommand_no_longer_stub`) | test (CLI smoke) | unit | `test_score_subcommand_no_longer_stub` (`test_cli_smoke.py:234-244`) | exact (mirror line-for-line) |

## Pattern Assignments

### `src/screener/sizing.py` (pure-function module — transform)

**Analog:** `src/screener/signals/composite.py`

**Module docstring + import block** (composite.py:1-17):
```python
"""composite — pre-registered weighted composite scorer (D-12, D-13).

DEFAULT_WEIGHTS is a Final dict importable by scripts/check_preregistration.py
without instantiating any pandas frame. M2 extension seam (D-13): adding a
new key (e.g., "ml_probability") is a one-line append; downstream iterators
over weights.items() need no changes.

Pure-function discipline (Phase 1 D-16): no I/O, no global state, panel-in /
panel-out. Imports only pandas + stdlib typing.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
```

**COPY:** keep `from __future__ import annotations`, `from typing import Final`, `import numpy as np`, `import pandas as pd`. Add `import structlog`, `from collections.abc import Callable`. Module docstring must (per CLAUDE.md): name the requirement IDs (SIZ-01..05), assert pure-function discipline, note the dispatch-by-`playbook_tag` design.

**Final-constants pattern** (composite.py:19-44):
```python
# Phase 6 D-13 — playbook tie-breaker thresholds. Final (not Settings-overridable)
# to defend Critical Pitfall 5 (in-sample tuning). Tuned via paper trading
# in v1.x, never against backtest results.
QULL_MAX_BARS: Final[int] = 25
QULL_MIN_ADR_PCT: Final[float] = 5.0
MINERVINI_MIN_BARS: Final[int] = 25
MINERVINI_MAX_FINAL_CONTRACTION_PCT: Final[float] = 8.0
LEADER_MIN_RS: Final[int] = 90

DEFAULT_WEIGHTS: Final[dict[str, float]] = { ... }
```

**COPY for sizing.py:**
```python
# D-09 ATR-zone thresholds — Final (locked, not Settings-overridable per
# Pitfall 5 / D-09; SIZ-05).
IN_ZONE_ATR: Final[float] = 0.66
EXTENDED_ATR: Final[float] = 1.00

# D-07 leader_hold swing-low lookback (reuses indicators/patterns conventions).
LEADER_SWING_LOOKBACK_BARS: Final[int] = 20   # same as FLAG_MAX_BARS
LEADER_SWING_PIVOT_ORDER: Final[int] = 3      # same as FLAG_PIVOT_ORDER

# D-08 Qullamaggie trail tier boundaries (ADR%).
QULL_TRAIL_FAST_ADR: Final[float] = 6.0       # >= 6.0 → 10d SMA
QULL_TRAIL_MEDIUM_ADR: Final[float] = 4.0     # 4.0..6.0 → 20d SMA
                                              # else → 50d SMA

# D-05 per-position cap.
MAX_POSITION_FRACTION: Final[float] = 0.25
```

**Pure-function signature pattern** (composite.py:114-191 `score()` — panel-in, panel-out, `.copy()`, dict-driven dispatch):
```python
def score(
    panel: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """...pure: returns a NEW DataFrame; the input is not mutated."""
    out = panel.copy()
    # ... iterate weights.items() and add columns ...
    return out
```

**COPY for sizing.py:**
```python
def compute_sizing(
    cross: pd.DataFrame,
    panel: pd.DataFrame,
    account_equity: float,
    risk_pct: float,
    regime_score: float,
) -> pd.DataFrame:
    """SIZ-01..05 dispatch — pure: returns NEW cross-section; input not mutated.

    Args:
        cross: snapshot-day cross-section (one row per ticker) — must contain
            close, low, high, atr_14, adr_pct, playbook_tag, pattern_diagnostics.
        panel: full MultiIndex(ticker, date) history — needed for swing-low
            lookback in _stop_leader_hold (D-07 RESEARCH §Pattern 2).
        account_equity: from Settings.ACCOUNT_EQUITY (D-05).
        risk_pct: from Settings.RISK_PCT (D-05).
        regime_score: from regime.compute_for_date — multiplies numerator (D-12).

    Returns:
        Same-indexed DataFrame with appended columns: stop_price, entry_price,
        shares, risk_per_share, atr_zone, pivot_distance_atr, trail_rule_label,
        adr_rejected, rejection_reason.
    """
    out = cross.copy()
    # ... dispatch + math ...
    return out
```

**Dict-registry dispatch pattern** (composite.py:193-238 `tag_playbook` — Phase 6 dispatch keyed by playbook tag; sizing follows the same registry idiom per RESEARCH §Pattern 1):

```python
# Per-playbook stop helper registry — SIZ-03 / D-07.
# SC-2 trivially satisfied by: `assert STOP_HELPERS["qullamaggie_continuation"]
# is _stop_qullamaggie`.
STOP_HELPERS: Final[dict[str, Callable[[pd.Series, pd.DataFrame], float]]] = {
    "qullamaggie_continuation": _stop_qullamaggie,
    "minervini_vcp": _stop_minervini_vcp,
    "leader_hold": _stop_leader_hold,
}
```

**Reuse existing utility:** `decode_pattern_diagnostics` from `screener.indicators.patterns` (patterns.py:126-134) for `_stop_minervini_vcp` — defensive `{"type": "none"}` fallback already implemented. Pitfall 5 guard: assert `diag["type"] == "vcp"` AND required keys present, else reject the row.

**Reuse existing utility:** `find_pivots(highs, lows, order=3)` from `screener.indicators.patterns` (patterns.py:79) for `_stop_leader_hold` swing-low lookback. Fallback to `2.0 * atr` when no trough in `LEADER_SWING_LOOKBACK_BARS` window (RESEARCH §Pattern 2).

**Structlog pattern (RESEARCH §Code Examples Pattern 5):**
```python
log = structlog.get_logger(__name__)

log.info(
    "sizing_applied",
    snapshot_date=snapshot_date,
    n_input=len(cross),
    n_actionable=int((~out["adr_rejected"]).sum()),
    n_rejected_adr=int((out["rejection_reason"] == "adr_exceeded").sum()),
    n_rejected_stop=int((out["rejection_reason"] == "invalid_stop").sum()),
    by_playbook={tag: int(c) for tag, c in out[~out["adr_rejected"]]["playbook_tag"].value_counts().items()},
)
```

---

### `src/screener/config.py` (Settings additive extension)

**Analog:** `src/screener/config.py` itself — Phase-2/3/4/6 additive extension pattern.

**Existing additive pattern** (config.py:36-75 — note the section headers):
```python
    # Indicator + sizing parameters
    RS_LOOKBACK_DAYS: int = 252
    RISK_PCT_PER_TRADE: float = 0.0075
    ACCOUNT_EQUITY: float = 100_000.0

    # Phase 2 (D-20) — data-layer paths and policy
    OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
    ...

    # Phase 6 — fundamentals + insider + pattern audit paths (CONTEXT.md D-05, D-08, D-09)
    FUNDAMENTALS_CACHE_DIR: Path = Path("data/fundamentals")
    INSIDER_CACHE_PATH: Path = Path("data/insider/form4.sqlite")
    PATTERN_AUDIT_DIR: Path = Path("data/pattern_audit")
```

**COPY for Phase 7 (append to Settings class body):**
```python
    # Phase 7 — sizing finalization + journal (CONTEXT.md D-05, D-01, OUT-04)
    # ACCOUNT_EQUITY already present at line 39; do NOT duplicate.
    RISK_PCT: float = 0.01                                    # SIZ-01 / D-05 (1% per trade)
    JOURNAL_THRESHOLD: float = 50.0                           # OUT-04 / D-01 composite cutoff
    JOURNAL_DB_PATH: Path = Path("data/journal.sqlite")       # mirrors INSIDER_CACHE_PATH idiom
```

**Notes:**
- `ACCOUNT_EQUITY` is ALREADY at config.py:39 — sizing reads it directly; DO NOT redeclare.
- `RISK_PCT_PER_TRADE` (config.py:38, default 0.0075) is the EXISTING field; CONTEXT D-05 spec calls the Phase 7 read-key `RISK_PCT`. Planner must decide: rename the existing field, or add `RISK_PCT` alongside and deprecate `RISK_PCT_PER_TRADE`. Recommend ADD new field with locked default 0.01 per D-05; leave `RISK_PCT_PER_TRADE` for any pre-Phase-7 callers (currently none — `grep -rn "RISK_PCT_PER_TRADE" src/` should return zero hits).
- Threshold value: CONTEXT D-01 says `JOURNAL_THRESHOLD = 0.5`; RESEARCH says `50` (since composite_score is 0-100). Use **`50.0`** to match the RankingSnapshotSchema bound (`composite_score: ge=0, le=100`).

**Mirror to `.env.example`:**
```
# Phase 7 — sizing + journal (D-05, OUT-04)
RISK_PCT=0.01
JOURNAL_THRESHOLD=50.0
# JOURNAL_DB_PATH=data/journal.sqlite
```

---

### `src/screener/persistence.py` — `RankingSnapshotSchema` extension

**Analog:** `RankingSnapshotSchema` Phase-6 additive block (persistence.py:253-269 — note "Phase 6 extension" comment block).

**Existing additive pattern** (persistence.py:253-269):
```python
    # Phase 6 extension (D-12 / D-15 / D-19) — playbook tag, three binary
    # scores, pattern_diagnostics JSON, breakout_strength, three catalyst
    # flags, earnings warn flag, eps_knowable_from report hint (checker W11).
    playbook_tag: Series[str] = pa.Field(
        isin=["qullamaggie_continuation", "minervini_vcp", "leader_hold", "none"],
        nullable=False,
    )
    qullamaggie_score: Series[pd.Int64Dtype] = pa.Field(ge=0, le=1, nullable=False)
    minervini_score: Series[pd.Int64Dtype] = pa.Field(ge=0, le=1, nullable=False)
    leader_hold_score: Series[pd.Int64Dtype] = pa.Field(ge=0, le=1, nullable=False)
    pattern_diagnostics: Series[str] = pa.Field(nullable=False)
    breakout_strength: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
    days_to_next_earnings: Series[pd.Int64Dtype] = pa.Field(ge=0, nullable=True)
    crossed_52w_high_within_60d: Series[bool] = pa.Field(nullable=False)
    insider_cluster_buy: Series[bool] = pa.Field(nullable=False)
    earnings_in_3d_warn: Series[bool] = pa.Field(nullable=False)
    eps_knowable_from: Series[str] = pa.Field(nullable=True)
```

**COPY for Phase 7 (append to `RankingSnapshotSchema` class body BEFORE `class Config:`):**
```python
    # Phase 7 extension (CONTEXT D-04 / SIZ-01..05) — sizing columns
    # populated by sizing.compute_sizing(), validated at write boundary.
    # adr_zone (3-state) supersedes Phase 4's pivot_zone (2-state at this layer).
    stop_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    entry_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    shares: Series[pd.Int64Dtype] = pa.Field(ge=0, nullable=False)
    risk_per_share: Series[float] = pa.Field(ge=0.0, nullable=False)
    atr_zone: Series[str] = pa.Field(
        isin=["in-zone", "extended", "chase, skip"], nullable=False,
    )
    # pivot_distance_atr ALREADY EXISTS at line 243 (Phase 4) — DO NOT redeclare.
    # Phase 7 may need to revise its sign convention (RESEARCH Assumption A3 /
    # Open Question 3); if a separate column is added, name it
    # `pivot_distance_atr_breakout` and append here.
    trail_rule_label: Series[str] = pa.Field(nullable=False)  # D-08 display string
```

**Important:** `pivot_distance_atr` is ALREADY in the schema (persistence.py:243) — Phase 4 added it. Phase 7 may need a 2nd column for the breakout-relative distance per RESEARCH Open Question 3.

---

### `src/screener/persistence.py` — Journal SQLite helpers

**Analog:** `_ensure_insider_schema` + `append_form4_rows` + `_insider_db_path` + `InsiderSchema` (persistence.py:891-944 + 306-326 + 461-464).

**DDL constant pattern** (persistence.py:891-906):
```python
_FORM4_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS form4 (
    filing_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    insider TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    type TEXT NOT NULL,
    shares REAL NOT NULL,
    value_usd REAL NOT NULL,
    ingested_at TEXT NOT NULL
);
"""

_FORM4_IDX: Final[str] = (
    "CREATE INDEX IF NOT EXISTS idx_form4_ticker_date ON form4(ticker, transaction_date);"
)
```

**COPY for Phase 7** (full DDL from RESEARCH §Code Examples Pattern 1 — verbatim, including UNIQUE + trigger + indexes; pitfall 1 mitigation requires `CREATE TRIGGER IF NOT EXISTS` inside same `executescript` as table DDL):
```python
_PICKS_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Decision columns (NOT NULL, immutable via trigger below)
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
    -- Outcome columns (nullable, updatable — explicitly excluded from trigger)
    entry_filled INTEGER,
    exit_price REAL,
    exit_date TEXT,
    hold_days INTEGER,
    mfe REAL,
    mae REAL,
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
"""
```

**Path-resolver pattern** (persistence.py:461-464):
```python
def _insider_db_path() -> Path:
    """Resolve the insider Form 4 SQLite path (Phase 6 D-08/D-10), with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "INSIDER_CACHE_PATH", "data/insider/form4.sqlite"))
```

**COPY for Phase 7:**
```python
def _journal_db_path() -> Path:
    """Resolve the picks journal SQLite path (Phase 7 D-01/D-02), with fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "JOURNAL_DB_PATH", "data/journal.sqlite"))
```

**Idempotent-schema-setup pattern** (persistence.py:909-916):
```python
def _ensure_insider_schema(db_path: "Path | None" = None) -> Path:
    """Idempotent form4 table + index setup. Returns the resolved db path."""
    path = Path(db_path) if db_path is not None else _insider_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_FORM4_DDL)
        conn.execute(_FORM4_IDX)
    return path
```

**COPY for Phase 7** — single `executescript` covers TABLE + INDEX + TRIGGER (Pitfall 1):
```python
def _ensure_picks_schema(db_path: "Path | None" = None) -> Path:
    """Idempotent picks table + indexes + immutability trigger.

    All three DDL statements run inside ONE executescript so a future
    table-rebuild migration (DROP + CREATE) cannot leave the trigger missing
    (RESEARCH Pitfall 1). All use CREATE ... IF NOT EXISTS so re-invocation
    is a no-op.
    """
    path = Path(db_path) if db_path is not None else _journal_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_PICKS_DDL)
    return path
```

**Append pattern** (persistence.py:919-944 — note: pandera-validate-BEFORE-call contract, return `cur.rowcount`):
```python
def append_form4_rows(db_path: "Path | None", rows: list[dict]) -> int:
    """Idempotent append — ON CONFLICT(filing_id) DO NOTHING per D-10.

    The caller MUST pandera-validate as InsiderSchema BEFORE calling this
    function (Pattern B — schema-at-write boundary). This function trusts
    that validation has already run and performs only the SQL insert.

    Returns the rowcount inserted (0 on full-duplicate batch).
    """
    if not rows:
        return 0
    path = _ensure_insider_schema(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.executemany(
            """INSERT INTO form4(filing_id, ticker, insider, transaction_date,
                                   type, shares, value_usd, ingested_at)
               VALUES (:filing_id, :ticker, :insider, :transaction_date,
                       :type, :shares, :value_usd, :ingested_at)
               ON CONFLICT(filing_id) DO NOTHING""",
            rows,
        )
        conn.commit()
        return cur.rowcount
```

**COPY for Phase 7** (RESEARCH §Code Examples Pattern 2 — verbatim; INSERT OR IGNORE chosen per CONTEXT specifics):
```python
def append_picks_rows(rows: list[dict], db_path: "Path | None" = None) -> int:
    """Idempotent append — INSERT OR IGNORE on UNIQUE(ticker, snapshot_date).

    Caller MUST pandera-validate as PicksSchema BEFORE calling (Pattern B,
    mirror append_form4_rows). Returns rowcount actually inserted (0 on
    full-duplicate batch); skipped duplicates are silent.
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
        log.info(
            "journal_appended",
            n_attempted=len(rows),
            n_inserted=cur.rowcount,
            n_idempotent_skip=len(rows) - cur.rowcount,
        )
        return cur.rowcount
```

**Pandera DataFrameModel pattern** (`InsiderSchema`, persistence.py:306-326 — pre-insert validation contract):
```python
class InsiderSchema(pa.DataFrameModel):
    filing_id: Series[str] = pa.Field(nullable=False, unique=True)
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    ...
    class Config:
        strict = True
        coerce = False
```

**COPY for Phase 7** — new `PicksSchema` (note: validates the dict-list-shaped DataFrame BEFORE the SQL insert):
```python
class PicksSchema(pa.DataFrameModel):
    """Pre-insert validation contract for the picks SQLite table.

    Mirrors InsiderSchema's "DataFrame view validated BEFORE INSERT" idiom.
    Called by publishers/pipeline._build_journal_rows() (or wrapper) before
    persistence.append_picks_rows().
    """
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    snapshot_date: Series[str] = pa.Field(nullable=False, str_matches=r"^\d{4}-\d{2}-\d{2}$")
    playbook_tag: Series[str] = pa.Field(
        isin=["qullamaggie_continuation", "minervini_vcp", "leader_hold"], nullable=False
    )
    composite_score: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=False)
    regime_state: Series[str] = pa.Field(
        isin=["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"], nullable=False
    )
    entry_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    stop_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    shares: Series[int] = pa.Field(ge=0, nullable=False)
    risk_per_share: Series[float] = pa.Field(ge=0.0, nullable=False)
    atr_zone: Series[str] = pa.Field(
        isin=["in-zone", "extended", "chase, skip"], nullable=False
    )
    pivot_distance_atr: Series[float] = pa.Field(nullable=False)
    features_json: Series[str] = pa.Field(nullable=False)
    ingested_at: Series[str] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False
```

**Read pattern** — add `read_picks_for_date(snapshot_date)` mirroring `read_insider_cluster_buy`'s `with sqlite3.connect(path) as conn: pd.read_sql_query(...)` idiom (persistence.py:1001-1006):
```python
def read_picks_for_date(snapshot_date: str, db_path: "Path | None" = None) -> pd.DataFrame:
    """Read picks for a single snapshot_date. Empty DataFrame if none."""
    path = _ensure_picks_schema(db_path)
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM picks WHERE snapshot_date = ? ORDER BY composite_score DESC",
            conn,
            params=(snapshot_date,),
        )
```

---

### `src/screener/publishers/pipeline.py` (modify `run_pipeline`)

**Analog:** `run_pipeline` itself (pipeline.py:116-193) — extend in place per RESEARCH §Pattern 4.

**Existing structure** (pipeline.py:116-193): a 9-step DAG with structlog `pipeline_complete` event at end.

**Modification points** (apply IN PLACE — additive only):

1. **Function signature** — add `write_journal: bool = True` param after `write_report` (D-01):
```python
def run_pipeline(
    snapshot_date: str,
    write_report: bool = True,
    write_journal: bool = True,
) -> None:
```

2. **Inject step 5.5 (sizing)** — between line 147 (`apply_regime_gate`) and line 149 (`pass_rate` computation):
```python
    today_panel = apply_regime_gate(today_panel, regime_score_value)

    # === Phase 7 step 5.5: SIZ-01..05 dispatch (CONTEXT D-04) ===
    from screener.sizing import compute_sizing
    today_panel = compute_sizing(
        today_panel,
        panel,                                   # full history for swing-low lookback
        account_equity=settings.ACCOUNT_EQUITY,
        risk_pct=settings.RISK_PCT,              # NEW Phase 7 Settings field
        regime_score=regime_score_value,
    )
    # Split into actionable + skipped (D-06 1xADR auto-reject; pitfall 6 entry<=stop).
    skipped_panel = today_panel[today_panel["adr_rejected"]].copy()
    today_panel = today_panel[~today_panel["adr_rejected"]].copy()
    # === END Phase 7 step 5.5 ===

    pass_rate = float(today_panel["passes_trend_template"].mean())
```

3. **Inject step 8.5 (journal append)** — after `write_snapshot(...)` at line 171, before the report-write at line 173:
```python
    write_snapshot(today_panel, snapshot_date)

    # === Phase 7 step 8.5: journal append (D-01 / OUT-04) ===
    if write_journal:
        from screener.persistence import (
            PicksSchema,
            append_picks_rows,
            validate_at_write,
        )
        journal_rows_df = _build_journal_rows_df(
            today_panel, regime_row, snapshot_date, settings,
        )
        # Pattern B — pandera-validate BEFORE the SQL insert.
        validated = validate_at_write(PicksSchema, journal_rows_df)
        n_inserted = append_picks_rows(validated.to_dict(orient="records"))
        log.info(
            "journal_append_summary",
            snapshot_date=snapshot_date,
            n_actionable=len(today_panel),
            n_inserted=n_inserted,
            n_idempotent_skip=len(journal_rows_df) - n_inserted,
        )
    else:
        log.info("journal_skipped", snapshot_date=snapshot_date, reason="write_journal=False")
```

4. **Forward `skipped_panel` to report** — modify line 173-183 `write_report_md(...)` call to add `skipped_picks=skipped_panel` kwarg.

5. **Add `_build_journal_rows_df` private helper** in the same module — builds the journal-row DataFrame from the sized cross-section + regime + Settings, with `features_json` embedded per D-03. Composite-threshold filter per D-01 (pre-gate semantics per RESEARCH Open Question 1 / Pitfall 3).

**No changes** to `apply_regime_gate` or `validate_run` — they remain untouched.

---

### `src/screener/publishers/report.py` (per-pick block extension + `## Skipped Picks` footer)

**Analog:** `render_report` per-pick block (report.py:286-307) + `## Data Quality` footer (report.py:312-334).

**Existing per-pick block pattern** (report.py:289-307):
```python
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        ticker = str(row["ticker"])
        composite = float(row["composite_score"])
        lines.append(f"### {i}. {ticker} -- Composite {composite:.1f}")
        lines.append("")
        lines.append("```")
        lines.append(_format_breakdown(row))
        lines.append("```")
        lines.append("")
        pz = str(row.get("pivot_zone", "unknown"))
        pd_atr = row.get("pivot_distance_atr")
        pd_str = "?" if pd.isna(pd_atr) else f"{float(pd_atr):.2f}"
        lines.append(
            f"- **Pivot zone:** {pz} ({pd_str} ATR from 52w high; "
            f"proxy -- Phase 6 will use real VCP pivot)"
        )
        lines.append("- **Playbook:** --(Phase 6)")
        lines.append("- **Catalysts:** --(Phase 6)")
        lines.append("")
```

**COPY for Phase 7** — add sizing fields after the playbook/catalyst lines (CONTEXT specifics — D-09 zone, D-07 stop, D-08 trail, SIZ-01 shares):
```python
        # Phase 7: sizing fields (D-04..D-09)
        stop = float(row["stop_price"])
        entry = float(row["entry_price"])
        shares = int(row["shares"])
        zone = str(row["atr_zone"])
        pdist = float(row["pivot_distance_atr"])
        trail = str(row["trail_rule_label"])
        playbook = str(row["playbook_tag"])
        # D-07 stop label by playbook
        stop_label = {
            "qullamaggie_continuation": "low-of-entry-day",
            "minervini_vcp": "final-contraction-low",
            "leader_hold": "max(1.5xATR, recent swing low)",
        }.get(playbook, "")
        lines.append(f"- **Entry:** ${entry:.2f}")
        lines.append(f"- **Stop:** ${stop:.2f} ({stop_label})   **Trail:** {trail}")
        lines.append(f"- **Shares:** {shares}")
        lines.append(f"- **Zone:** {zone} ({pdist:.2f}xATR above pivot)")
        lines.append("")
```

**`## Skipped Picks` footer pattern** — copy the `## Data Quality` table idiom (report.py:312-329), but rendered AS A LIST since picks have heterogeneous reasons. Insert AFTER the per-pick blocks and BEFORE `## Data Quality`:

```python
    # --- Skipped Picks (D-06 / Pitfall 6) — auto-rejected by sizing ----
    if skipped_picks is not None and len(skipped_picks) > 0:
        lines.append("## Skipped Picks")
        lines.append("")
        lines.append(
            "Picks excluded by the SIZ-02 1xADR auto-reject (or Pitfall 6 "
            "invalid stop). Excluded from both the report top-N and the journal."
        )
        lines.append("")
        for _, srow in skipped_picks.iterrows():
            ticker = str(srow["ticker"])
            reason = str(srow["rejection_reason"])
            risk = float(srow.get("risk_per_share", 0.0))
            adr_pct = float(srow.get("adr_pct", 0.0))
            entry = float(srow.get("entry_price", 0.0))
            adr_dollars = (adr_pct / 100.0) * entry if entry > 0 else 0.0
            multiple = (risk / adr_dollars) if adr_dollars > 0 else 0.0
            if reason == "adr_exceeded":
                lines.append(
                    f"- **{ticker}** — skipped: R/R broken, risk = {multiple:.2f}xADR"
                )
            else:
                lines.append(f"- **{ticker}** — skipped: {reason}")
        lines.append("")
        lines.append("---")
        lines.append("")
```

**Function signatures** — extend `render_report` and `write_report` with `skipped_picks: pd.DataFrame | None = None` (default None preserves backwards compatibility for tests that don't pass it):
```python
def render_report(
    scored_cross: pd.DataFrame,
    regime_row: pd.Series,
    snapshot_date: str,
    top_n: int,
    pass_rate: float,
    skipped_picks: pd.DataFrame | None = None,
) -> str: ...
```

---

### `src/screener/cli.py` — fill `journal` command body (lines 232-235)

**Analog:** `score` command body (cli.py:198-214) — the closest by shape (`configure_logging` + `try`/`except typer.Exit` re-raise + `except Exception → log error_type + raise typer.Exit(1)`).

**Existing `score` body** (cli.py:198-214) — COPY THIS SHAPE EXACTLY:
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

**COPY for Phase 7 `journal` body** — idempotent catch-up that reads today's snapshot and re-appends (CONTEXT D-01):
```python
@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract).

    Idempotent catch-up: reads data/snapshots/<today>.parquet, filters to
    actionable picks (composite_score >= JOURNAL_THRESHOLD AND
    regime_state != 'Correction'), and re-appends via
    persistence.append_picks_rows. INSERT OR IGNORE on UNIQUE(ticker,
    snapshot_date) makes re-runs zero-insert (D-01).
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
        raise  # Pitfall 7
    except Exception as e:
        log.error("journal_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

The `_build_journal_rows_df_from_snapshot` helper lives in `publishers/pipeline.py` and reads via `pd.read_parquet(_snapshot_dir() / f"{today_iso}.parquet")`. This factoring avoids duplicating the journal-row build logic between `run_pipeline` and `cli.journal`.

---

### `.env.example` — Phase 7 additive extension

**Analog:** existing `.env.example` Phase-2/3/6 additive blocks.

**Existing pattern** (`.env.example` end-of-file):
```
# Phase 6 — fundamentals + insider + pattern audit paths (D-05/D-08/D-09).
# Optional path overrides; defaults shown below.
# FUNDAMENTALS_CACHE_DIR=data/fundamentals
# INSIDER_CACHE_PATH=data/insider/form4.sqlite
# PATTERN_AUDIT_DIR=data/pattern_audit
```

**COPY for Phase 7** (append):
```
# Phase 7 — sizing + journal (D-05, OUT-04).
# ACCOUNT_EQUITY already declared above (line ~26); do NOT duplicate.
RISK_PCT=0.01
JOURNAL_THRESHOLD=50.0
# JOURNAL_DB_PATH=data/journal.sqlite
```

---

### `tests/test_sizing.py` (NEW — unit tests for `compute_sizing`)

**Analog:** `tests/test_publishers_pipeline.py` (pure-function tests for `apply_regime_gate` + `validate_run`).

**Test-function pattern** (test_publishers_pipeline.py:12-23):
```python
def test_soft_regime_gate_multiplies() -> None:
    """D-03: composite_score *= regime_score on the cross-section frame."""
    panel = pd.DataFrame(
        {"composite_score": [50.0, 80.0, 30.0]},
        index=pd.Index(["AAA", "BBB", "CCC"], name="ticker"),
    )
    out = apply_regime_gate(panel, regime_score=0.5)
    assert out.loc["AAA", "composite_score"] == 25.0
    ...
    # Original frame is untouched (.copy() inside apply_regime_gate).
    assert panel.loc["AAA", "composite_score"] == 50.0
```

**COPY for Phase 7** — each test name from RESEARCH §Validation Architecture Test Map:
- `test_shares_formula` (SIZ-01)
- `test_zero_regime_score_zero_shares` (SIZ-01 / Pitfall 6)
- `test_shares_nonneg_property` (hypothesis property test)
- `test_adr_reject_boundary` (SIZ-02 — risk_per_share at exactly adr_dollars)
- `test_stop_dispatch_per_playbook` (SIZ-03 / SC-2 — uses the dict registry):
  ```python
  from screener.sizing import STOP_HELPERS, _stop_qullamaggie, _stop_minervini_vcp, _stop_leader_hold
  assert STOP_HELPERS["qullamaggie_continuation"] is _stop_qullamaggie
  assert STOP_HELPERS["minervini_vcp"] is _stop_minervini_vcp
  assert STOP_HELPERS["leader_hold"] is _stop_leader_hold
  ```
- `test_leader_swing_fallback` (SIZ-03 — empty pivot list → 2xATR)
- `test_vcp_stop_from_diagnostics` (SIZ-03 — uses `pattern_diagnostics` JSON)
- `test_trail_label_dispatch` (SIZ-04)
- `test_qull_trail_speed_tiers` (SIZ-04 — boundary ADR%=4.0 and 6.0)
- `test_atr_zone_boundaries` (SIZ-05 — exactly 0.66 → in-zone; exactly 1.00 → extended)
- `test_pure_function_no_input_mutation` (mirror line 22-23 of analog)

All use the `sized_input_cross()` conftest fixture (NEW — see below).

---

### `tests/test_journal.py` (NEW — SQLite + trigger semantics + idempotency)

**Analog:** `tests/test_insider_io.py` — SQLite append-only test idiom.

**Patterns to copy:**

1. **`tmp_path` + monkeypatch + `get_settings.cache_clear()` pattern** (test_insider_io.py:92-117):
```python
def test_form4_bulk_fetch_idempotent(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-10: second invocation with same filings inserts ZERO rows.
    ON CONFLICT(filing_id) DO NOTHING preserves append-only history.
    """
    db_path = str(tmp_path / "form4.sqlite")
    monkeypatch.setenv("INSIDER_CACHE_PATH", db_path)
    from screener.config import get_settings
    get_settings.cache_clear()
    ...
```

**COPY for Phase 7** — every test isolates to `tmp_path / "journal.sqlite"`, monkeypatches `JOURNAL_DB_PATH`, clears `get_settings` cache.

2. **Pandera-rejection-blocks-insert pattern** (test_insider_io.py:120-157):
```python
def test_form4_schema_validated_before_sqlite_insert(...) -> None:
    persistence._ensure_insider_schema(db_path)
    bad_df = pd.DataFrame({..., "type": ["GIFT"], ...})  # invalid per InsiderSchema
    with pytest.raises(Exception):
        persistence.validate_at_write(persistence.InsiderSchema, bad_df)
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM form4").fetchone()[0]
    assert count == 0
```

**Tests to write** (from RESEARCH §Validation Architecture Test Map):
- `test_immutability_trigger` (OUT-05 — UPDATE on decision col raises `sqlite3.IntegrityError` with `'decision column immutable'`)
- `test_outcome_col_not_in_trigger` (OUT-06 — UPDATE on `exit_price` succeeds)
- `test_outcome_column_updatable` (OUT-06)
- `test_idempotent_append` (OUT-04 — RESEARCH §Code Examples Pattern 4 verbatim — mixed insertable + duplicate; assert `cur.rowcount == 1`)
- `test_features_json_roundtrip` (OUT-05 — `json.loads` round-trips)
- `test_features_json_includes_diagnostics` (OUT-05 — full Phase 6 D-05 keys present)
- `test_schema_idempotent_recreates_trigger` (Pitfall 1 — DROP table + re-call `_ensure_picks_schema` + assert trigger still fires)
- `test_picks_schema_rejects_invalid_playbook_tag` (mirror `test_form4_schema_validated_before_sqlite_insert`)
- `test_picks_schema_rejects_invalid_atr_zone` (CHECK constraint defense in depth)
- `test_journal_cli_idempotent` (OUT-04 — invoke `cli.journal` twice, assert second call inserts 0)

---

### `tests/test_pipeline_journal.py` (NEW — integration)

**Analog 1:** `tests/test_publishers_pipeline.py` (pipeline building-block tests).
**Analog 2:** `tests/test_cli_smoke.py::test_report_data_quality_gate_d08` (test_cli_smoke.py:203-231 — `monkeypatch.setattr("screener.publishers.pipeline.run_pipeline", fake_pipeline)` + `CliRunner`).

**Pattern from analog 2** (test_cli_smoke.py:213-231):
```python
def fake_pipeline(snapshot_date: str, write_report: bool = True) -> None:
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

**Tests to write:**
- `test_pipeline_writes_journal` (OUT-04 — invoke `run_pipeline(..., write_journal=True)`, assert `data/journal.sqlite` has rows)
- `test_journal_disabled` (D-01 — `write_journal=False` skips append; expect `journal_skipped` event)
- `test_rejected_picks_not_in_journal` (SIZ-02 / D-06 — set fixture row with `risk_per_share > adr_dollars`, run pipeline, assert no row in journal AND row in `## Skipped Picks`)
- `test_golden_pipeline_journal` (SC-1 — full integration round-trip; deterministic seed; assert row count + features_json shape)

Uses `sized_input_cross()` fixture for synthetic cross-section input.

---

### `tests/conftest.py` (add `sized_input_cross()` fixture)

**Analog:** `synthetic_scored_panel` (conftest.py:443-473).

**Existing pattern** (conftest.py:443-473):
```python
@pytest.fixture(scope="session")
def synthetic_scored_panel(synthetic_panel_for_trend_template: pd.DataFrame) -> pd.DataFrame:
    """Post-composite panel cross-section with composite_score / pivot_zone /
    regime_state / regime_score columns populated...
    """
    from screener.publishers.report import _add_publisher_columns
    from screener.signals.composite import DEFAULT_WEIGHTS, score
    from screener.signals.minervini import passes_trend_template

    panel = passes_trend_template(synthetic_panel_for_trend_template)
    panel = score(panel, DEFAULT_WEIGHTS)
    latest_date = panel.index.get_level_values("date").max()
    cross = panel.xs(latest_date, level="date").copy()
    regime_row = pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82})
    cross = _add_publisher_columns(cross, regime_row)
    return cross
```

**COPY for Phase 7** — Pitfall 7 mitigation: build a 5-ticker cross-section with ALL columns sizing requires (close, low, high, atr_14, adr_pct, playbook_tag, pattern_diagnostics, composite_score, regime_state):
```python
@pytest.fixture(scope="function")  # function-scope: tests may mutate
def sized_input_cross() -> pd.DataFrame:
    """5-ticker cross-section with ALL columns sizing.compute_sizing requires.

    Tickers cover all three playbook tags + one with depth_sequence (VCP) +
    one with insufficient history (leader_hold fallback to 2xATR). Required
    columns per RESEARCH §Pitfall 7: close, low, high, atr_14, adr_pct,
    playbook_tag, pattern_diagnostics, composite_score, regime_state,
    passes_trend_template, rs_rating, trend_template_score, volume_component.
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
    flag_diag = encode_pattern_diagnostics({"type": "flag"})  # extend per Plan 06-02 schema

    return pd.DataFrame(
        {
            "ticker": ["QULL", "VCP1", "LEAD", "REJC", "INVS"],
            "close": [120.0, 100.0, 200.0, 80.0, 50.0],
            "low":   [118.0,  99.0, 198.0, 79.5, 49.5],
            "high":  [121.5, 101.0, 202.0, 80.5, 50.5],
            "atr_14": [2.0, 1.5, 4.0, 0.5, 1.0],
            "adr_pct": [5.5, 4.2, 2.1, 0.3, 3.0],  # REJC has tiny adr_pct → risk > adr$
            "playbook_tag": [
                "qullamaggie_continuation", "minervini_vcp", "leader_hold",
                "qullamaggie_continuation", "leader_hold",
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
```

---

### `tests/test_cli_smoke.py` (modify — remove `"journal"` from `PHASE_1_STUBS` + add `test_journal_subcommand_no_longer_stub`)

**Analog:** `test_score_subcommand_no_longer_stub` (test_cli_smoke.py:234-244) — mirror line-for-line.

**Existing PHASE_1_STUBS list** (test_cli_smoke.py:38-43):
```python
PHASE_1_STUBS = [
    # Phase 6 (Plan 06-01) removed `refresh-fundamentals` from this list — its
    # body is filled by Plan 06-05 (Wave 4); see test_refresh_fundamentals_
    # subcommand_no_longer_stub below.
    "journal",
]
```

**MODIFY for Phase 7** — remove the `"journal"` element (the list becomes empty, but the test `test_each_phase1_stub_exits_zero_with_stub_log` is a `for name in PHASE_1_STUBS` loop, so an empty list is harmless: zero iterations, zero assertions). Replace with:
```python
PHASE_1_STUBS: list[str] = [
    # Phase 7 (Plan 07-XX) removed `journal` from this list — its body is filled
    # by Plan 07-XX; see test_journal_subcommand_no_longer_stub below.
]
```

**Existing mirror test** (test_cli_smoke.py:234-244):
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

**COPY for Phase 7** — add immediately after `test_backtest_audit_subcommand_no_longer_stub` (line 286 area), BEFORE the `test_subcommand_surface_locked` block at line 289:
```python
def test_journal_subcommand_no_longer_stub() -> None:
    """Phase 7: `journal` ships a real body — invoking it does NOT emit a
    '[stub] journal not yet implemented' line. Real run will fail without
    data/snapshots/<today>.parquet (FileNotFoundError from
    publishers.pipeline._build_journal_rows_df_from_snapshot), but the
    failure is from the catch-up loader, not [stub]."""
    runner = CliRunner()
    result = runner.invoke(app, ["journal"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events if ev.get("command") == "journal" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener journal` still emits a [stub] line: {stub_events!r}"
```

**Do NOT touch** `D14_SUBCOMMANDS` (line 20-30) or `test_subcommand_surface_locked` (line 292-316) — D-11/D-24 locks the 9-subcommand surface.

---

## Shared Patterns

### Pure-function discipline
**Source:** `src/screener/signals/composite.py:1-17` module docstring + `score()` `out = panel.copy()` idiom
**Apply to:** `src/screener/sizing.py` and the new `_build_journal_rows_df` helper
**Excerpt:**
```python
"""...
Pure-function discipline (Phase 1 D-16): no I/O, no global state, panel-in /
panel-out. Imports only pandas + stdlib typing.
"""
def score(panel: pd.DataFrame, weights: dict[str, float] = DEFAULT_WEIGHTS) -> pd.DataFrame:
    out = panel.copy()
    ...
    return out
```
Architecture test (`tests/test_architecture.py`) ALLOWED dict permits `sizing → {signals, regime, config, obs}`; NEVER imports `data` or `persistence` from sizing.py (Anti-Pattern from RESEARCH §Architecture Patterns).

### Structlog event-name conventions
**Source:** `src/screener/persistence.py` throughout — `snapshot_written`, `fundamentals_written`, etc.; `src/screener/publishers/pipeline.py:185-193` `pipeline_complete`
**Apply to:** every new structlog event in sizing.py, persistence (picks helpers), publishers/pipeline.py, cli.journal
**Excerpt:**
```python
log = structlog.get_logger(__name__)
log.info("snapshot_written", path=str(target), n_rows=len(validated), snapshot_date=snapshot_date)
```
Phase 7 events (RESEARCH §Code Examples Pattern 5): `sizing_applied`, `sizing_rejected` (DEBUG), `journal_appended`, `journal_append_summary`, `journal_skipped`, `journal_catchup_complete`, `journal_catchup_empty`, `journal_failed`. Prefix_action naming shape.

### Atomic-write idiom (Parquet)
**Source:** `src/screener/persistence.py:369-391` `_write_parquet_atomic`
**Apply to:** any Parquet write of the extended snapshot — already reused via `write_snapshot_atomic` (persistence.py:536-552); Phase 7 does NOT add a new Parquet writer (the extended snapshot reuses `write_snapshot_atomic` because the schema extension is additive).
**Excerpt:**
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False,
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

### Pandera validation at I/O boundary
**Source:** `src/screener/persistence.py:356-363` `validate_at_write` (eager) + `validate_at_read` (lazy); usage in `write_snapshot_atomic:543`
**Apply to:** Phase 7's new `PicksSchema` — caller `_build_journal_rows_df` calls `validate_at_write(PicksSchema, df)` BEFORE `append_picks_rows` (mirror `append_form4_rows`'s "Pattern B — caller validates" contract at persistence.py:925).
**Excerpt:**
```python
def validate_at_write(schema_cls: type[pa.DataFrameModel], df: pd.DataFrame) -> pd.DataFrame:
    """Eager validation (lazy=False): fail on first error. Use at write boundary."""
    return schema_cls.validate(df, lazy=False)
```

### SQLite append-only with idempotency
**Source:** `src/screener/persistence.py:891-944` — `_FORM4_DDL` Final constant + `_ensure_insider_schema` + `append_form4_rows` (`ON CONFLICT(filing_id) DO NOTHING`)
**Apply to:** `_PICKS_DDL` + `_ensure_picks_schema` + `append_picks_rows` (Phase 7's `INSERT OR IGNORE` on `UNIQUE(ticker, snapshot_date)` — per CONTEXT specifics)
**Excerpt:** see "Append pattern" in `persistence.py` section above.

### Settings additive extension
**Source:** `src/screener/config.py` — Phase 2/3/4/6 sections added as `# Phase N — ...` comment blocks
**Apply to:** Phase 7 — new `RISK_PCT`, `JOURNAL_THRESHOLD`, `JOURNAL_DB_PATH` fields appended to Settings class body; mirrored to `.env.example` with same section header.

### CLI typer command body shape
**Source:** `src/screener/cli.py:198-214` `score` (and 217-229 `report`)
**Apply to:** `journal` command body fill
**Excerpt:** `configure_logging()` → `try`/`except typer.Exit: raise` (Pitfall 7 — typer.Exit must propagate) → `except Exception as e: log.error(...error_type=type(e).__name__); raise typer.Exit(code=1) from e` (T-3-02 — never log exception string).

### Per-pick block extension in report
**Source:** `src/screener/publishers/report.py:289-307` per-pick loop
**Apply to:** add sizing fields (Stop / Trail / Shares / Zone / Entry) at the end of each per-pick block; Pitfall 12 — plain ASCII only, no emoji.

### Pitfall 7 — Test fixtures need ALL Phase-6 + Phase-7 columns
**Source:** RESEARCH §Pitfall 7 + `tests/conftest.py:443-473` `synthetic_scored_panel`
**Apply to:** the new `sized_input_cross()` fixture must carry `close, low, high, atr_14, adr_pct, playbook_tag, pattern_diagnostics, composite_score, regime_state` — `KeyError` in any sizing test means extend the fixture, NOT add defensive `.get()` in sizing.py (sizing's input contract is strict).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All 13 Phase 7 files map to strong in-repo analogs. Phase 7 is purely additive wiring; no genuinely-new patterns are introduced. |

The only genuinely-new artifacts (per RESEARCH §"Don't Hand-Roll" final line) are the immutability trigger SQL (~10 lines, embedded in `_PICKS_DDL` constant) and the `picks` table DDL (~30 lines, ditto). Both are derived from RESEARCH §Code Examples Pattern 1 (empirically verified 2026-05-18 against sqlite 3.51.0) and the `_FORM4_DDL` shape at persistence.py:891-906.

## Metadata

**Analog search scope:** `src/screener/sizing.py`, `src/screener/signals/composite.py`, `src/screener/config.py`, `src/screener/persistence.py`, `src/screener/publishers/pipeline.py`, `src/screener/publishers/report.py`, `src/screener/cli.py`, `src/screener/indicators/patterns.py`, `src/screener/indicators/volatility.py`, `tests/conftest.py`, `tests/test_publishers_pipeline.py`, `tests/test_insider_io.py`, `tests/test_cli_smoke.py`, `.env.example`
**Files scanned:** 14 source + 4 test fixtures examined; 13 strong analogs returned
**Pattern extraction date:** 2026-05-18
**Stack confidence:** HIGH — all required patterns exist in repo; Phase 7 is wiring, not invention.
