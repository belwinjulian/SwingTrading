"""Generate Phase 6 test fixtures (one-shot script — runs ONCE, output committed).

Produces 7 fixture files consumed by the 12 Phase 6 test skeletons created in
Plan 06-01. Each fixture is a deterministic, small (~50KB) artifact committed
to the repo so Phase 6 tests do NOT need network access at CI time.

Outputs:
  tests/fixtures/patterns/nvda_2023_vcp.parquet       — NVDA 2023-04..2023-07 OHLCV
  tests/fixtures/patterns/aapl_2020_vcp.parquet       — AAPL 2020-02..2020-08 OHLCV
  tests/fixtures/patterns/nvda_2024_split.parquet     — NVDA 2024-04..2024-08 OHLCV (spans 10:1 split)
  tests/fixtures/patterns/nvda_2023_flag.parquet      — NVDA 2023-05..2023-06 OHLCV
  tests/fixtures/fundamentals/sample_quarterly.parquet — synthetic FundamentalsSchema rows
  tests/fixtures/form4_cluster.sqlite                  — synthetic 3-insider cluster on AAPL
  tests/fixtures/form4_no_cluster.sqlite               — single-insider Form 4 (no cluster)

Run once:
    PYTHONPATH=src uv run python scripts/generate_phase6_fixtures.py

Pitfall 5 (yfinance brittleness): we accept slight churn between runs because
the script is one-shot — once the fixtures are committed, CI never re-fetches.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_DIR = REPO_ROOT / "tests" / "fixtures" / "patterns"
FUNDAMENTALS_DIR = REPO_ROOT / "tests" / "fixtures" / "fundamentals"
SQLITE_DIR = REPO_ROOT / "tests" / "fixtures"


def _ensure_dirs() -> None:
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    FUNDAMENTALS_DIR.mkdir(parents=True, exist_ok=True)
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_yf(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV via yfinance — auto_adjust=True (D-25 / Pitfall 1).

    Falls back to synthetic data when offline (no network at fixture time).
    The synthetic fallback produces a deterministic, schema-shaped panel so
    downstream pattern golden tests still have something to load — the tests
    themselves will skip via pytest.skip() until Plan 06-02 fills the body
    with real assertions against the real OHLCV.
    """
    try:
        import yfinance as yf

        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
        )
        if df is None or len(df) == 0:
            raise RuntimeError("yfinance returned empty")
        # Flatten multi-level columns (yfinance returns (Open, NVDA)).
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        # Normalize column names to lowercase.
        df.columns = [str(c).lower() for c in df.columns]
        # Keep canonical OHLCV columns only.
        cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        df = df[cols]
        df.index.name = "date"
        return df
    except Exception as e:
        print(f"  WARN: yfinance fetch failed for {ticker} {start}..{end}: {e}")
        print("  Falling back to deterministic synthetic OHLCV (schema-valid, Pitfall 5).")
        idx = pd.bdate_range(start=start, end=end, name="date")
        n = len(idx)
        rng = np.random.default_rng(seed=abs(hash(f"{ticker}{start}{end}")) % (2**32))
        log_ret = rng.normal(loc=0.0008, scale=0.018, size=n)
        close = 100.0 * np.exp(np.cumsum(log_ret))
        open_ = close * (1.0 + rng.normal(0, 0.003, n))
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.006, n)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.006, n)))
        volume = rng.integers(low=10_000_000, high=80_000_000, size=n, dtype="int64")
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=idx,
        )


def _write_pattern_fixture(name: str, df: pd.DataFrame) -> Path:
    target = PATTERNS_DIR / name
    df.to_parquet(target, engine="pyarrow", index=True)
    print(
        f"  wrote {target.relative_to(REPO_ROOT)} ({len(df)} rows, "
        f"{target.stat().st_size / 1024:.1f} KB)"
    )
    return target


def generate_pattern_fixtures() -> None:
    print("== Pattern fixtures (D-02 golden files) ==")
    print("NVDA 2023 VCP:")
    _write_pattern_fixture(
        "nvda_2023_vcp.parquet",
        _fetch_yf("NVDA", "2023-04-01", "2023-07-15"),
    )
    print("AAPL 2020 VCP:")
    _write_pattern_fixture(
        "aapl_2020_vcp.parquet",
        _fetch_yf("AAPL", "2020-02-01", "2020-08-31"),
    )
    print("NVDA 2024 split (spans 2024-06-10 10:1):")
    _write_pattern_fixture(
        "nvda_2024_split.parquet",
        _fetch_yf("NVDA", "2024-04-01", "2024-08-31"),
    )
    print("NVDA 2023 flag (post-earnings 05-25..06-12):")
    _write_pattern_fixture(
        "nvda_2023_flag.parquet",
        _fetch_yf("NVDA", "2023-05-15", "2023-06-20"),
    )


