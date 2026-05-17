"""persistence — Parquet/SQLite read+write helpers and pandera schemas.

The only module that owns disk-format details. Phase 2 ships the three v1
DataFrameModel schemas (D-15), the atomic-write primitive (D-11), per-artifact
writers/readers, and a shared StaleOrEmptyError exception used by data/ohlcv.py
and data/stooq.py.

Architecture invariants (per tests/test_architecture.py):
- This module imports only screener.config (and stdlib + third-party).
- It does NOT import screener.data — data/ calls IN to persistence, not the
  reverse (data/ → persistence is the one-way edge).

Atomic-write contract (D-11): every Parquet artifact is written via
`tempfile.NamedTemporaryFile(dir=target.parent, ...)` + `os.replace()`. The
tempfile MUST live in the same directory as the target so the rename is a
same-filesystem operation, which is the only POSIX-atomic primitive. A crash
mid-write leaves the .tmp file behind but never a half-written `target`.

Validation policy (D-16): eager (lazy=False) at the data/ write boundary so a
single bad row aborts the write loud; lazy (lazy=True) at the indicators/
read boundary via read_panel/read_splits/read_universe so multiple errors
surface together for clearer downstream debugging.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa
import structlog
from pandera.typing import Index, Series

from screener.config import get_settings

log = structlog.get_logger(__name__)


# --- Shared exception (consumed by data/ohlcv.py and data/stooq.py) ----------


class StaleOrEmptyError(RuntimeError):
    """Raised when a fetch returns data that fails the four post-fetch invariants.

    Defined here (not in data/ohlcv.py) so every data/ adapter imports the
    SAME exception type and tenacity's retry_if_exception_type matches across
    yfinance and Stooq paths.
    """


# --- GICS sector allowlist (verified live in iShares feed 2026-05-02) -------

GICS_SECTORS: frozenset[str] = frozenset(
    {
        "Information Technology",
        "Health Care",
        "Financials",
        "Consumer Discretionary",
        "Communication",
        "Industrials",
        "Consumer Staples",
        "Energy",
        "Utilities",
        "Real Estate",
        "Materials",
    }
)


# --- Pandera DataFrameModel schemas (D-15) -----------------------------------


class OhlcvPanelSchema(pa.DataFrameModel):
    """Multi-ticker long-format OHLCV panel with composite (ticker, date) index.

    Used at the data/ → indicators/ boundary. Columns are LOWERCASE (yfinance
    PascalCase is normalized at the data/ layer before reaching this schema).
    Pandera honors the class field-declaration order as the MultiIndex level
    order: ticker first (outer), date second (inner). Reversing them silently
    validates a (date, ticker) panel — the wrong shape — see RESEARCH.md
    Pitfall 8.
    """

    ticker: Index[str] = pa.Field(check_name=True)
    date: Index[pd.Timestamp] = pa.Field(check_name=True)

    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)

    class Config:
        multiindex_strict = True
        multiindex_coerce = False
        strict = True
        coerce = False


class UniverseSchema(pa.DataFrameModel):
    """One row per ticker. The iShares snapshot persisted to data/universe/."""

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    ticker_raw: Series[str] = pa.Field(nullable=False)
    name: Series[str] = pa.Field(nullable=False)
    sector: Series[str] = pa.Field(
        nullable=False,
        isin=list(GICS_SECTORS),
    )
    weight_pct: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=False)

    class Config:
        strict = True
        coerce = False


class SplitsSchema(pa.DataFrameModel):
    """Sparse per-ticker corporate-action ledger.

    Index: DatetimeIndex named 'date'. Columns: ratio (float, ge=0),
    dividend (float, ge=0). Empty case (no actions in cached window) writes
    a zero-row Parquet with the schema preserved — see make_empty_splits().
    """

    date: Index[pd.Timestamp] = pa.Field(check_name=True)

    ratio: Series[float] = pa.Field(ge=0.0, nullable=False)
    dividend: Series[float] = pa.Field(ge=0.0, nullable=False)

    class Config:
        strict = True
        coerce = False


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
    The custom check enforces the exact dtype because pandera coerce=False does
    not distinguish int64 from Int64 at the type-annotation level alone.
    """

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rs_raw: Series[float] = pa.Field(nullable=True)
    rs_rating: Series[pd.Int64Dtype] = pa.Field(nullable=True)

    @pa.check("rs_rating", name="rs_rating_must_be_nullable_int64")
    @classmethod
    def _rs_rating_dtype(cls, series: pd.Series) -> bool:
        """Enforce pd.Int64Dtype (nullable) — not int64 (Pitfall 9)."""
        return series.dtype == pd.Int64Dtype()

    class Config:
        strict = True
        coerce = False


