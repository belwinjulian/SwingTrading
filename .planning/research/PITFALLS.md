# Pitfalls Research

**Domain:** Long-only momentum swing-trading screener (free-data, rules-based, EOD pipeline)
**Researched:** 2026-04-27
**Confidence:** HIGH (almost all pitfalls are documented in CLAUDE.md §5/§6/§13 and corroborated by the broader quant-retail community; the specific failure modes are not speculative — they are the canonical reasons retail momentum systems fail)

> **Headline:** the four pitfalls that single-handedly kill credibility of free-data momentum screeners are **(1) survivorship bias**, **(2) look-ahead in signals/fundamentals**, **(3) in-sample weight optimization**, and **(4) journal pollution**. Everything else is corollary. Treat these as inviolable invariants enforced by tests, not as guidelines.

---

## Critical Pitfalls

### Pitfall 1: Survivorship bias in the universe (the headline data-quality issue)

**What goes wrong:**
yfinance, Finnhub, and most free APIs return only the **current** index constituents. ENRN, BBBY, LEHM, GTAT — every delisted, bankrupt, or merged name is silently absent. A backtest of "Russell 1000 stocks 2018→2024" using today's ticker list is actually a backtest of "Russell 1000 stocks that survived to 2024." Backtest CAGR is inflated by an estimated **1–3%** annualized; Sharpe by **0.2–0.5**. The strategy looks profitable; on a real point-in-time universe it would not be.

**Why it happens:**
Free APIs don't expose historical constituency. Naïve `tickers = pd.read_html(wiki_R1000_url)` returns today's list. The error is invisible — code runs fine, numbers come out, the bias is in *what's missing*.

**How to avoid:**
1. **Snapshot the universe weekly** from Day 1 (Phase 1): write `data/universe/russell1000_YYYY-MM-DD.parquet` to disk and commit. Over time you accumulate a real point-in-time dataset. This does **not** fix historical backtests; it fixes future ones.
2. **For historical backtests, accept and disclose** the bias openly in the README and any backtest output. State the period, universe construction method, and expected Sharpe inflation (~0.2–0.5).
3. **Stable benchmark universe**: when running long-history backtests, use today's S&P 500 as the universe but **explicitly label** the result "survivorship-biased benchmark" and report the equivalent uncorrected number.
4. **Optionally** include a small list of known-delisted high-profile names (ENRN, LEHM, BBBY, WCOM, GTAT) re-ingested from manual sources as a "Class A: corrupted-but-real" universe to spot-check the bias direction.

**Warning signs (testable invariants):**
- `assert universe_snapshot_count >= 950 and universe_snapshot_count <= 1010` for Russell 1000 — sudden drops or spikes indicate Wikipedia table parsing broke.
- **Backtest Sharpe > 2.0 on a multi-year free-data backtest**: nearly always survivorship + look-ahead + over-fit. Treat as a red flag, not a result.
- Test: `assert (universe_today - universe_30d_ago).symmetric_difference_size > 0` once per quarter — if no churn ever appears, the snapshot pipeline is broken.
- **README check**: every backtest result must be accompanied by a "Universe construction" disclosure block. CI lint can grep for it.

**Phase to address:**
- **Phase 1 (Data foundation)**: weekly universe snapshot job in GitHub Actions cron from day one.
- **Phase 4 (Backtest harness)**: disclosure scaffolding wired into every `vbt.Portfolio.stats()` output.

---

### Pitfall 2: Look-ahead bias in signals and indicators

**What goes wrong:**
A signal computed at bar `t` accidentally uses information that is only available *after* bar `t`'s close. The most common failure modes:

1. Computing a rolling indicator and entering on the same bar (`signal[t] → entry[t] @ close[t]`) — you knew the close to compute the signal; in real life you would have to enter at `t+1` open.
2. Earnings dates: yfinance returns the **period-end date**; the actual announcement is days later. A backtest that "knows" earnings on the period-end inflates the signal.
3. Fundamentals (EPS growth, etc.): the 10-Q deadline is **45 days** after fiscal-quarter end. Treating quarterly fundamentals as "known" on the period-end date leaks ~45 days of information.
4. RS percentile rank computed using **today's** universe membership — a stock that was delisted before today won't appear, so the percentile is computed against a forward-looking subset.
5. Splits: comparing a `t`-bar close to a pre-split pivot price reads as a breakout when no breakout occurred.

**Why it happens:**
pandas vectorization makes "all data is available everywhere" the default mental model. Forgetting `.shift(1)` is a one-character bug with no runtime error.

**How to avoid:**
1. **Convention enforced everywhere**: "signal at `t` triggers entry at `t+1` open." Wire this into `signals/composite.py` and the vectorbt portfolio call:
   ```python
   pf = vbt.Portfolio.from_signals(
       close=open_prices.shift(-1),  # exit on next-bar open
       entries=entries,              # entries are bar-t signals
       ...
   )
   ```
   Better: encapsulate in a single helper `build_portfolio_from_eod_signals()` that nobody bypasses.
2. **Earnings dates**: use Finnhub `/calendar/earnings` `time` flag (BMO/AMC), not yfinance period-end. Add the announcement date as a typed column; `assert announcement_date >= period_end` at ingestion.
3. **Fundamentals lag**: every fundamental feature gets a `.shift(periods=45_days)` applied at the feature layer — never trust the raw period-end date. Document and unit-test this.
4. **Universe-relative RS**: snapshot the universe **as of each historical date** (impossible retroactively for free data — see Pitfall 1) or compute RS percentile against a **fixed, large stable set** for backtest periods.
5. **Splits**: see Pitfall 4.

**Warning signs (testable invariants):**
- **THE canonical no-look-ahead test** (must exist in `tests/test_backtest_no_lookahead.py`):
  ```python
  def test_perfect_signal_with_correct_shift_is_unprofitable():
      # Signal == next-day return; if shifted correctly, the strategy
      # cannot use this future info, so PnL must be ~0 (or pure noise).
      close = synthetic_close()
      forward_ret = close.pct_change().shift(-1)
      # Signal = sign of NEXT-DAY return. Cheating signal.
      entries = forward_ret > 0
      # Backtest with our standard entry-at-next-bar-open helper.
      pf = build_portfolio_from_eod_signals(close, entries)
      # If our helper is correct, the cheating is neutralized:
      assert abs(pf.total_return()) < 0.05, "Look-ahead leak detected!"
  ```
  If this test passes (low PnL), the harness is honest. If it fails (huge PnL), there's a leak. Run on every PR touching `signals/` or `backtest/`.
- Property test: for any indicator `f`, `f(close.iloc[:t])[t-1] == f(close)[t-1]` (computing on a prefix gives the same value as computing on the full series — i.e., no future leak).
- **Realism sniff test**: Sharpe > 2.5 on a multi-year backtest is a leak/overfit signal until proven otherwise.

