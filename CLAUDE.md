# Technical Reference: Long-Only Momentum Swing Trading Screener
## Definitive Specification for AI-Assisted Development (Source Document for `CLAUDE.md`)

**Prepared for:** Belwin (Data Engineer, Python / PySpark / SQL)
**Purpose:** A single, authoritative technical brief that consolidates trading methodology, data architecture, ML/DS layer, deployment, and AI-pairing conventions into one document. The downstream `CLAUDE.md` can be assembled from sections of this brief largely verbatim. Where speculation, controversy, or known-bad practice exists, it is flagged inline.

---

## 1. Project Mission, Scope, and Audience

This is a **long-only, swing-timeframe momentum screener and analysis tool** built in Python on free-tier data sources. It operationalizes three overlapping methodologies — **Mark Minervini's SEPA / Trend Template**, **Kristjan Kullamägi's (Qullamaggie) Breakout / Episodic Pivot / Parabolic** setups, and **William O'Neil's CANSLIM** — into a daily ranked watchlist with backtests, ML-augmented scoring, and an interactive dashboard.

The artifact serves two audiences simultaneously:
1. **Belwin as an end user** — a personal swing-trading research tool with a daily ranked watchlist, position-sizing guidance, and trade journaling.
2. **Hiring managers reviewing a portfolio** — a public deployment that demonstrates competence in modular Python design, ETL/data pipelines, ML feature engineering, backtesting rigor, and DevOps (CI/CD, scheduled jobs, observability) on a zero-cost stack.

Because the same codebase serves both, the project is engineered to look credible to a senior data engineer or quant reviewer: clean module boundaries, reproducible runs, honest backtests, type-checked code, and explicit handling of data-quality issues (survivorship bias, look-ahead, corporate actions, rate limits).

---

## 2. Trading Methodology — Authoritative Specifications

The screener implements three composable signal stacks. They share data and indicators but score independently so backtests can isolate which methodology contributes alpha.

### 2.1 Minervini Trend Template (Stage 2 confirmation gate)

The Trend Template is sourced from Minervini's *Trade Like a Stock Market Wizard* and *Think & Trade Like a Champion*. All eight conditions must pass simultaneously; failing one disqualifies the stock. Use **simple moving averages**, not EMAs.

1. Close > SMA(150) **and** Close > SMA(200)
2. SMA(150) > SMA(200)
3. SMA(200) is trending up for **at least one month** (~22 trading days). Stricter: rising 4–5 months. Implementation: `SMA200[today] > SMA200[today-22]`.
4. SMA(50) > SMA(150) **and** SMA(50) > SMA(200)
5. Close > SMA(50)
6. Close ≥ 1.30 × 52-week low (i.e., at least 30% above the low). The original *Wizard* book specifies 30%; *Think & Trade* relaxes to 25%. Use **30% as default**, expose as config.
7. Close ≥ 0.75 × 52-week high (within 25% of the high; closer is better — capture the gap as a continuous feature `pct_from_52w_high`).
8. **IBD RS Rating ≥ 70** (preferably ≥ 80–90). Because IBD's rating is proprietary, compute an IBD-style percentile rank in-house (see §2.4).

Implementation note: produce both a boolean `passes_trend_template` and a 0–8 integer `trend_template_score` so partial matches surface in ranking even when one condition fails marginally.

### 2.2 Qullamaggie Setups

Qullamaggie's published rules (qullamaggie.com, qullamaggie.net, his Twitch streams summarized in the community "Laws of Swing" doc) define three setups. The screener should implement all three but emphasize Setup A and B for daily EOD scans (Setup C — Episodic Pivots — needs intraday data and is implemented as an alert on gappers).

**Setup A — Breakout / Continuation Flag** (the core daily-EOD setup):

*Universe filter (the "scan"):*
- Stock is among the **top 1–2% of performers** over a lookback. Run three parallel scans: 1-month, 3-month, and 6-month % return rankings. A stock qualifies if it ranks in the top of any of them.
  - 1-month gain ≥ 30% (loosen to 20% in weak markets)
  - 3-month gain ≥ 50%
  - 6-month gain ≥ 100%
- Average daily dollar volume > $1.5M (Qullamaggie commonly cites volume > 1,500,000 shares; use dollar volume to normalize across price levels).
- **ADR% (20-day) ≥ 4%** (some traders use 3.5%). ADR% formula: `100 * (mean(high/low over 20 days) - 1)`.
- Price > $10 (avoid very low-priced names) — optional.

*Pattern (the "setup"):*
- Following a large prior leg up, the stock builds a 2-week to 2-month consolidation with **higher lows and a tightening range**, riding the 10-, 20-, or 50-day moving average ("the strongest ones find support on the 10-day, strong ones on the 20, and the slower ones on the 50"). Detect with a pivot-based contraction algorithm (see §3.4).

*Entry:*
- Buy stop at the recent swing high (consolidation high). Enters as the daily candle breaks the range.
- For intraday refinement: opening range high (1-min, 5-min, or 60-min ORH).
- **Buy zone**: best price is between half and two-thirds of the day's ATR above the prior close.

*Position sizing & risk:*
- **Stop = low of the day** (or low of the entry candle).
- **Risk per trade ≤ 1 × ADR**, ideally < 0.5 × ADR. If `entry_price - stop > ADR_dollars`, skip (R/R is broken).
- Position size = `account_risk_$ / (entry - stop)`.

*Exit:*
- Take 33–50% off after 3–5 days of profit, then move stop to break-even.
- Trail remainder on the **10-day SMA** (strongest movers), 20-day (medium), or 50-day (slowest). Exit on first daily close below the chosen MA.

**Setup B — Episodic Pivot (EP):**
- Trigger: stock gaps up **≥ 10%** on a major catalyst (earnings the strongest), strong volume, on/near the open.
- Entry: opening range breakout (1/5/60-min). Stop = low of opening candle (do not include the gap in the stop calculation).
- Risk ≤ 1 × ADR (preferably 1.5 × ADR maximum).
- Universe: pre-market gap scanner (use Finnhub/yfinance to detect overnight % change). For free EOD-only mode, EP can run as a "post-gap continuation" pattern detected on D+1.

**Setup C — Parabolic Long after Capitulation:**
- A successful parabolic short setup that has fallen 50–60%+ in a few days creates the long premise. Entry on first 5-min green candle / range break.
- Lower priority for the screener; flag candidates only.

### 2.3 CANSLIM (William O'Neil)

Used as a **fundamental quality overlay** rather than a primary signal. Free-tier data limits a strict implementation; we approximate.

