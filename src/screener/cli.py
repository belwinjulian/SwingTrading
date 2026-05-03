"""cli — typer composition root for the screener console script.

Exposes the v1 subcommand surface (D-14). Phase 1 shipped every subcommand as
a structured-logging no-op; Phase 2 fills in refresh-universe and refresh-ohlcv
with real bodies that orchestrate the data/ layer through persistence. The
remaining 7 subcommands stay as [stub] no-ops until their owning phases land.

The 9-subcommand surface is LOCKED by tests/test_cli_smoke.py D14_SUBCOMMANDS;
this module MUST NOT add or rename a subcommand without coordinating with that
test.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import structlog
import typer

from screener.config import get_settings
from screener.data.ohlcv import (
    fetch_ohlcv,
    fetch_splits,
    run_with_breaker,
)
from screener.data.universe import (
    iso_week_monday,
    refresh_universe as refresh_universe_impl,
)
from screener.obs import configure as configure_logging
from screener.persistence import (
    read_universe,
    write_ohlcv_atomic,
    write_splits_atomic,
)

app = typer.Typer(
    name="screener",
    help="Long-only EOD momentum swing-trading screener (Russell 1000).",
    no_args_is_help=True,
    add_completion=False,
)

log = structlog.get_logger(__name__)


def _stub(command: str) -> None:
    """Log a structured [stub] line and return (exit 0)."""
    configure_logging()
    log.info("stub", command=command, message=f"[stub] {command} not yet implemented")


# --- refresh-universe (Phase 2 real body) -----------------------------------


@app.command("refresh-universe")
def refresh_universe(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-write this ISO week's snapshot even if it exists."),
    ] = False,
) -> None:
    """Refresh the Russell 1000 universe (iShares IWB CSV); weekly Parquet snapshot (D-01, D-02)."""
    configure_logging()
    try:
        written = refresh_universe_impl(force=force, today=date.today())
    except Exception as e:
        log.error("refresh_universe_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
    if written is None:
        # Idempotent skip — already wrote this week.
        log.info("refresh_universe_skipped", reason="snapshot already exists for this ISO week")
    # Exit 0 implicit on successful return.


# --- refresh-ohlcv (Phase 2 real body, with --ticker debug + health gate) ---


def _latest_universe_snapshot() -> Path | None:
    """Return the path of the most-recent data/universe/<date>.parquet, or None."""
    settings = get_settings()
    universe_dir = Path(settings.UNIVERSE_CACHE_DIR)
    if not universe_dir.exists():
        return None
    candidates = sorted(universe_dir.glob("*.parquet"))
    return candidates[-1] if candidates else None


@app.command("refresh-ohlcv")
def refresh_ohlcv(
    ticker: Annotated[
        str | None,
        typer.Option("--ticker", help="Single-ticker debug fetch; bypasses universe loop and gate."),
    ] = None,
) -> None:
    """Refresh per-ticker OHLCV via yfinance (Stooq fallback); incremental Parquet append (DAT-03, DAT-07)."""
    configure_logging()
    settings = get_settings()
    today = date.today()

    # --- Single-ticker debug path ----------------------------------------
    if ticker is not None:
        try:
            df = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
            df = df.rename(columns=str.lower)
            if df.index.name is None or df.index.name.lower() != "date":
                df.index.name = "date"
            write_ohlcv_atomic(ticker, df)
            splits_df = fetch_splits(ticker)
            write_splits_atomic(ticker, splits_df)
            log.info("single_ticker_refresh_ok", ticker=ticker, n_bars=len(df))
        except Exception as e:
            log.error("single_ticker_refresh_failed", ticker=ticker, error=str(e))
            raise typer.Exit(code=1) from e
        return

    # --- Universe path with 95% health gate ------------------------------
    snapshot = _latest_universe_snapshot()
    if snapshot is None:
        log.error(
            "refresh_ohlcv_no_universe",
            message="No data/universe/<date>.parquet found; run `screener refresh-universe` first.",
        )
        raise typer.Exit(code=1)

    snapshot_date = snapshot.stem  # "2026-04-27"
    universe = read_universe(snapshot_date)
    tickers = universe["ticker"].tolist()
    n_universe = len(tickers)

    yf_ok, stooq_ok, failed = run_with_breaker(tickers, today)
    combined_ok = yf_ok + stooq_ok
    ratio = combined_ok / n_universe if n_universe > 0 else 0.0
    threshold = settings.UNIVERSE_HEALTH_THRESHOLD

    if ratio < threshold:
        log.error(
            "health_check_failed",
            success_count=combined_ok,
            universe_size=n_universe,
            ratio=ratio,
            threshold=threshold,
            failed_tickers=failed[:20],
        )
        raise typer.Exit(code=1)

    log.info(
        "health_check_passed",
        success_count=combined_ok,
        universe_size=n_universe,
        ratio=ratio,
        threshold=threshold,
    )


# --- Phase 1 stubs preserved verbatim --------------------------------------


@app.command("refresh-macro")
def refresh_macro() -> None:
    """Refresh macro inputs (SPY, ^IXIC, ^VIX, NYSE A/D, FRED yields)."""
    _stub("refresh-macro")


@app.command("refresh-fundamentals")
def refresh_fundamentals() -> None:
    """Refresh fundamentals (Finnhub earnings + EPS); 45-day post-quarter-end lag enforced."""
    _stub("refresh-fundamentals")


@app.command("score")
def score() -> None:
    """Compute composite scores + playbook tags; write data/snapshots/YYYY-MM-DD.parquet."""
    _stub("score")


@app.command("report")
def report() -> None:
    """Render the daily Markdown report to reports/YYYY-MM-DD.md."""
    _stub("report")


@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract)."""
    _stub("journal")


@app.command("backtest")
def backtest() -> None:
    """Run vectorbt walk-forward backtest (3-yr IS / 1-yr OOS rolling windows)."""
    _stub("backtest")


@app.command("backtest-audit")
def backtest_audit() -> None:
    """Run forensic checks (no-look-ahead, weight-preregistration hash, universe snapshot)."""
    _stub("backtest-audit")
