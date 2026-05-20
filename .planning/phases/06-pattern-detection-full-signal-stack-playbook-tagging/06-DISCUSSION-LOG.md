# Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 6-pattern-detection-full-signal-stack-playbook-tagging
**Areas discussed:** Pattern detection scope & rigor, Catalyst data sources & refresh cadence, Playbook tagging — strict CMP-03 vs multi-score shadow, CANSLIM C+L+M scoring shape & 45-day lag enforcement

---

## Pattern detection scope & rigor

### Q1: Phase 6 is large (18 reqs). Should all three pattern detectors ship in v1, or cut post-gap?

| Option | Description | Selected |
|--------|-------------|----------|
| All three, full rigor | VCP + flag + post-gap full detection per PAT-01..04 | |
| VCP + flag full, post-gap as a simple flag-only signal | Reduces scope ~25%; post-gap = boolean column feeding catalyst | ✓ |
| VCP only; defer flag + post-gap to Phase 6.5 | Cuts SIG-02 entry signal quality; splits the ROADMAP bundle | |

**User's choice:** VCP + flag full, post-gap as a simple flag-only signal
**Notes:** Captured as D-01. Full post-gap playbook deferred to v1.x if paper trading justifies.

### Q2: Lock PAT-06 golden files (NVDA 2023 base, AAPL 2020 base, NVDA 2024 split-adjusted) or substitute?

| Option | Description | Selected |
|--------|-------------|----------|
| Lock the three from PAT-06 verbatim | Stable, well-documented; covers split invariant | |
| Add a continuation-flag setup as a 4th golden file | Keep PAT-06 three; add one flag regression test | ✓ |
| I'll name specific tickers/dates I trust | User-supplied | |

**User's choice:** Add a continuation-flag setup as a 4th golden file
**Notes:** Captured as D-02.

### Q3: For the 4th (continuation-flag) golden file, what's the source-of-truth ticker/date?

| Option | Description | Selected |
|--------|-------------|----------|
| NVDA 2023-05 (post-earnings flag) | NVDA 2023-05-25..2023-06-12 — flag along rising 10-SMA after AI-boom earnings gap | ✓ |
| TSLA 2020-08 (pre-split flag) | TSLA 2020-08-04..2020-08-21 — second corp-action test | |
| Claude picks based on what's clean in yfinance data | Less reproducible until locked | |

**User's choice:** NVDA 2023-05 (post-earnings flag)
**Notes:** Captured as D-02. Also exercises post-gap-flag interaction.

### Q4: VCP thresholds — lock verbatim or expose as tunable Settings?

| Option | Description | Selected |
|--------|-------------|----------|
| Lock verbatim as constants in patterns.py | Final constants; tuned via golden files only | |
| Settings fields with verbatim defaults | Enables env-var A/B testing; invites in-sample tuning | |
| Lock verbatim, but emit pattern_diagnostics column for audit | Hardcoded constants + per-pick diagnostics dict | ✓ |

**User's choice:** Lock verbatim, but emit pattern_diagnostics column for audit
**Notes:** Captured as D-03 + D-05. Pattern_diagnostics has compact dict in snapshot + full per-leg history in `data/pattern_audit/YYYY-MM-DD.parquet` (gitignored).

### Q5 (follow-up): Pattern_diagnostics column schema — what level of detail per pick?

| Option | Description | Selected |
|--------|-------------|----------|
| Compact: VCP key metrics only | ~150 bytes/pick, eyeballable | |
| Full: every contraction leg with date ranges | Per-leg sub-objects; ~1KB/pick | |
| Compact + a separate pattern_audit/ Parquet for full details | Snapshot stays lean; deep audit on demand | ✓ |

**User's choice:** Compact + a separate pattern_audit/ Parquet for full details
**Notes:** Captured as D-05.

### Q6 (follow-up): Post-gap-continuation "held the gap" — upper third of high–low, or (open, high)?