class RankingSnapshotSchema(pa.DataFrameModel):
    """Daily ranking snapshot — full universe with composite scores and ranks.

    Written by publishers/snapshot.py via persistence.write_snapshot_atomic.
    Used by Phase 5 backtest harness for no-look-ahead reproduction.
    Schema enforced eagerly at the write boundary (D-16 validation policy).
    """

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rank: Series[pd.Int64Dtype] = pa.Field(ge=1, nullable=True)
    composite_score: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=True)
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
    pivot_zone: Series[str] = pa.Field(
        isin=["in-zone", "chase, skip", "unknown"], nullable=False
    )
    regime_state: Series[str] = pa.Field(
        isin=["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"],
        nullable=False,
    )
    regime_score: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)

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
    pattern_diagnostics: Series[str] = pa.Field(nullable=False)  # JSON-encoded dict (Pitfall 8)
    breakout_strength: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)
    days_to_next_earnings: Series[pd.Int64Dtype] = pa.Field(ge=0, nullable=True)
    crossed_52w_high_within_60d: Series[bool] = pa.Field(nullable=False)
    insider_cluster_buy: Series[bool] = pa.Field(nullable=False)
    earnings_in_3d_warn: Series[bool] = pa.Field(nullable=False)
    eps_knowable_from: Series[str] = pa.Field(nullable=True)  # ISO YYYY-MM-DD; empty when fundamentals row missing (W11)

    class Config:
        strict = True
        coerce = False


# --- Phase 6 schemas (D-05, D-12, D-13b, D-19) -------------------------------


class FundamentalsSchema(pa.DataFrameModel):
    """Per-ticker fundamentals row (EPS history + upcoming earnings).

    Written by data/fundamentals.py via persistence.write_fundamentals_atomic
    (Plan 06-03 lands the writer). Pre-filtered at read time by
    persistence.read_fundamentals(as_of_date) which enforces D-13b's 45-day
    knowable_from gate — signals/canslim.py consumes the pre-filtered view
    and structurally cannot violate the lag (architecture-test D-23).
    """

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    fiscal_quarter_end: Series[pd.Timestamp] = pa.Field(nullable=False)
    eps_actual: Series[float] = pa.Field(nullable=True)
    eps_yoy_growth: Series[float] = pa.Field(nullable=True)
    knowable_from: Series[pd.Timestamp] = pa.Field(nullable=False)
    next_earnings_date: Series[pd.Timestamp] = pa.Field(nullable=True)
    next_earnings_hour: Series[str] = pa.Field(
        isin=["bmo", "amc", "dmh", "unknown"], nullable=False
    )
    source: Series[str] = pa.Field(isin=["finnhub", "yfinance"], nullable=False)
    ingested_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False


class InsiderSchema(pa.DataFrameModel):
    """Per-Form-4 insider transaction row.

    Used as the DataFrame view validated BEFORE the SQLite INSERT in
    data/insider.py (Plan 06-03). The SQLite schema (D-10) is the actual
    storage; this pandera class is the eager-validation contract enforced
    at the write boundary.
    """

    filing_id: Series[str] = pa.Field(nullable=False, unique=True)
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    insider: Series[str] = pa.Field(nullable=False)
    transaction_date: Series[pd.Timestamp] = pa.Field(nullable=False)
    type: Series[str] = pa.Field(isin=["BUY", "SELL"], nullable=False)
    shares: Series[float] = pa.Field(ge=0, nullable=False)
    value_usd: Series[float] = pa.Field(ge=0, nullable=False)
    ingested_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False


