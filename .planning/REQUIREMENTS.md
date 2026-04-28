# Requirements: Momentum Swing Screener

**Defined:** 2026-04-27
**Core Value:** Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.

## v1 Requirements

Each requirement is user-centric, atomic, and testable. Maps to exactly one roadmap phase.

### Foundation

- [ ] **FND-01**: Repo skeleton runs on `uv` with `pyproject.toml` pinning the v1 stack (pandas, pandas-ta-classic, yfinance, vectorbt, edgartools, finnhub-python, fredapi, pydantic-settings, pandera, structlog, typer)
- [ ] **FND-02**: `make data && make rank && make report && make backtest` runs end-to-end locally with no manual steps after setup
- [ ] **FND-03**: CI runs ruff, mypy (strict on `signals/` and `indicators/`), and pytest on every PR
- [ ] **FND-04**: `tests/test_backtest_no_lookahead.py` exists, is mutation-tested (removing `.shift(1)` causes failure), and is a CI-blocking gate on every PR touching `signals/` or `backtest/`
- [ ] **FND-05**: `docs/strategy_v1_preregistration.md` records the v1 composite-score weights with a git hash before any backtest result is reported

### Data

- [ ] **DAT-01**: User can refresh Russell 1000 universe with `make universe`; current and historical constituent lists are fetched from Wikipedia + iShares IWB CSV
- [ ] **DAT-02**: A weekly snapshot of the universe is written to `data/universe/YYYY-MM-DD.parquet` so future backtests have point-in-time membership
- [ ] **DAT-03**: User can refresh OHLCV with `make ohlcv`; data fetched via yfinance ≥1.3.0 with Stooq fallback, cached to per-ticker Parquet, and incrementally appended on subsequent runs
- [ ] **DAT-04**: User can refresh macro data (SPY, ^IXIC, ^VIX, A/D line, FRED yields) with `make macro`
- [ ] **DAT-05**: User can refresh fundamentals (Finnhub earnings calendar + EPS data) with `make fundamentals`; fundamentals are tagged with a 45-day post-quarter-end "knowable from" date and not used until that date passes
- [ ] **DAT-06**: All HTTP-based fetchers use `requests-cache` (24h fundamentals / 1h news) plus `tenacity` retries with exponential backoff; rate-limit failures (429) trigger backoff, not silent zero-row results
- [ ] **DAT-07**: Universe-coverage health check runs after every nightly fetch; if `successful_fetches < 95% of universe_size`, the run fails loudly and does not commit partial results
- [ ] **DAT-08**: Corporate-action splits are stored alongside OHLCV (`splits.parquet`) so pivot levels can be re-derived correctly across split events
- [ ] **DAT-09**: Pandera schemas are enforced at the `data/ → indicators/` and `composite → publishers/` boundaries (DataFrame shape, dtypes, non-null index)

### Indicators

- [ ] **IND-01**: `indicators.build_panel()` returns a multi-ticker DataFrame panel with SMA(10/20/50/150/200), ATR(14), ADR%(20), OBV, and dryup-ratio columns for every ticker in the universe
- [ ] **IND-02**: SMAs are simple moving averages, not exponential — enforced by a CI grep that fails if `ema` appears in `src/screener/signals/minervini.py` or `src/screener/indicators/trend.py`
- [ ] **IND-03**: IBD-style relative-strength is computed daily using `RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`, then percentile-ranked across the universe to produce an integer 1–99 RS rating
- [ ] **IND-04**: ADR%(20) uses the Qullamaggie formula `100 * (mean(high/low over 20 days) - 1)`
- [ ] **IND-05**: Indicators are pure functions — no I/O, no global state, panel-in / panel-out

### Patterns

- [ ] **PAT-01**: VCP detector identifies pivot points using `scipy.signal.argrelextrema` and emits a contraction sequence with depth + volume per leg
- [ ] **PAT-02**: VCP is recognized only if: prior leg ≥ 30% over ≤6 months, 2–6 contractions, each contraction smaller than the previous (depth_i ≤ 0.85 × depth_i-1), first-leg depth ≤ 35%, final-contraction depth ≤ 12%, volume contracts in step with price, breakout volume ≥ 1.5× SMA(volume, 50)
- [ ] **PAT-03**: Continuation-flag detector recognizes a 5–25 bar consolidation along a rising 10/20/50 SMA with higher lows, range tightness < 1×ATR(20) per bar, and volume contracting vs the prior leg
- [ ] **PAT-04**: Post-gap-continuation detector flags D+1 candidates that gapped ≥ 8% with strong volume on D-0 and held the gap (D-0 close in upper third of D-0 range)
- [ ] **PAT-05**: VCP/flag pivot prices are re-derived from adjusted closes on every run, never cached as fixed dollar levels (avoids split-adjustment drift)
- [ ] **PAT-06**: Golden-file tests exist for at least three known historical setups (e.g., NVDA 2023 base, AAPL 2020 base, NVDA 2024 split-adjusted) — they must classify correctly

