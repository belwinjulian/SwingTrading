"""FND-04 + BCK-02: CI-blocking no-look-ahead mutation test.

Integration test. Calls the REAL screener.backtest.vbt_runner.run() with synthetic
OHLCV (via monkeypatch) and a perfect-foresight signal (signal[t] = close[t+1] > close[t]).

Assertion structure (per CONTEXT.md D-07 REVISED 2026-05-16; 05-RESEARCH.md §B Q5,
empirically recalibrated for the production harness -- see 05-02-SUMMARY.md DEVIATION-1):

  - _lookahead=False  ->  abs(total_return) < LOOKAHEAD_FALSE_MAX_RETURN
                          (correct path; .shift(1) negates foresight)
  - _lookahead=True   ->  total_return > LOOKAHEAD_TRUE_MIN_RETURN
                          (mutation backdoor; foresight wins)
  - PLUS ratio guard:  total_return(True) / max(abs(total_return(False)), 1e-15)
                          > LOOKAHEAD_RATIO_MIN
                       (the third defense recommended in §B Q5; drift-invariant)

ITER-3 EMPIRICAL RECALIBRATION (DEVIATION-1 in 05-02-SUMMARY.md):

The plan's pre-execution thresholds (0.50 / 1.00) were calibrated in §B Q5 on a
single-ticker, ungrouped vbt.Portfolio.from_signals call with default
size_type. The PRODUCTION harness (src/screener/backtest/vbt_runner.py shipped
in 05-01) uses a fundamentally different configuration:

  - 3-ticker MultiIndex panel with cash_sharing=True + group_by=np.zeros (one
    composite portfolio), NOT three independent portfolios.
  - size=0.05 with size_type='value' -- each entry deploys $5,000 (5% of the
    $100k init_cash), NOT the full available cash.
  - Multi-bar trades held until an exit signal fires (entries clean = first
    True bar; exits = False after True), NOT the per-bar long-only treatment
    Q5 implicitly assumed.
  - The synthetic_ohlcv_panel fixture (05-00) constructs intraday
    `open = close * (1 + N(0, 0.002))` -- the open->close gap is ~20 bps,
    SO the perfect-foresight signal (which predicts close[t+1] direction)
    captures at most ~20 bps per trade when vbt executes the entry at open[t+1].

The combined effect: total_return for _lookahead=True is on the order of 1e-6
to 1e-5 (positive, clean win rate ~94%, but compounded over only ~200 trades
of 5% sizing with 20 bps per-trade gain), NOT the >100% Q5 predicted.

A 10-seed Monte Carlo on the production harness (RESEARCH §B Q5 recipe applied
to the actual vbt_runner.run() call, NOT a synthetic from_signals shortcut):

  | seed | False (correct)  | True (mutation)  | ratio (True/|False|) |
  | ---- | ---------------- | ---------------- | -------------------- |
  | 42   | -2.639e-07       | +1.640e-06       |  6.22x               |
  | 0    | -1.276e-07       | +1.624e-06       | 12.73x               |
  | 1    | -3.206e-08       | +1.816e-06       | 56.66x               |
  | 7    | -1.919e-07       | +1.577e-06       |  8.22x               |
  | 100  | -1.376e-07       | +1.738e-06       | 12.63x               |
  | 13   | -2.306e-07       | +1.553e-06       |  6.74x               |
  | 25   | +1.175e-07       | +1.859e-06       | 15.82x               |
  | 50   | -3.714e-07       | +1.577e-06       |  4.25x               |
  | 99   | -2.323e-07       | +1.833e-06       |  7.89x               |
  | 200  | -1.894e-07       | +1.726e-06       |  9.11x               |

Observed envelopes (10 seeds):
  - max(|False|): 3.714e-07  -- choose ceiling  8e-7 (2.15x headroom above noise)
  - min(True)   : 1.553e-06  -- choose floor    8e-7 (1.94x below mutation floor)
  - min(ratio)  : 4.25x      -- choose floor    3.0x (drift-invariant backup;
                                 plan's Q5 alt-rec gave 3.0; 1.4x headroom)

CRITICAL CALIBRATION CONSTRAINT (CR-1 in 05-02-SUMMARY.md): The pre-mutation
correct-path return and the post-mutation correct-path return DIFFER BY ONLY
~6x (correct path on seed 42: 2.64e-7 pre-mutation; same path becomes the
mutation arm 1.64e-6 post-mutation). Therefore the absolute ceiling MUST sit
strictly between them, NOT loose like the iter-1 1e-4 attempt which left the
post-mutation value inside the passing band. The 8e-7 ceiling (chosen by
geometric mean of the per-seed pre/post envelopes) correctly catches the
mutation: post-mutation 1.64e-6 > 8e-7 = ceiling, test FAILS.

THE MECHANISM (window-count precondition + tight-threshold + ratio) IS PRESERVED.
Only the absolute threshold magnitudes are recalibrated empirically to the
production harness. The mutation gate fires LOUDLY when .shift(1) is removed
(manually verified -- see 05-02-SUMMARY.md mutation log).

If a future change to vbt_runner alters position-sizing semantics (e.g., size=1.0
or size_type='amount'), thresholds will need re-recalibration. The mechanism
is robust; the magnitudes are configuration-dependent. Treat threshold edits
as a deliberate breaking change, not a noise update -- ping the user.

B-2 fix (iter 2): The fixture span was extended from 250 bars x 1 ticker to
1008 bars x 3 tickers so vbt_runner.run() would produce >=1 complete window.

C-1 fix (iter 3): Iter-2's 1008/2020-01-01 fixture span actually produced ZERO
complete windows because `start + 4yr = 2024-01-01 > fixture_end ~ 2023-11-15`.
Plan 05-00 (iter 3) extended the fixture to 1300 bdays / 2019-01-01 (~4.98
calendar years; produces 1 walk-forward window per 05-00 deviation #1; the
plan's narrative target of >=2 is not achieved by the on-disk fixture, but >=1
suffices to make the mutation test non-trivial). This test (iter 3) adds an
explicit precondition assertion `len(result.windows) >= 1` BEFORE the
threshold checks, so any future fixture-span regression that brings the
silent-zero-window defect back is caught loudly at test time (rather than
producing a deceptive total_return = 0.0 for both lookahead modes -- which
would trivially satisfy both thresholds).

Mutation check (manual): removing `.shift(1, fill_value=False)` from
`vbt_runner.run()`'s else-branch is equivalent to hardcoding `_lookahead=True` --
test_no_lookahead_correct_path will fail because the harness would always
execute on the foresight bar. This is the FND-04 CI gate. Documented in
05-02-SUMMARY.md mutation log.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from screener.backtest import vbt_runner

# Empirically recalibrated thresholds (see module docstring DEVIATION-1).
# Originally calibrated in §B Q5 against a single-ticker ungrouped Portfolio:
#   LOOKAHEAD_FALSE_MAX_RETURN = 0.50  (50%)
#   LOOKAHEAD_TRUE_MIN_RETURN  = 1.00  (100%)
# Production harness shifts magnitudes by ~6 orders. Recalibrated values
# below preserve the SAME structural assertion (correct path near zero;
# mutation strictly positive and distinguishable) and -- critically --
# the ceiling 8e-7 sits TIGHTLY between max(|False|)=3.71e-7 (envelope
# across 10 seeds) and min(True)=1.55e-6 so the mutation arm exceeds the
# ceiling and the test FAILS when .shift(1) is removed. See module docstring
# CR-1 for the calibration-constraint analysis.
LOOKAHEAD_FALSE_MAX_RETURN = 8e-7   # correct path: max obs |return| 3.71e-7 (10 seeds)
LOOKAHEAD_TRUE_MIN_RETURN = 8e-7    # mutation:     min obs return  1.55e-6 (10 seeds)
LOOKAHEAD_RATIO_MIN = 3.0           # drift-invariant third defense (§B Q5)


def _fixture_date_range(panel: pd.DataFrame) -> tuple[str, str]:
    """Derive (start, end) ISO date strings from the fixture's date index.

    B-2 fix (iter 2) / C-1 fix (iter 3): test date range MUST cover enough
    calendar years that walk_forward_windows() produces >=1 complete window
    (for default IS=3yr / OOS=1yr, that means `start + 4yr <= end`). The
    synthetic_ohlcv_panel fixture is calibrated to span 1300 bdays starting
    2019-01-01 (~4.98 calendar years; produces 1 walk-forward window). We
    read the endpoints rather than hardcoding dates, so any future
    fixture-span change propagates here automatically.
    """
    dates = panel.index.get_level_values("date")
    return (
        dates.min().strftime("%Y-%m-%d"),
        dates.max().strftime("%Y-%m-%d"),
    )


def _assert_nontrivial_window_count(
    result: vbt_runner.BacktestResult,
    start: str,
    end: str,
) -> None:
    """C-1 fix (iter 3): explicit precondition that the harness produced >=1 complete window.

    If the fixture span shrinks below `is_years + oos_years` calendar years
    (default 4yr for IS=3/OOS=1), `walk_forward_windows()` returns `[]` and
    `vbt_runner.run()` returns a BacktestResult with `windows=[]` and
    `total_return=0.0` -- which TRIVIALLY satisfies both the
    `abs(total_return) < THRESHOLD` AND defeats `total_return > THRESHOLD`
    in the mutation arm with zero discriminating power. Both lookahead
    branches would produce identical zero-return "results", defeating the
    FND-04 gate entirely.

    This was the iter-2 C-1 defect. Catch it here LOUDLY with a remediation
    pointer rather than letting the test silently pass against zero data.
    """
    if len(result.windows) < 1:
        gap_yr = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
        pytest.fail(
            f"Fixture span insufficient -- walk_forward_windows produced 0 windows. "
            f"Extend synthetic_ohlcv_panel start date in tests/conftest.py "
            f"(need start + (is_years + oos_years) <= fixture_end; "
            f"currently start={start}, end={end}, gap={gap_yr:.2f} years; "
            f"need >= 4.00 years for default IS=3yr/OOS=1yr). "
            f"See 05-00-PLAN.md iter-3 C-1 fix."
        )


def _build_perfect_foresight_snapshot(panel: pd.DataFrame) -> pd.DataFrame:
    """Construct a fake snapshot DataFrame matching what _load_snapshots_in_range returns.

    Perfect-foresight signal per D-06: True at bar t when close[t+1] > close[t].
    Last bar is False (no next bar exists).

    Schema must match the columns vbt_runner.run() consumes:
      - date (pd.Timestamp), ticker (str), passes_trend_template (bool),
        regime_state (str), composite_score (float)
    """
    # panel is MultiIndex (ticker, date). Extract per-ticker close, build signal.
    close_wide = panel["close"].unstack(level="ticker")  # noqa: PD010
    foresight = (close_wide.shift(-1) > close_wide).astype(bool)
    foresight = foresight.fillna(False)  # last bar has no next-day -> False

    # Stack back to long format with the required columns.
    rows: list[dict[str, Any]] = []
    for date in foresight.index:
        for ticker in foresight.columns:
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "passes_trend_template": bool(foresight.loc[date, ticker]),
                    "regime_state": "Confirmed Uptrend",
                    "composite_score": 50.0,
                    "regime_score": 1.0,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def _patched_runner(
    monkeypatch: pytest.MonkeyPatch, synthetic_ohlcv_panel: pd.DataFrame
) -> tuple[str, str]:
    """Monkeypatch vbt_runner's data-loading seams to return synthetic data.

    Per RESEARCH §B Q7: patch the SYMBOL inside vbt_runner (not in persistence)
    because vbt_runner does `from screener.persistence import read_panel` --
    Python binds `read_panel` as a local module attribute at import time.

    Returns (start_iso, end_iso) derived from the fixture's date endpoints --
    B-2/C-1 fix: tests use this dynamic range, not hardcoded 2024-01-01..2024-12-31.
    """
    snapshot_df = _build_perfect_foresight_snapshot(synthetic_ohlcv_panel)

    def _fake_read_panel(_snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
        return synthetic_ohlcv_panel

    def _fake_load_snapshots(
        _start: pd.Timestamp, _end: pd.Timestamp
    ) -> pd.DataFrame:
        return snapshot_df

    monkeypatch.setattr(
        "screener.backtest.vbt_runner.read_panel", _fake_read_panel
    )
    monkeypatch.setattr(
        "screener.backtest.vbt_runner._load_snapshots_in_range", _fake_load_snapshots
    )

    return _fixture_date_range(synthetic_ohlcv_panel)


def test_no_lookahead_correct_path(_patched_runner: tuple[str, str]) -> None:
    """_lookahead=False: harness applies .shift(1); foresight is negated; return stays near zero."""
    start, end = _patched_runner
    result = vbt_runner.run(start, end, _lookahead=False)
    # C-1 (iter 3) precondition -- fail LOUDLY before the threshold check if
    # the fixture span produced zero walk-forward windows.
    _assert_nontrivial_window_count(result, start, end)
    assert abs(result.total_return) < LOOKAHEAD_FALSE_MAX_RETURN, (
        f"Look-ahead detected: total_return={result.total_return:+.3e} "
        f"exceeds noise ceiling {LOOKAHEAD_FALSE_MAX_RETURN:+.0e} "
        f"(range {start}..{end}, {len(result.windows)} windows). "
        f"Check that vbt_runner.run() applies .shift(1, fill_value=False) to entries/exits "
        f"in the `else` branch of `if _lookahead:`. (FND-04 / BCK-02 / D-19)"
    )


def test_no_lookahead_mutation_detected(_patched_runner: tuple[str, str]) -> None:
    """_lookahead=True: harness skips .shift(1); foresight produces clean positive return.

    Combined assertion (the third-defense ratio guard per §B Q5):
      - absolute floor: total_return(True) > LOOKAHEAD_TRUE_MIN_RETURN
      - ratio floor:    total_return(True) / max(|correct|, 1e-15) > LOOKAHEAD_RATIO_MIN

    Both must hold. Re-running the correct-path call here (rather than relying
    on fixture-shared state) costs ~10s on the 1300-bar fixture but gives a
    drift-invariant guarantee: even if both magnitudes drift due to a future
    fixture re-roll, the *separation* between mutation and correct-path must
    remain at least 3x. The min observed ratio over 5 seeds is 6.22x, so the
    3x floor has ~2x headroom against the worst observed seed.
    """
    start, end = _patched_runner
    result_mutation = vbt_runner.run(start, end, _lookahead=True)
    # C-1 (iter 3) precondition -- fail LOUDLY before the threshold check if
    # the fixture span produced zero walk-forward windows.
    _assert_nontrivial_window_count(result_mutation, start, end)
    assert result_mutation.total_return > LOOKAHEAD_TRUE_MIN_RETURN, (
        f"Mutation backdoor failed to outperform: total_return={result_mutation.total_return:+.3e} "
        f"is below the floor {LOOKAHEAD_TRUE_MIN_RETURN:+.0e} "
        f"(range {start}..{end}, {len(result_mutation.windows)} windows). "
        f"Either the perfect-foresight signal construction is wrong, or .shift(1) "
        f"is not actually being bypassed when _lookahead=True. (FND-04 gate broken)"
    )

    # Third-defense ratio guard -- drift-invariant per §B Q5.
    result_correct = vbt_runner.run(start, end, _lookahead=False)
    _assert_nontrivial_window_count(result_correct, start, end)
    ratio = result_mutation.total_return / max(abs(result_correct.total_return), 1e-15)
    assert ratio > LOOKAHEAD_RATIO_MIN, (
        f"Mutation/correct ratio = {ratio:.2f}x is below the floor "
        f"{LOOKAHEAD_RATIO_MIN:.2f}x. Observed magnitudes: "
        f"mutation={result_mutation.total_return:+.3e}, "
        f"correct={result_correct.total_return:+.3e}. "
        f"The two lookahead arms produced returns within "
        f"{LOOKAHEAD_RATIO_MIN:.1f}x of each other -- "
        f"the FND-04 gate cannot distinguish them. (FND-04 mechanism broken)"
    )
