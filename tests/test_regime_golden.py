"""REG-04 golden-file regime tests.

Each of the three canonical historical corrections (2008-Q4, 2020-Q1, 2022-H1)
must classify at least one date in its window as 'Correction'. Tests use
synthetic SPY/VIX series with deterministic distribution-day and SMA-break
positions per RESEARCH Open Question 4 recommendation.

Note: fixtures and helpers are defined module-locally (not in conftest) to keep
Plan 03-05's files_modified orthogonal to Plan 03-04's.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from screener.regime import compute_for_date


def _make_synthetic_spy_for_correction(
    start: str,
    end: str,
    sma_break_dates: list[str],
) -> pd.DataFrame:
    """Build a synthetic SPY OHLCV series whose close crosses below 200d SMA
    at known dates and has injected distribution days. Deterministic — used
    by REG-04 golden-file tests.
    """
    # Pre-pad with 250 calendar days of stable price so SMA200 is well-defined
    # at the start of the test window.
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    idx = pd.bdate_range(start=pad_start, end=end)
    close = np.full(len(idx), 100.0)
    volume = np.full(len(idx), 1_000_000, dtype="int64")
    for d in sma_break_dates:
        ts = pd.Timestamp(d)
        if ts in idx:
            i = idx.get_loc(ts)
            close[i:] *= 0.7  # 30% drop persisting forward
    # Inject 10 strict-IBD distribution days uniformly across the post-break window.
    if sma_break_dates:
        first_break = pd.Timestamp(sma_break_dates[0])
        post = idx[idx >= first_break]
        if len(post) >= 12:
            for offset in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19):
                if offset < len(post):
                    j = idx.get_loc(post[offset])
                    if j > 0:
                        close[j] = close[j - 1] * 0.99  # 1% drop > 0.2%
                        volume[j] = int(volume[j - 1] * 1.5)  # higher volume
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": volume,
        },
        index=pd.DatetimeIndex(idx, name="date"),
    )


def _make_synthetic_vix_for_correction(
    start: str,
    end: str,
    panic_dates: list[str],
    panic_level: float = 35.0,
) -> pd.DataFrame:
    """VIX with calm baseline (15) + panic spikes (>=30) on specified dates."""
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    idx = pd.bdate_range(start=pad_start, end=end)
    close = np.full(len(idx), 15.0)
    for d in panic_dates:
        ts = pd.Timestamp(d)
        if ts in idx:
            i = idx.get_loc(ts)
            # 5-day panic plateau
            for k in range(min(5, len(idx) - i)):
                close[i + k] = panic_level
    return pd.DataFrame(
        {"close": close},
        index=pd.DatetimeIndex(idx, name="date"),
    )


@pytest.fixture(scope="session")
def synthetic_spy_2008q4() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2008-10-01",
        end="2009-03-01",
        sma_break_dates=["2008-10-06"],
    )


@pytest.fixture(scope="session")
def synthetic_spy_2020q1() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2020-02-15",
        end="2020-04-15",
        sma_break_dates=["2020-02-25"],
    )


@pytest.fixture(scope="session")
def synthetic_spy_2022h1() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2022-01-01",
        end="2022-07-01",
        sma_break_dates=["2022-01-20"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2008q4() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2008-10-01",
        end="2009-03-01",
        panic_dates=["2008-10-10", "2008-11-20"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2020q1() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2020-02-15",
        end="2020-04-15",
        panic_dates=["2020-03-09", "2020-03-16"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2022h1() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2022-01-01",
        end="2022-07-01",
        panic_dates=["2022-02-24", "2022-06-13"],
    )


def _setup_macro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
) -> None:
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    spy_df.to_parquet(macro_dir / "spy.parquet", engine="pyarrow", index=True)
    vix_df.to_parquet(macro_dir / "vix.parquet", engine="pyarrow", index=True)


def _trivial_panel(date: pd.Timestamp, n_tickers: int = 5) -> pd.DataFrame:
    """A trivial indicator-panel with 5 tickers, all close > sma_200 (high
    breadth). Real Correction signal has to come from SPY-below-200d, VIX>=30,
    or dist-days, not breadth.
    """
    tickers = [f"TKR{i}" for i in range(n_tickers)]
    rows = []
    idx_pairs = []
    for t in tickers:
        idx_pairs.append((t, date))
        rows.append({"close": 110.0, "sma_200": 100.0})
    return pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"]),
    )


def _scan_for_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    window_start: str,
    window_end: str,
) -> bool:
    """Walk dates in [window_start, window_end] and return True on first Correction."""
    _setup_macro(tmp_path, monkeypatch, spy_df, vix_df)
    candidate_dates = [
        d for d in spy_df.index if pd.Timestamp(window_start) <= d <= pd.Timestamp(window_end)
    ]
    for d in candidate_dates:
        panel = _trivial_panel(d)
        out = compute_for_date(d, panel)
        if out["regime_state"] == "Correction":
            return True
    return False


def test_2008q4_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2008q4: pd.DataFrame,
    synthetic_vix_2008q4: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path,
        monkeypatch,
        synthetic_spy_2008q4,
        synthetic_vix_2008q4,
        "2008-10-01",
        "2009-03-01",
    )
    assert found, "2008-Q4 fixture must classify at least one date as Correction"


def test_2020q1_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2020q1: pd.DataFrame,
    synthetic_vix_2020q1: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path,
        monkeypatch,
        synthetic_spy_2020q1,
        synthetic_vix_2020q1,
        "2020-02-15",
        "2020-04-15",
    )
    assert found, "2020-Q1 fixture must classify at least one date as Correction"


def test_2022h1_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2022h1: pd.DataFrame,
    synthetic_vix_2022h1: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path,
        monkeypatch,
        synthetic_spy_2022h1,
        synthetic_vix_2022h1,
        "2022-01-01",
        "2022-07-01",
    )
    assert found, "2022-H1 fixture must classify at least one date as Correction"
