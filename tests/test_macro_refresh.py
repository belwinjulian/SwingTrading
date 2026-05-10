"""Macro data layer tests (DAT-04, RESEARCH Pitfalls 1/4/5, Threats T-3-01..T-3-04).

Mocks:
- yfinance: mock.patch("screener.data.macro.yf.download", ...)
- Stooq: mock.patch("screener.data.macro.stooq_module.fetch_ohlcv", ...)
- FRED: mock.patch("screener.data.macro.Fred", ...) — patch the class import
- Persistence: monkeypatch _macro_dir to tmp_path
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import structlog
from structlog.testing import capture_logs

from screener.data import macro as macro_module
from screener.persistence import StaleOrEmptyError

REF_DATE = date(2026, 4, 30)


def _synthetic_yf_ohlcv(n: int = 252) -> pd.DataFrame:
    """yfinance-shape: PascalCase columns, date index unnamed."""
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    return pd.DataFrame(
        {
            "Open": np.full(n, 100.0),
            "High": np.full(n, 101.0),
            "Low": np.full(n, 99.0),
            "Close": np.full(n, 100.5),
            "Volume": np.full(n, 1_000_000, dtype="int64"),
        },
        index=idx,
    )


def _synthetic_breadth_df(n: int = 200) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    return pd.DataFrame(
        {"advances": np.full(n, 600, dtype="int64"),
         "declines": np.full(n, 400, dtype="int64"),
         "ad_line": np.arange(200, n + 200, dtype="int64")},
        index=pd.DatetimeIndex(idx, name="date"),
    )


def test_yf_invariants_applied() -> None:
    """_fetch_yf_macro applies the 4-invariant gate (lowercase + date index + close present)."""
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        df = macro_module._fetch_yf_macro("SPY", "2024-01-01", REF_DATE)
    assert "close" in df.columns
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing


def test_yf_empty_raises_stale() -> None:
    empty = pd.DataFrame({"Close": []}, index=pd.DatetimeIndex([]))
    with mock.patch("screener.data.macro.yf.download", return_value=empty):
        with pytest.raises(StaleOrEmptyError, match="empty"):
            macro_module._fetch_yf_macro("SPY", "2024-01-01", REF_DATE)


def test_refresh_spy_writes_macro_parquet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_spy routes through write_macro_atomic → _write_parquet_atomic."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        path = macro_module.refresh_spy(force=True, today=REF_DATE)
    assert path == macro_dir / "spy.parquet"
    assert path.exists()


def test_refresh_vix_drops_volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RESEARCH Pitfall 4: ^VIX must be projected to close-only."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        path = macro_module.refresh_vix(force=True, today=REF_DATE)
    loaded = pd.read_parquet(path)
    assert list(loaded.columns) == ["close"], f"expected close-only; got {list(loaded.columns)}"


def test_nyad_fallback_to_r1000_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stooq raises (RESEARCH Pitfall 1) → falls back to _compute_breadth_fallback."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch(
        "screener.data.macro.stooq_module.fetch_ohlcv",
        side_effect=StaleOrEmptyError("ParserError"),
    ), mock.patch(
        "screener.data.macro._compute_breadth_fallback",
        return_value=_synthetic_breadth_df(),
    ):
        with capture_logs() as logs:
            macro_module.refresh_nyad(force=True, today=REF_DATE)
    sources = [e.get("source") for e in logs if e.get("event") == "nyad_source"]
    assert "r1000_proxy" in sources, f"expected r1000_proxy event; got logs={logs}"


def test_nyad_fallback_on_thin_stooq(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-05: > 5% missing close in Stooq triggers fallback."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    n = 200
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    close = np.full(n, 100.0)
    close[:20] = np.nan  # 10% missing
    thin = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": np.full(n, 1_000_000, dtype="int64")},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    with mock.patch(
        "screener.data.macro.stooq_module.fetch_ohlcv", return_value=thin
    ), mock.patch(
        "screener.data.macro._compute_breadth_fallback",
        return_value=_synthetic_breadth_df(),
    ):
        with capture_logs() as logs:
            macro_module.refresh_nyad(force=True, today=REF_DATE)
    sources = [e.get("source") for e in logs if e.get("event") == "nyad_source"]
    assert "r1000_proxy" in sources


def test_yields_parquet_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_yields writes a Parquet with exactly {dgs2, dgs10, t10y2y} columns."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": "TEST_KEY",
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=100)
    series = pd.Series(np.full(100, 4.5), index=idx)

    fake_fred_instance = mock.MagicMock()
    fake_fred_instance.get_series.return_value = series
    with mock.patch("screener.data.macro.Fred", return_value=fake_fred_instance):
        path = macro_module.refresh_yields(force=True, today=REF_DATE)
    loaded = pd.read_parquet(path)
    assert set(loaded.columns) == {"dgs2", "dgs10", "t10y2y"}


def test_yields_skipped_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing FRED_API_KEY → warning emitted, empty Parquet written."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": "",
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )
    with capture_logs() as logs:
        path = macro_module.refresh_yields(force=True, today=REF_DATE)
    events = [e.get("event") for e in logs]
    assert "skipping_yields_no_key" in events
    assert path.exists()


def test_no_secret_in_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """T-3-02: FRED_API_KEY must NEVER appear in any captured log event from
    macro.py OR cli.py during a refresh-macro invocation.

    This test is driven via typer.testing.CliRunner so the assertion covers
    BOTH structured logs from screener.data.macro AND screener.cli — exactly
    the surface a real run touches. caplog is set at module scope (root
    logger, DEBUG level) so we capture every record regardless of which
    logger emits it.
    """
    from typer.testing import CliRunner

    from screener.cli import app as cli_app

    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    secret = "SECRET_FAKE_KEY_12345"
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": secret,
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )

    # Stub the four happy-path series (so the run reaches refresh_yields).
    monkeypatch.setattr("screener.data.macro.refresh_spy", lambda force, today: macro_dir / "spy.parquet")
    monkeypatch.setattr("screener.data.macro.refresh_qqq", lambda force, today: macro_dir / "qqq.parquet")
    monkeypatch.setattr("screener.data.macro.refresh_vix", lambda force, today: macro_dir / "vix.parquet")
    monkeypatch.setattr("screener.data.macro.refresh_nyad", lambda force, today: macro_dir / "nyad.parquet")

    # FRED raises an exception whose stringified form embeds the secret
    # in the URL querystring — exactly the leak vector T-3-02 guards against.
    leaky_url = (
        f"rate limit hit at https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=DGS10&api_key={secret}"
    )

    class FredError(RuntimeError):
        pass

    fake_fred_instance = mock.MagicMock()
    fake_fred_instance.get_series.side_effect = FredError(leaky_url)

    runner = CliRunner()
    with mock.patch("screener.data.macro.Fred", return_value=fake_fred_instance):
        with caplog.at_level(logging.DEBUG):  # root logger; captures every record
            with capture_logs() as structlog_events:
                result = runner.invoke(cli_app, ["refresh-macro"])

    # Refresh must have failed (non-zero exit).
    assert result.exit_code != 0, "expected non-zero exit when FRED raises"

    # 1) Secret must not appear in any structlog event from macro/cli.
    for entry in structlog_events:
        for v in entry.values():
            assert secret not in str(v), f"secret leaked in structlog entry {entry}"
            assert "api_key=" not in str(v), f"api_key= leaked in structlog entry {entry}"

    # 2) Secret must not appear in stdlib caplog text (covers any non-structlog path).
    assert secret not in caplog.text, f"secret leaked in caplog: {caplog.text}"
    assert "api_key=" not in caplog.text, f"api_key= leaked in caplog: {caplog.text}"


def test_refresh_spy_appends_only_new_bars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-06 incremental-append contract: a second refresh fetches ONLY bars
    after max(date)+1d and appends them; it does NOT re-issue the full backfill.

    Uses real persistence.read_macro_spy() to round-trip through the
    schema-shaped empty-frame path on first run, then through the populated
    path on second run.
    """
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)

    # First run — 100 bars from 2025-01-01..(date+100bd). yfinance mock returns
    # the synthetic frame; we capture (start, end) so we can verify the second
    # run uses the NEXT-DAY start.
    first_n = 100
    first_idx = pd.bdate_range(start=pd.Timestamp("2025-01-01"), periods=first_n)
    first_df = pd.DataFrame(
        {
            "Open": np.full(first_n, 100.0),
            "High": np.full(first_n, 101.0),
            "Low": np.full(first_n, 99.0),
            "Close": np.full(first_n, 100.5),
            "Volume": np.full(first_n, 1_000_000, dtype="int64"),
        },
        index=first_idx,
    )
    captured_starts: list[str] = []

    def _mock_yf_first(ticker: str, *args: object, **kwargs: object) -> pd.DataFrame:
        # First call captures whatever start refresh_spy passes in.
        captured_starts.append(str(kwargs.get("start", args[0] if args else "")))
        return first_df

    with mock.patch("screener.data.macro.yf.download", side_effect=_mock_yf_first):
        path1 = macro_module.refresh_spy(force=False, today=date(2025, 5, 21))
    loaded1 = pd.read_parquet(path1)
    assert len(loaded1) == first_n, f"expected first run to write {first_n} bars; got {len(loaded1)}"
    last_first = loaded1.index.max()

    # Second run — yfinance returns ONLY the next bar (1 row).
    next_day = (last_first + pd.Timedelta(days=1)).normalize()
    second_df = pd.DataFrame(
        {
            "Open": [102.0],
            "High": [103.0],
            "Low": [101.0],
            "Close": [102.5],
            "Volume": [2_000_000],
        },
        index=pd.DatetimeIndex([next_day]),
    )

    def _mock_yf_second(ticker: str, *args: object, **kwargs: object) -> pd.DataFrame:
        captured_starts.append(str(kwargs.get("start", args[0] if args else "")))
        return second_df

    with mock.patch("screener.data.macro.yf.download", side_effect=_mock_yf_second):
        path2 = macro_module.refresh_spy(force=False, today=date(2025, 5, 22))
    loaded2 = pd.read_parquet(path2)

    assert len(loaded2) == first_n + 1, f"expected {first_n + 1} bars after append; got {len(loaded2)}"
    assert loaded2.index.max() == next_day, f"expected last date {next_day}; got {loaded2.index.max()}"

    # Critical assertion: the SECOND yf.download call's start arg is
    # next_day_str, NOT MACRO_BACKFILL_START. captured_starts[1] is the
    # second run's start.
    assert len(captured_starts) >= 2, f"expected 2 yf calls; got {captured_starts}"
    next_day_str = next_day.strftime("%Y-%m-%d")
    assert captured_starts[1] == next_day_str, (
        f"D-06 incremental-fetch start was {captured_starts[1]!r}; "
        f"expected {next_day_str!r} (max(date)+1d)"
    )
