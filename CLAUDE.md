# Momentum Swing Screener — Claude Context

## CLAUDE.md Maintenance Rule
- This file must stay under 35k characters (buffer below the 40k warning)
- Completed phase plans → archive to docs/phase-history.md
- New reference material → goes to docs/, not inline here
- After every phase completion, run: `wc -c CLAUDE.md` and trim if needed
- **Before starting Phase N work:** run `wc -c CLAUDE.md` — if over 35k, move completed phase details to `docs/phase-history.md` first, then proceed. Keep any context still relevant to upcoming phases (e.g. architectural decisions, constraints, signal formulas still in use).

**Stack:** Python 3.11 · pandas-ta-classic · vectorbt 1.0 · yfinance ≥1.3.0 · GitHub Actions cron · (M2: Streamlit)
**Universe:** Russell 1000 · EOD data only · $0/month hard constraint · paper-trade before real money
  37
## Commands

```
make data          # full OHLCV refresh (yfinance → Parquet cache)
make rank          # score + rank universe → Markdown report
make backtest      # vectorbt walk-forward
make app           # streamlit run app/streamlit_app.py

pytest                                            # full test suite
pytest tests/test_backtest_no_lookahead.py        # run after ANY signals/ or backtest/ change
ruff check src/                                   # lint
mypy src/screener/indicators/ src/screener/signals/  # type-check math modules
```

## Repository Layout

```
src/screener/
  config.py           # pydantic-settings — single source of truth for all params
  universe.py         # Russell 1000 construction
  data/               # ALL external I/O lives here (ohlcv, fundamentals, news, edgar, macro)
  indicators/         # trend.py · relative_strength.py · volatility.py · volume.py · patterns.py
  signals/            # minervini.py · qullamaggie.py · canslim.py · composite.py
  regime.py           # market regime score + state
  catalysts/          # sentiment.py (FinBERT) · insider.py (EDGAR Form 4)
  ml/                 # features.py · train.py (LightGBM) · predict.py
  backtest/           # vbt_runner.py · walkforward.py · metrics.py
  sizing.py           # position sizing + stop rules
  persistence.py      # Parquet + SQLite I/O
  cli.py              # typer CLI: refresh / rank / train / backtest
app/pages/            # Streamlit pages (M2)
tests/                # indicators · signals · regime · no-lookahead (critical)
docs/                 # extracted reference docs — see Documentation Index below
```

## Library Quick-Reference

| Library | Version | Purpose |
|---------|---------|---------|
| pandas-ta-classic | 0.4.47 | Indicators — SMA, ATR, ADR%, OBV, BBands. Pure Python, no C deps. |
| vectorbt | 1.0.x | Vectorized backtest + walk-forward (Apache 2 + Commons Clause — not MIT). |
| yfinance | ≥1.3.0 | Primary OHLCV — one ticker at a time, throttled, cached to Parquet. |
| edgartools | 5.30.x | Form 4 insider + 13F — call `set_identity(...)` at startup. |
| finnhub-python | 2.4.28 | News, earnings calendar, analyst upgrades. 60 calls/min free. |
| pandera | 0.31.1 | DataFrame schema validation at every IO boundary. |
| pydantic-settings | 2.14.x | Typed env/config (`Settings` class, `.env` file). |
| structlog | 25.5.x | JSON logging — no `print()` anywhere. |
| lightgbm | 4.x | ML model (M2+). |

**Never use:** original `pandas-ta` (PyPI, unmaintained), Alpha Vantage as primary (~25 calls/day), IEX Cloud (shut down Aug 2024), TA-Lib C (fails on Streamlit Cloud), yfinance batch download without throttle.

## Coding Conventions

- Python 3.11+. Type hints required in `signals/` and `indicators/`. Looser in `data/` and `app/`.
- Pure functions in `signals/` and `indicators/` — no side effects, no I/O.
- All external API calls go through `data/` modules. Never call yfinance or Finnhub from `signals/`.
- No `print()` anywhere — use `structlog`.
- No global mutable state in modules.
- `mypy --strict` on `indicators/` and `signals/`. Per-module overrides OK elsewhere.
- `ruff check` + `ruff format` before every commit (pre-commit hook).
- Prefer `uv add` over `pip install` — lockfile goes in git.