### Signals

- [ ] **SIG-01**: Minervini Trend Template gate evaluates all 8 SMA-based conditions and emits both `passes_trend_template: bool` and `trend_template_score: int (0-8)` per ticker
- [ ] **SIG-02**: Qullamaggie Setup A scan filters to the top 1–2% performers over 1m/3m/6m AND avg dollar volume > $1.5M AND ADR%(20) ≥ 4
- [ ] **SIG-03**: CANSLIM C+L+M overlay (recent EPS acceleration ≥ 25% YoY, RS rating ≥ 80, market regime in confirmed uptrend) is applied as additive scoring, not as a hard gate
- [ ] **SIG-04**: Signals layer is pure functions — no I/O, no global state; consumes the indicator panel and returns DataFrames of identical index

### Regime

- [ ] **REG-01**: `regime.py` produces one row per date (universe-wide) with: SPY 200d trend pass, breadth (% of universe above 200d SMA), distribution-day count over last 25 sessions, VIX level
- [ ] **REG-02**: Regime emits both a discrete state (`Confirmed Uptrend` / `Uptrend Under Pressure` / `Correction`) and a continuous `regime_score ∈ [0, 1]`
- [ ] **REG-03**: `regime_score` is multiplied into base risk during position sizing — pausing or reducing new entries when the market is hostile
- [ ] **REG-04**: Golden-file tests verify regime classifies 2008-Q4, 2020-Q1, and 2022-H1 as Correction at the correct dates

### Composite Scoring & Playbook Tagging

- [ ] **CMP-01**: Composite confidence score (0–100) is a weighted sum of 6 components: RS percentile (25%), Trend Template (20%), Pattern (20%), Volume (10%), Earnings (15%), Catalyst (10%); weights are pre-registered in `docs/strategy_v1_preregistration.md`
- [ ] **CMP-02**: Each pick declares a playbook tag — one of `qullamaggie_continuation`, `minervini_vcp`, or `leader_hold`
- [ ] **CMP-03**: Tie-breaking rules: Qullamaggie wins if pattern < 25 bars and ADR% ≥ 5; Minervini VCP wins if pattern ≥ 25 bars or final contraction ≤ 8%; leader-hold is the fallback when no actionable pattern exists
- [ ] **CMP-04**: Composite scorer co-locates score + playbook tag in `signals/composite.py` so v2 ML probability adds a single weight key without refactoring downstream consumers
- [ ] **CMP-05**: Each pick exposes its component breakdown (e.g., `RS=92, Trend=8/8, Pattern_VCP_tightness=6.2%, Volume=1.2, Earnings=1, Catalyst=0.5`) so the score is auditable

### Sizing & Trade Plans

- [ ] **SIZ-01**: Position sizer computes `shares = (account_equity × risk_pct × regime_score) / (entry - stop)` per pick, capped at 25% of equity per single position
- [ ] **SIZ-02**: A pick is auto-rejected if `risk_per_share > 1 × ADR_dollars` (Qullamaggie risk-≤-1×ADR rule); rejection reason appears in the report
- [ ] **SIZ-03**: Per-playbook stop placement: Qullamaggie continuation → low of entry day; Minervini VCP → below final-contraction low; leader-hold → below recent swing low (1.5–2×ADR distance)
- [ ] **SIZ-04**: Per-playbook trail rules: Qullamaggie → trail 10/20/50d SMA based on speed; Minervini VCP → 21d EMA or 50d SMA; leader-hold → 50d SMA close
- [ ] **SIZ-05**: Each pick reports distance-from-pivot in ATRs and is annotated as `in-zone` (≤ 0.66×ATR above pivot) or `chase, skip` (> 1×ATR above pivot)

### Catalysts

- [ ] **CAT-01**: Each pick's report block flags `days_to_next_earnings` from Finnhub earnings calendar, with explicit `BMO/AMC` notation
- [ ] **CAT-02**: Each pick's report block flags `crossed_52w_high_within_60d: bool`
- [ ] **CAT-03**: EDGAR Form 4 insider cluster-buy detection: ≥ 2 insiders buying within a rolling 5-day window in the last 30 days surfaces as `insider_cluster_buy: true` in the report
- [ ] **CAT-04**: edgartools `set_identity()` is configured at startup (SEC requires it)

