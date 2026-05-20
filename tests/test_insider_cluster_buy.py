"""Insider cluster-buy SQL/Python rolling-window tests — CAT-03 / Pitfall 7.

Plan 06-03 (Wave 1) fills the test bodies with real SQL/Python rolling
assertions. Cluster definition (D-10): 2+ distinct insiders BUY transactions
within a 5-day rolling window over the last ``window_days`` days.
Pitfall 7: SQLite's RANGE INTERVAL is unsupported; fall back to a Python
rolling-window post-process if julianday RANGE is unavailable.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

from pathlib import Path

import pandas as pd
import pytest

from screener.persistence import (
    _ensure_insider_schema,
    append_form4_rows,
    read_insider_cluster_buy,
)


def _seed_db(db_path: Path, rows: list) -> None:
    """Helper: ensure schema + seed rows into a SQLite db at db_path."""
    _ensure_insider_schema(db_path)
    append_form4_rows(db_path, rows)


def test_cluster_buy_two_insiders_in_5d_window(form4_cluster_db_path: Path) -> None:
    """CAT-03: form4_cluster.sqlite has 3 distinct insiders BUYing AAPL within 3d.

    Fixture: Insider A (2026-04-01), B (2026-04-03), C (2026-04-04).
    Any rolling dt=5-day window covers at least 2 distinct insiders.
    We use window_days=60 to reach back 46+ days to the April fixture dates.
    """
    result = read_insider_cluster_buy(
        window_days=60, cluster_size=2, dt=5, db_path=form4_cluster_db_path
    )
    assert "AAPL" in result, (
        f"Expected AAPL in cluster-buy result for form4_cluster.sqlite "
        f"(3 insiders in 3d window), got: {result}"
    )


def test_cluster_buy_one_insider_no_cluster(form4_no_cluster_db_path: Path) -> None:
    """CAT-03 boundary: form4_no_cluster.sqlite has a single insider BUY on GOOGL.

    One insider cannot form a cluster (need >= 2 distinct insiders).
    We use window_days=60 to reach back to the April fixture dates.
    """
    result = read_insider_cluster_buy(
        window_days=60, cluster_size=2, dt=5, db_path=form4_no_cluster_db_path
    )
    assert "GOOGL" not in result, (
        f"Expected GOOGL NOT in cluster-buy result for form4_no_cluster.sqlite "
        f"(single insider), got: {result}"
    )


def test_cluster_buy_three_insiders_outside_window(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """CAT-03 boundary: 3 BUYs spaced 12 days apart — no 5-day window contains 2+.

    We use today-relative dates so window_days=30 covers all three rows.
    Spacing: day 0, day 12, day 24 (each gap > dt=5), so no single 5-day
    window ever has more than 1 distinct insider.
    """
    db_path = tmp_path / "form4.sqlite"  # type: ignore[operator]
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    rows = [
        {
            "filing_id": "OUT-001",
            "ticker": "AAPL",
            "insider": "Alice",
            "transaction_date": (today - pd.Timedelta(days=24)).strftime("%Y-%m-%d"),
            "type": "BUY",
            "shares": 1000.0,
            "value_usd": 150000.0,
            "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
        },
        {
            "filing_id": "OUT-002",
            "ticker": "AAPL",
            "insider": "Bob",
            "transaction_date": (today - pd.Timedelta(days=12)).strftime("%Y-%m-%d"),
            "type": "BUY",
            "shares": 500.0,
            "value_usd": 75000.0,
            "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
        },
        {
            "filing_id": "OUT-003",
            "ticker": "AAPL",
            "insider": "Carol",
            "transaction_date": today.strftime("%Y-%m-%d"),
            "type": "BUY",
            "shares": 800.0,
            "value_usd": 120000.0,
            "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
        },
    ]
    _seed_db(db_path, rows)

    result = read_insider_cluster_buy(window_days=30, cluster_size=2, dt=5, db_path=db_path)
    assert "AAPL" not in result, (
        f"Expected AAPL NOT in cluster-buy result (3 insiders each 12d apart, "
        f"no 5-day window contains 2+), got: {result}"
    )


def test_cluster_buy_sqlite_julianday_or_python_fallback(form4_cluster_db_path: Path) -> None:
    """Pitfall 7: both Recommendation A (julianday RANGE) and Recommendation B
    (Python rolling fallback) produce the same result for the cluster fixture.

    We call read_insider_cluster_buy normally (it auto-selects A or B) and
    assert AAPL is in the result. The test is path-agnostic: it passes whether
    Rec A or Rec B executed.
    """
    result = read_insider_cluster_buy(
        window_days=60, cluster_size=2, dt=5, db_path=form4_cluster_db_path
    )
    assert "AAPL" in result, (
        f"Expected AAPL in cluster-buy result regardless of SQL vs Python path, got: {result}"
    )