| Letter | Strict criterion | Free-data implementation |
|---|---|---|
| C | Quarterly EPS YoY ≥ 25% (≥18–20% minimum) | `yfinance.Ticker(t).quarterly_earnings` or Finnhub `company-earnings`. Compute YoY growth on most recent quarter. |
| A | 3-yr annual EPS growth ≥ 25% per year | yfinance income statements `Ticker.financials` (annual) |
| N | New product / new high / new management | Proxy by **52-week high crossing** within last 60 days (computable) + 8-K filings via EDGAR for "new product" keyword (optional). |
| S | Limited supply, accumulation | Float < 50M is preferred for explosive moves; use Finnhub `stock/profile2` for `shareOutstanding`. Accumulation: 50-day up-volume vs down-volume ratio > 1. |
| L | Leader (RS ≥ 80–90) | Same RS rating as §2.4. |
| I | Institutional sponsorship rising | Quarter-over-quarter change in 13F holders count via EDGAR (edgartools). Optional. |
| M | Market in confirmed uptrend | See §2.5. **Critical gate** — reduce position size or pause new entries when this fails. |

Be honest with hiring reviewers: studies (Portfolio123 2019 analysis of CANSLIM) found that strict CANSLIM screening did not consistently outperform; the most robust factors are **C (recent earnings acceleration)**, **L (high RS)**, and **M (market direction)**. The screener uses these three as required, others as additive scoring.

### 2.4 Relative Strength Rating (IBD-style)

Two formulas widely circulate. Implement both, default to the **quarter-weighted** one because it matches IBD's stated "most recent quarter is weighted double."

