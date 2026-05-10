---
phase: 03-indicator-panel-regime
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/screener/config.py
  - src/screener/persistence.py
  - .env.example
  - tests/conftest.py
  - tests/test_persistence.py
  - tests/test_rs_snapshot.py
autonomous: true
requirements:
  - DAT-04
  - IND-03
tags:
  - settings
  - schemas
  - persistence

must_haves:
  truths:
    - "Settings exposes 8 new D-12 fields (MACRO_CACHE_DIR, RS_SNAPSHOT_DIR, MACRO_BACKFILL_START, REGIME_BREADTH_THRESHOLD, REGIME_DIST_DAYS_PRESSURE, REGIME_DIST_DAYS_CORRECTION, REGIME_VIX_CORRECTION, REGIME_VIX_CONFIRMED) with typed defaults; .env.example mirrors them under a Phase 3 (D-12) comment block."
    - "persistence.py defines 5 new pandera DataFrameModel schemas: MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema — all with strict=True, coerce=False; rs_rating uses pd.Int64Dtype (nullable), not int."
    - "persistence.py exports write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, and one read_macro_<series> per macro file — every writer routes through _write_parquet_atomic (D-11); every reader uses validate_at_read on existing files. Each read_macro_<series>() returns a SCHEMA-SHAPED EMPTY DataFrame when the cache file does not yet exist (required by Plan 03-02 D-06 incremental-refresh — the refresh_<series> functions can call read_macro_<series>() unconditionally to inspect existing.index.max() without an extra path.exists() guard at the call site)."
    - "_macro_dir() and _rs_snapshot_dir() resolver helpers exist following the _ohlcv_dir() pattern (getattr-with-default for race safety)."
  artifacts:
    - path: "src/screener/config.py"
      provides: "8 new D-12 fields appended to Settings"
      contains: "MACRO_CACHE_DIR, RS_SNAPSHOT_DIR, MACRO_BACKFILL_START, REGIME_BREADTH_THRESHOLD, REGIME_DIST_DAYS_PRESSURE, REGIME_DIST_DAYS_CORRECTION, REGIME_VIX_CORRECTION, REGIME_VIX_CONFIRMED"
    - path: "src/screener/persistence.py"
      provides: "5 new schemas + write_rs_snapshot_atomic + read_rs_snapshot + write_macro_atomic + 5 read_macro_* helpers + _macro_dir + _rs_snapshot_dir"
      contains: "class MacroOhlcvSchema, class VixSchema, class YieldsSchema, class NyadMacroSchema, class RsSnapshotSchema, def write_rs_snapshot_atomic, def read_rs_snapshot, def write_macro_atomic, def _macro_dir, def _rs_snapshot_dir"
    - path: ".env.example"
      provides: "Phase 3 (D-12) mirror block — 8 keys with default values"
      contains: "# Phase 3 (D-12) — macro + RS snapshot paths and regime thresholds, MACRO_CACHE_DIR=data/macro, RS_SNAPSHOT_DIR=data/rs_snapshots"
    - path: "tests/test_rs_snapshot.py"
      provides: "Atomic-write crash test + round-trip test + dtype-rejection test for RsSnapshotSchema; lazy-validation test for MacroOhlcvSchema reader"
      exports: ["test_rs_snapshot_atomic_write", "test_rs_snapshot_round_trip", "test_rs_snapshot_schema_rejects_bad_rating", "test_read_macro_spy_validates"]
  key_links:
    - from: "src/screener/persistence.py write_rs_snapshot_atomic"
      to: "src/screener/persistence.py _write_parquet_atomic"
      via: "direct function call"
      pattern: "_write_parquet_atomic\\(validated, target\\)"
    - from: "src/screener/persistence.py write_rs_snapshot_atomic"
      to: "src/screener/persistence.py validate_at_write"
      via: "schema validation before write"
      pattern: "validate_at_write\\(RsSnapshotSchema, df\\)"
    - from: "src/screener/persistence.py read_rs_snapshot / read_macro_*"
      to: "src/screener/persistence.py validate_at_read"
      via: "schema validation at read boundary"
      pattern: "validate_at_read\\("
    - from: ".env.example"
      to: "src/screener/config.py Settings"
      via: "1:1 field-name mirror"
      pattern: "MACRO_CACHE_DIR=data/macro"
---

<objective>
Lay the schema + Settings + persistence-helper foundation that every other Phase 3 plan depends on. This is Wave 1 because Plan 03-02 (macro data layer), Plan 03-03 (indicator panel), Plan 03-04 (regime), and Plan 03-05 (CI gates + tests) all import from these primitives.

Purpose: Centralize the pandera schemas at the persistence seam (Phase 1 D-13), extend Settings additively (Phase 2 D-20 pattern), and provide the atomic-write helpers (Phase 2 D-11) that downstream macro and RS-snapshot writers will call. No business logic — pure schema and helper definition.

