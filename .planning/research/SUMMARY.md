# Project Research Summary

**Project:** Momentum Swing Screener
**Domain:** Long-only EOD momentum swing-trading screener (Russell 1000, free data, daily markdown report)
**Researched:** 2026-04-27
**Confidence:** HIGH

## Executive Summary

This is an EOD pipeline project, not a web application. The architecture is a one-way DAG — network calls in `data/`, pure-function computation in `indicators/` and `signals/`, fan-out to three publishers (Markdown report, Parquet snapshot, SQLite journal). Every expert building a free-data momentum screener converges on the same structural answer: aggressive caching of OHLCV in Parquet, a cross-sectional indicator panel (RS percentile forces this from day one), a rules-based composite scorer with a playbook tagger, and a regime gate that multiplies into position size. The toolchain is locked: Python 3.11, `pandas-ta-classic` (NOT the original `pandas-ta` — its GitHub repo was removed in 2024), `vectorbt 1.0` (Commons Clause, fine for personal/portfolio use), `yfinance >= 1.3.0`, `edgartools 5.30+`, `uv` for env, `ruff`/`mypy`/`pytest` for QA.

The single most important design decision — confirmed across all four research files — is that **per-pick playbook tagging** is the core differentiator. Finviz, MarketSurge, and ChartMill all produce a ranked list; none produce a list where each pick declares which playbook it fits (Qullamaggie continuation / Minervini VCP / leader-hold) and emits playbook-specific entry, stop, trail, and sizing rules. This is what makes the tool tradeable rather than informational, and it is the feature to protect in every architecture and scope decision.

The primary risks are data-quality risks, not engineering risks: survivorship bias from free APIs silently omitting delisted names (inflates Sharpe by 0.2–0.5), look-ahead bias from signals computed at bar `t` but entered at close of `t` (inflates Sharpe 0.3–1.0), and in-sample composite weight optimization (overfit guarantee). All three are mitigated by specific, testable invariants — weekly universe snapshots, a CI-blocking no-look-ahead test, and walk-forward-only weight reporting — not by guidelines.

## Key Findings

### Recommended Stack

The v1 stack is fully locked and version-pinned. The single most important library correction: **do not use `pandas-ta` from PyPI — its GitHub repo (`twopirllc/pandas-ta`) was removed in 2024–2025 and the PyPI package is now beta (0.4.71b0) with murky provenance. Use `pandas-ta-classic` (v0.4.47, March 2026) instead.** Same API, clean community fork, NumPy 2 support, stable releases. Using the original would introduce a hard-to-debug dependency risk and fail on `numpy >= 2.0` (which the rest of the stack requires).

The second critical stack note: `vectorbt 1.0` (April 2026) ships with Apache 2.0 + Commons Clause. Free for personal/research/portfolio use — Belwin's use case is unambiguously covered. The 1.0 API mostly preserves the `Portfolio.from_signals` public surface, but blog posts and LLM-generated code targeting 0.25–0.28 may need updates. When generating vectorbt code, specify version 1.0 explicitly.

**Core technologies (v1 version pins):**
- `python 3.11.x` — all libraries confirmed compatible; avoid 3.12+ until Numba-dependent libs catch up
- `uv 0.11.x` — env + lockfile; signals current practice to a reviewer
- `pandas 2.2.x` + `numpy >= 2.0` + `pyarrow 17.x` — the data substrate; pin `numpy >= 2` or pandas-ta-classic breaks silently
- `pandas-ta-classic 0.4.47` — indicators (SMA, ATR, ADR%, OBV, BBands); pure Python, no C deps (preserves M2 Streamlit Cloud path)
- `yfinance >= 1.3.0, < 2` — OHLCV primary; post-1.0 graduation (Dec 2024) is substantially more stable
- `vectorbt 1.0.x` — backtest harness and parameter sweeps
- `edgartools 5.30.x` — SEC EDGAR; requires `set_identity()` at startup per SEC policy
- `finnhub-python 2.4.28` — earnings calendar, news, sector profile; 60 calls/min free
- `fredapi 0.5.2` — FRED macro (VIX, yields); library is stale but FRED API itself is stable
- `requests-cache 1.3.x` + `tenacity 9.1.x` — HTTP caching (24h fundamentals / 1h news) + retry/backoff
- `pydantic-settings 2.14.x` + `pandera 0.31.1` — typed config + schema enforcement at I/O boundaries
- `structlog 25.5.x` + `typer 0.25.x` — JSON structured logging + CLI
- `ruff 0.15.x` + `mypy 1.20.x` + `pytest 8.x` + `hypothesis 6.x` — QA toolchain

