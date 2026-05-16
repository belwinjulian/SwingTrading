"""Shared pytest configuration and fixtures.

Phase 1 ships only the fixtures Phase 1 tests need. Phase 2 adds 10 synthetic
fixtures consumed by tests/test_data_universe.py, tests/test_data_ohlcv.py,
tests/test_data_stooq.py, tests/test_persistence.py, and the extended
tests/test_cli_smoke.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# --- Reference date used by the OHLCV fixtures (deterministic) --------------

# Pinned to a recent weekday so business-day arithmetic is stable across
# CI runs. A fixed value also makes the fixtures hashable for session scope.
_REF_DATE = pd.Timestamp("2026-04-30")


# --- Phase 1 fixtures (KEEP unchanged) --------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root (parent of `tests/`)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_screener(repo_root: Path) -> Path:
    """Absolute path to src/screener/."""
    return repo_root / "src" / "screener"


# --- Phase 2 OHLCV fixtures -------------------------------------------------


@pytest.fixture(scope="session")
def synthetic_ohlcv_valid_df() -> pd.DataFrame:
    """252 daily bars passing all 4 D-08 invariants.

    Invariants: non-empty, recent, monotonic, no null close.
    """
    idx = pd.bdate_range(end=_REF_DATE, periods=252)
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_empty_df() -> pd.DataFrame:
    """Empty OHLCV frame — the silent-empty-from-yfinance simulation."""
    return pd.DataFrame(
        {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []},
        index=pd.DatetimeIndex([], name="Date"),
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_stale_df() -> pd.DataFrame:
    """Last bar 10 business days before _REF_DATE — fails the recency invariant."""
    end_stale = _REF_DATE - pd.tseries.offsets.BDay(10)
    idx = pd.bdate_range(end=end_stale, periods=252)
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_null_close_df() -> pd.DataFrame:
    """One NaN in Close — fails the null-close invariant."""
    idx = pd.bdate_range(end=_REF_DATE, periods=252)
    close = np.full(len(idx), 100.5)
    close[5] = np.nan
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": close,
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_non_monotonic_df() -> pd.DataFrame:
    """DatetimeIndex with the last 5 bars in random order — fails monotonicity."""
    idx = list(pd.bdate_range(end=_REF_DATE, periods=252))
    # Shuffle the last 5 bars deterministically.
    idx[-5:] = [idx[-1], idx[-3], idx[-5], idx[-2], idx[-4]]
    didx = pd.DatetimeIndex(idx)
    return pd.DataFrame(
        {
            "Open": np.full(len(didx), 100.0),
            "High": np.full(len(didx), 101.0),
            "Low": np.full(len(didx), 99.0),
            "Close": np.full(len(didx), 100.5),
            "Volume": np.full(len(didx), 1_000_000, dtype="int64"),
        },
        index=didx,
    )


# --- Phase 2 iShares CSV fixtures (BYTES, encoded UTF-8 with BOM) ----------


def _make_ishares_csv_bytes(
    n_equity_rows: int,
    sector_override_for_first: str | None = None,
) -> bytes:
    """Build an iShares-shaped CSV. Replicates the verified live structure:
    9 metadata lines, blank, header, then `n_equity_rows` equity rows, then
    a couple of cash/derivative rows, then trailer text.
    """
    metadata = "\n".join(f"Field {i},Value {i}" for i in range(9))
    blank = ""
    header = (
        "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,"
        "Quantity,Price,Location,Exchange,Currency"
    )
    sectors = [
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
    ]
    rows: list[str] = []
    for i in range(n_equity_rows):
        ticker = f"AA{i:04d}"
        sector = sectors[i % len(sectors)]
        if i == 0 and sector_override_for_first is not None:
            sector = sector_override_for_first
        rows.append(
            f"{ticker},Company {i},{sector},Equity,1000.00,0.10,1000.00,10,100.00,US,NASDAQ,USD"
        )
    cash_rows = [
        "XTSLA,BLK CSH,-,Cash,500.00,0.05,500.00,500,1.00,US,-,USD",
        "USD,USD CASH,-,Cash,250.00,0.03,250.00,250,1.00,US,-,USD",
    ]
    trailer = 'The content of this CSV is provided "as is".'
    body = (
        metadata
        + "\n"
        + blank
        + "\n"
        + header
        + "\n"
        + "\n".join(rows)
        + "\n"
        + "\n".join(cash_rows)
        + "\n"
        + trailer
        + "\n"
    )
    # UTF-8 with BOM (matches utf-8-sig encoding the live feed uses).
    bom = bytes([0xEF, 0xBB, 0xBF])  # UTF-8 BOM matches utf-8-sig encoding
    return bom + body.encode("utf-8")  # UTF-8 BOM prefix matches utf-8-sig


@pytest.fixture(scope="session")
def synthetic_ishares_csv_bytes() -> bytes:
    """1010-row valid iShares-shaped CSV that passes parse + sanity_check."""
    return _make_ishares_csv_bytes(n_equity_rows=1005)


@pytest.fixture(scope="session")
def synthetic_ishares_csv_undersized_bytes() -> bytes:
    """500-row variant — sanity_check raises ValueError (count outside [800, 1100])."""
    return _make_ishares_csv_bytes(n_equity_rows=500)


@pytest.fixture(scope="session")
def synthetic_ishares_csv_bad_sector_bytes() -> bytes:
    """First row has Sector='Bogus Sector' — sanity_check raises ValueError."""
    return _make_ishares_csv_bytes(n_equity_rows=1005, sector_override_for_first="Bogus Sector")


# --- Phase 2 sentinel-mismatch fixture --------------------------------------


@pytest.fixture(scope="session")
def synthetic_split_mismatch_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A (cached, refetched) pair where the sentinel close differs by ~50%.

    Cached has Close[-1] = 200.0; refetched has the same date but Close = 100.0
    (simulating a 2:1 split that retroactively halved historical adjusted prices).
    """
    idx = pd.bdate_range(end=_REF_DATE, periods=10)
    cached = pd.DataFrame(
        {
            "Open": np.full(len(idx), 199.0),
            "High": np.full(len(idx), 201.0),
            "Low": np.full(len(idx), 198.0),
            "Close": np.full(len(idx), 200.0),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )
    # Refetched starts at the same last_cached_date and goes 5 bars forward.
    new_idx = pd.bdate_range(start=idx[-1], periods=5)
    refetched = pd.DataFrame(
        {
            "Open": np.full(len(new_idx), 99.0),
            "High": np.full(len(new_idx), 101.0),
            "Low": np.full(len(new_idx), 98.0),
            "Close": np.full(len(new_idx), 100.0),  # half of cached — sentinel mismatch
            "Volume": np.full(len(new_idx), 2_000_000, dtype="int64"),
        },
        index=new_idx,
    )
    return cached, refetched


# --- Phase 2 Stooq-shaped fixture -------------------------------------------


@pytest.fixture(scope="session")
def synthetic_stooq_descending_df() -> pd.DataFrame:
    """Stooq-shape DataFrame: descending DatetimeIndex + PascalCase columns."""
    idx = pd.bdate_range(end=_REF_DATE, periods=20)
    df = pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )
    return df.sort_index(ascending=False)


