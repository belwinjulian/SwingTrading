# Phase 7: Sizing Finalization & Paper-Trade Journal - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 ships the execution layer that transforms scored, playbook-tagged picks (from Phase 6) into concrete trade plans and a durable audit trail. Three interlocking pieces:

1. **Sizing finalization** — `sizing.py` implementation: per-playbook stop placement (SIZ-03) and trailing rules (SIZ-04), shares calculation (SIZ-01), 1×ADR auto-rejection (SIZ-02), and 3-bucket ATR zone annotation: `in-zone` (≤ 0.66×ATR), `extended` (0.66–1×ATR), `chase, skip` (> 1×ATR above pivot) (SIZ-05). Sizing runs inside `run_pipeline` so the snapshot Parquet carries sizing columns (`stop_price`, `entry_price`, `shares`, `risk_per_share`, `atr_zone`, `pivot_distance_atr`).

2. **Journal integration** — `data/journal.sqlite` append-only table wired into `run_pipeline`. Actionable picks (composite ≥ threshold AND regime ≠ Correction) are appended automatically at publish time. The `journal` CLI command serves as an idempotent catch-up: reads the day's snapshot Parquet and re-appends, with `(ticker, snapshot_date)` as primary key preventing double-inserts. Picks that fail the 1×ADR check are excluded from both the report and the journal.

3. **Journal schema** — append-only, decision columns immutable (DB constraint), `features_json` blob with full signal snapshot, and 6 nullable outcome columns for v2 ML training labels. The `journal-update` CLI flow is deferred to v1.x; Phase 7 ships only the schema.

Requirements covered: **SIZ-01..05** (position sizing, stop/trail, auto-reject, ATR zone), **OUT-04..06** (journal append, schema, outcome columns).

</domain>

<decisions>
## Implementation Decisions

### Journal write trigger (OUT-04)

- **D-01: Journal append fires inside `run_pipeline` AND `journal` command is an idempotent catch-up.**
  - `run_pipeline(date, write_report=True/False, write_journal=True/False)` — journal is appended as part of the pipeline pass. The `report` command calls `run_pipeline(..., write_journal=True)` by default.
  - The `journal` CLI command (already stubbed) fills its body to read the day's snapshot Parquet and re-append actionable picks. Primary key `(ticker, snapshot_date)` on the `picks` table enforces idempotency — INSERT OR IGNORE on conflict.
  - Actionable pick definition: `composite_score >= Settings.JOURNAL_THRESHOLD AND regime_state != 'Correction'`. Regime gate consistent with SC-4's "regime allows new entries."

### Journal schema (OUT-04, OUT-05, OUT-06)

- **D-02: Journal table `picks` — decision columns (immutable) + outcome columns (nullable, updated later).**
  - **Decision columns** (all NOT NULL, immutable via DB trigger or documented convention):
    - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
    - `ticker` (TEXT)
    - `snapshot_date` (TEXT, ISO format)
    - `playbook_tag` (TEXT — qullamaggie_continuation / minervini_vcp / leader_hold)
    - `composite_score` (REAL)
    - `regime_state` (TEXT)
    - `entry_price` (REAL — next-open execution price estimate, from snapshot)
    - `stop_price` (REAL — per-playbook stop per SIZ-03)
    - `shares` (INTEGER)
    - `risk_per_share` (REAL)
    - `atr_zone` (TEXT — in-zone / extended / chase-skip)
    - `pivot_distance_atr` (REAL)
    - `features_json` (TEXT — JSON blob, see D-03)
    - `ingested_at` (TEXT, ISO timestamp)
    - UNIQUE constraint on `(ticker, snapshot_date)`
  - **Outcome columns** (nullable — updated by future `journal-update` flow in v1.x):
    - `entry_filled` (INTEGER nullable — boolean 0/1)
    - `exit_price` (REAL nullable)
    - `exit_date` (TEXT nullable)
    - `hold_days` (INTEGER nullable)
    - `mfe` (REAL nullable — max favorable excursion)
    - `mae` (REAL nullable — max adverse excursion)
  - Decision columns immutability: enforced via an UPDATE trigger that raises `RAISE(ABORT, 'decision column immutable')` on any UPDATE to decision columns. Outcome columns are explicitly excluded from the trigger.

