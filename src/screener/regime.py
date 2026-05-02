"""regime — universe-wide market-regime gate (one row per date).

Emits a discrete state in {Confirmed Uptrend, Uptrend Under Pressure,
Correction} plus a continuous regime_score in [0, 1]. Imports `data/` and
`indicators/`; consumed by `sizing` and `publishers/`. Implementation lands in
Phase 3 (REG-01..REG-04).
"""
