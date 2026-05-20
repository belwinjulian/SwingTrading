"""Universe — iShares IWB CSV fetcher, parser, normalizer, weekly snapshot writer.

The Russell 1000 source of truth (D-01). Implements the IWB AJAX CSV path
verified live 2026-05-02 (HTTP/2 200, 1010 lines, 9 metadata + blank +
header + 1005 Equity rows + 5 cash/derivative + trailer; UTF-8 with BOM)
and the BRKB/BFB/BFA allowlist (D-03 amended).

Layered-DAG contract: this module imports only stdlib, third-party, and
screener.persistence + screener.config. It does NOT import any other
screener.* layer. tests/test_architecture.py enforces this.
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import requests
import requests_cache
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from screener.config import get_settings
from screener.persistence import (
    GICS_SECTORS,
    write_universe_atomic,
)

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)


# --- iShares feed constants (verified live 2026-05-02) ---------------------

ISHARES_IWB_URL = (
    "https://www.ishares.com/us/products/239707/"
    "ishares-russell-1000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWB_holdings&dataType=fund"
)

ISHARES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# 9 metadata rows, then a blank, then the header at row 9 (0-indexed).
# skiprows=9 skips lines 0..8 and treats line 9 as the header.
ISHARES_SKIPROWS = 9
ISHARES_ENCODING = "utf-8-sig"  # strips the UTF-8 BOM that prefixes the file

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"Ticker", "Name", "Sector", "Asset Class", "Weight (%)"}
)


# --- Symbol normalization (D-03 amended 2026-05-02 — allowlist replaces regex) ---

# Hand-curated iShares -> yfinance share-class divergences. Verified live in
# the IWB feed 2026-05-02 (BRKB/BFB/BFA). The Original D-03 regex
# `\.([A-Z])$` -> `-\1` was a no-op against the live feed (no dots).
ALLOWLIST: dict[str, str] = {
    "BRKB": "BRK-B",
    "BFB": "BF-B",
    "BFA": "BF-A",
}


def normalize_ticker(raw: str) -> str:
    """Convert iShares ticker form to canonical yfinance form.

    iShares uses NO separator for share classes (BRKB, BFB, BFA); yfinance
    uses dash (BRK-B, BF-B, BF-A). Pass-through for everything else.
    """
    return ALLOWLIST.get(raw, raw)


# --- Sanity-gate row thresholds (Open Question 5 resolution) ---------------

ROW_HARD_MIN = 800
ROW_HARD_MAX = 1100
ROW_WARN_MIN = 950
ROW_WARN_MAX = 1010


# --- HTTP cache configuration (Open Question 6 resolution) -----------------

CACHE_PATH = Path.home() / ".cache" / "screener" / "http.sqlite"

URLS_EXPIRE_AFTER = {
    "*.ishares.com/*holdings*": timedelta(hours=1),
    "*.finnhub.io/*calendar*": timedelta(hours=1),
    "*.finnhub.io/*fundamentals*": timedelta(hours=24),
    "*.fred.stlouisfed.org/*": timedelta(hours=24),
}


def get_cached_session() -> requests_cache.CachedSession:
    """Single shared CachedSession for all HTTP-based fetchers.

    Backend: SQLite at ~/.cache/screener/http.sqlite (XDG-style, host-local,
    survives `git clean`). 1h expiry on iShares, 1h on Finnhub calendar,
    24h on Finnhub fundamentals + FRED. NOT used for yfinance (yfinance
    manages its own session — see RESEARCH.md Anti-Patterns).

    Asserts session.verify is True at construction (T-02-22 defense): any
    future regression that flips the requests default to verify=False fails
    loud here rather than silently in flight against a MitM proxy.
    """
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    session = requests_cache.CachedSession(
        cache_name=str(CACHE_PATH),
        backend="sqlite",
        urls_expire_after=URLS_EXPIRE_AFTER,
        allowable_codes=[200],
        stale_if_error=False,
    )
    assert session.verify is True, "requests session has TLS verification disabled"
    return session


# --- HTTP fetch with tenacity retry ----------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(
        (requests.HTTPError, requests.ConnectionError, requests.Timeout, ConnectionError, TimeoutError)  # noqa: E501
    ),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_ishares_iwb_csv(session: requests.Session | None = None) -> bytes:
    """Fetch the raw iShares IWB CSV bytes.

    Caller may pass a requests-cache CachedSession for repeat-run cache hits;
    omitted, a one-shot requests session is used.
    """
    s: requests.Session = session if session is not None else requests.Session()
    log.info("fetch_start", source="ishares", url=ISHARES_IWB_URL)
    resp = s.get(ISHARES_IWB_URL, headers=ISHARES_HEADERS, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.content


# --- CSV parsing -----------------------------------------------------------


def parse_ishares_iwb_csv(content: bytes) -> pd.DataFrame:
    """Parse + filter to Equity rows. Returns a DataFrame ready for sanity_check."""
    df = pd.read_csv(
        io.BytesIO(content),
        skiprows=ISHARES_SKIPROWS,
        encoding=ISHARES_ENCODING,
        thousands=",",
        na_values=["-"],
    )
    # Drop rows with NaN Ticker (post-equity blank line + trailer text rows).
    df = df.dropna(subset=["Ticker"])
    # Drop the BlackRock disclaimer text row.
    df = df[~df["Ticker"].astype(str).str.startswith("The content")]
    # Filter to Equity rows; drops 5 cash/derivative rows in live feed.
    df = df[df["Asset Class"] == "Equity"].copy()
    return df


# --- Sanity check (D-02 hard gate + Open-Question-5 soft warning) ----------


def sanity_check(df: pd.DataFrame) -> None:
    """Raise ValueError on out-of-band row count, missing required columns,
    or unknown sector. Emit structured warning when row count is outside
    [950, 1010] but still within [800, 1100].
    """
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"iShares CSV missing columns: {sorted(missing)}")
    n = len(df)
    if not (ROW_HARD_MIN <= n <= ROW_HARD_MAX):
        raise ValueError(
            f"iShares CSV row count {n} outside hard-gate [{ROW_HARD_MIN}, {ROW_HARD_MAX}]"
        )
    if not (ROW_WARN_MIN <= n <= ROW_WARN_MAX):
        log.warning(
            "universe_row_count_warning",
            n=n,
            warn_min=ROW_WARN_MIN,
            warn_max=ROW_WARN_MAX,
        )
    bad_sectors = set(df["Sector"]) - GICS_SECTORS
    if bad_sectors:
        raise ValueError(f"iShares CSV unknown sectors: {sorted(bad_sectors)}")


# --- ISO-week-Monday keying (Open Question 4 resolution) -------------------


def iso_week_monday(today: date) -> date:
    """Return the Monday of the ISO week containing `today`.

    Holiday-agnostic per Open Question 4 (planner-finalized).
    Memorial Day / Juneteenth / etc. are not special-cased; the cron runs
    daily and the Monday of the week is the snapshot key.
    """
    return today - timedelta(days=today.isoweekday() - 1)


# --- Universe DataFrame construction ---------------------------------------


def build_universe_dataframe(parsed: pd.DataFrame) -> pd.DataFrame:
    """Map the iShares-shape DataFrame to the UniverseSchema-shape DataFrame."""
    out = pd.DataFrame(
        {
            "ticker_raw": parsed["Ticker"].astype(str).to_numpy(),
            "ticker": [normalize_ticker(t) for t in parsed["Ticker"].astype(str).to_numpy()],
            "name": parsed["Name"].astype(str).to_numpy(),
            "sector": parsed["Sector"].astype(str).to_numpy(),
            "weight_pct": parsed["Weight (%)"].astype(float).to_numpy(),
        }
    )
    return out


# --- CLI-callable entrypoint -----------------------------------------------


def refresh_universe(force: bool = False, today: date | None = None) -> Path | None:
    """Idempotent weekly universe refresh.

    Returns the Path written when a snapshot is written, or None when the
    snapshot already exists for the current ISO week and force is False.

    Raises ValueError on sanity-check failure; raises requests.HTTPError on
    fetch failure after tenacity exhaustion; raises pandera.SchemaError on
    schema validation failure at the write boundary.
    """
    settings = get_settings()
    today_d = today if today is not None else date.today()
    monday = iso_week_monday(today_d)
    target = Path(settings.UNIVERSE_CACHE_DIR) / f"{monday.isoformat()}.parquet"
    if target.exists() and not force:
        log.info("snapshot_idempotent_skip", path=str(target), iso_monday=monday.isoformat())
        return None

    session = get_cached_session()
    content = fetch_ishares_iwb_csv(session=session)
    parsed = parse_ishares_iwb_csv(content)
    sanity_check(parsed)
    universe_df = build_universe_dataframe(parsed)
    written = write_universe_atomic(universe_df, monday.isoformat())
    log.info(
        "snapshot_written",
        path=str(written),
        n_rows=len(universe_df),
        iso_monday=monday.isoformat(),
        forced=force,
    )
    return written
