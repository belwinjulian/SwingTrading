# Phase 4: Trend Template, Composite Skeleton & First Report - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the first end-to-end signal pipeline and a real daily markdown report:

1. **Trend Template gate** — `signals/minervini.py` with pure function `passes_trend_template(panel) -> DataFrame` emitting `passes_trend_template: bool` and `trend_template_score: int (0–8)` per ticker. All 8 Minervini conditions implemented with SMA (not EMA). Pass-rate sanity check: alert at >25%.

2. **Composite skeleton** — `signals/composite.py` accepting a weights dict, emitting a `composite_score` (0–100) per ticker. Phase 4 has only RS (25%), Trend Template (20%), and Volume via `dryup_ratio` (10%) live. Pattern (20%), Earnings (15%), and Catalyst (10%) are zeroed out with placeholder labels. Score multiplied by `regime_score` (soft gate — picks still appear in Correction but scores compress).

3. **First daily markdown report** — `publishers/report.py` writing `reports/YYYY-MM-DD.md` with: regime banner, top-15 picks table, per-pick blocks (composite score breakdown including live vs `—(Phase 6)` placeholders, ATR distance from 52-week high proxy, in-zone/chase annotation), data-quality footer (universe size, scan time, fetch success rate, last yfinance refresh, pass-rate warning if >25%).

4. **Ranking snapshot** — `data/snapshots/YYYY-MM-DD.parquet` written on every `make report` run with the full ranked universe (not just top picks) for audit and backtest reproducibility.

5. **Preregistration** — `docs/strategy_v1_preregistration.md` committed with v1 weights table, freeze date, and `Frozen at commit: <sha>` line. CI grep-diff script asserts that `DEFAULT_WEIGHTS` in `signals/composite.py` matches the weights table in the doc.

Requirements covered: **FND-05** (preregistration), **SIG-01** (Trend Template gate), **SIG-04** (composite skeleton), **OUT-01** (daily report), **OUT-02** (per-pick blocks), **OUT-03** (full ranked snapshot).

</domain>

<decisions>
## Implementation Decisions

### Composite skeleton — handling unimplemented components (SIG-04)

- **D-01: Missing components contribute zero.** Pattern (20%), Earnings (15%), and Catalyst (10%) are zeroed out in Phase 4. Phase 4 maximum composite score is ~55/100 (RS + Trend + Volume). Scores are honest — they reflect only what's implemented. Phase 6 adds the remaining components and scores move to the full 0–100 range.

- **D-02: Volume component is live in Phase 4** using `dryup_ratio` from the indicator panel (`dryup_ratio = volume / SMA(volume, 50)`). Mapping: `dryup_ratio ≤ 0.5 → component_score = 1.0` (tight contraction, bullish); `dryup_ratio ≥ 2.0 → component_score = 0.0`; linear interpolation between. Carries 10% weight. Phase 6 can refine the mapping without changing the API.

- **D-03: Regime gate is soft — `composite_score *= regime_score`.** Not a hard zero. Picks still appear in the report during Correction but scores compress (regime_score is low). The report's regime banner communicates the state; the user decides whether to act. Aligns with REG-03 seam established in Phase 3.

- **D-04: Report per-pick breakdown shows all six components with live vs placeholder labels.** Format: `RS=92 | Trend=7/8 | Pattern=—(Phase 6) | Volume=0.7 | Earnings=—(Phase 6) | Catalyst=—(Phase 6)`. Transparent about what's live. Phase 6 swaps in real values by updating the template string — no structural refactor needed.

### Pivot price proxy (OUT-02)

- **D-05: 52-week high (`MAX(High, 252)`) is the Phase 4 pivot proxy.** Already computed in the indicator panel for Trend Template condition 7. Column label in report: `ATR from 52w high (Phase 4 proxy)`. Phase 6 replaces with the VCP breakout level without changing the column name in the report block.

- **D-06: In-zone vs chase annotation ships in Phase 4.** `≤ 1×ATR above 52w high → "in-zone"`; `> 1×ATR above 52w high → "chase, skip"`. Phase 7 formalizes the same logic with the real pivot level. Column: `pivot_zone` ∈ {`in-zone`, `chase, skip`}.

