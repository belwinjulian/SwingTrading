"""backtest — offline-only; reads disk artifacts, never makes network calls.

vectorbt 1.0 walk-forward harness, no-look-ahead test target, slippage tiers.
Imports `persistence` + stdlib only. The no-look-ahead test gate (FND-04)
lands here in Phase 5.
"""
