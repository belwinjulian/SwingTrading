"""Fundamentals data adapter tests — CAT-01 / DAT-05.

Plan 06-03 (Wave 1) fills the test bodies with mocked assertions over
``data/fundamentals.py`` (Finnhub earnings calendar + yfinance EPS history).
No real network calls are made in any test.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def test_earnings_calendar_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    """CAT-01: Finnhub /calendar/earnings response is normalized correctly.

    Asserts:
    - shape (2, ...) for a 2-row mock payload
    - null hour field is coerced to "unknown"
    - date column is datetime64 dtype
    """
    mock_payload = {
        "earningsCalendar": [
            {
                "symbol": "AAPL",
                "date": "2026-05-15",
                "hour": "bmo",
                "quarter": 2,
                "year": 2026,
                "epsActual": 1.5,
                "epsEstimate": 1.4,
            },
            {
                "symbol": "MSFT",
                "date": "2026-05-16",
                "hour": None,
                "quarter": 2,
                "year": 2026,
                "epsActual": 2.1,
                "epsEstimate": 2.0,
            },
        ]
    }

    import screener.data.fundamentals as fmod

    mock_client = MagicMock()
    mock_client.earnings_calendar.return_value = mock_payload

    with patch.object(fmod.finnhub, "Client", return_value=mock_client):
        df = fmod.fetch_earnings_calendar(date(2026, 5, 1), date(2026, 7, 1))

    assert len(df) == 2, f"Expected 2 rows, got {len(df)}"
    # null hour on MSFT should be normalized to "unknown"
    msft_row = df[df["symbol"] == "MSFT"]
    assert len(msft_row) == 1, "MSFT row not found"
    assert msft_row["hour"].iloc[0] == "unknown", (
        f"Expected 'unknown' for null hour, got {msft_row['hour'].iloc[0]!r}"
    )
    # AAPL "bmo" should be preserved
    aapl_row = df[df["symbol"] == "AAPL"]
    assert aapl_row["hour"].iloc[0] == "bmo"
    # date column must be datetime
    assert pd.api.types.is_datetime64_any_dtype(df["date"]), (
        f"Expected datetime64 dtype for date column, got {df['date'].dtype}"
    )


def test_eps_history_yfinance_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """DAT-05: yfinance Ticker.quarterly_income_stmt mocked; Diluted EPS extracted.

    Asserts:
    - columns [fiscal_quarter_end, eps_actual, eps_yoy_growth] present
    - len(df) == 4 (one row per quarter in the mock 4-row index)
    """
    import screener.data.fundamentals as fmod

    # Build a mock quarterly_income_stmt DataFrame (yfinance shape: rows=metrics, cols=dates)
    dates = pd.date_range("2025-03-31", periods=4, freq="QE")
    mock_stmt = pd.DataFrame(
        {
            dates[0]: {"Diluted EPS": 1.2, "Net Income": 1e9},
            dates[1]: {"Diluted EPS": 1.4, "Net Income": 1.1e9},
            dates[2]: {"Diluted EPS": 1.5, "Net Income": 1.2e9},
            dates[3]: {"Diluted EPS": 1.6, "Net Income": 1.3e9},
        }
    )

    mock_ticker = MagicMock()
    mock_ticker.quarterly_income_stmt = mock_stmt

    with patch.object(fmod.yf, "Ticker", return_value=mock_ticker):
        df = fmod.fetch_eps_history("AAPL")

    assert not df.empty, "Expected non-empty DataFrame from mock"
    for col in ("fiscal_quarter_end", "eps_actual", "eps_yoy_growth"):
        assert col in df.columns, f"Expected column '{col}' in result, got {list(df.columns)}"
    assert len(df) == 4, f"Expected 4 rows, got {len(df)}"


def test_knowable_from_45d_added(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[type-arg]
    """D-13b: knowable_from = fiscal_quarter_end + 45 days after refresh_fundamentals.

    Uses monkeypatch to bypass all network calls:
    - fetch_earnings_calendar returns empty DataFrame
    - fetch_eps_history_with_pacing returns a 1-row EPS DataFrame

    After refresh_fundamentals, reads back via read_fundamentals(Timestamp)
    and asserts knowable_from = fiscal_quarter_end + 45d.
    """
    monkeypatch.setenv("FUNDAMENTALS_CACHE_DIR", str(tmp_path))
    from screener.config import get_settings

    get_settings.cache_clear()

    import screener.data.fundamentals as fmod
    from screener.persistence import read_fundamentals

    quarter_end = pd.Timestamp("2026-03-31")
    mock_eps = pd.DataFrame(
        {
            "fiscal_quarter_end": [quarter_end],
            "eps_actual": [1.5],
            "eps_yoy_growth": [0.3],
        }
    )
    expected_knowable = quarter_end + pd.Timedelta(days=45)  # 2026-05-15

    with (
        patch.object(fmod, "fetch_earnings_calendar", return_value=pd.DataFrame()),
        patch.object(fmod, "fetch_eps_history_with_pacing", return_value=mock_eps),
    ):
        fmod.refresh_fundamentals(today=date(2026, 5, 15), tickers=["AAPL"])

    # Read back after knowable_from (2026-05-15) — use 2026-06-01 to be safely past it
    df = read_fundamentals(pd.Timestamp("2026-06-01"))
    assert len(df) > 0, "Expected at least 1 row after refresh_fundamentals"

    aapl_rows = df[df["ticker"] == "AAPL"]
    assert len(aapl_rows) > 0, f"Expected AAPL in result, got {df['ticker'].tolist()}"
    actual_kf = pd.Timestamp(aapl_rows["knowable_from"].iloc[0])
    assert actual_kf == expected_knowable, (
        f"Expected knowable_from = {expected_knowable}, got {actual_kf}"
    )
