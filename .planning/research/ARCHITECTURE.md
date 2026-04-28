# Architecture Research

**Domain:** Long-only EOD momentum swing-trading screener (personal-trading-first, daily Russell 1000 scan, markdown output, GitHub Actions cron orchestrator)
**Researched:** 2026-04-27
**Confidence:** HIGH (CLAUDE.md §10 prescribes the layout in detail; this document validates and tightens it for the v1 personal-trading scope)

## Standard Architecture

### System Overview

The pipeline is a one-way **DAG**, not a service. Every layer reads from disk artifacts produced by the previous layer; no module mutates state outside its own output directory. This is the single most important architectural property — it guarantees reproducibility, makes any stage independently re-runnable, and is the precondition for honest backtests.

```
┌────────────────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR  GitHub Actions cron (22:30 UTC weekdays) → src.cli      │
│               (typer commands: refresh-universe, refresh-ohlcv,       │
│                refresh-macro, score, report, journal)                 │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ invokes (in order)
┌──────────────────────────▼─────────────────────────────────────────────┐
│  EXTERNAL                                                              │
│  yfinance · Finnhub · FRED · Stooq · Wikipedia · iShares · EDGAR      │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │  HTTP/scrape (rate-limited, cached, retried)
┌──────────────────────────▼─────────────────────────────────────────────┐
│  DATA  (the only layer that does I/O against the network)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ universe │  │  ohlcv   │  │  macro   │  │  edgar   │  │  cache  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────────┘ │
└───────┼─────────────┼─────────────┼─────────────┼──────────────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼  (Parquet + SQLite on disk)
┌────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE  data/{ohlcv,universe,macro,edgar,rankings,journal}      │
│  Parquet partitioned by ticker · SQLite for transactional artifacts   │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │  pandas DataFrames in / DataFrames out
┌──────────────────────────▼─────────────────────────────────────────────┐
│  INDICATORS  (pure functions, no I/O, vectorized over the universe)   │
│  trend · relative_strength · volatility · volume · patterns           │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────┐
│  SIGNALS  (pure functions; consume indicator panel, emit boolean +    │
│  ┌──────────┐  ┌─────────────┐  ┌─────────┐   numeric per-ticker     │
│  │minervini │  │ qullamaggie │  │ canslim │  scores aligned by index)│
│  └──────────┘  └─────────────┘  └─────────┘                           │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │ regime · catalysts  │  (regime is universe-wide; catalysts per-ticker)
                └──────────┬──────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────┐
│  COMPOSITE SCORER  (single function: signals + regime → score 0-100   │
│  + per-row playbook tag ∈ {qullamaggie, minervini, leader_hold, none})│
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────┐
│  SIZING  (per-playbook entry/stop/size given ATR, ADR, regime)        │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
                  ┌────────▼────────┐
                  │   PUBLISHERS    │
                  ├─────────────────┤
                  │ report (.md)    │  ←  v1 user-facing output
                  │ journal (sqlite)│  ←  v2 ML training set
                  │ snapshot (parq) │  ←  ranking history for backtest
                  └────────┬────────┘
                           │
              ┌────────────▼────────────┐
              │ BACKTEST (offline only) │  reads snapshots + ohlcv
              │ vbt_runner · walkforward│  produces metrics, never reads
              │ metrics                 │  from publishers' transactional state
              └─────────────────────────┘
```

**Critical property:** every arrow points downward. There are no cycles. The backtest layer reads the same Parquet artifacts as the publishers; it does not call into `data/` or `signals/` over the network. This means a backtest can be reproduced from a frozen snapshot of `data/` without any API access.

### Component Responsibilities