Output:
- 8 new typed fields appended to `Settings` under a `# Phase 3 (D-12)` comment block
- 5 new pandera DataFrameModel schemas in `persistence.py`
- 4 new public helpers in `persistence.py`: `write_rs_snapshot_atomic`, `read_rs_snapshot`, `write_macro_atomic`, plus per-series `read_macro_*` accessors
- 2 new private resolver helpers: `_macro_dir`, `_rs_snapshot_dir`
- `.env.example` mirrored block
- Unit tests covering atomic-write crash safety, round-trip, schema dtype enforcement, and lazy-read validation
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
@.planning/phases/03-indicator-panel-regime/03-CONTEXT.md
@.planning/phases/03-indicator-panel-regime/03-RESEARCH.md
@.planning/phases/03-indicator-panel-regime/03-PATTERNS.md
@.planning/phases/03-indicator-panel-regime/03-VALIDATION.md
@.planning/phases/02-data-foundation/02-CONTEXT.md

@src/screener/persistence.py
@src/screener/config.py
@.env.example
@tests/test_persistence.py
@tests/conftest.py

<interfaces>
<!-- Existing primitives in persistence.py that Phase 3 reuses 1:1 — DO NOT redefine. -->

From src/screener/persistence.py (lines 154-176, 141-148, 193-207):
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Atomic write: tempfile in target.parent, os.replace. mkdir(parents=True, exist_ok=True)
    auto-creates data/macro/ and data/rs_snapshots/ on first run (Pitfall 10)."""

def validate_at_write(schema_cls, df):
    """Eager validation (lazy=False); fails loud at write boundary."""
    return schema_cls.validate(df, lazy=False)

def validate_at_read(schema_cls, df):
    """Lazy validation (lazy=True); collect-all errors at read boundary."""
    return schema_cls.validate(df, lazy=True)

# Resolver helper template (existing _ohlcv_dir / _universe_dir pattern):
def _ohlcv_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "OHLCV_CACHE_DIR", "data/ohlcv"))

# Existing schema template (OhlcvPanelSchema, lines 76-100):
class OhlcvPanelSchema(pa.DataFrameModel):
    ticker: Index[str] = pa.Field(check_name=True)
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    # ...
    class Config:
        multiindex_strict = True
        multiindex_coerce = False
        strict = True
        coerce = False
```

From src/screener/config.py (existing Settings class):
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # ... existing 15 Phase 1+2 fields ...
    # Phase 2 (D-20) — data-layer paths and policy
    OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
    UNIVERSE_CACHE_DIR: Path = Path("data/universe")
    OHLCV_BACKFILL_START: str = "2005-01-01"
    UNIVERSE_HEALTH_THRESHOLD: float = 0.95
    STOOQ_BREAKER_PROBE_N: int = 50
    STOOQ_BREAKER_THRESHOLD: float = 0.80
    OHLCV_FETCH_SLEEP_MIN_S: float = 0.5
    OHLCV_FETCH_SLEEP_MAX_S: float = 1.5
```
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| disk → persistence | Parquet on local filesystem may be tampered with or partially-written; pandera lazy validation at read catches schema violations |
| Settings → persistence | Config values may be missing if .env is not populated; getattr-with-default fallback prevents crash |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 | Tampering | persistence.py read_macro_* / read_rs_snapshot | mitigate | Use validate_at_read(SchemaCls, df) lazy validation at every read boundary; lazy=True collects all schema errors instead of stopping at first; references RESEARCH Pitfall 4 (^VIX volume=0 — VixSchema is close-only, blocks malformed full-OHLCV macro inputs from masquerading as VIX). |
| T-3-04 | Tampering | persistence.py write_rs_snapshot_atomic | mitigate | Reuse _write_parquet_atomic (Phase 2 D-11): tempfile in target.parent + os.replace; on exception unlink tmp; ensures no partial data/rs_snapshots/<date>.parquet ever exists. Crash-safety verified by test_rs_snapshot_atomic_write. |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend Settings with 8 D-12 fields and mirror in .env.example</name>
  <files>src/screener/config.py, .env.example</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/config.py (current state — 60 lines; understand the existing additive pattern from Phase 2 D-20 lines 41-49)
    - /Users/belwinjulian/Desktop/SwingTrading/.env.example (current state — to find the insertion point for Phase 3 mirror block; existing Phase 2 mirror at lines 32-39 is the template)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-CONTEXT.md (D-12 — exact 8 field names, types, and default values; section "Settings additions")
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 633-679 — Additive Settings Extension pattern; lines 812-841 — .env.example mirror pattern)
  </read_first>
  <behavior>
    - Test: `from screener.config import get_settings; s = get_settings(); assert s.MACRO_CACHE_DIR == Path("data/macro")` — MACRO_CACHE_DIR field exists with correct typed default.
    - Test: `s.RS_SNAPSHOT_DIR == Path("data/rs_snapshots")` — RS_SNAPSHOT_DIR field exists with correct typed default.
    - Test: `s.MACRO_BACKFILL_START == "2005-01-01"` — backfill date matches OHLCV history (per D-12).
    - Test: `s.REGIME_BREADTH_THRESHOLD == 0.60` and is `float`.
    - Test: `s.REGIME_DIST_DAYS_PRESSURE == 5` and is `int`; `s.REGIME_DIST_DAYS_CORRECTION == 9` and is `int`.
    - Test: `s.REGIME_VIX_CORRECTION == 30.0` and is `float`; `s.REGIME_VIX_CONFIRMED == 20.0` and is `float`.
    - Test: `.env.example` contains a `# Phase 3 (D-12)` comment header followed by all 8 keys (grep-verifiable).
    - Test: All 15 pre-existing Phase 1+2 Settings fields still present (no regression to FRED_API_KEY, OHLCV_CACHE_DIR, etc.).
  </behavior>
  <action>
Append to `src/screener/config.py` after the existing Phase 2 (D-20) block (currently ending at line 49 with `OHLCV_FETCH_SLEEP_MAX_S: float = 1.5`) — insert these 9 lines (1 comment + 8 fields) BEFORE the closing of the `Settings` class. Use the exact comment-block style and indentation from Phase 2:

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

Do NOT modify the existing `model_config`, `get_settings()`, or any pre-existing field. The `lru_cache(maxsize=1)` on `get_settings()` covers new fields automatically (Phase 2 precedent — lines 52-60).

Then append to `.env.example` at end of file, mirroring per D-12:

```
# Phase 3 — macro + RS snapshot paths and regime thresholds (D-12)
MACRO_CACHE_DIR=data/macro
RS_SNAPSHOT_DIR=data/rs_snapshots
MACRO_BACKFILL_START=2005-01-01
REGIME_BREADTH_THRESHOLD=0.60
REGIME_DIST_DAYS_PRESSURE=5
REGIME_DIST_DAYS_CORRECTION=9
REGIME_VIX_CORRECTION=30.0
REGIME_VIX_CONFIRMED=20.0
```

Style note: paths unquoted, integers/floats raw (no quotes), one comment header naming phase + decision ID.
  </action>
  <verify>
    <automated>uv run python -c "from screener.config import get_settings; s=get_settings(); assert s.MACRO_CACHE_DIR.as_posix()=='data/macro'; assert s.RS_SNAPSHOT_DIR.as_posix()=='data/rs_snapshots'; assert s.MACRO_BACKFILL_START=='2005-01-01'; assert s.REGIME_BREADTH_THRESHOLD==0.60; assert s.REGIME_DIST_DAYS_PRESSURE==5; assert s.REGIME_DIST_DAYS_CORRECTION==9; assert s.REGIME_VIX_CORRECTION==30.0; assert s.REGIME_VIX_CONFIRMED==20.0; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "MACRO_CACHE_DIR" src/screener/config.py` returns 1 (exactly one definition).
    - `grep -c "RS_SNAPSHOT_DIR" src/screener/config.py` returns 1.
    - `grep -c "REGIME_BREADTH_THRESHOLD" src/screener/config.py` returns 1.
    - `grep -c "Phase 3 (D-12)" src/screener/config.py` returns 1 (header present once).
    - `grep -E "^MACRO_CACHE_DIR=data/macro$" .env.example` returns one line.
    - `grep -E "^RS_SNAPSHOT_DIR=data/rs_snapshots$" .env.example` returns one line.
    - `grep -E "^MACRO_BACKFILL_START=2005-01-01$" .env.example` returns one line.
    - `grep -cE "^REGIME_(BREADTH_THRESHOLD|DIST_DAYS_PRESSURE|DIST_DAYS_CORRECTION|VIX_CORRECTION|VIX_CONFIRMED)=" .env.example` returns 5.
    - `uv run mypy --config-file pyproject.toml src/screener/config.py` exits 0 (typed defaults pass strict mode).
    - `uv run ruff check src/screener/config.py` exits 0.
    - The instantiation command in `<automated>` exits 0 with `OK` on stdout.
  </acceptance_criteria>
  <done>Settings extended with 8 typed D-12 fields; .env.example mirrored; existing fields untouched; type-check clean; instantiation test passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 5 pandera schemas + 4 public helpers + 2 resolver helpers to persistence.py</name>
  <files>src/screener/persistence.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/persistence.py (current state — 331 lines; key references: imports lines 25-39, OhlcvPanelSchema lines 76-100, validate_at_write/validate_at_read lines 141-148, _write_parquet_atomic lines 154-176, _ohlcv_dir/_universe_dir lines 193-207, write_universe_atomic lines 213-219, write_ohlcv_atomic lines 222-241, read_universe lines 276-292)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Pattern 7 lines 374-412 — exact schema bodies; Pitfall 4 — VIX is close-only; Pitfall 9 — rs_rating must be Series[pd.Int64Dtype], not int; Pitfall 10 — _write_parquet_atomic mkdir handles new dirs)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 92-156 — schema definition + atomic-write contract + path-resolver helper pattern; lines 1186-1262 — Shared Patterns: Atomic Parquet Write, Validation Policy, Pandera Schema Definition)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/02-data-foundation/02-CONTEXT.md (D-11 atomic-write, D-15 schema policy, D-16 lazy-at-read / eager-at-write — Phase 3 must mirror verbatim)
  </read_first>
  <behavior>
    - Test: `from screener.persistence import MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema` — all 5 schemas importable.
    - Test: `MacroOhlcvSchema` has columns {open, high, low, close, volume} (lowercase) and `date` Index; volume `Series[int]`; strict=True, coerce=False.
    - Test: `VixSchema` has only `close` column (no volume — Pitfall 4) and `date` Index.
    - Test: `YieldsSchema` has columns {dgs2, dgs10, t10y2y} all `nullable=True` (FRED weekend gaps — Pitfall 5).
    - Test: `NyadMacroSchema` has columns {advances, declines, ad_line}; advances/declines `ge=0`, ad_line nullable=False but can be negative.
    - Test: `RsSnapshotSchema` has `ticker: Series[str]` with `str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$"`, `rs_raw: Series[float] nullable=True`, `rs_rating: Series[pd.Int64Dtype] nullable=True`.
    - Test: `from screener.persistence import write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, read_macro_spy, read_macro_qqq, read_macro_vix, read_macro_yields, read_macro_nyad` — all importable.
    - Test: `_macro_dir()` returns `Path("data/macro")` after Settings is populated; `_rs_snapshot_dir()` returns `Path("data/rs_snapshots")`.
    - Test: `write_rs_snapshot_atomic(valid_df, "2026-04-30")` creates `data/rs_snapshots/2026-04-30.parquet` and emits structlog event `rs_snapshot_written`.
    - Test: `write_macro_atomic(valid_df, "spy")` creates `data/macro/spy.parquet`; `read_macro_spy()` reads and lazy-validates.
    - Test: A `to_parquet` exception during atomic-write leaves NO partial `data/rs_snapshots/<date>.parquet` AND no `.tmp` residue.
    - Test: Reading a Parquet that violates `MacroOhlcvSchema` (e.g., missing `volume` column) raises `pandera.errors.SchemaError` (lazy mode collects errors).
    - Test: `RsSnapshotSchema` rejects a DataFrame where `rs_rating` is `int` not `Int64` (Pitfall 9).
  </behavior>
  <action>
Modify `src/screener/persistence.py` in-place. DO NOT create a new module. Phase 1 D-13 locks `persistence.py` as the single schema seam.

**Step A — Add schemas after `SplitsSchema` (find existing `class SplitsSchema(pa.DataFrameModel):` and append immediately after its closing `class Config:` block).**

Add the 5 new schemas verbatim from RESEARCH.md Pattern 7:

```python
class MacroOhlcvSchema(pa.DataFrameModel):
    """Single-index (date) macro OHLCV — SPY, QQQ. Lowercase columns
    (data/ layer normalizes yfinance PascalCase before reaching this schema).
    """
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)

    class Config:
        strict = True
        coerce = False


class VixSchema(pa.DataFrameModel):
    """^VIX is close-only — yfinance returns Volume=0 always (RESEARCH Pitfall 4)."""
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)

    class Config:
        strict = True
        coerce = False


class YieldsSchema(pa.DataFrameModel):
    """FRED yields — DGS2, DGS10, T10Y2Y in a single Parquet.
    Nullable because FRED has weekday-only data + holiday gaps (RESEARCH Pitfall 5);
    consumer side ffills at read time.
    """
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    dgs2: Series[float] = pa.Field(nullable=True)
    dgs10: Series[float] = pa.Field(nullable=True)
    t10y2y: Series[float] = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = False


class NyadMacroSchema(pa.DataFrameModel):
    """NYSE A/D line — Stooq $NYAD primary, R1000-breadth fallback per D-05.
    ad_line is the cumulative advances - declines (can be negative).
    """
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    advances: Series[int] = pa.Field(ge=0, nullable=False)
    declines: Series[int] = pa.Field(ge=0, nullable=False)
    ad_line: Series[int] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False


class RsSnapshotSchema(pa.DataFrameModel):
    """One row per ticker, taken on a single trading date.
    rs_rating is nullable Int64 — pd.Int64Dtype, NOT int (RESEARCH Pitfall 9):
    int cannot hold NaN, but tickers with < 252d history must produce NaN.
    """
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rs_raw: Series[float] = pa.Field(nullable=True)
    rs_rating: Series[pd.Int64Dtype] = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = False
```

**Step B — Add 2 resolver helpers near the existing `_ohlcv_dir` / `_universe_dir` (lines 193-207).**

Use the same `getattr(s, NAME, default)` pattern (cross-wave Settings race safety):

```python
def _macro_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "MACRO_CACHE_DIR", "data/macro"))


def _rs_snapshot_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "RS_SNAPSHOT_DIR", "data/rs_snapshots"))
```

**Step C — Add 4 public writers near `write_universe_atomic` / `write_ohlcv_atomic` (lines 213-241).**

```python
def write_rs_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write an RS snapshot to data/rs_snapshots/<date>.parquet.
    Eager validation (D-16): bad row aborts loud at the write boundary."""
    validated = validate_at_write(RsSnapshotSchema, df)
    target = _rs_snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("rs_snapshot_written", path=str(target), n_rows=len(validated), snapshot_date=snapshot_date)
    return target