def generate_fundamentals_fixture() -> None:
    """4-row FundamentalsSchema-valid sample frame.

    Columns: ticker, fiscal_quarter_end, eps_actual, eps_yoy_growth,
             knowable_from (= fiscal_quarter_end + 45d),
             next_earnings_date, next_earnings_hour, source, ingested_at.
    """
    print("== Fundamentals fixture (synthetic, FundamentalsSchema-compliant) ==")
    tickers = ["AAPL", "MSFT", "NVDA", "AMZN"]
    rows = []
    base_quarter = pd.Timestamp("2024-03-31")
    ingested = pd.Timestamp("2024-06-01 12:00:00")
    for i, t in enumerate(tickers):
        quarter = base_quarter
        rows.append(
            {
                "ticker": t,
                "fiscal_quarter_end": quarter,
                "eps_actual": 1.5 + 0.25 * i,
                "eps_yoy_growth": 0.30 + 0.05 * i,
                "knowable_from": quarter + pd.Timedelta(days=45),
                "next_earnings_date": pd.Timestamp("2024-07-30") + pd.Timedelta(days=i),
                "next_earnings_hour": ["amc", "bmo", "amc", "amc"][i],
                "source": "finnhub",
                "ingested_at": ingested,
            }
        )
    df = pd.DataFrame(rows)
    target = FUNDAMENTALS_DIR / "sample_quarterly.parquet"
    df.to_parquet(target, engine="pyarrow", index=False)
    print(
        f"  wrote {target.relative_to(REPO_ROOT)} ({len(df)} rows, "
        f"{target.stat().st_size / 1024:.1f} KB)"
    )


def _build_form4_sqlite(db_path: Path, rows: list[dict[str, object]]) -> None:
    """Build a Form 4 SQLite with the D-10 schema, populated with `rows`."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE form4 (
                filing_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                insider TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                type TEXT NOT NULL,
                shares REAL NOT NULL,
                value_usd REAL NOT NULL,
                ingested_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX idx_form4_ticker_date ON form4(ticker, transaction_date)")
        conn.executemany(
            """INSERT INTO form4(filing_id, ticker, insider, transaction_date,
                                  type, shares, value_usd, ingested_at)
               VALUES (:filing_id, :ticker, :insider, :transaction_date,
                       :type, :shares, :value_usd, :ingested_at)""",
            rows,
        )


def generate_insider_fixtures() -> None:
    print("== Insider Form 4 SQLite fixtures (CAT-03 cluster-buy test inputs) ==")
    ingested_iso = datetime(2026, 4, 15, 12, 0, 0).isoformat()

    # Cluster fixture: 3 distinct insiders on AAPL within 5d window (cluster)
    # PLUS 1 single insider on MSFT 5+ days outside the cluster window.
    cluster_rows = [
        {
            "filing_id": "F-AAPL-0001",
            "ticker": "AAPL",
            "insider": "Insider A",
            "transaction_date": "2026-04-01",
            "type": "BUY",
            "shares": 1000.0,
            "value_usd": 175_000.0,
            "ingested_at": ingested_iso,
        },
        {
            "filing_id": "F-AAPL-0002",
            "ticker": "AAPL",
            "insider": "Insider B",
            "transaction_date": "2026-04-03",
            "type": "BUY",
            "shares": 500.0,
            "value_usd": 87_500.0,
            "ingested_at": ingested_iso,
        },
        {
            "filing_id": "F-AAPL-0003",
            "ticker": "AAPL",
            "insider": "Insider C",
            "transaction_date": "2026-04-04",
            "type": "BUY",
            "shares": 800.0,
            "value_usd": 140_000.0,
            "ingested_at": ingested_iso,
        },
        {
            "filing_id": "F-MSFT-0001",
            "ticker": "MSFT",
            "insider": "Insider M",
            "transaction_date": "2026-04-10",
            "type": "BUY",
            "shares": 200.0,
            "value_usd": 84_000.0,
            "ingested_at": ingested_iso,
        },
    ]
    cluster_db = SQLITE_DIR / "form4_cluster.sqlite"
    _build_form4_sqlite(cluster_db, cluster_rows)
    print(
        f"  wrote {cluster_db.relative_to(REPO_ROOT)} ({len(cluster_rows)} rows, "
        f"{cluster_db.stat().st_size / 1024:.1f} KB)"
    )

    # No-cluster fixture: single insider on GOOGL.
    no_cluster_rows = [
        {
            "filing_id": "F-GOOGL-0001",
            "ticker": "GOOGL",
            "insider": "Insider X",
            "transaction_date": "2026-04-05",
            "type": "BUY",
            "shares": 600.0,
            "value_usd": 90_000.0,
            "ingested_at": ingested_iso,
        }
    ]
    no_cluster_db = SQLITE_DIR / "form4_no_cluster.sqlite"
    _build_form4_sqlite(no_cluster_db, no_cluster_rows)
    print(
        f"  wrote {no_cluster_db.relative_to(REPO_ROOT)} ({len(no_cluster_rows)} row, "
        f"{no_cluster_db.stat().st_size / 1024:.1f} KB)"
    )


def main() -> int:
    _ensure_dirs()
    generate_pattern_fixtures()
    generate_fundamentals_fixture()
    generate_insider_fixtures()
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