### Output

- [ ] **OUT-01**: User can generate the daily markdown report with `make report`; output written to `reports/YYYY-MM-DD.md`
- [ ] **OUT-02**: Report contains: regime banner (state + score), top-N picks (default N=15) ranked by composite score, per-pick block (ticker, playbook tag, score breakdown, entry/stop/size, ATR distance from pivot, catalyst flags), data-quality footer (universe size, scan time, fetch success rate, last yfinance refresh)
- [ ] **OUT-03**: A daily snapshot of the full ranked universe is written to `data/snapshots/YYYY-MM-DD.parquet` for later backtesting and decile analysis
- [ ] **OUT-04**: Every actionable pick (composite score above the configured threshold) is appended to the SQLite paper-trade journal at publish time — including picks the user does not execute (so the dataset has negative samples for v2 ML)
- [ ] **OUT-05**: Journal schema is append-only, immutable on decision columns, and stores a `features_json` blob with the full score-component snapshot at signal time
- [ ] **OUT-06**: Journal records both the decision-time state and the eventual outcome (entry filled? exit price? holding period? max favorable/adverse excursion?) once the trade closes

### Backtest

- [ ] **BCK-01**: vectorbt 1.0 walk-forward harness runs with 3-year IS / 1-year OOS rolling windows; outputs the OOS Sharpe distribution across windows, not a single number
- [ ] **BCK-02**: Backtest enforces signals execute at next-bar open (not current-bar close); the no-look-ahead test (FND-04) regresses against this
- [ ] **BCK-03**: Slippage is tiered by ADV (5 bps for ADV > $50M, 15 bps for $5M–$50M, 30 bps for < $5M); transaction-cost-zero is not a supported reporting mode
- [ ] **BCK-04**: Backtest report includes per-playbook attribution (CAGR / Sharpe / max DD / win rate / profit factor / expectancy split by `qullamaggie_continuation` / `minervini_vcp` / `leader_hold`)
- [ ] **BCK-05**: Backtest report includes per-regime breakdown (returns during Confirmed Uptrend vs Uptrend Under Pressure vs Correction)
- [ ] **BCK-06**: Backtest report disclosure header explicitly states the universe source date, survivorship-bias caveat, slippage assumptions, and period selection
- [ ] **BCK-07**: `make backtest-audit` runs a forensic checklist (no-look-ahead, weight-pre-registration hash match, universe snapshot ≤ start date) before any backtest result is considered reportable

### Operations

- [ ] **OPS-01**: GitHub Actions workflow `.github/workflows/refresh.yml` runs nightly at `30 22 * * 1-5` (UTC) and executes the full pipeline (universe → ohlcv → macro → fundamentals → score → report → journal)
- [ ] **OPS-02**: Workflow commits the day's report, journal updates, and run log via `stefanzweifel/git-auto-commit-action@v5`
- [ ] **OPS-03**: A separate heartbeat workflow runs weekly to prevent GitHub from disabling the nightly cron after 60 days of inactivity
- [ ] **OPS-04**: Workflow supports `workflow_dispatch` for manual re-runs
- [ ] **OPS-05**: Each run appends a structured JSON record (start time, duration, fetch success rate, regime state, picks count) to `runs.jsonl` for observability

## v2 Requirements

Acknowledged, deferred. Not in current roadmap; revisited at the M2 milestone or after first 30 paper trades.

### v1.x — after first 30 paper trades

- **CAT-V1X-01**: Score-decile spread report (top vs bottom decile, weekly rebalance) demonstrates score monotonicity
- **CAT-V1X-02**: Industry RS rank as composite score booster (industry-level RS aggregated from member-stock RS)
- **CAT-V1X-03**: Mistake-tag taxonomy in journal (e.g., `chased`, `gap_too_far`, `stop_too_tight`)
- **CAT-V1X-04**: Per-playbook performance attribution time-series in the daily report

### M2 — ML & Dashboard

- **ML-01**: LightGBM probability score (P(forward 20d return > 10% AND max DD > -8%)) trained on the v1 paper-trade journal
- **ML-02**: SHAP per-prediction explanations published alongside each pick
- **ML-03**: ML score adds one weight key to the composite scorer; rules-based score remains authoritative
- **DASH-01**: Streamlit dashboard with watchlist, stock detail, regime, backtest lab, and journal pages
- **DASH-02**: Hosted on Streamlit Community Cloud (free tier)

### M3 — Catalyst NLP