- **D-03: `features_json` blob — full signal snapshot: score components + indicator values + sizing inputs + full pattern_diagnostics.**
  - Score components: `rs_rating`, `trend_template_score`, `pattern_component`, `volume_score`, `earnings_component`, `catalyst_component`, `composite_score`, `regime_score`, `regime_state`, `playbook_tag`, `qullamaggie_score`, `minervini_score`, `leader_hold_score`
  - Key indicator values at signal time: `atr`, `adr_pct`, `dryup_ratio`, `breakout_strength`, `sma_50`, `sma_150`, `sma_200`, `high_52w`, `low_52w`
  - Sizing inputs: `entry_price`, `stop_price`, `shares`, `risk_per_share`, `atr_zone`, `pivot_distance_atr`, `account_equity_used`, `risk_pct_used`
  - Full `pattern_diagnostics` dict inlined (not referenced) — same Phase 6 D-05 compact schema: `{type, n_contractions, depth_sequence, first_leg_depth, final_contraction_depth, breakout_vol_multiple, breakout_strength, pivot_price, days_in_consolidation}` for VCP; flag equivalent for flags; `{type: "none"}` for leader_hold.
  - Estimated blob size: ~400–600 bytes/row. Acceptable for SQLite; well within the 150-bytes-for-pattern_diagnostics budget established in Phase 6.

### Sizing finalization (SIZ-01..05)

- **D-04: Sizing runs in `run_pipeline` — snapshot Parquet carries sizing columns.**
  - `sizing.py` pure function: `compute_sizing(panel: pd.DataFrame, account_equity: float, risk_pct: float, regime_score: float) -> pd.DataFrame`
  - Returns the same-indexed DataFrame with columns added: `stop_price`, `entry_price`, `shares`, `risk_per_share`, `atr_zone`, `pivot_distance_atr`.
  - Called in `run_pipeline` after `apply_regime_gate`, before `write_snapshot_atomic`.
  - `entry_price` = the day's close (next-bar-open execution placeholder; actual fill is tracked in outcome columns at update time).

- **D-05: Shares formula per SIZ-01:** `shares = floor((account_equity × risk_pct × regime_score) / (entry_price - stop_price))`, capped at `floor(account_equity × 0.25 / entry_price)` per position. Both account_equity and risk_pct come from Settings (new: `ACCOUNT_EQUITY`, `RISK_PCT`).

- **D-06: 1×ADR auto-rejection per SIZ-02** — pick is excluded if `risk_per_share > adr_dollars` where `adr_dollars = (adr_pct / 100) × entry_price`. Rejection reason surfaced in report footer section ("Skipped: R/R broken, risk = 1.4×ADR"). Rejected picks are excluded from both the top-N report table AND the journal.

- **D-07: Per-playbook stop placement per SIZ-03:**
  - `qullamaggie_continuation` → `stop_price = entry_day_low` (the D-0 low bar, same bar that triggered the breakout signal)
  - `minervini_vcp` → `stop_price = final_contraction_low` (from `pattern_diagnostics.depth_sequence[-1]` — the pivot price minus final contraction depth, per Phase 6 D-05 schema)
  - `leader_hold` → `stop_price = entry_price - max(1.5 × atr, recent_swing_low_distance)` where `recent_swing_low_distance` is computed from the last argrelextrema trough (same `order` parameter used in Phase 6 pattern detection); distance capped at 2×ATR per SIZ-03.
  - A unit test asserts each playbook calls the correct stop helper (per Phase 7 SC-2).

- **D-08: Per-playbook trail rules per SIZ-04 (defined but not auto-executed in v1 — displayed in report):**
  - `qullamaggie_continuation` → trail on 10/20/50d SMA; speed determines which: high ADR% (≥ 6%) uses 10d SMA; moderate (4–6%) uses 20d SMA; slow (< 4%) uses 50d SMA.
  - `minervini_vcp` → trail on 21d EMA or 50d SMA (21d EMA until the trade matures ≥ 15 bars, then 50d SMA). Planner decides if 21d EMA is already in the indicator panel or must be added.
  - `leader_hold` → trail on 50d SMA close only.
  - Trail rule is surfaced as a text field in the report per-pick block. Not auto-computed against future bars (no intraday or live execution in v1).

- **D-09: ATR zone annotation — 3 buckets (SIZ-05):**
  - `in-zone`: `pivot_distance_atr <= 0.66`
  - `extended`: `0.66 < pivot_distance_atr <= 1.0`
  - `chase, skip`: `pivot_distance_atr > 1.0`
  - All three labels surfaced in both the report per-pick block and the `atr_zone` snapshot column.

### OUT-06 outcome update flow

- **D-10: Phase 7 ships nullable outcome columns only; `journal-update` flow deferred to v1.x.**
  - The 6 outcome columns (`entry_filled`, `exit_price`, `exit_date`, `hold_days`, `mfe`, `mae`) are defined as nullable in the schema.
  - No update CLI logic ships in Phase 7. SC-6 is satisfied by the schema design (columns exist, are nullable, and the immutability trigger explicitly excludes them from the "decision column immutable" enforcement).
  - v1.x ships a `scripts/journal_update.py` helper (outside the D-14 CLI surface lock) or a typer subapp within `journal`; decision deferred.

### Carried-forward constraints (not re-discussed)

