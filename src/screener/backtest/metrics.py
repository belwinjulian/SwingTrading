"""backtest/metrics - cross-window aggregation of vectorbt Portfolio results.

Architectural contract (D-17): persistence + stdlib only. Uses stdlib logging
(NOT structlog - see RESEARCH section E L12). All log calls use f-string form
(stdlib Logger does NOT accept arbitrary kwargs - B-1 fix iter 2).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Canonical regime list (B-3 fix iter 2). Source: persistence.RankingSnapshotSchema
# regime_state field. metrics.per_regime_breakdown always reindexes against this
# list so every backtest report shows all 3 rows, even if some are empty.
CANONICAL_REGIMES: tuple[str, ...] = (
    "Confirmed Uptrend",
    "Uptrend Under Pressure",
    "Correction",
)


def oos_sharpe_distribution(
    per_window_sharpes: list[float],
) -> dict[str, float | int]:
    """Aggregate per-window OOS Sharpe ratios into (min, median, max).

    BCK-01: OOS Sharpe distribution is the reported metric, not a single value.
    RESEARCH section E L16: filter NaN Sharpe (zero-trade windows) before
    aggregation; report n_zero_trade_windows separately so the user sees the
    denominator.

    Args:
        per_window_sharpes: One float per window; NaN for zero-trade windows.

    Returns:
        ``{'min', 'median', 'max', 'n_zero_trade_windows', 'n_windows'}`` dict.
    """
    series = pd.Series(per_window_sharpes, dtype="float64")
    n_total = len(series)
    n_nan = int(series.isna().sum())
    clean = series.dropna()
    if len(clean) == 0:
        return {
            "min": float("nan"),
            "median": float("nan"),
            "max": float("nan"),
            "n_zero_trade_windows": n_nan,
            "n_windows": n_total,
        }
    return {
        "min": float(clean.min()),
        "median": float(clean.median()),
        "max": float(clean.max()),
        "n_zero_trade_windows": n_nan,
        "n_windows": n_total,
    }


def per_regime_breakdown(
    regime_returns: pd.DataFrame,
    regime_col: str = "regime_state",
    return_col: str = "daily_return",
) -> pd.DataFrame:
    """Group per-day OOS portfolio returns by regime_state (BCK-05, D-13).

    REVISED (B-3 fix iter 2): operates on the long-format DataFrame produced by
    vbt_runner (cols [date, regime_state, daily_return]) - NOT on a per-trade
    DataFrame. The data lives in BacktestResult.all_regime_returns (built per
    window by joining vbt.Portfolio.returns() with snapshots[regime_state]).

    Always returns 3 rows indexed by the canonical regime list. Empty regimes
    (no OOS days observed) get n_days=0 and NaN for total_return/sharpe/win_rate.

    Args:
        regime_returns: Long-format DataFrame with columns
            ``[date, regime_state, daily_return]``.
        regime_col:    Column name of the regime state (default 'regime_state').
        return_col:    Column name of the daily portfolio return (default 'daily_return').

    Returns:
        DataFrame indexed by regime_state (3 canonical rows in CANONICAL_REGIMES order)
        with columns ``[n_days, total_return, sharpe, win_rate]``.
    """
    empty_template = pd.DataFrame(
        {
            "n_days": [0, 0, 0],
            "total_return": [float("nan")] * 3,
            "sharpe": [float("nan")] * 3,
            "win_rate": [float("nan")] * 3,
        },
        index=pd.Index(list(CANONICAL_REGIMES), name=regime_col),
    )
    if regime_returns is None or regime_returns.empty:
        return empty_template
    if regime_col not in regime_returns.columns or return_col not in regime_returns.columns:
        return empty_template

    rows: list[dict[str, float | int]] = []
    for regime in CANONICAL_REGIMES:
        subset = regime_returns.loc[regime_returns[regime_col] == regime, return_col]
        subset = subset.dropna()
        n_days = len(subset)
        if n_days == 0:
            rows.append(
                {
                    "n_days": 0,
                    "total_return": float("nan"),
                    "sharpe": float("nan"),
                    "win_rate": float("nan"),
                }
            )
            continue
        # Geometric compounding of daily returns.
        total_return = float(np.prod(1.0 + subset.to_numpy()) - 1.0)
        std = float(subset.std(ddof=0))
        # Annualized Sharpe (252 trading days, no risk-free rate offset).
        if std == 0.0 or math.isnan(std):
            sharpe = float("nan")
        else:
            sharpe = float(subset.mean() / std * math.sqrt(252))
        win_rate = float((subset > 0).mean())
        rows.append(
            {
                "n_days": n_days,
                "total_return": total_return,
                "sharpe": sharpe,
                "win_rate": win_rate,
            }
        )
    out = pd.DataFrame(rows, index=pd.Index(list(CANONICAL_REGIMES), name=regime_col))
    return out


def per_playbook_breakdown(
    trades: pd.DataFrame,
    playbook_col: str = "playbook_tag",
) -> pd.DataFrame:
    """Group OOS trade outcomes by playbook_tag (BCK-04).

    Phase 5 stub (D-12): all picks are tagged 'leader_hold'. Phase 6 adds
    real 'qullamaggie_continuation' and 'minervini_vcp' rows without
    structural refactor - same groupby code path.
    """
    if trades.empty or playbook_col not in trades.columns:
        return pd.DataFrame(
            columns=[
                "n_trades",
                "total_return",
                "mean_return",
                "win_rate",
                "profit_factor",
                "expectancy",
            ]
        )
    grouped = trades.groupby(playbook_col)["pnl_pct"]
    n = grouped.count()
    total = grouped.sum()
    mean = grouped.mean()
    win_rate = grouped.apply(lambda s: float((s > 0).mean()))
    profit_factor = grouped.apply(
        lambda s: (
            float(s[s > 0].sum() / -s[s < 0].sum())
            if (s < 0).any() and s[s < 0].sum() != 0
            else float("inf")
        )
    )
    expectancy = mean  # mean per-trade pnl_pct
    return pd.DataFrame(
        {
            "n_trades": n,
            "total_return": total,
            "mean_return": mean,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
        }
    )


@dataclass(frozen=True)
class _AggregatedStats:
    """Internal handoff struct between per-window aggregation and report rendering."""

    sharpe_min: float
    sharpe_median: float
    sharpe_max: float
    n_zero_trade_windows: int
    n_windows: int
