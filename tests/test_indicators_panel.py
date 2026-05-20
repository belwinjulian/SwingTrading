"""build_panel integration tests (IND-01, D-07, D-08)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from screener.indicators import build_panel
from screener.persistence import write_ohlcv_atomic, write_universe_atomic

REQUIRED_NEW_COLS = {
    "sma_10",
    "sma_20",
    "sma_50",
    "sma_150",
    "sma_200",
    "atr_14",
    "adr_pct",
    "obv",
    "dryup_ratio",
    "rs_raw",
    "rs_rating",
    "high_52w",
    "low_52w",
}


def _make_universe_df(tickers: list[str]) -> pd.DataFrame:
    """Build a UniverseSchema-compliant DataFrame (all required columns)."""
    return pd.DataFrame(
        {
            "ticker": tickers,
            "ticker_raw": tickers,
            "name": [f"{t} Co" for t in tickers],
            "sector": ["Information Technology"] * len(tickers),
            "weight_pct": [0.1] * len(tickers),
        }
    )


def _setup_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: tmp_path / "ohlcv")
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: tmp_path / "universe")


def test_build_panel_returns_10_new_cols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_multi_ticker_panel: pd.DataFrame,
) -> None:
    _setup_persistence(tmp_path, monkeypatch)
    tickers = list(synthetic_multi_ticker_panel.index.get_level_values("ticker").unique())
    for ticker in tickers:
        ticker_df = synthetic_multi_ticker_panel.xs(ticker, level="ticker", drop_level=False)
        write_ohlcv_atomic(ticker, ticker_df.droplevel("ticker"))
    write_universe_atomic(_make_universe_df(tickers), "2026-04-27")
    panel = build_panel("2026-04-27")
    new = set(panel.columns) - {"open", "high", "low", "close", "volume"}
    missing = REQUIRED_NEW_COLS - new
    assert not missing, f"build_panel missing IND-01 columns: {missing}"


def test_build_panel_preserves_multiindex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_multi_ticker_panel: pd.DataFrame,
) -> None:
    _setup_persistence(tmp_path, monkeypatch)
    tickers = list(synthetic_multi_ticker_panel.index.get_level_values("ticker").unique())
    for ticker in tickers:
        ticker_df = synthetic_multi_ticker_panel.xs(ticker, level="ticker", drop_level=False)
        write_ohlcv_atomic(ticker, ticker_df.droplevel("ticker"))
    write_universe_atomic(_make_universe_df(tickers), "2026-04-27")
    panel = build_panel("2026-04-27")
    assert panel.index.names == ["ticker", "date"]


def test_build_panel_high_52w_low_52w_per_ticker_rolling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_multi_ticker_panel: pd.DataFrame,
) -> None:
    """high_52w[t=-1] == max(high[t in last 252 bars]), per-ticker (no MultiIndex bleed)."""
    _setup_persistence(tmp_path, monkeypatch)
    tickers = list(synthetic_multi_ticker_panel.index.get_level_values("ticker").unique())
    for ticker in tickers:
        ticker_df = synthetic_multi_ticker_panel.xs(ticker, level="ticker", drop_level=False)
        write_ohlcv_atomic(ticker, ticker_df.droplevel("ticker"))
    write_universe_atomic(_make_universe_df(tickers), "2026-04-27")
    panel = build_panel("2026-04-27")

    for ticker in tickers:
        ticker_data = panel.xs(ticker, level="ticker")
        # high_52w at the last bar must equal max(high) over last 252 bars
        expected_high = ticker_data["high"].iloc[-252:].max()
        actual_high = ticker_data["high_52w"].iloc[-1]
        assert abs(actual_high - expected_high) < 1e-9, (
            f"{ticker}: high_52w={actual_high} != expected={expected_high}"
        )
        # low_52w at the last bar must equal min(low) over last 252 bars
        expected_low = ticker_data["low"].iloc[-252:].min()
        actual_low = ticker_data["low_52w"].iloc[-1]
        assert abs(actual_low - expected_low) < 1e-9, (
            f"{ticker}: low_52w={actual_low} != expected={expected_low}"
        )


def test_short_history_nan_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_short_history_panel: pd.DataFrame,
) -> None:
    """D-08: 50-bar ticker has valid sma_10..50 but NaN sma_150/200/rs_rating."""
    _setup_persistence(tmp_path, monkeypatch)
    short = synthetic_short_history_panel
    write_ohlcv_atomic("SHORT", short.droplevel("ticker"))
    write_universe_atomic(_make_universe_df(["SHORT"]), "2026-04-27")
    panel = build_panel("2026-04-27")
    last = panel.iloc[-1]
    assert pd.notna(last["sma_50"])
    assert pd.isna(last["sma_150"])
    assert pd.isna(last["sma_200"])
    assert pd.isna(last["rs_rating"]) or last["rs_rating"] is pd.NA