- **NLP-01**: FinBERT-based news sentiment score per ticker (Finnhub `/company-news`)
- **NLP-02**: Reddit social buzz score (PRAW: r/wallstreetbets, r/stocks, r/swingtrading), treated as contrarian at extremes

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Pre-market and intraday scanning | Evening-review workflow only; EOD data sufficient for v1 |
| Opening-range entries (1/5/60-min) | Requires intraday feed; out of scope per `PROJECT.md` |
| Setup C (parabolic capitulation longs) | Intraday-dependent; lower priority than continuation/VCP |
| Cup-and-handle pattern | Hardest to detect cleanly; deferred to v2; VCP and continuation flag carry v1 |
| Real broker API (Alpaca, IBKR, Robinhood) | Paper-trade-first; real-money execution gated on validated paper performance |
| Paid data feeds (Polygon, Norgate, Alpha Vantage premium, IEX Cloud) | $0/month hard cap; survivorship bias accepted and disclosed |
| TA-Lib (C-extension indicator library) | C-deps break Streamlit Cloud deploy; pandas-ta-classic is a pure-Python equivalent |
| PySpark universe scan | Russell 1000 fits comfortably in pandas; portfolio-decoration eng work without picks-quality benefit |
| dbt + duckdb modeling layer | Same — adds friction without improving picks |
| Hosted public live demo | Personal-trading first; local execution + GitHub Actions cron is sufficient |
| Options activity / unusual options flow | No reliable free source; paid scrapers are ToS-fragile |
| Alternative data (satellite, web scraping) | $0 budget + signal-to-noise too low for v1 |
| Real-time alerting (push / SMS / Slack) | Evening review workflow doesn't require it |
| Mobile / native app | Markdown report is consumable on phone in any git client |

## Traceability

Empty initially — populated during roadmap creation by `gsd-roadmapper`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | TBD | Pending |
| FND-02 | TBD | Pending |
| FND-03 | TBD | Pending |
| FND-04 | TBD | Pending |
| FND-05 | TBD | Pending |
| DAT-01 | TBD | Pending |
| DAT-02 | TBD | Pending |
| DAT-03 | TBD | Pending |
| DAT-04 | TBD | Pending |
| DAT-05 | TBD | Pending |
| DAT-06 | TBD | Pending |
| DAT-07 | TBD | Pending |
| DAT-08 | TBD | Pending |
| DAT-09 | TBD | Pending |
| IND-01 | TBD | Pending |
| IND-02 | TBD | Pending |
| IND-03 | TBD | Pending |
| IND-04 | TBD | Pending |
| IND-05 | TBD | Pending |
| PAT-01 | TBD | Pending |
| PAT-02 | TBD | Pending |
| PAT-03 | TBD | Pending |
| PAT-04 | TBD | Pending |
| PAT-05 | TBD | Pending |
| PAT-06 | TBD | Pending |
| SIG-01 | TBD | Pending |
| SIG-02 | TBD | Pending |
| SIG-03 | TBD | Pending |
| SIG-04 | TBD | Pending |
| REG-01 | TBD | Pending |
| REG-02 | TBD | Pending |
| REG-03 | TBD | Pending |
| REG-04 | TBD | Pending |
| CMP-01 | TBD | Pending |
| CMP-02 | TBD | Pending |
| CMP-03 | TBD | Pending |
| CMP-04 | TBD | Pending |
| CMP-05 | TBD | Pending |
| SIZ-01 | TBD | Pending |
| SIZ-02 | TBD | Pending |
| SIZ-03 | TBD | Pending |
| SIZ-04 | TBD | Pending |
| SIZ-05 | TBD | Pending |
| CAT-01 | TBD | Pending |
| CAT-02 | TBD | Pending |
| CAT-03 | TBD | Pending |
| CAT-04 | TBD | Pending |
| OUT-01 | TBD | Pending |
| OUT-02 | TBD | Pending |
| OUT-03 | TBD | Pending |
| OUT-04 | TBD | Pending |
| OUT-05 | TBD | Pending |
| OUT-06 | TBD | Pending |
| BCK-01 | TBD | Pending |
| BCK-02 | TBD | Pending |
| BCK-03 | TBD | Pending |
| BCK-04 | TBD | Pending |
| BCK-05 | TBD | Pending |
| BCK-06 | TBD | Pending |
| BCK-07 | TBD | Pending |
| OPS-01 | TBD | Pending |
| OPS-02 | TBD | Pending |
| OPS-03 | TBD | Pending |
| OPS-04 | TBD | Pending |
| OPS-05 | TBD | Pending |

**Coverage:**
- v1 requirements: 64 total
- Mapped to phases: 0 (filled by roadmapper)
- Unmapped: 64 ⚠️ (will be 0 after roadmap creation)

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after initial definition*