## Architectural Rules

- Signals consume DataFrames, return DataFrames of identical index. No shape surprises.
- Entry signals computed at bar `t` execute at open of bar `t+1`. **Never same-bar execution.**
- Fundamentals lag 45 days after fiscal-quarter end before being treated as known.
- Parquet on disk for OHLCV (partitioned by ticker); `requests-cache` SQLite for HTTP APIs.
- Every IO boundary validates with a `pandera` schema.

## Testing Rules

- **YOU MUST run `pytest tests/test_backtest_no_lookahead.py` after any change to `signals/` or `backtest/`.**
- Indicator tests: deterministic inputs → known outputs (compare to TA-Lib reference within 1e-6).
- Regime tests: 2008, 2020-Q1, 2022 must each classify as Correction at some point.

## Signal Formulas — Quick-Reference

**Minervini Trend Template (all 8 must pass; use SMA not EMA):**
```
1. Close > SMA150 AND Close > SMA200
2. SMA150 > SMA200
3. SMA200 > SMA200[t-22]          # rising at least 1 month
4. SMA50 > SMA150 AND SMA50 > SMA200
5. Close > SMA50
6. Close >= 1.30 * MIN(Low, 252)  # 30% above 52-wk low
7. Close >= 0.75 * MAX(High, 252) # within 25% of 52-wk high
8. RS_Rating >= 70
```
Produce `passes_trend_template` (bool) AND `trend_template_score` (0–8 int) for partial ranking.

**IBD-style RS:**
```
RS_raw    = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
RS_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(int)
```
Recompute daily across full universe; cache snapshots for reproducibility (no look-ahead).

**ADR% formula:**
```
ADR_pct = 100 * ((high/low).rolling(20).mean() - 1)
```

**Qullamaggie Breakout (canonical):**
```
SCAN:  top 1-2% over 1m/3m/6m AND ADV > $1.5M AND ADR%(20) >= 4
SETUP: 5-25 bar consolidation along rising 10/20/50 SMA, higher lows, range tightening
ENTRY: buy stop at consolidation high
STOP:  low of entry day; risk <= 1×ADR
EXIT:  33-50% off after 3-5 days; trail rest on 10/20/50 SMA close
```

**VCP detection thresholds:**
```
prior_uptrend_pct        >= 30% over <= 6 months
n_contractions           in [2, 6]
depth[i] / depth[i-1]   <= 0.85  (each contraction >= 15% smaller)
first_leg_max_depth      <= 35%
final_contraction_depth  <= 12%
volume_per_leg           decreasing
breakout_volume          >= 1.5 × SMA(volume, 50)
```

## Critical Pitfalls

1. **EMA substitution** for SMA in the Trend Template — produces meaningfully different results; always use SMA.
2. **In-sample weight optimization** for composite score — guaranteed overfit; always walk-forward.
3. **Ignoring the M filter** — long-only through 2008/2022 unhedged = 50%+ loss; regime gate is non-negotiable.
4. **Free EOD + intraday entries** — EP/ORH entries need intraday data; accept next-day-open execution for free-tier.
5. **News sentiment as a primary signal** — FinBERT correlates weakly with forward returns; tertiary feature only.
6. **WSB sentiment as a buy signal** — contrarian indicator at extremes (GME); flag, don't vote.
7. **Survivorship-biased Sharpe** quoted without disclosure.
8. **Forgetting splits in pivot detection** — pre-split pivot vs post-split bar = false breakout signal.
9. **Alpha Vantage as primary** — ~25 calls/day free; cannot scan 1000 tickers.
10. **yfinance batch download without throttle** — one ticker at a time, `random.uniform(0.5, 1.5)` sleep + tenacity.

## Documentation Index

