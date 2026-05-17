"""Fundamentals data adapter tests — CAT-01 / DAT-05.

Plan 06-03 (Wave 1) replaces every pytest.skip with mocked assertions over
data/fundamentals.py (Finnhub earnings calendar + yfinance EPS history),
following the tests/test_data_ohlcv.py mock pattern (no network at test time).
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import pytest


def test_earnings_calendar_normalize() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates CAT-01: mocked Finnhub /calendar/earnings response is "
        "normalized to FundamentalsSchema with next_earnings_hour in "
        "{bmo, amc, dmh, unknown}."
    )


def test_eps_history_yfinance_mock() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates DAT-05: yfinance.Ticker(t).quarterly_income_stmt is "
        "mocked; the Diluted EPS row is extracted and joined to the "
        "fundamentals row for the ticker."
    )


def test_knowable_from_45d_added() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates D-13b: every fundamentals row written by "
        "data/fundamentals.refresh_fundamentals has "
        "knowable_from = fiscal_quarter_end + 45 days (calendar days)."
    )