**Phase to address:**
- **Phase 2 (Indicators)**: indicator API requires `[:t]`-prefix-stable outputs; property test in `tests/test_indicators.py`.
- **Phase 4 (Backtest harness)**: `test_perfect_signal_with_correct_shift_is_unprofitable` ships with the harness as a **blocking** CI test.
- **Phase 5 (Fundamentals & catalysts)**: 45-day lag enforced at the fundamentals ingestion layer.

---

### Pitfall 3: Corporate-action / split-adjustment integrity for pivot detection

**What goes wrong:**
`yfinance.download(t, auto_adjust=True)` retroactively adjusts historical OHLCV for splits and dividends. This is correct for **indicator math** (SMAs, returns, RS) but **wrong for pattern/pivot detection**: a VCP pivot established at $500 pre-NVDA-2024-10:1 split now looks like a $50 pivot in adjusted data. If the screener compares an adjusted close to a re-derived adjusted pivot, this is fine. But if you cache pivots from one run with one adjustment basis and compare them in another run, or if you mix unadjusted volume with adjusted price (yfinance has been observed to return split-unadjusted volume sporadically), you get phantom breakouts.

**Why it happens:**
Most tutorials use `auto_adjust=True` and forget that pattern detection is pivot-level — not return-level — math. Volume is occasionally split-unadjusted in yfinance even when prices are adjusted (documented inconsistency).

**How to avoid:**
1. **Standardize on `auto_adjust=True`** for all indicator and pivot math. Re-derive pivots from adjusted closes every run; never cache raw-price pivot values.
2. **Store adjustment factors** alongside cached OHLCV (`splits.parquet` from `Ticker.splits`) so any cached run can be re-adjusted if the basis changes (e.g., new split occurs after the cache was written).
3. **Volume sanity check**: on every fetch, `assert (df['Volume'] > 0).all()` and spot-check known split events: `df.loc[split_date - 1d, 'Volume'] / df.loc[split_date + 1d, 'Volume']` should equal the split ratio if both are adjusted.
4. **At pivot-detection time**, compute the pivot from the **same series** you'll compare against (don't mix adjusted highs with cached unadjusted highs).

**Warning signs (testable invariants):**
- Spot-check assertion in `test_corporate_actions.py` for known splits: NVDA 2024-06-10 (10:1), AAPL 2020-08-31 (4:1), TSLA 2022-08-25 (3:1):
  ```python
  def test_nvda_split_2024_handled():
      df = cached_ohlcv("NVDA", start="2024-05-01", end="2024-08-01")
      pre = df.loc["2024-06-07", "Close"]
      post = df.loc["2024-06-11", "Close"]
      # Adjusted: prices should be near-continuous (ratio ~ 1, not 10).
      assert 0.9 < (pre / post) < 1.1
  ```
- Dashboard / report sanity: any breakout flagged within 5 trading days of a split event should be **manually reviewed** (or auto-flagged with a "near-split" warning).
- Detect mismatched volume: `if (df['Volume'].pct_change().abs() > 5).any() and split_within_window(df.index)` raise a warning.

**Phase to address:**
- **Phase 1 (Data layer)**: `cached_ohlcv()` always uses `auto_adjust=True` and persists `splits.parquet` per ticker. Spot-check tests included.
- **Phase 3 (Pattern detection)**: pivot detection re-derives from adjusted closes in the same call; never reads cached pivot dollar levels.

---

### Pitfall 4: EMA-vs-SMA confusion in the Trend Template

**What goes wrong:**
Minervini's Trend Template explicitly specifies **simple moving averages**. EMAs put more weight on recent prices, so they cross faster and produce a different (looser) "Stage 2" gate. A screener that uses `pandas_ta.ema` instead of `pandas_ta.sma` *quietly passes more stocks*, biasing the watchlist toward shorter-duration moves that don't fit the methodology. The bug is silent — the test passes, the watchlist looks fine, but the methodology fidelity is broken and the M2 ML model trained on these labels learns the wrong thing.

**Why it happens:**
`pandas_ta` API: `df.ta.sma(length=50)` vs `df.ta.ema(length=50)` — one character. Tutorials interchange them. Some screener forks on GitHub use EMA "because they cross sooner" without realizing they've changed the strategy.

