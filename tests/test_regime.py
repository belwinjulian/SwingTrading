"""Regime module unit tests (REG-01, REG-02, REG-03; D-01, D-02, D-03; Pitfall 11)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from screener.regime import (
    _classify_state,
    _compute_distribution_days,
    _regime_score,
    compute_for_date,
)


class _StubSettings:
    REGIME_BREADTH_THRESHOLD = 0.60
    REGIME_DIST_DAYS_PRESSURE = 5
    REGIME_DIST_DAYS_CORRECTION = 9
    REGIME_VIX_CORRECTION = 30.0
    REGIME_VIX_CONFIRMED = 20.0


SETTINGS = _StubSettings()


# --- _classify_state — D-01 priority chain ---------------------------------


def test_classify_state_confirmed_uptrend() -> None:
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Confirmed Uptrend"


def test_classify_state_uptrend_under_pressure_breadth() -> None:
    """Breadth < 60% — not Correction; falls back to Pressure."""
    s = _classify_state(spy_above_200d=True, breadth_pct=50.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Uptrend Under Pressure"


def test_correction_overrides_on_spy_below_200d() -> None:
    s = _classify_state(spy_above_200d=False, breadth_pct=70.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Correction"


def test_correction_overrides_pressure() -> None:
    """D-01: dist >= 9 forces Correction even if breadth and VIX are healthy."""
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=10, vix_level=15.0, settings=SETTINGS)
    assert s == "Correction"


def test_correction_overrides_on_vix_30() -> None:
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=2, vix_level=35.0, settings=SETTINGS)
    assert s == "Correction"


# --- _compute_distribution_days — strict IBD definition (D-02) -------------


def test_distribution_day_idiom(synthetic_spy_with_dist_days: pd.DataFrame) -> None:
    """4 injected dist days within the last 25 sessions → rolling sum at last day == 4."""
    out = _compute_distribution_days(synthetic_spy_with_dist_days, window=25)
    assert out.iloc[-1] == 4


def test_distribution_day_volume_filter() -> None:
    """A close-down day with NOT-higher volume must NOT count as a distribution day."""
    n = 30
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    close = np.full(n, 100.0)
    close[15] = 99.0  # 1% drop
    vol = np.full(n, 1_000_000, dtype="int64")
    vol[15] = vol[14] - 1  # LOWER volume — must NOT count
    spy = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.98,
         "close": close, "volume": vol},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    out = _compute_distribution_days(spy, window=25)
    assert out.iloc[-1] == 0


# --- _regime_score boundary cases ------------------------------------------


def test_regime_score_all_good() -> None:
    df = pd.DataFrame({
        "spy_above_200d": [True],
        "breadth_pct": [100.0],
        "distribution_days": [0],
        "vix_level": [10.0],
    })
    score = _regime_score(df).iloc[0]
    assert score == pytest.approx(1.0)


def test_regime_score_all_bad() -> None:
    df = pd.DataFrame({
        "spy_above_200d": [False],
        "breadth_pct": [0.0],
        "distribution_days": [10],
        "vix_level": [50.0],
    })
    score = _regime_score(df).iloc[0]
    assert score == pytest.approx(0.0)


# --- compute_for_date — REG-01/02/03 integration ---------------------------


def _setup_macro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                 spy_df: pd.DataFrame, vix_df: pd.DataFrame) -> None:
    """Write macro parquets to tmp_path/macro and monkeypatch the dir."""
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    spy_df.to_parquet(macro_dir / "spy.parquet", engine="pyarrow", index=True)
    vix_df.to_parquet(macro_dir / "vix.parquet", engine="pyarrow", index=True)


def _make_indicator_panel(n_tickers: int = 5, n_days: int = 260) -> pd.DataFrame:
    """Build a minimal indicator-panel-shaped frame with sma_200 and close."""
    tickers = [f"TKR{i}" for i in range(n_tickers)]
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n_days)
    rows = []
    idx_pairs = []
    for t in tickers:
        for d in dates:
            idx_pairs.append((t, d))
            rows.append({"close": 110.0, "sma_200": 100.0})  # close > sma_200
    idx = pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"])
    return pd.DataFrame(rows, index=idx)


def test_compute_for_date_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]  # use last shared date
    out = compute_for_date(target, panel)
    expected = {"spy_above_200d", "breadth_pct", "distribution_days",
                "vix_level", "regime_state", "regime_score"}
    assert set(out.index) == expected


def test_regime_state_enum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]
    out = compute_for_date(target, panel)
    assert out["regime_state"] in {"Confirmed Uptrend", "Uptrend Under Pressure", "Correction"}


def test_regime_score_seam_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    """REG-03: regime_score column is present and is a float in [0, 1]."""
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]
    out = compute_for_date(target, panel)
    assert "regime_score" in out.index
    assert 0.0 <= float(out["regime_score"]) <= 1.0


def test_breadth_pct_denominator_uses_valid_sma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    """Pitfall 11: tickers without sma_200 are excluded from breadth denominator.
    Build a panel where half the tickers have NaN sma_200; the other half
    all have close > sma_200. Breadth should be 100% (only the valid half counts)."""
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    target = synthetic_spy_with_dist_days.index[-1]
    tickers = [f"TKR{i}" for i in range(10)]
    rows = []
    idx_pairs = []
    for i, t in enumerate(tickers):
        idx_pairs.append((t, target))
        if i < 5:
            rows.append({"close": 110.0, "sma_200": 100.0})  # valid + above
        else:
            rows.append({"close": 110.0, "sma_200": float("nan")})  # ineligible
    panel = pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"]),
    )
    out = compute_for_date(target, panel)
    assert float(out["breadth_pct"]) == pytest.approx(100.0)
