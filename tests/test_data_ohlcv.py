"""data/ohlcv.py tests (DAT-03, DAT-06, DAT-07, DAT-08).

Covers the 9 unit tests + 2 golden-file split tests + 1 combined-gate test in
02-VALIDATION.md lines 60-69, 72, 74. The two NVDA/AAPL split-ratio golden
tests are skipped at the unit-test level — they require a checked-in
fixture Parquet which is captured by the manual-only verification in
02-VALIDATION.md "Live first-run 20-year backfill". The unit-test path
covers the fetch + write codepath without requiring the live data.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from screener.data.ohlcv import (
    append_incremental,
    fetch_ohlcv,
    run_with_breaker,
)
from screener.persistence import StaleOrEmptyError

REF_DATE = date(2026, 4, 30)


# --- DAT-03: invariant gate tests ------------------------------------------


def test_fetch_all_invariants_pass(synthetic_ohlcv_valid_df: pd.DataFrame) -> None:
    with mock.patch("screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_valid_df):
        df = fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
    assert len(df) > 0
    assert "close" in df.columns or "Close" in df.columns
    # fetch_ohlcv normalizes to lowercase + names the index 'date'.
    assert df.index.name is None or df.index.name.lower() == "date"


def test_fetch_empty_raises_after_retries(synthetic_ohlcv_empty_df: pd.DataFrame) -> None:
    """5 tenacity attempts then StaleOrEmptyError. We mock yf.download
    to always return empty; tenacity will call it 5 times; reraise=True
    ensures StaleOrEmptyError surfaces (not RetryError)."""
    call_count = {"n": 0}

    def _empty(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return synthetic_ohlcv_empty_df

    with mock.patch("screener.data.ohlcv.yf.download", side_effect=_empty):
        with pytest.raises(StaleOrEmptyError, match="empty"):
            fetch_ohlcv("FAKE", "2024-01-01", REF_DATE)
    assert call_count["n"] == 5, f"Expected 5 retry attempts; got {call_count['n']}"


def test_fetch_stale_fails(synthetic_ohlcv_stale_df: pd.DataFrame) -> None:
    with mock.patch("screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_stale_df):
        with pytest.raises(StaleOrEmptyError, match="stale"):
            fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)


def test_fetch_non_monotonic_fails(synthetic_ohlcv_non_monotonic_df: pd.DataFrame) -> None:
    with (
        mock.patch(
            "screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_non_monotonic_df
        ),
        pytest.raises(StaleOrEmptyError, match="non-monotonic"),
    ):
        fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)


def test_fetch_null_close_fails(synthetic_ohlcv_null_close_df: pd.DataFrame) -> None:
    with (
        mock.patch("screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_null_close_df),
        pytest.raises(StaleOrEmptyError, match="null close"),
    ):
        fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)


# --- DAT-03: sentinel-bar refetch ------------------------------------------


def test_sentinel_mismatch_full_refetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the sentinel bar mismatches, append_incremental triggers a full re-fetch.

    We build a stale cache (last bar 5 BD before REF_DATE, Close=200). The first
    yf.download call returns a sentinel window with Close=100 (50% mismatch).
    append_incremental must detect the mismatch and trigger a second full re-fetch.
    """
    ohlcv_dir = tmp_path / "ohlcv"
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: ohlcv_dir)

    # Seed the cache with a DataFrame that is NOT up-to-date so append_incremental
    # proceeds past the early-return gate (last_cached_date >= today - 1 day).
    # Use a cache whose last bar is 5 business days before REF_DATE, with Close=200.
    # The refetched fixture returns Close=100 for the same date, triggering mismatch.
    import numpy as _np

    stale_end = pd.Timestamp(REF_DATE) - pd.tseries.offsets.BDay(5)
    stale_idx = pd.bdate_range(end=stale_end, periods=10)
    cached_lower = pd.DataFrame(
        {
            "open": _np.full(10, 199.0),
            "high": _np.full(10, 201.0),
            "low": _np.full(10, 198.0),
            "close": _np.full(10, 200.0),  # will mismatch refetched Close=100
            "volume": _np.full(10, 1_000_000, dtype="int64"),
        },
        index=pd.DatetimeIndex(stale_idx, name="date"),
    )
    cache_path = ohlcv_dir / "AAPL" / "prices.parquet"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cached_lower.to_parquet(cache_path, engine="pyarrow", index=True)

    # Also patch the settings OHLCV_CACHE_DIR so append_incremental finds the tmp cache.
    monkeypatch.setattr(
        "screener.data.ohlcv.get_settings",
        lambda: type(
            "S",
            (),
            {
                "OHLCV_CACHE_DIR": ohlcv_dir,
                "OHLCV_BACKFILL_START": "2005-01-01",
                "OHLCV_FETCH_SLEEP_MIN_S": 0.0,
                "OHLCV_FETCH_SLEEP_MAX_S": 0.0,
                "STOOQ_BREAKER_PROBE_N": 50,
                "STOOQ_BREAKER_THRESHOLD": 0.80,
            },
        )(),
    )

    # Build the two DataFrames the mock needs to return:
    # 1st call: the sentinel-window fetch — includes the last_cached_date bar
    #           with Close=100.0 (mismatches cached Close=200.0).
    # 2nd call: the full re-fetch after mismatch — full backfill with Close=100.5.
    # yf.download returns PascalCase columns; fetch_ohlcv normalizes to lowercase.
    sentinel_window_df = pd.DataFrame(
        {
            "Open": [99.0] * 6,
            "High": [101.0] * 6,
            "Low": [98.0] * 6,
            "Close": [100.0] * 6,  # 50% below cached 200.0 — forces mismatch
            "Volume": [2_000_000] * 6,
        },
        # Start at stale_end (the last cached date) through REF_DATE
        index=pd.bdate_range(start=stale_end, periods=6, name="Date"),
    )
    full_backfill_df = pd.DataFrame(
        {
            "Open": [100.0] * 252,
            "High": [101.0] * 252,
            "Low": [99.0] * 252,
            "Close": [100.5] * 252,
            "Volume": [1_000_000] * 252,
        },
        index=pd.bdate_range(end=REF_DATE, periods=252, name="Date"),
    )

    call_count = {"n": 0}

    def _yf(ticker, start, **kwargs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        # First call: sentinel-window refetch starting at last_cached_date.
        # Second call: full backfill triggered by sentinel mismatch.
        if call_count["n"] == 1:
            return sentinel_window_df.copy()
        return full_backfill_df.copy()

    with mock.patch("screener.data.ohlcv.yf.download", side_effect=_yf):
        _df, full_refetched = append_incremental("AAPL", REF_DATE)
    assert full_refetched is True, "Sentinel mismatch must trigger a full re-fetch"
    assert call_count["n"] == 2


# --- DAT-06: tenacity backoff and structured fail event --------------------


def test_tenacity_backoff_on_429(synthetic_ohlcv_valid_df: pd.DataFrame) -> None:
    """First 4 attempts raise ConnectionError; 5th returns valid -> success."""
    call_count = {"n": 0}

    def _flaky(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] < 5:
            raise ConnectionError("simulated 429")
        return synthetic_ohlcv_valid_df

    with mock.patch("screener.data.ohlcv.yf.download", side_effect=_flaky):
        df = fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
    assert call_count["n"] == 5
    assert len(df) > 0


def test_structured_log_on_fail(
    synthetic_ohlcv_empty_df: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 5-attempt yfinance failure inside run_with_breaker emits a fetch_fail event.

    src/screener/obs.py configures structlog with PrintLoggerFactory (verified
    2026-05-02 — see obs.py lines 33-39), which writes events directly to
    stdout via PrintLogger and DOES NOT route them through stdlib logging. As
    a result, pytest's caplog fixture cannot capture structlog events emitted
    by this module. Use structlog.testing.capture_logs() instead — it
    intercepts events at the bound-logger layer regardless of factory.
    """
    import structlog

    monkeypatch.setattr(
        "screener.data.ohlcv.get_settings",
        lambda: type(
            "S",
            (),
            {
                "OHLCV_CACHE_DIR": Path("/tmp/_unused"),
                "OHLCV_BACKFILL_START": "2005-01-01",
                "OHLCV_FETCH_SLEEP_MIN_S": 0.0,
                "OHLCV_FETCH_SLEEP_MAX_S": 0.0,
                "STOOQ_BREAKER_PROBE_N": 50,
                "STOOQ_BREAKER_THRESHOLD": 0.80,
            },
        )(),
    )

    def _fail_append(ticker: str, today: date) -> tuple[pd.DataFrame, bool]:
        raise StaleOrEmptyError(f"simulated failure for {ticker}")

    with mock.patch("screener.data.ohlcv.append_incremental", side_effect=_fail_append):
        with structlog.testing.capture_logs() as cap_logs:
            _yf_ok, _stooq_ok, failed = run_with_breaker(["FAKE1"], REF_DATE)
    assert "FAKE1" in failed
    # Single hard assertion: capture_logs must have recorded a fetch_fail
    # event for ticker FAKE1. No disjunctive fallback — the fixture is the
    # source of truth, and a missing event is a real bug.
    fail_events = [
        e for e in cap_logs if e.get("event") == "fetch_fail" and e.get("ticker") == "FAKE1"
    ]
    assert fail_events, (
        f"Expected at least one fetch_fail event for ticker=FAKE1; captured events: {cap_logs!r}"
    )


# --- DAT-07: circuit-breaker trip ------------------------------------------


def test_circuit_breaker_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_ohlcv_valid_df: pd.DataFrame,
) -> None:
    """49/50 first-50 yfinance failures trip the breaker; remaining 50 route through Stooq.

    We mock append_incremental (not yf.download) so we bypass tenacity's
    exponential backoff — otherwise 49 failures * 4 retries * ~8s/retry = ~1570s.
    The circuit-breaker logic lives in run_with_breaker around the append_incremental
    call, so mocking at that boundary exercises the correct code path.
    """
    ohlcv_dir = tmp_path / "ohlcv"
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: ohlcv_dir)

    monkeypatch.setattr(
        "screener.data.ohlcv.get_settings",
        lambda: type(
            "S",
            (),
            {
                "OHLCV_CACHE_DIR": ohlcv_dir,
                "OHLCV_BACKFILL_START": "2005-01-01",
                "OHLCV_FETCH_SLEEP_MIN_S": 0.0,
                "OHLCV_FETCH_SLEEP_MAX_S": 0.0,
                "STOOQ_BREAKER_PROBE_N": 50,
                "STOOQ_BREAKER_THRESHOLD": 0.80,
            },
        )(),
    )

    valid_df = synthetic_ohlcv_valid_df.rename(columns=str.lower).copy()
    valid_df.index.name = "date"

    append_calls = {"n": 0}

    def _append(ticker: str, today: date) -> tuple[pd.DataFrame, bool]:
        append_calls["n"] += 1
        # First ticker succeeds; tickers 2..50 fail with StaleOrEmptyError (49 failures).
        if append_calls["n"] != 1 and append_calls["n"] <= 50:
            raise StaleOrEmptyError(f"simulated yf failure for {ticker}")
        return valid_df.copy(), True

    # Stooq successes for tickers 50..99 (post-breaker).
    def _stooq(ticker: str, start: str | date, today: date) -> pd.DataFrame:
        return valid_df.copy()

    tickers = [f"T{i:03d}" for i in range(100)]
    with (
        mock.patch("screener.data.ohlcv.append_incremental", side_effect=_append),
        mock.patch("screener.data.ohlcv.yf.Ticker") as ticker_mock,
        mock.patch("screener.data.ohlcv.stooq_module.fetch_ohlcv", side_effect=_stooq),
    ):
        empty_actions = pd.DataFrame(index=pd.DatetimeIndex([]))
        ticker_mock.return_value.actions = empty_actions
        yf_ok, stooq_ok, _failed = run_with_breaker(tickers, REF_DATE)

    assert yf_ok <= 1, f"Expected ≤ 1 yf successes (only the first); got {yf_ok}"
    assert stooq_ok >= 40, (
        f"Expected stooq fallback to handle most of tickers 50..99; got {stooq_ok}"
    )


# --- DAT-07: combined gate counter shape -----------------------------------


def test_combined_gate_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_ohlcv_valid_df: pd.DataFrame,
) -> None:
    """run_with_breaker over 10 tickers all-yf-success -> yf_ok == 10, stooq_ok == 0, failed = []."""
    ohlcv_dir = tmp_path / "ohlcv"
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: ohlcv_dir)

    monkeypatch.setattr(
        "screener.data.ohlcv.get_settings",
        lambda: type(
            "S",
            (),
            {
                "OHLCV_CACHE_DIR": ohlcv_dir,
                "OHLCV_BACKFILL_START": "2005-01-01",
                "OHLCV_FETCH_SLEEP_MIN_S": 0.0,
                "OHLCV_FETCH_SLEEP_MAX_S": 0.0,
                "STOOQ_BREAKER_PROBE_N": 50,
                "STOOQ_BREAKER_THRESHOLD": 0.80,
            },
        )(),
    )

    valid_df = synthetic_ohlcv_valid_df.rename(columns=str.lower).copy()
    valid_df.index.name = "date"

    with (
        mock.patch("screener.data.ohlcv.append_incremental", return_value=(valid_df, True)),
        mock.patch("screener.data.ohlcv.yf.Ticker") as ticker_mock,
    ):
        ticker_mock.return_value.actions = pd.DataFrame(index=pd.DatetimeIndex([]))
        yf_ok, stooq_ok, failed = run_with_breaker([f"T{i}" for i in range(10)], REF_DATE)

    assert yf_ok == 10
    assert stooq_ok == 0
    assert failed == []
    # 95% gate: (yf_ok + stooq_ok) / n_universe >= 0.95
    n_universe = 10
    assert (yf_ok + stooq_ok) / n_universe >= 0.95


# --- DAT-08: golden-file split tests (skipped — see test docstring) --------


@pytest.mark.skip(
    reason=(
        "ROADMAP success criterion 4 (NVDA 2024-06-10 10:1 split ratio match). "
        "Requires a checked-in tests/fixtures/golden/NVDA/splits.parquet captured "
        "from a live yfinance fetch. Owning row: 02-VALIDATION.md Manual-Only "
        "Verifications -> 'NVDA/AAPL split ratio match (golden-file capture)'. "
        "Phase 2 ships the codepath; the developer captures the golden file "
        "post-merge per the VALIDATION instructions and removes this skip decorator."
    )
)
def test_nvda_split_2024_recorded() -> None:
    pass


@pytest.mark.skip(
    reason=(
        "ROADMAP success criterion 4 (AAPL 2020-08-31 4:1 split ratio match). "
        "Same owning row as test_nvda_split_2024_recorded — see 02-VALIDATION.md "
        "Manual-Only Verifications -> 'NVDA/AAPL split ratio match (golden-file capture)'."
    )
)
def test_aapl_split_2020_recorded() -> None:
    pass