# --- Phase 3 indicator + regime fixtures -----------------------------------
# Populated by Plans 03-03, 03-04, 03-05. This section header is a Wave 0
# anchor; downstream plans add fixtures (synthetic_short_history_panel,
# synthetic_multi_ticker_panel, synthetic_spy_2008q4, synthetic_vix_panic)
# without re-touching the prior phase blocks.


@pytest.fixture(scope="session")
def synthetic_short_history_panel() -> pd.DataFrame:
    """50-bar single-ticker panel — exercises SMA200 NaN warmup path (D-08).
    Ticker = SHORT; close starts at 100, drifts up by 0.1/day."""
    n = 50
    idx = pd.MultiIndex.from_product(
        [["SHORT"], pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)],
        names=["ticker", "date"],
    )
    close = np.linspace(100.0, 100.0 + 0.1 * (n - 1), n)
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_multi_ticker_panel() -> pd.DataFrame:
    """5 tickers x 260 business days (>252d so RS rating is defined for all).
    Tickers: AAA, BBB, CCC, DDD, EEE — distinct returns trajectories."""
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    n = 260
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    frames = []
    for i, t in enumerate(tickers):
        # Each ticker has a different drift — produces distinguishable RS values.
        drift = 0.001 * (i + 1)
        close = 100.0 * np.cumprod(1.0 + np.full(n, drift))
        idx = pd.MultiIndex.from_product([[t], dates], names=["ticker", "date"])
        frames.append(pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n, 1_000_000, dtype="int64"),
            },
            index=idx,
        ))
    return pd.concat(frames).sort_index()


