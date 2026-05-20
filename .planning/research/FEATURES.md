# Feature Research

**Domain:** Long-only momentum swing-trading screener (Russell 1000, EOD, free data, daily markdown report — personal-trading-first)
**Researched:** 2026-04-27
**Confidence:** HIGH (methodology and trader-rule sourcing well-documented; product-feature comparisons cross-verified across vendor pages and review sites)

---

## Executive Frame

The reference products fall into three buckets:

1. **Filter-driven screeners** (Finviz Elite, ChartMill, MarketInOut, TradingView screener). Strength: 70+ filters, fast iteration, charting. Weakness: they output a *list*, not a *trade plan*. The user still has to score, rank, and write the playbook themselves.
2. **Curated rating systems** (IBD MarketSurge / MarketSmith). Strength: proprietary 1–99 ratings (Composite, RS, EPS, A/D, SMR), AI pattern recognition. Weakness: $1,499/yr; ratings are opaque ("trust the score"); no playbook tagging beyond "stock looks like a base."
3. **Trader-curated daily lists** (Stockbee Bulletin, Qullamaggie's daily streams, TraderLion). Strength: opinionated, playbook-tagged, "go trade these tomorrow" actionable. Weakness: human-curated, doesn't scale, no audit trail, no backtest.

**This project's positional insight:** combine bucket 1's auditable rules with bucket 3's playbook-tagged, trade-plan-emitting output — at $0 cost and reproducible. The strongest differentiator is **per-pick playbook tagging with playbook-specific entry/stop/trail rules** — Finviz tells you a stock passes the Trend Template; this tool tells you "this is a Qullamaggie continuation flag — buy stop at $187.40, stop at $182.10, risk 0.7×ADR, trail on 10-SMA."

---

## Feature Landscape

### Table Stakes (Users Expect These)

A screener missing these would feel broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Daily Russell 1000 EOD scan** | Without a fresh universe scan, the report is stale and useless | M | yfinance + Stooq fallback, Parquet-on-disk cache, incremental nightly append |
| **Cached OHLCV with retry/backoff** | yfinance breaks weekly; without caching, scans fail nondeterministically | M | `tenacity` retry + `requests-cache` for HTTP + Parquet for OHLCV; 50–100ms delay between tickers |
| **Trend filter (Minervini Trend Template, 8 conditions)** | Universal momentum pre-filter; reference products all have it (ChartMill, Finviz custom screen, MarketSurge SmartSelect) | S | SMA-based (NOT EMA — easy bug); pure pandas; produces both bool gate and 0–8 partial score |
| **IBD-style RS percentile rating (1–99)** | Reference standard; every momentum tool produces one | S | `RS_raw = 2*(C/C_63)+(C/C_126)+(C/C_189)+(C/C_252)`, then percentile-rank universe-relative |
| **ATR / ADR%-based volatility metrics** | Required for stop placement, position sizing, Qullamaggie filters | S | `pandas-ta` ATR(14); ADR% = `100*(rolling_mean(high/low, 20) - 1)` |
| **Volume confirmation flags** | Breakout without volume = not a breakout; users distrust pure-price breakouts | S | 50-day up/down ratio, 5d/50d dryup ratio, breakout-day volume vs 50d-mean ratio |
| **VCP / continuation-flag pattern detection** | Core to Minervini and Qullamaggie playbooks; without pattern detection the screener is just a momentum sort | L | Pivot detection via `scipy.signal.argrelextrema`; depth/volume contraction rules; depends on ATR + volume features |
| **Per-pick entry, stop, and position size** | A pick without a trade plan is not actionable — user has to do the work the tool was supposed to do | M | ATR-based stop, Qullamaggie risk≤1×ADR rule, account-equity-aware sizing |
| **Composite confidence score (0–100)** | Without a single rankable number, top picks aren't surfaceable; reference standard (MarketSurge Composite Rating, ChartMill scores, Finviz custom rank) | M | Weighted: RS 25% / Trend 20% / Pattern 20% / Volume 10% / Earnings 15% / Catalyst 10% (starting weights — flagged for walk-forward validation) |
| **Score component breakdown per pick** | "Score = 84" without "RS=92, Trend=8/8, Pattern=tight, Vol=accumulation" is opaque; users distrust opaque scores | S | Render in the markdown report as a small table per pick |
| **Market-regime gate (SPY/breadth/distribution/VIX)** | Long-only momentum gets killed in 2008/2022 without a regime gate; non-negotiable per CLAUDE.md §2.5 | M | Three-state output (Confirmed Uptrend / Under Pressure / Correction) + continuous score multiplier on position size |
| **Daily markdown report** | The deliverable. Without it, the system isn't usable | S | Top 10–20 picks, regime banner, runtime metadata footer (universe size, scan time, refresh timestamp) |
| **Honest backtest harness** | Without backtests the screener is a hypothesis; reviewers and the user both need numerical evidence | L | vectorbt + walk-forward + slippage assumptions + survivorship-disclosed reporting |
| **No-look-ahead enforcement** | A backtest with look-ahead is worse than no backtest (overconfidence). Tested via dedicated `test_backtest_no_lookahead.py` | M | Signals at bar `t` execute at bar `t+1` open; pytest gate in CI |
| **Reproducible local pipeline** (`make data && make rank && make backtest`) | Same run on different days produces the same output for the same date — table stakes for any data engineer artifact | S | Idempotent Parquet writes; deterministic ordering; `Makefile` targets |
| **Weekly universe snapshot** | The only mitigation for survivorship bias on free data; without it future backtests are biased forever | S | Cron'd weekly snapshot of Russell 1000 constituents → Parquet, partitioned by date |
| **Historical OHLCV depth (≥ 252 trading days)** | Needed for 200-day SMA, 252-day RS, 52-week high/low calculations — core indicators are unusable without it | S | Cache layer must support backfill; nightly job appends only delta |
| **Corporate-action handling (splits/dividends)** | NVDA 2024 split would mis-trigger every breakout detector if unhandled | S | `yf.download(auto_adjust=True)` for indicators; preserve unadjusted copy for pivot-level integrity |
| **Sector / industry tagging** | Reviewer expectation; users want to see "is this a leader-led move or a one-off?" | S | `yfinance.Ticker.info` sector field; cache once, refresh weekly |

### Differentiators (Competitive Advantage)

These are where this tool beats $0 alternatives like Finviz free or DeepVue and earns the user's trust to actually trade off it.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-pick playbook tagging (Qullamaggie continuation / Minervini VCP / leader-hold)** | THE core differentiator. Finviz / ChartMill / MarketSurge produce a list; this produces a list where each pick declares which playbook it fits and emits playbook-specific trade plans. A continuation flag and a VCP are different trades — users currently make this judgment manually | M | See §"Playbook Tagging Logic" below. Depends on: Trend Template, VCP detector, flag detector, RS percentile, ADR%, regime |
| **Playbook-specific entry/stop/trail rules** | Qullamaggie continuation: buy-stop at consolidation high, stop=low-of-day, trail on 10/20/50-SMA per momentum tier. Minervini VCP: buy-stop at pivot, stop=low-of-final-contraction, trail on 50-SMA. Leader-hold: weekly close > 10-week MA, looser exit. Each pick gets the right plan, not a generic one | M | Encoded as small playbook objects in `signals/`; depends on playbook tagging |
| **Auditable composite score (every component is interpretable)** | MarketSurge Composite Rating is a black box (proprietary). Here every component is sourced, scored, and rendered. The user can disagree with a single component and override — paper journal captures both system and user reasoning | S | Already in the design (`composite.py`); ensure markdown renders per-component values |
| **Regime-scaled position sizing (built into the report)** | Most screeners output picks regardless of regime; this tool reduces the suggested position size in "Under Pressure" and pauses new entries in "Correction." The size shown is *already regime-adjusted*, not an academic ATR number | S | `regime_score ∈ [0, 1]` multiplies into base risk per CLAUDE.md §2.6 |
| **Risk-≤-1×ADR rejection (Qullamaggie's rule, automated)** | If `(entry - stop) > 1×ADR_dollars`, the pick is auto-rejected even if all other signals pass. Most screeners list everything; this rejects mathematically broken R/R automatically | S | Single boolean gate after entry/stop are computed |
| **Paper-trade journal designed as ML training data (M2)** | A journal that captures every actionable pick — including ones not taken — with all score components at signal time. This becomes the LightGBM training set in M2; it's also the honest validation gate for live capital | M | SQLite schema: pick_id, date, ticker, playbook, all score components, regime state, suggested entry/stop/size, paper-executed (Y/N), executed_entry, executed_stop, executed_exit, exit_reason, R-multiple realized, mistake tags |
| **Walk-forward OOS Sharpe distribution (not single number)** | A single backtest Sharpe is a fitted lie. Walk-forward distribution is the honest answer. Almost no retail screener does this; the ones that do (TrendSpider) charge for it | M | Already in CLAUDE.md §6.4; expose distribution chart + 5th-percentile DD in the backtest report |
| **Score-decile spread report (top decile vs bottom decile, weekly rebalance)** | Standard quant-research presentation that demonstrates score monotonicity — convincing to a hiring manager and an honest signal to the user that the score actually ranks | M | Equal-weight top-decile vs bottom-decile, rolling. Output as a single chart per backtest run |
| **Honest data-quality footer (universe size, scan time, refresh timestamp, source health)** | "Last refresh: 2026-04-28 22:30 UTC \| universe: 998 \| yfinance OK \| Finnhub 47/60 calls \| scan: 3.4s" — operational honesty that signals professionalism and surfaces drift early | S | Already aligned with CLAUDE.md §9.3; add to markdown report footer |
| **Pivot tightness as a continuous feature, not just a gate** | "Final contraction: 7.8%" is more useful than "VCP=True." The tightness is the *quality* signal; surface it in the per-pick breakdown | S | Already implicit in pattern detector; ensure exposed in scoring |
| **Distance-from-pivot in ATRs (the buy-zone metric)** | Qullamaggie's buy zone is half-to-two-thirds ATR above prior close. Surface "currently 0.4×ATR above pivot — in zone" or "currently 1.8×ATR above pivot — chase, skip" | S | Single derived feature, surfaced in the report's "Action" column |
| **Industry RS rank as a score booster** | Group-leadership tenet from O'Neil/Minervini; aggregating member-stock RS to industry-level rank gives a leadership filter most retail tools don't have | M | Depends on sector mapping; bump composite score for top-quartile industry RS |

### Anti-Features (Deliberately Excluded)

These are commonly built or commonly demanded, but actively wrong for this project's scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time / intraday alerts** | "I want to know the moment a stock breaks out" | Scope explicitly EOD-only; intraday data is not free at scale; alerts encourage emotional trading; user reviews evening and orders next day | EOD report; user sets next-day buy-stops manually |
| **Pre-market gap scanner** | EP setup is gap-driven; "I want to catch the gap" | Out of scope per PROJECT.md; needs paid pre-market data; intraday execution conflicts with EOD workflow | Post-gap-continuation detection on D+1 (in active scope as proxy for Setup B) |
| **In-app order entry / broker integration** | "Just place the trade for me" | Out of scope per PROJECT.md; paper-trading first is non-negotiable; real-money execution gated on validated paper performance | User executes manually after morning review of report |
| **Streamlit / web dashboard in v1** | "It looks unprofessional without a UI" | Deferred to M2/M3 per PROJECT.md; markdown report covers evening-review at 1/10th the build cost; UI before validated picks is decoration | Daily markdown report committed by GitHub Actions cron; M2 dashboard rendered against same data layer |
| **LightGBM probability score in v1** | "ML signals are stronger than rules" | Deferred to M2 per PROJECT.md; ML on synthetic / backtested labels overfits and is unfalsifiable; need real paper-trade outcomes (the v1 journal) as honest training data | Rules-based composite score is the v1 confidence number; ML layers on top in M2 |
| **FinBERT news sentiment + Reddit social buzz** | "Sentiment matters" | Deferred per PROJECT.md; weak headline-level signal; data pipeline complexity not worth v1 effort; WSB is contrarian at extremes | Catalyst flag in v1 is binary "earnings within 7d Y/N"; sentiment in M2/M3 if validated |
| **Cup-and-handle pattern detection** | "Classic O'Neil pattern, must have it" | Deferred to v2 per PROJECT.md; hardest to detect cleanly (requires curve-fitting + symmetry checks); VCP and continuation flag carry v1 | VCP captures the common case; cup-and-handle is a nice-to-have |
| **Setup C (parabolic capitulation longs)** | "Qullamaggie's third setup" | Out of scope per PROJECT.md; intraday-dependent; lower edge than continuation/VCP; flag candidates only | Surface as informational flag, no trade plan emitted |
| **Options activity / unusual options flow** | "Smart money signals" | Out of scope per PROJECT.md; no reliable free source; conflicts with $0 budget rule | Skip entirely; do not pretend to have the data |
| **Alternative data (satellite, credit-card, web traffic)** | "Edge from non-public data" | Out of scope; all paid; conflicts with $0 budget; not the project's edge | Skip entirely |
| **Multi-account portfolio management / position aggregation** | "Show me my whole portfolio" | Personal-trading-first; user's actual brokerage account is separate from the screener's paper journal; conflating them creates confusion | Paper journal stays separate from any real-money tracking |
| **Short-side / inverse momentum signals** | "Short the laggards" | Project is explicitly long-only per PROJECT.md; symmetric short logic doubles complexity for no scope value | Skip; out of scope |
| **Over-decorated dashboard with 50 indicators per chart** | "Bloomberg-style" | Decoration before correctness; M2/M3 dashboard concern, not v1 | Markdown report; M2 dashboard kept disciplined |
| **Hosted / public live demo** | "Portfolio piece needs a live URL" | Deferred per PROJECT.md; personal use is local + GitHub Actions cron; public deploy is M3 work | Local pipeline + private-repo nightly cron; M3 deploys to Streamlit Cloud once validated |
| **Hourly / 5-minute regime updates** | "Regime changes intraday" | EOD scope; CLAUDE.md regime model is daily; intraday regime requires 5-min SPY data and adds complexity for the wrong workflow | Daily regime computation; EOD-only state |
| **Configurable strategy DSL / "build your own setup" UI** | "What if I want a different setup?" | Massive scope creep; the three playbooks are the project; user can edit YAML config for thresholds | Strategy parameters in `config/strategies.yaml`; no DSL |

### Nice-to-Have (Defer)

Real value, but not v1.

- **Catalyst tagging (earnings within 7 days, recent 52w-high cross)** — S — Cheap to add via Finnhub free; useful context. Mark as v1.x if Finnhub rate limit holds.
- **Insider cluster-buy flag (EDGAR Form 4)** — M — `edgartools` makes this tractable; defer to v1.x once core picks validate.
- **Industry-level relative-strength heatmap** — M — Sector context for picks; informational only.
- **Cup-and-handle pattern (v2)** — L — Defer per PROJECT.md.
- **PySpark parallel scan** — M — Cut from v1 per PROJECT.md; only earns place at >5,000-ticker universe.
- **dbt + DuckDB modeling layer** — M — Cut from v1; portfolio polish only.
- **Streamlit dashboard** — L — M2 milestone.
- **LightGBM ML probability + SHAP** — L — M2 milestone, needs paper-journal labels first.

---

## Playbook Tagging Logic (Differentiator Detail)

This is the core differentiator and deserves explicit specification — it's the rule that separates this tool from a generic screener.

A pick can be tagged as **one of**: `Qullamaggie continuation`, `Minervini VCP`, or `Leader hold`. Tags are mutually-exclusive at report time (one tag per pick); the underlying detection runs all three in parallel and the strongest match wins.

### Tagging Rules

**Tag = `Qullamaggie continuation`** when:
- Top 1–2% performer over 1m or 3m or 6m (the "scan") AND
- ADR%(20) ≥ 4 AND
- Avg dollar volume > $1.5M AND
- Continuation-flag pattern detected (5–25 bar consolidation along rising 10/20/50 SMA, higher lows, range tightening, volume contracting) AND
- Pattern is *short* (≤ 25 bars) — runs faster than VCPs

**Tag = `Minervini VCP`** when:
- Trend Template passes (8/8 conditions) AND
- VCP pattern detected (≥ 2 contractions, each smaller, final contraction ≤ 12%, volume contracts in step) AND
- Pattern is *longer* (25–65 bars, 5–13 weeks) — Minervini bases are fuller AND
- Final contraction ≤ 10% (the "tight right side") for premium tag

**Tag = `Leader hold`** when:
- Trend Template passes (8/8) AND
- RS rating ≥ 90 AND
- No active VCP or flag pattern (stock is trending but not in a base) AND
- Close > SMA(10-week) — i.e., not actionable as breakout but qualifies as ride-the-trend

### Tie-Breaking Priority

When multiple playbooks match the same stock:
1. **Qullamaggie continuation** wins if pattern is < 25 bars and ADR% ≥ 5 (faster movers go to the runner playbook)
2. **Minervini VCP** wins if pattern is ≥ 25 bars or final contraction ≤ 8% (tighter, longer bases go to the VCP playbook)
3. **Leader hold** is the fallback when no actionable pattern is present

Edge case: if Trend Template fails but Qullamaggie scan passes, tag as `Qullamaggie continuation` (Qullamaggie's rules don't require strict Trend Template — only momentum + ADR + flag).

### Per-Tag Trade Plan Emitted

| Tag | Entry | Stop | Risk Cap | Initial Trim | Trail Rule |
|-----|-------|------|----------|-------------|------------|
| Qullamaggie continuation | Buy stop at consolidation high | Low of entry day | ≤ 1×ADR ($) | 33–50% off after 3–5 days of profit | 10-SMA (fastest movers) / 20-SMA (medium) / 50-SMA (slowest) — pick by ADR% tier |
| Minervini VCP | Buy stop at pivot (final-contraction high) | Low of final contraction | ≤ 1×ADR ($), prefer < 0.5×ADR | None (full position rides) | 50-SMA close-below; cut on Trend Template break |
| Leader hold | None (already in trend; can scale on weekly close > 10-week MA pullback) | Below recent swing low | 1.5–2.0×ADR (looser) | None | Weekly close < 10-week MA |

### Why This Matters

Two stocks both scoring composite=85 might be radically different trades:
- A Qullamaggie continuation: 5–15 day hold, 10-SMA trail, 1×ADR risk, 33% trim early
- A Minervini VCP: 4–8 week hold, 50-SMA trail, 0.5×ADR risk, full ride
- A Leader hold: months-long hold, weekly trail, looser stop

A composite score alone can't tell the user any of this. The playbook tag does. **This is the feature that makes the tool actually tradable, not just informational.**

---

## Markdown Report Spec (Per-Pick Fields)

The daily markdown report is the only v1 output surface; getting its content right is critical.

### Per-Pick Block (One Block Per Top 10–20 Pick)

```markdown
### #1 NVDA — Qullamaggie Continuation — Score 87

**Setup:** 12-bar flag on rising 10-SMA, range tightening (last 5 bars within 0.6×ATR)
**Action:** Buy stop $187.40 (consolidation high) | Stop $182.10 (low of yesterday) | Risk $5.30/sh = 0.7×ADR
**Size:** 145 shares @ $187.40 = $27,173 (regime-adjusted from base 0.75% risk)
**Trail:** 10-day SMA close-below

**Why:**
| Component | Value | Score |
|---|---|---|
| RS Rating | 96 (top 4%) | 24/25 |
| Trend Template | 8/8 pass | 20/20 |
| Pattern (flag tightness) | final contraction 6.2% | 18/20 |
| Volume | accumulation (50d up/down = 1.42) | 9/10 |
| Earnings momentum | last quarter EPS +38% YoY | 12/15 |
| Catalyst | earnings 12 days ago, beat | 4/10 |
| **Composite** | | **87/100** |

**Context:** Top 1% performer 3m (+71%); industry RS rank 4th of 11 (top quartile);
sector: Information Technology. Distance from pivot: 0.3×ATR (in buy zone).
```

### Report Header

```markdown
# Daily Watchlist — 2026-04-28

**Regime:** Confirmed Uptrend (score 0.84) | SPY > 200d ✓ | Breadth 67% | DD count 2/25 | VIX 14.2
**Position-size multiplier:** 1.00× (full size)
**Picks below:** 12 actionable | 8 leader-hold flagged | 0 Setup C parabolics
```

### Report Footer

```markdown
---
*Last refresh: 2026-04-28 22:30 UTC | Universe: 998 R1000 | Scan: 3.4s
yfinance OK | Finnhub 47/60 calls used | next refresh: 2026-04-29 22:30 UTC*
```

---

## Paper-Trade Journal Schema (M2 Training Set)

Every actionable pick is logged regardless of whether the user paper-executes. This is critical: the **non-executed picks are the negative samples** the M2 ML model needs.

### Required Fields

| Field | Type | Source | Why Critical |
|---|---|---|---|
| `pick_id` | UUID | generated | Stable join key |
| `date_published` | date | report date | Time-series anchor |
| `ticker` | str | screener | — |
| `playbook` | enum | playbook tagger | Ground truth for per-playbook performance analysis |
| `composite_score` | float | scorer | The v1 confidence number — and the M2 ML target's strongest baseline feature |
| `score_rs` / `score_trend` / `score_pattern` / `score_volume` / `score_earnings` / `score_catalyst` | float | scorer | Component breakdown — required to debug live divergence |
| `regime_state` | enum | regime module | Trades in different regimes are not comparable |
| `regime_score` | float | regime module | Continuous version |
| `suggested_entry` / `suggested_stop` / `suggested_size` | float | sizer | What the system told the user to do |
| `adr_pct` / `atr_dollars` / `rs_rating` | float | indicators | Useful slicers for analysis |
| `paper_executed` | bool | user | Did the user paper-trade it? |
| `executed_entry` / `executed_entry_date` | float / date | user | Real fill (or simulated) |
| `executed_stop_initial` | float | user | The user may override system stop |
| `executed_exit` / `executed_exit_date` / `exit_reason` | float / date / enum | user | enum: stop_hit / trail_stop / trim / target / time_stop / discretionary / thesis_invalidated |
| `r_multiple_realized` | float | computed | (exit - entry) / (entry - stop_initial) |
| `mistake_tags` | list[str] | user | "chased entry," "moved stop down," "exited too early," "ignored regime," etc. |
| `notes` | text | user | Free-form post-hoc commentary |

### Critical Discipline

The journal must capture the **thesis at signal time, not at exit time** (a known journaling pitfall — hindsight bias makes winners obvious in retrospect). The published markdown report itself serves as the at-signal-time thesis (immutable; committed to git nightly). The journal layers user actions and outcomes on top.

---

## Backtest Reporting (Honest Numbers)

### Required Metrics (Show All, Not Cherry-Pick One)

| Metric | Why Required |
|---|---|
| CAGR | Top-line return |
| Sharpe (rf=0) | Standard reference |
| **Sortino** | Better for skewed momentum returns; downside-vol focused |
| **Calmar** (CAGR / max DD) | Drawdown-aware; momentum strategies have ugly DDs |
| Max DD | Pain |
| Win rate | Strategy character |
| **Profit factor** (gross win / gross loss) | Edge per dollar risked; > 1.75 strong |
| **Expectancy per trade** ($ or R) | Per-trade edge |
| Exposure (% time in market) | Honest comparison vs B&H |
| Turnover | Cost sensitivity |
| **vs SPY alpha and beta** (monthly OLS) | Required by any reviewer |
| **Walk-forward OOS Sharpe distribution** | Single fitted Sharpe is a lie; distribution is the answer |
| **Decile-spread (top - bottom decile, equal-weight, weekly rebalance)** | Demonstrates score monotonicity |
| **Performance by playbook tag** | Critical for this project — does Qullamaggie or Minervini contribute the alpha? |
| **Performance by regime state** | Sanity-check the regime gate is doing its job |
| **5th-percentile max DD from Monte-Carlo block-bootstrap** | Honest worst-case for sizing decisions |

### Mandatory Disclosures (in Backtest Report Header)

- Universe used (and survivorship-bias caveat)
- Period covered
- Slippage assumed (default: 5 bps liquid, 25 bps thin)
- Commission assumed (0)
- Look-ahead test: passed
- Number of parameter combinations tested (and flag if walk-forward not used → results suspect)

---

## Feature Dependencies

```
[OHLCV cache + retry/backoff]
    └──> [Indicators: SMA, ATR, ADR%, volume]
              ├──> [Trend Template]
              │        └──> [Composite score]
              ├──> [RS percentile (universe-wide)]
              │        └──> [Composite score]
              ├──> [Pattern detection: VCP, flag]
              │        └──> [Composite score]
              │        └──> [Playbook tagging]
              ├──> [Regime module (SPY + breadth + DD count + VIX)]
              │        └──> [Position sizing multiplier]
              │        └──> [Markdown report header banner]
              └──> [Volume features (up/down ratio, dryup, breakout vol)]
                       └──> [Composite score]

[Trend Template] + [Pattern detection] + [Qullamaggie scan] + [RS percentile]
    └──> [Playbook tagging]
              └──> [Per-tag trade-plan emitter]
                       └──> [Markdown report per-pick block]

[Composite score] + [Playbook tag] + [Trade plan]
    └──> [Markdown report]
              └──> [Paper-trade journal entry (auto-logged at publish time)]
                       └──> [Performance review / M2 ML training set]

[Composite score] + [Regime] + [Sizing] + [No-look-ahead enforcement]
    └──> [vectorbt backtest harness]
              └──> [Walk-forward + decile-spread + per-playbook + per-regime breakdowns]

[Russell 1000 universe builder]
    ├──> [Weekly snapshot (for survivorship mitigation)]
    └──> [Daily scan target]

[Reproducible Makefile pipeline]
    └──> wraps everything
```

### Key Dependency Notes

- **Pattern detection is the longest pole.** VCP and flag detection feed both composite scoring and playbook tagging. If pattern detection is weak, the differentiator collapses. Spend disproportionate engineering time here.
- **Playbook tagging requires Trend Template + RS + pattern detection + ADR%.** It's not standalone — sequence carefully in roadmap (these foundations come first).
- **Regime module gates everything.** It must work *before* the markdown report is published; the regime banner at the top sets expectations for the entire report.
- **Paper journal must be wired before backtest harness is "done."** The journal is the M2 training set; if v1 ships without it, M2 has no honest data.
- **No-look-ahead test must exist before any backtest result is quoted.** Quoting a backtest Sharpe without the look-ahead gate is a credibility-killer with reviewers.

---

## MVP Definition

### Launch With (v1)

The minimum that makes the tool reliable enough for the user to paper-trade off it.

- [ ] OHLCV cache layer (yfinance + Stooq fallback, retry/backoff, Parquet on disk) — **foundation**
- [ ] Russell 1000 universe builder + weekly snapshot — **foundation, survivorship mitigation**
- [ ] Indicators: SMA(10/20/50/150/200), ATR(14), ADR%(20), volume features — **foundation**
- [ ] IBD-style RS percentile (universe-relative, daily) — **table stakes**
- [ ] Minervini Trend Template (8 conditions, SMA-based) — **table stakes**
- [ ] VCP pattern detector (pivot-based, depth/volume contraction) — **table stakes**
- [ ] Continuation-flag pattern detector — **table stakes**
- [ ] Qullamaggie Setup A scan (top 1–2% + ADR + dollar volume) — **table stakes**
- [ ] Post-gap-continuation D+1 detection (free-tier proxy for Setup B) — **table stakes**
- [ ] Composite score (0–100, six components, weights flagged for walk-forward) — **table stakes**
- [ ] Market regime gate (SPY trend + breadth + DD count + VIX, three states + continuous score) — **table stakes**
- [ ] ATR-based position sizer with Qullamaggie risk-≤-1×ADR rejection — **table stakes**
- [ ] **Per-pick playbook tagging (Qullamaggie continuation / Minervini VCP / leader-hold)** — **THE differentiator**
- [ ] **Per-tag trade-plan emitter (entry/stop/size/trail per playbook)** — **THE differentiator**
- [ ] Daily markdown report with regime banner + per-pick blocks + ops footer — **the output**
- [ ] Paper-trade journal (SQLite) auto-logging every actionable pick at publish time — **M2 prerequisite**
- [ ] vectorbt backtest harness with walk-forward + per-playbook + per-regime breakdowns — **table stakes**
- [ ] No-look-ahead enforcement test — **non-negotiable credibility gate**
- [ ] Reproducible local pipeline (`make data && make rank && make backtest`) — **table stakes**
- [ ] GitHub Actions nightly cron that publishes the report — **the workflow**

### Add After Validation (v1.x)

Add once core picks are validating in paper-trading and the user trusts the report.

- [ ] **Catalyst tagging** (earnings within 7d, recent 52w-high cross) — cheap, useful context. Trigger: after first 30 paper trades.
- [ ] **Insider cluster-buy flag** (EDGAR Form 4 via `edgartools`) — adds texture to picks. Trigger: after journal shows fundamentals matter.
- [ ] **Industry RS rank as score booster** — leadership filter. Trigger: when picks cluster suspiciously in lagging industries.
- [ ] **Score-decile spread report** in backtest output — trigger: after first walk-forward result is in.
- [ ] **Performance attribution by playbook tag** — trigger: after 60+ paper trades to have meaningful per-tag samples.
- [ ] **Mistake-tag taxonomy in journal** — trigger: after first painful loss the user wants to learn from.

### Future Consideration (v2+)

Defer until v1 is paper-validated and the user is trading off the report.

- [ ] **LightGBM ML probability + SHAP** (M2) — needs paper-journal labels first
- [ ] **Streamlit dashboard** (M2/M3) — daily markdown covers the workflow at a fraction of cost
- [ ] **FinBERT news sentiment + Reddit social buzz** — weak signal, defer until validated
- [ ] **Cup-and-handle pattern detection** (v2) — hardest to detect cleanly
- [ ] **Setup C parabolic capitulation longs** — intraday-dependent
- [ ] **Hosted public live demo** — M3 deploy concern
- [ ] **PySpark parallel scan** — only earns place at >5,000-ticker universe
- [ ] **dbt + DuckDB modeling layer** — portfolio polish, not pick quality

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| OHLCV cache layer with retry/backoff | HIGH | MEDIUM | P1 |
| Indicators (SMA/ATR/ADR%/volume) | HIGH | LOW | P1 |
| IBD-style RS percentile | HIGH | LOW | P1 |
| Minervini Trend Template | HIGH | LOW | P1 |
| VCP pattern detector | HIGH | HIGH | P1 |
| Continuation-flag detector | HIGH | MEDIUM | P1 |
| Qullamaggie Setup A scan | HIGH | LOW | P1 |
| Composite score (with component breakdown) | HIGH | MEDIUM | P1 |
| Market-regime gate | HIGH | MEDIUM | P1 |
| ATR-based sizer + 1×ADR rejection | HIGH | LOW | P1 |
| **Per-pick playbook tagging** | **HIGH** | **MEDIUM** | **P1 (differentiator)** |
| **Per-tag trade-plan emitter** | **HIGH** | **MEDIUM** | **P1 (differentiator)** |
| Daily markdown report | HIGH | LOW | P1 |
| Paper-trade journal (auto-log at publish) | HIGH | MEDIUM | P1 |
| vectorbt backtest harness + walk-forward | HIGH | HIGH | P1 |
| No-look-ahead test | HIGH | LOW | P1 |
| Weekly universe snapshot | MEDIUM | LOW | P1 |
| GitHub Actions nightly cron | HIGH | LOW | P1 |
| Post-gap-continuation D+1 detection | MEDIUM | MEDIUM | P1 |
| Sector/industry tagging | MEDIUM | LOW | P1 |
| Catalyst tagging (earnings within 7d) | MEDIUM | LOW | P2 |
| Insider cluster-buy flag | MEDIUM | MEDIUM | P2 |
| Industry RS rank booster | MEDIUM | MEDIUM | P2 |
| Score-decile spread in backtest | MEDIUM | MEDIUM | P2 |
| Per-playbook performance attribution | MEDIUM | LOW | P2 |
| Mistake-tag taxonomy in journal | MEDIUM | LOW | P2 |
| LightGBM ML probability + SHAP | HIGH | HIGH | P3 (M2) |
| Streamlit dashboard | MEDIUM | HIGH | P3 (M2/M3) |
| FinBERT sentiment | LOW | HIGH | P3 |
| Reddit social buzz | LOW | MEDIUM | P3 |
| Cup-and-handle | LOW | HIGH | P3 (v2) |
| Setup C parabolic | LOW | HIGH | P3 |
| PySpark scan | LOW | LOW | P3 (portfolio decoration) |
| dbt + DuckDB layer | LOW | MEDIUM | P3 (portfolio decoration) |

**Priority key:**
- P1: v1 launch (must have or it's not the product)
- P2: v1.x (add post-validation as triggers fire)
- P3: M2+ / future

---

## Competitor Feature Analysis

| Feature | Finviz Elite ($39/mo) | TradingView (free/paid) | IBD MarketSurge ($1,499/yr) | Stockbee Bulletin (subscription) | This Tool ($0) |
|---|---|---|---|---|---|
| Universe filtering (60+ filters) | Yes, fast | Yes, broad | Limited (preset) | Hand-curated | Russell 1000 only, but methodology-driven |
| Trend Template / momentum gate | Custom-build (filters) | Pine Script DIY | SmartSelect Composite Rating | Implicit in lists | Native + auditable + scored partial-pass |
| RS percentile | No (no native rating) | DIY in Pine | IBD RS Rating 1–99 (proprietary) | Implicit | IBD-style 1–99, transparent formula |
| VCP detection | Manual (pattern scanner only catches generic patterns) | Pine Script community indicators | AI pattern recognition (proprietary) | Manual | Native pivot-based detector with depth/volume rules |
| Continuation flag detection | No native | Pine Script DIY | Some (chart pattern AI) | Manual | Native |
| **Playbook tagging per pick** | **No** | **No** | **No** | **Implicit (human curator)** | **YES — core differentiator** |
| **Playbook-specific trade plan** | **No** | **No** | **No** | **Sometimes (text commentary)** | **YES — entry/stop/size/trail per tag** |
| Regime gate | No | DIY | Some (market in confirmed uptrend flag) | Yes (text commentary) | Native, three-state + continuous score, gates sizing |
| ATR-based sizer | No | DIY | No | No | Native, Qullamaggie 1×ADR rule auto-rejects |
| Backtesting | No | Yes (Pine Strategy) | Limited | No | vectorbt + walk-forward + per-playbook attribution |
| Walk-forward / OOS distribution | No | Limited | No | No | Yes |
| Honest survivorship-bias disclosure | No | No | No | No | Yes (footer + README + weekly snapshot mitigation) |
| Paper-trade journal | No | Limited | No | No | Native, auto-logged, M2 ML training set |
| Cost | $39/mo | $0–$60/mo | $1,499/yr | Subscription | $0 |
| Reproducible / auditable | No | Partial | No | No | Yes (committed code + nightly artifacts) |

**Where this tool wins:** playbook tagging, playbook-specific trade plans, auditable composite, regime-scaled sizing, honest backtest reporting, $0 cost, reproducible pipeline.

**Where comparables win:** breadth of filters (Finviz), real-time data (Finviz, TradingView), AI pattern recognition (MarketSurge), pre-built community scripts (TradingView). All explicitly out of v1 scope.

---

## Honest Gaps and Open Questions

These should flow forward as research flags for later phases.

1. **Composite weights are starting points, not validated.** §2.7 of CLAUDE.md flags this. Walk-forward weight optimization in v1 backtest harness is required *before* the user paper-trades on the system at full size.
2. **VCP detection thresholds are heuristic.** The recommended starting values in CLAUDE.md §13.4 come from community implementations; tune via golden-file tests on known historical VCPs (NVDA 2023 base, AAPL 2020 base, NVDA 2024 split-adjusted).
3. **Playbook-tagging tie-breaker rules need empirical tuning.** The proposed rules above are reasonable defaults; the *correct* tie-breaker comes from observing which tag's trade plan actually worked in paper-trading.
4. **Catalyst flag is binary in v1 (earnings within 7d Y/N).** Richer catalyst signals (analyst upgrades, insider clusters) deferred to v1.x.
5. **Leader-hold playbook is the loosest defined.** Without a clean entry trigger (it's a "ride the trend" tag), how the user actions a leader-hold pick is subtle — possibly "scale on weekly close > 10-week MA pullback." Validate with paper trading; may collapse into "informational only" tag.
6. **Post-gap-continuation D+1 detection** as a Setup B proxy is novel — no comparable tool offers this; the rule needs to be specified concretely (gap > 8% on day 0, day-1 closes in upper third of range, day-2 entry?). Flag for phase-specific research.

---

## Sources

### Reference Products
- [Finviz Elite — Stock Screener](https://finviz.com/elite)
- [Finviz Elite Review (2026)](https://traderhq.com/finviz-elite-review-best-stock-screener-tool/)
- [How to Use Finviz for Stock Screening (2026 Guide)](https://tradingtoolshub.com/blog/how-to-use-finviz-for-stock-screening-step-by-step-guide/)
- [MarketSurge Review (2026): IBD's Pro Platform](https://traderhq.com/marketsurge-review-data-driven-stock-analysis-smart-investors/)
- [MarketSurge Review — WallStreetZen](https://www.wallstreetzen.com/blog/ibd-marketsurge-review/)
- [Using IBD SmartSelect Ratings (PDF)](http://gimonline.net/Module_5_User.pdf)
- [TrendSpider vs DeepVue Comparison](https://trendspider.com/compare-trendspider/deepvue/)
- [Top 10 Swing Trading Screeners — DeepVue](https://deepvue.com/screener/top-10-swing-trading-screens/)
- [ChartMill — Mark Minervini Trend Template Guide](https://www.chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/496-Mark-Minervini-Trend-Template-A-Step-by-Step-Guide-for-Beginners)
- [ChartMill — Minervini Stocks Screen](https://www.chartmill.com/stock/markets/usa/screener/minervini-stocks)
- [Stockbee — Creating a Watchlist](https://stockbee.blogspot.com/2022/10/creating-watchlist.html)
- [Stockbee — How to Identify Good Momentum Burst](https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html)
- [Stockbee — 30-Day Momentum Watchlist](https://stockbee.blogspot.com/2022/08/30-day-momentum-to-build-watchlist.html)
- [Stockbee Screener — Momentum Burst Scanner (TradingView)](https://www.tradingview.com/script/aUbyMkHj-Stockbee-Screener-Momentum-Burst-Episodic-Pivot-Scanner/)

### Methodology
- [Qullamaggie — 3 Timeless Setups](https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/)
- [Qullamaggie — FAQ](https://qullamaggie.com/faq/)
- [Qullamaggie's Laws of Swing (community summary)](https://www.scribd.com/document/655331063/Qullamaggie-s-Laws-of-Swing)
- [AsymTrading — Leveraging ADR for Reward-to-Risk](https://x.com/AsymTrading/status/1872319904487297284)
- [Qullamaggie Swing Trading Setups — Tikam Singh Alma](https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups)
- [PaulStifler's Method (Qullamaggie variant)](https://qullamaggie.net/paulstiflers-method/)
- [VCP Pattern Explained — TrendSpider](https://trendspider.com/learning-center/volatility-contraction-pattern-vcp/)
- [VCP Trading Guide — Tradingsim](https://www.tradingsim.com/blog/volatility-contraction-pattern)
- [VCP Complete Guide — FinerMarketPoints](https://www.finermarketpoints.com/post/what-is-a-vcp-pattern-mark-minervini-s-volatility-contraction-pattern-explained)
- [Mastering VCP — TraderLion](https://traderlion.com/technical-analysis/volatility-contraction-pattern/)
- [Minervini Step-by-Step Guide — QuantVPS](https://www.quantvps.com/blog/mark-minervinis-guide-to-finding-winning-stocks)
- [VCP — Deepvue](https://deepvue.com/screener/volatility-contraction-pattern/)

### Trade Journal & Backtesting
- [Swing Trading Journal: 12 Fields That Matter](https://traderssecondbrain.com/guides/trading-journal-for-swing-trading)
- [Swing Trading Journal: What to Track — JournalPlus](https://journalplus.co/blog/trading-journal-for-swing-traders/)
- [Best Swing Trading Trade Log — Trade That Swing](https://tradethatswing.com/the-best-swing-trading-trade-log-for-stocks-download-2022-excel/)
- [Pro Trader Dashboard — Complete Swing Trader Journal Guide](https://protraderdashboard.com/blog/swing-trading-journal/)
- [Top 7 Backtesting Metrics — LuxAlgo](https://www.luxalgo.com/blog/top-7-metrics-for-backtesting-results/)
- [Performance Metrics Explained — OptionAlpha](https://optionalpha.com/learn/performance-metrics)
- [Trading Performance Metrics — QuantifiedStrategies](https://www.quantifiedstrategies.com/trading-performance/)
- [Advanced Trading Metrics: Sharpe/Sortino/Calmar/SQN — AlgoStrategyAnalyzer](https://algostrategyanalyzer.com/en/blog/advanced-trading-metrics/)

### Market Regime
- [US Stock Momentum Trading System — Cracking Markets](https://www.crackingmarkets.com/us-stock-momentum-trading-system-for-retail-traders-deep-research/)
- [Market Regime Indicators — QuantifiedStrategies](https://www.quantifiedstrategies.com/market-regime-indicators/)
- [Market Regime Trading Strategies — Pollinate Trading](https://www.pollinatetrading.com/blog/market-regime-trading-strategies)
- [Detecting VIX Term Structure Regimes — Cristian Velasquez](https://medium.com/@crisvelasquez/detecting-vix-term-structure-regimes-8f3b1a4ddf15)

### Internal
- `/Users/belwinjulian/Desktop/SwingTrading/CLAUDE.md` (sections 2, 3, 6, 7, 9, 13)
- `/Users/belwinjulian/Desktop/SwingTrading/.planning/PROJECT.md`

---

*Feature research for: long-only momentum swing-trading screener, personal-trading-first*
*Researched: 2026-04-27*