| Component | Owns | Does NOT do |
|-----------|------|-------------|
| `cli` | Typer entry points, argument parsing, top-level orchestration of the DAG, exit codes for CI | Any business logic; calls only into the layers below |
| `config` | `pydantic-settings` typed config (env + YAML), single source of truth for thresholds and paths | Read/write artifacts; everything else imports `settings` |
| `data/universe` | Wikipedia / iShares CSV scrape → Parquet snapshot of ticker list with sector/industry; weekly snapshot for survivorship-mitigation | Compute indicators; filter for liquidity (that is `signals/qullamaggie`'s scan) |
| `data/ohlcv` | yfinance bulk fetch with Stooq fallback, per-ticker Parquet append, retry/backoff via tenacity, requests-cache for HTTP | Adjust for splits beyond what yfinance returns; emit indicators |
| `data/fundamentals` | Finnhub earnings, profile (`shareOutstanding`, sector); 45-day fundamentals lag enforced here | Score CANSLIM letters (that is `signals/canslim`) |
| `data/macro` | FRED (VIX, yields), SPY/QQQ OHLCV, NYSE A/D from Stooq, distribution-day raw inputs | Compute regime state (that is `regime`) |
| `data/edgar` | edgartools wrapper for Form 4 / 13F (deferred from v1 unless a phase explicitly pulls it in) | Score insider signals; that is `catalysts/insider` |
| `persistence` | Read/write helpers for Parquet (per-ticker partitioned) and SQLite (rankings, journal); schema enforcement via pandera | Make API calls; transform data |
| `indicators/trend` | SMA panels (10/20/50/150/200) and slope features; SMA200 22-day slope flag | Encode the 8-condition Trend Template gate (that is `signals/minervini`) |
| `indicators/relative_strength` | Quarter-weighted raw RS series + universe-relative percentile ranking on a given date | Cross-sectional ranking against any universe other than the one passed in |
| `indicators/volatility` | ATR(14) Wilder, ADR%(20), realized vol, BBand width | Position sizing (that is `sizing`) |
| `indicators/volume` | OBV, dryup ratio, pocket-pivot flag, 50-day up/down volume ratio | Make breakout calls |
| `indicators/patterns` | Pivot detection (`scipy.signal.argrelextrema`), VCP contraction enumeration, flag detection, returns per-ticker pattern feature record | Decide which pattern is the playbook (that's the composite scorer's playbook tagger) |
| `signals/minervini` | Boolean `passes_trend_template` + 0–8 `trend_template_score` from indicator panel | Read OHLCV directly; consume only indicator outputs |
| `signals/qullamaggie` | Setup A scan (top-1–2% momentum, ADV > $1.5M, ADR% ≥ 4) + continuation-flag detection wrapping `indicators/patterns` | Compute ATR/ADR (delegated to `indicators/volatility`) |
| `signals/canslim` | C+L+M letter computations (others optional); fundamental-quality overlay score | Be a hard gate; CANSLIM is additive scoring per CLAUDE.md §2.3 |
| `signals/composite` | Weighted score 0–100 + per-row playbook tag using priority rules (Qullamaggie continuation > Minervini VCP > leader-hold) | Position-size; that is `sizing` |
| `regime` | SPY trend gate, breadth %, distribution-day count, VIX → discrete state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction} + continuous `regime_score` ∈ [0,1] | Per-ticker filtering; it returns one row per date |
| `catalysts` | (v1: stub returning zeros) FinBERT sentiment, insider cluster-buy flags — deferred but the seam exists so M2 can plug in without refactor | News fetch (lives in `data/news` when added) |
| `sizing` | Per-playbook entry / stop / shares given ATR, ADR%, regime_score, account_equity; rejects trades where risk_per_share > 1×ADR | Touch the report; emits a DataFrame with sizing columns appended |
| `publishers/report` | Render a single Markdown file per session: regime stamp, top picks with playbook tag, entry/stop/size, "skipped because…" appendix | Persist anything (the snapshot publisher does that) |
| `publishers/journal` | Append every actionable pick to `journal.sqlite` with the schema that v2's ML pipeline will read | Track executed trades automatically — paper-trade outcomes are entered manually |
| `publishers/snapshot` | Write the ranking DataFrame as `rankings/YYYY-MM-DD.parquet` for historical reproducibility and backtest input | — |
| `backtest/vbt_runner` | vectorbt portfolio construction from cached snapshots + OHLCV | Make API calls; backtests run from disk |
| `backtest/walkforward` | Rolling IS/OOS windows, OOS Sharpe distribution | — |
| `backtest/metrics` | CAGR, Sharpe, Sortino, Calmar, profit factor, expectancy, exposure | — |

## Recommended Project Structure

```
momentum-screener/
├── src/screener/
│   ├── config.py                 # pydantic-settings; thresholds in YAML
│   ├── cli.py                    # typer: refresh-*, score, report, backtest
│   ├── data/                     # ONLY layer with network I/O
│   │   ├── universe.py           # Wikipedia + iShares + weekly snapshot
│   │   ├── ohlcv.py              # yfinance + Stooq fallback + Parquet cache
│   │   ├── fundamentals.py       # Finnhub (45-day lag enforced here)
│   │   ├── macro.py              # FRED + SPY + breadth inputs
│   │   └── edgar.py              # edgartools (deferred; stub seam in v1)
│   ├── persistence.py            # Parquet/SQLite helpers + pandera schemas
│   ├── indicators/               # Pure functions, no I/O
│   │   ├── trend.py
│   │   ├── relative_strength.py
│   │   ├── volatility.py
│   │   ├── volume.py
│   │   └── patterns.py
│   ├── signals/                  # Pure functions, consume indicator panel
│   │   ├── minervini.py
│   │   ├── qullamaggie.py
│   │   ├── canslim.py
│   │   └── composite.py          # score + playbook tag (THE extension point for ML)
│   ├── regime.py                 # Universe-wide; one row per date
│   ├── catalysts/                # v1: stub seam; v2 plug-in here
│   │   ├── sentiment.py          # placeholder
│   │   └── insider.py            # placeholder
│   ├── sizing.py                 # Per-playbook entry/stop/shares
│   ├── publishers/
│   │   ├── report.py             # Markdown renderer
│   │   ├── journal.py            # SQLite append (M2 ML reads from this)
│   │   └── snapshot.py           # Parquet snapshot of daily ranking
│   └── backtest/                 # Offline only; reads disk artifacts
│       ├── vbt_runner.py
│       ├── walkforward.py
│       └── metrics.py
├── data/                         # Gitignored locally; published artifacts go to data branch
│   ├── universe/YYYY-MM-DD.parquet      # Weekly snapshots
│   ├── ohlcv/{TICKER}.parquet           # One file per ticker, partitioned
│   ├── macro/{spy,vix,breadth}.parquet
│   ├── rankings/YYYY-MM-DD.parquet      # One per session (immutable)
│   ├── reports/YYYY-MM-DD.md            # One per session (the user-facing artifact)
│   └── journal.sqlite                   # Single transactional file
├── tests/
│   ├── conftest.py               # Synthetic OHLCV fixtures
│   ├── test_indicators.py
│   ├── test_signals.py
│   ├── test_regime.py
│   └── test_backtest_no_lookahead.py    # CRITICAL: see §13 of CLAUDE.md
├── .github/workflows/
│   ├── ci.yml                    # ruff + mypy + pytest on PR
│   └── refresh.yml               # nightly cron orchestrator
├── pyproject.toml
├── Makefile                      # make data / make rank / make report / make backtest
├── CLAUDE.md
└── README.md
```