# --- Phase 5 backtest harness fixtures (Plan 05-00) --------------------------


@pytest.fixture(scope="session")
def synthetic_ohlcv_panel() -> pd.DataFrame:
    """1300 business days x 3 tickers mean-zero GBM OHLCV in the panel shape
    `persistence.read_panel()` returns. Pinned seed=42 (per-ticker shift seed+i);
    loc=0.0 drift (mean-zero) satisfies the FND-04 no-look-ahead test thresholds
    (`abs(total_return) < 0.50` shifted; `total_return > 1.00` unshifted)
    with margin — 10-seed verification documented in 05-RESEARCH.md §B Q5.

    Span rationale (REVISED 2026-05-16 iter 3, C-1 fix): 1300 bdays starting
    2019-01-01 covers ≈ 5.15 calendar years (ends ≈ 2024-01-XX) — large enough
    for `walk_forward_windows(IS=3yr, OOS=1yr, slide=1yr)` to produce ≥2
    complete windows:
        Win 1: IS 2019-01-01..2021-12-31 | OOS 2022-01-01..2022-12-31
        Win 2: IS 2020-01-01..2022-12-31 | OOS 2023-01-01..2023-12-31
    Earlier iter-2 attempt (1008 bars starting 2020-01-01, ending ~2023-11-15)
    was the C-1 defect: `start + 4yr = 2024-01-01 > 2023-11-15` → ZERO complete
    windows → mutation test trivially passed (total_return = 0.0 for both
    lookahead modes), smuggling B-2 back in. Iter 3 fix: extend start by 1 year
    and grow span to ≥5 calendar years.

    Multi-ticker (AAA/BBB/CCC) gives the per-ticker slippage panel (D-11 tiers)
    real shape to test — plan 05-01's `_build_slippage_panel` unstacks by ticker.

    Schema matches `persistence.read_panel()`:
      - MultiIndex (ticker, date), names=["ticker", "date"]
      - Columns: open, high, low, close (float64); volume (int64)
      - 1300 business days starting 2019-01-01 per ticker (3 tickers x 1300 = 3900 rows)
    """
    n_bars = 1300
    tickers = ("AAA", "BBB", "CCC")
    seed_base = 42
    dates = pd.bdate_range(start="2019-01-01", periods=n_bars)
    frames: list[pd.DataFrame] = []
    for i, ticker in enumerate(tickers):
        rng = np.random.default_rng(seed_base + i)
        log_returns = rng.normal(loc=0.0, scale=0.012, size=n_bars)
        close = 100.0 * np.exp(np.cumsum(log_returns))
        open_ = close * (1 + rng.normal(0, 0.002, n_bars))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n_bars)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n_bars)))
        volume = rng.integers(500_000, 2_000_000, n_bars, dtype="int64")
        idx = pd.MultiIndex.from_product([[ticker], dates], names=["ticker", "date"])
        frames.append(
            pd.DataFrame(
                {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
                index=idx,
            )
        )
    return pd.concat(frames).sort_index()


# --- Phase 3 regime fixtures (Plan 03-04) ------------------------------------


@pytest.fixture(scope="session")
def synthetic_spy_with_dist_days() -> pd.DataFrame:
    """SPY OHLCV with exactly 4 strict-IBD distribution days in the last 25
    sessions — used by test_distribution_day_idiom.

    Distribution day = close down >0.2% AND volume > prev_volume.
    """
    n = 50
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    close = np.full(n, 100.0)
    volume = np.full(n, 1_000_000, dtype="int64")

    # Inject 4 distribution days at indices 30, 35, 40, 45 (within last 25 sessions
    # of index n-1=49; window covers indices 25..49).
    for i in (30, 35, 40, 45):
        close[i] = close[i - 1] * 0.99   # 1% drop > 0.2%
        volume[i] = int(volume[i - 1] * 1.5)  # higher volume
    return pd.DataFrame(
        {
            "open": close, "high": close * 1.01, "low": close * 0.98,
            "close": close, "volume": volume,
        },
        index=pd.DatetimeIndex(idx, name="date"),
    )


@pytest.fixture(scope="session")
def synthetic_vix_calm() -> pd.DataFrame:
    """VIX series with close always at 15 (calm market — Confirmed Uptrend territory)."""
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=50)
    return pd.DataFrame(
        {"close": [15.0] * 50},
        index=pd.DatetimeIndex(idx, name="date"),
    )


