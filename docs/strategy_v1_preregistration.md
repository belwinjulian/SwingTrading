# Strategy v1 Pre-Registration

**Status:** Frozen on 2026-05-10

**Frozen at git hash:** <PLACEHOLDER_TO_BE_REPLACED_BY_NEXT_COMMIT>

Frozen at commit: <PLACEHOLDER_TO_BE_REPLACED_BY_NEXT_COMMIT>

This document pre-registers the v1 composite-score weights BEFORE any backtest result is reported. Pre-registration is a discipline against the canonical pitfall of in-sample weight optimization (PITFALLS.md #5) and multiple-testing blindness (#13). Once frozen, the weights below cannot be tuned against backtest data; v2 ML weight tuning waits for the paper-trade journal (Phase 7).

## Status Token

Weights frozen on 2026-05-10. The CI gate (FND-05) in scripts/check_preregistration.py
enforces that DEFAULT_WEIGHTS in signals/composite.py always matches this table.

## v1 Composite Weights

The composite confidence score (0–100) is a weighted sum of six components. Weights below are
pre-registered per FND-05 and D-12. Targets from `.planning/STATE.md`:

| Component                              | Target Weight | Frozen Weight |
|----------------------------------------|---------------|---------------|
| RS percentile (IBD-style)              | 25%           | 25%           |
| Trend Template (0–8 normalized)        | 20%           | 20%           |
| Pattern (VCP/flag tightness)           | 20%           | 20%           |
| Volume confirmation                    | 10%           | 10%           |
| Earnings momentum (CANSLIM C+A)        | 15%           | 15%           |
| Catalyst presence                      | 10%           | 10%           |

**Total:** 100% (target). Frozen weights must also sum to 100% within rounding tolerance.

## Methodology Summary

The v1 composite is rules-based and authoritative — the M2 ML probability score will add a single weight key (`ml_probability`) to this dict without refactoring the scorer. The composite combines:

- **RS percentile (25%)** — IBD-style quarter-weighted relative strength, percentile-ranked daily across the Russell 1000 universe (1–99 integer rating). Formula: `RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`, then percentile-rank.
- **Trend Template (20%)** — Minervini's 8 SMA-based conditions; emits both a boolean gate and a 0–8 partial-match score (the score, normalized to 0–100, feeds the composite). SMAs (NOT EMAs) per CLAUDE.md §13.6 pitfall #4.
- **Pattern (20%)** — VCP contraction tightness or continuation-flag fitness, computed from the indicator panel's pivot-detection output (Phase 6).
- **Volume confirmation (10%)** — 50-day up/down volume ratio plus pocket-pivot flag plus dryup detection.
- **Earnings momentum (15%)** — CANSLIM C (recent quarterly EPS YoY ≥ 25%) + A (3-yr annual EPS growth ≥ 25%) score, lagged 45 days post-quarter-end (PITFALLS.md #2).
- **Catalyst presence (10%)** — flags for `days_to_next_earnings`, `crossed_52w_high_within_60d`, `insider_cluster_buy` (Phase 6 catalyst pipeline).

## Freeze Procedure (Phase 4) — COMPLETED 2026-05-10

The v1 weights were frozen as part of Plan 04-05. The two-commit ceremony (D-10) was:
1. Commit with concrete weights in the table above and placeholder SHA in the hash lines.
2. Capture `git rev-parse HEAD` from commit 1, substitute into the `Frozen at commit:` and
   `Frozen at git hash:` lines, then commit again.

The CI gate (scripts/check_preregistration.py) enforces that any future change to
`DEFAULT_WEIGHTS` in `signals/composite.py` must also update this table, or CI fails.

## References

- `.planning/REQUIREMENTS.md` FND-05 (Phase 4 ships the freeze; Phase 1 ships this placeholder)
- `.planning/STATE.md` "Composite Score Weights (Pre-Registration Targets)"
- `.planning/research/PITFALLS.md` #5 (in-sample weight overfit), #13 (multiple-testing blindness)
- `CLAUDE.md` §2.7 (Composite Scoring)
