"""Insider cluster-buy SQL/Python rolling-window tests — CAT-03 / Pitfall 7.

Plan 06-03 (Wave 1) replaces every pytest.skip with real SQL/Python rolling
assertions against the committed `tests/fixtures/form4_cluster.sqlite` and
`tests/fixtures/form4_no_cluster.sqlite` fixtures. Cluster definition (D-10):
2+ distinct insiders BUY transactions within a 5-day rolling window over the
last 30 days. Pitfall 7: SQLite's RANGE INTERVAL is unsupported; fall back
to a Python rolling-window post-process if julianday RANGE is unavailable.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import pytest


def test_cluster_buy_two_insiders_in_5d_window() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates CAT-03: form4_cluster.sqlite has 3 distinct insiders "
        "BUYing AAPL on 2026-04-01/03/04 (within 5d) — "
        "read_insider_cluster_buy returns True for AAPL."
    )


def test_cluster_buy_one_insider_no_cluster() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates CAT-03 boundary: form4_no_cluster.sqlite has a single "
        "insider BUY on GOOGL — read_insider_cluster_buy returns False."
    )


def test_cluster_buy_three_insiders_outside_window() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates CAT-03 boundary: 3 insider BUYs spaced 6+ days apart "
        "(outside the 5-day rolling window) return False (no cluster)."
    )


def test_cluster_buy_sqlite_julianday_or_python_fallback() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates Pitfall 7: read_insider_cluster_buy uses either "
        "Recommendation A (sqlite julianday RANGE window) when the local "
        "sqlite3 supports it, or Recommendation B (Python rolling-window "
        "post-process) — both paths produce identical cluster sets."
    )