- **D-11 (from Phase 6 D-24):** 9-subcommand CLI surface locked. `journal` fills its body in Phase 7; no 10th subcommand.
- **D-12 (from Phase 6 D-20):** Regime gate stays soft (`composite_score × regime_score`). Sizing formula incorporates `regime_score` in the numerator per SIZ-01 formula.
- **D-13 (from Phase 6 D-22):** Snapshot already carries `playbook_tag` from Phase 6; sizing dispatches stop/trail by reading this column.
- **D-14 (from Phase 6 architecture):** `publishers/pipeline.py` docstring already authorizes `publishers/` to import `sizing`. Zero architecture constraint change.

### Claude's Discretion

- **21d EMA for VCP trail** — check if 21d EMA is already computed by the indicator panel (pandas-ta-classic has it); if not, add it to `indicators/trend.py` or compute inline in sizing. Planner decides.
- **`recent_swing_low_distance` for leader_hold stop** — use the most recent argrelextrema trough within the last 20 bars. If no trough found in that window, fall back to 2×ATR distance. Planner decides the lookback window.
- **`entry_price` column semantics** — use the day's close as the sizing-time entry estimate. Actual fill is tracked in outcome columns. Planner decides whether to store as `entry_price_estimate` (clearer) or `entry_price` (shorter).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 7: Sizing Finalization & Paper-Trade Journal" — goal, success criteria 1–6, phase dependency on Phase 6
- `.planning/REQUIREMENTS.md` §SIZ-01..05 — position sizer formula, 1×ADR auto-reject, per-playbook stop/trail, ATR zone annotation
- `.planning/REQUIREMENTS.md` §OUT-04..06 — journal append, append-only schema, `features_json` blob, outcome columns

### Methodology (sizing rules)
- `CLAUDE.md` §"Signal Formulas — Quick-Reference" — Qullamaggie stop/trail rules (low-of-entry-day, 10/20/50 SMA trail by speed), ADR% formula
- `docs/methodology.md` §2 "Qullamaggie Setups" — full entry/stop/exit rules per playbook (Setup A/B/C); v1 implements A only

### Prior phase decisions (carry-forward constraints)
- `.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md` §D-05 — `pattern_diagnostics` compact schema (VCP/flag/none); `features_json` embeds this dict inline
- `.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md` §D-12, D-15 — snapshot carries `playbook_tag`, `pivot_price`, `breakout_strength`; sizing dispatches by tag
- `.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md` §D-23 — architecture test ALLOWED dict; Phase 7 must check that `sizing` is allowed in `publishers`
- `.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md` §D-24 — 9-subcommand CLI surface locked; `journal` fills its body; no 10th command
- `.planning/phases/04-trend-template-composite-skeleton-first-report/04-CONTEXT.md` §D-03 — regime soft gate (composite × regime_score); sizing formula multiplies by regime_score in numerator
- `.planning/phases/02-data-foundation/02-CONTEXT.md` §D-11 — atomic-write idiom; journal SQLite uses sqlite3 transaction pattern (same as form4.sqlite)

### Architecture and code seams
- `src/screener/sizing.py` — stub only; Phase 7 fills the implementation. Pure function module: no I/O, no side effects.
- `src/screener/publishers/pipeline.py` — `run_pipeline()` is the integration point; Phase 7 adds `write_journal: bool = True` param and calls `sizing.compute_sizing()` + journal append after `apply_regime_gate`.
- `src/screener/cli.py` — `journal` command stub (lines ~232–235); Phase 7 fills body to read latest snapshot + re-append.
- `src/screener/persistence.py` — `_write_parquet_atomic`, `append_form4_rows` (SQLite pattern to copy for journal); `RankingSnapshotSchema` must gain sizing columns (`stop_price`, `entry_price`, `shares`, `risk_per_share`, `atr_zone`, `pivot_distance_atr`).
- `tests/test_cli_smoke.py` — D14_SUBCOMMANDS list; Phase 7 must NOT modify.
- `tests/test_architecture.py` — ALLOWED dict; verify `publishers` → `sizing` is allowed.

