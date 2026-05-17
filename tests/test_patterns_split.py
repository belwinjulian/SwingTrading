"""Split-adjusted pivot continuity — PAT-05 / D-25 / Pitfall 1.

Separate from tests/test_patterns_golden.py to make the Pitfall 1
regression (pre-split pivot = post-split bar => false breakout) explicit
and discoverable in CI failure summaries.

Plan 06-02 (Wave 1) fills the body with the real assertion against
`tests/fixtures/patterns/nvda_2024_split.parquet` (extended window
2024-04-01..2024-08-31 per Plan 01 generator). Pivot prices MUST be
re-derived from auto_adjust=True closes; storing a pre-split pivot would
cause a false breakout signal on the post-split bar.
"""

# Wave: 1  (body filled by Plan 06-02 — see 06-VALIDATION.md "New test files")

import pandas as pd

from screener.indicators.patterns import detect_all_patterns
from screener.indicators.trend import sma_panel
from screener.indicators.volatility import atr_panel


def _prep_ticker_panel(raw_ohlcv: pd.DataFrame, ticker: str) -> pd.DataFrame:
    df = raw_ohlcv.copy()
    df.columns = [c.lower() for c in df.columns]
    df.index.name = "date"
    df["ticker"] = ticker
    df = df.set_index("ticker", append=True).swaplevel().sort_index()
    df = sma_panel(df, lengths=(10, 20, 50, 150, 200))
    df = atr_panel(df, length=14)
    return df


def test_nvda_2024_split_pivot_continuity(nvda_2024_split_panel: pd.DataFrame) -> None:
    """PAT-05 / D-25 / CLAUDE.md Pitfall 3: NVDA 2024 spans the 2024-06-10
    10:1 split. detect_all_patterns must run cleanly over the split-adjusted
    panel; any pivot price the detector emits MUST be in post-split price
    units (< $200, well below the pre-split level of ~$900–1200).

    Structural defense per D-25: pivot prices are re-derived from
    auto_adjust=True closes on every run — there is no pivot caching
    across runs. This test confirms the property end-to-end on a real
    split-spanning OHLCV slice.
    """
    panel = _prep_ticker_panel(nvda_2024_split_panel, "NVDA")
    result = detect_all_patterns(panel)

    for col in (
        "vcp_passes",
        "flag_passes",
        "post_gap_continuation",
        "pivot_price",
        "breakout_strength",
        "pattern_diagnostics",
    ):
        assert col in result.columns

    pivot_fired = result.loc[
        result["vcp_passes"] | result["flag_passes"], "pivot_price"
    ]
    if len(pivot_fired) > 0:
        max_pivot = float(pivot_fired.max())
        min_pivot = float(pivot_fired.min())
        assert max_pivot < 200.0, (
            f"Detected pivot_price max={max_pivot} >= $200 — pre-split pivot "
            f"leakage suspected (Pitfall 1 / D-25 regression)."
        )
        assert max_pivot < 500.0
        assert min_pivot > 0.0