# --- Phase 4 fixtures (Plans 04-01 through 04-05) ---------------------------


@pytest.fixture(scope="session")
def synthetic_panel_for_trend_template(synthetic_multi_ticker_panel: pd.DataFrame) -> pd.DataFrame:
    """Multi-ticker panel with all Trend Template input columns populated.

    Builds on the Phase 3 multi-ticker fixture by running the full Phase 4
    build_panel chain (sma + atr + adr + obv + dryup + rs + high_52w +
    low_52w). Tickers have >=260 bars; high_52w/low_52w require 252 bars so
    values at the tail are non-NaN for all 5 tickers (260 > 252).
    Used by tests/test_signals_minervini.py.
    """
    from screener.indicators.relative_strength import rs_panel
    from screener.indicators.trend import (
        high_52w_panel,
        low_52w_panel,
        sma_panel,
    )
    from screener.indicators.volatility import adr_pct_panel, atr_panel
    from screener.indicators.volume import dryup_ratio_panel, obv_panel

    panel = synthetic_multi_ticker_panel.copy()
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))
    panel = atr_panel(panel, length=14)
    panel = adr_pct_panel(panel, length=20)
    panel = obv_panel(panel)
    panel = dryup_ratio_panel(panel, length=50)
    panel = rs_panel(panel)
    panel = high_52w_panel(panel, length=252)
    panel = low_52w_panel(panel, length=252)
    return panel


@pytest.fixture(scope="session")
def synthetic_scored_panel(synthetic_panel_for_trend_template: pd.DataFrame) -> pd.DataFrame:
    """Post-composite panel cross-section with composite_score / pivot_zone /
    regime_state / regime_score columns populated. Used by publisher tests
    (tests/test_publishers_report.py, tests/test_publishers_snapshot.py).

    Returns a single-date cross-section (one row per ticker) — matches the
    shape consumed by publishers/report.write_report and persistence
    .write_snapshot_atomic.

    NOTE: Imports from screener.signals.minervini and screener.signals.composite
    are lazy (inside the fixture body) so collection-time does not fail when
    these modules do not yet exist (Plans 04-02/04-03 land them).
    """
    from screener.publishers.report import _add_publisher_columns
    from screener.signals.composite import DEFAULT_WEIGHTS, score
    from screener.signals.minervini import passes_trend_template

    panel = passes_trend_template(synthetic_panel_for_trend_template)
    panel = score(panel, DEFAULT_WEIGHTS)

    # Take the latest cross-section — one row per ticker.
    latest_date = panel.index.get_level_values("date").max()
    cross = panel.xs(latest_date, level="date").copy()

    # REVIEW WR-06: delegate pivot/regime/rank column derivation to the
    # production helper so this fixture cannot silently diverge from
    # publishers/report's behavior (e.g., after CR-05's sign-convention fix).
    regime_row = pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82})
    cross = _add_publisher_columns(cross, regime_row)
    return cross


@pytest.fixture(scope="function")
def synthetic_high_pass_rate_panel(
    synthetic_panel_for_trend_template: pd.DataFrame,
) -> pd.DataFrame:
    """A panel where ~30% of tickers pass the Trend Template — triggers
    D-08 hard-fail when paired with regime_state == 'Correction'.

    Used by tests/test_publishers_pipeline.py and the integration test
    in tests/test_cli_smoke.py for the data-quality gate.

    Function-scope (not session) because tests may mutate the frame in
    the failure-injection path.

    NOTE: Import from screener.signals.minervini is lazy so collection-time
    does not fail when the module does not yet exist (Plan 04-02 lands it).
    """
    from screener.signals.minervini import passes_trend_template

    panel = passes_trend_template(synthetic_panel_for_trend_template)
    # The fixture's pass rate depends on the synthetic data construction
    # in synthetic_multi_ticker_panel. If the existing Phase 3 fixture
    # already produces a high-pass-rate uptrend pattern across all tickers
    # this is a no-op. Otherwise tests use this fixture's `passes_trend_template`
    # column directly and inject a regime_state == 'Correction' for D-08.
    return panel
