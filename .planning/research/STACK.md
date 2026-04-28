# Stack Research

**Domain:** End-of-day momentum swing-trading screener (long-only, free-data, Russell 1000)
**Researched:** 2026-04-27
**Confidence:** HIGH (versions verified against PyPI / GitHub releases on this date; license/maintenance status verified for the high-risk libraries — yfinance, vectorbt, pandas-ta)

---

## TL;DR

Build on **Python 3.11**, **uv** for env, **yfinance >= 1.3.0** for OHLCV with **Stooq** as fallback, **pandas-ta-classic** (NOT the original `pandas-ta` — see "What NOT to Use"), **vectorbt 1.0.x** for backtesting (license caveat noted), **edgartools 5.30+** for SEC, **pandas/pyarrow** Parquet on disk for the cache, **requests-cache + tenacity** for HTTP hygiene, **pydantic-settings + pandera** for config and schema, **ruff + mypy + pytest** for QA, **structlog** for logging, **typer** for CLI, **GitHub Actions cron** for nightly refresh (with retry-tolerant scheduling — Actions cron is *not* punctual). No Streamlit, no LightGBM in v1.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11.x | Runtime | 3.11 hits the sweet spot for the 2026 ecosystem: every library below supports it, pandas/numba/numpy 2 wheels are stable, and Streamlit Cloud (M2) still defaults to 3.11. Avoid 3.12+ until you need it; some Numba-dependent libs (vectorbt, pandas-ta-classic) lag a release cycle. |
| uv | 0.11.x (Astral) | Package + venv manager | 10–100× faster than pip; lockfile is reproducible; `uv sync` in CI is a one-liner. Astral has eaten this niche — using uv signals current practice to a reviewer. |
| pandas | 2.2.x | DataFrames | The substrate for everything. Pin >=2.2,<3 — pandas-ta-classic and vectorbt 1.0 both depend on pandas 2.x. |
| numpy | 2.x | Numerics | Pandas-ta-classic >=0.4.47 requires NumPy >=2.0. vectorbt 1.0 supports NumPy 2. The "NumPy 2 migration" pain has largely passed in 2026. |
| pyarrow | 17.x or later | Parquet I/O | Required for the OHLCV cache (Parquet partitioned by ticker). Substantially faster than CSV; columnar reads for indicator pipelines. |
| yfinance | >=1.3.0 | OHLCV ingest (primary) | Reached 1.0 Dec 2024 ("stable a long time now") and 1.3.0 in April 2025; the chronic 2023–2024 breakage cycle has settled significantly. Built-in retry config (`yf.config.network.retries`) replaces ad-hoc patches. **Pin lower bound at 1.3.0**, leave upper bound floating but expect to bump on major Yahoo backend changes. |
| pandas-ta-classic | 0.4.47 (March 2026) | Technical indicators (SMA, ATR, ADR%, OBV, BBands, ADX, etc.) | The original `twopirllc/pandas-ta` repo was **removed from GitHub** in 2024–2025; the PyPI `pandas-ta` package has changed maintainer and is at 0.4.71b0 (beta). `pandas-ta-classic` is the cleanest community continuation: NumPy 2 support, Python 3.9–3.13, stable release cadence, modular extras (`[performance]`, `[talib]`, `[vectorbt]`). Pure Python — no C deps. |
| vectorbt | 1.0.x (April 2026) | Vectorized backtest harness, parameter sweeps | Just hit 1.0 with an optional Rust backend (Numba still default). Best free option for the walk-forward / weight-sweep workflow this project needs. **License caveat**: Apache 2.0 + **Commons Clause** — source-available, free for personal/research/portfolio use, but you cannot resell it or build a paid product on top. For Belwin's use case (personal trading + public portfolio repo) this is a non-issue; just don't claim it's "MIT" in the README. |
| edgartools | 5.30.x | SEC EDGAR (10-K, 10-Q, 8-K, Form 4 insider, 13F) | The recommended free EDGAR library. Parses XBRL into pandas DataFrames so you skip writing your own EDGAR HTTP + XML logic. Requires `set_identity(...)` per SEC policy; mature in 2025–2026. |
| finnhub-python | 2.4.28 | News, earnings calendar, upgrade/downgrade, profile, basic financials | Official Finnhub SDK, single dependency (`requests`), Apache 2.0. Free tier: 60 calls/min, 1y history, US data 15-min delayed. Sufficient for nightly catalysts and CANSLIM "C" approximation. |
| fredapi | 0.5.2 | FRED macro (VIX, T-bill yields, yield curve, ISM) | The de-facto FRED client. Last release May 2024 — no recent activity, but the underlying FRED API is stable so this is fine. |
| requests-cache | 1.3.x | HTTP response cache (Finnhub, NewsAPI, FRED) | SQLite backend by default, Cache-Control aware, drop-in for `requests.Session`. Cuts your Finnhub call count by ~80% across re-runs. |
| tenacity | 9.1.x | Retry + exponential backoff | Standard for resilient API clients. Wrap every external call (yfinance, Finnhub, EDGAR) with `@retry(wait=wait_exponential(...), stop=stop_after_attempt(5))`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.14.x | Typed env-driven config | Single `Settings` class loads `FINNHUB_API_KEY`, `FRED_API_KEY`, risk params, universe choice from `.env` and GitHub Actions secrets. |
| pandera | 0.31.1 | DataFrame schema validation | Validate every IO boundary: OHLCV loader output, indicator output, ranking output. Catches "extra column", "wrong dtype", "null in close" silently before they corrupt the report. |
| structlog | 25.5.x | Structured JSON logging | `log.info("rank_complete", n_pass=..., regime=...)` → JSON line per event. CI workflow uploads `runs.jsonl` as an artifact. |
| typer | 0.25.x | CLI | `screener refresh`, `screener rank`, `screener backtest`. Auto-generated `--help`, type-hint-driven. Built on Click. |
| ruff | 0.15.x | Lint + format | Replaces black + isort + flake8. One tool, ~100× faster, matches modern Python style. |
| mypy | 1.20.x | Type checking | `--strict` on `signals/` and `indicators/` (the math); looser on data/IO modules where third-party stubs are weak. |
| pytest | 8.x | Test runner | With `hypothesis` for property-based tests on indicator math (e.g., SMA of N constants = that constant). |
| hypothesis | 6.x | Property-based testing | Indicators are math; property tests catch edge cases (NaN handling, zero-volume bars) deterministic tests miss. |
| pre-commit | 4.x | Local git hooks | Run ruff + mypy --quick + pytest -m "not slow" before commits. |
| sec-cik-mapper | (transitive) | CIK ↔ ticker | Often pulled in via edgartools; useful when you need to go ticker → CIK explicitly. |
| stockstats / stooq via pandas-datareader | latest | Stooq EOD CSV fallback | When yfinance breaks, hit Stooq via `pandas-datareader` (`pdr.DataReader(t, 'stooq')`) for indices and a sanity-check feed. Don't make Stooq the primary — it occasionally lags a day. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Env + dependency management | `uv init`, `uv add yfinance`, `uv sync` in CI. Lockfile (`uv.lock`) goes in git. |
| GitHub Actions | CI (lint/type/test on PR) + scheduled cron (nightly refresh) | Public repo: unlimited free minutes on standard runners. Schedule cron with `cron: '30 22 * * 1-5'` for 22:30 UTC = 18:30 ET (post-close). **Actions cron is not punctual** — delays of 15–60 min are routine, and idle public repos may be throttled (workflows skipped after ~60 days no commits). Mitigations: (a) accept up to 1h drift; (b) commit a tiny "heartbeat" file in the workflow so the repo never goes idle; (c) trigger `workflow_dispatch` manually on suspicion. |
| Makefile | Convenience targets | `make data && make rank && make backtest && make report`. Reviewers expect this. |
| GitHub Actions secrets | Secrets store | `FINNHUB_API_KEY`, `FRED_API_KEY` etc. — never `.env` in repo. |