# Schema dispatch for macro writes — one of: spy, qqq, vix, nyad, yields.
_MACRO_SCHEMAS: dict[str, type[pa.DataFrameModel]] = {
    "spy": MacroOhlcvSchema,
    "qqq": MacroOhlcvSchema,
    "vix": VixSchema,
    "yields": YieldsSchema,
    "nyad": NyadMacroSchema,
}


def write_macro_atomic(df: pd.DataFrame, series_name: str) -> Path:
    """Validate + atomically write a macro series to data/macro/<series>.parquet.
    series_name must be one of: spy, qqq, vix, nyad, yields.
    """
    if series_name not in _MACRO_SCHEMAS:
        raise ValueError(f"unknown macro series {series_name!r}; expected one of {sorted(_MACRO_SCHEMAS)}")
    schema = _MACRO_SCHEMAS[series_name]
    validated = validate_at_write(schema, df)
    target = _macro_dir() / f"{series_name}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("macro_snapshot_written", series=series_name, path=str(target), n_rows=len(validated))
    return target
```

**Step D — Add 6 public readers near `read_universe` / `read_panel` (line 276+).**

```python
def read_rs_snapshot(snapshot_date: str) -> pd.DataFrame:
    """Read + lazy-validate an RS snapshot from data/rs_snapshots/<date>.parquet."""
    path = _rs_snapshot_dir() / f"{snapshot_date}.parquet"
    df = pd.read_parquet(path)
    return validate_at_read(RsSnapshotSchema, df)