| Option | Description | Selected |
|--------|-------------|----------|
| Upper third of D-0 high–low range | `close >= low + (2/3) × (high - low)` | ✓ |
| Upper third of (open, high) | More restrictive; "buying pressure into the close" | |

**User's choice:** Upper third of D-0 high–low range
**Notes:** Captured as D-04.

### Q7 (follow-up): Breakout-volume confirmation timing on EOD data.

| Option | Description | Selected |
|--------|-------------|----------|
| Same-bar breakout: close > pivot AND vol ≥ 1.5×SMA(50) on that bar | Entry tomorrow at open per BCK-02 | |
| Two-bar confirmation: pivot crossed today AND held next day | More conservative, less Qullamaggie-faithful | |
| Same-bar but emit `breakout_strength` quality score (0–1) | Same-bar + graded quality, feeds pattern component | ✓ |

**User's choice:** Same-bar but emit `breakout_strength` quality score (0–1)
**Notes:** Captured as D-06.

---

## Catalyst data sources & refresh cadence

### Q1: CAT-01 earnings calendar — source?

| Option | Description | Selected |
|--------|-------------|----------|
| Finnhub free /calendar/earnings | Structured, BMO/AMC, 60/min, ~10 calls/day total | |
| yfinance Ticker(t).calendar | Free unlimited but per-ticker × 1000 = slow, BMO/AMC unreliable | |
| yfinance for EPS history + Finnhub for calendar (split) | Plays to each one's strengths | ✓ |

**User's choice:** yfinance for EPS history + Finnhub for calendar (split)
**Notes:** Captured as D-07.

### Q2: CAT-03 EDGAR Form 4 — per-ticker on-demand vs bulk nightly refresh?

| Option | Description | Selected |
|--------|-------------|----------|
| Bulk nightly refresh into local SQLite cache | edgartools universe pull → form4.sqlite; cluster detection = SQL query | ✓ |
| Per-ticker on-demand at score time | Slow at 1000 tickers, fragile to EDGAR rate ceiling | |
| Bulk weekly + on-demand backfill on cache miss | Middle ground; complexity not worth it | |

**User's choice:** Bulk nightly refresh into local SQLite cache
**Notes:** Captured as D-08.

### Q3: `make fundamentals` scope — single target or split?

| Option | Description | Selected |
|--------|-------------|----------|
| Single `make fundamentals` covers earnings + insider | Consistent with `make ohlcv` covering prices + splits | |
| Split: `make fundamentals` + `make insider` | Forces 10th subcommand or flag-gymnastics | |
| Single `make fundamentals`, with --skip-insider / --insider-only flags | One target + flexible debug flags | ✓ |

**User's choice:** Single `make fundamentals`, with --skip-insider / --insider-only flags
**Notes:** Captured as D-09. Preserves the 9-subcommand lock.

### Q4: Insider cluster-buy SQLite cache schema.

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only event log | Every Form 4 transaction is a row; never deletes; SQL query for cluster | ✓ |
| Rolling 30-day window with hard delete | Loses historical insider data | |

**User's choice:** Append-only event log
**Notes:** Captured as D-10. Historical insider data is valuable for v2 ML and audit trail.

### Q5: Catalyst component score (10% of composite) — how do flags compose?

| Option | Description | Selected |
|--------|-------------|----------|
| Count-of-flags / 3 | Simple equal-weight | ✓ |
| Weighted: insider 0.5, 52w high 0.3, earnings 0.2 | Invites tuning; needs own pre-registration | |
| Count-of-flags / 3 + post-gap as 4th flag | Post-gap mis-categorized as catalyst | |

**User's choice:** Count-of-flags / 3
**Notes:** Captured as D-11. Post-gap stays in pattern_diagnostics, not catalyst.

### Q6: Earnings-proximity flag thresholding.