**Explicitly excluded from v1:** TA-Lib (C deps break M2 Streamlit Cloud path), Alpha Vantage as primary OHLCV (25 req/day, unusable for universe scans), IEX Cloud (discontinued Aug 2024), Zipline (legacy Quantopian workflow), backtrader (development tapered 2021).

**GitHub Actions cron note:** schedule at `cron: '30 22 * * 1-5'` (22:30 UTC). Actions cron is not punctual — 15–60 min delays are routine; add a heartbeat job and a `workflow_dispatch` trigger to handle idle-repo throttling (workflows skipped after ~60 days no commits).

### Expected Features

The feature set is anchored by the playbook-tagging differentiator. Every other feature either enables it (indicators, pattern detection, RS percentile) or flows from it (per-tag trade plans, composite score, journal schema).

**Must have (table stakes) — all P1:**
- Daily Russell 1000 EOD scan with cached OHLCV (yfinance + Stooq fallback, Parquet on disk)
- Minervini Trend Template gate: 8 SMA-based conditions, produces both `passes_trend_template` bool and `trend_template_score` 0–8 integer
- IBD-style RS percentile (1–99): `RS_raw = 2*(C/C_63)+(C/C_126)+(C/C_189)+(C/C_252)`, universe-relative daily rank
- ATR(14) + ADR%(20): `100*(rolling_mean(high/low, 20) - 1)` — required for stop placement, Qullamaggie ADR% filter, position sizing
- VCP pattern detector: pivot-based (`scipy.signal.argrelextrema`), depth/volume contraction rules per CLAUDE.md §13.4
- Continuation-flag pattern detector: 5–25 bar consolidation along rising 10/20/50 SMA, higher lows, range tightening, volume contracting
- Qullamaggie Setup A scan: top 1–2% performer over 1m/3m/6m AND ADV > $1.5M AND ADR% >= 4
- Post-gap-continuation D+1 detection (free-tier proxy for Setup B Episodic Pivot)
- Composite confidence score 0–100 (6 components: RS 25% / Trend 20% / Pattern 20% / Volume 10% / Earnings 15% / Catalyst 10%)
- Market-regime gate (SPY trend + breadth + distribution-day count + VIX) — three-state output + continuous `regime_score` in [0,1]
- ATR-based position sizer: Qullamaggie risk-1xADR rejection; regime score multiplied into base risk
- **Per-pick playbook tagging (Qullamaggie continuation / Minervini VCP / leader-hold)** — THE differentiator
- **Per-tag trade-plan emitter** (entry/stop/size/trail per playbook)
- Daily markdown report: regime banner + per-pick blocks (entry/stop/size/trail/component breakdown) + ops footer
- Paper-trade journal (SQLite) with append-only schema, decision-time feature snapshot, full `features_json` blob
- vectorbt backtest harness with walk-forward + per-playbook + per-regime breakdowns
- No-look-ahead enforcement test — CI-blocking in every PR touching `signals/` or `backtest/`
- Weekly universe snapshot (survivorship mitigation, from day one)
- Reproducible local pipeline (`make data && make rank && make backtest`)
- GitHub Actions nightly cron

**Should have (competitive differentiators after core validation):**
- Auditable per-component score breakdown per pick ("RS=92, Trend=8/8, VCP-tightness=6.2%")
- Regime-scaled position size shown in report (already regime-adjusted, not an academic ATR number)
- Risk-1xADR rejection displayed explicitly ("skipped because R/R broken")
- Walk-forward OOS Sharpe distribution over 5+ windows (not a single number)
- Score-decile spread report (top vs bottom decile, weekly rebalance) — demonstrates score monotonicity
- Honest data-quality footer on every report (universe size, scan time, yfinance/Finnhub health, last refresh)
- Distance-from-pivot in ATRs ("0.4xATR above pivot — in zone" / "1.8xATR above pivot — chase, skip")
- Industry RS rank as composite score booster

**Defer to v1.x (after first 30 paper trades):**
- Catalyst tagging (earnings within 7d, recent 52w-high cross) via Finnhub
- Insider cluster-buy flag (EDGAR Form 4 via edgartools)
- Performance attribution by playbook tag
- Mistake-tag taxonomy in journal