# Macro readers — graceful "missing cache" semantics (D-06 incremental refresh).
# When the Parquet does not yet exist (first run), return an empty DataFrame with
# the right schema-shape so refresh_<series>() can use the standard
#   existing = read_macro_<series>()
#   if existing.empty: start = MACRO_BACKFILL_START else: start = existing.index.max()+1d
# pattern from Phase 2 D-07 without an extra path.exists() guard at the call site.

_EMPTY_DT_INDEX = pd.DatetimeIndex([], name="date")


def read_macro_spy() -> pd.DataFrame:
    path = _macro_dir() / "spy.parquet"
    if not path.exists():
        return pd.DataFrame(
            {"open": pd.Series([], dtype="float64"),
             "high": pd.Series([], dtype="float64"),
             "low": pd.Series([], dtype="float64"),
             "close": pd.Series([], dtype="float64"),
             "volume": pd.Series([], dtype="int64")},
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(MacroOhlcvSchema, df)


def read_macro_qqq() -> pd.DataFrame:
    path = _macro_dir() / "qqq.parquet"
    if not path.exists():
        return pd.DataFrame(
            {"open": pd.Series([], dtype="float64"),
             "high": pd.Series([], dtype="float64"),
             "low": pd.Series([], dtype="float64"),
             "close": pd.Series([], dtype="float64"),
             "volume": pd.Series([], dtype="int64")},
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(MacroOhlcvSchema, df)


def read_macro_vix() -> pd.DataFrame:
    path = _macro_dir() / "vix.parquet"
    if not path.exists():
        return pd.DataFrame({"close": pd.Series([], dtype="float64")}, index=_EMPTY_DT_INDEX)
    df = pd.read_parquet(path)
    return validate_at_read(VixSchema, df)


def read_macro_yields() -> pd.DataFrame:
    path = _macro_dir() / "yields.parquet"
    if not path.exists():
        return pd.DataFrame(
            {"dgs2": pd.Series([], dtype="float64"),
             "dgs10": pd.Series([], dtype="float64"),
             "t10y2y": pd.Series([], dtype="float64")},
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(YieldsSchema, df)


def read_macro_nyad() -> pd.DataFrame:
    path = _macro_dir() / "nyad.parquet"
    if not path.exists():
        return pd.DataFrame(
            {"advances": pd.Series([], dtype="int64"),
             "declines": pd.Series([], dtype="int64"),
             "ad_line": pd.Series([], dtype="int64")},
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(NyadMacroSchema, df)
```

**No new module-level imports needed** — `pandera.pandas as pa`, `Index`, `Series`, `pd`, `Path`, `Any`, `get_settings`, `log`, `tempfile`, `os` are all already imported (persistence.py lines 25-39).

DO NOT touch the existing `OhlcvPanelSchema`, `UniverseSchema`, `SplitsSchema`, `_write_parquet_atomic`, `validate_at_write`, `validate_at_read`, `write_universe_atomic`, `write_ohlcv_atomic`, `write_splits_atomic`, `make_empty_splits`, `read_panel`, `read_splits`, `read_universe`, `_assert_safe_ticker` — they are Phase 1+2 contracts.
  </action>
  <verify>
    <automated>uv run python -c "from screener.persistence import MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema, write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, read_macro_spy, read_macro_qqq, read_macro_vix, read_macro_yields, read_macro_nyad, _macro_dir, _rs_snapshot_dir; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^class MacroOhlcvSchema" src/screener/persistence.py` returns 1.
    - `grep -c "^class VixSchema" src/screener/persistence.py` returns 1.
    - `grep -c "^class YieldsSchema" src/screener/persistence.py` returns 1.
    - `grep -c "^class NyadMacroSchema" src/screener/persistence.py` returns 1.
    - `grep -c "^class RsSnapshotSchema" src/screener/persistence.py` returns 1.
    - `grep -c "^def write_rs_snapshot_atomic" src/screener/persistence.py` returns 1.
    - `grep -c "^def write_macro_atomic" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_macro_spy" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_macro_qqq" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_macro_vix" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_macro_yields" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_macro_nyad" src/screener/persistence.py` returns 1.
    - `grep -c "^def read_rs_snapshot" src/screener/persistence.py` returns 1.
    - `grep -c "^def _macro_dir" src/screener/persistence.py` returns 1.
    - `grep -c "^def _rs_snapshot_dir" src/screener/persistence.py` returns 1.
    - `grep -c "_write_parquet_atomic(validated, target)" src/screener/persistence.py` returns at least 4 (write_universe_atomic, write_ohlcv_atomic, write_rs_snapshot_atomic, write_macro_atomic — atomic-write contract reused).
    - `grep -c "Series\[pd.Int64Dtype\]" src/screener/persistence.py` returns 1 (rs_rating only — Pitfall 9).
    - `grep -c "validate_at_read(" src/screener/persistence.py` returns at least 9 (3 existing: read_universe + read_panel + read_splits; 6 new: read_rs_snapshot + read_macro_spy/qqq/vix/yields/nyad).
    - `uv run mypy --config-file pyproject.toml src/screener/persistence.py` exits 0.
    - `uv run ruff check src/screener/persistence.py` exits 0.
    - The import command in `<automated>` exits 0 with `OK`.
  </acceptance_criteria>
  <done>5 new schemas defined; 4 new public writers + 5 new public readers + 1 read_rs_snapshot helper added; 2 new resolver helpers added; Phase 1+2 primitives untouched; ruff + mypy clean; all symbols importable.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Write Wave 0 unit tests for atomic-write crash safety, round-trip, schema enforcement, and lazy-read validation</name>
  <files>tests/test_rs_snapshot.py, tests/test_persistence.py, tests/conftest.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_persistence.py (existing — for the `_make_panel` helper at lines 23-38, the `test_atomic_write_crash_no_partial` pattern at lines 133-145, and the monkeypatch idiom at lines 161-192)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/conftest.py (existing — for the additive fixture pattern; Phase 3 fixture stubs go at end of file)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 1111-1138 — Atomic-write crash test pattern + Required test functions for tests/test_rs_snapshot.py; lines 1141-1182 — conftest.py extension pattern; lines 942-955 — monkeypatched-dirs round-trip pattern)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (lines 916-918 — RsSnapshotSchema test requirements; Pitfall 9 — Int64 dtype enforcement; Pitfall 10 — atomic-write requires same-filesystem mkdir)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-VALIDATION.md (line 56 — `tests/test_rs_snapshot.py` Wave 0 obligations: round-trip + read_rs_snapshot point-in-time read)
  </read_first>
  <behavior>
    - Test: `test_rs_snapshot_atomic_write` — monkeypatch `pd.DataFrame.to_parquet` to raise OSError mid-write; assert `data/rs_snapshots/<date>.parquet` does NOT exist; assert no `.tmp` residue in target dir.
    - Test: `test_rs_snapshot_round_trip` — write a 5-ticker df with rs_raw / rs_rating (one row NaN for short-history ticker); read back; assert frame equals (after dtype-aware compare).
    - Test: `test_rs_snapshot_schema_rejects_bad_rating` — pass df with `rs_rating: int64` (NOT `Int64`); assert `pandera.errors.SchemaError` raised (Pitfall 9).
    - Test: `test_rs_snapshot_schema_rejects_lowercase_ticker` — pass df with `ticker="aapl"`; assert `pandera.errors.SchemaError` (regex `^[A-Z][A-Z0-9\-]{0,9}$`).
    - Test: `test_read_macro_spy_validates` — write a Parquet missing the `volume` column; `read_macro_spy()` raises `pandera.errors.SchemaError` (lazy mode catches; lazy=True surfaces the schema violation).
    - Test: `test_write_macro_atomic_unknown_series_raises` — `write_macro_atomic(df, "junk")` raises `ValueError` with message containing `"unknown macro series"`.
    - Test: `test_macro_dir_resolves_from_settings` — `_macro_dir()` returns `Path("data/macro")` (matches D-12 default).
  </behavior>
  <action>
**Step A — Create `tests/test_rs_snapshot.py`** with 4 test functions. Use the monkeypatch pattern from `tests/test_persistence.py` lines 161-192 to redirect `_rs_snapshot_dir` and `_macro_dir` to `tmp_path`.

```python
"""RS snapshot + macro persistence tests (D-10, D-11, D-15, D-16; RESEARCH Pitfalls 9, 10).

Wave 0 covers the persistence-layer schema seam additions for Phase 3:
- write_rs_snapshot_atomic / read_rs_snapshot
- write_macro_atomic / read_macro_*
- atomic-write crash safety
- schema dtype enforcement (Int64 nullable; ticker regex)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.errors
import pytest

from screener.persistence import (
    MacroOhlcvSchema,
    NyadMacroSchema,
    RsSnapshotSchema,
    VixSchema,
    YieldsSchema,
    _macro_dir,
    _rs_snapshot_dir,
    _write_parquet_atomic,
    read_macro_spy,
    read_rs_snapshot,
    write_macro_atomic,
    write_rs_snapshot_atomic,
)


def _make_rs_snapshot_df(n_tickers: int = 5) -> pd.DataFrame:
    """Build an RsSnapshotSchema-shaped df: rs_rating MUST be Int64 nullable."""
    tickers = [f"AAA{i}" if i > 0 else "AAA" for i in range(n_tickers)]
    rs_raw = [1.5 + i * 0.1 for i in range(n_tickers)]
    rs_rating = pd.array([90 - i * 10 for i in range(n_tickers)], dtype="Int64")
    return pd.DataFrame({"ticker": tickers, "rs_raw": rs_raw, "rs_rating": rs_rating})


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


def test_rs_snapshot_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write + read recovers exactly the same RS snapshot frame."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    df = _make_rs_snapshot_df()
    target = write_rs_snapshot_atomic(df, "2026-04-30")
    assert target.exists()

    loaded = read_rs_snapshot("2026-04-30")
    assert list(loaded.columns) == ["ticker", "rs_raw", "rs_rating"]
    assert len(loaded) == len(df)
    assert loaded["rs_rating"].dtype == pd.Int64Dtype()


def test_rs_snapshot_schema_rejects_bad_rating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pitfall 9: rs_rating must be pd.Int64Dtype (nullable Int64), NOT int64."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    bad = pd.DataFrame({
        "ticker": ["AAA"],
        "rs_raw": [1.0],
        "rs_rating": pd.Series([50], dtype="int64"),  # NOT nullable Int64
    })
    with pytest.raises(pandera.errors.SchemaError):
        write_rs_snapshot_atomic(bad, "2026-04-30")


def test_rs_snapshot_schema_rejects_lowercase_ticker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ticker must match ^[A-Z][A-Z0-9\\-]{0,9}$ — lowercase rejected."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    bad = pd.DataFrame({
        "ticker": ["aapl"],
        "rs_raw": [1.0],
        "rs_rating": pd.array([50], dtype="Int64"),
    })
    with pytest.raises(pandera.errors.SchemaError):
        write_rs_snapshot_atomic(bad, "2026-04-30")


def test_write_macro_atomic_unknown_series_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown series name fails fast — typo guard."""
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: tmp_path / "macro")
    df = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex(["2026-04-30"], name="date"))
    with pytest.raises(ValueError, match="unknown macro series"):
        write_macro_atomic(df, "junk")


def test_read_macro_spy_validates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Parquet missing the volume column fails MacroOhlcvSchema lazy validation."""
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)

    bad_spy = pd.DataFrame(
        {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5]},  # missing volume
        index=pd.DatetimeIndex(["2026-04-30"], name="date"),
    )
    target = macro_dir / "spy.parquet"
    bad_spy.to_parquet(target, engine="pyarrow", index=True)
    with pytest.raises(pandera.errors.SchemaError):
        read_macro_spy()


def test_macro_dir_resolves_from_settings() -> None:
    """_macro_dir() returns the D-12 default path."""
    assert _macro_dir() == Path("data/macro")


def test_rs_snapshot_dir_resolves_from_settings() -> None:
    assert _rs_snapshot_dir() == Path("data/rs_snapshots")
```

**Step B — Append synthetic-fixture stubs to `tests/conftest.py`** (NOT full-bodied — just the section header and any fixtures that Plans 03-03/04/05 will populate; this preserves Phase 2 fixtures intact). Add at the bottom of the file:

```python
# --- Phase 3 indicator + regime fixtures -----------------------------------
# Populated by Plans 03-03, 03-04, 03-05. This section header is a Wave 0
# anchor; downstream plans add fixtures (synthetic_short_history_panel,
# synthetic_multi_ticker_panel, synthetic_spy_2008q4, synthetic_vix_panic)
# without re-touching the prior phase blocks.
```

**Step C — Extend `tests/test_persistence.py`** with one extra test confirming `_write_parquet_atomic` auto-creates the new dirs (covers Pitfall 10 for `data/macro/` and `data/rs_snapshots/`):

Find the existing `test_atomic_write_crash_no_partial` test (lines 133-145) and add this test below it:

```python
def test_write_parquet_atomic_auto_creates_new_dirs(tmp_path: Path) -> None:
    """Pitfall 10: target.parent.mkdir(parents=True, exist_ok=True) covers
    data/macro/ and data/rs_snapshots/ on first run."""
    nested = tmp_path / "macro" / "deep" / "tree" / "spy.parquet"
    df = pd.DataFrame({"a": [1, 2, 3]})
    _write_parquet_atomic(df, nested)
    assert nested.exists()
```

Keep all existing tests in `tests/test_persistence.py` untouched.
  </action>
  <verify>
    <automated>uv run pytest tests/test_rs_snapshot.py tests/test_persistence.py -m "not slow and not integration" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_rs_snapshot.py` exists.
    - `grep -c "^def test_" tests/test_rs_snapshot.py` returns 8 (atomic_write, round_trip, bad_rating, lowercase_ticker, unknown_series, read_macro_spy_validates, macro_dir, rs_snapshot_dir).
    - `grep -c "Phase 3 indicator + regime fixtures" tests/conftest.py` returns 1.
    - `grep -c "test_write_parquet_atomic_auto_creates_new_dirs" tests/test_persistence.py` returns 1.
    - `uv run pytest tests/test_rs_snapshot.py -x -q` exits 0.
    - `uv run pytest tests/test_persistence.py -x -q` exits 0 (existing tests + 1 new test all pass).
    - `uv run ruff check tests/test_rs_snapshot.py tests/test_persistence.py tests/conftest.py` exits 0.
  </acceptance_criteria>
  <done>tests/test_rs_snapshot.py created with 8 tests; tests/test_persistence.py extended with 1 atomic-create test; tests/conftest.py extended with Phase 3 fixture section header; full test suite green; ruff clean.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_rs_snapshot.py tests/test_persistence.py -m "not slow and not integration" -x -q` exits 0
- `uv run ruff check src/screener/config.py src/screener/persistence.py tests/test_rs_snapshot.py tests/test_persistence.py tests/conftest.py .env.example` exits 0 (note: ruff doesn't lint .env files — included for completeness)
- `uv run mypy --config-file pyproject.toml src/screener/config.py src/screener/persistence.py` exits 0
- `uv run python -c "from screener.config import get_settings; from screener.persistence import MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema, write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, read_macro_spy, read_macro_qqq, read_macro_vix, read_macro_yields, read_macro_nyad; s=get_settings(); assert s.MACRO_CACHE_DIR.as_posix()=='data/macro'; print('OK')"` exits 0
- All Phase 1 + Phase 2 tests still pass: `uv run pytest -m "not slow and not integration" -x -q` exits 0
</verification>

<success_criteria>
- Settings has 8 new typed D-12 fields, mirrored in .env.example
- persistence.py exports 5 new pandera schemas (MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema)
- persistence.py exports 4 new writer helpers (write_rs_snapshot_atomic, write_macro_atomic) and 6 new reader helpers (read_rs_snapshot, read_macro_spy/qqq/vix/yields/nyad)
- Every new writer routes through `_write_parquet_atomic`; every new reader uses `validate_at_read` (Phase 2 D-11 / D-16 contract)
- rs_rating uses `pd.Int64Dtype` (RESEARCH Pitfall 9); ticker uses `str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$"` regex
- 8 new tests pass: atomic-write crash safety, round-trip, schema dtype enforcement (Int64, ticker regex), lazy-validation on read, unknown-series ValueError, dir resolution, Pitfall 10 auto-mkdir
- Phase 1 + Phase 2 contracts untouched (existing OhlcvPanelSchema / UniverseSchema / SplitsSchema / `_write_parquet_atomic` / `validate_at_*` not modified)
- ruff + mypy clean on all touched files
</success_criteria>

<output>
After completion, create `.planning/phases/03-indicator-panel-regime/03-01-SUMMARY.md` documenting the new schemas, helpers, Settings additions, and test coverage. Note any deviations from the plan (none expected — this is a contract-first plan).
</output>