### Structure Rationale

- **`data/` is the only layer permitted to make network calls.** Every other module receives DataFrames. This is the rule that makes backtests reproducible and tests fast — you can fixture a synthetic OHLCV DataFrame and run the entire `indicators → signals → composite → sizing → publishers` chain offline.
- **`signals/` consumes only indicator outputs, never raw OHLCV.** This forces indicators to be the right level of abstraction. If `signals/qullamaggie.py` finds itself computing rolling means, that's a smell — push it into `indicators/`.
- **`regime.py` lives at the package root, not inside `signals/`.** Regime is a one-row-per-date series that scales the whole portfolio's risk; it isn't a per-ticker signal. Putting it at the root prevents the temptation to compute it per ticker and re-aggregate.
- **`composite.py` is the single function that emits the score and the playbook tag.** Both v1 (rules-only) and v2 (rules + ML probability) write into this module. Keeping the playbook-tagger and the score-combiner co-located prevents the v2 split where ML probability and rules-based playbook drift apart.
- **`publishers/` is a thin layer.** Each publisher is essentially a `(ranked_df) -> file_artifact` function. This is the seam where Streamlit (M2) plugs in: `publishers/dashboard.py` will be a sibling of `report.py`, reading the same `rankings/*.parquet` snapshots, never re-running scoring.
- **`catalysts/` exists in v1 as stub seams** even though FinBERT and Reddit are deferred. The seam is cheap and prevents a refactor when M2 adds them.
- **`backtest/` is a sibling of the live pipeline, not a wrapper around it.** It reads `data/ohlcv/*.parquet` and `data/rankings/*.parquet` and never imports from `publishers/`. This is the only way the no-look-ahead test can be honest — backtest cannot accidentally call live-pipeline code that has access to "future" data.

## Architectural Patterns

### Pattern 1: One-Way DAG with Disk Hand-off Between Stages

**What:** Each pipeline stage reads its inputs from disk artifacts, computes, and writes its output to disk. Stages don't call each other in-process unless they share a parent CLI command.

**When to use:** Always for this project. EOD pipelines have hours of slack between stages; cheap I/O cost buys reproducibility, debuggability, and CI-friendliness.

**Trade-offs:**
- Pro: Any stage is independently re-runnable from yesterday's artifacts. CI can fixture stage N's input and assert on stage N's output without running stages 1..N-1.
- Pro: A failed run halfway through is recoverable — you don't have to re-fetch the universe to re-run scoring.
- Con: Slightly more disk I/O than an in-process pipeline. Irrelevant at Russell-1000 scale.

**Example:**
```python
# src/screener/cli.py
import typer
from screener import data, indicators, signals, regime, sizing, publishers

app = typer.Typer()

@app.command("refresh-ohlcv")
def refresh_ohlcv() -> None:
    universe = data.universe.load_latest()       # reads data/universe/*.parquet
    data.ohlcv.refresh(universe.ticker.tolist()) # writes data/ohlcv/*.parquet

@app.command("score")
def score() -> None:
    universe = data.universe.load_latest()
    px = data.ohlcv.load_panel(universe.ticker.tolist())   # reads from disk
    ind = indicators.build_panel(px)                       # pure function
    sig = signals.evaluate_all(ind)                        # pure function
    reg = regime.compute(data.macro.load_latest())         # pure function
    ranked = signals.composite.score(sig, reg)             # pure function
    ranked = sizing.apply(ranked, ind)                     # pure function
    publishers.snapshot.write(ranked)                      # writes data/rankings/
    publishers.report.write(ranked, reg)                   # writes data/reports/
    publishers.journal.append_actionable(ranked, reg)      # writes data/journal.sqlite
```

### Pattern 2: Pure-Function Discipline Inside `indicators/` and `signals/`

**What:** Every function in `indicators/` and `signals/` takes pandas DataFrames in, returns DataFrames with identical index. No file I/O, no logging-to-disk, no global state, no clock reads.

**When to use:** Strictly enforced for these two layers. The layers above (`data/`) and below (`publishers/`, `cli`) are I/O layers; the middle is pure.

**Trade-offs:**
- Pro: Property-based testing is trivial. Hypothesis fixtures generate synthetic OHLCV; assertions check shape, monotonicity, no-NaN-explosions.
- Pro: Vectorbt parameter sweeps for backtest weight optimization run inside a single process — no subprocess fork needed, since all signal code is referentially transparent.
- Pro: Look-ahead bugs become structurally impossible — there's no "live data" object the function can accidentally consult.
- Con: Performance-sensitive code (pattern detection over 1,000 tickers) must be vectorized or it's slow. Acceptable at Russell-1000 EOD scale.