**Defer to M2+:**
- LightGBM ML probability + SHAP (needs paper-journal labels)
- Streamlit dashboard (5-page Bloomberg-style UI)
- FinBERT news sentiment + Reddit social buzz
- Cup-and-handle pattern detection
- Hosted public live demo

**Playbook-tagging tie-breaking logic:** Qullamaggie continuation wins if pattern < 25 bars and ADR% >= 5; Minervini VCP wins if pattern >= 25 bars or final contraction <= 8%; leader-hold is the fallback when no actionable pattern. Important: Trend Template failure does NOT disqualify a Qullamaggie continuation tag — Qullamaggie's scan does not require the full 8-condition template.

### Architecture Approach

The pipeline is a strict one-way DAG with disk hand-offs between stages. The only layer permitted to make network calls is `data/`; everything downstream receives DataFrames. This single rule makes backtests reproducible, tests fast (fixture a synthetic OHLCV DataFrame and run the entire `indicators -> signals -> composite -> sizing -> publishers` chain offline), and look-ahead bugs structurally impossible. The composite scorer (`signals/composite.py`) is the single extension point where v1's weighted-sum rules and v2's ML probability converge — keeping the playbook tagger co-located with the scorer prevents the v2 scenario where ML probability and rules-based playbook drift apart.

**Major components and responsibilities:**
1. `data/` — the only I/O layer: yfinance + Stooq fallback OHLCV, Finnhub fundamentals/catalysts, FRED macro, Wikipedia/iShares universe scrape. No other module touches the network.
2. `persistence.py` — Parquet/SQLite read/write helpers + pandera schema enforcement at two I/O boundaries: `data/ -> indicators/` and `composite -> publishers/`.
3. `indicators/` — pure functions, no I/O: `trend.py` (SMA panels + slope), `relative_strength.py` (RS raw + percentile rank), `volatility.py` (ATR, ADR%), `volume.py` (OBV, dryup, pocket pivot), `patterns.py` (VCP + flag detection).
4. `signals/` — pure functions consuming indicator panel: `minervini.py` (Trend Template), `qullamaggie.py` (Setup A + flag), `canslim.py` (C+L+M overlay), `composite.py` (weighted score + playbook tag — THE ML extension point for v2).
5. `regime.py` — one row per date, not per ticker; SPY trend + breadth + distribution-day count + VIX -> discrete state + continuous `regime_score`; multiplied into position size.
6. `sizing.py` — per-playbook entry/stop/shares given ATR, ADR%, regime_score, account_equity; auto-rejects trades where risk > 1xADR.
7. `publishers/` — thin fan-out: `report.py` (Markdown), `snapshot.py` (Parquet ranking for backtest), `journal.py` (SQLite append — the M2 ML training set).
8. `backtest/` — offline only; reads disk artifacts; never imports from `publishers/` or makes network calls.
9. `catalysts/` — v1 stub seams returning zero-filled DataFrames with the column names M2 will populate. Zero M2 refactor cost.
10. `cli.py` — typer commands: `refresh-universe`, `refresh-ohlcv`, `refresh-macro`, `refresh-fundamentals`, `score`, `report`, `journal`, `backtest`. No business logic; orchestrates the DAG.

**Key structural note — panel-first from Phase 2 onward:** IBD-style RS percentile is a cross-sectional operation across the full universe. It cannot be computed per ticker. This forces every indicator and signal function to take a multi-ticker DataFrame from Phase 2 onward. Discovering this in Phase 2 avoids a refactor in Phase 5.

**M2 extension point in `signals/composite.py`:** v1 composite scorer takes a weights dict. v2 adds `"ml_probability": 0.20` to the dict and imports from a new `screener/ml/predict.py`. Zero changes to `data/`, `indicators/`, `signals/{minervini,qullamaggie,canslim}`, `regime`, `sizing`, or `publishers`.

### Critical Pitfalls

The four headline killers (each enforced by tests, not guidelines):

1. **Look-ahead in signals** — signal at bar `t` must execute at bar `t+1` open. Enforce with `test_backtest_no_lookahead.py` in CI: construct a "perfect-foresight" signal equal to next-day return; with correct `.shift(1)` the backtest must be unprofitable. If profitable, there is a leak. Run on every PR touching `signals/` or `backtest/`. Also: fundamentals lag 45 days after fiscal-quarter end; earnings dates from Finnhub `time` flag (BMO/AMC), not yfinance period-end date.

