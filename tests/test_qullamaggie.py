"""Qullamaggie Setup A scan — SIG-02 / D-13.

Plan 06-04 (Wave 2) replaces every pytest.skip with a real assertion that
exercises the passes_qullamaggie_setup_a(panel) signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from screener.signals.qullamaggie import (
    passes_qullamaggie_setup_a,
)


def _make_panel(
    n_tickers: int = 100,
    n_bars: int = 200,
    seed: int = 42,
    close_scale: float = 50.0,
    volume: float = 20.0,  # close~50 * volume=20 = $1000 ADV (well below $1.5M)
    adr_pct: float = 5.0,
) -> pd.DataFrame:
    """Build a synthetic (n_tickers x n_bars) MultiIndex panel.

    Default volume=20 ensures close*volume << $1.5M threshold so the dollar-volume
    gate fails by default — allowing individual tests to isolate each condition.
    """
    rng = np.random.default_rng(seed=seed)
    tickers = [f"T{i:03d}" for i in range(n_tickers)]
    dates = pd.bdate_range("2024-01-01", periods=n_bars)
    rows = []
    for t in tickers:
        base = close_scale
        for d in dates:
            base *= 1.0 + rng.normal(0.0005, 0.015)
            rows.append(
                {
                    "ticker": t,
                    "date": d,
                    "close": base,
                    "volume": volume,
                    "adr_pct": adr_pct,
                }
            )
    df = pd.DataFrame(rows).set_index(["ticker", "date"]).sort_index()
    return df


def test_setup_a_top_2pct_filter() -> None:
    """SIG-02 percentile gate: ticker with top-2% 3m return + high ADV + high ADR passes;
    other tickers fail because their ADV (close*20 ~ $1000) is far below $1.5M.
    """
    panel = _make_panel(n_tickers=100, n_bars=200, volume=20.0)
    tickers = panel.index.get_level_values("ticker").unique().tolist()
    dates = panel.index.get_level_values("date").unique().sort_values()
    last_date = dates[-1]

    hero_ticker = tickers[0]
    hero_dates = dates[-40:]
    # Inflate close for hero ticker so its 3m pct_change is dominant in the universe
    for i, d in enumerate(hero_dates):
        panel.loc[(hero_ticker, d), "close"] = 500.0 + i * 50.0

    # Hero has high dollar volume: close~2400 * volume=10000 = $24M >> $1.5M
    panel.loc[hero_ticker, "volume"] = 10_000.0
    panel.loc[hero_ticker, "adr_pct"] = 6.0

    out = passes_qullamaggie_setup_a(panel)

    # Hero ticker should pass
    hero_score = out.loc[(hero_ticker, last_date), "qullamaggie_score"]
    assert hero_score == 1, (
        f"Expected hero ticker '{hero_ticker}' to have qullamaggie_score=1, got {hero_score}"
    )

    # Other tickers have volume=20, close~50-200 => dollar_volume~1000-4000 << $1.5M
    # They should all fail the ADV gate regardless of their return rank
    other_tickers = tickers[1:]
    passing_others = [t for t in other_tickers if out.loc[(t, last_date), "qullamaggie_score"] == 1]
    assert len(passing_others) == 0, (
        f"Expected no other tickers to pass (ADV << $1.5M), "
        f"but {len(passing_others)} did: {passing_others[:5]}"
    )


def test_setup_a_dollar_volume_filter() -> None:
    """SIG-02 liquidity gate: ADV < $1.5M fails even with top RS + high ADR%."""
    panel = _make_panel(n_tickers=100, n_bars=200, volume=20.0)
    tickers = panel.index.get_level_values("ticker").unique().tolist()
    dates = panel.index.get_level_values("date").unique().sort_values()
    last_date = dates[-1]

    hero_ticker = tickers[5]
    hero_dates = dates[-40:]
    # Give dominant returns (top 2%)
    for i, d in enumerate(hero_dates):
        panel.loc[(hero_ticker, d), "close"] = 500.0 + i * 50.0
    panel.loc[hero_ticker, "adr_pct"] = 8.0
    # Keep volume low: close~2400, volume=1 => avg dollar_vol ~ $2400 >> wait, that's enough
    # Need volume s.t. close * volume << $1.5M. Close ~2400, so volume = 0.5 => $1200 < $1.5M
    panel.loc[hero_ticker, "volume"] = 0.5

    out = passes_qullamaggie_setup_a(panel)

    score = out.loc[(hero_ticker, last_date), "qullamaggie_score"]
    assert score == 0, (
        f"Expected ticker with low ADV (close*0.5 ~ $1200) to fail dollar_volume gate, "
        f"got qullamaggie_score={score}"
    )


def test_setup_a_adr_pct_filter() -> None:
    """SIG-02 ADR%(20) gate: ADR%=3.5 (below 4) is rejected even with top return + high ADV."""
    panel = _make_panel(n_tickers=100, n_bars=200, volume=20.0)
    tickers = panel.index.get_level_values("ticker").unique().tolist()
    dates = panel.index.get_level_values("date").unique().sort_values()
    last_date = dates[-1]

    hero_ticker = tickers[10]
    hero_dates = dates[-40:]
    for i, d in enumerate(hero_dates):
        panel.loc[(hero_ticker, d), "close"] = 500.0 + i * 50.0
    # High dollar volume: close~2400 * volume=10000 = $24M >> $1.5M
    panel.loc[hero_ticker, "volume"] = 10_000.0
    # Low ADR% below the 4.0 threshold
    panel.loc[hero_ticker, "adr_pct"] = 3.5

    out = passes_qullamaggie_setup_a(panel)

    score = out.loc[(hero_ticker, last_date), "qullamaggie_score"]
    assert score == 0, (
        f"Expected ticker with ADR%=3.5 (below 4.0 threshold) to fail adr_pct gate, "
        f"got qullamaggie_score={score}"
    )


def test_setup_a_combined_and_gate() -> None:
    """SIG-02 AND-gate: score=1 when ALL three conditions True; flips to 0 if any fails."""
    panel = _make_panel(n_tickers=100, n_bars=200, volume=20.0)
    tickers = panel.index.get_level_values("ticker").unique().tolist()
    dates = panel.index.get_level_values("date").unique().sort_values()
    last_date = dates[-1]

    hero_ticker = tickers[20]
    hero_dates = dates[-40:]

    # Inflate close for dominant return
    for i, d in enumerate(hero_dates):
        panel.loc[(hero_ticker, d), "close"] = 500.0 + i * 50.0

    # Condition 2 (ADV): high dollar volume (close~2400 * 10000 = $24M >> $1.5M)
    panel.loc[hero_ticker, "volume"] = 10_000.0

    # Condition 3 (ADR%): above threshold
    panel.loc[hero_ticker, "adr_pct"] = 6.0

    out_all_true = passes_qullamaggie_setup_a(panel)
    assert out_all_true.loc[(hero_ticker, last_date), "qullamaggie_score"] == 1, (
        "Expected qullamaggie_score=1 when all three conditions True"
    )

    # Now reset ADR% below threshold — should flip to 0
    panel_low_adr = panel.copy()
    panel_low_adr.loc[hero_ticker, "adr_pct"] = 2.0
    out_low_adr = passes_qullamaggie_setup_a(panel_low_adr)
    assert out_low_adr.loc[(hero_ticker, last_date), "qullamaggie_score"] == 0, (
        "Expected qullamaggie_score=0 when ADR% below threshold"
    )

    # Reset volume such that dollar volume is below threshold
    # close~2400, need avg(close*vol, 20) < $1.5M => vol < 1500000/2400 ~ 625
    panel_low_vol = panel.copy()
    panel_low_vol.loc[hero_ticker, "volume"] = 1.0  # close*1 ~ $2400 rolling avg << $1.5M... wait
    # Actually close=2400*1=2400, that is $2400 << $1.5M, so we need close * vol < 1.5M
    # close~2400, vol=600 => 2400*600=1.44M < 1.5M OK
    panel_low_vol.loc[hero_ticker, "volume"] = 600.0
    out_low_vol = passes_qullamaggie_setup_a(panel_low_vol)
    assert out_low_vol.loc[(hero_ticker, last_date), "qullamaggie_score"] == 0, (
        "Expected qullamaggie_score=0 when dollar volume below threshold"
    )
