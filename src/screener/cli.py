"""cli — typer composition root for the screener console script.

Exposes the v1 subcommand surface (D-14). Phase 1 ships every subcommand as a
structured-logging no-op; later phases fill in the bodies. The Makefile in
Plan 04 shells out to these subcommands.
"""

import structlog
import typer

from screener.obs import configure as configure_logging

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


@app.command("refresh-universe")
def refresh_universe() -> None:
    """Refresh the Russell 1000 universe (Wikipedia + iShares IWB); weekly Parquet snapshot."""
    _stub("refresh-universe")


@app.command("refresh-ohlcv")
def refresh_ohlcv() -> None:
    """Refresh OHLCV via yfinance (Stooq fallback); incremental per-ticker Parquet append."""
    _stub("refresh-ohlcv")


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