| Option | Description | Selected |
|--------|-------------|----------|
| Within 14 calendar days | Captures the run-up window | |
| Within 7 calendar days | Misses the run-up window | |
| Two-tier: <=14d flag + <=3d 'earnings risk' anti-flag | Catalyst boost + report-only warning | ✓ |

**User's choice:** Two-tier: <=14d flag + <=3d 'earnings risk' anti-flag
**Notes:** Captured as D-11a. Anti-flag does not decrement catalyst score.

---

## Playbook tagging — strict CMP-03 vs multi-score shadow

### Q1: Tagging emission — one tag, or all three scores + primary tag?

| Option | Description | Selected |
|--------|-------------|----------|
| Primary tag + all three scores | Snapshot carries playbook_tag + Q/M/LH scores | ✓ |
| Strict CMP-03 only — one tag, no shadow scores | Simpler, no diagnostic visibility | |
| Strict CMP-03 + single tag_confidence float | Middle ground | |

**User's choice:** Primary tag + all three scores
**Notes:** Captured as D-12. Enables paper-trade threshold-sensitivity audit per STATE.md open question.

### Q2: CMP-03 thresholds in code — Settings vs Final constants?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level Final constants in composite.py | Locked; consistent with VCP threshold decision | ✓ |
| Settings fields with verbatim defaults | Invites in-sample tuning anti-pattern | |

**User's choice:** Module-level Final constants in composite.py
**Notes:** Captured as D-13.

### Q3: What defines a leader_hold pick?

| Option | Description | Selected |
|--------|-------------|----------|
| Trend Template pass + RS >= 90, no pattern required | Institutional-leader archetype | |
| Same as #1 + composite_score >= 60 floor | Risk of being too strict given Phase 4 zeroed components | |
| leader_hold is informational only — surfaced but not in top-N by default | Separate report section; user monitors, doesn't initiate | ✓ |

**User's choice:** leader_hold is informational only — surfaced but not in top-N by default
**Notes:** Captured as D-15. Aligns with STATE.md note that leader_hold "may collapse to informational only."

### Q4: Tie-break edge case — pick passes BOTH Qullamaggie and Minervini criteria.

| Option | Description | Selected |
|--------|-------------|----------|
| Qullamaggie wins ties — momentum-bias default | Shorter consolidation + high ADR = faster setup; Qullamaggie sizing better fit | ✓ |
| Minervini wins ties — pattern-quality bias | Tight final contraction is strictest VCP quality signal | |
| Higher of qullamaggie_score vs minervini_score wins | Makes tag emergent from scoring formula | |

**User's choice:** Qullamaggie wins ties — momentum-bias by default
**Notes:** Captured as D-14. Documented as CMP-03 amendment.

### Q5: Playbook score formula — binary or graded?

| Option | Description | Selected |
|--------|-------------|----------|
| Binary (0 or 1) for v1 | Auditable; no calibration; CMP-03 priority decides tag | ✓ |
| Graded by pattern quality (0–1 continuous) | More diagnostic; needs pre-registration | |

**User's choice:** Binary (0 or 1) for v1
**Notes:** Captured as D-12.

---

## CANSLIM C+L+M scoring shape & 45-day lag enforcement

### Q1: CANSLIM scoring shape.

| Option | Description | Selected |
|--------|-------------|----------|
| Boolean: C+L+M each 0/1, canslim_component = sum/3 | Simple, auditable, additive-not-hard-gate intent | ✓ |
| Graded: C scaled by EPS magnitude, L by RS, M by regime_score | More knobs, harder to defend | |
| Hybrid: C/L graded, M boolean | Awkward asymmetry | |

**User's choice:** Boolean: C+L+M each 0/1, canslim_component = sum/3
**Notes:** Captured as D-18 with a critical amendment per Q3 below (only C feeds earnings_component to avoid double-count).

### Q2: 45-day lag enforcement — where does it live?