### Pass-rate alerting (SIG-01, OUT-01)

- **D-07: Alert on both structlog AND report banner.** When `pass_rate > 0.25`:
  - Structlog: `log.warning("trend_template_pass_rate_high", pass_rate=0.31, expected_range="0.05–0.15")`
  - Report data-quality footer: `⚠ Pass rate: 31% (expected 5–15% — verify data quality)`
- **D-08: Hard failure when `pass_rate > 0.25 AND regime_state == "Correction"`.** This combination is almost certainly a data error (high pass rate shouldn't coexist with a Correction signal). `make report` exits non-zero, no report committed, no snapshot written. Error message: `"Pass rate {pct}% in Correction regime — data quality gate failed"`.

### Preregistration CI gate (FND-05)

- **D-09: Weights consistency enforced by a grep-diff CI script.** A small Python script (e.g., `scripts/check_preregistration.py`) reads `DEFAULT_WEIGHTS` from `signals/composite.py` and parses the weights table from `docs/strategy_v1_preregistration.md`, then fails if they differ. Failure message: `"Weight mismatch: composite.py rs=0.30 vs doc rs=0.25"`. Added as a CI step in `.github/workflows/ci.yml`.

- **D-10: Preregistration doc records a git hash.** `docs/strategy_v1_preregistration.md` includes a `Frozen at commit: <sha>` line populated at the Phase 4 freeze commit. The commit that first writes the weights is the tamper-evident registration event.

### Carried-forward constraints (not re-discussed)

- **D-11 (from Phase 3/CLAUDE.md): SMA not EMA** for all Trend Template conditions — already CI-enforced.
- **D-12 (from ROADMAP): Composite weights are RS 25% / Trend 20% / Pattern 20% / Volume 10% / Earnings 15% / Catalyst 10%.** These are pre-registered, not backtested.
- **D-13 (from STATE.md): `signals/composite.py` accepts a weights dict.** Not hardcoded column references. v2 ML adds `"ml_probability"` as a new key without touching downstream consumers.
- **D-14 (from Phase 1): Signal execution at next-bar open.** Enforced by Phase 5's no-look-ahead test.

### Claude's Discretion

- `make report` CLI wiring: The Phase 1 stub surface locks 9 subcommands. The planner decides whether `make report` calls `screener rank` (scoring) piped to a publish step, or a dedicated `screener report` subcommand that orchestrates the full pipeline. Either is acceptable as long as the 9-subcommand surface isn't extended.
- Snapshot schema: `data/snapshots/YYYY-MM-DD.parquet` column set — planner decides exact columns (at minimum: ticker, composite_score, rank, passes_trend_template, trend_template_score, regime_score, regime_state, pivot_zone).
- Top-N default: N=15 per ROADMAP SC1. The `Settings` class should expose this as a configurable field (`REPORT_TOP_N: int = 15`).
- Report Markdown structure: Planner decides exact Markdown layout (table vs sections, emoji/badge usage) consistent with the field list from SC1.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 4: Trend Template, Composite Skeleton & First Report" — goal, success criteria 1–5, phase dependencies
- `.planning/REQUIREMENTS.md` §FND-05 — preregistration requirement
- `.planning/REQUIREMENTS.md` §SIG-01 — Minervini Trend Template gate (8 conditions, pass/fail + score)
- `.planning/REQUIREMENTS.md` §SIG-04 — composite skeleton (weights dict, M2 extension seam)
- `.planning/REQUIREMENTS.md` §OUT-01..OUT-03 — report, per-pick blocks, ranking snapshot

### Signal formulas (MUST read before touching signals/ or indicators/)
- `CLAUDE.md` §"Signal Formulas — Quick-Reference" — all 8 Minervini Trend Template conditions verbatim (use SMA, not EMA); IBD RS formula; ADR% formula
- `CLAUDE.md` §"Critical Pitfalls" pitfall #1 — EMA substitution is the #1 silent error; always SMA
- `CLAUDE.md` §"Critical Pitfalls" pitfall #3 — long-only without M filter = 50%+ loss; regime gate is non-negotiable
- `CLAUDE.md` §"Critical Pitfalls" pitfall #4 — >25% pass rate = data quality alert

### Prior phase decisions (carry-forward constraints)
- `.planning/phases/03-indicator-panel-regime/03-CONTEXT.md` — D-01..D-12: regime classification thresholds, regime_score formula, indicator panel structure, RS snapshot persistence, Settings additive extension pattern
- `.planning/phases/02-data-foundation/02-CONTEXT.md` — D-11 (atomic write pattern), D-15 (pandera schemas), D-16 (validation policy)
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` — D-16 (architecture test: signals/ imports only indicators/, regime, persistence, config), D-14 (9-subcommand CLI surface locked)

### Methodology context
- `docs/methodology.md` — Full Minervini Trend Template rules; RS formula derivation; VCP thresholds (Phase 6 reference for pivot proxy replacement)
- `docs/tech-stack.md` — pandas-ta-classic 0.4.47 for SMA/ATR; confirm no C deps

### Architecture constraints
- `src/screener/cli.py` — locked 9-subcommand surface (enforced by `tests/test_cli_smoke.py`). `make report` must not add a 10th subcommand.
- `src/screener/indicators/` — `build_panel()` exports SMA10/20/50/150/200, ATR14, ADR%20, OBV, dryup_ratio, rs_raw, rs_rating. Phase 4 consumes these directly — no new indicator computation.
- `src/screener/regime.py` — `compute_for_date(date, panel)` → Series with `regime_state`, `regime_score`. Phase 4 reads this to populate the regime banner and multiply the composite score.
- `src/screener/publishers/__init__.py` — publishers stub; Phase 4 implements `report.py` here

### Preregistration
- `docs/strategy_v1_preregistration.md` — Phase 1 template with `<weights frozen at Phase 4 completion>` placeholder. Phase 4 fills in the weights table, freeze date, and git hash.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/screener/indicators/relative_strength.py` — `rs_panel(panel)` already computes `rs_raw` and `rs_rating` (1–99 Int64). Phase 4 reads `rs_rating` directly from the panel — no recomputation needed.
- `src/screener/regime.py` — `compute_for_date(date, panel)` and `build_history(start, end)` already implemented. Phase 4 calls `compute_for_date` to get `regime_score` for composite multiplication and `regime_state` for the report banner.
- `src/screener/indicators/trend.py` — SMA10/20/50/150/200 computed via `build_panel()`. Trend Template conditions 1–6 are direct comparisons on these columns. Condition 7 (within 25% of 52w high) uses `MAX(High, 252)` — verify this column is exported by `build_panel()` or add it.
- `src/screener/indicators/volatility.py` — ATR14 already in panel as `atr`. Phase 4 uses this for ATR distance from 52w high: `(close - high_52w) / atr`.
- `src/screener/indicators/volume.py` — `dryup_ratio` already in panel. Phase 4 volume component maps this to 0–1 score.
- `src/screener/persistence.py` — `_write_parquet_atomic()` for snapshot writes. Phase 4 adds `write_snapshot_atomic()` following the same pattern.
- `src/screener/obs.py` — structlog configured; Phase 4 emits `trend_template_pass_rate`, `composite_scored`, `report_written`, `snapshot_written` events.

### Established Patterns
- **Pure functions in `signals/`:** Panel-in, Panel-out with identical MultiIndex. Architecture test enforces this. `minervini.py` and `composite.py` must be pure.
- **Atomic write pattern:** `tempfile.NamedTemporaryFile` + `os.replace()`. All Parquet writes use this. `data/snapshots/` follows the same pattern.
- **Settings additive extension:** New fields (`REPORT_TOP_N`, `TREND_TEMPLATE_PASS_RATE_WARN`) added to `Settings` with typed defaults.
- **Pandera schema at I/O boundary:** `data/snapshots/*.parquet` needs a `RankingSnapshotSchema` in `persistence.py`.

### Integration Points
- **`build_panel()` → `minervini.passes_trend_template()`:** Phase 4's Trend Template consumes the indicator panel as input, returns the same DataFrame with `passes_trend_template` and `trend_template_score` appended.
- **`minervini` + `rs_panel` + `regime` → `composite.score()`:** Composite aggregates these three plus volume component. Input: panel with all indicator columns + trend template columns. Output: panel with `composite_score` appended.
- **`composite.score()` → `publishers/report.py`:** Report reads the scored, ranked DataFrame and writes Markdown. Top-N slice goes to the report; full ranked DataFrame goes to `data/snapshots/`.
- **`composite.score()` → `data/snapshots/`:** Full ranked universe snapshot for Phase 5 backtest harness (no-look-ahead: reads snapshots, not live scores).
- **`signals/composite.py` → Phase 7 sizing seam:** `DEFAULT_WEIGHTS` dict is the M2 extension point. Phase 7 adds `"ml_probability"` as a weight key. Phase 4 must not hardcode column references.

### 52w High Column Check
- Trend Template condition 7 (`close >= 0.75 * MAX(High, 252)`) and condition 6 (`close >= 1.30 * MIN(Low, 252)`) need a 52-week high and low. Verify that `build_panel()` already exports `high_52w` and `low_52w` columns, or plan to add them to `indicators/trend.py`.

</code_context>

<specifics>
## Specific Ideas

- **Composite score breakdown format in report:** `RS=92 | Trend=7/8 | Pattern=—(Phase 6) | Volume=0.7 | Earnings=—(Phase 6) | Catalyst=—(Phase 6)`. The `—(Phase 6)` label is the placeholder for zeroed components.
- **Volume component mapping:** Linear: `score = clip(1 - (dryup_ratio - 0.5) / 1.5, 0, 1)`. At dryup_ratio=0.5 → 1.0, at dryup_ratio=2.0 → 0.0.
- **Pivot zone annotation:** `pivot_zone = "in-zone"` if `(close - high_52w) / atr <= 1.0` else `"chase, skip"`.
- **ATR distance label in report:** `ATR from 52w high (Phase 4 proxy)` — explicit about the proxy to avoid confusion when Phase 6 replaces it.
- **Pass-rate check logic:** `pass_rate = passes_trend_template.sum() / len(passes_trend_template)`. Warn at `> 0.25`. Hard fail (non-zero exit) when `> 0.25 AND regime_state == "Correction"`.
- **Preregistration script location:** `scripts/check_preregistration.py`. CI step added to `.github/workflows/ci.yml` alongside the existing lint/typecheck/test steps.
- **Frozen commit hash:** Populated by running `git rev-parse HEAD` after the weights freeze commit and writing it into `docs/strategy_v1_preregistration.md` as `Frozen at commit: <sha>`.

</specifics>

<deferred>
## Deferred Ideas

- **Full playbook tagging (Qullamaggie / Minervini VCP / leader-hold)** — Phase 6. Phase 4 report shows only the composite score; playbook tag placeholder appears in the per-pick block as `Playbook: —(Phase 6)`.
- **catalyst-flag annotations (insider buys, earnings proximity)** — Phase 6 (CAT-01..04). Phase 4 report shows `Catalyst: —(Phase 6)` placeholder in per-pick blocks.
- **Hard regime gate (zero composite in Correction)** — Revisit in Phase 7 or after paper-trade validation. Current decision is soft multiplication by regime_score (D-03). If paper trading reveals picks in Correction are consistently bad, the gate can be hardened to zero.
- **`make report` failure alerting via GitHub Actions** — Phase 8. Phase 4's alerting is local (structlog + report banner). GitHub Actions failure notification is an OPS phase concern.
- **Per-regime and per-playbook report breakdowns** — Phase 5/6. Phase 4 shows only a single regime banner; breakdown by regime and playbook tag is a Phase 6+ reporting feature.

</deferred>

---

*Phase: 4-Trend Template, Composite Skeleton & First Report*
*Context gathered: 2026-05-10*