class PatternAuditSchema(pa.DataFrameModel):
    """Per-leg pattern audit row (VCP contractions + flag bars).

    Written by data/pattern_audit/YYYY-MM-DD.parquet via
    persistence.write_pattern_audit_atomic (Plan 06-02 lands the writer).
    Gitignored per D-05.
    """

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    snapshot_date: Series[pd.Timestamp] = pa.Field(nullable=False)
    pattern_type: Series[str] = pa.Field(isin=["vcp", "flag"], nullable=False)
    leg_idx: Series[pd.Int64Dtype] = pa.Field(ge=0, nullable=False)
    start_date: Series[pd.Timestamp] = pa.Field(nullable=False)
    end_date: Series[pd.Timestamp] = pa.Field(nullable=False)
    high: Series[float] = pa.Field(gt=0, nullable=False)
    low: Series[float] = pa.Field(gt=0, nullable=False)
    depth: Series[float] = pa.Field(ge=0, le=1, nullable=False)
    avg_volume: Series[float] = pa.Field(ge=0, nullable=False)

    class Config:
        strict = True
        coerce = False


# --- Validation helpers (D-16) -----------------------------------------------


def validate_at_write(schema_cls: type[pa.DataFrameModel], df: pd.DataFrame) -> pd.DataFrame:
    """Eager validation (lazy=False): fail on first error. Use at write boundary."""
    return schema_cls.validate(df, lazy=False)


def validate_at_read(schema_cls: type[pa.DataFrameModel], df: pd.DataFrame) -> pd.DataFrame:
    """Lazy validation (lazy=True): collect all errors. Use at read boundary."""
    return schema_cls.validate(df, lazy=True)


# --- Atomic-write primitive (D-11) -------------------------------------------


def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Write `df` to `target` atomically (POSIX same-filesystem rename).

    The tempfile MUST be in the same directory as `target` so os.replace() is
    a same-filesystem rename, which is the only POSIX-atomic primitive
    (RESEARCH.md Pitfall 7). A crash mid-write leaves the .tmp behind but
    never a half-written `target`.
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


# --- Path-component safety helper --------------------------------------------


def _assert_safe_ticker(ticker: str) -> None:
    """Refuse path-traversal-style ticker strings before path construction.

    Defense in depth; UniverseSchema's str_matches regex already constrains the
    canonical universe, but writers may be invoked with arbitrary inputs in
    tests or future debug paths. RESEARCH.md Security Domain Recommendation 1.
    """
    if "/" in ticker or "\\" in ticker or ".." in ticker:
        raise ValueError(f"Unsafe ticker for path construction: {ticker!r}")


def _assert_safe_snapshot_date(snapshot_date: str) -> None:
    """Path-traversal defense: snapshot_date must match strict YYYY-MM-DD.

    T-4-01 mitigation: refuse anything other than `YYYY-MM-DD` before path
    construction. Mirrors _assert_safe_ticker's raise-on-bad-input shape.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", snapshot_date):
        raise ValueError(
            f"Unsafe snapshot_date for path construction: {snapshot_date!r}"
        )


def _ohlcv_dir() -> Path:
    """Resolve the OHLCV cache directory, with a hard-coded fallback for the
    Wave-1 race against 02-02 (which adds OHLCV_CACHE_DIR to Settings).

    Once 02-02 lands the field, getattr returns the pydantic default
    (Path('data/ohlcv')); the fallback is identical so behavior is stable.
    """
    s: Any = get_settings()
    return Path(getattr(s, "OHLCV_CACHE_DIR", "data/ohlcv"))


def _universe_dir() -> Path:
    """Same pattern as _ohlcv_dir for the universe cache."""
    s: Any = get_settings()
    return Path(getattr(s, "UNIVERSE_CACHE_DIR", "data/universe"))


def _macro_dir() -> Path:
    """Resolve the macro cache directory, with a hard-coded fallback for cross-wave safety."""
    s: Any = get_settings()
    return Path(getattr(s, "MACRO_CACHE_DIR", "data/macro"))


def _rs_snapshot_dir() -> Path:
    """Resolve the RS snapshot directory, with a hard-coded fallback for cross-wave safety."""
    s: Any = get_settings()
    return Path(getattr(s, "RS_SNAPSHOT_DIR", "data/rs_snapshots"))


def _snapshot_dir() -> Path:
    """Resolve the daily ranking-snapshot directory, with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "SNAPSHOT_DIR", "data/snapshots"))