**Formula 1 (most cited; quarter-weighted, used by Skyte's open-source `rs-log`):**
```
RS_raw = 2 * (C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
```
Where C is today's close and C_n is the close n trading days ago (63 = 1 quarter, 252 = 1 year).

**Formula 2 (IBD-style ROC sum, popular in Optuma/AmiBroker community):**
```
StrengthFactor = 0.4*ROC(C,63) + 0.2*ROC(C,126) + 0.2*ROC(C,189) + 0.2*ROC(C,252)
```

**Percentile transformation (the actual "rating"):**
After computing `RS_raw` for every stock in the investable universe on the same date, rank to a 1–99 percentile:
```python
rs_rating = pd.qcut(rs_raw_today, 99, labels=range(1,100)).astype(int)
# or:
rs_rating = (rs_raw_today.rank(pct=True) * 99).round().clip(1, 99).astype(int)
```
The percentile is universe-relative — recompute daily across the same universe (e.g., Russell 3000 or "all NYSE/NASDAQ common stocks > $5 and > 100k ADV"). Cache snapshots so historical RS ratings are reproducible (no look-ahead).

**Mansfield RS (alternative line for charts):**
```
Mansfield_RS = ((stock_close / index_close) / SMA_52w(stock_close / index_close) - 1) * 100
```
Use the Mansfield line on the chart pane to visualize RS leadership; use the IBD percentile for ranking.

**Edge cases:**
- Stocks with < 252 trading days of history: assign rating = NaN (do not pretend); for IPOs use IBD's convention of "1" until 5 trading days, then progressively widen.
- Splits: yfinance `auto_adjust=True` handles this in the close series; verify by spot-checking against known split events (NVDA 2024).

### 2.5 Market Regime / "M" Filter

A momentum book that ignores the M lets you down hard in 2008, 2022, etc. Implement a composite regime score that gates net long exposure.

Components (compute daily on `^GSPC` and `^IXIC`):
- **Trend filter:** `SPY_close > SMA(SPY, 200)` AND `SMA(SPY, 50) > SMA(SPY, 200)`.
- **Breadth:** % of stocks in the universe trading above their own 200-day SMA. Bullish > 60%, bearish < 40%.
- **Distribution day count** (IBD-style): in the last 25 sessions, count days where SPY closes down ≥ 0.2% on higher volume than the prior day. **5+ distribution days** = "Uptrend Under Pressure"; 6+ = "Market in Correction".
- **Walter Deemer Breakaway Momentum / Zweig Breadth Thrust** (optional, but a recognizable signal): 10-day advance/decline ratio crossing 2.0 marks a breadth thrust. Implement using NYSE A/D from Stooq or scraping from a free source.
- **VIX:** full size when VIX 12–20; cut 30% when 20–30; cut 50%+ above 30; pause new entries on intraday VIX spikes ≥ 5 points.

Output a single discrete state in `{Confirmed Uptrend, Uptrend Under Pressure, Correction}` plus a continuous `regime_score` ∈ [0, 1] that the position sizer multiplies into base risk.

### 2.6 ATR-Based Position Sizing & Stop Placement

Standard implementation:
```
ATR = pandas_ta.atr(high, low, close, length=14)  # Wilder's smoothing
ADR_pct = 100 * (high/low).rolling(20).mean() - 100   # Qullamaggie's ADR%
risk_per_share = entry - stop
shares = (account_equity * risk_pct_per_trade * regime_score) / risk_per_share
```
Defaults: `risk_pct_per_trade = 0.0075` (0.75%), capped at 1.5%. Hard cap any single position at 25% of equity even if the math allows more. Reject the trade if `risk_per_share > 1.0 * ADR_dollars` (Qullamaggie rule).

### 2.7 Composite Scoring

Each stock receives a 0–100 composite score combining:

| Component | Weight | Source |
|---|---|---|
| RS Rating (percentile) | 25% | §2.4 |
| Trend Template score (0–8 → 0–100) | 20% | §2.1 |
| Pattern score (VCP/Flag tightness, see §3.4) | 20% | §3.4 |
| Volume confirmation (50-day up/down ratio + breakout volume) | 10% | §3.3 |
| Earnings momentum (C+A from CANSLIM) | 15% | §2.3 |
| Catalyst presence (news/sentiment/EP gap) | 10% | §4 |

Weights are **starting points, not validated**. The backtest harness must run a weight-optimization sweep (vectorbt parameter grid) and report out-of-sample stability. Document this honestly in the README — over-fitted weights are the #1 reason these systems fail in live trading.

---

## 3. Technical Indicators — Implementation Detail

### 3.1 Library choice

Primary: **`pandas-ta`** (pure Python, no compilation). Secondary: **`TA-Lib`** when available (faster, but C dependency complicates Streamlit Cloud deploys). Wrap both behind a thin internal module `indicators.py` so the choice is swappable.

```python
import pandas_ta as ta
df.ta.sma(length=50, append=True)  # appends 'SMA_50'
df.ta.atr(length=14, append=True)
df.ta.adx(length=14, append=True)
df.ta.obv(append=True)
df.ta.bbands(length=20, std=2, append=True)
```

### 3.2 Multi-timeframe data

Resample daily OHLCV to weekly with `df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})`. Compute weekly Trend Template + RS in parallel; final score combines daily + weekly (Minervini explicitly references weekly MAs: "30-week" = 150-day, "40-week" = 200-day — they are equivalent up to resampling drift; document that the screener uses daily SMAs).

### 3.3 Volume Analysis

- **Volume dry-up**: 5-day average volume < 60% of 50-day average volume during the right side of a base. Coded as `dryup_ratio = vol_5d_mean / vol_50d_mean < 0.6`.
- **Volume surge / Pocket Pivot (Gil Morales)**: today's volume exceeds the largest down-day volume of the last 10 days, while price is above the 10-day MA. Strong accumulation marker.
- **Up/Down volume ratio (50-day)**: sum of volume on up-days / sum on down-days. Bullish > 1.0; for breakout stocks expect > 1.25.
- **OBV** divergences detected via `ta.obv()` then linear-regression slope vs price slope.

### 3.4 Pattern Detection — VCP and Flag

The most-asked-about and hardest-to-get-right component.

**Pivot detection** (foundation for all base patterns):
```python
from scipy.signal import argrelextrema
highs_idx = argrelextrema(df['High'].values, np.greater_equal, order=5)[0]
lows_idx  = argrelextrema(df['Low'].values,  np.less_equal,    order=5)[0]
```
`order=5` finds local extrema with at least 5 bars on each side; tune by base length.

**VCP algorithm (Minervini, simplified for code):**
1. Identify a prior **stage-2 uptrend leg** (≥ 30% rise over ≤ 6 months).
2. Within the most recent N bars (N ∈ [25, 65] — 5 to 13 weeks), enumerate consecutive contraction legs from local highs to local lows.
3. Require **at least 2 contractions, ideally 3–6**.
4. Each contraction's depth (high-to-low %) must be **smaller than the previous one**: `depth[i] < depth[i-1] * 0.85` is a usable threshold.
5. Maximum first-leg depth: ≤ 35% (deep VCPs ≤ 50% sometimes work but raise risk).
6. Final contraction depth: ≤ 10–12% (the "tight right side" — Minervini wants under 10%).
7. Volume contracts in step with price (volume on each leg's down-bars decreases). Coded: `mean_volume[leg_i] < mean_volume[leg_{i-1}]`.
8. Pivot price = high of the most recent contraction. Breakout signal = close > pivot on > 1.5× 50-day average volume.

Reference implementations to study (do not copy verbatim — license-check first): `clairetsoi1129/stock-screener`, `shiyu2011/cookstock`, `crankycandle/volatility-contraction-pattern`. The TradingView indicator by Amphibiantrading codifies the same logic in Pine.

**Flag / Continuation pattern (Qullamaggie):**
Detect a **prior leg of ≥ 25% in ≤ 30 trading days**, followed by a **consolidation of 5–25 bars** where:
- Range (`bar.high - bar.low`) for each bar < 1.0 × ATR(20).
- Each bar's close stays above the 10-day OR 20-day SMA.
- Higher lows: the 5-bar trailing low is non-decreasing across the consolidation.
- Volume during consolidation < volume during the leg.
Pivot = highest high of the consolidation. Same breakout trigger as VCP.

**Cup & Handle:**
- Cup: U-shape with depth 12–35%, duration 7–65 weeks. Detect by fitting a quadratic to the rolling window and checking concavity, plus pivot symmetry.
- Handle: 1–4 week pullback after cup right-side recovery, depth 8–15%, on declining volume.
This is the hardest to detect cleanly; consider deferring to V2 and using VCP/Flag in V1.

### 3.5 Sector / Industry Relative Strength

For each stock, fetch its sector/industry from `yfinance.Ticker(t).info` or Finnhub `stock/profile2`. Compute sector ETF returns (e.g., XLK, XLF, XLE for SPDR sectors) and industry-level RS by aggregating member-stock RS. Boost the composite score for stocks whose **industry RS rank** is in the top quartile — group moves are a strong Minervini and O'Neil tenet.

---

## 4. Catalyst Detection from Free Data

| Catalyst | Free source | Library / endpoint |
|---|---|---|
| Earnings calendar | yfinance `Ticker.calendar`, Finnhub `/calendar/earnings` | yfinance, finnhub-python |
| Earnings surprise | Finnhub `/stock/earnings`, yfinance `earnings_dates` | finnhub-python |
| Analyst rating changes | Finnhub `/stock/upgrade-downgrade` (free tier) | finnhub-python |
| News headlines | NewsAPI free (100 req/day, 24-hr delay), Finnhub `/company-news`, yfinance `Ticker.news` | requests, finnhub-python |
| Reddit sentiment | r/wallstreetbets, r/stocks, r/swingtrading, r/StockMarket via PRAW | praw |
| Insider trading | SEC Form 4 via EDGAR | **edgartools** (recommended) or sec-edgar-downloader |
| Institutional holdings | SEC Form 13F-HR | edgartools |
| Macro context | FRED API (rates, unemployment, ISM, yield curve) | fredapi |
| Unusual options activity | No reliable free source. Closest free proxy: CBOE daily volume PDFs, or Barchart "unusual options" scrape (ToS-fragile). **Honestly omit from V1.** |

### 4.1 News Sentiment with FinBERT

Use **ProsusAI/finbert** via Hugging Face transformers. Runs locally on CPU; a single headline classifies in ~50ms.

```python
from transformers import pipeline
nlp = pipeline("sentiment-analysis", model="ProsusAI/finbert", tokenizer="ProsusAI/finbert")
# Returns label in {positive, negative, neutral} with score
```

Pipeline:
1. Pull last 7 days of headlines per ticker (Finnhub `/company-news`).
2. Run FinBERT on each headline + first 256 chars of body.
3. Compute `sentiment_score = mean(positive_prob - negative_prob)` weighted by recency (exp decay, half-life 3 days).
4. Spike detection: today's mean sentiment > 1.5 standard deviations above 30-day mean → flag.

FinBERT-tone (`yiyanghkust/finbert-tone`) is also viable; the Prosus model is the canonical research baseline.

### 4.2 Reddit / Social Sentiment (PRAW)

```python
import praw
reddit = praw.Reddit(client_id=..., client_secret=..., user_agent="momentum-screener/0.1 by Belwin")
subs = ['wallstreetbets', 'stocks', 'swingtrading', 'StockMarket', 'pennystocks']
```
For each sub, pull `.new(limit=500)` daily, regex-extract `$TICKER` mentions (filtered against the ticker universe to avoid common-word collisions like `A`, `IT`), count mentions, run FinBERT on titles, and compute a `social_buzz_score` per ticker. Cache in SQLite. Treat WSB sentiment as a **contrarian indicator at extremes** and disclose this in the dashboard.

### 4.3 SEC EDGAR

Use **`edgartools`** (the dgunning/edgartools library — pip-installable, parses XBRL, returns pandas DataFrames). It is materially easier than rolling raw EDGAR HTTP. Set the SEC-required identity once:
```python
from edgar import set_identity, Company
set_identity("Belwin <email@example.com>")
form4s = Company("NVDA").get_filings(form="4").head(20)
df = pd.concat([f.obj().to_dataframe() for f in form4s])
```
Daily job: pull all Form 4 filings in the last 24h, extract net insider buying (cluster buying = multiple insiders buying within 5 days = strong signal), join to the watchlist.

For 13F: download quarterly filings of a curated list of "smart money" funds (Baillie Gifford, Whale Rock, Tiger Global, Berkshire, Stanley Druckenmiller's Duquesne) and flag stocks newly added by ≥ 2 funds in the latest quarter.

---

## 5. Data Sourcing Architecture

### 5.1 Source matrix (free tiers, current as of 2026)

| Source | Free tier reality | Best for | Watch out for |
|---|---|---|---|
| **yfinance** | No official rate limit; unofficial, scrapes Yahoo, occasionally breaks | Bulk daily OHLCV, splits/dividends, fundamentals | **Frequent rate-limit / 429 episodes**; the library has been unstable in 2024–2025. Always cache aggressively. |
| **Finnhub free** | 60 calls/min, US real-time delayed 15 min, 1 yr historical | News, earnings calendar, upgrade/downgrade, profile, basic financials | Historical depth limited; some endpoints premium. |
| **Alpha Vantage free** | ~25 requests/day (recently tightened), 5/min historically | Technical indicators (pre-computed), some fundamentals | Daily quota too small for universe scans — use only for indicator validation or specific lookups. |
| **NewsAPI free** | 100 requests/day, 24-hour-delayed articles, dev only | Broad news queries | The 24-hour delay rules it out for catalyst trading; OK for backtests / sentiment training. |
| **Reddit / PRAW** | Generous; OAuth app required | Social sentiment | Rate limit ~60 req/min per OAuth app. |
| **SEC EDGAR** | Free, 10 req/sec with proper User-Agent identity | Form 4, 13F, 10-K/Q, 8-K | Must set identity header; respect rate limit. |
| **FRED** | Free with API key, very generous | Macro: VIX, Treasury yields, credit spreads, ISM | None significant. |
| **Stooq** | Free, EOD CSVs, no key | Index history, A/D line, sector ETFs | Data quality occasionally lags by a day. |

### 5.2 Stock universe (free)

- **Wikipedia tables** for S&P 500, S&P 400, S&P 600 (via `pd.read_html`). Re-scrape weekly.
- **NASDAQ Trader symbol directory** (`ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt`) for all listed symbols.
- **Russell 1000 / 3000**: iShares publishes the IWB/IWV holdings CSV (free download).
- Filter common-stock-only, price > $5, ADV > $1M, exclude OTC/PINK.

### 5.3 Survivorship bias

This is the largest data-quality pitfall on free sources, and you must call it out explicitly in the README. **yfinance and Finnhub return current constituents; delisted stocks are silently absent.** A backtest universe built today will *not* contain ENRN, BBBY, etc.

Mitigations:
1. Snapshot the universe weekly and persist (SQLite or Parquet on disk + a backup commit to a private git submodule). Over time you accumulate a real point-in-time universe.
2. For longer historical backtests, accept a **smaller, stable universe** (S&P 500 current constituents — explicitly a survivorship-biased benchmark) and disclose the bias in the report. Quote the Sharpe degradation typically observed (0.2–0.5) when survivorship is corrected.
3. Optional paid escape hatch: Norgate Data ($30/mo, has historical S&P constituents) — but this violates the "free only" constraint. Document the limitation and move on.

### 5.4 Look-ahead bias

Every indicator value at time `t` must be computable with data available *as of* the close of `t`. Discipline:
- Backtests use `signal[t]` to **enter at open of t+1** (not close of t).
- Earnings dates: use the **announcement timestamp**, not the period-end date — yfinance returns period dates; Finnhub returns proper `time` (BMO/AMC) flags.
- Fundamentals: lag 45 days after fiscal-quarter end (10-Q deadline) before considering the data "known."

### 5.5 Corporate Actions

`yfinance.download(t, auto_adjust=True)` gives split-and-dividend-adjusted closes — sufficient for indicators. Keep an unadjusted copy for pivot/breakout-level integrity in pattern detection (Minervini's pivots are price-based; if you fail to use unadjusted prices you'll mis-identify pre-split bases; alternatively, store adjustment factors and re-apply).

### 5.6 Caching

Use **`requests-cache`** for HTTP-based APIs (Finnhub, NewsAPI, Alpha Vantage) with a 1-hour expiry for intraday endpoints and 24h for fundamentals. For yfinance, cache OHLCV to **Parquet on disk**, partitioned by ticker. Daily job appends only the last bar.

```python
from pathlib import Path
import pyarrow.parquet as pq
def cached_ohlcv(ticker: str, start='2010-01-01') -> pd.DataFrame:
    path = Path(f'data/ohlcv/{ticker}.parquet')
    if path.exists():
        df = pd.read_parquet(path)
        if df.index[-1].date() == pd.Timestamp.today().normalize().date():
            return df
        new = yf.download(ticker, start=df.index[-1] + pd.Timedelta(days=1), auto_adjust=True)
        df = pd.concat([df, new]).drop_duplicates()
    else:
        df = yf.download(ticker, start=start, auto_adjust=True)
    df.to_parquet(path)
    return df
```
Use **`tenacity`** for retry/backoff on 429s. Sleep `random.uniform(0.5, 1.5)` between tickers; never go faster than 60 req/min for Finnhub.

---

## 6. Backtesting Framework

### 6.1 Library choice

**Primary: `vectorbt` (community edition)** for parameter-sweep research.
- Reasons: blazing-fast (Numba/Rust), Plotly integration, native DataFrame I/O, fits naturally with pandas-ta, can backtest 1000s of parameter combinations in seconds. Great signal for ML hiring managers.
- Caveat: free version's active development has slowed (PRO is paid). API is mature enough that this is acceptable.

**Secondary: `backtrader`** for event-driven verification of selected strategies and trade journaling.
- Reasons: easy realistic order modeling (limit orders, stops, slippage), strong precedent for research-to-paper-trading transition.
- Caveat: development tapered around 2018–2021 (community fork `backtrader2` exists for bug fixes). Use it as a sanity check, not the primary engine.

**Skip Zipline-reloaded** for new development — it's installation-heavy, designed around the legacy Quantopian bundle/ingest workflow, and is now a "learn the concepts" library more than a default choice.

### 6.2 Vectorbt patterns for momentum

```python
import vectorbt as vbt
# Universe close prices: shape (T x N)
close = data['Close']
# Signal stack
trend_ok = trend_template_pass(close, ...)        # bool DataFrame
breakout = (close > pivot.shift(1)) & (volume > 1.5 * volume.rolling(50).mean())
entries = trend_ok & breakout
# ATR-based stop and 10/20/50-MA trailing exit
exits = close < ema_trail
pf = vbt.Portfolio.from_signals(
    close, entries, exits,
    init_cash=100_000,
    fees=0.0005,           # 5 bps round-trip ≈ realistic on retail with no commission
    slippage=0.001,        # 10 bps; larger for thin names
    sl_stop=atr_stop_pct,  # ATR stop as a percent of entry
    size=position_size,    # dollar amount per trade
    freq='D'
)
print(pf.stats())
```

### 6.3 Mandatory hygiene

- **Transaction costs**: 0 commission (Robinhood/IBKR Lite), but model **5 bps slippage minimum** for liquid names, 25 bps for ADV < $5M. Round-trip > 30 bps for low-ADV breakout entries (real, due to spread + impact at breakout volume).
- **Look-ahead**: enforce by computing all signals with `.shift(1)` before entry/exit logic, OR using `from_signals` with the convention that signals at bar `t` execute at bar `t+1` open.
- **Position sizing**: never assume infinite capital; cap per-position to 25% and per-strategy total exposure to 100%.
- **Survivorship**: see §5.3.

### 6.4 Walk-forward + Monte Carlo

- **Walk-forward**: split history into rolling (3-yr in-sample, 1-yr out-of-sample) windows; optimize composite score weights on IS, evaluate on OOS, report the **OOS Sharpe distribution** rather than a single number.
- **Monte Carlo**: shuffle the realized-trade sequence (block-bootstrap, block size = 10) 1000 times, plot the distribution of terminal equity and max drawdown. The 5th-percentile max DD is the honest worst case to plan around.

### 6.5 Metrics to report

| Metric | Computation | Why |
|---|---|---|
| CAGR | Annualized geometric return | Standard |
| Sharpe (rf=0) | `mean / std * sqrt(252)` | Risk-adjusted |
| **Sortino** | `mean / downside_std * sqrt(252)` | Better for skewed momentum returns |
| **Calmar** | `CAGR / max_drawdown` | Drawdown-aware |
| Max DD | `1 - (equity / equity.cummax()).min()` | Pain |
| Win rate, Avg win / Avg loss, **Profit Factor**, **Expectancy** | Per-trade stats | Strategy character |
| Exposure | `% time in market` | Honest comparison vs B&H |
| Turnover | Trades / period | Cost sensitivity |
| **vs. Benchmark (SPY)** alpha and beta | OLS on monthly returns | Required by any reviewer |

### 6.6 Evaluating composite scores

Test the score in deciles: rank stocks daily by composite score, hold the top decile equal-weight rebalanced weekly, report the spread between top decile and bottom decile (a long-short proxy demonstrating the score's monotonicity even though we trade long-only). This is a standard quant-research presentation that signals competence to a hiring manager.

---

## 7. ML / Data Science Layer

### 7.1 Scope decision

**Include this layer.** It is the single most useful differentiator for portfolio impact. Keep it tightly bounded — predict probability of "stock will be up X% over next 20 days conditional on triggering a breakout."

### 7.2 Stack

- **LightGBM** (preferred) or **XGBoost** for tabular gradient boosting. Both are free, well-documented, and famously strong on financial features.
- **scikit-learn** for pipelines, cross-validation, calibration.
- **MLflow** for experiment tracking (free, local file backend works).
- **SHAP** for model explainability — produce a per-prediction SHAP plot in the dashboard. Recruiters love this.

### 7.3 Feature engineering (60–80 features)

Group | Examples
---|---
Trend & MA distance | `pct_above_sma_50`, `sma50_slope_20d`, `days_since_above_sma200`
Momentum | 1m/3m/6m/12m return, IBD RS rating, RS vs sector, sector RS rank
Volatility | ATR/price, 20-day realized vol, ADR%, BBand width
Volume | Volume z-score, up/down vol ratio (50d), days since pocket pivot
Pattern | VCP contraction count, final-leg depth, base length, distance from pivot
Fundamentals | EPS YoY %, EPS QoQ acceleration, sales YoY %, ROE, debt/equity
Catalysts | Days to next earnings, last earnings surprise %, FinBERT 7d sentiment, social buzz z-score
Insider | Net insider buying $ last 30/90 days, cluster-buy flag
Market regime | SPY 200d trend flag, breadth %, distribution day count, VIX level

### 7.4 Target

Binary: `1 if forward 20-day return > 10% AND max drawdown over 20d > -8%`, else 0. Train on triggered breakouts only (the system already filtered the universe — predicting on all stocks dilutes signal). This is **purchase-quality classification**, not return forecasting; calibrated probability becomes the ML score component of the composite.

### 7.5 Avoiding overfit (critical for credibility)

- **Time-series CV** (sklearn `TimeSeriesSplit` or purged k-fold à la López de Prado).
- **Embargo period** of ~21 days between train and test to prevent label leakage from overlapping forward windows.
- Feature scaling done **inside the CV fold**, never on the full dataset.
- Report **OOS log-loss / AUC / Brier score**, not in-sample accuracy.
- Calibrate output probabilities (`sklearn.calibration.CalibratedClassifierCV`) so the score is interpretable as P(success).
- Run **deflated Sharpe** on the strategy after weighting by ML score — shows you know about multiple-testing bias.

---

## 8. Deployment Architecture (Free Tier)

### 8.1 Recommended stack

| Layer | Choice | Why |
|---|---|---|
| Dashboard | **Streamlit Community Cloud** | Free, GitHub-integrated, instant Python deploys. Public URL. |
| Code & CI | **GitHub** + **GitHub Actions** | 2,000 min/mo free for private repos, unlimited for public. |
| Scheduled data jobs | **GitHub Actions cron** (`schedule: cron: '30 22 * * 1-5'`) | Free for public repos. Runs nightly, commits Parquet/SQLite snapshots back to a `data` branch or pushes to Supabase. |
| Database | **Supabase free tier** (500 MB Postgres, 2 GB bandwidth) **or** SQLite committed to repo | Supabase if you want a real Postgres demonstration; SQLite-on-disk if simpler. |
| Object storage | Supabase Storage 1 GB or commit to repo (if < 100 MB) | |
| Secrets | GitHub Actions secrets + Streamlit `secrets.toml` | |
| Model artifacts | Hugging Face Hub (free, public) | Demonstrates ML ops awareness. |
| Optional alt-deploy | **Hugging Face Spaces** (Streamlit-compatible, free CPU) | Backup deployment; surfaces in HF community. |

Avoid: Render free tier (spins down after inactivity, slow cold starts), Vercel (Python serverless is awkward for long-running ML inference), Railway (free tier eliminated mid-2023).

### 8.2 Daily pipeline (GitHub Actions example)

```yaml
name: daily-data-refresh
on:
  schedule: [{cron: '30 22 * * 1-5'}]  # 22:30 UTC weekdays = post-close ET
  workflow_dispatch:
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -e .
      - env:
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          # ...
        run: python -m screener.cli refresh-all
      - run: python -m screener.cli rank
      - uses: stefanzweifel/git-auto-commit-action@v5
        with: {commit_message: "data: nightly refresh"}
```

### 8.3 What signals "data engineering competence" to a reviewer

1. **Deterministic pipelines** — every run produces a reproducible artifact (Parquet snapshot of the universe + ranking with timestamp).
2. **Idempotent, incremental loads** — re-running yesterday's job doesn't double-write.
3. **Schema enforcement** with **`pandera`** or **`pydantic`** at every IO boundary.
4. **Observability** — `structlog` JSON logs streamed to stdout; metrics pushed to a free Prometheus-compatible endpoint (Grafana Cloud free tier, 10k series) or simply written to a `runs.jsonl` log committed to the repo.
5. **Data quality tests** — Great Expectations or hand-rolled pytest checks on row counts, null rates, date monotonicity. Fail loud on drift.
6. **A small DAG diagram** in the README showing source → staging → feature → score → publish.
7. **`Makefile`** with `make data`, `make rank`, `make backtest`, `make app`. Simple, professional.
8. **Type hints everywhere**, ruff + mypy in CI, ≥ 80% coverage on the indicator/score modules.
9. **A `dbt`-style modeling layer is overkill** for this size, but if you want extra signal, add a tiny dbt project that materializes views over the Parquet store via `duckdb` — that single addition is hugely impressive for a portfolio piece.
10. **PySpark mention**: implement a parallel `spark_runner.py` that performs the universe-scan computation on Spark for runs of > 5,000 tickers. Even if not used in the daily job, it's a 2-hour add that lets you say "scales horizontally to Russell 3000+ via PySpark."

---

## 9. UI / UX — Dashboard

### 9.1 Streamlit page layout

- **Page 1: Today's Watchlist** — Table sorted by composite score; columns: ticker, sector, RS rating, trend score, pattern, days from pivot, ADR%, suggested entry / stop / size, last earnings date. Color-coded composite score (green ≥ 80). Filters in sidebar (min RS, min ADR%, sector multi-select, regime gate on/off).
- **Page 2: Stock Detail** — Candlestick (Plotly with rangeslider), overlaid SMAs (10/20/50/150/200), volume sub-panel, RS line vs SPY (Mansfield), VCP contraction annotations, pivot line, ATR stop band, recent earnings & analyst rating cards, news headlines with FinBERT sentiment chips, SHAP waterfall for the ML probability.
- **Page 3: Market Regime** — SPY chart with 200d MA, breadth gauge, distribution-day stamps, VIX, FRED yield-curve plot. Big traffic-light at the top.
- **Page 4: Backtest Lab** — User picks signal weights with sliders, hit "Run" → vectorbt portfolio runs (cached with `@st.cache_data`), shows equity curve vs SPY, drawdown curve, monthly returns heatmap, trade list, walk-forward bar plot. SHA-stamped so reviewers see honest results, not cherry-picked.
- **Page 5: Trade Journal** — Manual trade log (CSV/SQLite-backed), realized P&L, win-rate, expectancy, mistake tags.

### 9.2 Charts & libraries

- **Plotly** for candlesticks, equity curves, scatter (factor exposure), heatmaps. Native Streamlit integration (`st.plotly_chart`). The **`plotly.graph_objects.Candlestick`** + range slider is the canonical financial chart.
- **`mplfinance`** as a fallback for static export PNGs (good for the README screenshots).
- **Altair** for clean monthly-return heatmaps (one of its best use-cases).
- Avoid using matplotlib directly in the live dashboard.

### 9.3 Aesthetic notes

Use Streamlit's dark theme by default for a "Bloomberg" look (set in `.streamlit/config.toml`). Add a custom Plotly template with monospaced axis labels. Include a small `Last refresh: 2026-04-28 22:30 UTC | universe: 2,847 tickers | scan time: 3.4s` strip at the bottom — small operational details signal professionalism.

---

## 10. Code Architecture & Quality

### 10.1 Repository layout

```
momentum-screener/
├── pyproject.toml              # uv / hatch managed
├── README.md
├── CLAUDE.md
├── Makefile
├── .github/workflows/
│   ├── ci.yml                  # ruff + mypy + pytest on PR
│   └── refresh.yml             # daily data + ranking
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── src/screener/
│   ├── __init__.py
│   ├── config.py               # pydantic-settings, single source of truth
│   ├── universe.py             # universe construction
│   ├── data/
│   │   ├── ohlcv.py            # yfinance + cache
│   │   ├── fundamentals.py     # finnhub + edgar
│   │   ├── news.py             # finnhub + newsapi
│   │   ├── reddit.py           # praw
│   │   ├── macro.py            # FRED + breadth
│   │   └── edgar.py            # form 4 / 13F
│   ├── indicators/
│   │   ├── trend.py            # SMAs + Trend Template
│   │   ├── relative_strength.py # IBD RS + percentile
│   │   ├── volatility.py       # ATR, ADR%
│   │   ├── volume.py           # OBV, dryup, pocket pivot
│   │   └── patterns.py         # VCP, flag, cup&handle
│   ├── signals/
│   │   ├── minervini.py
│   │   ├── qullamaggie.py
│   │   ├── canslim.py
│   │   └── composite.py        # weighted score
│   ├── regime.py
│   ├── catalysts/
│   │   ├── sentiment.py        # finbert
│   │   └── insider.py
│   ├── ml/
│   │   ├── features.py
│   │   ├── train.py            # lightgbm + mlflow
│   │   └── predict.py
│   ├── backtest/
│   │   ├── vbt_runner.py
│   │   ├── walkforward.py
│   │   └── metrics.py
│   ├── sizing.py               # position sizing rules
│   ├── persistence.py          # parquet + sqlite I/O
│   ├── cli.py                  # typer-based: refresh, rank, train, bt
│   └── spark_runner.py         # optional PySpark parallel scan
├── app/
│   ├── streamlit_app.py
│   └── pages/
│       ├── 1_Watchlist.py
│       ├── 2_Stock_Detail.py
│       ├── 3_Regime.py
│       ├── 4_Backtest_Lab.py
│       └── 5_Journal.py
├── tests/
│   ├── test_indicators.py
│   ├── test_signals.py
│   ├── test_regime.py
│   ├── test_backtest_no_lookahead.py  # critical
│   └── conftest.py             # synthetic OHLCV fixtures
└── notebooks/
    ├── 01_research_minervini.ipynb
    ├── 02_research_qullamaggie.ipynb
    └── 03_ml_feature_importance.ipynb
```

### 10.2 Configuration

`pydantic-settings` for typed env-driven config; YAML for strategy parameters that humans edit. Avoid Hydra — overkill for this scope and adds friction to the Streamlit deploy.

```python
# src/screener/config.py
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    finnhub_api_key: str
    fred_api_key: str
    reddit_client_id: str
    reddit_client_secret: str
    universe: str = "russell1000"
    rs_lookback_days: int = 252
    risk_pct_per_trade: float = 0.0075
    class Config:
        env_file = ".env"
settings = Settings()
```

### 10.3 Tooling

- **`uv`** (Astral) for venv + dependency resolution — fast, modern, signals competence.
- **`ruff`** for lint + format (replaces black + isort + flake8).
- **`mypy --strict`** on `src/screener/indicators/` and `signals/` (the math).
- **`pytest`** + **`hypothesis`** for property-based tests on indicators (e.g., "SMA of N constants = that constant").
- **`pre-commit`** with ruff, mypy, pytest --quick.

### 10.4 Logging / observability

```python
import structlog
log = structlog.get_logger()
log.info("rank_complete", n_pass=len(passing), regime=regime.state, top=top10)
```
Stream JSON logs; in CI, attach a summary of the run (passing tickers, count) as a workflow artifact.

### 10.5 Testing strategy

- **Indicators**: deterministic, test against known inputs (e.g., SMA, ATR against TA-Lib reference outputs to within 1e-6).
- **Signals**: golden-file tests on historical examples (`assert was_in_trend_template("NVDA", "2023-05-15") == True`).
- **No-look-ahead test**: critical. Construct a backtest where signal is identical to "next-day return"; assert that the strategy *cannot* be profitable when signals are correctly shifted. If it is profitable, you have a bug.
- **Regime test**: 2008, 2020-Q1, 2022 should all classify as Correction at some point.

---

## 11. CLAUDE.md File Best Practices (How to Author the Companion File)

Synthesizing Anthropic's official guidance with HumanLayer, abhishekray07/claude-md-templates, and the developer community consensus:

### 11.1 Length and tone

- Target **< 300 lines** for the project root `CLAUDE.md`. Shorter is better; HumanLayer's root file is < 60 lines.
- Frontier models attend to ~150–200 instructions reliably; everything beyond gets dropped silently.
- Prefer **short imperative bullets**, not prose. "Use SMAs not EMAs for the Trend Template" beats a paragraph explaining why.
- Use `IMPORTANT` and `YOU MUST` sparingly to flag inviolable rules (e.g., "YOU MUST shift signals by one bar before computing entries").

### 11.2 Required sections

A high-leverage `CLAUDE.md` covers WHAT, WHY, HOW:

1. **Project summary** (1–3 lines): what the tool is and its tech stack.
2. **Commands** (the Bash incantations: `make data`, `make rank`, `pytest`, `streamlit run app/streamlit_app.py`, `ruff check`, `mypy`).
3. **Repository map** (where things live so Claude doesn't grep blindly).
4. **Coding conventions** (Python 3.11+, type hints required in `signals/` and `indicators/`, prefer pure functions, no print → use `structlog`, no global state in modules).
5. **Library preferences** (yfinance for OHLCV; `edgartools` not raw EDGAR; vectorbt over backtrader for new tests; pandas-ta over TA-Lib by default; LightGBM over XGBoost).
6. **Architectural rules** (every external API call goes through `data/`; signals consume DataFrames, return DataFrames of identical index; no I/O in `signals/`).
7. **Testing rules** ("Run `pytest tests/test_backtest_no_lookahead.py` after any change to `signals/` or `backtest/`").
8. **Trading-domain pitfalls** ("The Trend Template uses SMA not EMA"; "Entry is at next-bar open, never current-bar close"; "Fundamentals lag 45 days after fiscal-quarter end before being used as features"; "yfinance occasionally returns split-unadjusted volume — verify on splits").
9. **What NOT to do** ("Do not introduce new dependencies without checking they install on Streamlit Cloud's free runner — avoid heavy CUDA wheels, TA-Lib C, etc."; "Do not use Alpha Vantage as primary OHLCV source — quota is 25/day").
10. **Self-update directive**: "When you make a mistake the user has to correct, append the lesson to this file."

### 11.3 Layered files

- `~/.claude/CLAUDE.md` — Belwin's personal global preferences.
- Project root `CLAUDE.md` — committed, the canonical project context.
- `CLAUDE.local.md` — gitignored, for personal workflow tweaks.
- `.claude/rules/` — modular rule files referenced via `@.claude/rules/python-style.md` for path-scoped or file-type-scoped instructions (e.g., separate rules for `notebooks/` allowing more exploratory style).

### 11.4 Progressive disclosure

Heavy reference material (e.g., the full Trend Template criteria, the full IBD formula) lives in `docs/methodology.md` and is referenced from `CLAUDE.md` via `@docs/methodology.md`, so Claude pulls it only when working on related code. This keeps the always-on context lean.

### 11.5 What to leave OUT

- Long descriptions of how external APIs work (Claude can read API docs when needed).
- Speculative future features.
- Long preambles, project history, "we are excited to..." filler.
- Code examples that duplicate what's in the codebase.

---

## 12. Portfolio Presentation

### 12.1 README structure

1. **Hero**: GIF screencast of the dashboard, three numbers (e.g., "Universe scanned: 2,847", "Daily watchlist: 12", "OOS Sharpe (2018–2025 walk-forward): 1.18").
2. **Problem statement** in 3 sentences: a swing trader needs to scan a few thousand stocks for a handful of setups daily; this tool automates Minervini/Qullamaggie/CANSLIM screening, ranks with ML, and runs free.
3. **Live demo link** (Streamlit Community Cloud public URL).
4. **Architecture diagram** (a single PNG showing source APIs → ETL → feature store → composite scorer → ML model → dashboard, with the GitHub Actions cron annotated). Generate with **excalidraw** or `mermaid`.
5. **Methodology summary** (link to `docs/methodology.md` for depth).
6. **Backtest results table**: CAGR, Sharpe, Sortino, Calmar, max DD, win rate vs SPY benchmark, **with disclosed data caveats** (universe, period, survivorship, slippage assumptions). Honesty is more impressive than flashy numbers.
7. **Walk-forward equity curve** (one Plotly export PNG).
8. **Tech stack badges** (Python, Streamlit, vectorbt, LightGBM, Hugging Face, GitHub Actions).
9. **Reproducibility**: `git clone && uv sync && cp .env.example .env && make data && make app`.
10. **Roadmap** (3 bullets — shows you know the limitations).

### 12.2 Honest backtest reporting

Hiring managers know that any momentum strategy on free data has at least three fudge points. Disclose all three explicitly:
- Survivorship bias on universe (estimate the upward bias as ~1–2% CAGR).
- Slippage assumptions and where they break (low-ADV breakouts).
- Period selection (your best period is probably 2017–2021; show 2022 too — even if it's painful).

A real walk-forward Sharpe of 0.7–1.2 with honest assumptions reads as more credible than a fitted Sharpe of 2.5.

### 12.3 Live demo, screenshots, video

- **Live demo: yes, must-have.** It is the difference between "another GitHub repo" and "an actual product." Streamlit Community Cloud cost: $0.
- **Screenshots: 3–5 high-quality PNGs** in the README (Watchlist, Stock Detail, Backtest Lab).
- **Video walkthrough: yes, 90 seconds.** Loom or asciinema recording showing: open dashboard → today's top 5 → click into NVDA → see VCP detection → run a 3-line backtest → show walk-forward result. Embed in README.

### 12.4 Talking about it in interviews

Frame the project around **engineering decisions**, not trading edge:
- "I used vectorbt over backtrader because the parameter sweep needed for walk-forward optimization is 20× faster on a vectorized engine."
- "I used `edgartools` instead of building EDGAR HTTP myself because parsing XBRL correctly is a project in itself, and I wanted to focus engineering time on the signal layer."
- "Survivorship bias is the most common pitfall here; I disclosed it, then partially mitigated it by snapshotting the universe weekly so going forward I'll have a real point-in-time dataset."
- "I included a PySpark version of the universe scan because at 5,000+ tickers the pandas loop becomes the bottleneck; this is a portfolio choice — over-engineered for the live use case but demonstrates I know how to scale it."

Avoid claiming the strategy "works" or quoting unverified Sharpe numbers. Talk about the *system*, not the *alpha*.

---

## 13. Specific Critical Details — Quick-Reference

### 13.1 Minervini Trend Template (canonical 8 conditions)
```
1. Close > SMA150 AND Close > SMA200
2. SMA150 > SMA200
3. SMA200 > SMA200 22 trading days ago
4. SMA50 > SMA150 AND SMA50 > SMA200
5. Close > SMA50
6. Close >= 1.30 * MIN(Low, 252)        # 30% above 52-wk low
7. Close >= 0.75 * MAX(High, 252)       # within 25% of 52-wk high
8. RS_Rating >= 70                       # IBD percentile rank
```

### 13.2 IBD-style RS (canonical formula)
```
RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
RS_rating = 1 + 98 * percentile_rank(RS_raw, universe)   # → integer 1..99
```

### 13.3 Qullamaggie Breakout (canonical scan + entry)
```
SCAN: top 1-2% performers over 1m / 3m / 6m AND
      ADV > $1.5M AND ADR%(20) >= 4
SETUP: 5-25 bar consolidation along rising 10/20/50 SMA, higher lows, range tightening
ENTRY: buy stop at consolidation high (or ORH on 1/5/60-min)
STOP: low of entry day (low of opening candle for EP); risk <= 1*ADR
EXIT: 33-50% off after 3-5 days of profit; trail rest on 10/20/50 SMA close
```

### 13.4 VCP detection thresholds (recommended starting values)
```
prior_uptrend_pct      >= 30% over <= 6 months
n_contractions         in [2, 6]
each_contraction_smaller_by  >= 15% (so depth_i / depth_{i-1} <= 0.85)
first_leg_max_depth    <= 35%
final_contraction_max_depth   <= 12%
volume_per_leg_decreasing      True
breakout_volume        >= 1.5 * SMA(volume, 50)
```

### 13.5 ADR% formula
```
ADR_pct = 100 * ( (high/low).rolling(20).mean() - 1 )
```

### 13.6 Common pitfalls (what doesn't work / what looks good but isn't)
1. **EMA substitution** for SMA in the Trend Template — produces meaningfully different results; stick to SMA.
2. **In-sample weight optimization** for the composite score — guaranteed overfit. Always walk-forward.
3. **Ignoring the M filter** — a long-only momentum book that ran through 2008 / 2022 unhedged would have lost 50%+; the regime gate is non-negotiable.
4. **Free EOD data and intraday entries** — the EP and ORH entries fundamentally need intraday data; for free-tier you can either accept next-day-open execution (lower edge but honest) or limit yourself to daily-bar setups.
5. **News sentiment as a primary signal** — at headline level, FinBERT correlates weakly with forward returns; treat as a tertiary feature, not a driver.
6. **WSB sentiment as a buy signal** — repeatedly demonstrated to be a contrarian indicator at extremes (GME aftermath); use as a flag, not a vote.
7. **Survivorship-biased Sharpe ratios** quoted without context.
8. **Forgetting to handle splits** in pivot-level breakout detection (the breakout level itself was at a pre-split price; if you compare a post-split bar to a pre-split pivot you get a false signal). Either store and compare on adjusted-only data, or store both and re-derive.
9. **Letting Alpha Vantage be the primary data source** — quota is now ~25/day on free tier; will throttle the whole scan.
10. **Not respecting Yahoo's unofficial rate limits** — yfinance breaks repeatedly; retry/backoff and aggressive caching are mandatory.

---

## 14. Recent (2024–2026) Updates Worth Knowing

- **Yahoo Finance API changes (2024–2025)**: yfinance has had multiple breaking-then-patched cycles; pin a known-good version (`yfinance>=0.2.40`) and have a fallback to Stooq for index data.
- **IEX Cloud was discontinued in August 2024**; many tutorials reference it. Substitute Finnhub or Alpha Vantage. (Confirmed in vendor comparison content; flagged because legacy code samples still circulate.)
- **vectorbt** added a Rust kernel (PyO3) in 2024–2025; community edition still works but PRO is where new features land. Expect to occasionally pin versions.
- **LightGBM 4.x** introduced GPU support and refined categorical handling; safe to upgrade.
- **`edgartools`** matured significantly through 2024–2025 and is now the recommended free EDGAR library.
- **Streamlit Community Cloud** deprecated some background jobs in 2024 — schedule data refreshes via GitHub Actions, not in-app.
- The Walter Deemer "Breakaway Momentum" indicator triggered most recently in **January 2023** per Bravos Research; useful as a regime-confirmation context.
- **Anthropic's CLAUDE.md ecosystem** (rules files in `.claude/rules/`, `@import` syntax, AGENTS.md convergence with other agentic IDEs) stabilized in late 2025. Use it.

These notes are based on widely-cited secondary sources; verify rate limits and quotas at integration time as vendors change them frequently and not always with notice.

---

## 15. Prioritized Build Order (Suggested 6-Week Plan)

| Week | Deliverable |
|---|---|
| 1 | Repo skeleton, `pyproject`, ruff/mypy/pytest CI, OHLCV cache layer, universe builder, basic Streamlit shell with hardcoded ticker. |
| 2 | Indicators (SMAs, ATR, ADR%, RS percentile), Minervini Trend Template, regime module. First "today's watchlist" page. |
| 3 | VCP + flag pattern detection, Qullamaggie scan, composite scorer, GitHub Actions daily refresh. |
| 4 | vectorbt backtest harness, walk-forward, metrics, Backtest Lab page. **First honest backtest result with disclosed caveats.** |
| 5 | EDGAR insider/13F, Finnhub catalysts, FinBERT sentiment, Reddit buzz, ML feature pipeline, LightGBM model with calibration + SHAP. |
| 6 | Polish: dashboard pages 2–5, README + architecture diagram + screencast, `CLAUDE.md` final review, deploy to Streamlit Cloud, optional PySpark scan, optional dbt+duckdb modeling layer. |

If schedule slips, defer in this order: Cup-and-Handle → Reddit sentiment → PySpark → ML SHAP UI → dbt layer. The minimum impressive package is Weeks 1–4 with a deployed dashboard, an honest backtest, and a clean repo.

---

This document is the single source of truth for `CLAUDE.md` assembly. The shipping `CLAUDE.md` should be a *compressed* (≤ 300-line) extract — keep §13 (the cheat-sheet formulas), the §10 architecture rules, the §11.2 conventions, and the "Common pitfalls" list. Move the longer narrative content into `docs/methodology.md` and reference it via `@docs/methodology.md` for progressive disclosure.