2. **Survivorship bias** — yfinance and Finnhub return only current constituents; delisted names are silently absent. Estimated Sharpe inflation: 0.2–0.5. Fix: weekly universe snapshot to `data/universe/YYYY-MM-DD.parquet` from Phase 1, day one. Assert `backtest.universe_source.snapshot_date <= backtest.start_date` in the harness.

3. **EMA instead of SMA in the Trend Template** — one-character difference; EMA passes more stocks and silently breaks methodology fidelity. CI code-grep: `rg "ema" src/screener/signals/minervini.py` must return zero matches. Pass-rate sanity: 5–15% of Russell 1000 should pass in a normal market; > 25% means the gate is broken.

4. **In-sample composite weight optimization** — overfit is guaranteed. Walk-forward (3-yr IS / 1-yr OOS rolling windows) is non-negotiable. Pre-register the v1 weights at Phase 3 completion by committing `docs/strategy_v1_preregistration.md` with a git hash; assert that hash in CI.

5. **yfinance silent partial failures** — `yf.download()` returns an empty DataFrame on most failure modes rather than raising. Universe health check after every nightly fetch: `assert successful_fetches >= 0.97 * universe_size`. Any run below 95% fails loudly and does not commit the partial result.

6. **Journal pollution corrupts M2 ML training data** — logging only trades the user "would have taken" introduces selection bias. The system appends every actionable pick at publish time, including skipped ones. Decision columns are immutable (append-only SQLite schema). Full `features_json` blob stored at insert time — M2 has the exact state the rules saw.

## Implications for Roadmap

The DAG structure makes the phase order almost deterministic — every phase delivers a thin runnable end-to-end slice, not a horizontal layer. Pattern detection is the longest pole (Phase 5), but cannot start until the indicator panel is solid (Phase 2). The regime module ships alongside the Trend Template (Phase 3) because the Template gate is meaningless without it. The journal schema is frozen at Phase 6 and treated as a v2 ML contract.