**Example:**
```python
# src/screener/signals/minervini.py
import pandas as pd

def passes_trend_template(ind: pd.DataFrame) -> pd.DataFrame:
    """ind has columns: close, sma50, sma150, sma200, sma200_22d_ago,
                       low_252, high_252, rs_rating. One row per (ticker, date).
       Returns DataFrame with columns: passes, score (0-8), aligned to ind.index.
    """
    cond = pd.DataFrame(index=ind.index)
    cond["c1"] = (ind.close > ind.sma150) & (ind.close > ind.sma200)
    cond["c2"] = ind.sma150 > ind.sma200
    cond["c3"] = ind.sma200 > ind.sma200_22d_ago
    cond["c4"] = (ind.sma50 > ind.sma150) & (ind.sma50 > ind.sma200)
    cond["c5"] = ind.close > ind.sma50
    cond["c6"] = ind.close >= 1.30 * ind.low_252
    cond["c7"] = ind.close >= 0.75 * ind.high_252
    cond["c8"] = ind.rs_rating >= 70
    return pd.DataFrame({
        "passes": cond.all(axis=1),
        "score":  cond.sum(axis=1).astype("int8"),
    }, index=ind.index)
```

### Pattern 3: Composite Scorer as the Single Extension Point for ML

**What:** v1's composite scorer is a weighted sum of signal columns. v2's scorer is the same function with one additional column — `ml_probability` — added to the weighted sum. The signature, the inputs, the playbook tagger, and the output schema are unchanged.

**When to use:** This is the v1 architectural decision that determines whether M2 is a clean addition or a rewrite. Get it right once.

**Trade-offs:**
- Pro: M2 adds `screener/ml/predict.py` (new file), updates `composite.py` to read its output (one-line change), and trains from `journal.sqlite` (zero coupling — the journal schema is already stable).
- Pro: The playbook tagger (which decides Qullamaggie vs. Minervini vs. leader-hold) lives next to the scorer; v2 doesn't accidentally reroute picks through ML probability and lose the playbook tag.
- Con: Requires writing the scorer signature with the v2 case in mind. Concretely: take a DataFrame of feature columns + a dict of weights, not hardcoded column references.

**Example:**
```python
# src/screener/signals/composite.py
import pandas as pd
from screener.config import settings

# v1 columns; v2 will add "ml_probability"
DEFAULT_WEIGHTS = {
    "rs_pct":           0.25,
    "trend_score_norm": 0.20,
    "pattern_score":    0.20,
    "volume_conf":      0.10,
    "earnings_mom":     0.15,
    "catalyst_score":   0.10,
}

def score(features: pd.DataFrame, regime_score: float,
          weights: dict[str, float] | None = None) -> pd.DataFrame:
    w = weights or settings.composite_weights or DEFAULT_WEIGHTS
    cols = [c for c in w if c in features.columns]
    raw = sum(features[c].fillna(0) * w[c] for c in cols)
    out = features.copy()
    out["composite_score"] = (raw * regime_score * 100).clip(0, 100)
    out["playbook"] = _tag_playbook(features)  # qullamaggie / minervini / leader_hold / none
    return out

def _tag_playbook(features: pd.DataFrame) -> pd.Series:
    """Priority: Qullamaggie continuation > Minervini VCP > leader-hold > none."""
    ...
```
**M2 diff:** add `"ml_probability": 0.20` to weights, rebalance others, ensure `features` arrives with the new column populated by `screener/ml/predict.py`. No other module changes.

### Pattern 4: Append-Only Journal as the Stable ML Training Schema

**What:** `journal.sqlite` has a fixed schema written from day one with the columns v2's LightGBM model will need: every actionable pick at publication time + every feature value at that timestamp + a nullable `outcome` block populated later by manual paper-trade entry.

**When to use:** Set this schema at the start of v1 and treat it as a contract. Migrations are allowed (`alembic` or hand-rolled), but column semantics must not silently change.

**Trade-offs:**
- Pro: M2 ML training is `SELECT * FROM picks JOIN outcomes ON pick_id` — zero coupling to live pipeline code.
- Pro: Backfilling labels (paper-trade entry) is decoupled from prediction time — the outcome columns are nullable and updated weeks later when the trade closes.
- Con: Schema design must anticipate ML feature needs. Solution: dump the entire feature-row DataFrame as a JSON blob column (`features_json`) alongside structured columns for the most-used ones. ML training parses the JSON; manual journaling reads the structured columns.

**Example schema:**
```sql
CREATE TABLE picks (
    pick_id          INTEGER PRIMARY KEY,
    session_date     DATE NOT NULL,           -- the EOD date the pick was generated
    ticker           TEXT NOT NULL,
    playbook         TEXT NOT NULL,           -- qullamaggie | minervini | leader_hold
    composite_score  REAL NOT NULL,
    regime_state     TEXT NOT NULL,
    regime_score     REAL NOT NULL,
    entry_price      REAL NOT NULL,
    stop_price       REAL NOT NULL,
    suggested_shares INTEGER NOT NULL,
    adr_pct          REAL,
    rs_rating        INTEGER,
    features_json    TEXT NOT NULL,           -- full feature row, future-proofs ML training
    UNIQUE (session_date, ticker)
);

CREATE TABLE outcomes (
    pick_id          INTEGER PRIMARY KEY REFERENCES picks(pick_id),
    entry_filled     BOOLEAN,
    actual_entry     REAL,
    actual_exit      REAL,
    exit_date        DATE,
    exit_reason      TEXT,                    -- stop | trail_break | discretionary | not_taken
    pnl_pct          REAL,
    notes            TEXT
);
```