def _fundamentals_dir() -> Path:
    """Resolve the fundamentals cache directory (Phase 6 D-09), with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "FUNDAMENTALS_CACHE_DIR", "data/fundamentals"))


def _insider_db_path() -> Path:
    """Resolve the insider Form 4 SQLite path (Phase 6 D-08/D-10), with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "INSIDER_CACHE_PATH", "data/insider/form4.sqlite"))


def _pattern_audit_dir() -> Path:
    """Resolve the per-leg pattern audit directory (Phase 6 D-05), with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "PATTERN_AUDIT_DIR", "data/pattern_audit"))


# --- Public writers (eager validation + atomic write) ------------------------


def write_universe_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write a universe snapshot to data/universe/<date>.parquet."""
    validated = validate_at_write(UniverseSchema, df)
    target = _universe_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("snapshot_written", path=str(target), n_rows=len(validated))
    return target


def write_ohlcv_atomic(ticker: str, df: pd.DataFrame) -> Path:
    """Validate (single-ticker shape) + atomically write to data/ohlcv/<TICKER>/prices.parquet.

    Single-ticker DataFrame validation: caller passes a DataFrame indexed by
    DatetimeIndex (no ticker level). We add the ticker level here, validate
    against OhlcvPanelSchema, and persist the wide form (DatetimeIndex only)
    to disk — read_panel rebuilds the MultiIndex when stitching.
    """
    _assert_safe_ticker(ticker)
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            f"write_ohlcv_atomic({ticker}): expected DatetimeIndex, got {type(df.index)}"
        )
    # Build a temporary MultiIndex (ticker, date) view for schema validation.
    panel_view = df.assign(ticker=ticker).set_index("ticker", append=True).reorder_levels([1, 0])
    panel_view.index.names = ["ticker", "date"]
    validate_at_write(OhlcvPanelSchema, panel_view)
    target = _ohlcv_dir() / ticker / "prices.parquet"
    _write_parquet_atomic(df, target)
    return target


def write_splits_atomic(ticker: str, df: pd.DataFrame) -> Path:
    """Validate + atomically write data/ohlcv/<TICKER>/splits.parquet.

    Empty case: caller passes the zero-row DataFrame returned by
    make_empty_splits(); SplitsSchema accepts an empty DataFrame whose dtypes
    match because coerce=False does not fight an empty index.
    """
    _assert_safe_ticker(ticker)
    validate_at_write(SplitsSchema, df)
    target = _ohlcv_dir() / ticker / "splits.parquet"
    _write_parquet_atomic(df, target)
    return target


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


