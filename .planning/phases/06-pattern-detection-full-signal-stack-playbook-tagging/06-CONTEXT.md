# Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 ships the differentiator — full pattern detection, the full signal stack, and the playbook tagger that gives every pick a Qullamaggie / Minervini / leader-hold trade-plan identity. Six interconnected pieces, all gated by the no-look-ahead harness from Phase 5:

1. **Pattern detection** — `indicators/patterns.py` with **VCP detector + continuation-flag detector at full rigor** and a **simplified boolean post-gap-continuation flag** (see D-01). Pivots re-derived from adjusted closes per PAT-05; thresholds locked as `Final` module constants; every pick carries a compact `pattern_diagnostics: dict` column for audit.

2. **Qullamaggie Setup A scan** — `signals/qullamaggie.py`. SIG-02 verbatim: top 1–2% performers over 1m/3m/6m AND avg dollar volume > $1.5M AND ADR%(20) ≥ 4. Pure function consuming the indicator panel.

3. **CANSLIM C+L+M overlay** — `signals/canslim.py`. Additive scoring per SIG-03; the C component (quarterly EPS YoY ≥ 25%) is the only one that contributes new signal — L (RS ≥ 80) and M (Confirmed Uptrend) are already in `rs_component` and the regime soft gate respectively, and are **NOT double-counted** (see D-12).

4. **Fundamentals + Catalysts** — `data/fundamentals.py` (Finnhub earnings calendar + yfinance EPS history) and `data/insider.py` (edgartools Form 4 bulk nightly into `data/insider/form4.sqlite`). Every fundamentals row carries a `knowable_from = fiscal_quarter_end + 45 days` column; persistence filters by `as_of_date` so signals cannot accidentally violate the lag (D-13).

5. **Composite full activation + playbook tagger** — `signals/composite.py` extension. Remove `pattern`, `earnings`, `catalyst` from `PHASE_4_ZEROED` frozenset; add `score_pattern_component()`, `score_earnings_component()`, `score_catalyst_component()` helpers. **Co-located playbook tagger** emits one `playbook_tag` per pick PLUS three diagnostic scores (`qullamaggie_score`, `minervini_score`, `leader_hold_score`) — see D-08..D-11.

6. **Snapshot + report extensions** — `data/snapshots/YYYY-MM-DD.parquet` gains: `playbook_tag`, `qullamaggie_score`, `minervini_score`, `leader_hold_score`, `pattern_diagnostics` (compact JSON dict), `breakout_strength`, `days_to_next_earnings`, `crossed_52w_high_within_60d`, `insider_cluster_buy`, `earnings_in_3d_warn` (the report-only anti-flag). Report adds a separate **"Currently Held / Leaders"** section for `leader_hold` picks (not in top-N). Full per-leg pattern history goes to `data/pattern_audit/YYYY-MM-DD.parquet` (gitignored).

Requirements covered: **DAT-05** (`make fundamentals` + 45d lag), **PAT-01..06** (pattern detectors + pivot from adjusted + golden files), **SIG-02** (Qullamaggie Setup A scan), **SIG-03** (CANSLIM additive), **CMP-01..05** (full composite + tagger + breakdown), **CAT-01..04** (earnings + 52w high + insider cluster + EDGAR identity).

</domain>

<decisions>
## Implementation Decisions

### Pattern detection scope, golden files, and audit (PAT-01..06)

- **D-01: Ship VCP + continuation flag at full rigor; post-gap-continuation as a simple boolean flag only.** VCP and continuation flag get full pivot-based detection with `scipy.signal.argrelextrema` (per PAT-01) and the four golden-file tests in D-02. Post-gap-continuation ships as a single boolean column on the panel: `gap_pct(D-0) >= 0.08 AND vol(D-0) > 1.5 × sma_vol_50 AND close(D-0) >= low(D-0) + 2/3 × (high(D-0) - low(D-0))` (see D-04). No separate `post_gap_continuation` playbook tag; this flag feeds the catalyst component (see D-15). Full post-gap playbook deferred to v1.x if paper trading justifies. Closes PAT-04 as a flag-only signal — not a separate detection module.

- **D-02: Four golden-file pattern tests (PAT-06 + one continuation flag):**
  1. **NVDA 2023 base** — clean VCP into AI-rally breakout (per PAT-06)
  2. **AAPL 2020 base** — COVID-recovery VCP (per PAT-06)
  3. **NVDA 2024 split-adjusted** — exercises pivot re-derivation across the 2024-06-10 10:1 split per PAT-05 (per PAT-06)
  4. **NVDA 2023-05-25..2023-06-12 continuation flag** — post-earnings flag along the rising 10-SMA (new; covers the flag detector + post-gap-flag interaction). Add to `tests/test_patterns_golden.py`.