### Pattern 5: Schema Enforcement at I/O Boundaries Only

**What:** `pandera` schemas validate DataFrames as they cross between layers (specifically: `data/ → indicators/`, `composite → publishers/`). Inside a layer, no validation overhead.

**When to use:** Apply at the two boundaries above. Skip elsewhere — over-validation slows the loop.

**Trade-offs:**
- Pro: Schema drift (e.g., yfinance changes a column name) fails loud at the layer boundary, not silently in pattern detection 200ms later.
- Con: Pandera adds startup cost; mitigate by validating on the daily run only, not in unit tests (use lighter assertions there).

## Data Flow

### Nightly Pipeline (the v1 hot path)

```
22:30 UTC  GitHub Actions cron trigger
   │
   ├─► refresh-universe         (Mondays only, weekly snapshot)
   │      Wikipedia + iShares CSV → data/universe/YYYY-MM-DD.parquet
   │
   ├─► refresh-macro
   │      FRED (VIX, yields) + Stooq (SPY, A/D) → data/macro/*.parquet
   │
   ├─► refresh-ohlcv             (incremental; appends only the latest bar)
   │      For each ticker in latest universe:
   │        if data/ohlcv/{T}.parquet exists: append new bars since last
   │        else: full backfill
   │      yfinance bulk fetch with tenacity retry; Stooq fallback on 429
   │
   ├─► refresh-fundamentals      (Finnhub; lag-aware)
   │      Earnings, profile → data/fundamentals/*.parquet
   │
   ├─► score
   │      Load OHLCV panel + macro → indicators.build_panel
   │        → signals.evaluate_all (minervini, qullamaggie, canslim)
   │        → regime.compute
   │        → signals.composite.score (weighted sum + playbook tag)
   │        → sizing.apply (entry, stop, shares per playbook)
   │      Write data/rankings/YYYY-MM-DD.parquet
   │
   ├─► report
   │      Render data/rankings/YYYY-MM-DD.parquet → data/reports/YYYY-MM-DD.md
   │      (regime banner, top picks with playbook tag and trade plan,
   │       skipped-because appendix, distribution-day count, VIX)
   │
   ├─► journal
   │      Append actionable picks (composite ≥ threshold AND regime allows new entries)
   │      to data/journal.sqlite picks table
   │
   └─► commit-artifacts
          git add data/reports data/rankings data/journal.sqlite data/universe
          git commit -m "data: nightly refresh"
          git push
```

**Direction property:** every step depends only on artifacts produced earlier in the same run, or on artifacts committed by previous runs. There are no in-process dependencies between stages — `score` could be re-run tomorrow morning by hand against last night's `data/ohlcv/` and produce a bit-identical `rankings/` Parquet. This is the test of architectural correctness.

### Backtest Flow (offline, separate hot path)

```
Developer runs `make backtest`
   │
   ├─► Load data/ohlcv/*.parquet (a frozen historical panel)
   │
   ├─► Optionally load data/rankings/*.parquet  ← if testing the live scorer's history
   │   OR re-run scorer over historical OHLCV  ← if testing a candidate weight set
   │
   ├─► vectorbt.Portfolio.from_signals
   │      entries  = composite_score >= threshold AND regime_allows
   │      exits    = close < trail_ma OR breached_stop
   │      sl_stop  = ATR-based
   │      fees     = 5 bps
   │      slippage = 10 bps (25 bps for ADV < $5M)
   │
   └─► Walk-forward: rolling 3-yr IS / 1-yr OOS windows
       Output: OOS Sharpe distribution, equity curve, drawdown, trade list
```

**Critical:** the backtest never imports from `publishers/` and never makes network calls. It reads the same Parquet files the live pipeline reads. The no-look-ahead test (`tests/test_backtest_no_lookahead.py`) constructs a synthetic signal equal to next-day return; if shifted-by-one-bar correctly, the backtest cannot be profitable. If it is, there's a leakage bug.

### State Management

There is **no in-memory state** between CLI invocations. State lives in three places only:

```
Disk artifacts (the source of truth)
   ├── data/ohlcv/*.parquet           append-only per ticker
   ├── data/universe/*.parquet        weekly snapshots, immutable once written
   ├── data/macro/*.parquet           daily snapshots
   ├── data/rankings/*.parquet        per-session, immutable once written
   ├── data/reports/*.md              per-session, immutable
   └── data/journal.sqlite            transactional: picks append, outcomes update
```

All other "state" (current regime, top picks, etc.) is derived by re-running the pipeline against these artifacts. This is the property that lets backtests be honest.

### Key Data Flows

1. **Universe → OHLCV:** Universe snapshot drives which tickers get fetched. Adding a ticker to the universe on Monday triggers full backfill the next refresh; removing a ticker leaves its Parquet behind (graceful degradation, useful for survivorship-aware future analysis).
2. **OHLCV → Indicator Panel:** A single function, `indicators.build_panel(ohlcv_panel) → indicator_panel`, returns one wide DataFrame with all features for all tickers. Downstream signals consume this; never raw OHLCV.
3. **Indicator Panel → Signals → Composite:** Each signal module is a pure function producing one or more columns aligned to the indicator panel's index. Composite scorer concatenates and weights.
4. **Composite + Sizing → Publishers:** Three publishers fan out from the same ranked DataFrame: report (Markdown), snapshot (Parquet, for backtest), journal (SQLite, for ML).
5. **Journal → ML Training (M2):** v2's ML pipeline reads `journal.sqlite` directly; it does not call into the live pipeline. Outcomes are populated manually as paper trades close.

