# Strategy v1 Pre-Registration

**Status:** Placeholder — weights frozen at Phase 4 completion

**Frozen at git hash:** <to be filled at Phase 4 completion>

This document pre-registers the v1 composite-score weights BEFORE any backtest result is reported. Pre-registration is a discipline against the canonical pitfall of in-sample weight optimization (PITFALLS.md #5) and multiple-testing blindness (#13). Once frozen, the weights below cannot be tuned against backtest data; v2 ML weight tuning waits for the paper-trade journal (Phase 7).

## Status Token

The literal string below is the placeholder Phase 4 will replace:

`<weights frozen at Phase 4 completion>`

A CI grep gate (deferred to Phase 4 per FND-05) will fail any change to this file that drops the token without simultaneously committing concrete numeric weights and a git hash.

## v1 Composite Weights (TBD — frozen at Phase 4)

The composite confidence score (0–100) is a weighted sum of six components. Targets below from `.planning/STATE.md`:

| Component                              | Target Weight | Frozen Weight |
|----------------------------------------|---------------|---------------|
| RS percentile (IBD-style)              | 25%           | TBD           |
| Trend Template (0–8 normalized)        | 20%           | TBD           |
| Pattern (VCP/flag tightness)           | 20%           | TBD           |
| Volume confirmation                    | 10%           | TBD           |
| Earnings momentum (CANSLIM C+A)        | 15%           | TBD           |
| Catalyst presence                      | 10%           | TBD           |

**Total:** 100% (target). Frozen weights must also sum to 100% within rounding tolerance.

## Methodology Summary

The v1 composite is rules-based and authoritative — the M2 ML probability score will add a single weight key (`ml_probability`) to this dict without refactoring the scorer. The composite combines:

- **RS percentile (25%)** — IBD-style quarter-weighted relative strength, percentile-ranked daily across the Russell 1000 universe (1–99 integer rating). Formula: `RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`, then percentile-rank.
- **Trend Template (20%)** — Minervini's 8 SMA-based conditions; emits both a boolean gate and a 0–8 partial-match score (the score, normalized to 0–100, feeds the composite). SMAs (NOT EMAs) per CLAUDE.md §13.6 pitfall #4.
- **Pattern (20%)** — VCP contraction tightness or continuation-flag fitness, computed from the indicator panel's pivot-detection output (Phase 6).
- **Volume confirmation (10%)** — 50-day up/down volume ratio plus pocket-pivot flag plus dryup detection.
- **Earnings momentum (15%)** — CANSLIM C (recent quarterly EPS YoY ≥ 25%) + A (3-yr annual EPS growth ≥ 25%) score, lagged 45 days post-quarter-end (PITFALLS.md #2).
- **Catalyst presence (10%)** — flags for `days_to_next_earnings`, `crossed_52w_high_within_60d`, `insider_cluster_buy` (Phase 6 catalyst pipeline).

## Freeze Procedure (Phase 4)

When Phase 4 completes:
1. Replace `TBD` in the table above with concrete numeric weights (one decimal place precision sufficient).
2. Replace the literal token `<weights frozen at Phase 4 completion>` with the date, e.g., `Frozen on 2026-MM-DD`.
3. Replace `<to be filled at Phase 4 completion>` with the actual `git rev-parse HEAD` of the freeze commit.
4. Commit the file as the FINAL action of Phase 4, so the freeze commit's hash is the one referenced (chicken-and-egg: commit, then amend the hash field in a follow-up commit, OR use a placeholder like `[freeze-commit]` and resolve in CI).

## References

- `.planning/REQUIREMENTS.md` FND-05 (Phase 4 ships the freeze; Phase 1 ships this placeholder)
- `.planning/STATE.md` "Composite Score Weights (Pre-Registration Targets)"
- `.planning/research/PITFALLS.md` #5 (in-sample weight overfit), #13 (multiple-testing blindness)
- `CLAUDE.md` §2.7 (Composite Scoring)
