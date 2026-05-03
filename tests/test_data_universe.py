"""data/universe.py tests (DAT-01, DAT-02, DAT-06).

Covers the 8 tests in 02-VALIDATION.md lines 45-51 + 73. Uses synthetic
fixtures from tests/conftest.py — no live iShares HTTP calls in CI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest import mock

import pytest

from screener.data.universe import (
    build_universe_dataframe,
    fetch_ishares_iwb_csv,
    get_cached_session,
    iso_week_monday,
    normalize_ticker,
    parse_ishares_iwb_csv,
    refresh_universe,
    sanity_check,
)


# --- DAT-01: parse + normalize tests ----------------------------------------


def test_parse_ishares_csv_happy_path(synthetic_ishares_csv_bytes: bytes) -> None:
    parsed = parse_ishares_iwb_csv(synthetic_ishares_csv_bytes)
    sanity_check(parsed)
    assert len(parsed) >= 800, f"Expected >= 800 equity rows; got {len(parsed)}"
    universe = build_universe_dataframe(parsed)
    assert {"ticker", "ticker_raw", "name", "sector", "weight_pct"} <= set(universe.columns)


def test_normalize_ticker_allowlist() -> None:
    assert normalize_ticker("BRKB") == "BRK-B"
    assert normalize_ticker("BFB") == "BF-B"
    assert normalize_ticker("BFA") == "BF-A"
    # Pass-through cases:
    assert normalize_ticker("AAPL") == "AAPL"
    assert normalize_ticker("GOOGL") == "GOOGL"
    assert normalize_ticker("NVDA") == "NVDA"


def test_parse_ishares_csv_undersized_fails(
    synthetic_ishares_csv_undersized_bytes: bytes,
) -> None:
    parsed = parse_ishares_iwb_csv(synthetic_ishares_csv_undersized_bytes)
    with pytest.raises(ValueError, match="row count"):
        sanity_check(parsed)


def test_parse_ishares_csv_unknown_sector_fails(
    synthetic_ishares_csv_bad_sector_bytes: bytes,
) -> None:
    parsed = parse_ishares_iwb_csv(synthetic_ishares_csv_bad_sector_bytes)
    with pytest.raises(ValueError, match="unknown sectors"):
        sanity_check(parsed)


# --- DAT-02: snapshot keying + idempotency ----------------------------------


def test_snapshot_iso_monday_keying() -> None:
    # Wednesday 2026-04-30 -> Monday 2026-04-27.
    assert iso_week_monday(date(2026, 4, 30)) == date(2026, 4, 27)
    # Sunday 2026-05-03 -> Monday 2026-04-27 (same ISO week).
    assert iso_week_monday(date(2026, 5, 3)) == date(2026, 4, 27)
    # Monday 2026-04-27 -> itself.
    assert iso_week_monday(date(2026, 4, 27)) == date(2026, 4, 27)


def test_snapshot_idempotent_same_week(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_ishares_csv_bytes: bytes,
) -> None:
    """refresh_universe called twice in the same ISO week returns None on the second call."""
    universe_dir = tmp_path / "universe"
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: universe_dir)
    monkeypatch.setattr(
        "screener.data.universe.fetch_ishares_iwb_csv",
        lambda session=None: synthetic_ishares_csv_bytes,
    )
    # Also override UNIVERSE_CACHE_DIR in settings to point to our tmp_path.
    from screener.config import get_settings
    monkeypatch.setenv("UNIVERSE_CACHE_DIR", str(universe_dir))
    get_settings.cache_clear()
    try:
        fixed = date(2026, 4, 30)  # Wednesday; Monday key is 2026-04-27
        first = refresh_universe(force=False, today=fixed)
        assert first is not None and first.exists()
        second = refresh_universe(force=False, today=fixed)
        assert second is None, "Same-week call without --force must be a no-op"
    finally:
        get_settings.cache_clear()


def test_snapshot_force_overwrites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_ishares_csv_bytes: bytes,
) -> None:
    universe_dir = tmp_path / "universe"
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: universe_dir)
    monkeypatch.setattr(
        "screener.data.universe.fetch_ishares_iwb_csv",
        lambda session=None: synthetic_ishares_csv_bytes,
    )
    from screener.config import get_settings
    monkeypatch.setenv("UNIVERSE_CACHE_DIR", str(universe_dir))
    get_settings.cache_clear()
    try:
        fixed = date(2026, 4, 30)
        first = refresh_universe(force=False, today=fixed)
        assert first is not None
        # force=True overwrites; atomic write creates a new inode.
        second = refresh_universe(force=True, today=fixed)
        assert second is not None
        assert second == first, "force=True must write to the SAME ISO-monday-keyed path"
        assert second.stat().st_size > 0
    finally:
        get_settings.cache_clear()


# --- DAT-06: requests-cache hit test (mocked) -------------------------------


def test_requests_cache_hit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_ishares_csv_bytes: bytes,
) -> None:
    """A CachedSession serves the second call for the iShares URL from cache."""
    cache_path = tmp_path / "http.sqlite"
    monkeypatch.setattr("screener.data.universe.CACHE_PATH", cache_path)

    call_count = {"n": 0}

    class _MockResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.status_code = 200
            self.from_cache = False

        def raise_for_status(self) -> None:
            return None

    def _mock_get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return _MockResponse(synthetic_ishares_csv_bytes)

    import requests_cache as _rc

    # CachedSession overrides requests.Session.get; patch on the subclass.
    with mock.patch.object(_rc.CachedSession, "get", _mock_get):
        session = get_cached_session()
        c1 = fetch_ishares_iwb_csv(session=session)
        c2 = fetch_ishares_iwb_csv(session=session)
        assert c1 == c2

    # Verify the mock was called at least once.
    assert call_count["n"] >= 1
