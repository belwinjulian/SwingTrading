"""backtest/vbt_runner - vectorbt 1.0 walk-forward harness entry point.

Architectural contract (D-17, RESEARCH section E L12): persistence + stdlib only.
Uses stdlib logging - NEVER structlog. Reads pre-computed signals from
``data/snapshots/<date>.parquet`` via stdlib ``pd.read_parquet`` (no signals/
import). Reads OHLCV via ``persistence.read_panel`` (the single allowed internal
import).

LOGGING DISCIPLINE (B-1 fix iter 2): stdlib ``logging.Logger.<level>()`` does
NOT accept arbitrary kwargs (would raise ``TypeError: Logger._log() got an
unexpected keyword argument``). All log lines use f-string form (preformatted
message strings) - NEVER the structlog-style ``log.info(event, key=value)``
call signature, which raises ``TypeError`` on the stdlib Logger.

FND-04 / BCK-02 enforcement: signals execute at next-bar open via
``.shift(1, fill_value=False)``. The literal ``if _lookahead: ... else: ...``
block in ``run()`` is the mutation surface - DO NOT refactor it into a helper.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

from screener.backtest.walkforward import walk_forward_windows
from screener.persistence import read_panel  # ONLY allowed internal import

log = logging.getLogger(__name__)

# BCK-03 / D-11 tier table - defined ONCE, consumed by _build_slippage_panel
# AND by the report's disclosure header (single source of truth - Pitfall 7).
SLIPPAGE_TIERS: tuple[tuple[float, float], ...] = (
    (50_000_000.0, 0.0005),  # ADV > $50M -> 5 bps
    (5_000_000.0, 0.0015),  # $5M <= ADV <= $50M -> 15 bps
    (0.0, 0.0030),  # ADV < $5M -> 30 bps  (also the NaN-warmup default)
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# B-3 fix: canonical empty regime_returns DataFrame (long format).
_EMPTY_REGIME_RETURNS: pd.DataFrame = pd.DataFrame(
    {
        "date": pd.Series(dtype="datetime64[ns]"),
        "regime_state": pd.Series(dtype="object"),
        "daily_return": pd.Series(dtype="float64"),
    }
)


@dataclass(frozen=True)
class WindowResult:
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    oos_sharpe: float
    oos_max_dd: float
    oos_win_rate: float
    oos_total_return: float
    n_trades: int
    # B-3 fix: per-bar regime + daily portfolio return for the OOS slice.
    # Long-format DataFrame with columns [date, regime_state, daily_return].
    # Built by joining vbt.Portfolio.returns() with snapshots[regime_state]
    # date-wise. Plan 05-03 concatenates these across windows for the
    # BCK-05 per-regime breakdown table.
    regime_returns: pd.DataFrame = field(default_factory=lambda: _EMPTY_REGIME_RETURNS.copy())


@dataclass(frozen=True)
class BacktestResult:
    windows: list[WindowResult]
    sharpe_min: float
    sharpe_median: float
    sharpe_max: float
    total_return: float  # geometric composite OOS return across windows
    n_zero_trade_windows: int
    # B-3 fix: concatenation of all windows' regime_returns (long format).
    # Consumed by plan 05-03's `_render_per_regime_section` which calls
    # `metrics.per_regime_breakdown(all_regime_returns)`.
    all_regime_returns: pd.DataFrame = field(default_factory=lambda: _EMPTY_REGIME_RETURNS.copy())


def _validate_date(date_str: str) -> None:
    """Reject any non-ISO date string (T-5-01 mitigation against path traversal)."""
    if not isinstance(date_str, str) or not _DATE_RE.match(date_str):
        raise ValueError(f"Invalid date string {date_str!r}; expected YYYY-MM-DD format.")


def _build_slippage_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """ADV-tiered slippage panel; same shape as the close panel (date x ticker).

    BCK-03 / D-10 / D-11 tiers (verbatim)::

        ADV > $50M           -> 0.0005 (5 bps)
        $5M <= ADV <= $50M   -> 0.0015 (15 bps)
        ADV < $5M            -> 0.0030 (30 bps)

    RESEARCH section E L1 / L5: first 19 bars of every ticker have NaN ADV
    (rolling 20-bar window not warm). Fill with 0.0030 (worst tier) - the
    defensive default. vectorbt rejects NaN in ``slippage``.
    """
    close = panel["close"].unstack(level="ticker")  # noqa: PD010
    volume = panel["volume"].unstack(level="ticker").astype("float64")  # noqa: PD010
    adv_20d = (close * volume).rolling(20, min_periods=20).mean()
    # Tier mapping via np.where chain (vectorized, no apply).
    slip = np.where(
        adv_20d > 50_000_000.0,
        0.0005,
        np.where(adv_20d >= 5_000_000.0, 0.0015, 0.0030),
    )
    slippage_panel = pd.DataFrame(slip, index=close.index, columns=close.columns)
    # Fill NaN-ADV warmup bars with the worst tier (RESEARCH section E L1).
    slippage_panel = slippage_panel.where(adv_20d.notna(), 0.0030)
    return slippage_panel


def _read_snapshot(snapshot_date: str) -> pd.DataFrame:
    """Read ``data/snapshots/<date>.parquet`` via stdlib ``pd.read_parquet``.

    Lives in vbt_runner.py (not persistence) so the FND-04 monkeypatch seam
    is well-defined - plan 05-02 patches
    ``screener.backtest.vbt_runner._read_snapshot``.
    """
    _validate_date(snapshot_date)
    snapshot_dir = Path("data/snapshots")
    target = snapshot_dir / f"{snapshot_date}.parquet"
    if not target.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {target}. Run `make backfill-snapshots` first."
        )
    return pd.read_parquet(target)


def _load_snapshots_in_range(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Read every ``data/snapshots/YYYY-MM-DD.parquet`` whose stem date falls
    in ``[start, end]``.

    RESEARCH section E L10: hard-fail if ``data/snapshots/`` does not exist or
    is empty - the user must run ``make backfill-snapshots`` first.
    """
    snap_dir = Path("data/snapshots")
    if not snap_dir.exists() or not any(snap_dir.glob("*.parquet")):
        raise RuntimeError(
            "No snapshots found in data/snapshots/. Run `make backfill-snapshots` first."
        )
    frames: list[pd.DataFrame] = []
    for p in sorted(snap_dir.glob("*.parquet")):
        # T-5-01 mitigation: validate stem matches YYYY-MM-DD before
        # pd.Timestamp() parse.
        if not _DATE_RE.match(p.stem):
            # B-1 fix: stdlib logger - no **kwargs. Use f-string form.
            log.warning(f"skipping_non_iso_snapshot file={p.name}")
            continue
        date = pd.Timestamp(p.stem)
        if not (start <= date <= end):
            continue
        df = pd.read_parquet(p)
        df["date"] = date
        frames.append(df)
    if not frames:
        raise RuntimeError(
            f"No snapshots in date range [{start.date()}..{end.date()}]. "
            "Run `make backfill-snapshots` first."
        )
    snapshot = pd.concat(frames, ignore_index=True)
    # L15: defensive non-null regime_state check.
    if "regime_state" in snapshot.columns and snapshot["regime_state"].isna().any():
        raise RuntimeError("Snapshot has NaN regime_state - backfill data is corrupt.")
    return snapshot