| File | Contents |
|------|----------|
| `docs/methodology.md` | Full Minervini/Qullamaggie/CANSLIM rules, RS formulas, regime components, VCP/flag/cup pattern algorithms, sector RS |
| `docs/data-architecture.md` | Catalyst sources (FinBERT, PRAW, EDGAR), data source matrix, universe construction, survivorship/look-ahead/corporate actions, caching |
| `docs/backtesting.md` | vectorbt patterns, mandatory hygiene, walk-forward + Monte Carlo, metrics table, decile evaluation |
| `docs/ml-layer.md` | LightGBM stack, 60-feature engineering table, target definition, time-series CV, overfit prevention |
| `docs/deployment.md` | Free-tier stack, GitHub Actions CI/CD YAML, Streamlit dashboard page layouts, chart libraries |
| `docs/code-architecture.md` | Full repo layout, pydantic-settings config pattern, tooling, structured logging, testing strategy |
| `docs/tech-stack.md` | Verbose stack with alternatives, "What NOT to Use", version compatibility matrix, confidence ratings |
| `docs/portfolio.md` | README structure, honest backtest reporting, live demo requirements, interview framing |
| `docs/archive/project-spec.md` | Original project mission, CLAUDE.md best practices, 2024–2026 library updates, 6-week build order |

---

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Momentum Swing Screener**

A long-only, end-of-day swing-trading screener that scans the Russell 1000 every evening and produces a ranked list of stocks worth buying tomorrow. Each pick declares which playbook it fits — Qullamaggie continuation flag, Minervini VCP, or leader-hold — and surfaces a concrete entry, stop, and position size for that playbook. Built for Belwin (the user) to actually trade off, starting in paper mode.

**Core Value:** Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.

### Constraints

- **Budget**: $0/month for data and infrastructure — Hard rule. No paid feeds, no cloud SaaS beyond GitHub Actions free tier and (later) Streamlit Community Cloud.
- **Tech stack**: Python 3.11+, pandas, pandas-ta, vectorbt (community edition), GitHub Actions cron — Free, mainstream, fast iteration. No CUDA/TA-Lib C deps in v1 (avoid Streamlit Cloud install issues for M2 dashboard).
- **Data**: yfinance + Finnhub free + FRED + EDGAR (`edgartools`) + Stooq — Only free, durable sources. Survivorship bias accepted and disclosed.
- **Workflow timing**: Evening, post-close (US ET) — EOD-only. No intraday or pre-market dependencies in v1.
- **Universe**: Russell 1000 (~1,000 large/mid-caps) — Liquid, broad enough for daily breakouts, manageable for free-tier rate limits.
- **Output**: Markdown report + paper-trade journal — No UI in v1; dashboard is a later milestone.
- **Validation gate**: Paper trading required before any real-money sizing — Non-negotiable.
- **Methodology fidelity**: Use SMAs (not EMAs) for the Trend Template; signals execute on next-bar open (not current-bar close); fundamentals lag 45 days post-quarter-end.
- **No deadline**: Build it right rather than ship by a date.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

See `docs/tech-stack.md` for the full reference including alternatives, version compatibility, confidence ratings, and sources.

**Core stack (pinned versions):**

| Package | Version | Role |
|---------|---------|------|
| Python | 3.11.x | Runtime |
| uv | 0.11.x | Package + venv manager |
| pandas | 2.2.x | DataFrames |
| numpy | 2.x | Numerics (NumPy 2 required by pandas-ta-classic) |
| pyarrow | 17.x | Parquet I/O |
| yfinance | ≥1.3.0 | OHLCV ingest (primary) |
| pandas-ta-classic | 0.4.47 | Technical indicators (pure Python) |
| vectorbt | 1.0.x | Vectorized backtest + parameter sweeps |
| edgartools | 5.30.x | SEC EDGAR (Form 4, 13F) |
| finnhub-python | 2.4.28 | News, earnings, analyst data |
| fredapi | 0.5.2 | FRED macro |
| requests-cache | 1.3.x | HTTP response cache |
| tenacity | 9.1.x | Retry + exponential backoff |
| pydantic-settings | 2.14.x | Typed config |
| pandera | 0.31.1 | DataFrame schema validation |
| structlog | 25.5.x | Structured JSON logging |
| typer | 0.25.x | CLI |
| ruff | 0.15.x | Lint + format |
| mypy | 1.20.x | Type checking |
| pytest + hypothesis | 8.x / 6.x | Tests + property-based tests |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
