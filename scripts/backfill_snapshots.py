"""Backfill historical data/snapshots/<date>.parquet files for the backtest harness.

D-01 / D-02 from .planning/phases/05-backtest-harness-no-lookahead-gate/05-CONTEXT.md:
Loops over trading days 2016-01-01..today and calls Phase 4's
publishers.pipeline.run_pipeline(date, write_report=False) for each date.
Idempotent: skips dates where data/snapshots/<date>.parquet already exists.

Lives OUTSIDE src/screener/backtest/ (D-17) so it can import publishers freely.
Not a screener CLI subcommand (D-18 — 9-subcommand surface locked); invoked
via `make backfill-snapshots` (Makefile target).

Module-top imports are stdlib + pandas only. Heavy imports (run_pipeline) live
INSIDE main() — matches scripts/check_preregistration.py discipline (Pitfall 9).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_START = "2016-01-01"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill data/snapshots/<date>.parquet for the backtest harness."
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help=f"ISO start date (YYYY-MM-DD); default {DEFAULT_START}.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="ISO end date (YYYY-MM-DD); default today.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Backfill loop. Returns 0 on completion (regardless of per-date failures).

    Per-date failures are logged + counted but do not abort the loop —
    a single bad yfinance day should not block a 10-year backfill.
    """
    # Lazy heavy import — module top is stdlib + pandas only (Pitfall 9 / 5).
    from screener.publishers.pipeline import run_pipeline

    args = _parse_args(argv)
    if not _DATE_RE.match(args.start):
        print(f"ERROR: --start must be YYYY-MM-DD; got {args.start!r}", file=sys.stderr)
        return 2
    if args.end is not None and not _DATE_RE.match(args.end):
        print(f"ERROR: --end must be YYYY-MM-DD; got {args.end!r}", file=sys.stderr)
        return 2

    start_ts = pd.Timestamp(args.start)
    end_ts = pd.Timestamp(args.end) if args.end else pd.Timestamp.today().normalize()
    snapshot_dir = Path("data/snapshots")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_skip = 0
    n_fail = 0
    dates = pd.bdate_range(start_ts, end_ts)
    print(f"BACKFILL START: {start_ts.date()}..{end_ts.date()} ({len(dates)} trading days)")
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        # T-5-01: defensive re-check on the rendered stem (paranoia for crafted format strings).
        if not _DATE_RE.match(date_str):
            print(f"SKIP {date_str}: invalid stem", file=sys.stderr)
            n_skip += 1
            continue
        target = snapshot_dir / f"{date_str}.parquet"
        if target.exists():
            print(f"SKIP {date_str}: already exists")
            n_skip += 1
            continue
        try:
            run_pipeline(date_str, write_report=False)
            print(f"OK   {date_str}")
            n_ok += 1
        except Exception as e:
            # Best-effort backfill: log and continue. T-3-02 carry-forward:
            # log only type, never the exception string (may contain API key URL).
            print(f"FAIL {date_str}: {type(e).__name__}", file=sys.stderr)
            n_fail += 1

    total = n_ok + n_skip + n_fail
    print(f"BACKFILL COMPLETE: ok={n_ok} skip={n_skip} fail={n_fail} (total={total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