### Settings extensions
- `src/screener/config.py` — `ACCOUNT_EQUITY` (float, default 100000), `RISK_PCT` (float, default 0.01 = 1%), `JOURNAL_THRESHOLD` (float, default 0.5 composite score cutoff) must be added to Settings. Mirror to `.env.example`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/screener/persistence.py` `append_form4_rows()` — SQLite append-only pattern with sqlite3 transaction; Phase 7's journal append copies this idiom with INSERT OR IGNORE for idempotency.
- `src/screener/persistence.py` `_write_parquet_atomic()` — atomic Parquet write; applies to any extended snapshot schema.
- `src/screener/indicators/volatility.py` — `adr_pct` already in panel; `adr_dollars = (adr_pct / 100) × close` is the rejection threshold for SIZ-02.
- `src/screener/indicators/volume.py` — `dryup_ratio` (volume / SMA50); already in panel; reusable in features_json.
- `src/screener/publishers/pipeline.py` `apply_regime_gate()` — already a separate function; sizing runs after this (regime_score is already applied to composite_score at this point, but sizing.py needs the raw regime_score from `compute_for_date` — pass it as a parameter).
- Phase 6 pattern_diagnostics schema — `pivot_price`, `final_contraction_depth`, `depth_sequence` are already in the snapshot's `pattern_diagnostics` JSON; stop computation for Minervini VCP reads these.

### Established Patterns
- **Pure function in `sizing.py`** — follows `signals/` and `indicators/` convention. No I/O, no side effects. Input: panel DataFrame + scalars. Output: same-indexed DataFrame with sizing columns added.
- **SQLite append-only via transaction** — established in Phase 6 for `form4.sqlite`. Journal copies this: BEGIN → INSERT OR IGNORE → COMMIT. DB trigger enforces decision-column immutability.
- **Settings additive extension** — typed fields with defaults; mirror to `.env.example`.
- **Pandera schema at I/O boundary** — `RankingSnapshotSchema` gains sizing columns; pandera validates before `write_snapshot_atomic`.
- **`Final` constants for thresholds** — consistent with Phase 4 (`DEFAULT_WEIGHTS`) and Phase 6 (VCP thresholds); ATR zone thresholds (`IN_ZONE_ATR = 0.66`, `CHASE_ATR = 1.0`) as `Final` float constants in `sizing.py`.

### Integration Points
- **`run_pipeline` → `compute_sizing` → `write_snapshot_atomic`** — sizing runs between regime gate and snapshot write; snapshot schema extended with 6 sizing columns.
- **`run_pipeline` → `append_journal_picks`** — after snapshot write; reads actionable picks from scored + sized panel and appends to journal.sqlite.
- **`cli.journal` → read_snapshot(today) → `append_journal_picks`** — idempotent catch-up path; same append function reused.
- **`publishers/report.py`** — reads sizing columns from panel (already computed by pipeline); renders stop/shares/trail rules/ATR zone per pick. Phase 6 D-19 report block gains sizing fields.

</code_context>

<specifics>
## Specific Ideas

- **Journal table name:** `picks` (not `journal` — `journal` is a reserved word in some SQL dialects; `picks` is unambiguous).
- **Immutability trigger canonical form:**
  ```sql
  CREATE TRIGGER picks_immutable_decision_cols
  BEFORE UPDATE OF ticker, snapshot_date, playbook_tag, composite_score,
                       regime_state, entry_price, stop_price, shares,
                       risk_per_share, atr_zone, pivot_distance_atr,
                       features_json, ingested_at
  ON picks
  BEGIN
    SELECT RAISE(ABORT, 'decision column immutable');
  END;
  ```
- **Idempotency on journal append:** `INSERT OR IGNORE INTO picks (...) VALUES (...)` — PK `(ticker, snapshot_date)` defined as UNIQUE constraint, so conflicting inserts are silently skipped.
- **Trail rule in report:** per-pick block gains a `Trail:` line after `Stop:`:
  ```
  Stop: $118.40 (low-of-entry-day)   Trail: 20d SMA (ADR% 5.2%)
  ```
- **ATR zone in report:** shown as `Zone: in-zone (0.41×ATR above pivot)` or `Zone: extended (0.78×ATR)` or `Zone: chase, skip (1.32×ATR)`.
- **Auto-reject report section:** A `## Skipped Picks` section at the end of the report (after "Currently Held / Leaders") lists rejected picks with reason: `AAPL — skipped: R/R broken, risk = 1.4×ADR`.
- **`ACCOUNT_EQUITY` default:** 100,000 (paper account). User overrides via `.env` before going live.

</specifics>

<deferred>
## Deferred Ideas

- **`journal-update` CLI flow** — v1.x. Phase 7 ships nullable outcome columns only; the update mechanism (`scripts/journal_update.py` or typer subapp within `journal`) ships after the first 30 paper trades when there are actual outcomes to record.
- **`rejection_reason` column in journal for negative ML samples** — v1.x. Rejected picks (1×ADR fail) are excluded from journal in Phase 7; revisit in v1.x once the model needs more negative samples.
- **Graded trail rules (continuous speed tiers)** — v1.x. Phase 7 ships discrete ADR%-based tiers for Qullamaggie trail (< 4% / 4–6% / ≥ 6% → 50d / 20d / 10d SMA).
- **Journal analytics / decile spread report** — v1.x after first 30 paper trades (CAT-V1X-01).
- **Per-playbook performance time-series in daily report** — v1.x (CAT-V1X-04).

</deferred>

---

*Phase: 7-Sizing Finalization & Paper-Trade Journal*
*Context gathered: 2026-05-17*