---

## Installation

```bash
# Bootstrap with uv (recommended)
uv init momentum-screener
cd momentum-screener

# Core data layer
uv add "yfinance>=1.3.0,<2"
uv add "pandas>=2.2,<3" "numpy>=2.0,<3" "pyarrow>=17"
uv add "pandas-ta-classic>=0.4.47"
uv add "edgartools>=5.30"
uv add "finnhub-python>=2.4.28"
uv add "fredapi>=0.5.2"
uv add "pandas-datareader>=0.10"   # Stooq fallback

# HTTP + resilience
uv add "requests-cache>=1.3" "tenacity>=9.1"

# Backtesting
uv add "vectorbt>=1.0,<2"

# Config / schema / logging / CLI
uv add "pydantic>=2.7" "pydantic-settings>=2.14"
uv add "pandera>=0.31"
uv add "structlog>=25.5"
uv add "typer>=0.25"

# Dev dependencies
uv add --dev "ruff>=0.15" "mypy>=1.20" "pytest>=8" "hypothesis>=6" "pre-commit>=4"
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **vectorbt 1.0 (community)** | **backtesting.py 0.6.5** (July 2025) | If vectorbt's Commons Clause license becomes a blocker (commercial reseller scenario), or if vectorbt PRO becomes the only path for new features. backtesting.py is small, AGPL/MIT-friendly, and adequate for single-strategy event-driven runs. **Drawback**: not vectorized → slow for 1000-ticker × 100-parameter sweeps. |
| **vectorbt 1.0** | **bt 1.2.0** (pmorissette) | When you need a "tree of strategies" composition model with weights and rebalancing — closer to portfolio construction than to single-strategy testing. MIT licensed. Less alpha-research-oriented than vectorbt. |
| **vectorbt 1.0** | **PyBroker (lib-pybroker) 1.2.12** | If/when you bring back the LightGBM ML layer in M2. PyBroker is explicitly ML-centric (built for walkforward training + Numba speed). Pull back into the conversation in M2; **not** a v1 replacement. |
| **vectorbt 1.0 (community)** | **vectorbt PRO** ($) | Belwin's $0/month rule rules this out. PRO has more features (newer ports, more indicators) but the community edition is sufficient for the v1 use case. |
| **pandas-ta-classic** | **TA-Lib (C)** | Only if you need the strictest IBD/Optuma-equivalence on candlestick patterns and are willing to install the C library. **Avoid for v1** — TA-Lib's C dependency complicates Streamlit Cloud deploy in M2 and the GitHub Actions runner setup. pandas-ta-classic supports `[talib]` extra if you want it later. |
| **pandas-ta-classic** | **freqtrade/pandas-ta** | If you adopt the freqtrade ecosystem (live execution bots), use their fork. For this standalone screener, pandas-ta-classic has cleaner pip installation (`pip install pandas-ta-classic` vs git URL), better Python/NumPy 2 compatibility matrix, and more thorough docs. |
| **yfinance + Stooq** | **Finnhub historical OHLCV** | Free tier of Finnhub gives 1y of OHLCV history — fine for daily refreshes once you have a baseline cache, **not** fine for the initial 5-year backtest backfill. Use Finnhub as a tertiary OHLCV cross-check, not primary. |
| **edgartools** | **sec-edgar-downloader** | edgartools is materially higher-level (returns DataFrames). Use sec-edgar-downloader only if you specifically need raw filing files on disk. |
| **uv** | **poetry** / **pip + venv** | Poetry is fine, pip works, but uv is faster, has equivalent features now, and is becoming the new default. Going with uv signals current practice. |
| **structlog** | **stdlib logging** | If you only need plain text logs. structlog's value is the *structured* JSON output that pipes cleanly into log aggregators / GitHub Actions artifacts. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`pandas-ta` (PyPI, original)** | The original `twopirllc/pandas-ta` GitHub repo was **removed in 2024–2025**. The PyPI package has a new maintainer and the latest is 0.4.71**b0** (still beta as of Sept 2025). Provenance is murky. | **`pandas-ta-classic`** — clean community fork, stable releases, NumPy 2 support, same API. |
| **`yfinance < 0.2.40`** | Pre-1.0 versions had the chronic Yahoo-backend breakage cycle (multiple incidents in 2023–2024 where the library went down for days). | **`yfinance >= 1.3.0`** — post-graduation to 1.0 (Dec 2024), stable retry config, much better behavior in 2025–2026. |
| **Alpha Vantage as primary OHLCV** | Free tier is **~25 calls/day** as of 2024–2025 (tightened from 500/day historically). Cannot scan a 1000-ticker universe even once. | yfinance primary, Stooq fallback, Finnhub for cross-checks. Reserve Alpha Vantage for the rare individual-ticker validation lookup. |
| **IEX Cloud** | **Discontinued August 2024.** Tutorials and Stack Overflow answers still reference it. | yfinance + Finnhub + Stooq cover IEX's old role for free. |
| **Zipline / Zipline-reloaded** | Designed around the deprecated Quantopian bundle/ingest workflow. Heavy install (CLI bundle setup, Postgres-style pipelines). Active development tapered. | vectorbt for vectorized research, backtesting.py for event-driven sanity checks. |
| **TA-Lib (C wheel)** | Compiles a C library; install issues on Streamlit Cloud (M2) and macOS ARM are common. The C-binding speedup doesn't matter at this scale. | pandas-ta-classic (pure Python). Pull in TA-Lib later via `pandas-ta-classic[talib]` only if a specific candlestick pattern requires it. |
| **vectorbt PRO** ($) | Violates the $0/month constraint. | vectorbt 1.0 community. |
| **Backtrader for new development** | Active development tapered around 2018–2021; community fork `backtrader2` exists for bug fixes only. Fine to read for inspiration; don't pick it up fresh. | vectorbt for primary; backtesting.py if you need event-driven. |
| **yfinance.download(tickers=[...])** parallel mode without throttling | Yahoo's unofficial rate limit gets you 429s in batch mode if you go too fast. | One ticker at a time with `time.sleep(random.uniform(0.5, 1.5))`, wrapped in tenacity. Cache aggressively (Parquet on disk). |
| **NewsAPI free tier as a primary news source** | 100 req/day, **24-hour delay** on articles — rules it out for catalyst-relevant signals. | Finnhub `/company-news` (60 calls/min on free tier, real-time-ish). NewsAPI fine for backfilling sentiment training data later. |
| **Hydra for config** | Overkill for this scope; adds friction to GitHub Actions and Streamlit Cloud (M2). | pydantic-settings + a YAML file for strategy parameters. |
| **Render free / Vercel / Railway** for the cron (M2 onwards) | Render free spins down on inactivity; Vercel Python serverless is awkward for long-running jobs; Railway eliminated their free tier mid-2023. | GitHub Actions cron (free for public repos). For M2 dashboard, Streamlit Community Cloud (free) — but data jobs stay on Actions. |

---

## Stack Patterns by Variant

**If you stay strictly within v1 (EOD-only, no UI, no ML):**
- The full stack above is sufficient. No GPU, no Streamlit, no Hugging Face. Single GitHub Actions runner, single SQLite/Parquet cache, single Markdown report artifact committed nightly.

**If yfinance breaks for >24h (it has happened ~3× in the last two years):**
- Stooq fallback via `pandas_datareader.data.DataReader(t, 'stooq')` for index data is reliable.
- For Russell 1000 individual tickers, Stooq coverage is patchy — accept a 1-day stale Markdown report and surface "yfinance health check failed; serving cached data from {date}" prominently in the report header. Don't silently fail.
- Long-term mitigation: subscribe to the yfinance GitHub issue tracker; pin a known-good version range and bump deliberately (not `*`).

**If GitHub Actions cron drifts >2h or skips:**
- Add a "heartbeat" job (`schedule: cron: '0 */6 * * *'`) that touches a `last_seen.txt` file — this prevents the 60-day-idle throttle.
- Add a `workflow_dispatch` trigger so Belwin can manually re-run the daily refresh from the Actions tab.
- Acceptance criterion: the report being late by an hour is fine; missing entirely is not. Build a "did the report run today?" check into the next morning's review.

**If Belwin wants to add the Streamlit dashboard (M2):**
- Streamlit Cloud's runner installs from `requirements.txt` or `pyproject.toml`. **TA-Lib C wheels fail there**; sticking to pandas-ta-classic from day one keeps the M2 path painless.
- Cache via `@st.cache_data` for any function that loads the Parquet OHLCV — don't re-read 5y of bars on every Streamlit interaction.

**If Belwin adds LightGBM ML (M2):**
- Add `lightgbm` (CPU-only is fine for this size), `mlflow` (local file backend), `shap`. PyBroker becomes worth a second look at that point.
- All three install cleanly on the GitHub Actions runner and Streamlit Cloud.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pandas-ta-classic 0.4.47 | numpy >=2.0, pandas >=2.0, Python 3.9–3.13 | NumPy 2 required — do not pin numpy<2 elsewhere in the project. |
| vectorbt 1.0.x | Python >=3.10, numpy 2, pandas 2.x | The Rust backend is optional; Numba path still works. Older vectorbt 0.x recipes from blog posts may need API updates. |
| yfinance 1.3.0 | pandas >=1.3, requests >=2.31 | Internal session is much better-behaved than 0.2.x. Still respect rate limits; tenacity backoff still recommended. |
| edgartools 5.30 | Python 3.10–3.14 | Requires `set_identity(name + email)` once at startup per SEC policy; will refuse requests without it. |
| pydantic-settings 2.14 | Pydantic >=2.7, Python 3.10+ | Pydantic v1 syntax is *not* supported. |
| pandera 0.31.1 | pandas, polars, pyspark, geopandas, xarray | We only need the pandas backend; install via `pip install pandera` (no extras needed). |
| typer 0.25 | Click, Rich, Python >=3.10 | |
| ruff 0.15 | Python 3.7–3.14 | Configure via `[tool.ruff]` in `pyproject.toml`. |
| mypy 1.20 | Python 3.9+ | `--strict` aggressively narrows types; in third-party-heavy modules (data/, app/) prefer per-module overrides in `pyproject.toml`. |

### Known Sharp Edges

1. **NumPy 2 transitive break**: pinning anything to `numpy<2` will silently downgrade and break pandas-ta-classic. Use `uv pip compile` to verify the resolved versions.
2. **vectorbt 1.0 vs blog/tutorial code**: most existing vectorbt tutorials are written for 0.25–0.28. The 1.0 API mostly preserves the public surface (`Portfolio.from_signals` etc.) but the Rust backend changes some import paths. When using LLM-generated vectorbt code, **explicitly tell it the version**.
3. **edgartools rate limits**: the SEC's documented cap is 10 req/sec per IP — edgartools respects this internally, but if you fan out across multiple workers (unlikely in v1), enforce shared rate limiting.
4. **Streamlit Cloud (M2) Python version**: defaults to 3.11; if you upgrade local to 3.12+, pin Python in `runtime.txt` (`python-3.11`) for parity.
5. **GitHub Actions schedule cron** uses **UTC**, not the runner's locale. `30 22 * * 1-5` = 22:30 UTC = 18:30 ET (winter) / 17:30 ET (summer, due to DST). For "30 minutes after US market close" you want **22:30 UTC year-round** (markets close 21:00 UTC EDT / 22:00 UTC EST → use 22:30 UTC to clear both).

---

## Confidence Per Recommendation

| Recommendation | Confidence | Verification |
|---------------|------------|--------------|
| Python 3.11 | HIGH | All dependencies confirmed compatible on PyPI metadata. |
| uv 0.11.x | HIGH | Astral's PyPI listing verified; widely adopted in 2025–2026. |
| yfinance >=1.3.0 | HIGH | PyPI release 1.3.0 (April 2025), 1.0 graduated Dec 2024 — verified in GitHub releases. |
| pandas-ta-classic | HIGH | Verified via Context7 + PyPI; explicitly maintained in response to original repo's removal. v0.4.47 (March 2026). |
| **NOT** original `pandas-ta` | HIGH | Original `twopirllc/pandas-ta` GitHub URL returns 404; corroborated by GitHub Discussions noting repo removal and PyPI maintainer change. |
| vectorbt 1.0.x | HIGH on version + maintenance, MEDIUM on long-term-free guarantee | Version verified on PyPI (1.0.0, April 2026); license verified as Apache 2.0 + Commons Clause. The Commons Clause means there is no future guarantee that current features remain free for commercial use, but the existing community release is locked in. |
| edgartools 5.30+ | HIGH | PyPI version + Context7 docs confirm active maintenance. |
| finnhub-python 2.4.28 | HIGH | PyPI verified (April 2026). Free-tier 60 calls/min has been stable for years; verify on integration. |
| pandera 0.31.1 | HIGH | GitHub releases confirm 0.31.1 (April 2025) is the current stable. |
| pydantic-settings 2.14 | HIGH | PyPI verified (April 2026). |
| structlog 25.5 | HIGH | PyPI verified (Oct 2025). |
| typer 0.25 | HIGH | PyPI verified (April 2026). |
| ruff 0.15 / mypy 1.20 | HIGH | PyPI verified, both Astral-style fast release cadence. |
| GitHub Actions cron reliability caveats | HIGH | Multiple 2025 community discussions document delays of 15–60 min and skips on idle repos. |
| fredapi 0.5.2 | MEDIUM | PyPI version is from May 2024 — no recent activity, but FRED API itself is stable. Acceptable risk. |
| Stooq fallback strategy | MEDIUM | Verified Stooq EOD coverage exists for indices; individual-ticker coverage of full Russell 1000 not exhaustively confirmed. Treat as best-effort safety net, not guaranteed identical coverage. |

---

## Sources

- [yfinance on PyPI](https://pypi.org/project/yfinance/) — verified version 1.3.0, dependencies (HIGH)
- [yfinance GitHub releases](https://github.com/ranaroussi/yfinance/releases) — 1.0 graduation Dec 2024, 1.3.0 April 2025 (HIGH)
- [vectorbt on PyPI](https://pypi.org/project/vectorbt/) — verified 1.0.0 April 2026 (HIGH)
- [vectorbt LICENSE](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md) — Apache 2.0 + Commons Clause confirmed (HIGH)
- Context7 `/polakowo/vectorbt` — installation, API surface for v1.0 (HIGH)
- Context7 `/freqtrade/pandas-ta` and `/xgboosted/pandas-ta-classic` — fork landscape after twopirllc removal (HIGH)
- [pandas-ta-classic on PyPI](https://pypi.org/project/pandas-ta-classic/) — 0.4.47 March 2026, NumPy 2 + Python 3.9–3.13 compatibility (HIGH)
- Context7 `/dgunning/edgartools` + [edgartools on PyPI](https://pypi.org/project/edgartools/) — 5.30.0, Python 3.10+ (HIGH)
- [finnhub-python on PyPI](https://pypi.org/project/finnhub-python/) — 2.4.28 April 2026 (HIGH)
- [pandera GitHub releases](https://github.com/unionai-oss/pandera/releases) — 0.31.1 April 2025, polars/xarray support (HIGH)
- [pydantic-settings on PyPI](https://pypi.org/project/pydantic-settings/) — 2.14.0 (HIGH)
- [structlog on PyPI](https://pypi.org/project/structlog/) — 25.5.0 Oct 2025 (HIGH)
- [typer on PyPI](https://pypi.org/project/typer/) — 0.25.0 April 2026 (HIGH)
- [ruff on PyPI](https://pypi.org/project/ruff/) — 0.15.12 (HIGH)
- [mypy on PyPI](https://pypi.org/project/mypy/) — 1.20.2 (HIGH)
- [tenacity on PyPI](https://pypi.org/project/tenacity/) — 9.1.4 Feb 2026 (HIGH)
- [requests-cache on PyPI](https://pypi.org/project/requests-cache/) — 1.3.1 (HIGH)
- [uv on PyPI](https://pypi.org/project/uv/) — 0.11.8 (HIGH)
- [fredapi on PyPI](https://pypi.org/project/fredapi/) — 0.5.2 May 2024 (MEDIUM — stale but functional)
- [GitHub Discussion #156282 — cron delay reports](https://github.com/orgs/community/discussions/156282) (HIGH)
- [devactivity post on Actions cron delays](https://devactivity.com/insights/github-actions-cron-delays-a-community-insight-into-engineering-workflow-scheduling/) (MEDIUM)
- [GitHub xgboosted/pandas-ta-classic Issue #30 — what happened to original pandas-ta](https://github.com/xgboosted/pandas-ta-classic/issues/30) (HIGH — community confirmation of repo removal)
- [pandas-ta-openbb on PyPI](https://pypi.org/project/pandas-ta-openbb/) — alternative fork, NumPy 2 (MEDIUM)
- [backtesting.py on PyPI](https://pypi.org/project/backtesting/) — 0.6.5 July 2025, alternative if vectorbt blocked (HIGH)
- [PyBroker (lib-pybroker) on PyPI](https://pypi.org/project/lib-pybroker/) — 1.2.12 March 2026, M2-relevant (HIGH)
- [bt on PyPI](https://pypi.org/project/bt/) — 1.2.0, MIT, alternative composition-style (HIGH)

---
*Stack research for: long-only EOD swing-trading screener, Russell 1000, $0 budget*
*Researched: 2026-04-27*