def _build_regime_returns_for_window(
    pf: vbt.Portfolio,
    snapshots: pd.DataFrame,
    oos_start: pd.Timestamp,
    oos_end: pd.Timestamp,
) -> pd.DataFrame:
    """Build a long-format ``(date, regime_state, daily_return)`` frame for one
    OOS window.

    B-3 fix iter 2: per-day regime attribution sourced from
    ``snapshots[regime_state]`` (D-13). ``regime_state`` is one of
    ``{'Confirmed Uptrend', 'Uptrend Under Pressure', 'Correction'}`` and is
    per-date (universe-wide), not per-trade - Phase 4's publisher writes ONE
    regime per snapshot date. We pick the modal regime per date (handles cases
    where the same date appears in multiple snapshot rows, e.g., one row per
    ticker).

    C-2 fix iter 3: the previous broad try/except graceful-degradation around
    ``pf.returns()`` is REPLACED with a hard ``assert isinstance(...)`` citing
    RESEARCH section A Q11. Rationale: a real vbt API shape change should fail
    LOUDLY rather than silently rendering empty regime rows in the
    user-facing backtest report. Legitimate empty-window cases (e.g., the
    OOS slice has no matching snapshot rows) still return the canonical
    empty DataFrame - only ``pf.returns()`` shape changes trigger the assert.
    """
    # C-2 fix iter 3: HARD assert on the returns API shape. NO try/except.
    pf_returns = pf.returns()
    assert isinstance(pf_returns, (pd.Series, pd.DataFrame)), (
        f"vbt.Portfolio.returns() returned unexpected type {type(pf_returns)} - "
        f"see 05-RESEARCH.md §A Q11. If vbt's API has changed, update this helper "
        f"to handle the new shape rather than silently rendering empty regime rows."
    )

    # vbt.Portfolio.returns() returns a DataFrame (cols=tickers/groups) or
    # Series. Collapse to a single per-bar portfolio return. (Series vs
    # DataFrame branching is preserved for legitimate single-vs-multi-ticker
    # handling.)
    if isinstance(pf_returns, pd.DataFrame):
        # cash_sharing=True + group_by=all-zeros -> single group column; take it.
        if pf_returns.shape[1] > 0:
            daily_returns = pf_returns.iloc[:, 0]
        else:
            daily_returns = pd.Series(dtype="float64")
    else:
        daily_returns = pf_returns

    if daily_returns.empty:
        return _EMPTY_REGIME_RETURNS.copy()

    # Slice snapshots to the OOS window and pick the modal regime per date.
    snap_window = snapshots[(snapshots["date"] >= oos_start) & (snapshots["date"] <= oos_end)]
    if snap_window.empty or "regime_state" not in snap_window.columns:
        return _EMPTY_REGIME_RETURNS.copy()
    regime_by_date = snap_window.groupby("date")["regime_state"].agg(
        lambda s: s.mode().iloc[0] if not s.mode().empty else None
    )
    # Align daily_returns to regime_by_date by date.
    df = pd.DataFrame({"daily_return": daily_returns})
    df.index.name = "date"
    df = df.reset_index()
    df = df.merge(
        regime_by_date.rename("regime_state"),
        left_on="date",
        right_index=True,
        how="left",
    )
    df = df.dropna(subset=["regime_state"])
    return df[["date", "regime_state", "daily_return"]].reset_index(drop=True)


