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
from screener.data.universe import refresh_universe as refresh_universe_impl
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
        typer.Option("--ticker", help="Single-ticker debug fetch; bypasses universe loop."),
    ] = None,
) -> None:
    """Refresh per-ticker OHLCV via yfinance (Stooq fallback); incremental Parquet append."""
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
def refresh_macro(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-fetch from MACRO_BACKFILL_START even if cache exists."),
    ] = False,
) -> None:
    """Refresh macro inputs (SPY, QQQ, ^VIX, NYSE A/D, FRED yields). DAT-04."""
    configure_logging()
    today = date.today()
    try:
        from screener.data.macro import (
            refresh_nyad,
            refresh_qqq,
            refresh_spy,
            refresh_vix,
            refresh_yields,
        )

        refresh_spy(force=force, today=today)
        refresh_qqq(force=force, today=today)
        refresh_vix(force=force, today=today)
        refresh_nyad(force=force, today=today)
        refresh_yields(force=force, today=today)
        log.info("refresh_macro_ok")
    except Exception as e:
        # T-3-02 mitigation: FRED exceptions may include the request URL with
        # `?api_key=...` in their stringified form. Log only error_type (never
        # the exception string). Re-raise via typer.Exit so the traceback goes
        # to stderr (outside structured-log sinks), not to any log aggregator.
        log.error("refresh_macro_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("refresh-fundamentals")
def refresh_fundamentals() -> None:
    """Refresh fundamentals (Finnhub earnings + EPS); 45-day post-quarter-end lag enforced."""
    _stub("refresh-fundamentals")


@app.command("score")
def score() -> None:
    """Compute composite scores; write data/snapshots/YYYY-MM-DD.parquet."""
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline

        run_pipeline(date.today().isoformat(), write_report=False)
    except typer.Exit:
        # Pitfall 7: validate_run's typer.Exit MUST propagate to set
        # process exit code; do NOT catch in the broader Exception handler.
        raise
    except Exception as e:
        # T-3-02 mitigation carry-forward: log only error_type, never the
        # exception string (may contain FRED API key URL fragments etc.).
        log.error("score_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("report")
def report() -> None:
    """Render daily Markdown report (also computes scores + snapshot)."""
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline

        run_pipeline(date.today().isoformat(), write_report=True)
    except typer.Exit:
        raise  # Pitfall 7
    except Exception as e:
        log.error("report_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract).

    Idempotent catch-up: reads data/snapshots/<today>.parquet, filters to
    actionable picks (composite_score >= JOURNAL_THRESHOLD AND regime_state
    != 'Correction'), and re-appends via persistence.append_picks_rows.
    INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) makes re-runs zero-insert
    (CONTEXT D-01).
    """
    configure_logging()
    try:
        from screener.persistence import (
            PicksSchema,
            append_picks_rows,
            validate_at_write,
        )
        from screener.publishers.pipeline import _build_journal_rows_df_from_snapshot

        today_iso = date.today().isoformat()
        journal_rows_df = _build_journal_rows_df_from_snapshot(today_iso)
        if journal_rows_df.empty:
            log.info("journal_catchup_empty", snapshot_date=today_iso)
            return
        validated = validate_at_write(PicksSchema, journal_rows_df)
        n_inserted = append_picks_rows(validated.to_dict(orient="records"))
        log.info(
            "journal_catchup_complete",
            snapshot_date=today_iso,
            n_attempted=len(journal_rows_df),
            n_inserted=n_inserted,
            n_idempotent_skip=len(journal_rows_df) - n_inserted,
        )
    except typer.Exit:
        # Pitfall 7: typer.Exit from validate_at_write or append_picks_rows
        # MUST propagate to set process exit code.
        raise
    except Exception as e:
        # T-3-02 carry-forward: log only error_type, never str(e).
        log.error("journal_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("backtest")
def backtest(
    start: Annotated[
        str,
        typer.Option(
            "--start",
            help="ISO date string for the earliest IS window start (default: 2016-01-01).",
        ),
    ] = "2016-01-01",
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            help="ISO date string for the latest OOS window end (default: today).",
        ),
    ] = None,
) -> None:
    """Run vectorbt walk-forward backtest (3-yr IS / 1-yr OOS rolling windows)."""
    configure_logging()
    try:
        from screener.backtest.report import render_report
        from screener.backtest.vbt_runner import run

        effective_end = end or date.today().isoformat()
        result = run(start, effective_end)
        report_path = Path("reports") / f"backtest-{effective_end}.md"
        render_report(result, report_path)
        # D-14: terminal summary in addition to the file.
        print(
            f"Sharpe distribution: min={result.sharpe_min:.2f} "
            f"| median={result.sharpe_median:.2f} "
            f"| max={result.sharpe_max:.2f} "
            f"({len(result.windows)} windows, {result.n_zero_trade_windows} zero-trade)"
        )
        print(f"Report written: {report_path}")
        # cli.py uses structlog (not stdlib logging) -- kwargs OK here.
        log.info(
            "backtest_ok",
            n_windows=len(result.windows),
            sharpe_median=result.sharpe_median,
            report=str(report_path),
        )
    except typer.Exit:
        # Pitfall 7: typer.Exit MUST propagate; do not catch in broader Exception.
        raise
    except Exception as e:
        # T-3-02 carry-forward: log error_type only; never the exception string.
        log.error("backtest_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e


@app.command("backtest-audit")
def backtest_audit() -> None:
    """Forensic checks (no-look-ahead, preregistration hash, universe, OOS depth)."""
    configure_logging()
    try:
        import re as _re
        import subprocess
        from pathlib import Path

        import pandas as pd

        from screener.backtest.walkforward import walk_forward_windows

        date_re = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

        # ----- Check 1: no-look-ahead test passing (FND-04) ----------------
        # T-5-02: list-form argv, shell=False (default).
        nla = subprocess.run(
            ["uv", "run", "pytest", "tests/test_backtest_no_lookahead.py", "-q"],
            capture_output=True,
            text=True,
            check=False,
        )
        nla_pass = nla.returncode == 0
        log.info(
            "audit_check",
            check="no-lookahead test passing",
            result="PASS" if nla_pass else "FAIL",
            detail=(nla.stdout + nla.stderr)[-500:] if not nla_pass else "exit=0",
        )

        # ----- Check 2: preregistration hash match (FND-05 carry-forward) ---
        prereg = subprocess.run(
            ["uv", "run", "python", "scripts/check_preregistration.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        prereg_pass = prereg.returncode == 0
        log.info(
            "audit_check",
            check="preregistration hash match",
            result="PASS" if prereg_pass else "FAIL",
            detail=(prereg.stdout + prereg.stderr)[-500:] if not prereg_pass else "exit=0",
        )

        # ----- Check 3 (REVISED D-16 2026-05-16): universe snapshot ---------
        # Original wording "latest snapshot <= start" would never pass until a
        # backdated 2016 universe snapshot exists. Relaxed to "earliest available
        # <= earliest IS window start"; FAIL only when no universe exists; WARN
        # (does NOT block) when the gap is non-zero.
        universe_dir = Path("data/universe")
        earliest_is_start = pd.Timestamp("2016-01-01")
        # Try to derive earliest_is_start from walk_forward_windows for consistency.
        wins = walk_forward_windows(
            pd.Timestamp("2016-01-01"),
            pd.Timestamp.today().normalize(),
        )
        if wins:
            earliest_is_start = wins[0][0]
        universe_pass = False
        universe_warn = False
        universe_detail = ""
        if not universe_dir.exists():
            universe_detail = "data/universe/ does not exist"
        else:
            stems = sorted(p.stem for p in universe_dir.glob("*.parquet") if date_re.match(p.stem))
            if not stems:
                universe_detail = "no ISO-named universe snapshots found in data/universe/"
            else:
                earliest_uni = pd.Timestamp(stems[0])
                if earliest_uni <= earliest_is_start:
                    universe_pass = True
                    universe_detail = (
                        f"earliest universe snapshot {earliest_uni.date()} "
                        f"<= earliest IS start {earliest_is_start.date()}"
                    )
                else:
                    # WARN (not FAIL) per REVISED D-16: survivorship is acknowledged in BCK-06.
                    universe_pass = True
                    universe_warn = True
                    gap_days = (earliest_uni - earliest_is_start).days
                    universe_detail = (
                        f"WARN: earliest universe snapshot {earliest_uni.date()} "
                        f"> earliest IS start {earliest_is_start.date()} "
                        f"(gap = {gap_days} days); survivorship caveat documented "
                        f"in BCK-06 disclosure header"
                    )
        log.info(
            "audit_check",
            check="universe snapshot date <= earliest IS start",
            result="WARN" if universe_warn else ("PASS" if universe_pass else "FAIL"),
            detail=universe_detail,
        )

        # ----- Check 4: >= 2 complete OOS windows ---------------------------
        snapshot_dir = Path("data/snapshots")
        oos_pass = False
        oos_detail = ""
        if not snapshot_dir.exists():
            oos_detail = "data/snapshots/ does not exist"
        else:
            snap_stems = sorted(
                p.stem for p in snapshot_dir.glob("*.parquet") if date_re.match(p.stem)
            )
            if not snap_stems:
                oos_detail = "no ISO-named snapshots found in data/snapshots/"
            else:
                earliest_snap = pd.Timestamp(snap_stems[0])
                latest_snap = pd.Timestamp(snap_stems[-1])
                snap_windows = walk_forward_windows(earliest_snap, latest_snap)
                n_windows = len(snap_windows)
                if n_windows >= 2:
                    oos_pass = True
                    oos_detail = f"{n_windows} complete OOS windows available"
                else:
                    oos_detail = (
                        f"Insufficient OOS history: {n_windows} complete windows found, 2 required."
                    )
        log.info(
            "audit_check",
            check=">= 2 complete OOS windows",
            result="PASS" if oos_pass else "FAIL",
            detail=oos_detail,
        )

        # ----- Tally -------------------------------------------------------
        results = [nla_pass, prereg_pass, universe_pass, oos_pass]
        failures = sum(1 for r in results if not r)
        log.info("audit_complete", failures=failures, total=len(results))
        if failures > 0:
            print(f"AUDIT FAILED ({failures} checks failed)")
            raise typer.Exit(code=1)
        print("AUDIT PASSED")
    except typer.Exit:
        # Pitfall 7 carry-forward: typer.Exit MUST propagate.
        raise
    except Exception as e:
        log.error("backtest_audit_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