| Option | Description | Selected |
|--------|-------------|----------|
| Data layer: `data/fundamentals.py` writes `knowable_from` column | Persistence filters at read; structurally enforced (signals can't import data) | ✓ |
| Signals layer: canslim.py applies the mask at read | Easy to forget in refactor; look-ahead risk | |
| Both — belt-and-suspenders | Tiny redundancy, defends future changes | |

**User's choice:** Data layer: `data/fundamentals.py` writes `knowable_from` column
**Notes:** Captured as D-13b. Architecture constraint (D-23) makes this structural.

### Q3: Weights mapping — CANSLIM C+L+M → which composite weights?

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm: canslim_component = `earnings` weight key (full C+L+M) | Clean 1:1 mapping | |
| Split: CANSLIM C → earnings; L+M overlap with rs/regime (don't double-count) | L already in rs_component; M already in regime soft gate | ✓ |
| Decide after researcher checks pre-registration doc | Defers a key contract decision | |

**User's choice:** Split: CANSLIM C → earnings; L+M overlap with rs/regime (don't double-count)
**Notes:** Captured as D-18 (overrides Q1's sum/3 framing). earnings_component = c_score only; report breakdown adjusted accordingly. Preregistration doc may need an amendment line clarifying the de-duplication (D-21).

### Q4: Fundamentals pending (knowable_from > as_of_date) — what does C contribute?

| Option | Description | Selected |
|--------|-------------|----------|
| C = 0 (no contribution; report shows 'EPS pending') | Honest; no-look-ahead discipline | ✓ |
| C = use previous quarter's value | Stale-data fallback | |
| Pick is excluded from report until fundamentals are knowable | Too strict | |

**User's choice:** C = 0 (no contribution; report shows 'EPS pending')
**Notes:** Captured as D-13b + D-19.

### Q5: Per-pick breakdown format (Phase 6 fully-live).

| Option | Description | Selected |
|--------|-------------|----------|
| Boolean+context: `Earnings=1 (EPS YoY 32%)` / `Earnings=0 (EPS pending, knowable 2026-06-15)` | Auditable, transparent | ✓ |
| Numeric only: `Earnings=1` | Compact but opaque | |
| Three-line block per pick (no inline format) | Easier to read; longer report | |

**User's choice:** Boolean+context
**Notes:** Captured as D-19. Playbook line: `Playbook: qullamaggie_continuation (Q=1, M=0, LH=0)`.

---

## Claude's Discretion

- `indicators/patterns.py` vs `signals/patterns.py` placement (planner confirms; CLAUDE.md repo layout says `indicators/`).
- Pivot detection algorithm specifics — `scipy.signal.argrelextrema` `order` parameter and smoothing approach.
- Higher-lows tolerance for continuation flags (strict vs ±0.5×ATR tolerance).
- Qullamaggie Setup A "top 1–2%" semantics (pure percentile vs percentile + absolute return floor).
- Sector RS (CANSLIM L extension, deferred from Phase 3) — keep ticker-level only in v1 unless planner sees easy win.

## Deferred Ideas

- Full post-gap-continuation playbook (own tag, EP-style entry rules) — v1.x after paper-trade validation.
- Sector RS — v1.x.
- Graded playbook scores (continuous 0–1) — v1.x.
- Settings-tunable VCP and tie-breaker thresholds — v1.x.
- Cup-and-handle detection — v2 per PROJECT.md.
- Setup C (parabolic capitulation longs) — out of scope per PROJECT.md.
- FinBERT news sentiment + Reddit social buzz — M3 per REQUIREMENTS.md.
- Per-pick `tag_confidence` (margin between top and runner-up scores) — v1.x.
- Pre-registration doc revision policy (re-hash on amendment vs amendment log) — defer to planning.
- Insider Form 4 from non-EDGAR sources (Finnhub /insider-transactions) — v1.x fallback if EDGAR proves unreliable.