**How to avoid:**
1. **Hardcode SMA in `signals/minervini.py`**; do not parameterize the MA type. Comment cites CLAUDE.md §13.1.
2. **Golden-file test** against known historical Stage-2 setups (NVDA 2023-05-15 should pass; SPY most days should fail — index doesn't qualify):
   ```python
   @pytest.mark.parametrize("ticker,date,expected", [
       ("NVDA", "2023-05-15", True),
       ("SPY",  "2023-05-15", False),
       ("META", "2022-11-01", False),  # mid-correction
   ])
   def test_trend_template_known_cases(ticker, date, expected):
       assert passes_trend_template(ticker, date) is expected
   ```
3. **CLAUDE.md** carries an `IMPORTANT: Use SMA not EMA in Trend Template` line in §13.1 already.

**Warning signs (testable invariants):**
- Pass-rate sanity: in a normal market, **5–15%** of the Russell 1000 should pass the Trend Template. > 30% means the gate is too loose (likely EMA leak or one condition silently bypassed). Add a daily metric `trend_template_pass_rate` to the run log; alert on > 25%.
- Code grep CI check: `rg "ema" src/screener/signals/minervini.py` must return zero matches.

**Phase to address:**
- **Phase 2 (Indicators + Minervini gate)**: SMA-only enforced; golden-file tests added.

---

### Pitfall 5: In-sample weight optimization of the composite score (overfit guarantee)

**What goes wrong:**
The composite score has six components (RS 25%, Trend 20%, Pattern 20%, Volume 10%, Earnings 15%, Catalyst 10%). Sweeping these weights with vectorbt against a single backtest period produces a "best" weight set that is **almost certainly overfit to that period's idiosyncrasies**. Reported Sharpe is a fiction; out-of-sample performance collapses.

**Why it happens:**
vectorbt makes parameter sweeps trivially fast. The dopamine of seeing the heatmap improve as you add components is hard to resist. The math: even with 6 weights × 5 levels each = 15,625 combinations; the multiple-testing inflation of the "best" Sharpe is enormous (Bailey & López de Prado's "deflated Sharpe" demonstrates this).

**How to avoid:**
1. **Walk-forward is non-negotiable**. Split history into rolling (3-yr in-sample, 1-yr out-of-sample) windows. Optimize on IS; report only **OOS** statistics.
2. **Report the OOS Sharpe distribution** across 5+ walk-forward windows, not the single best. Show min, median, max; the **min is the honest worst case**.
3. **Deflated Sharpe ratio**: compute and report alongside raw Sharpe. Formula uses N (number of trials), skew/kurt of returns. If deflated Sharpe < 0, the strategy hasn't beaten chance after multiple-testing correction.
4. **Hold weights constant for v1** — start with the weights from CLAUDE.md §2.7 and **do not tune them on backtest data**. Use the v1 paper-trade journal (Phase 6+) to inform M2 weights; that's its job.
5. **Block-bootstrap Monte Carlo** of realized trade sequence (block size = 10) to compute terminal-equity and max-DD distributions — the 5th-percentile max DD is the planning number, not the point estimate.

**Warning signs (testable invariants):**
- IS Sharpe / OOS Sharpe ratio. If IS > 2× OOS consistently → overfit. Add a CI assertion: `assert oos_sharpe >= 0.5 * is_sharpe` for any committed weight set.
- **Sharpe > 2 on the full period**: red flag, almost always overfit on free-data universe with survivorship.
- Number of parameters tested per published result: track in MLflow / runs.jsonl. If `n_trials > 100` and `deflated_sharpe < raw_sharpe * 0.6`, mark the result "untrusted."

**Phase to address:**
- **Phase 4 (Backtest harness)**: walk-forward + deflated Sharpe wired into the default `vbt_runner.py` output. The single-period backtest is *not* a supported reporting mode.
- **Phase 6 (Paper-trade journal)**: weights are frozen at v1 launch; tuning waits for M2 with real journal labels.

---

### Pitfall 6: Forgetting the market-regime ("M") gate

**What goes wrong:**
A long-only momentum book without a regime gate **gets crushed in 2008 (-50%), 2020-Q1 (-35% in weeks), 2022 (-25%)**. The Trend Template still produces "passing" stocks during a bear market — they're the least-broken names, not the breakout-ready leaders — and the screener happily ranks them. The user takes positions; the broad market drags everything down 1.5–2× SPY's drop.

**Why it happens:**
The regime gate feels like "extra complexity" that doesn't show up in pleasant backtests run from 2017–2021 (a relentless bull). Skipping the M filter is the most common shortcut in retail momentum systems and the one that most reliably produces ruin.

**How to avoid:**
1. **Composite regime score** as a hard gate, computed daily on `^GSPC` and `^IXIC`:
   - SPY > SMA(SPY, 200) AND SMA(SPY, 50) > SMA(SPY, 200) — trend filter.
   - % of universe above own 200-day SMA — breadth (bullish > 60%, bearish < 40%).
   - Distribution-day count (last 25 sessions, SPY down ≥ 0.2% on rising volume): 5+ = "Uptrend Under Pressure"; 6+ = "Correction".
   - VIX level: full size 12–20; cut 30% in 20–30; cut 50%+ above 30; pause new entries on intraday VIX +5.
2. **Regime → position sizing multiplier**, continuous in [0, 1]:
   - Confirmed Uptrend → 1.0
   - Uptrend Under Pressure → 0.5
   - Correction → 0.2 (tiny pilot trades) or 0.0 (pause)
3. **Test**: 2008-Q4, 2020-Q1, 2022-Q1, 2022-Q3 must all classify as `Correction` for at least 2 weeks each. Hard-coded golden-file tests.

**Warning signs (testable invariants):**
- `test_regime_2008_classified_correction()`, `test_regime_2020q1_classified_correction()`, `test_regime_2022_classified_correction()`. All must pass.
- Daily report should display the regime state prominently — if it ever displays "Confirmed Uptrend" while SPY is below SMA(200) for > 3 weeks, log a `regime_inconsistency` warning.

**Phase to address:**
- **Phase 2 (Trend + RS)**: regime module shipped at the same time as Trend Template. The Trend Template gate is meaningless without it.
- **Phase 3 (Composite scoring)**: regime score multiplies into final position size, not just composite score.

---

### Pitfall 7: yfinance rate-limit / 429 silent partial failures

**What goes wrong:**
yfinance is an unofficial scraper of Yahoo's web endpoints. There is no official rate limit; in practice you get throttled around 1,500–2,000 requests per session, and Yahoo occasionally returns **partial** OHLCV (last N bars missing) or empty DataFrames with no exception. A naïve loop over the Russell 1000 silently produces a universe where 200 tickers have stale data, the rank is wrong, and the screener misses real setups.

**Why it happens:**
`yf.download()` returns an empty DataFrame on most failure modes rather than raising. No retry by default. The library has had multiple breaking-then-patched cycles in 2024–2025.

**How to avoid:**
1. **Pin a known-good version** (`yfinance>=0.2.40`); never let dependabot auto-bump in prod.
2. **Wrap every fetch with `tenacity.retry`** (exponential backoff, 5 retries, jitter):
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential
   @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
   def fetch_ohlcv(ticker, start):
       df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
       if df.empty or df.index[-1] < pd.Timestamp.today() - pd.Timedelta(days=4):
           raise ValueError(f"stale or empty data for {ticker}")
       return df
   ```
3. **Sleep `random.uniform(0.5, 1.5)` between tickers**; never go faster than ~60 req/min sustained.
4. **Stooq fallback** for index data (`^GSPC`, `^IXIC`, `^VIX`) — it's a separate source that doesn't share Yahoo's failure modes.
5. **Post-fetch invariants** (the critical bit): every fetch is validated:
   - `assert len(df) >= expected_min_rows`
   - `assert df.index[-1].date() >= today - 4 business days` (covering long weekends)
   - `assert df['Volume'].sum() > 0`
6. **Universe-level health check** at end of nightly run: `assert successful_fetches >= 0.97 * universe_size` else fail the workflow loudly (don't commit the partial result).

**Warning signs (testable invariants):**
- `daily_run_quality_check.py` posts a single line to GitHub Actions summary: `✓ 998/1000 fetched, last_bar=2026-04-25`. Anything < 95% triggers an alert.
- Time-since-last-bar histogram across the universe: should be unimodal at "yesterday." A bimodal distribution with a tail at "weeks ago" is a partial-failure signature.

**Phase to address:**
- **Phase 1 (Data layer)**: tenacity retries, post-fetch invariants, universe health check — all shipped with the cache layer before any indicator code is written.

---

### Pitfall 8: Backtest realism (slippage, fees, infinite-capital, fills)

**What goes wrong:**
Backtests assume zero commissions (correct for Robinhood/IBKR Lite), tight fills, and unlimited capital. In reality:
- **Breakout entries on low-ADV names** suffer 30–100 bps slippage (you're buying *into* a breakout, where your order is the marginal demand pushing price higher).
- **Position size > 5% of bar volume** moves the market against you — yet a backtest fills the whole order at the bar close.
- **Stops gap through** in real life (overnight news); a backtest exits cleanly at the stop level.
- **Halts and circuit breakers** (during 2020-03 they were daily). Backtests fill anyway.
- A single huge winner (NVDA 2023) can mask 10 mediocre trades; the backtest summary number doesn't reveal this concentration without trade-level inspection.

**Why it happens:**
Default vectorbt parameters are zero-friction. Slippage is invisible until you live-trade.

**How to avoid:**
1. **Slippage tier by ADR/ADV**:
   - Liquid (ADV > $50M): 5 bps round-trip
   - Mid (ADV $5M–$50M): 15 bps
   - Thin (ADV $1.5M–$5M): 30 bps
   - Ultra-thin (< $1.5M): exclude entirely (also Qullamaggie's universe filter — `ADV > $1.5M` cuts these)
2. **Fees**: 0 commission, but **regulatory fees** (SEC + FINRA) ~ 0.5 bps on sells. Negligible but include for completeness.
3. **Position-size cap**: `max_position_$ = 0.05 * bar_dollar_volume_t`. If the math wants more, reject the trade or split across days.
4. **Per-position cap**: 25% of equity, hard cap.
5. **Stop-gap modeling**: 10% of stop-outs assumed to fill 1–3% below the stop level (gap-through penalty). Cheap proxy, but better than nothing.
6. **Trade-list inspection**: every backtest output includes top-10-by-PnL trades and bottom-10. Concentration > 50% of returns in top 3 trades = "fragile result" warning.

**Warning signs (testable invariants):**
- Backtest with zero slippage produces Sharpe X. Backtest with realistic slippage produces Sharpe Y. If `X / Y > 1.5`, the strategy is fragile to costs and probably won't survive live.
- "Realism delta" reported on every backtest: `(zero-cost Sharpe) - (realistic-cost Sharpe)`. Anything > 0.5 is a flag.

**Phase to address:**
- **Phase 4 (Backtest harness)**: slippage tier and position-size caps wired into the default vectorbt config; the "zero-friction" path is not exposed as a public API.

---

### Pitfall 9: Free-tier API quota exhaustion

**What goes wrong:**
- **Alpha Vantage free**: ~25 requests/day (recently tightened from 500/day). Universe scan is impossible — you'd cover 3% of Russell 1000 before quota.
- **Finnhub free**: 60 calls/min, 1-yr historical depth on most endpoints. A naïve catalyst-news loop over 1,000 tickers takes 17 minutes minimum and breaks halfway when you hit the burst limit.
- **NewsAPI free**: 100 requests/day **with a 24-hour delay** on articles. Useless for live catalysts; OK for sentiment training data only.
- **Reddit (PRAW)**: ~60 req/min per OAuth app. Pulling `.new(limit=500)` across 5 subs × multiple times daily is fine, but be careful with backfills.

**Why it happens:**
Vendor rate limits change without notice. Tutorials reference old, more generous limits.

**How to avoid:**
1. **Don't make Alpha Vantage primary**; it's a validation/spot-check tool only. Document this in CLAUDE.md.
2. **Aggressive caching** for Finnhub: `requests-cache` with 24h TTL on fundamentals (they change quarterly), 1h on news (they update intraday), never on indicators (compute locally).
3. **Token-bucket rate limiter** wrapping every external client (`aiolimiter` or hand-rolled). Stay below 80% of stated limit to leave headroom.
4. **Quota-aware scheduler**: nightly job orders calls (cheapest cache hits first, then fundamentals once-a-quarter, then news daily), so a quota exhaustion mid-run doesn't lose the most-valuable data.
5. **Quota dashboard**: `runs.jsonl` logs `n_calls_finnhub`, `n_calls_alpha`, etc. per run. Fail loud if you ever consume > 90% of a daily quota.

**Warning signs (testable invariants):**
- `assert n_finnhub_calls_per_minute < 50` at run end (10 req/min headroom).
- Surface 429s in run log: `n_429_responses > 0` should always trigger an alert in CI even if retry rescued the call.

**Phase to address:**
- **Phase 1 (Data layer)**: rate limiter + quota tracking before any external API client is used.
- **Phase 5 (Catalysts/fundamentals)**: cache-first, quota-aware scheduling for Finnhub.

---

### Pitfall 10: Universe leakage (today's R1000 used to backtest 2018)

**What goes wrong:**
A subtle, lethal variant of survivorship bias **and** look-ahead. If you backtest 2018 using the 2026 Russell 1000 list, every member of the universe **was selected for being in the index in 2026** — i.e., they survived AND grew enough to qualify for inclusion. Backtest CAGR includes the "next NVDA" effect for the entire 2018–2026 period because the universe already over-samples future winners.

**Why it happens:**
"I'll just use the current Russell 1000 ticker list" is the obvious shortcut. The bias is invisible without thinking through which selection happened when.

**How to avoid:**
1. **Phase 1 weekly snapshots** are the only durable fix going forward. Backtests that need pre-snapshot history are stuck disclosing the bias.
2. For pre-Phase-1 history, use a **stable, large universe** (current S&P 500) and explicitly label "biased benchmark."
3. **Never** use `iShares IWB.csv` (today's Russell 1000) as the universe for any backtest period earlier than the snapshot start date without a banner: "UNIVERSE LEAK — survivorship + selection bias."
4. **Document in PITFALLS section of README** the magnitude (~1–3% CAGR inflation, 0.2–0.5 Sharpe inflation per academic literature on selection-biased universes).

**Warning signs (testable invariants):**
- `assert backtest.universe_source.snapshot_date <= backtest.start_date` — any backtest whose universe was sourced *after* its start date triggers a lint failure unless explicitly tagged `biased_benchmark=True`.
- Visual: report includes "Universe construction: snapshotted YYYY-MM-DD; backtest start YYYY-MM-DD" — the gap visible to the reviewer.

**Phase to address:**
- **Phase 1**: weekly snapshot infrastructure.
- **Phase 4**: enforce snapshot-date-vs-backtest-start invariant in the harness.

---

### Pitfall 11: Paper-trade journal pollution (the M2 ML training set is at stake)

**What goes wrong:**
The paper-trade journal *is* the M2 training set. Three failure modes corrupt it irreversibly:

1. **Selection bias**: only logging trades the user "would have taken" — implicit hindsight filtering. The journal becomes a record of obvious winners.
2. **Backfill / retroactive editing**: marking a paper trade as "skipped" after seeing the next-day move ("I wouldn't have taken this one"). Same hindsight bias, more insidious because timestamps look honest.
3. **Outcome leakage**: the journal records *what happened* (entry, stop, exit, PnL) but not *what the system signaled at decision time*. Reproducing the decision later (for ML labels) is impossible without the snapshot of inputs.

The result: M2 model trains on filtered-good-decisions data and learns nothing generalizable. Live performance collapses.

**Why it happens:**
Discipline. It feels bad to log losing picks. Hindsight is a hell of a drug.

**How to avoid:**
1. **Journal every actionable pick** the system surfaces, period. The system writes the entry; the human only writes the *executed paper outcome* (filled / not filled, exit reason, exit price). The system's pick row is **append-only** and timestamped at the moment of publication.
2. **Snapshot inputs at decision time**: the journal row stores the full feature vector (RS, trend score, pattern type, volume z, regime, ADR%, all 60+ ML features the M2 model will use). This means M2 has the *exact* state the rules saw, not a reconstruction.
3. **No backfill, ever**: enforce an `INSERT-only, UPDATE on outcome columns only` SQLite schema. The "decision" columns are immutable. CI lint: `assert journal.decision_hash == sha256(decision_columns_at_insert_time)`.
4. **Honest "skipped" marker**: if the user chooses not to paper-execute a pick, that's recorded with a reason — but the pick itself is **still in the journal** as a published signal. The M2 model can learn from skipped picks too (they're labeled training data).
5. **Outcome labeled by deterministic forward-window**: `outcome_at_t+20 = price[t+20] / price[t+1_open] - 1` plus `max_drawdown_t+1_to_t+20`. No discretionary outcome flagging.

**Warning signs (testable invariants):**
- `assert journal.row_count_per_day >= 5` on average — if the system suddenly only logs 1 pick/day, the user is hidden-filtering.
- Decision-hash check on every row at audit time.
- Distribution of outcomes: if win-rate on logged picks is **suspiciously high** (> 70%), suspect the user is filtering out losers before logging.

**Phase to address:**
- **Phase 6 (Paper-trade journal)**: append-only schema, decision-hash invariant, full feature snapshot at insert.
- **Phase 3 (Composite scoring)**: composite score output already produces the feature snapshot needed for journal storage — design these together.

---

### Pitfall 12: WSB / social sentiment as a buy signal (contrarian at extremes)

**What goes wrong:**
Reddit/WSB mentions correlate with **the top of the move**, not the start. GME, AMC, BBBY, RIVN — by the time WSB sentiment z-score spikes above +2, the move is mostly over. Using WSB as a long-side signal in v2 would systematically buy tops.

**Why it happens:**
Sentiment seems intuitively bullish ("everyone's excited"). The data doesn't bear this out for retail-driven names.

**How to avoid:**
1. **Treat WSB sentiment as a flag/risk indicator, not a buy signal**. v1 doesn't include it; M2 includes it as a contrarian feature ("if buzz_z > 2, reduce position size") not a long signal.
2. **In the dashboard (M2)**: display buzz score with a contrarian-warning chip when extreme.
3. **Ticker collision filter**: regex `\$[A-Z]{1,5}` extracts mentions, but `$A`, `$IT`, `$IS`, `$ON` collide with English words. Filter against the actual ticker universe and **exclude common-word tickers** below a confidence threshold.

**Warning signs (testable invariants):**
- Backtest with WSB-sentiment-as-long-signal: should produce **negative** alpha vs the same strategy without it. If positive, suspect overfit on the GME-2021 outlier.
- Z-score of WSB mentions for known top-tickers (GME on 2021-01-27, AMC on 2021-06-02): should be > +3 — sanity-check the buzz-score scale.

**Phase to address:**
- **Phase 5 / M2 (Catalysts)**: when WSB sentiment is added, it ships as a contrarian feature with explicit documentation. v1 explicitly excludes it.

---

### Pitfall 13: Multiple-testing / deflated-Sharpe blindness

**What goes wrong:**
Beyond Pitfall 5 (in-sample weight tuning), even *honest* walk-forward testing of multiple strategy variants suffers multiple-testing inflation. If you try 50 reasonable strategy variants and pick the best, the "best Sharpe" is biased upward by ~`sqrt(2 * log(50)) ≈ 2.8` standard deviations vs. a single hypothesis.

**Why it happens:**
The bug is in the analyst, not the code. Trying many strategies is the right thing to do; reporting only the winner is the wrong thing to do.

**How to avoid:**
1. **Pre-register** the v1 strategy: composite weights, rules, gate — frozen at end of Phase 3. **The pre-registration document is committed to git** with a hash, so future dishonesty is detectable.
2. **Report all variants** that were tested in walk-forward, not just the winner. README backtest table shows the median variant, not the cherry.
3. **Deflated Sharpe ratio** (Bailey & López de Prado 2014): `DSR = sqrt((SR² - skew·SR + ((kurt-1)/4)·SR²) · (n-1))` adjusted for the number of trials. Compute and report.
4. **Bonferroni-corrected p-value** for the headline strategy result.

**Warning signs (testable invariants):**
- `n_strategy_variants_tested` logged per backtest run; deflated Sharpe < 0 → "untrusted result" tag in the report.
- Pre-registration hash mismatch in CI: any change to the pre-registered strategy after Phase 3 lock requires explicit re-registration with rationale.

**Phase to address:**
- **Phase 3 (Composite scoring)**: pre-register weights at phase end.
- **Phase 4 (Backtest harness)**: deflated-Sharpe in default reporting.

---

### Pitfall 14: Streamlit Cloud deploy gotchas (M2 architectural debt v1 can pre-empt)

**What goes wrong:**
v1 has no UI — but architectural choices in v1 silently disqualify M2's Streamlit deployment. The killers:

1. **TA-Lib C dependency**: needs `apt-get install ta-lib` which Streamlit Cloud free runner doesn't have. App fails to build.
2. **Model file size**: > 100 MB in repo triggers Git LFS requirements; > 1 GB exceeds Streamlit Cloud's container memory.
3. **Heavy CUDA / torch wheels**: container build times out at 10 min on free tier.
4. **Secrets handling**: secrets.toml committed accidentally; Streamlit Cloud requires app-side `st.secrets` reads, not env-var.
5. **Background scheduled jobs**: Streamlit Cloud deprecated these in 2024; if v1 puts the cron in-app rather than GitHub Actions, M2 is stuck.

**Why it happens:**
v1's "make it run locally" mindset doesn't anticipate a Streamlit deploy that depends on the same dependency tree.

**How to avoid (in v1, not later):**
1. **Use `pandas-ta` (pure Python)** as the indicator library. TA-Lib is **forbidden** in `pyproject.toml`. Document in CLAUDE.md.
2. **Cron lives in GitHub Actions** from day one — never in-app.
3. **Secrets via `st.secrets` + `.streamlit/secrets.toml.example`** committed; real `secrets.toml` in `.gitignore`. Same pattern works for v1's GitHub Actions secrets.
4. **Model artifact** (when M2 ships): host on Hugging Face Hub or compress < 50 MB; do not commit > 25 MB binaries.
5. **`requirements.txt` install must fit in 5 minutes** on a free runner. Test in CI by running a `pip install -r requirements.txt` in a clean container as a job.

**Warning signs (testable invariants):**
- CI job: `docker build -f Dockerfile.streamlit-cloud-sim .` — replicates the cloud constraints (no apt, 1 GB memory). Must pass on every PR.
- `find . -size +25M -not -path './.git/*'` returns empty in CI.

**Phase to address:**
- **Phase 1 (Foundation)**: pyproject locks pandas-ta, forbids ta-lib, secrets pattern established.
- **Phase 7 / M2 (Dashboard)**: deployment validates the v1 contracts held.

---

### Pitfall 15: "Looks good but isn't" — Sharpe > 2 on free-tier data

**What goes wrong:**
A backtest on free-tier data with Sharpe > 2.0 over multi-year periods is **almost always** one of:
- Survivorship-biased universe
- Look-ahead leak
- In-sample overfit
- Dependent on 1–2 huge winners (NVDA-shaped trades)
- Unrealistically low slippage assumption

Reporting Sharpe > 2 to a hiring reviewer who has been around quant signals "I don't know what I don't know." A walk-forward Sharpe of 0.7–1.2 with disclosed assumptions is **more credible**.

**Why it happens:**
Confirmation bias. The number feels validating. The user wants to be done.

**How to avoid:**
1. **Skepticism budget**: any backtest result with Sharpe > 1.5 triggers a forensic checklist before publication:
   - Universe construction date vs backtest start date (universe leak?)
   - No-look-ahead test passing? (signal leak?)
   - Walk-forward OOS Sharpe ≥ 0.5 × full-period Sharpe? (overfit?)
   - Top-3 trades concentration < 40% of total PnL? (single-name dependency?)
   - Slippage tier applied? (cost reality?)
   - Deflated Sharpe > 0? (multiple-testing?)
2. **README target**: aim to report **walk-forward OOS Sharpe 0.7–1.2** with full disclosure. Anything higher gets a banner "RESULT REQUIRES VERIFICATION" until the user has actually paper-traded it.

**Warning signs:**
- Sharpe > 2 + universe < 1,000 names + period > 3 years → red.
- Sharpe > 2 + survivorship not corrected → red.

**Phase to address:**
- **Phase 4 (Backtest harness)**: forensic checklist as a CLI subcommand `make backtest-audit`.
- **README/Docs**: cultural commitment to honest reporting.

---

### Pitfall 16: Cup-and-handle false positives (correctly deferred to v2)

**What goes wrong:**
Cup-and-handle pattern fits a U-shape via quadratic + handle pullback. The fit is sensitive to: window length, smoothing, depth threshold, handle definition. A naïve detector flags **20–40%** of mid-cap names as "in a cup" — most aren't. Live picks dilute the watchlist with noise.

**Why it happens:**
The pattern is geometrically vague compared to VCP (which has clean depth/contraction/volume tests) or continuation flag (clean range/MA tests). Tutorials make it look easy; production is hard.

**How to avoid:**
1. **Defer to v2** — already done in PROJECT.md. VCP and continuation flag carry v1.
2. When v2 builds it: **calibrate against a labeled test set** (Minervini's published examples, IBD-marked bases) before shipping.
3. **False-positive rate ≤ 5%** as a release gate; if a fresh implementation flags > 10% of names, it doesn't ship.

**Warning signs:**
- If v2 implementation flags > 15% of universe as "cup" → broken.

**Phase to address:**
- **v2 / M3** — explicitly out of scope for v1.

---

### Pitfall 17: Headline-level news sentiment as a primary signal (correctly deferred)

**What goes wrong:**
FinBERT (and similar) on news headlines has weak predictive power for forward returns at headline level. Academic studies (and Prosus' own benchmarks) show low correlation with 5-day forward returns. Using sentiment as a primary score component in v1 dilutes the rules-based composite with noise.

**Why it happens:**
Sentiment is intuitively appealing and demos well. The signal is weaker than it looks.

**How to avoid:**
1. **v1 excludes sentiment** — already in PROJECT.md "Out of Scope."
2. **M2 onward**: sentiment is a tertiary feature, not a driver. ML model can learn whether/when it helps. Ship as one of 60+ ML features, not as a hand-weighted composite component.
3. **If used**: aggregate by ticker over a 7-day window with recency-weighted exponential decay (half-life ~3 days) — single-headline FinBERT is too noisy.

**Warning signs:**
- Backtest with sentiment-as-feature shows < 0.05 Sharpe contribution → confirms low signal.

**Phase to address:**
- **M2** — sentiment ships as one ML feature among many; v1 leaves it out.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use yfinance without retry/cache | Fast iteration | Silent partial data on every run; backtests poisoned | **Never** — Phase 1 must ship retries |
| Use `iShares IWB.csv` (today's R1000) for all backtests | One-line universe | Universe leakage + survivorship inflate Sharpe 0.3–0.5 | Only with explicit `biased_benchmark=True` tag |
| Tune composite weights on the same period as the backtest | Pretty Sharpe | Overfit guaranteed; OOS collapse | **Never** — walk-forward is non-negotiable |
| Cache OHLCV without checking last-bar freshness | Fewer API calls | Stale rankings shipped on Mondays after long weekends | If staleness check runs separately |
| Use `auto_adjust=True` everywhere without storing splits | Simpler | Pivot mis-detection on split events | Acceptable if split spot-check tests pass |
| Skip the no-look-ahead test in CI | Faster CI | A subtle leak ships and corrupts every result downstream | **Never** |
| Hardcode regime gate thresholds without backtest validation | Quick to ship | Wrong thresholds → false bull/bear classifications | Acceptable for v1; revisit each milestone with regime-classification accuracy on 2008/2020/2022 |
| Skip slippage modeling because "I'm not trading low-ADV" | Cleaner numbers | First time you deviate, the strategy underperforms | Only with explicit `slippage=0` warning banner on output |
| Log only "interesting" picks to the journal | Less clutter | M2 ML training set is biased; live model fails | **Never** — append-only invariant |
| Use TA-Lib for one indicator pandas-ta lacks | 2× faster on that indicator | Streamlit Cloud deploy fails in M2 | **Never** in v1 |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **yfinance** | Assuming `yf.download` raises on failure | Always validate `len(df) >= expected_min_rows` and `df.index[-1] >= today - 4bd`; wrap in `tenacity.retry`; pin version |
| **yfinance** | Using `Ticker.calendar` for earnings date | yfinance returns period-end; use Finnhub `/calendar/earnings` `time` flag (BMO/AMC) |
| **yfinance** | Mixing adjusted prices with cached pivots | Re-derive pivots from adjusted closes every run; don't cache dollar levels |
| **Finnhub** | Hammering 60 req/min with no rate limiter | Token-bucket limiter at 50 req/min; 24h cache on fundamentals, 1h on news |
| **Finnhub free tier** | Assuming historical depth is sufficient | Free tier is **1 yr** historical on most endpoints; not a backtest data source |
| **Alpha Vantage** | Using as primary OHLCV source | 25 req/day free tier — unusable for universe scans; relegate to spot-check tool |
| **NewsAPI** | Treating articles as live | 24-hour delay on free tier; OK for sentiment training, not catalyst trading |
| **EDGAR / `edgartools`** | Forgetting `set_identity()` | SEC requires `User-Agent: Name <email>`; rate limit 10 req/sec |
| **Reddit / PRAW** | Regex `\$[A-Z]{1,5}` without ticker filter | `$A`, `$IT`, `$IS`, `$ON` collide with English words; filter against your ticker universe |
| **FRED** | No retry on rate-limit | Generous quota but still wrap in retry; cache series locally — they're slow-changing |
| **Stooq** | Treating as same-day source | Stooq EOD often lags by one day; fine for index history, not for today's regime |
| **GitHub Actions** | Cron at 16:30 ET | Markets close 16:00 ET; some EOD data takes 30–60 min to settle. Schedule **22:30 UTC** (18:30 ET) minimum |
| **GitHub Actions** | Committing changes back via PAT in workflow | Use `stefanzweifel/git-auto-commit-action@v5` with `GITHUB_TOKEN` (built-in, scoped to repo) |
| **Streamlit Cloud** (M2) | Reading env vars instead of `st.secrets` | `st.secrets["FINNHUB_API_KEY"]`; commit `secrets.toml.example` |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-ticker `yf.download` loop | 30+ minutes for R1000 scan; rate-limit failures | Batch via `yf.download(list_of_tickers, ...)` where possible; or async with semaphore = 5 | At ~500 tickers, the loop length × rate-limit headroom collide |
| Re-computing all indicators every run | Slow nightly jobs | Cache OHLCV; compute indicators incrementally; only the last bar of each indicator changes day-over-day | When universe > 1,500 names or backtest range > 5 years |
| Reading Parquet partition-by-partition with pandas | Slow scan-time aggregation | Use `duckdb` to query Parquet files directly; 10–50× faster | Once you have > 10 GB of OHLCV history |
| Holding all OHLCV in memory | Memory blow-up | Stream-process per-ticker; don't load entire universe into one DataFrame for indicator math | At ~3,000 tickers × 10 years on a free runner (16 GB RAM) |
| Single-threaded vectorbt parameter sweep | 20-minute walk-forward | Use `vbt.Portfolio.from_signals(... grouped_by='param')` with vectorized parameter dim | At > 100 parameter combinations |
| Recomputing universe-relative RS for every ticker independently | O(N²) | Compute once per date as a single rank operation across all tickers | Already at R1000 |
| Markdown report assembled with string concat | Slow + ugly diffs | Use `jinja2` templates; commit the rendered output | At any size — diffs matter for git history |
| Pulling news headlines daily for full universe | Quota exhaustion | Pull only for the top-50-ranked tickers + tickers in the journal | Already at R1000 with Finnhub free 60/min |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `.env` or `secrets.toml` | API keys leaked; quota theft; account suspension | `.gitignore` template + pre-commit hook (`gitleaks` or `trufflehog`); GitHub secret scanning enabled |
| API keys in GitHub Actions logs | Credentials in CI logs visible to forks | Use `${{ secrets.X }}`, never echo; enable "secret masking" verification in workflow |
| Reddit OAuth user_agent revealing identity / repo | Reddit may rate-limit known crawlers; doxxing vector | Generic user_agent like `momentum-screener/0.1` without personal name |
| EDGAR `set_identity()` with personal email in public repo | Email harvested for spam | Use a dedicated alias; or pull from secret at runtime |
| Storing paper-trade journal with brokerage account info | If real-money phase begins, account # in plaintext | Never store account numbers; the journal stores only ticker, prices, sizes |
| Streamlit Cloud (M2) public app exposes journal | Personal positions visible to internet | Either keep the app private OR redact size/PnL columns in the public view |
| Exposing internal RS percentile snapshots publicly | Trivial to clone the strategy | If portfolio-public, redact composite weights and feature snapshots; ship a read-only watchlist view |

---

## UX Pitfalls

Common user experience mistakes in this domain (relevant for the daily markdown report in v1, dashboard in M2).

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Daily report dumps 50+ tickers | Decision fatigue; user picks favorites by gut | Cap at top 10–15 with explicit cutoff rule (composite ≥ 70 OR top decile, whichever is fewer) |
| Single composite score, no playbook | User doesn't know whether to enter on breakout-stop or chase ORH | **Per-pick playbook tagging** (Qullamaggie / Minervini VCP / leader-hold) with style-specific entry/stop — already in PROJECT.md scope |
| Showing a buy signal during a Correction regime without warning | User loses money in a clear bear market | Banner at top of report: regime state in big colored text; if Correction, suggested position-size multiplier shown explicitly |
| Burying "last data refresh" timestamp | User trades on stale data Monday morning after a Sunday-failed cron | Top-of-report banner with last-refresh timestamp + universe size + scan time |
| No reason given for each pick | User can't audit; black-box feel even though rules are explicit | Each pick row shows top-3 contributing components ("RS: 92, VCP-tightness: 87, regime: 0.9") |
| Position-size guidance without account context | Number is meaningless ($X risk on what equity?) | Surface the assumed account equity at top of report; compute size as a % too |
| "PASS" / "FAIL" boolean for Trend Template | Loses partial-match information | Show `7/8` with the failing condition explicitly listed |
| Reporting 4-decimal-place Sharpe ratios | False precision | Round to 1 decimal; report distribution (min/median/max) over walk-forward windows |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **OHLCV cache layer**: often missing post-fetch validation — verify `assert df.index[-1] >= today - 4bd` and `assert len(df) >= expected_min_rows` on every fetch.
- [ ] **Trend Template gate**: often uses EMA by mistake — verify with `rg "ema" src/screener/signals/minervini.py` returning empty.
- [ ] **RS percentile rating**: often computed without snapshotting the universe — verify `rs_rating[t]` is reproducible from a stored snapshot, not recomputed against today's universe.
- [ ] **VCP detection**: often missing volume-contraction check — verify the `volume_per_leg_decreasing` invariant in unit tests.
- [ ] **Regime gate**: often implemented but not wired into position sizing — verify `position_size = base_size * regime_score` actually used downstream.
- [ ] **Backtest harness**: often missing walk-forward — verify `vbt_runner.py` reports OOS-Sharpe distribution, not single-period Sharpe.
- [ ] **No-look-ahead test**: often missing — verify `tests/test_backtest_no_lookahead.py` exists, runs on every PR, and *fails* when `.shift(1)` is removed (mutation test).
- [ ] **Universe snapshot**: often skipped "for now" — verify `data/universe/` has at least 4 weekly snapshots before claiming v1 done.
- [ ] **Paper-trade journal**: often missing decision-time feature snapshot — verify journal row includes the full composite-score component vector at insert time.
- [ ] **Daily report**: often missing regime state banner — verify the report header has regime state + size multiplier.
- [ ] **Survivorship disclosure**: often forgotten in README — verify backtest section has a "Data limitations" subsection naming survivorship explicitly.
- [ ] **Slippage assumption**: often defaults to 0 — verify `vbt.Portfolio.from_signals` is called with explicit `slippage` and `fees` and the value is shown in the report.
- [ ] **Pre-registration of weights**: often skipped — verify `docs/strategy_v1_preregistration.md` exists with composite weights, frozen-on date, and a git hash referenced.
- [ ] **Run health metrics**: often missing — verify `runs.jsonl` records `n_fetched / n_universe`, `n_429s`, `n_finnhub_calls`, and CI fails on coverage < 95%.
- [ ] **`make` targets**: often `make data` / `make rank` / `make backtest` / `make app` exist; verify they actually run from a clean clone in CI.
- [ ] **Split spot-check tests**: often missing — verify NVDA-2024, AAPL-2020, TSLA-2022 split tests pass.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Look-ahead leak shipped to a backtest | HIGH | (1) Add the breaking unit test first; (2) bisect the leak via git; (3) re-run all walk-forward; (4) prepend a "v1.0.x results invalid" banner to README; (5) retract any public claims |
| Survivorship-biased backtest published | MEDIUM | Disclose in a top-of-README banner; add bias-magnitude estimate; do not retract numbers — annotate them |
| yfinance silent partial fetch poisoned a daily run | LOW | Ranking job exits non-zero on universe-coverage < 95%; nightly artifact not committed; re-run manually next morning |
| Composite weights overfit (OOS Sharpe < 0.5 × IS) | MEDIUM | Roll back to pre-registration weights; do not tune further until M2's paper-trade ground truth exists |
| Quota exhausted mid-run | LOW | Cache existing fetches; resume tomorrow; the quota-aware scheduler should already have prioritized the most-valuable calls first |
| Streamlit Cloud (M2) build fails on TA-Lib | MEDIUM | Replace TA-Lib calls with pandas-ta equivalents; if performance regresses, profile and accept the loss |
| Paper-trade journal corruption (manual edits, gaps) | HIGH | Forensically reconstruct from git history of the SQLite/CSV; flag corrupted period as "training-set excluded" for M2; restart clean from a new milestone marker |
| Regime gate misclassified a real correction (false bull) | MEDIUM | Add the failing date to the regime golden-file tests; tighten the breadth/distribution-day thresholds; re-run regime backtest on 2008/2020/2022 |
| Universe leakage in a published result | LOW–MEDIUM | Re-tag the result with `biased_benchmark=True`; re-run with stable-universe-of-the-day method; show the gap to the audience |
| Mid-strategy cherry-pick (analyst tested 50 variants, reported 1) | HIGH | Compute deflated Sharpe; if < 0, retract the result; commit the full set of variants tried |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls. This mapping is the **primary input to the roadmapper** — every phase below should ship the prevention named here.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Survivorship bias (#1) | **Phase 1** (Data foundation) — weekly snapshot job | `data/universe/` has ≥ 1 snapshot/week; CI asserts presence |
| Look-ahead bias (#2) | **Phase 2** (Indicators) + **Phase 4** (Backtest harness) | `test_backtest_no_lookahead.py` blocking in CI; mutation test (remove the `.shift(1)`, expect failure) |
| Corporate actions (#3) | **Phase 1** (Data layer) + **Phase 3** (Pattern detection) | NVDA-2024, AAPL-2020, TSLA-2022 split tests pass |
| EMA-vs-SMA confusion (#4) | **Phase 2** (Trend Template) | Code-grep CI: `rg "ema" src/screener/signals/minervini.py` returns empty; pass-rate sanity (5–15%) |
| In-sample weight overfit (#5) | **Phase 3** (Composite scoring) — pre-registration + **Phase 4** walk-forward harness | Pre-registration doc committed; OOS Sharpe ≥ 0.5 × IS asserted in CI |
| Forgotten regime gate (#6) | **Phase 2** (regime ships with Trend Template) | 2008/2020/2022 classified-as-Correction tests pass; `position_size *= regime_score` in tests |
| yfinance rate limits (#7) | **Phase 1** (Data layer) | Tenacity retries; post-fetch invariants; universe-coverage health check ≥ 95% |
| Backtest realism (#8) | **Phase 4** (Backtest harness) | Slippage tier applied by default; trade-list concentration check in default report |
| Free-tier quota (#9) | **Phase 1** (Data layer) + **Phase 5** (Catalysts/fundamentals) | Token-bucket limiter; quota dashboard in `runs.jsonl` |
| Universe leakage (#10) | **Phase 1** (snapshots) + **Phase 4** (harness) | `assert universe.snapshot_date <= backtest.start_date` invariant in harness |
| Journal pollution (#11) | **Phase 6** (Paper-trade journal) | Append-only schema; decision-hash invariant; full feature snapshot at insert |
| WSB sentiment as buy signal (#12) | **Out of scope v1**; **M2** treats as contrarian feature | Backtest test: WSB-as-long-signal produces negative alpha — confirm before any inclusion |
| Multiple-testing blindness (#13) | **Phase 3** (pre-registration) + **Phase 4** (deflated-Sharpe in default report) | Pre-registration hash check in CI; deflated-Sharpe column in every backtest output |
| Streamlit deploy debt (#14) | **Phase 1** (no TA-Lib in pyproject; cron in GH Actions) | Docker build sim of Streamlit Cloud constraints in CI; size check < 25 MB binaries |
| Sharpe > 2 self-skepticism (#15) | **Phase 4** (forensic-checklist subcommand) + **README** | `make backtest-audit` runs all 6 forensic checks; banner appears for high-Sharpe results |
| Cup-and-handle false positives (#16) | **v2** — explicitly out of scope v1 | When v2 ships, false-positive rate ≤ 5% as release gate |
| Headline sentiment as primary (#17) | **Out of scope v1**; **M2** as one ML feature among many | M2: feature-importance / SHAP must show non-zero contribution before retention |

---

## Sources

- **CLAUDE.md** §5.3 (survivorship), §5.4 (look-ahead), §5.5 (corporate actions), §6.3 (backtest hygiene), §13.6 (canonical pitfalls list), §14 (recent updates) — primary authoritative source for this project.
- **PROJECT.md** — confirms v1 scope, free-only constraint, paper-trade journal as M2 ML training set, weekly universe snapshots, EOD-only workflow.
- **Bailey & López de Prado (2014)** "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality" — formal treatment of multiple-testing correction.
- **López de Prado, *Advances in Financial Machine Learning* (2018)** — purged k-fold, embargo, combinatorial cross-validation; canonical reference for time-series ML hygiene.
- **Portfolio123 2019 analysis of CANSLIM** — empirical evidence that strict CANSLIM screening underperforms; the C / L / M components individually carry most of the signal.
- **Skyte's `rs-log`** (open-source IBD-RS) — reference implementation of the quarter-weighted RS formula.
- **vectorbt documentation** — `from_signals` semantics, parameter sweep API, default fees/slippage parameters.
- **yfinance issue tracker (2024–2025)** — multiple breaking-then-patched cycles documented; volume-adjustment inconsistencies reported.
- **Anthropic CLAUDE.md guidance + abhishekray07/claude-md-templates + HumanLayer** — for the Streamlit-deploy-debt avoidance pattern.
- **Personal experience / known issues**: yfinance silent partial failures, Finnhub 60/min behavior, Alpha Vantage 25/day tightening (2024).

---
*Pitfalls research for: Long-only momentum swing-trading screener (free-data, rules-based, EOD pipeline)*
*Researched: 2026-04-27*
