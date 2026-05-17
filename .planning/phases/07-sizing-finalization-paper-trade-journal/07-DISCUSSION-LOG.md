# Phase 7: Sizing Finalization & Paper-Trade Journal - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 07-sizing-finalization-paper-trade-journal
**Areas discussed:** Journal write trigger, features_json blob scope, OUT-06 outcome update flow, Sizing columns in snapshot

---

## Journal Write Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Inside run_pipeline | run_pipeline(date, write_report, write_journal=True). Single workflow step. | |
| Separate journal CLI step | `make journal` after `make report`. Journal reads snapshot and appends. | |
| Both — pipeline AND journal command as catch-up | run_pipeline appends inline; `journal` command is idempotent re-run via PK on (ticker, snapshot_date). | ✓ |

**User's choice:** Both — journal writes inline in run_pipeline AND journal command serves as idempotent catch-up.
**Notes:** Idempotency via `INSERT OR IGNORE` on UNIQUE `(ticker, snapshot_date)` constraint.

---

### Journal Actionable Pick Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| composite_score >= threshold AND regime != Correction | Regime gate keeps junk-market picks out of ML training set. | ✓ |
| composite_score >= threshold only | No regime gating on journal entries. | |
| All picks that pass trend template | Broader dataset, no quality floor. | |

**User's choice:** composite_score >= threshold AND regime_state != 'Correction'.
**Notes:** Consistent with SC-4's "regime allows new entries." Threshold from Settings.JOURNAL_THRESHOLD.

---

## features_json Blob Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Score components + key indicator values | Score breakdown + ATR, pivot_price, pattern_diagnostics, adr_pct, dryup_ratio. | |
| Score components only | Just scoring breakdown — recoverable from snapshot Parquet. | |
| Everything — score components + indicators + sizing inputs | Full audit trail: score + indicators + stop_price, shares, risk_per_share, entry_price. | ✓ |

**User's choice:** Everything — score components + indicators + raw sizing inputs.
**Notes:** Estimated ~400–600 bytes/row. Enables forensic replay and v2 ML feature engineering without re-running the pipeline.

---

### pattern_diagnostics in blob

| Option | Description | Selected |
|--------|-------------|----------|
| Full pattern_diagnostics dict inlined | Embed full Phase 6 D-05 compact schema as nested object inside features_json. | ✓ |
| Reference only (type + pivot_price) | Lighter — full diagnostics join from snapshot Parquet on (ticker, date). | |
| You decide | Let planner decide based on blob size/query ergonomics. | |

**User's choice:** Full pattern_diagnostics dict inlined.
**Notes:** JSON-in-JSON. Single blob load recovers everything without a Parquet join.

---

## OUT-06 Outcome Update Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Typer subapp within `journal` command | `screener journal update AAPL --exit-price 120 --exit-date 2026-05-18`. D-24 compliant. | |
| scripts/journal_update.py standalone | Outside CLI surface lock. Less discoverable. | |
| Defer to v1.x — define nullable columns only | Ship schema with 6 nullable outcome columns; update logic ships later. | ✓ |

**User's choice:** Defer to v1.x — Phase 7 ships nullable outcome columns only.
**Notes:** SC-6 is satisfied by the schema design (columns exist, nullable, excluded from immutability trigger). Update mechanics ship in v1.x after first 30 paper trades produce actual outcomes.

---

### Outcome column set

| Option | Description | Selected |
|--------|-------------|----------|
| Standard 6 | entry_filled, exit_price, exit_date, hold_days, mfe (max favorable excursion), mae (max adverse excursion). | ✓ |
| Minimal 3 | entry_filled, exit_price, exit_date only. | |
| You decide | Let planner size outcome schema for v2 ML. | |

**User's choice:** Standard 6.
**Notes:** Sufficient for v2 ML training labels. MFE and MAE required for risk-adjusted analysis.

---

## Sizing Columns in Snapshot

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — sizing runs in run_pipeline, snapshot carries sizing columns | Snapshot Parquet gains stop_price, entry_price, shares, risk_per_share, atr_zone, pivot_distance_atr. Journal reads directly. | ✓ |
| No — sizing runs in report renderer only | Not in Parquet; journal must re-derive at append time. | |

**User's choice:** Yes — sizing runs in run_pipeline before snapshot write.
**Notes:** Single source of truth. Journal reads sizing columns from snapshot without re-deriving.

---

### 1×ADR auto-reject handling

| Option | Description | Selected |
|--------|-------------|----------|
| Excluded from report AND journal | Rejected picks surfaced in report footer only; journal stays clean. | ✓ |
| Excluded from report, appended to journal as negative ML sample | Broader training set with rejection_reason column. | |

**User's choice:** Excluded from report AND journal.
**Notes:** Keeps ML training set focused on actionable signals. Rejected picks appear in "## Skipped Picks" report section.

---

### ATR zone bucket count

| Option | Description | Selected |
|--------|-------------|----------|
| Two buckets: in-zone / chase-skip | ≤0.66×ATR = in-zone, >0.66×ATR = chase-skip. Simpler. | |
| Three buckets: in-zone / extended / chase-skip | ≤0.66×ATR = in-zone, 0.66–1×ATR = extended, >1×ATR = chase-skip. Aligns with Minervini layered entry. | ✓ |

**User's choice:** Three buckets — in-zone / extended / chase-skip.
**Notes:** The 0.66–1×ATR "extended" bucket signals a smaller-size entry opportunity rather than a hard skip.

---

## Claude's Discretion

- **21d EMA for VCP trail rule** — check if EMA is in the panel; if not, add to `indicators/trend.py` or compute inline in sizing.
- **`recent_swing_low_distance` lookback for leader_hold stop** — most recent argrelextrema trough within last 20 bars; fallback to 2×ATR if no trough found.
- **`entry_price` column naming** — `entry_price_estimate` vs `entry_price` (shorter); planner decides.

## Deferred Ideas

- **`journal-update` CLI flow** — v1.x after first 30 paper trades produce real outcomes.
- **`rejection_reason` column in journal for negative ML samples** — v1.x; evaluate once model needs more training signal.
- **Graded trail speed tiers** — v1.x; Phase 7 ships discrete ADR%-based tiers.
- **Journal analytics / decile spread report** — v1.x (CAT-V1X-01).