- **D-03: VCP thresholds locked as `Final` module-level constants in `indicators/patterns.py`.** No Settings field, no env override. Tuned via golden-file tests, never against backtest results (pitfall #5). Values verbatim from `CLAUDE.md` §"Signal Formulas — VCP detection thresholds": prior uptrend ≥30%, n_contractions ∈ [2, 6], depth[i]/depth[i-1] ≤ 0.85, first leg ≤ 35%, final ≤ 12%, breakout vol ≥ 1.5×SMA(volume, 50). Phase 7+ paper trading revisits.

- **D-04: "Held the gap" definition (post-gap-continuation):** `close(D-0) >= low(D-0) + (2/3) × (high(D-0) - low(D-0))` — upper third of the full D-0 high–low range (NOT (open, high)). Standard interpretation of PAT-04.

- **D-05: Pattern diagnostics — compact dict in snapshot + full per-leg history in `data/pattern_audit/YYYY-MM-DD.parquet` (gitignored).**
  - **Snapshot column `pattern_diagnostics` (JSON-encoded dict, ~150 bytes/pick):**
    - VCP picks: `{type: "vcp", n_contractions, depth_sequence: [...], first_leg_depth, final_contraction_depth, breakout_vol_multiple, breakout_strength, pivot_price, days_in_consolidation}`
    - Flag picks: `{type: "flag", flag_bars, range_tightness, vol_contraction_ratio, ma_anchor: "10/20/50", breakout_strength, pivot_price}`
    - Leader/no-pattern picks: `{type: "none"}`
  - **`data/pattern_audit/YYYY-MM-DD.parquet`** — per-leg sub-objects (`leg_idx, start_date, end_date, high, low, depth, avg_volume`) for VCP picks; per-bar tightness/volume for flag picks. Gitignored. New `persistence.write_pattern_audit_atomic()` helper.

- **D-06: Breakout-volume confirmation is same-bar + graded `breakout_strength`.** Pick fires when scoring runs after EOD: `close > pivot AND vol >= 1.5 × sma_vol_50` on the same bar. Entry tomorrow at open (next-bar-open execution per BCK-02). `breakout_strength = clip((vol / sma_vol_50 - 1.0) / 1.5, 0, 1)` — 1.5× SMA = 0.33, 3× SMA = 1.0. Carried in `pattern_diagnostics`. Feeds the pattern composite component (D-14) so weak breakouts score lower but still surface.

### Catalyst data sources, refresh cadence, and component score (CAT-01..04, DAT-05)

- **D-07: Earnings sources split — yfinance for EPS history, Finnhub for upcoming calendar.**
  - **Finnhub `/calendar/earnings`** — upcoming dates + BMO/AMC for CAT-01. Cache 24h via `requests-cache`. ~10 calls/day for the universe via date-range queries. Add `FINNHUB_API_KEY` to `Settings` + `.env.example`.
  - **yfinance `Ticker(t).quarterly_earnings`** (or `.income_stmt`) — quarterly EPS history for CANSLIM C (EPS YoY ≥ 25%). Per-ticker; integrate with existing yfinance throttle pattern from `data/ohlcv.py`.
  - Both write to `data/fundamentals/*.parquet` with the `knowable_from` column (D-13).

- **D-08: EDGAR Form 4 = bulk nightly refresh into `data/insider/form4.sqlite`.** `data/insider.py` calls `edgartools` once per nightly `make fundamentals` to fetch the universe-wide Form 4 filings from EDGAR's full-text index for the last 35 days. SQLite append-only event log schema (D-10). Cluster detection (CAT-03) runs as a SQL query at score time — fast, no network. `edgartools.set_identity(...)` called at startup of `cli.py` (CAT-04); if not set, the run fails loud.

- **D-09: `make fundamentals` is a single Make target with `--skip-insider` / `--insider-only` flags.** CLI `refresh-fundamentals` body orchestrates: Finnhub `/calendar/earnings` → yfinance EPS history → EDGAR Form 4 bulk pull. The flags scope-down for debugging (EDGAR outage day = `--skip-insider`). Preserves the 9-subcommand lock (refresh-fundamentals stub already exists). Adds the corresponding `make fundamentals` target.

- **D-10: Insider Form 4 SQLite schema — append-only event log.**
  - Table `form4`: `(filing_id PRIMARY KEY, ticker, insider, transaction_date, type, shares, value_usd, ingested_at)`.
  - Cluster detection query: `SELECT ticker, COUNT(DISTINCT insider) FROM form4 WHERE type='BUY' AND transaction_date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(DISTINCT insider) >= 2` — applied with a rolling 5-day window over the last 30 days per CAT-03.
  - Never deletes — historical insider data is valuable for v2 ML and audit trail.
  - Atomic write via `sqlite3` transaction (already a pattern; documented in persistence).

- **D-11: Catalyst component score (composite 10% weight) = `(earnings_proximity + crossed_52w_high_within_60d + insider_cluster_buy) / 3`.**
  - Three boolean flags, equal weight. Range [0, 1].
  - `earnings_proximity = 1 if days_to_next_earnings <= 14 else 0`.
  - `crossed_52w_high_within_60d` per CAT-02.
  - `insider_cluster_buy` per CAT-03.
  - Per-pick breakdown shows `Catalyst=0.67 (2/3 flags)`.

- **D-11a: Two-tier earnings handling.**
  - `<=14 days to earnings` → catalyst flag = 1 (D-11).
  - `<=3 days to earnings` → report block shows `⚠ Earnings in 2d` annotation; **does NOT** decrement catalyst score (sizing decision is the user's, not the scorer's). Stored as boolean column `earnings_in_3d_warn` on snapshot.
  - Post-gap-continuation flag (D-01) is **NOT** in the catalyst component — it's a pattern signal and lives in `pattern_diagnostics` only.

### Playbook tagging (CMP-02, CMP-03)

- **D-12: Snapshot emits primary `playbook_tag` AND all three diagnostic scores.** Columns added: `playbook_tag` (one of `qullamaggie_continuation` / `minervini_vcp` / `leader_hold` / `none`), `qullamaggie_score` (0 or 1), `minervini_score` (0 or 1), `leader_hold_score` (0 or 1). The three scores are **binary in v1** — diagnostic flags, not magnitudes. CMP-03 tie-breakers select the primary tag from the scores. Paper-trade validation in v1.x can audit threshold sensitivity by reading historical snapshots. Phase 5's BCK-04 leader_hold-only stub gains real per-playbook attribution automatically once Phase 6's tags land.

- **D-13: Tie-breaker thresholds locked as `Final` module-level constants in `signals/composite.py`** (consistent with VCP D-03). Constants:
  ```
  QULL_MAX_BARS = 25
  QULL_MIN_ADR_PCT = 5.0
  MINERVINI_MIN_BARS = 25
  MINERVINI_MAX_FINAL_CONTRACTION_PCT = 8.0
  LEADER_MIN_RS = 90
  ```
  Phase 7+ paper trading revisits.

- **D-14: Tie-break rule when a pick satisfies BOTH Qullamaggie and Minervini criteria — Qullamaggie wins.** When `pattern_bars < QULL_MAX_BARS AND adr_pct >= QULL_MIN_ADR_PCT AND final_contraction_pct <= MINERVINI_MAX_FINAL_CONTRACTION_PCT`, the primary tag is `qullamaggie_continuation` (momentum-bias default; shorter consolidation + high ADR% is by definition a faster-moving setup; Qullamaggie sizing — low-of-entry stop, fast trail — is the better fit). Documented as **CMP-03 amendment** in `docs/strategy_v1_preregistration.md` if tie-breakers are recorded there.

- **D-15: `leader_hold` definition — Trend Template pass + RS ≥ 90 + no VCP/flag detected; routed to a SEPARATE report section, NOT the top-N.**
  - `leader_hold_score = 1` if `passes_trend_template AND rs_rating >= LEADER_MIN_RS AND pattern_diagnostics["type"] == "none"`.
  - The report's top-N picks table excludes `leader_hold` picks by default.
  - A separate `## Currently Held / Leaders` section lists these (ranked by composite score) — informational only; the user doesn't open new positions, they monitor existing.
  - Matches STATE.md "open question" that leader_hold may collapse to informational.
  - **Picks that fail ALL three playbook scores get `playbook_tag = "none"` and are excluded from the report entirely** — composite scoring still ran, but without a tag they have no actionable trade plan.

### Composite score component formulas (CMP-01, CMP-04, CMP-05)

- **D-16: Phase 6 removes `pattern`, `earnings`, `catalyst` from `PHASE_4_ZEROED` frozenset.** D-13 (Phase 4)'s `weights.items()` scoring loop picks up the new components with zero refactor. `DEFAULT_WEIGHTS` values are **unchanged** (RS 25 / Trend 20 / Pattern 20 / Volume 10 / Earnings 15 / Catalyst 10). Pre-registration doc check at CI (Phase 4 D-09) continues to enforce this.

- **D-17: Pattern component (20% weight) = `breakout_strength` of the winning pattern, OR 0 if no pattern.**
  - `pattern_component = breakout_strength` (0..1) for VCP / flag picks.
  - `pattern_component = 0` for leader_hold / no-pattern picks.
  - Single graded value 0..1, no extra knobs. Pattern_diagnostics carries the contributing factors for audit.

- **D-18: Earnings component (15% weight) = CANSLIM C only — boolean, no L/M double-count.**
  - `earnings_component = 1.0 if (quarterly EPS YoY >= 25% AND knowable_from <= as_of_date) else 0.0`.
  - **L (RS ≥ 80) is already captured in `rs_component`** (rs_rating / 99); double-counting it would inflate the contribution of RS-strong stocks beyond the pre-registered 25% weight.
  - **M (Confirmed Uptrend) is already captured in the regime soft gate** (composite × regime_score per Phase 4 D-03); double-counting would compound the regime penalty/boost.
  - Per-pick breakdown shows `Earnings=1 (EPS YoY 32%)` or `Earnings=0 (EPS pending, knowable 2026-06-15)` (D-19).
  - **Important:** This makes the "earnings" weight more accurately a "fundamental earnings momentum" weight. If `docs/strategy_v1_preregistration.md` names the components abstractly ("Earnings momentum (CANSLIM C+A)"), the meaning narrows but the weight value and key are unchanged — no preregistration freeze violation. Verify by reading the doc; if it names CANSLIM L or M as participating, add an explicit **amendment line** to the preregistration doc clarifying the de-duplication.

- **D-19: Per-pick report block format (revised for Phase 6 fully-live components):**
  ```
  RS=92 | Trend=8/8 | Pattern=0.67 (VCP, 4 contractions, brk_vol=2.1x) | Volume=0.7 | Earnings=1 (EPS YoY 32%) | Catalyst=0.67 (2/3 flags)
  Playbook: qullamaggie_continuation (Q=1, M=0, LH=0)
  ⚠ Earnings in 2d  [shown only when earnings_in_3d_warn=true]
  ```
  Each component shows its 0–1 score with a parenthetical context. The playbook line shows the primary tag plus the three binary scores. Phase 4 placeholders `—(Phase 6)` are removed.

### 45-day fundamentals lag enforcement (DAT-05)

- **D-13b: Lag enforcement lives in the DATA LAYER via `knowable_from` column + persistence-time filtering.**
  - `data/fundamentals.py` writes every row with `knowable_from = fiscal_quarter_end + 45 days` (calendar days).
  - `persistence.read_fundamentals(as_of_date)` filters `WHERE knowable_from <= as_of_date` at read time.
  - `signals/canslim.py` consumes pre-filtered data — it cannot accidentally violate the lag (signals/ cannot import data/ per architecture constraint, so this is structurally enforced).
  - Unit test: `tests/test_canslim_lag.py` writes a fundamentals row with `quarter_end = as_of_date - 30d`, calls `read_fundamentals(as_of_date)`, asserts the row is masked. Then advances to `as_of_date + 16d` and asserts it appears.
  - When fundamentals are not yet knowable for a candidate: `earnings_component = 0`; report shows `Earnings=0 (EPS pending, knowable from YYYY-MM-DD)`. Honest reflection of incomplete data; does not silently fail the pick.

### Carried-forward constraints (not re-discussed)

- **D-20 (from Phase 4 D-03):** Regime gate stays soft (`composite_score *= regime_score`). Playbook-tagged picks still appear in Correction with compressed scores. `leader_hold` section unaffected by regime (these are existing positions to monitor, not new entries).
- **D-21 (from Phase 4 D-09):** `scripts/check_preregistration.py` continues to enforce `DEFAULT_WEIGHTS` ↔ `docs/strategy_v1_preregistration.md` consistency. Phase 6 may add an **amendment** line to the preregistration doc clarifying the CANSLIM L/M de-duplication (D-18); the weights table is unchanged.
- **D-22 (from Phase 5 D-12):** Phase 5 backtest report shipped per-playbook attribution as `leader_hold`-only stub. Phase 6's playbook tags populate the snapshot, and Phase 5's harness (which reads `data/snapshots/*.parquet` per Phase 5 D-04) picks them up automatically — no harness refactor required. Backfilled historical snapshots get re-derived if `make backfill-snapshots` is re-run after Phase 6 ships.
- **D-23 (from Phase 1 D-16):** Architecture test `ALLOWED` dict for Phase 6 new modules:
  - `data/fundamentals` → `persistence`, `config`, `obs` (network OK; pandera schema at write)
  - `data/insider` → `persistence`, `config`, `obs` (network OK; sqlite3 stdlib)
  - `indicators/patterns` → no internal imports beyond `pandas`/`scipy` (pure functions)
  - `signals/qullamaggie` → `indicators`, `persistence`, `config` (per existing signals/ allowance)
  - `signals/canslim` → `indicators`, `persistence`, `config`
  - **`signals/` and `indicators/` MUST NOT import `data/`** — this is the structural enforcement of D-13b.
- **D-24 (from Phase 1 D-14):** 9-subcommand CLI surface locked. Phase 6 fills bodies for `refresh-fundamentals` and extends `score` + `report`. No 10th subcommand.
- **D-25 (from CLAUDE.md pitfall #3):** Pivot prices re-derived from adjusted closes on every run per PAT-05; the NVDA 2024 split golden-file test (D-02) is the regression gate.

### Claude's Discretion

- **`indicators/patterns.py` vs `signals/patterns.py` placement.** CLAUDE.md repo layout says `indicators/patterns.py`. Planner confirms — pattern detection is conceptually an indicator (panel-in, panel-out, pure function), but consumes results from other indicators. Either is acceptable as long as the architecture test ALLOWED dict (D-23) reflects the choice.
- **Pivot detection algorithm — `scipy.signal.argrelextrema` vs custom zigzag.** PAT-01 names argrelextrema explicitly; planner decides the `order` parameter and smoothing approach (e.g., apply ADR-relative smoothing before peak finding).
- **Higher-lows tolerance for continuation flags.** PAT-03 says "higher lows" — planner decides whether this is strict (each low > prior low) or tolerant (each low > prior low - 0.5×ATR).
- **Qullamaggie Setup A "top 1–2%" semantics.** Pure percentile rank, or also require a minimum absolute return? Planner decides; pure percentile is the documented default.
- **Sector RS (CANSLIM L extension, deferred from Phase 3).** Planner decides whether to add a basic sector-RS column in Phase 6 or keep CANSLIM L purely as ticker-level rs_rating ≥ 80. Default: keep ticker-level only; sector RS is a v1.x feature.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging" — goal, success criteria 1–6, phase dependencies on Phase 5 (FND-04 gate)
- `.planning/REQUIREMENTS.md` §DAT-05 — `make fundamentals` + 45-day lag
- `.planning/REQUIREMENTS.md` §PAT-01..06 — VCP/flag/post-gap detection + pivot from adjusted closes + golden files
- `.planning/REQUIREMENTS.md` §SIG-02 — Qullamaggie Setup A scan
- `.planning/REQUIREMENTS.md` §SIG-03 — CANSLIM C+L+M additive overlay
- `.planning/REQUIREMENTS.md` §CMP-01..05 — composite + playbook tagging contract
- `.planning/REQUIREMENTS.md` §CAT-01..04 — catalyst flags + EDGAR identity

### Methodology and signal formulas (MUST read before touching signals/ or indicators/)
- `CLAUDE.md` §"Signal Formulas — Quick-Reference" — VCP detection thresholds verbatim (prior uptrend ≥30%, n_contractions ∈ [2,6], depth contraction ≤0.85, first leg ≤35%, final ≤12%, breakout vol ≥1.5× SMA50), Qullamaggie Setup A formula, IBD RS, ADR%
- `CLAUDE.md` §"Critical Pitfalls" #1 (EMA-vs-SMA — CI grep already enforces in Phase 3)
- `CLAUDE.md` §"Critical Pitfalls" #3 (corp actions in pivot detection — D-25 is the structural defense; PAT-05 + NVDA 2024 split golden file enforce it)
- `CLAUDE.md` §"Critical Pitfalls" #5 (in-sample weight overfit — D-03/D-13 lock thresholds as Final constants, tuned via golden files, not backtests)
- `CLAUDE.md` §"Library Quick-Reference" — pandas-ta-classic (indicators), edgartools (Form 4; `set_identity()` required), finnhub-python (60 calls/min ceiling)
- `docs/methodology.md` §2 "Qullamaggie Setups" — full Setup A/B/C playbook rules + entry/stop/exit detail
- `docs/methodology.md` §3 "CANSLIM (William O'Neil)" — full C+L+M criteria + data sources table
- `docs/methodology.md` §"Pattern Detection — VCP and Flag" — VCP algorithm narrative + edge cases
- `docs/data-architecture.md` — catalyst sources (FinBERT M2 only; v1 = Finnhub + EDGAR), caching tiers, free-tier rate limits

### Prior phase decisions (carry-forward constraints)
- `.planning/phases/05-backtest-harness-no-lookahead-gate/05-CONTEXT.md` §D-04 (harness reads `data/snapshots/*.parquet` — Phase 6 must add `playbook_tag` + 9 new columns to snapshot per D-12, D-15, D-19), §D-12 (leader_hold stub → Phase 6 fills with real tags; BCK-04 attribution auto-populates), §D-13 (regime_state already in snapshot)
- `.planning/phases/04-trend-template-composite-skeleton-first-report/04-CONTEXT.md` §D-01 (zeroed components → Phase 6 removes from PHASE_4_ZEROED), §D-04 (report breakdown format → D-19 supersedes), §D-13 (composite weights-iterating scoring loop — Phase 6 needs zero scoring-loop refactor), §D-03 (regime soft gate — preserved by D-20), §D-09 (preregistration CI script — D-21 confirms unchanged)
- `.planning/phases/03-indicator-panel-regime/03-CONTEXT.md` §D-07 (build_panel pure-function contract — patterns.py follows), §D-09 (dryup_ratio formula — Phase 6 may reuse for flag vol-contraction logic), §D-12 (Settings additive extension pattern — Phase 6 adds FINNHUB_API_KEY, FUNDAMENTALS_CACHE_DIR, INSIDER_CACHE_PATH, EDGAR_IDENTITY, PATTERN_AUDIT_DIR)
- `.planning/phases/02-data-foundation/02-CONTEXT.md` §D-11 (atomic-write idiom for all Parquet — fundamentals + pattern_audit follow), §D-15 (pandera schemas at I/O boundary — FundamentalsSchema, InsiderSchema required)
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` §D-16 (architecture test ALLOWED dict — Phase 6 extends per D-23), §D-14 (9-subcommand CLI surface locked — preserved per D-24)

### Architecture and code seams
- `src/screener/cli.py` — `refresh-fundamentals`, `score`, `report` stubs (lines ~190–235); Phase 6 fills bodies. NO new subcommands.
- `src/screener/signals/composite.py` — `DEFAULT_WEIGHTS` (Final dict, lines ~21–28), `PHASE_4_ZEROED` (Final frozenset, line ~36); Phase 6 removes `pattern`/`earnings`/`catalyst` from frozenset and adds the playbook tagger.
- `src/screener/catalysts/__init__.py` — empty M2 reserve seam; Phase 6 may populate or may leave empty if `data/insider.py` + `data/fundamentals.py` carry the load. Per its docstring: "Implementation in Phase 6 (CAT-01..CAT-04 limited subset) and M2."
- `src/screener/persistence.py` — atomic-write idiom; Phase 6 adds `write_pattern_audit_atomic()`, `write_fundamentals_atomic()`, `read_fundamentals(as_of_date)` (filters on knowable_from per D-13b), `read_insider_cluster_buy(window_days=30, cluster_size=2, dt=5)`.
- `src/screener/data/__init__.py` — barrel re-exports; Phase 6 adds `fundamentals` and `insider` modules.
- `tests/test_architecture.py` — ALLOWED dict; Phase 6 extends per D-23.
- `tests/test_cli_smoke.py` — D14_SUBCOMMANDS list; Phase 6 must NOT modify.

### Pre-registration governance
- `docs/strategy_v1_preregistration.md` — weights table (frozen at commit 7ea58d3 per STATE.md). Phase 6 may add an **amendment line** clarifying CANSLIM L/M de-duplication (D-18); weights table itself is unchanged. CI check (`scripts/check_preregistration.py`) continues to enforce DEFAULT_WEIGHTS ↔ doc consistency.

### Stack
- `docs/tech-stack.md` — finnhub-python 2.4.28, edgartools 5.30.x, scipy (for `signal.argrelextrema`), pandera 0.31.1
- `CLAUDE.md` §"Library Quick-Reference" — finnhub free 60/min; edgartools needs `set_identity()`; scipy.signal in std SciPy

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/screener/indicators/relative_strength.py` — `rs_rating` (1–99 Int64) already in panel; Qullamaggie Setup A uses `rs_rating` as the percentile proxy.
- `src/screener/indicators/volume.py` — `dryup_ratio = volume / SMA(volume, 50)`; reusable for flag vol-contraction logic and for the breakout-volume confirmation (D-06: `breakout_strength` is a transformation of the same SMA-50 baseline).
- `src/screener/indicators/volatility.py` — `adr_pct` already in panel; Qullamaggie Setup A filters on `adr_pct >= 4`.
- `src/screener/indicators/trend.py` — `high_52w`, `low_52w` columns; CAT-02 `crossed_52w_high_within_60d` reads these.
- `src/screener/regime.py` — `regime_state` column; CANSLIM M check + leader_hold filter both consume this. Already in snapshot per Phase 4.
- `src/screener/signals/composite.py` — `DEFAULT_WEIGHTS` + `PHASE_4_ZEROED` + `weights.items()` scoring loop; Phase 6 extension is keys-removed + three new `score_*_component()` helpers + a `tag_playbook(panel)` function. Zero refactor of the scoring loop.
- `src/screener/persistence.py` — `_write_parquet_atomic()`; pattern_audit + fundamentals follow. Existing `validate_at_write`/`validate_at_read` for pandera enforcement.
- `src/screener/data/ohlcv.py` — yfinance throttling + retry pattern (`run_with_breaker`, `tenacity`); fundamentals fetcher reuses the same wrappers for yfinance EPS calls.
- `src/screener/data/stooq.py` — illustrative pattern for a per-source adapter; Phase 6's `data/fundamentals.py` and `data/insider.py` follow the same shape (fetch → normalize → pandera-validate → return).
- `src/screener/publishers/snapshot.py` — atomic snapshot writer; Phase 6 extends `RankingSnapshotSchema` with 9+ new columns.
- `src/screener/publishers/report.py` — report renderer; Phase 6 swaps Phase 4 placeholders for real values (D-19) and adds the "Currently Held / Leaders" section after the top-N table.

### Established Patterns
- **Pure functions in `signals/` and `indicators/`** — Architecture test enforces. Patterns module must follow.
- **Atomic write pattern** — `tempfile.NamedTemporaryFile` + `os.replace()`. Applies to fundamentals Parquet, pattern_audit Parquet.
- **SQLite append-only via transaction** — established for the journal (Phase 7 plans); insider Form 4 uses the same idiom but ships first in Phase 6.
- **`Settings` additive extension** — typed fields with defaults, mirror to `.env.example`.
- **Pandera schema at every I/O boundary** — `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema` required.
- **Final-constant locking of thresholds** — Phase 4 set the precedent with `DEFAULT_WEIGHTS: Final[dict]`; Phase 6 extends to VCP thresholds (D-03) and tie-breaker thresholds (D-13).
- **`PHASE_4_ZEROED` frozenset reduction pattern** — adding a new live component = removing a key. Already proven in Phase 4.

### Integration Points
- **`build_panel()` → `indicators/patterns.py`** — patterns detector consumes the panel + uses pre-computed SMAs, ATR, ADR%, dryup_ratio, high_52w. Adds `vcp_passes`, `flag_passes`, `post_gap_continuation`, `pivot_price`, `breakout_strength`, `pattern_diagnostics` columns.
- **`data/fundamentals.py` → `persistence.read_fundamentals(as_of_date)` → `signals/canslim.py`** — lag-enforced read path. Signals never touch the data layer (D-13b / D-23).
- **`data/insider.py` → `data/insider/form4.sqlite` → `persistence.read_insider_cluster_buy()` → `signals/composite.py` catalyst component** — bulk-cached event log + SQL-query cluster detection.
- **`signals/composite.py` `tag_playbook(panel)` → `data/snapshots/*.parquet` `playbook_tag` column → Phase 5 backtest BCK-04 attribution** — Phase 5 harness reads snapshots; no harness refactor required (D-22).
- **`publishers/snapshot.py` `RankingSnapshotSchema` extension** — must add the 9 new columns (D-19) and refresh the pandera schema. Phase 5 backfill snapshots (Phase 5 D-01) re-derive when `make backfill-snapshots` is re-run.
- **`cli.py` `score` + `report` bodies** — Phase 6 extends to call patterns → qullamaggie → canslim → composite (now full) → tag_playbook → snapshot (extended schema) → report (extended format + leader_hold section).
- **`docs/strategy_v1_preregistration.md`** — possible amendment line for CANSLIM L/M de-duplication (D-18); weights table unchanged; preregistration hash check (Phase 4 D-09) continues to gate CI.

### Architecture constraints (Phase 6 specific)
- `tests/test_architecture.py` ALLOWED dict extension (D-23) — add entries for `data/fundamentals`, `data/insider`, `indicators/patterns`, `signals/qullamaggie`, `signals/canslim`. Verify that `signals/` is NOT permitted to import `data/` (structural defense of the lag enforcement, D-13b).
- `tests/test_cli_smoke.py` D14_SUBCOMMANDS list — must NOT change. Phase 6 fills bodies; no 10th subcommand.

</code_context>

<specifics>
## Specific Ideas

- **Golden-file flag setup:** NVDA 2023-05-25 to 2023-06-12 — post-earnings continuation flag along rising 10-SMA. Specifically chosen for the post-earnings overlap (also exercises the post-gap-continuation boolean + flag detector simultaneously).
- **Pattern_diagnostics compact schema:** VCP example `{"type": "vcp", "n_contractions": 4, "depth_sequence": [0.22, 0.15, 0.09, 0.06], "first_leg_depth": 0.22, "final_contraction_depth": 0.06, "breakout_vol_multiple": 2.1, "breakout_strength": 0.73, "pivot_price": 487.50, "days_in_consolidation": 32}`. JSON-encoded as a string in Parquet; ~150 bytes/pick.
- **Insider cluster-buy SQL query (canonical form):**
  ```sql
  WITH windows AS (
    SELECT ticker, transaction_date,
           COUNT(DISTINCT insider) OVER (
             PARTITION BY ticker
             ORDER BY transaction_date
             RANGE BETWEEN INTERVAL '4 days' PRECEDING AND CURRENT ROW
           ) AS cluster_size
    FROM form4
    WHERE type = 'BUY'
      AND transaction_date BETWEEN date('now', '-30 days') AND date('now')
  )
  SELECT DISTINCT ticker FROM windows WHERE cluster_size >= 2;
  ```
  (SQLite's window-function support is sufficient; if it isn't on the deployed sqlite3, fall back to a Python rolling-window post-process.)
- **Earnings two-tier in report:** `⚠ Earnings in 2d` annotation appears on the per-pick block (NOT in the top-line table). Visual distinct from the `📊` or 🔥 emoji used elsewhere — pick a single warning marker convention with the planner.
- **`leader_hold` report section title:** "Currently Held / Leaders" — explicit that these are existing positions to monitor, not new entries.
- **`pattern_audit/` directory policy:** Gitignored (consistent with `data/snapshots/`, `data/rs_snapshots/`, `data/ohlcv/`). `.gitkeep` to anchor the directory.
- **CANSLIM L/M de-duplication amendment text (draft):** "CANSLIM L (rs_rating ≥ 80) is captured by the `rs` weight (25%); CANSLIM M (Confirmed Uptrend) is captured by the regime soft gate (composite × regime_score). The `earnings` weight (15%) corresponds to CANSLIM C only (quarterly EPS YoY ≥ 25%). This de-duplication does not change the weight values or keys."
- **Pivot detection `argrelextrema(order=N)`:** Standard starting point is `order=5` (a peak/trough must be the extremum over a 5-bar window on each side). Tune via the four golden files; document the chosen value in `patterns.py` module docstring.

</specifics>

<deferred>
## Deferred Ideas

- **Full post-gap-continuation playbook (own tag, EP-style entry rules)** — v1.x after paper-trade validation. Phase 6 ships only the boolean flag (D-01).
- **Sector RS (CANSLIM L extension; deferred from Phase 3)** — v1.x. Phase 6 keeps CANSLIM L as ticker-level rs_rating only (D-18 + Discretion).
- **Graded playbook scores (continuous 0–1 instead of binary)** — v1.x once paper trading shows whether binary tags are too coarse. Phase 6 ships binary (D-12).
- **Settings-tunable VCP and tie-breaker thresholds** — v1.x. Phase 6 hardcodes as `Final` constants (D-03 + D-13) to defend against in-sample tuning.
- **Cup-and-handle detection** — v2 per `.planning/PROJECT.md` Out of Scope. VCP + flag carry v1.
- **Setup C (parabolic capitulation longs)** — Out of scope per `.planning/PROJECT.md`; intraday-dependent.
- **FinBERT news sentiment + Reddit social buzz** — Deferred to M3 per `.planning/REQUIREMENTS.md` (NLP-01, NLP-02). Catalysts in Phase 6 are limited to earnings + 52w high + insider Form 4 only.
- **Per-pick `tag_confidence` (margin between top score and runner-up)** — v1.x once binary scores prove insufficient.
- **Pre-registration doc revision policy** — If the CANSLIM L/M amendment (D-18) is added, the freeze-hash convention (Phase 4 D-10) requires either a new git hash on the doc or an explicit "amendment" log. Decision deferred to planning.
- **Insider Form 4 from non-EDGAR sources (Finnhub /insider-transactions)** — Phase 6 sticks with EDGAR (CAT-04 explicit). Finnhub alternative is a fallback option in v1.x if EDGAR proves unreliable.

</deferred>

---

*Phase: 6-Pattern Detection, Full Signal Stack & Playbook Tagging*
*Context gathered: 2026-05-16*