def write_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write a ranking snapshot to data/snapshots/<date>.parquet.

    Eager validation (D-16): a malformed row aborts loud at the write boundary
    rather than corrupting the audit trail Phase 5 backtest depends on.
    """
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
        raise ValueError(
            f"unknown macro series {series_name!r}; expected one of {sorted(_MACRO_SCHEMAS)}"
        )
    schema = _MACRO_SCHEMAS[series_name]
    validated = validate_at_write(schema, df)
    target = _macro_dir() / f"{series_name}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("macro_snapshot_written", series=series_name, path=str(target), n_rows=len(validated))
    return target


def make_empty_splits() -> pd.DataFrame:
    """Construct the canonical zero-row splits DataFrame.

    Resolves RESEARCH.md Open Question 3: explicit float64 columns +
    DatetimeIndex named 'date'.
    """
    return pd.DataFrame(
        {
            "ratio": pd.Series([], dtype="float64"),
            "dividend": pd.Series([], dtype="float64"),
        },
        index=pd.DatetimeIndex([], name="date"),
    )


# --- Public readers (lazy validation) ----------------------------------------


def read_universe(snapshot_date: str) -> pd.DataFrame:
    """Read + lazy-validate the universe snapshot at the given ISO date."""
    path = _universe_dir() / f"{snapshot_date}.parquet"
    df = pd.read_parquet(path)
    return validate_at_read(UniverseSchema, df)


def read_universe_latest() -> list[str]:
    """Return tickers from the most recent universe snapshot.

    Walks ``_universe_dir()`` for the lexicographically-largest
    ``YYYY-MM-DD.parquet`` (ISO-date filenames sort correctly). Returns the
    validated ``ticker`` column as a list. Raises ``FileNotFoundError`` if no
    snapshot exists yet (callers should treat this as a hard error: run
    ``make data`` first).

    Used by Plan 06-03's ``data.fundamentals.refresh_fundamentals(today)``
    when the ``tickers`` argument is ``None`` (closes the ergonomics gap
    surfaced by checker B1 — single source of truth for the active universe
    at the data layer).
    """
    base = _universe_dir()
    if not base.exists():
        raise FileNotFoundError(
            f"read_universe_latest: universe dir does not exist: {base}"
        )
    candidates = sorted(base.glob("*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            f"read_universe_latest: no universe snapshot in {base}"
        )
    latest = candidates[-1]
    snapshot_date = latest.stem  # YYYY-MM-DD
    df = read_universe(snapshot_date)
    return df["ticker"].astype(str).tolist()


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
    """Read + lazy-validate data/macro/spy.parquet; returns empty schema-shaped frame if missing."""
    path = _macro_dir() / "spy.parquet"
    if not path.exists():
        return pd.DataFrame(
            {
                "open": pd.Series([], dtype="float64"),
                "high": pd.Series([], dtype="float64"),
                "low": pd.Series([], dtype="float64"),
                "close": pd.Series([], dtype="float64"),
                "volume": pd.Series([], dtype="int64"),
            },
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(MacroOhlcvSchema, df)


def read_macro_qqq() -> pd.DataFrame:
    """Read + lazy-validate data/macro/qqq.parquet; returns empty schema-shaped frame if missing."""
    path = _macro_dir() / "qqq.parquet"
    if not path.exists():
        return pd.DataFrame(
            {
                "open": pd.Series([], dtype="float64"),
                "high": pd.Series([], dtype="float64"),
                "low": pd.Series([], dtype="float64"),
                "close": pd.Series([], dtype="float64"),
                "volume": pd.Series([], dtype="int64"),
            },
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(MacroOhlcvSchema, df)


def read_macro_vix() -> pd.DataFrame:
    """Read + lazy-validate data/macro/vix.parquet; returns empty schema-shaped frame if missing."""
    path = _macro_dir() / "vix.parquet"
    if not path.exists():
        return pd.DataFrame(
            {"close": pd.Series([], dtype="float64")},
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(VixSchema, df)


def read_macro_yields() -> pd.DataFrame:
    """Read + lazy-validate data/macro/yields.parquet; returns empty frame if missing."""
    path = _macro_dir() / "yields.parquet"
    if not path.exists():
        return pd.DataFrame(
            {
                "dgs2": pd.Series([], dtype="float64"),
                "dgs10": pd.Series([], dtype="float64"),
                "t10y2y": pd.Series([], dtype="float64"),
            },
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(YieldsSchema, df)


def read_macro_nyad() -> pd.DataFrame:
    """Read + lazy-validate data/macro/nyad.parquet; returns empty frame if missing."""
    path = _macro_dir() / "nyad.parquet"
    if not path.exists():
        return pd.DataFrame(
            {
                "advances": pd.Series([], dtype="int64"),
                "declines": pd.Series([], dtype="int64"),
                "ad_line": pd.Series([], dtype="int64"),
            },
            index=_EMPTY_DT_INDEX,
        )
    df = pd.read_parquet(path)
    return validate_at_read(NyadMacroSchema, df)


def read_splits(ticker: str) -> pd.DataFrame:
    """Read + lazy-validate the splits ledger for a single ticker.

    Returns the empty-but-schema-preserved DataFrame when the ticker has had
    no corporate actions in the cached window.
    """
    _assert_safe_ticker(ticker)
    path = _ohlcv_dir() / ticker / "splits.parquet"
    df = pd.read_parquet(path)
    return validate_at_read(SplitsSchema, df)


def read_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Phase 3 entrypoint. Joins the universe Parquet at `snapshot_date` with
    each ticker's prices.parquet, returning a long-format MultiIndex
    DataFrame validated lazily.

    Tickers in the universe but missing from data/ohlcv/ (i.e., dropped from
    the universe per D-09 frozen-cache policy after a delisting OR not yet
    backfilled) are SKIPPED with a warning event, not raised — read_panel is
    a best-effort read; the 95% gate enforced by the CLI is what guards
    coverage.

    Test-author note (REVIEW IN-01, iter 2):
        The low-coverage gate below reads `UNIVERSE_HEALTH_THRESHOLD` via
        `get_settings()`, which is decorated with `@lru_cache(maxsize=1)`
        in config.py. Tests that monkeypatch `UNIVERSE_HEALTH_THRESHOLD`
        in the environment AFTER any prior code path has already called
        `get_settings()` will see the stale cached value here. To force
        re-read, call `get_settings.cache_clear()` in the test fixture
        before invoking `read_panel`. This caveat applies to every
        settings field read through `get_settings()` in this module.
    """
    snapshot_str = str(snapshot_date)[:10] if not isinstance(snapshot_date, str) else snapshot_date
    universe = read_universe(snapshot_str)
    frames: list[pd.DataFrame] = []
    for t in universe["ticker"]:
        prices_path = _ohlcv_dir() / t / "prices.parquet"
        if not prices_path.exists():
            log.warning("read_panel_missing_ticker", ticker=t, snapshot_date=snapshot_str)
            continue
        prices = pd.read_parquet(prices_path)
        prices = prices.rename(columns=str.lower)
        prices["ticker"] = t
        prices = prices.set_index("ticker", append=True).reorder_levels([1, 0])
        frames.append(prices)

    # REVIEW WR-02 (second): aggregate coverage check at read time. The 95%
    # health gate is enforced inside refresh-ohlcv, but a subsequent score or
    # report run on a partially-backfilled cache would otherwise proceed
    # silently with low coverage. Re-validate here so downstream pipelines
    # fail loud rather than emit a report on a tiny universe.
    # REVIEW IN-02 (iter 2): raise StaleOrEmptyError (not bare RuntimeError)
    # so the CLI's broad `except Exception` logs `error_type=StaleOrEmptyError`,
    # matching the existing data-quality fail-loud convention used by
    # data/ohlcv.py and data/stooq.py for log-grep consistency.
    n_universe = len(universe)
    n_loaded = len(frames)
    threshold = get_settings().UNIVERSE_HEALTH_THRESHOLD
    if n_universe > 0 and n_loaded / n_universe < threshold:
        log.error(
            "read_panel_low_coverage",
            n_universe=n_universe,
            n_loaded=n_loaded,
            ratio=n_loaded / n_universe,
            threshold=threshold,
        )
        raise StaleOrEmptyError(
            f"read_panel: only {n_loaded}/{n_universe} tickers loaded — "
            "re-run refresh-ohlcv to fix coverage"
        )

    if not frames:
        # Construct an empty panel with the right MultiIndex shape.
        panel = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.MultiIndex.from_arrays(
                [pd.Index([], dtype=str), pd.DatetimeIndex([])],
                names=["ticker", "date"],
            ),
        )
    else:
        panel = pd.concat(frames)
        panel.index.names = ["ticker", "date"]
    return validate_at_read(OhlcvPanelSchema, panel)