## Build Order with Dependencies

The natural phase order falls out of the DAG. Each phase delivers an end-to-end thin slice — a runnable CLI command that produces a real artifact — rather than a horizontal layer.

| Phase | Delivers | Hard Dependencies | Why this order |
|-------|----------|------------------|----------------|
| **P0 Skeleton** | `pyproject.toml`, `cli.py` typer skeleton, `config.py` pydantic-settings, ruff/mypy/pytest in CI, Makefile | none | Engineering hygiene first; reduces friction in every later phase |
| **P1 Data foundation** | `data/universe.py`, `data/ohlcv.py` with Parquet cache, `persistence.py` with pandera schemas, weekly universe snapshot | P0 | Everything downstream needs OHLCV; no signals without data |
| **P2 Indicator panel** | `indicators/{trend,relative_strength,volatility,volume}.py`, `indicators.build_panel()` | P1 | RS percentile is universe-relative — must run over the full universe at once, which forces the panel pattern early |
| **P3 Trend Template + Regime** | `signals/minervini.py`, `regime.py`, `data/macro.py` | P2 | Minervini gate is the simplest end-to-end signal; regime is a small universe-wide series. Ship a `score` command that produces a Parquet of trend-passers |
| **P4 First Markdown report** | `publishers/report.py`, `publishers/snapshot.py`, `cli report` | P3 | First user-facing artifact; closes the loop and validates the DAG end-to-end before adding pattern complexity |
| **P5 Pattern detection** | `indicators/patterns.py` (VCP + flag), `signals/qullamaggie.py` (Setup A scan + continuation flag), `signals/composite.py` weighted score + playbook tagger | P4 | This is the longest phase; defer until the simpler pipeline proves the architecture works |
| **P6 Sizing + Journal** | `sizing.py`, `publishers/journal.py`, journal schema frozen | P5 | Sizing requires playbook tag (P5). Journal requires sizing (entry/stop/shares are journaled). Schema-first because it's the v2 ML contract |
| **P7 GitHub Actions cron** | `.github/workflows/refresh.yml`, commit-artifacts step | P6 | Productionalize once everything works locally |
| **P8 Backtest harness** | `backtest/{vbt_runner,walkforward,metrics}.py`, `tests/test_backtest_no_lookahead.py` | P5 (needs ranked snapshots) | Can be parallelized with P6/P7 because it reads from disk artifacts only |
| **P9 CANSLIM overlay + Catalysts stubs** | `signals/canslim.py`, `data/fundamentals.py`, empty `catalysts/` modules | P5 | Additive scoring, not a gate; can ship after the core works |

**Key dependency observations:**

- **RS percentile forces the panel pattern early.** You cannot compute IBD-style RS percentile per ticker independently — it's a cross-sectional rank across the universe on a date. This means `indicators/relative_strength.py` must operate on a multi-ticker DataFrame from day one, which sets the convention for every other indicator (panel in, panel out). Discovering this in P2 saves a refactor in P5.
- **Playbook tagger must exist before sizing.** Sizing rules differ by playbook (Qullamaggie: stop = entry-day low, risk ≤ 1×ADR; Minervini VCP: stop = pivot - X% or below most-recent-contraction low). If sizing is built before tagging, it gets a mess of conditionals; if tagging produces the playbook column first, sizing dispatches cleanly.
- **Journal schema is frozen at P6 and treated as a contract.** Changing it later forces ML retraining migrations. Spend the time at P6 to enumerate every column M2 will want, including the `features_json` blob.
- **GitHub Actions cron is last in v1, not first.** Run the pipeline locally end-to-end before scheduling it. CI scheduling is the easy part; the hard part is making the pipeline robust to yfinance 429s and Finnhub quota exhaustion.

## M2 Extension Points

The v1 architecture must not block M2. The three known M2 additions are LightGBM ML probability scoring, FinBERT/Reddit catalyst signals, and the Streamlit dashboard. Each plugs in at a designated seam.

| M2 feature | Seam | What v1 must do | What v2 adds |
|------------|------|-----------------|--------------|
| **LightGBM ML probability** | `signals/composite.py` (weights dict) + `journal.sqlite` (training data) | Make composite scorer take a weights dict that can include arbitrary feature columns; freeze journal schema with full `features_json` blob from day one | New module `screener/ml/{features,train,predict}.py`. `predict.py` reads the indicator panel, emits an `ml_probability` column. Composite scorer adds a weight for it. Zero changes to `data/`, `indicators/`, `signals/{minervini,qullamaggie,canslim}`, `regime`, `sizing`, `publishers`. |
| **FinBERT sentiment + Reddit buzz** | `catalysts/sentiment.py` and `catalysts/insider.py` (stub seams in v1) | Keep stub modules in v1 returning zero-filled DataFrames with the column names M2 will populate (`finbert_score`, `social_buzz_z`, etc.). Composite scorer's `catalyst_score` weight is already wired | Implement the stubs against `data/news.py` (new) and `data/reddit.py` (new). FinBERT runs locally on CPU; one new pipeline stage `refresh-news` between `refresh-fundamentals` and `score`. |
| **Streamlit dashboard** | `publishers/` directory | Snapshot publisher writes ranking history as Parquet from day one; report publisher's data is reproducible from the same snapshot | New module `app/streamlit_app.py` reads `data/rankings/*.parquet`, `data/reports/*.md`, `data/ohlcv/*.parquet` directly. Dashboard does NOT call into the live pipeline — it visualizes already-computed artifacts. This is what makes Streamlit Cloud deployment trivial: no API keys, no heavy compute in-app. |
| **Setup B (Episodic Pivot) D+1 detection** | `signals/qullamaggie.py` (additional setup function) | Setup A function exists; signature accepts indicator panel | Add `detect_setup_b(ind)` returning a parallel boolean column. Composite scorer treats it as another playbook tag. |
| **Cup-and-handle pattern** | `indicators/patterns.py` | Pivot-detection helper is shared infrastructure | Add `detect_cup_handle(prices)` alongside `detect_vcp` and `detect_flag`. New playbook tag value. |
| **Real-broker integration (out of scope but mentioned)** | `publishers/` or new `execution/` sibling | Journal schema captures suggested entry/stop/size already; an executor reads pending picks | Keep all order placement out of the daily-pipeline DAG; it should be a separate, independently-failing job that consumes the published artifact. |