### Phase 0: Repo Skeleton
**Rationale:** Engineering hygiene first. Every downstream phase touches the same repo, CI, config, and Makefile. Fixing the skeleton in Phase 0 reduces friction everywhere else.
**Delivers:** `pyproject.toml` (uv-managed, version pins locked), `config.py` (pydantic-settings), `cli.py` (typer skeleton), CI workflow (ruff + mypy + pytest on every PR), Makefile (`make data`, `make rank`, `make backtest`, `make report`), `docs/strategy_v1_preregistration.md` placeholder.
**Avoids:** Streamlit deploy debt (pitfall #14) — pandas-ta-classic locked in pyproject, TA-Lib absent, secrets pattern established from day one.
**Research flag:** Standard patterns, skip research-phase.

### Phase 1: Data Foundation
**Rationale:** All downstream signals are blocked on OHLCV. Survivorship bias is mitigated only if weekly snapshots start on day one — there is no retroactive fix. yfinance rate-limit failures corrupt every downstream result if retries are not in place before the first ticker is fetched.
**Delivers:** `data/universe.py` (Wikipedia + iShares CSV, weekly snapshot to Parquet), `data/ohlcv.py` (yfinance + Stooq fallback, per-ticker Parquet cache with incremental append), `persistence.py` (pandera schemas at I/O boundary), tenacity retries with post-fetch invariants, universe-coverage health check (>= 95% or fail loud), quota tracking in `runs.jsonl`.
**Key invariants shipped:** `assert successful_fetches >= 0.97 * universe_size`; `assert df.index[-1].date() >= today - 4bd`; `splits.parquet` stored alongside OHLCV.
**Avoids:** Survivorship bias (#1, #10), yfinance silent partial failures (#7), API quota exhaustion (#9).
**Research flag:** Standard patterns, skip research-phase.

### Phase 2: Indicator Panel
**Rationale:** RS percentile forces the panel pattern (multi-ticker DataFrame in, same-shape out) from the start. Any refactor from per-ticker to panel later requires touching every indicator and signal module. The regime module ships here because the Trend Template gate (Phase 3) is meaningless without it.
**Delivers:** `indicators/{trend,relative_strength,volatility,volume}.py`, `indicators.build_panel()`, `regime.py` (SPY trend + breadth + distribution-day count + VIX), `data/macro.py` (FRED + Stooq), SMA-only enforcement CI grep, pass-rate sanity check (5–15% of R1000), regime golden-file tests (2008/2020/2022 classified as Correction).
**Avoids:** EMA-vs-SMA confusion (#4), forgotten regime gate (#6).
**Research flag:** May warrant 30 minutes targeting the distribution-day counter formula (IBD-style, CLAUDE.md §2.5) and breadth calculation at planning time. Otherwise standard.

### Phase 3: Trend Template + First Markdown Report
**Rationale:** Ship the simplest end-to-end signal first to validate the full DAG before adding pattern detection complexity. The first report (even with no VCP/flag, just Trend Template + RS + regime) closes the loop. Composite score weights are pre-registered here — the baseline for walk-forward honesty.
**Delivers:** `signals/minervini.py` (8-condition gate + 0–8 partial score), `signals/composite.py` skeleton (weighted sum, playbook tagger added in Phase 5), `sizing.py` (ATR-based, regime-multiplied, 1xADR rejection), `publishers/report.py` (regime banner, picks, ops footer), `publishers/snapshot.py` (Parquet ranking per session), first live markdown report, `docs/strategy_v1_preregistration.md` committed with weights and git hash.
**Avoids:** In-sample weight overfit (#5), multiple-testing blindness (#13).
**Research flag:** Standard patterns. All 8 conditions specified in CLAUDE.md §13.1.

### Phase 4: Backtest Harness
**Rationale:** The no-look-ahead test must exist before any backtest Sharpe number is quoted. Walk-forward is non-negotiable. Running backtests against the Trend-Template-only signal set also gives a useful signal-isolation baseline before pattern detection is added.
**Delivers:** `backtest/{vbt_runner,walkforward,metrics}.py`, `tests/test_backtest_no_lookahead.py` (CI-blocking, mutation-tested — removing `.shift(1)` must cause test failure), walk-forward (3-yr IS / 1-yr OOS), OOS Sharpe distribution, slippage tiers wired by default (5/15/30 bps by ADV tier), `make backtest-audit` forensic checklist CLI command, per-backtest survivorship-disclosure header.
**Avoids:** Look-ahead bias (#2), in-sample overfit (#5), backtest realism (#8), Sharpe > 2 self-skepticism (#15), universe leakage (#10).
**Research flag:** vectorbt 1.0 walk-forward parameter sweep syntax changed from 0.28. 30 min with Context7 `/polakowo/vectorbt` docs at planning time to confirm `Portfolio.from_signals` signature and parameter-grouping API.

### Phase 5: Pattern Detection + Full Signal Stack
**Rationale:** This is the longest phase and the source of the core differentiator. VCP and continuation-flag detection are the hardest components to get right. The signals layer (Qullamaggie Setup A, CANSLIM overlay, full composite scorer with playbook tagger) is all wired here.
**Delivers:** `indicators/patterns.py` (VCP: pivot detection via `scipy.signal.argrelextrema`, contraction enumeration, depth/volume rules per CLAUDE.md §13.4; continuation flag: 5–25 bar consolidation checks), `signals/qullamaggie.py` (Setup A + flag + D+1 post-gap-continuation), `signals/canslim.py` (C+L+M overlay, 45-day fundamentals lag enforced), `signals/composite.py` updated with full playbook tagger (priority: Qullamaggie continuation > Minervini VCP > leader-hold), `data/fundamentals.py`, volume-contraction invariant tests, VCP golden-file tests on NVDA 2023 and AAPL 2020.
**Avoids:** Corporate-action integrity in pivot detection (#3) — pivots re-derived from adjusted closes on every run, never cached as dollar levels.
**Research flag:** VCP detection algorithm is a targeted research candidate — review reference implementations in CLAUDE.md §3.4 (clairetsoi1129/stock-screener, crankycandle/VCP) for API patterns at planning time. Post-gap-continuation D+1 detection (Setup B proxy) is novel — needs a concrete entry rule specified during planning (gap > 8% on day 0, day-1 close in upper third of range, day-2 entry?).

### Phase 6: Sizing + Paper-Trade Journal
**Rationale:** Sizing requires the playbook tag (Phase 5). The journal schema must be set before any paper trades are logged — migrating a corrupt training set is expensive. The journal is the v2 ML contract.
**Delivers:** `sizing.py` finalized per-playbook (Qullamaggie: stop=entry-day-low, risk<=1xADR; Minervini VCP: stop=below-final-contraction-low, prefer<0.5xADR; leader-hold: stop=below-recent-swing-low, 1.5–2xADR), `publishers/journal.py` with append-only SQLite schema, decision-hash invariant, full `features_json` blob at insert, outcomes table with nullable columns for paper-trade results, `data/edgar.py` stub seam (returns empty DataFrames with M2 column names).
**Avoids:** Journal pollution (#11) — append-only constraint, decision columns immutable, every actionable pick logged including skipped ones.
**Research flag:** Journal SQLite schema is the M2 ML training contract — internal design time is high-value. Review FEATURES.md journal schema section to enumerate all columns LightGBM will need in `features_json`. No external research needed.

### Phase 7: GitHub Actions Cron
**Rationale:** Productionalize only after the pipeline works end-to-end locally. The cron is the easy part; the hard part is the robust data layer from Phase 1 which must already be solid.
**Delivers:** `.github/workflows/refresh.yml` (nightly 22:30 UTC weekdays, `workflow_dispatch`, `stefanzweifel/git-auto-commit-action@v5` to commit artifacts), heartbeat job to prevent 60-day idle throttle, GitHub Actions secrets wiring, `runs.jsonl` artifact uploaded per run, nightly report committed to repo.
**Research flag:** Standard patterns, skip research-phase.

### Phase Ordering Rationale

- **Panel-first discipline (Phase 2 gates everything):** RS percentile forces multi-ticker panel pattern from the start. Per-ticker-loop refactor later would touch every indicator and signal module.
- **Regime with Trend Template (Phase 2–3 coupled):** Shipping the regime gate with the Trend Template prevents producing "passing" stocks in 2022 with no warning in early testing.
- **Pattern detection last among core signals (Phase 5):** VCP and flag detection depend on correct ATR/ADR%, correct split-adjusted pivot prices, and correct volume features — all must be solid before pattern logic is added.
- **Backtest before full signal stack (Phase 4 before Phase 5):** The no-look-ahead test must block PRs before pattern detection code is merged. Phase 4 also gives a Trend-Template-only baseline to measure Phase 5's incremental contribution.
- **Journal schema frozen at Phase 6 (after playbook tagger, before any paper trades):** The schema depends on the playbook tag column (Phase 5) but must be finalized before the user begins paper trading.
- **Cron last (Phase 7):** Debugging a nightly failure is much easier when the pipeline is already locally robust.

### Research Flags

Phases needing targeted research during planning:
- **Phase 4 (Backtest harness):** vectorbt 1.0 walk-forward and parameter sweep API changed from 0.28. 30 min Context7 at planning time to confirm current API.
- **Phase 5 (Pattern detection):** VCP contraction enumeration + `argrelextrema` order parameter benefit from reviewing CLAUDE.md §3.4 reference implementations. Post-gap-continuation D+1 detection (Setup B proxy) is novel — needs a concrete entry rule specified during planning.
- **Phase 6 (Journal schema):** Internal design review, not external research. Enumerate all 60+ ML feature columns needed in `features_json` for LightGBM (M2).

Phases with standard patterns (skip research-phase):
- **Phase 0 (Skeleton):** pyproject.toml, pydantic-settings, typer, uv, ruff/mypy/pytest — stable, well-documented.
- **Phase 1 (Data foundation):** tenacity, requests-cache, pandera, Parquet I/O — verified in STACK.md.
- **Phase 2 (Indicator panel):** SMA/ATR/ADR% in CLAUDE.md §3.1 and §13.5; RS formula in §13.2; regime in §2.5.
- **Phase 3 (Trend Template + report):** Exact 8 conditions in CLAUDE.md §13.1; report format in FEATURES.md.
- **Phase 7 (Cron):** GitHub Actions yaml and git-auto-commit-action are standard.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All version pins verified on PyPI 2026-04-27; compatibility matrix confirmed; one critical correction (pandas-ta -> pandas-ta-classic) explicitly sourced from GitHub Issue #30 |
| Features | HIGH | Playbook-tagging differentiator and all table-stakes features cross-verified across CLAUDE.md, PROJECT.md, and competitor analysis; tie-breaking thresholds are heuristic defaults (flagged for paper-trade calibration) |
| Architecture | HIGH | One-way DAG prescribed in CLAUDE.md §10 and validated by pure-function / panel-first / disk-handoff patterns; M2 extension points confirmed via composite.py and catalysts/ stubs |
| Pitfalls | HIGH | All pitfalls sourced from canonical references (Lopez de Prado, Bailey 2014, yfinance issue tracker) plus CLAUDE.md §13.6; every pitfall has a testable invariant |

**Overall confidence:** HIGH

### Gaps to Address

- **Composite score weights are starting points, not validated.** CLAUDE.md §2.7 explicitly flags this. Weights (RS 25%, Trend 20%, Pattern 20%, Volume 10%, Earnings 15%, Catalyst 10%) are pre-registered at Phase 3 and frozen for v1. Walk-forward may surface near-zero contribution from one component — that informs M2 weight tuning, not v1 changes.
- **VCP detection thresholds are heuristic defaults.** CLAUDE.md §13.4 values are community-verified starting points. Tune via golden-file tests on NVDA 2023, AAPL 2020, NVDA 2024 (split-adjusted); do not tune against the backtest result.
- **Playbook tie-breaking thresholds need empirical calibration.** Proposed rules are reasonable defaults. Correct tie-breakers emerge from paper-trading — track which tag's trade plan actually worked and revise in v1.x.
- **Post-gap-continuation D+1 detection (Setup B proxy) is novel.** No comparables implement this. A concrete entry rule needs to be specified during Phase 5 planning: gap > 8% on day 0, day-1 close in upper third of range, day-2 entry?
- **Leader-hold playbook is the loosest defined.** No clean entry trigger. May collapse to "informational only" after paper-trading validates (or invalidates) it. Flag for v1.x revision.
- **Stooq Russell 1000 individual-ticker coverage.** Confirmed for index data (SPY, QQQ, A/D line); full R1000 per-ticker coverage is not exhaustively verified. Treat as best-effort index fallback, not guaranteed per-ticker fallback.

## Sources

### Primary (HIGH confidence — verified 2026-04-27)
- `/Users/belwinjulian/Desktop/SwingTrading/CLAUDE.md` — methodology (§2), indicators (§3), data sourcing (§5), backtesting (§6), architecture (§10), pitfalls (§13.6)
- `/Users/belwinjulian/Desktop/SwingTrading/.planning/PROJECT.md` — scope, out-of-scope, key decisions, constraints
- pandas-ta-classic PyPI (v0.4.47) + xgboosted/pandas-ta-classic Issue #30 (original repo removal confirmed)
- yfinance PyPI (v1.3.0) + GitHub releases (1.0 graduation Dec 2024)
- vectorbt PyPI (v1.0.0 April 2026) + LICENSE.md (Apache 2.0 + Commons Clause confirmed)
- edgartools PyPI (v5.30.0) + Context7 docs
- pandera PyPI (v0.31.1), pydantic-settings PyPI (v2.14.0), structlog PyPI (v25.5.0), typer PyPI (v0.25.0)
- GitHub Actions cron delay community discussion (#156282) + devactivity post

### Secondary (MEDIUM confidence)
- Qullamaggie.com setups + "Laws of Swing" community doc — Setup A/B/C rules
- Minervini books — Trend Template 8 conditions
- Skyte rs-log open-source IBD-RS — RS formula corroboration
- Portfolio123 2019 CANSLIM analysis — C/L/M components carry most signal
- Bailey & Lopez de Prado (2014) "The Deflated Sharpe Ratio" — multiple-testing correction
- Finviz Elite, IBD MarketSurge, Stockbee Bulletin competitor analysis — feature landscape

### Tertiary (LOW confidence — needs validation at integration time)
- Stooq full Russell 1000 individual-ticker coverage — not exhaustively tested
- Finnhub free tier 60 calls/min stability — verify at integration; vendor can change without notice
- fredapi 0.5.2 (May 2024, no recent activity) — FRED API itself is stable; library is frozen but functional

---

**Full research files for drill-in:**
- Stack details + alternatives: `.planning/research/STACK.md`
- Feature dependency graph + markdown report spec + journal schema: `.planning/research/FEATURES.md`
- Full DAG diagram + component responsibility matrix + anti-patterns: `.planning/research/ARCHITECTURE.md`
- Per-pitfall prevention code + testable invariants + recovery strategies: `.planning/research/PITFALLS.md`

---
*Research completed: 2026-04-27*
*Ready for roadmap: yes*
