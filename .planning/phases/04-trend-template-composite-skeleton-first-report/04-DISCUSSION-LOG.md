# Phase 4: Trend Template, Composite Skeleton & First Report - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 04-trend-template-composite-skeleton-first-report
**Areas discussed:** Composite skeleton gaps, Pivot price proxy, Pass-rate alerting, Preregistration CI gate

---

## Composite skeleton gaps

**Q1: How to handle missing components (Pattern, Earnings, Catalyst)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Zero them out | Missing components contribute 0; max score ~55/100 in Phase 4; honest | ✓ |
| Renormalize weights | Re-weight available components to 100%; scores span 0–100 but formula changes between phases | |
| Stub at neutral (0.5) | Missing components contribute 50% of weight; creates false confidence | |

**User's choice:** Zero them out

---

**Q2: Should Volume (dryup_ratio) be wired as the volume component?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — wire dryup_ratio | Already in panel; map to 0–1 score; carries 10% weight | ✓ |
| Zero it out too | Treat volume as unimplemented; Phase 4 max score ~45/100 | |

**User's choice:** Yes — wire dryup_ratio as the volume component

---

**Q3: Regime gate — hard zero in Correction or soft multiply?**

| Option | Description | Selected |
|--------|-------------|----------|
| Hard gate — zero in Correction | composite_score = 0.0 if Correction; no picks appear | |
| Soft — multiply by regime_score | composite *= regime_score; picks appear but scores compress | ✓ |

**User's choice:** Soft — multiply by regime_score

---

**Q4: Should report show live vs placeholder component labels?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — show placeholder labels | Format: RS=92 \| Trend=7/8 \| Pattern=—(Phase 6) \| ... | ✓ |
| Just show non-zero components | Omit zeroed from breakdown; cleaner but hides pending components | |

**User's choice:** Yes — show placeholder labels for missing components

---

## Pivot price proxy

**Q1: What stands in as the pivot for Phase 4?**

| Option | Description | Selected |
|--------|-------------|----------|
| 52-week high | MAX(High, 252) already in panel for Trend Template SC7; meaningful | ✓ |
| Recent 20-day high | Rough proxy; noisy; not grounded in playbooks | |
| Skip it | Show — placeholder; avoids misleading proxy | |

**User's choice:** 52-week high

---

**Q2: In-zone vs chase annotation in Phase 4?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — annotate in-zone vs chase | ≤1×ATR above 52w high = in-zone; >1×ATR = chase, skip | ✓ |
| Just show ATR distance number | Raw number only; user applies threshold judgment | |

**User's choice:** Yes — annotate in-zone vs chase now

---

## Pass-rate alerting

**Q1: Where does the >25% pass-rate alert surface?**

| Option | Description | Selected |
|--------|-------------|----------|
| Both — structlog + report banner | Belt and suspenders: catches it in logs AND daily report | ✓ |
| Structlog warning only | Visible in log stream; invisible in daily report | |
| Report banner only | Visible in report; invisible in pipeline monitoring | |

**User's choice:** Both — structlog warning AND report banner

---

**Q2: Fail the run when pass-rate >25% AND regime is Correction?**

| Option | Description | Selected |
|--------|-------------|----------|
| No — warn only, never fail | Alert is advisory; pipeline stays non-fatal | |
| Yes — fail loudly | >25% pass rate in Correction is almost certainly wrong; exit non-zero | ✓ |

**User's choice:** Yes — fail loudly when pass-rate >25% AND regime is Correction

---

## Preregistration CI gate

**Q1: How to enforce weights consistency in CI?**

| Option | Description | Selected |
|--------|-------------|----------|
| Grep check — parse and diff | Python script reads DEFAULT_WEIGHTS and doc table; fails with readable mismatch message | ✓ |
| SHA hash of doc section | Hash comparison; brittle (whitespace); two-file lockstep update required | |
| Import-and-compare in pytest | Test asserts hardcoded expected values; test and doc can drift independently | |

**User's choice:** Grep check — parse values from both files and diff

---

**Q2: Record git hash in preregistration doc?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — record git hash | "Frozen at commit: <sha>" line; tamper-evident registration | ✓ |
| No — just weights table and date | Simpler; git history is the audit trail | |

**User's choice:** Yes — record git hash in the doc at freeze time

---

## Claude's Discretion

- `make report` CLI wiring: whether `make report` calls `screener rank` piped to publish step, or a `screener report` subcommand that orchestrates the pipeline. Must not add a 10th subcommand beyond the locked 9.
- Snapshot Parquet column set: exact columns beyond minimum required (ticker, composite_score, rank, passes_trend_template, trend_template_score, regime_score, regime_state, pivot_zone).
- Markdown report layout: exact Markdown structure (tables, sections) consistent with the required field list.

## Deferred Ideas

- Full playbook tagging (Qullamaggie / Minervini VCP / leader-hold) — Phase 6
- Catalyst-flag annotations (insider buys, earnings proximity) — Phase 6
- Hard regime gate (zero composite in Correction) — revisit after paper-trade validation
- `make report` failure alerting via GitHub Actions — Phase 8
- Per-regime and per-playbook report breakdowns — Phase 6/7