**The architectural contract for M2:** any new feature is added by (a) creating a new module that reads existing Parquet/SQLite artifacts, or (b) adding a column-emitting pure function to `indicators/`, `signals/`, or `catalysts/`, plus a one-line wiring change in `composite.py`. Anything more invasive indicates an architectural problem in v1.

## Scaling Considerations

This is a personal-trading tool against the Russell 1000 (~1,000 tickers). Real-world scale:

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Russell 1000 (v1 target)** | Pandas DataFrame in-memory is fine. Per-ticker Parquet files. Sequential yfinance fetch with 0.5–1.5s jitter is ~15–25 minutes nightly. |
| **Russell 3000** | Indicator panel still fits in memory (~2GB RAM for 5 years of daily OHLCV × 60 features × 3000 tickers). Bottleneck is yfinance fetch — switch to bulk download in batches of 100. |
| **Full US equities (~8000 names)** | Indicator panel in memory becomes tight. Switch to chunked computation (compute indicators per sector). yfinance is no longer adequate; would force the $0 budget rule to break. |

**The user is explicitly choosing Russell 1000.** Do not over-engineer for scale that is out of scope. The PySpark variant mentioned in CLAUDE.md §10.1 was cut from v1 in PROJECT.md; do not build it speculatively.

### Scaling Priorities (real bottlenecks at v1 scale)

1. **First bottleneck: yfinance rate limiting and stability.** Mitigation: aggressive Parquet caching (already specified), tenacity retry with exponential backoff, Stooq fallback for index data, randomized delays between tickers, never run faster than once per second per ticker. This is the operational risk that will most often fail the nightly job.
2. **Second bottleneck: pattern detection over 1,000 tickers.** Mitigation: vectorize the pivot detection — run `argrelextrema` once per ticker but enumerate contractions in pure NumPy. If this becomes slow (> 5 minutes), profile before optimizing; do not pre-optimize.
3. **Third bottleneck: vectorbt parameter sweeps.** Mitigation: cache OHLCV panels in memory across sweep iterations; vectorbt's vectorized portfolio construction handles thousands of parameter combinations natively.

## Anti-Patterns

### Anti-Pattern 1: I/O leaking into `signals/`

**What people do:** A `signals/qullamaggie.py` function that calls `data.ohlcv.load_panel(...)` directly because "it needs fresh data."
**Why it's wrong:** Breaks pure-function discipline, makes signals untestable without network access, makes backtests potentially leak future data through accidental fresh fetches, and corrupts the DAG (a downstream layer reaching back upstream).
**Do this instead:** The CLI passes the already-loaded panel into the signal function. The signal function is `f(DataFrame) → DataFrame`. If a signal needs new data, it's because an indicator is missing — push the requirement into `indicators/`, not into `signals/`.

### Anti-Pattern 2: Per-ticker loops in the scorer

**What people do:** `for ticker in universe: df = compute_indicators(ohlcv[ticker]); score = score_one(df)`.
**Why it's wrong:** RS percentile is cross-sectional — it cannot be computed per ticker. As soon as one feature requires the full universe to be in memory at once, the per-ticker loop pattern collapses and forces a refactor. Also: per-ticker loops are 100× slower than the panel pattern at Russell-1000 scale.
**Do this instead:** From P2 onward, indicator and signal functions take a multi-ticker DataFrame (either long format with a `ticker` column or wide format with a MultiIndex column) and return DataFrames of identical shape.

### Anti-Pattern 3: Look-ahead via current-bar entries

**What people do:** Backtest enters at close of bar `t` when signal fires at close of bar `t`.
**Why it's wrong:** In live trading you cannot see today's close before the close. Doing this silently inflates Sharpe by 0.3–1.0 in momentum strategies because the close-bar already contains the breakout move.
**Do this instead:** Convention: signals at bar `t` execute at the open of bar `t+1`. Enforced in the backtest harness via `vectorbt.Portfolio.from_signals(..., price='open')` with explicit signal shift, and verified by `tests/test_backtest_no_lookahead.py` which constructs a "perfect-foresight" signal and asserts the strategy is unprofitable when the shift is correct.

### Anti-Pattern 4: ML probability replacing the rules-based score in v2

