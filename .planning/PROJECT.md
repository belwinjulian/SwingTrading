# Momentum Swing Screener

## What This Is

A long-only, end-of-day swing-trading screener that scans the Russell 1000 every evening and produces a ranked list of stocks worth buying tomorrow. Each pick declares which playbook it fits — Qullamaggie continuation flag, Minervini VCP, or leader-hold — and surfaces a concrete entry, stop, and position size for that playbook. Built for Belwin (the user) to actually trade off, starting in paper mode.

## Core Value

Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. v1 hypotheses until paper-trade validated. -->

- [ ] Daily Russell 1000 EOD scan with cached OHLCV (yfinance + Stooq fallback)
- [ ] Minervini Trend Template gate (8 conditions, SMA-based)
- [ ] IBD-style relative-strength percentile rating (universe-relative, recomputed daily)
- [ ] VCP and continuation-flag pattern detection (pivot-based, with depth/volume contraction checks)
- [ ] Qullamaggie Setup A momentum scan (top-1–2% performer + ADR% + dollar-volume filters)
- [ ] Post-gap-continuation detection on D+1 (free-tier proxy for Setup B Episodic Pivot)
- [ ] Per-pick playbook tagging (Qullamaggie continuation / Minervini VCP / leader-hold) with style-specific entry, stop, and trail rules
- [ ] Composite confidence score (0–100) combining trend, RS, pattern, volume, regime — this *is* the v1 confidence number; ML probability is M2
- [ ] Market-regime gate (SPY 200d trend + breadth + distribution-day count + VIX) that scales position size
- [ ] ATR-based position sizing with risk ≤ 1×ADR per Qullamaggie rule
- [ ] Daily markdown report (top picks, entry/stop/size, playbook tag, regime state) committed nightly by GitHub Actions cron
- [ ] Paper-trade journal (CSV/SQLite) capturing every actionable pick + executed paper outcomes — *the M2 ML training set*
- [ ] Weekly universe snapshot (mitigates survivorship bias going forward)
- [ ] vectorbt backtest harness with walk-forward + honest reporting (slippage assumed, survivorship disclosed, no-look-ahead enforced)
- [ ] Reproducible local pipeline (`make data && make rank && make backtest`)

### Out of Scope

<!-- Explicit boundaries with reasoning. -->

- **LightGBM ML probability scoring + SHAP explanations** — Deferred to M2. Need real paper-trade labels first; training on synthetic/backtested labels overfits and is hard to debug live.
- **Streamlit dashboard (5-page Bloomberg-style UI)** — Deferred to M2/M3. Daily markdown report covers the evening-review workflow at a fraction of the build cost.
- **FinBERT news sentiment + Reddit/social buzz scoring** — Deferred. Personal-trading-first scope; weak headline-level signal not worth the data pipeline complexity in v1.
- **Pre-market and intraday scanning, opening-range entries, real-time gap scanner** — Out of scope. EOD-only workflow; user reviews after the close, places orders for next day.
- **Setup C (parabolic capitulation longs)** — Flagged but not actively traded; intraday-dependent and lower priority than continuation/VCP.
- **Cup-and-handle pattern detection** — Deferred to v2. Hardest to detect cleanly; VCP and continuation flag carry v1.
- **Real broker API integration (Robinhood / IBKR / Alpaca)** — Out of scope. Paper-trading first; real-money execution is gated on validated paper performance.
- **Paid data feeds (Polygon, Norgate, Alpha Vantage premium, IEX Cloud)** — Hard $0 budget. Accept survivorship bias and yfinance instability; mitigate with caching, retries, weekly universe snapshots.
- **PySpark scan, dbt+duckdb modeling layer** — Cut from v1. Personal-trading-first means engineering effort follows pick quality, not portfolio decoration.
- **Hosted dashboard / public live demo** — Deferred. Personal use is local + GitHub Actions cron.
- **Options activity, alternative data, satellite imagery, anything alt-data** — Out of scope.

## Context

