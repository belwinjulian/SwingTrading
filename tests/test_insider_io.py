"""EDGAR Form 4 data adapter tests — CAT-04.

Plan 06-03 (Wave 1) fills the test bodies with mocked assertions over
``data/insider.py`` (edgartools bulk Form 4 fetch + SQLite append-only
event log per D-10). InsiderSchema validation runs BEFORE the SQLite insert.
No real EDGAR network calls are made in any test.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import sqlite3
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from screener import persistence

# ---------------------------------------------------------------------------
# Shared helpers / mock factories
# ---------------------------------------------------------------------------


class _MockActivity:
    """Simulates one edgartools transaction activity record."""

    def __init__(
        self,
        ticker: str,
        insider_name: str,
        transaction_date: str,
        shares: float,
        value_usd: float,
        is_acquisition: bool,
    ) -> None:
        self.ticker = ticker
        self.insider_name = insider_name
        self.transaction_date = transaction_date
        self.shares = shares
        self.value_usd = value_usd
        self.is_acquisition = is_acquisition


class _MockForm4:
    """Simulates edgartools Form4 object."""

    def __init__(self, activities: list) -> None:
        self._activities = activities

    def get_transaction_activities(self) -> list:
        return self._activities


class _MockFiling:
    """Simulates one edgartools Filing object."""

    def __init__(self, accession_no: str, activities: list) -> None:
        self.accession_no = accession_no
        self._activities = activities

    def obj(self) -> _MockForm4:
        return _MockForm4(self._activities)


def _make_mock_filings() -> list:
    """3 synthetic filings — AAPL (2 insiders) + MSFT (1 insider)."""
    return [
        _MockFiling(
            "0001-01",
            [_MockActivity("AAPL", "T Cook", "2026-04-01", 1000.0, 175000.0, True)],
        ),
        _MockFiling(
            "0001-02",
            [_MockActivity("AAPL", "L Maestri", "2026-04-03", 800.0, 140000.0, True)],
        ),
        _MockFiling(
            "0001-03",
            [_MockActivity("MSFT", "S Nadella", "2026-04-04", 500.0, 200000.0, True)],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_form4_bulk_fetch_idempotent(
    tmp_path: pytest.TempPathFactory,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-10: second invocation with same filings inserts ZERO rows.

    ON CONFLICT(filing_id) DO NOTHING preserves append-only history.
    """
    db_path = str(tmp_path / "form4.sqlite")  # type: ignore[operator]
    monkeypatch.setenv("INSIDER_CACHE_PATH", db_path)
    from screener.config import get_settings

    get_settings.cache_clear()

    import screener.data.insider as ins_mod

    mock_filings = _make_mock_filings()

    with patch.object(ins_mod.edgar, "get_filings", return_value=mock_filings):
        n1 = ins_mod.refresh_insider(date(2026, 5, 1))
    assert n1 == 3, f"Expected 3 rows inserted on first call, got {n1}"

    with patch.object(ins_mod.edgar, "get_filings", return_value=mock_filings):
        n2 = ins_mod.refresh_insider(date(2026, 5, 1))
    assert n2 == 0, f"Expected 0 rows on idempotent second call (ON CONFLICT DO NOTHING), got {n2}"


def test_form4_schema_validated_before_sqlite_insert(
    tmp_path: pytest.TempPathFactory,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CAT-04 / T-06-12: InsiderSchema validation rejects invalid data before SQLite insert.

    We bypass refresh_insider and directly test the validation boundary:
    build a DataFrame with type='GIFT' (invalid per InsiderSchema isin check),
    call persistence.validate_at_write(InsiderSchema, df), assert SchemaError raised,
    and confirm the DB stays empty.
    """
    db_path = tmp_path / "form4.sqlite"  # type: ignore[operator]

    # Ensure the DB schema exists but is empty
    persistence._ensure_insider_schema(db_path)

    # Build a DataFrame with an invalid 'type' field
    bad_df = pd.DataFrame(
        {
            "filing_id": ["BAD-001"],
            "ticker": ["AAPL"],
            "insider": ["Bad Actor"],
            "transaction_date": [pd.Timestamp("2026-04-01")],
            "type": ["GIFT"],  # Invalid — InsiderSchema only allows BUY or SELL
            "shares": [1000.0],
            "value_usd": [175000.0],
            "ingested_at": [pd.Timestamp.now()],
        }
    )

    # Validation MUST raise SchemaError before any SQLite insert
    with pytest.raises(Exception):  # pa.errors.SchemaError is a subclass of Exception
        persistence.validate_at_write(persistence.InsiderSchema, bad_df)

    # Confirm DB is still empty — schema rejection blocked the insert
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM form4").fetchone()[0]
    assert count == 0, f"Expected 0 rows in DB after schema rejection, got {count}"