def run(start: str, end: str, *, _lookahead: bool = False) -> BacktestResult:
    """Walk-forward backtest entry point (BCK-01).

    Args:
        start: ISO date string, e.g. ``'2016-01-01'``.
        end:   ISO date string, e.g. ``'2025-12-31'``.
        _lookahead: FND-04 mutation-test backdoor - keyword-only,
            underscore-prefixed. NEVER use from production code. When True,
            signals execute on the SAME bar (no ``.shift(1)``) - proves the
            gate by producing wild outperformance against perfect-foresight
            signals.

    Returns:
        BacktestResult with per-window stats + OOS Sharpe distribution +
        ``all_regime_returns`` (B-3: long-format DataFrame consumed by plan
        05-03's BCK-05 renderer).

    Raises:
        ValueError:    on malformed date strings (T-5-01).
        RuntimeError:  when ``data/snapshots/`` is empty (L10) or corrupt (L15).
    """
    _validate_date(start)
    _validate_date(end)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    windows = walk_forward_windows(start_ts, end_ts)
    # B-1 fix: stdlib logging - f-string form, NEVER **kwargs.
    log.info(f"run_start start={start} end={end} n_windows={len(windows)} lookahead={_lookahead}")

    # Load assembled OHLCV panel + snapshots ONCE; slice per-window.
    panel = read_panel(end)  # most-recent universe (A2 assumption per RESEARCH)
    snapshots = _load_snapshots_in_range(start_ts, end_ts)

    close = panel["close"].unstack(level="ticker")  # noqa: PD010
    open_panel = panel["open"].unstack(level="ticker")  # noqa: PD010
    slippage_panel = _build_slippage_panel(panel)

    # Entries: passes_trend_template = True (snapshot column from Phase 4).
    # W-3: explicit aggfunc='first' to avoid mean-coercion of bool columns.
    raw_entries = snapshots.pivot_table(
        index="date",
        columns="ticker",
        values="passes_trend_template",
        fill_value=False,
        aggfunc="first",
    ).astype(bool)
    # Reindex to the close-panel index so .loc slices align
    # (RESEARCH section E L4).
    raw_entries = raw_entries.reindex(index=close.index, columns=close.columns, fill_value=False)
    raw_exits = (~raw_entries) & raw_entries.shift(1, fill_value=False)
    # Edge-trigger entries (avoid re-entry on every bar a True signal persists).
    raw_entries_clean = raw_entries & ~raw_entries.shift(1, fill_value=False)

    # ----- FND-04 / BCK-02 MUTATION SURFACE - DO NOT REFACTOR ------------
    # The literal `if _lookahead: ... else: ...` block below is the line that
    # the FND-04 test (tests/test_backtest_no_lookahead.py) defends. Removing
    # `.shift(1, fill_value=False)` from the `else` branch is equivalent to
    # hardcoding `_lookahead=True` - the test will catch it.
    if _lookahead:
        entries_exec = raw_entries_clean
        exits_exec = raw_exits
    else:
        entries_exec = raw_entries_clean.shift(1, fill_value=False).astype(bool)
        exits_exec = raw_exits.shift(1, fill_value=False).astype(bool)
    # ----------------------------------------------------------------------

    window_results: list[WindowResult] = []
    per_window_regime_frames: list[pd.DataFrame] = []
    for is_s, is_e, oos_s, oos_e in windows:
        sl = slice(oos_s, oos_e)
        # RESEARCH section E L4: always slice by Timestamp (.loc), never by
        # integer (.iloc).
        try:
            pf = vbt.Portfolio.from_signals(
                close=close.loc[sl],
                entries=entries_exec.loc[sl],
                exits=exits_exec.loc[sl],
                price=open_panel.loc[sl],
                slippage=slippage_panel.loc[sl],
                direction="longonly",  # L13: ALWAYS pass explicitly
                init_cash=100_000.0,
                cash_sharing=True,
                group_by=np.zeros(close.shape[1], dtype=int),  # L6
                fees=0.0,
                size=0.05,
                size_type="value",
                freq="1D",
            )
        except Exception as e:
            # B-1 fix: stdlib logger - f-string form, NEVER **kwargs.
            log.error(f"window_failed window_start={oos_s.date()} error_type={type(e).__name__}")
            raise

        n_trades = int(pf.trades.count())
        sharpe_val = float(pf.sharpe_ratio()) if n_trades > 0 else float("nan")
        win_rate_val = float(pf.trades.win_rate()) if n_trades > 0 else 0.0

        # B-3 fix: per-day regime + portfolio return for the OOS slice.
        # C-2 fix iter 3: the helper now uses a hard assert, not try/except.
        window_regime_returns = _build_regime_returns_for_window(pf, snapshots, oos_s, oos_e)
        per_window_regime_frames.append(window_regime_returns)

        window_results.append(
            WindowResult(
                is_start=is_s,
                is_end=is_e,
                oos_start=oos_s,
                oos_end=oos_e,
                oos_sharpe=sharpe_val,
                oos_max_dd=float(pf.max_drawdown()),
                oos_win_rate=win_rate_val,
                oos_total_return=float(pf.total_return()),
                n_trades=n_trades,
                regime_returns=window_regime_returns,
            )
        )

    sharpes = pd.Series([w.oos_sharpe for w in window_results], dtype="float64")
    clean_sharpes = sharpes.dropna()
    n_zero = int(sharpes.isna().sum())
    total_ret = float((1.0 + pd.Series([w.oos_total_return for w in window_results])).prod() - 1.0)

    # B-3 fix: concatenate per-window regime_returns into a single long
    # DataFrame.
    if per_window_regime_frames:
        all_regime_returns = pd.concat(per_window_regime_frames, ignore_index=True)
    else:
        all_regime_returns = _EMPTY_REGIME_RETURNS.copy()

    result = BacktestResult(
        windows=window_results,
        sharpe_min=float(clean_sharpes.min()) if len(clean_sharpes) > 0 else float("nan"),
        sharpe_median=(float(clean_sharpes.median()) if len(clean_sharpes) > 0 else float("nan")),
        sharpe_max=float(clean_sharpes.max()) if len(clean_sharpes) > 0 else float("nan"),
        total_return=total_ret,
        n_zero_trade_windows=n_zero,
        all_regime_returns=all_regime_returns,
    )
    # B-1 fix: stdlib logger - f-string form, NEVER **kwargs.
    log.info(
        f"run_complete n_windows={len(windows)} "
        f"sharpe_min={result.sharpe_min} sharpe_median={result.sharpe_median} "
        f"sharpe_max={result.sharpe_max} total_return={result.total_return} "
        f"n_zero_trade_windows={result.n_zero_trade_windows}"
    )
    return result