- **User profile:** Belwin is a data engineer fluent in Python, PySpark, and SQL. The project is technically within reach; the bottleneck is methodology rigor and validation discipline, not engineering capability.
- **Trading status:** Not currently trading these picks. Paper-trading phase is the validation gate before any real capital. The journal must therefore capture actionable picks honestly (no hindsight cherry-picking).
- **Methodology source:** Three overlapping playbooks — Mark Minervini (SEPA / Trend Template), Kristjan Kullamägi / Qullamaggie (continuation flags, EP), and William O'Neil (CANSLIM). Detailed methodology lives in `CLAUDE.md`. v1 implements the rule-based core; CANSLIM fundamentals are a quality overlay.
- **Confidence score philosophy:** v1's confidence number is the rule-based composite (0–100). It is *interpretable by construction* — every component (trend pass, RS percentile, pattern tightness, volume confirmation, regime score) is auditable. The user trades from explainable signals first; the ML black box (M2) layers on top once it has paper-trade ground truth.
- **Per-pick style tagging:** A pick that scores high under Qullamaggie's runner playbook gets different entry/stop/exit guidance than a pick that scores high under Minervini's VCP. The system surfaces *which* playbook each candidate fits and emits playbook-specific trade plans.
- **Survivorship bias:** Real and known. yfinance returns current constituents; delisted names silently disappear. Disclosed openly; mitigated by snapshotting the Russell 1000 weekly so future backtests have a real point-in-time universe even though the historical record will be biased.
- **Free-tier reality:** yfinance breaks periodically; Finnhub is 60 calls/min; Alpha Vantage is unusable for universe scans (~25/day). Aggressive caching (Parquet on disk for OHLCV, requests-cache for HTTP), retry/backoff (`tenacity`), and incremental nightly appends are non-negotiable.

## Constraints

- **Budget**: $0/month for data and infrastructure — Hard rule. No paid feeds, no cloud SaaS beyond GitHub Actions free tier and (later) Streamlit Community Cloud.
- **Tech stack**: Python 3.11+, pandas, pandas-ta, vectorbt (community edition), GitHub Actions cron — Free, mainstream, fast iteration. No CUDA/TA-Lib C deps in v1 (avoid Streamlit Cloud install issues for M2 dashboard).
- **Data**: yfinance + Finnhub free + FRED + EDGAR (`edgartools`) + Stooq — Only free, durable sources. Survivorship bias accepted and disclosed.
- **Workflow timing**: Evening, post-close (US ET) — EOD-only. No intraday or pre-market dependencies in v1.
- **Universe**: Russell 1000 (~1,000 large/mid-caps) — Liquid, broad enough for daily breakouts, manageable for free-tier rate limits.
- **Output**: Markdown report + paper-trade journal — No UI in v1; dashboard is a later milestone.
- **Validation gate**: Paper trading required before any real-money sizing — Non-negotiable. The picks must demonstrate honest live performance, not just backtest performance, before risk capital follows.
- **Methodology fidelity**: Use SMAs (not EMAs) for the Trend Template; signals execute on next-bar open (not current-bar close); fundamentals lag 45 days post-quarter-end before being treated as known — Three rules from `CLAUDE.md` §11/§13 that are easy to violate accidentally and silently overstate backtest performance.
- **No deadline**: Build it right rather than ship by a date — User has time; favor correctness over speed-to-first-pick.

## Key Decisions

<!-- Significant choices that constrain future work. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Personal trading is the primary audience; portfolio polish is secondary | When trade-offs hit, the picks must work; PySpark/dbt/dashboard polish only earns its place if it improves picks | — Pending |
| Per-pick playbook tagging (Qullamaggie / Minervini / leader-hold), not single composite | A continuation flag and a VCP are different trades — same composite score should not imply the same trade plan | — Pending |
| Rules-first composite scoring in v1; LightGBM ML deferred to M2 | ML on synthetic/backtest labels overfits. Need real paper-trade outcomes (the v1 journal) as honest training data for M2 | — Pending |
| Daily markdown report in v1; Streamlit dashboard deferred to M2/M3 | Evening review workflow doesn't need a UI. Build the data layer right; UI follows once picks are trusted | — Pending |
| Free-only data sources; accept survivorship bias and disclose openly | $0 budget is a hard rule. Mitigation: weekly universe snapshots from day one to build a real point-in-time dataset going forward | — Pending |
| EOD-only; no intraday or pre-market in v1 | Evening-review workflow + free-tier APIs make intraday a poor fit. Setup C and EP intraday-entry deferred | — Pending |
| Paper trading required before real money | The journal validates the system on live (post-publication) picks, not backtests. Backtests overstate returns; paper trading does not | — Pending |
| Russell 1000 universe | Liquid enough that fills aren't an issue; wide enough for 5-15 daily breakout candidates; manageable under yfinance rate limits | — Pending |
| SMAs for Trend Template (not EMAs); next-bar-open execution; 45-day fundamentals lag | Three subtle methodology rules that, if violated, silently inflate backtest performance | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-03 — Phase 2 (Data Foundation) complete; DAT-01/02/03/06/07/08/09 satisfied; 39 tests passing; Phase 3 (Indicator Panel & Regime) next.*