**What people do:** v2 ships, ML probability is high, the developer rewrites composite.py to "just use ML probability" and removes the rules-based components.
**Why it's wrong:** The v1 rules-based score is interpretable; every component is auditable. ML probability is not. PROJECT.md is explicit: "v1's confidence number is the rule-based composite. It is interpretable by construction." The user trades from explainable signals; ML layers on top.
**Do this instead:** v2's composite is `0.20 * ml_probability + 0.80 * rules_components` (weights tunable). Both must remain in `composite.py`, both must be visible in the report, and the playbook tagger continues to use rules — not ML — to assign the playbook because playbook assignment must be explainable to the trader at the moment of review.

### Anti-Pattern 5: Streamlit calling the live pipeline at request time

**What people do:** M2's dashboard, on page load, calls `score()` and waits 30 seconds.
**Why it's wrong:** Streamlit Cloud's free runner has limited memory and cold-start latency; running the full pipeline per-request is a broken UX, and worse, would require the dashboard to have API keys for every data source. It also makes "what does the dashboard show?" non-deterministic.
**Do this instead:** Dashboard is a pure read-side: it loads `data/rankings/YYYY-MM-DD.parquet` and `data/reports/YYYY-MM-DD.md` from the repo or a deployed artifact bucket. The pipeline runs nightly via GitHub Actions cron and commits artifacts; the dashboard reads them. Build the pipeline and the dashboard as separate services that share a disk format.

### Anti-Pattern 6: Schema drift in the journal

**What people do:** v1 ships, then over time someone adds a new column to the journal `picks` table without a migration, or renames `composite_score` → `score`.
**Why it's wrong:** v2's ML training reads this table. Schema drift silently corrupts the training set, and labels become misaligned with features for old picks. The model trains on garbage and the ML probability score is worse than the rules-based score.
**Do this instead:** Treat `journal.sqlite` schema as a contract. Use Alembic migrations or a hand-rolled `migrations/` directory. Every column change ships with a migration that backfills or marks old rows null. Document the schema in `docs/journal_schema.md` and reference it from CLAUDE.md.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| yfinance | Bulk download in batches; retry/backoff with tenacity; Stooq fallback for index data | Most fragile dependency. Pin `yfinance>=0.2.40`. Cache aggressively; never re-fetch what's on disk. |
| Finnhub | requests-cache 1-hour expiry on intraday endpoints, 24h on fundamentals; respect 60 calls/min | API key in env. Used for earnings calendar, profile, sector. |
| FRED | `fredapi` with API key, generous quota | VIX, Treasury yields. Daily refresh sufficient. |
| Stooq | EOD CSV download, no key | SPY/QQQ index history, NYSE A/D line. Backup for yfinance index data. |
| Wikipedia / iShares | Weekly `pd.read_html` scrape | Universe construction. Snapshot to Parquet so a future Wikipedia structure change doesn't break a re-run of last week's job. |
| EDGAR (deferred) | edgartools with required identity header | v1 stub seam in `data/edgar.py` returning empty DataFrames; v2 wires it up. |
| GitHub Actions | yaml workflow, `stefanzweifel/git-auto-commit-action@v5` to commit artifacts | The orchestrator. Free tier is unlimited for public repos. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `cli` → all layers | Function calls, top-down only | Only the CLI orchestrates; no module calls another's CLI command. |
| `data/` ↔ network | HTTP via requests/yfinance/etc. | The only place network I/O is permitted. |
| `data/` → `persistence.py` → disk | Parquet/SQLite, schema-validated via pandera | Every artifact write goes through `persistence.py` so paths and partitioning are centralized. |
| `persistence.py` → `indicators/` → `signals/` | DataFrames in memory | Pure functional chain. No I/O. No globals. |
| `signals/composite.py` → `sizing.py` → `publishers/` | DataFrames in memory | Composite emits the score + playbook; sizing appends entry/stop/shares; publishers fan out. |
| `publishers/snapshot.py` → disk → `backtest/` | Parquet ranking snapshots | This disk hand-off is what makes the backtest reproducible from frozen artifacts. |
| `journal.sqlite` → M2 ML | SQL `SELECT` only; no writes from ML side | Append-only contract from v1. Outcomes are updated by manual journaling, not by the live pipeline. |
| `publishers/` → M2 Streamlit | Read-only file access to `data/reports/`, `data/rankings/`, `data/ohlcv/` | Dashboard is a sibling of the report publisher, not a wrapper around the pipeline. |

## Sources

- `/Users/belwinjulian/Desktop/SwingTrading/CLAUDE.md` §5 (data sourcing), §6 (backtest), §8 (deployment), §10 (architecture and code quality), §13 (cheat-sheet formulas)
- `/Users/belwinjulian/Desktop/SwingTrading/.planning/PROJECT.md` (v1 scope, out-of-scope items, M2 deferrals, key decisions)
- vectorbt community-edition documentation (Portfolio.from_signals, parameter sweeps) — referenced via CLAUDE.md §6
- pandas-ta documentation patterns — referenced via CLAUDE.md §3.1
- pandera schema-validation patterns at I/O boundaries — referenced via CLAUDE.md §8.3 #3
- Established Python packaging conventions for typer-based CLIs and pydantic-settings configuration

---
*Architecture research for: long-only EOD momentum swing-trading screener, personal-trading-first*
*Researched: 2026-04-27*
