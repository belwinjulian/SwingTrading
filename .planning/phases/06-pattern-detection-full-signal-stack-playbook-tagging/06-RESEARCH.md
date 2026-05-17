# Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging - Research

**Researched:** 2026-05-16
**Domain:** Quantitative pattern detection (scipy peak finding), SEC filings ingestion (edgartools Form 4), financial calendar APIs (Finnhub), append-only event-log storage (SQLite), pandera schema versioning, composite scoring extension
**Confidence:** HIGH on stack + architecture + lag enforcement; MEDIUM on SQL cluster query (SQLite limitation discovered — see Pitfall 7); MEDIUM on yfinance EPS reliability (documented brittleness — see Pitfall 5)

---

## Summary

Phase 6 is the largest single phase in v1: six interconnected pieces (patterns, Qullamaggie, CANSLIM, fundamentals/EDGAR, full composite, playbook tagger) that all gate downstream Phases 7–8. Every locked decision in CONTEXT.md (D-01..D-25) is preserved verbatim in this research; the planner has zero design freedom on the contracts, only on plan/wave structure.

Three findings change implementation details from CONTEXT.md but **do not invalidate any locked decision**:

1. **SQLite `RANGE BETWEEN INTERVAL '<n> days'` is not supported** [VERIFIED: caniuse modern-sql + SQLite docs]. The canonical insider cluster-buy SQL in CONTEXT.md §Specifics will not parse on the SQLite engine that ships with Python 3.11 (modern SQLite 3.40+ also lacks date-interval RANGE frames). CONTEXT.md acknowledges this with the "if it isn't on the deployed sqlite3, fall back to a Python rolling-window post-process" note — research **confirms the fallback is mandatory**, not optional. Two viable shapes documented in Pitfall 7 and the Code Examples section.

2. **`scipy.signal.find_peaks` is the modern replacement for `argrelextrema`** [CITED: scipy 1.16 docs]. PAT-01 names `argrelextrema` explicitly and CONTEXT.md D-01 reaffirms; both still work in scipy 1.17. We use `argrelextrema` as named by the requirement, but note `find_peaks` (with `distance=` and `prominence=`) as a superior alternative if the four golden files fail to converge with `argrelextrema(order=N)` tuning alone.

3. **yfinance `.quarterly_earnings` has been deprecated/unstable since 0.2.6+** [CITED: yfinance GitHub #1345 + ranaroussi/yfinance docs]. The migration target is `Ticker.quarterly_income_stmt` filtered to the "Net Income" / "Diluted EPS" rows. CONTEXT.md D-07 names both `.quarterly_earnings` and `.income_stmt` as alternatives — the planner should default to `.quarterly_income_stmt` and treat missing-data as `earnings_component = 0` per D-13b's lag-enforcement pattern.

**Primary recommendation:** Structure Phase 6 as 5 waves: (W0) test skeletons + 5 pandera schema extensions + Settings additions; (W1) pure indicators (`patterns.py`) — VCP + flag + post-gap-continuation boolean; (W2) data adapters (`data/fundamentals.py`, `data/insider.py`) in parallel; (W3) pure signals (`signals/qullamaggie.py`, `signals/canslim.py`) + composite extension + playbook tagger; (W4) wiring — CLI body fills, snapshot/report extensions, `make fundamentals` target, preregistration amendment, CI green. This sequence respects the structural defense of D-13b (signals/ cannot import data/ — verified in CONTEXT.md D-23 + tests/test_architecture.py).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Ship VCP + continuation flag at full rigor; post-gap-continuation as a simple boolean flag only.**
VCP and continuation flag get full pivot-based detection with `scipy.signal.argrelextrema` (per PAT-01) and the four golden-file tests in D-02. Post-gap-continuation ships as a single boolean column on the panel:
`gap_pct(D-0) >= 0.08 AND vol(D-0) > 1.5 × sma_vol_50 AND close(D-0) >= low(D-0) + 2/3 × (high(D-0) - low(D-0))`
No separate `post_gap_continuation` playbook tag; flag feeds the catalyst component? **No — D-11a clarifies the flag stays in `pattern_diagnostics` only, NOT in catalyst component.** Full post-gap playbook deferred to v1.x.

**D-02: Four golden-file pattern tests (PAT-06 + one continuation flag):**
1. NVDA 2023 base — clean VCP into AI-rally breakout
2. AAPL 2020 base — COVID-recovery VCP
3. NVDA 2024 split-adjusted — pivot re-derivation across 2024-06-10 10:1 split
4. NVDA 2023-05-25..2023-06-12 continuation flag — post-earnings flag along rising 10-SMA

**D-03: VCP thresholds locked as `Final` module-level constants in `indicators/patterns.py`.** No Settings field, no env override. Values verbatim from CLAUDE.md: prior_uptrend ≥30%, n_contractions ∈ [2,6], depth[i]/depth[i-1] ≤ 0.85, first_leg ≤ 35%, final ≤ 12%, breakout_vol ≥ 1.5×SMA50.

**D-04:** "Held the gap" = `close(D-0) >= low(D-0) + (2/3) × (high(D-0) - low(D-0))` — upper third of D-0 high-low range.

**D-05: Pattern diagnostics — compact dict in snapshot + full per-leg history in `data/pattern_audit/YYYY-MM-DD.parquet` (gitignored).**

**D-06: Breakout-volume confirmation is same-bar + graded `breakout_strength`.**
`breakout_strength = clip((vol / sma_vol_50 - 1.0) / 1.5, 0, 1)`.

**D-07:** Finnhub `/calendar/earnings` for upcoming; yfinance for EPS history. Both write to `data/fundamentals/*.parquet`.

**D-08:** EDGAR Form 4 = bulk nightly refresh into `data/insider/form4.sqlite`. `edgartools.set_identity()` at startup of `cli.py`; fail loud if not set.

**D-09:** Single `make fundamentals` target with `--skip-insider` / `--insider-only` flags. Preserves 9-subcommand lock.

**D-10:** Insider Form 4 SQLite schema — append-only event log: `(filing_id PK, ticker, insider, transaction_date, type, shares, value_usd, ingested_at)`.

**D-11:** Catalyst component (10%) = `(earnings_proximity + crossed_52w_high_within_60d + insider_cluster_buy) / 3`.

**D-11a:** Two-tier earnings — ≤14d to earnings → catalyst=1; ≤3d → report annotation `earnings_in_3d_warn` (does NOT decrement catalyst).

**D-12:** Snapshot emits primary `playbook_tag` AND three binary diagnostic scores (`qullamaggie_score`, `minervini_score`, `leader_hold_score`).

**D-13:** Tie-breaker thresholds locked as `Final` constants in `signals/composite.py`: QULL_MAX_BARS=25, QULL_MIN_ADR_PCT=5.0, MINERVINI_MIN_BARS=25, MINERVINI_MAX_FINAL_CONTRACTION_PCT=8.0, LEADER_MIN_RS=90.

**D-13b: Lag enforcement lives in the DATA LAYER via `knowable_from` column + persistence-time filtering.** `signals/canslim.py` consumes pre-filtered data — it cannot accidentally violate the lag (signals/ cannot import data/ per architecture constraint).

**D-14:** Tie-break when pick satisfies BOTH Qullamaggie and Minervini — **Qullamaggie wins** (momentum-bias default; shorter consolidation + high ADR%).

**D-15:** `leader_hold` = Trend Template pass + RS ≥ 90 + no VCP/flag detected; routed to SEPARATE report section "Currently Held / Leaders", NOT the top-N. Picks failing ALL three scores get `playbook_tag = "none"` and are excluded from report entirely.

**D-16:** Phase 6 removes `pattern`, `earnings`, `catalyst` from `PHASE_4_ZEROED` frozenset. `DEFAULT_WEIGHTS` values unchanged. Zero refactor of `weights.items()` scoring loop.

**D-17:** Pattern component = `breakout_strength` of winning pattern OR 0 if no pattern.

**D-18:** Earnings component = CANSLIM C only — boolean (EPS YoY ≥ 25% AND knowable). L and M are not double-counted (already in `rs_component` and regime gate).

**D-19:** Per-pick report block format (revised):
```
RS=92 | Trend=8/8 | Pattern=0.67 (VCP, 4 contractions, brk_vol=2.1x) | Volume=0.7 | Earnings=1 (EPS YoY 32%) | Catalyst=0.67 (2/3 flags)
Playbook: qullamaggie_continuation (Q=1, M=0, LH=0)
WARNING: Earnings in 2d  [shown only when earnings_in_3d_warn=true]
```

**D-20..D-25:** Carried-forward — regime gate stays soft; preregistration CI script unchanged; Phase 5 harness auto-picks-up playbook tags; architecture ALLOWED dict extension per D-23; 9-subcommand lock preserved; pivot re-derived from adjusted closes per PAT-05.

### Claude's Discretion

- **`indicators/patterns.py` vs `signals/patterns.py` placement.** CLAUDE.md repo layout says `indicators/patterns.py`. **Research recommends `indicators/patterns.py`** — pattern detection is panel-in, panel-out, pure function, consumes other indicators; matches existing `indicators/` purity contract.
- **Pivot detection algorithm — `argrelextrema` vs custom zigzag.** PAT-01 names argrelextrema; planner chooses `order` parameter and smoothing. **Research recommendation in Code Examples §2.**
- **Higher-lows tolerance for continuation flags.** PAT-03 says "higher lows". **Research recommends tolerant (each low ≥ prior low - 0.5 × ATR) per Code Examples §3** — strict comparison fails on noisy intraday wicks.
- **Qullamaggie Setup A "top 1–2%" semantics.** **Research recommends pure percentile rank** (CONTEXT.md documented default) — simpler, matches IBD RS pattern already in codebase.
- **Sector RS (CANSLIM L extension).** **Research recommends keeping ticker-level only**, sector RS to v1.x.

### Deferred Ideas (OUT OF SCOPE)

- Full post-gap-continuation playbook (own tag, EP-style entry rules) — v1.x
- Sector RS (CANSLIM L extension; deferred from Phase 3) — v1.x
- Graded playbook scores (continuous 0–1 instead of binary) — v1.x
- Settings-tunable VCP and tie-breaker thresholds — v1.x
- Cup-and-handle detection — v2
- Setup C (parabolic capitulation longs) — Out of scope
- FinBERT news sentiment + Reddit social buzz — M3
- Per-pick `tag_confidence` (margin between top score and runner-up) — v1.x
- Insider Form 4 from non-EDGAR sources (Finnhub /insider-transactions) — v1.x fallback only

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DAT-05 | `make fundamentals` + 45d lag | §Code Examples §5 (knowable_from), §Architecture Patterns "Data → Signals one-way edge" |
| PAT-01 | VCP detector via `scipy.signal.argrelextrema` with contraction sequence | §Code Examples §2 (pivot detection with order tuning), §Standard Stack scipy.signal |
| PAT-02 | VCP recognition thresholds (prior leg, contractions, depth ratios, breakout vol) | §User Constraints D-03 (locked Final constants), §Code Examples §2 |
| PAT-03 | Flag detector (5–25 bar consolidation, rising 10/20/50 SMA, higher lows, range tightness, vol contraction) | §Code Examples §3 (tolerant higher-lows), §Reusable Assets `dryup_ratio` |
| PAT-04 | Post-gap-continuation D+1 detection | §User Constraints D-01 + D-04 (boolean flag only; not separate detector) |
| PAT-05 | Pivot prices re-derived from adjusted closes every run | §Standard Stack note on `auto_adjust=True` already in `data/ohlcv.py`; §Validation Architecture pivot continuity test |
| PAT-06 | Golden-file tests for ≥3 historical setups | §User Constraints D-02 (four golden files), §Validation Architecture |
| SIG-02 | Qullamaggie Setup A scan (top 1–2% performers, $1.5M ADV, ADR%≥4) | §Code Examples §6 (pure-function vectorized scan); existing `adr_pct` + `rs_rating` columns |
| SIG-03 | CANSLIM C+L+M additive scoring | §User Constraints D-18 (C-only to avoid double-counting); §Code Examples §7 |
| CMP-01 | Composite weights (RS 25/Trend 20/Pattern 20/Volume 10/Earnings 15/Catalyst 10) | Unchanged from Phase 4; D-16 removes 3 keys from PHASE_4_ZEROED |
| CMP-02 | Each pick declares playbook tag | §Code Examples §8 (`tag_playbook(panel)` pure function) |
| CMP-03 | Tie-breaking rules (Qullamaggie if <25 bars + ADR%≥5; Minervini if ≥25 bars or final ≤8%; leader-hold fallback) | §User Constraints D-13 + D-14; §Code Examples §8 |
| CMP-04 | Composite co-locates score + tag in `signals/composite.py` | §Architecture Patterns (Phase 6 extension is keys-removed + three helpers + tagger; zero refactor of scoring loop) |
| CMP-05 | Per-pick component breakdown exposed | §User Constraints D-19 format; existing report block extended |
| CAT-01 | `days_to_next_earnings` from Finnhub + BMO/AMC | §Code Examples §4 (Finnhub `/calendar/earnings` schema with `hour` field) |
| CAT-02 | `crossed_52w_high_within_60d: bool` | Existing `high_52w` column; trivial rolling-60 lookup |
| CAT-03 | EDGAR Form 4 cluster-buy (≥2 insiders within 5-day rolling window in last 30 days) | §Code Examples §5 + §Pitfalls #7 (SQLite RANGE INTERVAL limitation — use julianday or Python fallback) |
| CAT-04 | `edgartools.set_identity()` at startup or fail loud | §Code Examples §1 (cli.py startup hook); confirmed via edgar docs (10 req/sec rate limit; identity required) |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Phase 6 Impact |
|------------|--------|----------------|
| Python 3.11+; type hints required in `signals/`, `indicators/` | Coding Conventions | `mypy --strict` on new `patterns.py`, `qullamaggie.py`, `canslim.py` |
| Pure functions in `signals/` and `indicators/` — no I/O, no side effects | Coding Conventions + Architectural Rules | Patterns detector, Qullamaggie scan, CANSLIM overlay, playbook tagger ALL pure |
| All external API calls go through `data/` modules | Coding Conventions | `data/fundamentals.py` and `data/insider.py` are the only modules touching Finnhub + edgartools |
| No `print()` anywhere — use `structlog` | Coding Conventions | All new modules use `log = structlog.get_logger(__name__)` |
| No global mutable state in modules | Coding Conventions | VCP thresholds, tie-breaker thresholds are `Final[...]` immutable; SQLite connection is per-call not module-level |
| `mypy --strict` on `indicators/` and `signals/` | Coding Conventions | Type-annotate every helper; `Final[float]`, `Final[int]` on D-03/D-13 constants |
| Entry signals at bar `t` execute at open of `t+1` — **Never same-bar execution** | Architectural Rules | D-06 confirms: pick fires after EOD on same bar (`close > pivot AND vol >= 1.5×SMA50`); entry tomorrow's open per BCK-02 already enforced in Phase 5 harness |
| Fundamentals lag 45 days after fiscal-quarter end | Architectural Rules | D-13b structural enforcement: `read_fundamentals(as_of_date)` filters `knowable_from <= as_of_date`; signals/ cannot import data/ |
| Parquet on disk for OHLCV; `requests-cache` SQLite for HTTP APIs | Architectural Rules | `requests-cache` 24h cache for Finnhub `/calendar/earnings`; separate `data/insider/form4.sqlite` is an event-log (NOT a request cache) |
| Every IO boundary validates with a `pandera` schema | Architectural Rules | `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema`, extended `RankingSnapshotSchema` |
| YOU MUST run `pytest tests/test_backtest_no_lookahead.py` after any change to `signals/` or `backtest/` | Testing Rules | Phase 6 modifies `signals/composite.py` — gate runs automatically on PR per `.github/workflows/no-lookahead-gate.yml` |
| SMA not EMA in Trend Template | Critical Pitfalls #1 | Existing CI grep gate covers `signals/minervini.py` + `indicators/trend.py`; planner extends grep scope to new files? **No** — grep is currently scoped to those two; new Phase 6 files don't add EMA risk. |
| Long-only without M filter = 50%+ loss; regime gate non-negotiable | Critical Pitfalls #3 | D-20 confirms: regime gate stays soft (`composite_score *= regime_score`); `leader_hold` section unaffected by regime |
| News sentiment as primary signal — tertiary feature only | Critical Pitfalls #5 | FinBERT deferred to M3; Phase 6 catalysts are earnings + 52w high + insider cluster only |
| In-sample weight optimization = guaranteed overfit | Critical Pitfalls #2 | D-03 + D-13: VCP and tie-breaker thresholds tuned via **golden-file tests only**, never against backtest results |
| Forgetting splits in pivot detection — pre-split pivot vs post-split bar = false breakout | Critical Pitfalls #8 | D-25 + PAT-05: pivot re-derived from adjusted closes every run; NVDA 2024-06-10 10:1 split golden file is the regression gate |
| yfinance: one ticker at a time, throttled, cached | Critical Pitfalls #10 | Reuse `data/ohlcv.py` `fetch_ohlcv_with_pacing` pattern for yfinance EPS calls (per-ticker, `random.uniform(0.5, 1.5)` sleep + tenacity retry) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| VCP / continuation-flag detection | `indicators/patterns.py` | — | Pure panel-in, panel-out; uses pre-computed SMAs/ATR/dryup_ratio; matches existing `indicators/` purity contract |
| Post-gap-continuation boolean | `indicators/patterns.py` | — | Same domain — derives from OHLCV + SMA(volume,50) already in panel |
| Qullamaggie Setup A scan | `signals/qullamaggie.py` | — | Composes indicator outputs (rs_rating, adr_pct, dollar_volume) into a signal predicate |
| CANSLIM overlay (C only — D-18) | `signals/canslim.py` | — | Reads pre-filtered fundamentals via `persistence.read_fundamentals(as_of_date)`; pure function over indicator panel + fundamentals frame |
| Earnings calendar fetch | `data/fundamentals.py` | `persistence` | All external I/O lives in `data/`; writes via persistence atomic helper |
| EPS history fetch | `data/fundamentals.py` | `persistence` | Same — yfinance call wrapped with existing throttle pattern |
| EDGAR Form 4 bulk fetch | `data/insider.py` | `persistence` | All external I/O lives in `data/`; writes append-only SQLite event log |
| Pattern audit per-leg storage | `persistence.py` | — | Atomic Parquet write helper for `data/pattern_audit/<date>.parquet` |
| Composite score full activation | `signals/composite.py` | `indicators/`, `regime`, `persistence` | Extension — remove keys from PHASE_4_ZEROED, add three component helpers, add `tag_playbook` |
| Playbook tagger | `signals/composite.py` | — | Co-located with composite per CMP-04; pure function over panel + diagnostics |
| Snapshot extension (+9 columns) | `publishers/snapshot.py` + `persistence.RankingSnapshotSchema` | — | Schema-at-IO contract — Phase 5 backfill snapshots will be re-derived on `make backfill-snapshots` re-run |
| "Currently Held / Leaders" report section | `publishers/report.py` | — | Extension of existing report renderer; new section after top-N table |
| `make fundamentals` orchestrator | `cli.py` `refresh-fundamentals` | `data/fundamentals`, `data/insider` | CLI is composition root; existing stub body fills with 3-step sequence (Finnhub → yfinance EPS → EDGAR Form 4) |
| `edgartools.set_identity()` startup hook | `cli.py` | — | Fail-loud at startup if EDGAR_IDENTITY env var unset and any subcommand needs EDGAR access |

## Standard Stack

### Core (verified installed in venv 2026-05-16)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scipy | 1.17.1 [VERIFIED: `uv run python -c "import scipy"`] | `scipy.signal.argrelextrema` for pivot detection (PAT-01 verbatim) | Named explicitly by PAT-01; pure Python wrapper around C peak-finding; available since scipy 0.11 |
| pandas-ta-classic | 0.4.47 [VERIFIED: in pyproject.toml] | SMA, ATR, ADR%, volume baselines already in panel | Pure-Python; no TA-Lib C deps; existing Phase 3 dependency |
| edgartools | ≥5.30,<6 [CITED: pyproject.toml — module name is `edgar`, not `edgartools`] | SEC EDGAR Form 4 bulk fetch | CONTEXT.md D-08 locks; benchmark score 91.6 on Context7; default 10 req/sec rate limit auto-enforced |
| finnhub-python | ≥2.4.28,<3 [VERIFIED: pyproject.toml + venv import] | `/calendar/earnings` for upcoming dates + BMO/AMC | CONTEXT.md D-07 locks; free tier 60 req/min ceiling; client method is `finnhub_client.earnings_calendar(_from=..., to=..., symbol=...)` |
| yfinance | 1.3.0 [VERIFIED: venv] | EPS history via `Ticker(t).quarterly_income_stmt` (NOT `.quarterly_earnings` — deprecated) | Existing dependency; throttle pattern in `data/ohlcv.py` reused |
| requests-cache | ≥1.3,<2 [VERIFIED: pyproject.toml] | 24h cache for Finnhub `/calendar/earnings` per `data-architecture.md` §7 | Existing dependency; SQLite backend |
| tenacity | ≥9.1 [from CLAUDE.md table] | Retry/backoff on Finnhub 429s | Existing dependency; pattern in `data/ohlcv.py` |
| pandera | 0.31.1 [VERIFIED: venv] | `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema`, extended `RankingSnapshotSchema` | Existing Phase 2 contract — schema at every IO boundary |
| structlog | 25.5.x | JSON logging in new modules | Existing repo standard; no `print()` allowed |
| sqlite3 (stdlib) | Python 3.11.x | Insider Form 4 event log | Stdlib — no new dependency |

### Supporting (already in repo)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typer | 0.25.x | CLI surface | `refresh-fundamentals` body fill; `--skip-insider` / `--insider-only` flags per D-09 |
| pydantic-settings | 2.14.x | `Settings` extension | Add `FINNHUB_API_KEY` (already present), `FUNDAMENTALS_CACHE_DIR`, `INSIDER_CACHE_PATH`, `PATTERN_AUDIT_DIR` (D-23 + CONTEXT.md Settings extension pattern) |
| pyarrow | 17.x | Parquet I/O for fundamentals + pattern_audit | Existing — `_write_parquet_atomic` already uses `engine="pyarrow"` |
| pytest + hypothesis | 8.x / 6.x | Golden-file regression tests | Existing — Phase 3 regime golden tests are precedent |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `scipy.signal.argrelextrema(order=N)` | `scipy.signal.find_peaks(distance=, prominence=)` | `find_peaks` has richer parameters (distance + prominence); use as fallback if argrelextrema tuning fails to converge on the 4 golden files. PAT-01 names argrelextrema explicitly — start there. |
| `edgartools` for Form 4 | Finnhub `/stock/insider-transactions` (free tier) | CAT-04 explicitly requires `edgartools.set_identity()`; Finnhub alternative documented as v1.x fallback only (CONTEXT.md Deferred Ideas) |
| `Ticker.quarterly_earnings` | `Ticker.quarterly_income_stmt` | `.quarterly_earnings` is deprecated as of yfinance 0.2.6+ (Pitfall 5); `.quarterly_income_stmt` is the supported path. CONTEXT.md D-07 mentions both — research recommends defaulting to `.quarterly_income_stmt`. |
| Custom zigzag pivot detection | `scipy.signal.argrelextrema` | PAT-01 names argrelextrema; custom zigzag adds maintenance burden without measurable benefit |
| SQLite `RANGE BETWEEN INTERVAL` window | `julianday()` numeric conversion OR Python rolling-window | SQLite does NOT support `RANGE BETWEEN INTERVAL '4 days' PRECEDING` for date columns (verified — see Pitfall 7). Use `julianday(transaction_date)` for numeric RANGE or pandas rolling-window in Python. |
| JSON-encoded dict in Parquet column | PyArrow struct/dict native type | JSON-string in `object` dtype column is simpler for pandera validation (`Series[str]` + custom check); avoids nested-schema complexity. ~150 bytes/pick is well under any concern. |

**Installation:** All required packages already in `pyproject.toml` (verified). No `uv add` needed.

**Version verification:** Run `uv run python -c "import scipy, edgar, finnhub, pandera, yfinance; print(scipy.__version__, finnhub.__name__, pandera.__version__, yfinance.__version__)"` before Wave 0 to confirm environment.

## Architecture Patterns

### System Architecture Diagram

```
                       ┌─────────────────────────────────────────────────────┐
                       │ Nightly  `make fundamentals` (cli.refresh-fundamentals)│
                       │ (calls set_identity() FIRST; fails loud if unset)   │
                       └─────────────┬───────────────────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
   ┌────────────────┐     ┌────────────────────┐    ┌────────────────────┐
   │ Finnhub        │     │ yfinance EPS       │    │ EDGAR Form 4 bulk  │
   │ /calendar/     │     │ Ticker(t).         │    │ get_filings(form=  │
   │ earnings       │     │ quarterly_         │    │   "4", filing_     │
   │ (24h           │     │ income_stmt        │    │   date="-35d:")    │
   │ requests-cache)│     │ (per-ticker        │    │ (rate-limited      │
   │                │     │ throttle reused    │    │ to 10/s by         │
   │                │     │ from data/ohlcv)   │    │ edgartools)        │
   └────────┬───────┘     └─────────┬──────────┘    └─────────┬──────────┘
            │                       │                          │
            └───────────────────────┼──────────────────────────┘
                                    ▼
                  ┌─────────────────────────────────────────┐
                  │ data/fundamentals.py + data/insider.py  │
                  │ (validate at write via pandera;          │
                  │  add knowable_from = qtr_end + 45 days)  │
                  └─────────┬───────────────────────────────┘
                            ▼
            ┌───────────────────────────────────┐    ┌──────────────────────────┐
            │ data/fundamentals/*.parquet       │    │ data/insider/form4.sqlite│
            │ (per-ticker; eager pandera valid) │    │ (append-only event log)  │
            └─────────┬─────────────────────────┘    └──────────┬───────────────┘
                      │                                          │
        ───────── architecture boundary (signals/ cannot reach data/) ──
                      │                                          │
                      ▼                                          ▼
       ┌────────────────────────────────┐    ┌─────────────────────────────────┐
       │ persistence.read_fundamentals  │    │ persistence.read_insider_       │
       │  (as_of_date)                  │    │  cluster_buy(window_days=30,    │
       │  FILTERS knowable_from         │    │  cluster_size=2, dt=5)          │
       │  <= as_of_date  (D-13b lag)    │    │  (SQL/Python hybrid — Pitfall 7)│
       └─────────┬──────────────────────┘    └──────────┬──────────────────────┘
                 │                                       │
                 ▼                                       │
   ┌─────────────────────────────────┐                  │
   │ signals/canslim.py              │                  │
   │ EPS YoY ≥ 25% check             │                  │
   │ → earnings_component (D-18)     │                  │
   └─────────┬───────────────────────┘                  │
             │                                          │
             ▼                                          ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │ indicators.build_panel() output (existing — Phase 3)            │
    │ + indicators/patterns.py (NEW — VCP, flag, post-gap)            │
    │   → vcp_passes, flag_passes, post_gap_continuation,             │
    │     pivot_price, breakout_strength, pattern_diagnostics         │
    │ + signals/qullamaggie.py (NEW — Setup A scan)                   │
    │   → qullamaggie_score (0/1)                                     │
    └─────────────────────┬───────────────────────────────────────────┘
                          ▼
       ┌──────────────────────────────────────────────────────────┐
       │ signals/composite.py (EXTENDED — D-16)                   │
       │   PHASE_4_ZEROED = frozenset()  # was {pattern,earnings,catalyst}│
       │   score_pattern_component(panel)  -> pattern_component   │
       │   score_earnings_component(panel) -> earnings_component  │
       │   score_catalyst_component(panel) -> catalyst_component  │
       │   tag_playbook(panel) -> playbook_tag, q/m/lh scores     │
       │   (existing weights.items() loop discovers new columns   │
       │    with zero refactor — D-13 contract preserved)         │
       └────────────────────────┬─────────────────────────────────┘
                                ▼
       ┌─────────────────────────────────────────────────────────┐
       │ publishers/pipeline.run_pipeline (extended)             │
       │   → publishers/snapshot.write_snapshot                  │
       │       (RankingSnapshotSchema +9 columns)                │
       │   → publishers/report.write_report                      │
       │       (D-19 format + Currently Held / Leaders section)  │
       │   → persistence.write_pattern_audit_atomic              │
       │       (data/pattern_audit/<date>.parquet, gitignored)   │
       └──────────────────────────┬──────────────────────────────┘
                                  ▼
       ┌─────────────────────────────────────────────────────────┐
       │ data/snapshots/YYYY-MM-DD.parquet (extended)            │
       │   + playbook_tag, qullamaggie_score, minervini_score,   │
       │     leader_hold_score, pattern_diagnostics,             │
       │     breakout_strength, days_to_next_earnings,           │
       │     crossed_52w_high_within_60d, insider_cluster_buy,   │
       │     earnings_in_3d_warn                                 │
       │                                                          │
       │ Phase 5 backtest harness reads these snapshots → BCK-04 │
       │ per-playbook attribution AUTO-POPULATES (D-22).         │
       └─────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (Phase 6 additions in **bold**)

```
src/screener/
  config.py                  # extended: FUNDAMENTALS_CACHE_DIR, INSIDER_CACHE_PATH, PATTERN_AUDIT_DIR
  data/
    fundamentals.py          # NEW — Finnhub /calendar/earnings + yfinance EPS history
    insider.py               # NEW — edgartools Form 4 bulk → SQLite append-only event log
  indicators/
    patterns.py              # NEW — VCP, flag, post_gap_continuation (pure)
  signals/
    qullamaggie.py           # NEW — Setup A scan (pure)
    canslim.py               # NEW — C-only overlay; reads pre-filtered fundamentals (pure)
    composite.py             # EXTENDED — D-16, three component helpers, tag_playbook
  persistence.py             # EXTENDED — FundamentalsSchema, InsiderSchema,
                             #            PatternAuditSchema, RankingSnapshotSchema (+9 cols),
                             #            read_fundamentals(as_of_date),
                             #            read_insider_cluster_buy(window_days, cluster_size, dt),
                             #            write_fundamentals_atomic, write_pattern_audit_atomic
  publishers/
    report.py                # EXTENDED — D-19 format + Currently Held / Leaders section
    snapshot.py              # EXTENDED — passes through 9 new columns
    pipeline.py              # EXTENDED — calls patterns → qullamaggie → canslim →
                             #            composite (full) → tag_playbook → snapshot → report
  cli.py                     # EXTENDED — set_identity() startup hook;
                             #            refresh-fundamentals body fill (3-step orchestrator);
                             #            --skip-insider / --insider-only flags
tests/
  test_patterns_golden.py    # NEW — 4 golden files (D-02)
  test_patterns_split.py     # NEW — NVDA 2024-06-10 10:1 split pivot continuity (PAT-05)
  test_qullamaggie.py        # NEW — Setup A scan (synthetic panel)
  test_canslim.py            # NEW — additive scoring + de-dup verification (D-18)
  test_canslim_lag.py        # NEW — 45d lag enforcement (D-13b verbatim)
  test_fundamentals_io.py    # NEW — Finnhub + yfinance EPS fetch (mocked)
  test_insider_io.py         # NEW — Form 4 fetch + SQLite write (mocked)
  test_insider_cluster_buy.py # NEW — cluster query against synthetic fixture
  test_composite_full.py     # NEW — all components active; D-16 frozenset shrink
  test_playbook_tagger.py    # NEW — D-14 tie-breaker matrix
  test_breakout_strength.py  # NEW — D-06 graded formula
  test_architecture.py       # EXTENDED — D-23 ALLOWED dict extension
data/
  fundamentals/              # gitignored; per-ticker Parquet
  insider/
    form4.sqlite             # gitignored; append-only event log
  pattern_audit/             # gitignored; daily per-leg detail
```

### Pattern 1: Final-Constant Locking (D-03 + D-13)

**What:** Thresholds are `Final[...]` module-level constants — not Settings fields, not env-overridable.
**When to use:** Heuristic parameters that must be defended against in-sample tuning (Critical Pitfall #2).
**Example:**

```python
# Source: existing pattern in src/screener/signals/composite.py (Phase 4 DEFAULT_WEIGHTS)
from typing import Final

# VCP thresholds (D-03) — verbatim from CLAUDE.md §"VCP detection thresholds"
PRIOR_UPTREND_MIN_PCT: Final[float] = 0.30
N_CONTRACTIONS_RANGE: Final[tuple[int, int]] = (2, 6)
DEPTH_CONTRACTION_MAX_RATIO: Final[float] = 0.85
FIRST_LEG_MAX_DEPTH_PCT: Final[float] = 0.35
FINAL_CONTRACTION_MAX_DEPTH_PCT: Final[float] = 0.12
BREAKOUT_VOLUME_MIN_MULTIPLE: Final[float] = 1.5
SMA_VOLUME_BASELINE_DAYS: Final[int] = 50
```

### Pattern 2: Pure Function Signal Contract (existing in Phase 4)

**What:** Signals consume DataFrames, return DataFrames of identical index. No I/O, no global state.
**When to use:** Every new file in `signals/` and `indicators/`.
**Example:**

```python
# Source: src/screener/signals/composite.py (existing)
def passes_qullamaggie_setup_a(panel: pd.DataFrame) -> pd.DataFrame:
    """Append qullamaggie_score column. Pure: panel-in, panel-out."""
    out = panel.copy()
    # ... computation ...
    out["qullamaggie_score"] = ...
    return out
```

### Pattern 3: Atomic Parquet Write (Phase 2 D-11)

**What:** `tempfile.NamedTemporaryFile(dir=target.parent, ...)` + `os.replace()`. Same-filesystem rename is the only POSIX-atomic primitive.
**When to use:** Every Parquet write in Phase 6 (`fundamentals`, `pattern_audit`).
**Example:** see `persistence._write_parquet_atomic` lines 273–295. New `write_fundamentals_atomic(df, ticker)` and `write_pattern_audit_atomic(df, date)` follow the same shape.

### Pattern 4: Pandera Schema at IO Boundary (Phase 2 D-15)

**What:** Eager validation (`lazy=False`) at write boundary; lazy (`lazy=True`) at read boundary.
**When to use:** `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema`, extended `RankingSnapshotSchema`.
**Example:**

```python
# Source: src/screener/persistence.py validate_at_write / validate_at_read
class FundamentalsSchema(pa.DataFrameModel):
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    fiscal_quarter_end: Series[pd.Timestamp] = pa.Field(nullable=False)
    eps_actual: Series[float] = pa.Field(nullable=True)
    eps_yoy_growth: Series[float] = pa.Field(nullable=True)
    knowable_from: Series[pd.Timestamp] = pa.Field(nullable=False)
    next_earnings_date: Series[pd.Timestamp] = pa.Field(nullable=True)
    next_earnings_hour: Series[str] = pa.Field(isin=["bmo", "amc", "dmh", "unknown"], nullable=False)
    class Config:
        strict = True
        coerce = False
```

### Pattern 5: Data → Signals One-Way Edge (D-13b structural enforcement)

**What:** `signals/` and `indicators/` modules cannot `import` from `data/` — enforced by `tests/test_architecture.py` ALLOWED dict.
**When to use:** This is the structural defense of the 45-day lag. Lag enforcement lives at the persistence read boundary; signals receive pre-filtered data.
**Example:**

```python
# Source: tests/test_architecture.py ALLOWED dict (Phase 1 D-16; D-23 extends)
ALLOWED: dict[str, set[str]] = {
    "data": {"persistence", "config", "obs"},
    "indicators": {"persistence", "config", "obs"},
    "signals": {"indicators", "regime", "persistence", "config", "obs"},
    # NOTE: "data" is NOT in signals' or indicators' ALLOWED set.
    # Phase 6 verifies this — adding `from screener.data.fundamentals import ...`
    # to signals/canslim.py would fail test_layer_import_contract loud.
}
```

### Anti-Patterns to Avoid

- **Putting VCP thresholds in `Settings`** — defeats D-03's defense against in-sample tuning; an operator could quietly bump `final_contraction_depth` to 0.20 to make more picks "pass" without a paper-trade audit trail.
- **Computing fundamentals lag at the SIGNAL layer** — defeats D-13b; signals/ would have to import data/ which violates architecture test.
- **Same-bar entry execution** — Critical Pitfall #4; D-06 confirms the breakout fires on the same EOD bar but ENTRY is next-day open (BCK-02 / Phase 5 harness enforces).
- **Calling `edgartools.set_identity()` lazily inside `data/insider.py`** — D-08: must be called at CLI startup so EDGAR_IDENTITY misconfiguration fails loud once at process start, not silently on the first network call deep in a job.
- **Iterating over weights and hardcoding column references inside the loop** — defeats D-13's M2 extension seam (verified in `signals/composite.py` line 113); Phase 6 adds component helpers ABOVE the loop, not inside it.
- **Strict higher-lows comparison** in flag detection (`each low > prior low`) — too brittle; use tolerant comparison (`each low >= prior low - 0.5 × ATR`) per Code Examples §3.
- **Storing pre-computed pivot prices** across runs — PAT-05 + D-25 forbid; always re-derive from current adjusted closes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Peak/trough detection on price series | Custom zigzag loop with manual neighbor comparisons | `scipy.signal.argrelextrema(arr, np.greater_equal, order=N)` | Named by PAT-01; battle-tested; ~10 LoC vs ~50 LoC custom; well-known `order` parameter for noise tuning |
| SEC EDGAR HTTP rate limiting | Custom token-bucket on `requests` calls to data.sec.gov | `edgartools` (auto-enforced 10 req/sec; `set_rate_limit()` to override) | SEC blocks IPs that exceed rate limits — `edgartools` handles compliance + retry + XBRL parsing |
| Form 4 XBRL parsing | Hand-rolled XML parsing of Form 4 documents | `edgartools.Filing.obj()` returns Form4 object with `.get_transaction_activities()` / `.to_dataframe()` | Form 4 has 30+ transaction codes; parsing is non-trivial |
| Earnings calendar BMO/AMC normalization | Per-source date wrangling across yfinance/Finnhub/Alpha Vantage | Finnhub `/calendar/earnings` returns `hour` field directly (`bmo`/`amc`/`dmh`) | One source, one normalization step; CONTEXT.md D-07 locks |
| HTTP request caching for fundamentals | Custom Parquet/JSON disk cache around `requests.get(...)` | `requests-cache` with 24h expiry (Phase 2 pattern; `docs/data-architecture.md` §7) | Existing repo dependency; SQLite-backed; transparent middleware |
| Atomic Parquet writes | `df.to_parquet(target)` directly (risk of half-written file on crash) | `persistence._write_parquet_atomic(df, target)` | Existing Phase 2 helper; tempfile + `os.replace()` is POSIX-atomic |
| DataFrame schema enforcement | Manual `assert df.columns.tolist() == [...]` and dtype checks | `pandera.DataFrameModel` with `Config.strict = True, coerce = False` | Existing Phase 2 contract; emits structured error with row index on validation failure |
| Composite weight scoring loop | Phase 6 rewriting `score()` to add three more `out["X_component"] = ...` lines individually | Phase 4 D-13's `weights.items()` loop — adding component is one helper + one column assignment ABOVE the loop | Phase 4 already proved this with `pattern_component = 0.0` placeholders; D-16 just removes keys from PHASE_4_ZEROED |
| SQLite append-only writes with crash safety | Manual `INSERT` + `commit()` per row | Single `INSERT ... ON CONFLICT(filing_id) DO NOTHING` in one transaction per nightly batch | SQLite transaction is atomic; `filing_id` PRIMARY KEY makes nightly re-runs idempotent |
| Per-pick playbook tag decision tree | If/else cascade in `publishers/report.py` | Pure function `tag_playbook(panel) -> Series` in `signals/composite.py` (CMP-04) | Co-location requirement; report.py reads the column |

**Key insight:** Every "don't hand-roll" item is already either solved by the existing Phase 1-5 codebase or by a named third-party library. Phase 6's design discipline is to refuse to build alternatives even when they look simpler — the architecture test, the preregistration CI, the no-look-ahead test, and the four golden files are the structural defenses against drift.

## Runtime State Inventory

Phase 6 is a feature-addition phase (no renames or migrations) but it DOES introduce two new persistent datastores. Audit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | NEW datastores: `data/fundamentals/*.parquet` (per-ticker; ~1000 files), `data/insider/form4.sqlite` (single file event log), `data/pattern_audit/YYYY-MM-DD.parquet` (daily; gitignored) | Add `.gitignore` entries; create `.gitkeep` anchors; document policy in directory README (none currently) |
| Live service config | None — Phase 6 introduces no live external service registrations | None |
| OS-registered state | None — no cron/launchd/systemd registrations in Phase 6 (Phase 8 ships GitHub Actions cron) | None |
| Secrets/env vars | NEW env vars required: `FINNHUB_API_KEY` (already in Settings — Phase 1), `EDGAR_IDENTITY` (already in Settings — Phase 1). Both populated in `.env`. **`.env.example` MUST be updated to show these as REQUIRED for Phase 6 onward.** | Update `.env.example`; document in README that Phase 6 needs both keys set or `make fundamentals` fails loud |
| Build artifacts | None — Phase 6 adds new Python modules but no compiled artifacts | None |

**The canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?* — N/A for Phase 6 (no renames). The closest analog is: **after Phase 6 ships, Phase 5 backfill snapshots are missing the 9 new columns until `make backfill-snapshots` is re-run** — addressed in D-22.

## Common Pitfalls

### Pitfall 1: Confusing `auto_adjust=True` with permanent split adjustment

**What goes wrong:** yfinance's `auto_adjust=True` retroactively adjusts the entire history when a new split happens. A pivot stored on 2024-06-09 (pre-split) as a fixed $1200 dollar level becomes meaningless on 2024-06-11 (post-10:1 split = $120).
**Why it happens:** Caching the pivot price as a dollar value instead of re-deriving from current adjusted closes.
**How to avoid:** D-25 + PAT-05: re-derive pivot every run. The 2024-06-10 NVDA golden file (D-02 #3) is the regression gate.
**Warning signs:** A pick's `pivot_price` doesn't match the most recent contraction high in the adjusted-close series.

### Pitfall 2: `argrelextrema(order=N)` silently truncates near edges

**What goes wrong:** Peaks within `N` bars of the array start/end are NOT detected. A breakout on the most recent bar (which is exactly the case the screener cares about) gets missed if `order` is too large.
**Why it happens:** `argrelextrema` requires `N` bars of context on EACH side; the last `N` bars cannot be peaks by definition.
**How to avoid:** Tune `order` against the four golden files. Start with `order=5` (CONTEXT.md §Specifics); reduce if the NVDA 2023-05-25 flag breakout date isn't detected. Pattern detector returns "breakout pending" status (not "no pattern") for bars within `order` of the most recent date.
**Warning signs:** Test fails on golden file #4 (NVDA 2023-05-25 flag) when the pivot date is exactly the most recent bar in the test slice.

### Pitfall 3: `edgartools.set_identity()` failure mode

**What goes wrong:** SEC requires a `User-Agent` header with name + email. If `set_identity()` isn't called, edgartools may either send a default (which SEC blocks) or raise an unfriendly error deep in a network call.
**Why it happens:** Easy to forget at startup; runs work locally because dev machine has identity cached.
**How to avoid:** D-08 + CAT-04: call `set_identity(...)` at the TOP of `cli.py` (composition root) BEFORE any subcommand runs. Fail loud with explicit error message if `EDGAR_IDENTITY` env var is unset AND the subcommand needs EDGAR.
**Warning signs:** First `make fundamentals` run on a CI machine fails with cryptic "403 Forbidden" from data.sec.gov.

### Pitfall 4: Finnhub free tier 60 req/min ceiling

**What goes wrong:** Naive ticker-by-ticker loop calling `/stock/earnings?symbol=AAPL` then `/stock/earnings?symbol=MSFT` ... blows past 60 req/min for a 1000-ticker universe.
**Why it happens:** Per-ticker query is the obvious shape; but Finnhub's `/calendar/earnings` accepts a date range and returns ALL symbols in that window.
**How to avoid:** D-07 + CONTEXT.md §Specifics: use date-range queries (`_from=2026-05-17, to=2026-06-17`) which return ~50 calls/day for the whole universe (not 1000). Cache 24h via `requests-cache`. Per-ticker EPS history (`Ticker.quarterly_income_stmt`) goes through the yfinance throttle pattern (random 0.5–1.5s sleep) — that's ~25 min for 1000 tickers, acceptable for nightly job.
**Warning signs:** Run aborts with 429 Too Many Requests after the first ~60 tickers.

### Pitfall 5: yfinance `.quarterly_earnings` is deprecated

**What goes wrong:** Code written against `Ticker(t).quarterly_earnings` works in yfinance ≤0.2.5, returns deprecation warning in 0.2.6+, and may return None or empty DataFrame in 1.3.x for many tickers.
**Why it happens:** Yahoo retired the underlying endpoint; yfinance maintainers redirected to the income-statement scraper.
**How to avoid:** Use `Ticker(t).quarterly_income_stmt` and extract "Diluted EPS" or "Basic EPS" row. Treat missing data as `eps_actual = NaN` → `earnings_component = 0` per D-13b. Document expected coverage (probably 70-85% of Russell 1000; the rest get `Earnings=0 (EPS data unavailable)` in the report).
**Warning signs:** `make fundamentals` log shows >30% of tickers with `eps_yoy_growth = NaN`.

### Pitfall 6: Composite scorer iteration loop is sacred (D-13 contract)

**What goes wrong:** Adding a new component as `out["pattern_component"] = score_pattern(panel)` *inside* the `for key, w in weights.items()` loop. Now adding a 7th weight key requires editing the loop, defeating the M2 extension seam.
**Why it happens:** Looks simpler in PR diff.
**How to avoid:** D-16 + D-13: helpers run BEFORE the loop, write columns into `out`. The loop iterates `weights.items()` and looks up `out[f"{key}_component"]`. Phase 6 verifies this by adding `ml_probability` to a test (Phase 4 already did this in `test_signals_composite.py::test_extension_seam_ml_probability`).
**Warning signs:** PR diff shows changes inside the `for key, w in weights.items():` block.

### Pitfall 7: SQLite does NOT support `RANGE BETWEEN INTERVAL '<n> days'` on date columns

**What goes wrong:** The canonical insider cluster-buy SQL in CONTEXT.md §Specifics uses `RANGE BETWEEN INTERVAL '4 days' PRECEDING AND CURRENT ROW`. This syntax does NOT parse on SQLite (any version through 3.40+). Only PostgreSQL, MySQL, and Oracle support interval RANGE frames on datetime columns [CITED: caniuse modern-sql; sqlite.org/windowfunctions.html].
**Why it happens:** ANSI SQL feature; SQLite hasn't implemented date-interval RANGE.
**How to avoid:** Two options:
  - **(A) Convert to numeric via `julianday()`** — `RANGE BETWEEN 4 PRECEDING AND CURRENT ROW` after `ORDER BY julianday(transaction_date)`. Works because julianday returns float days.
  - **(B) Python rolling-window post-process** — load `SELECT ticker, transaction_date, insider FROM form4 WHERE type='BUY' AND transaction_date >= date('now', '-30 days')` into pandas, then apply a per-ticker rolling 5-day window. CONTEXT.md D-10 hints at this fallback.
Recommendation: ship (A) as primary, (B) as a unit-test-validated alternative if SQLite version is older than expected.
**Warning signs:** `sqlite3.OperationalError: near "INTERVAL": syntax error` on the first cluster-buy query.

### Pitfall 8: Pattern diagnostics dict not validated by pandera

**What goes wrong:** Snapshot column `pattern_diagnostics` is a JSON-encoded string; pandera `Series[str]` accepts any string. A bug in the encoder writes invalid JSON; downstream report renderer crashes on `json.loads`.
**Why it happens:** Pandera's strict + coerce=False doesn't introspect string contents.
**How to avoid:** Add a `@pa.check("pattern_diagnostics")` custom check that validates each row parses as JSON and has required key `"type"` ∈ {"vcp","flag","none"}. Encode/decode helpers `encode_pattern_diagnostics()` and `decode_pattern_diagnostics()` in `signals/composite.py` (NOT in pandera schema — keep schema as gate-only).
**Warning signs:** Report renders blank pick blocks when one ticker has malformed diagnostics.

### Pitfall 9: `leader_hold` picks accidentally pollute the top-N

**What goes wrong:** D-15 says leader_hold picks go to a SEPARATE report section. If the planner sorts the full panel by `composite_score` and slices `[:top_n]`, leader_hold picks (which can have high RS=99 + Trend=8/8) will dominate the top-N and push out actionable picks.
**Why it happens:** Naive top-N selection.
**How to avoid:** Two-pass selection in `publishers/report.py`:
  1. Filter to `playbook_tag in {"qullamaggie_continuation","minervini_vcp"}`, take top-N — this is the "Top Picks" table.
  2. Filter to `playbook_tag == "leader_hold"`, sort by composite, take all — this is "Currently Held / Leaders".
  3. Picks with `playbook_tag == "none"` are dropped entirely (D-15).
**Warning signs:** First report after Phase 6 ships has zero `qullamaggie_continuation` picks in top-15.

### Pitfall 10: `breakout_strength` formula edge case at 0× volume

**What goes wrong:** D-06 formula `clip((vol / sma_vol_50 - 1.0) / 1.5, 0, 1)` — if `sma_vol_50` is NaN (insufficient history) or 0, division by zero or NaN propagates into `pattern_component`, which propagates into `composite_score`, which makes the pick rank `NaN` (which pandas usually sorts to the bottom but pandera schema may reject).
**Why it happens:** Tickers with <50 bars of history are still in the panel (per RsSnapshotSchema's nullable handling).
**How to avoid:** Wrap the formula: `breakout_strength = ((vol / sma_vol_50 - 1.0) / 1.5).clip(0, 1).fillna(0.0)` — NaN → 0 (no breakout confirmation = no graded score).
**Warning signs:** First production run has tickers with `composite_score = NaN`.

## Code Examples

Verified patterns from official sources.

### Example 1: edgartools startup hook (cli.py)

```python
# Source: edgartools docs https://edgartools.readthedocs.io/en/stable/configuration/
# CITED: SEC requires identity header (10 req/sec rate limit auto-enforced)
from edgar import set_identity
from screener.config import get_settings

def _ensure_edgar_identity() -> None:
    """Fail loud at startup if EDGAR_IDENTITY env var is unset.

    Called from the top of cli.py BEFORE any subcommand runs. If a subcommand
    needs EDGAR access (refresh-fundamentals, score, report) and identity isn't
    set, the error message points at .env.example.
    """
    identity = get_settings().EDGAR_IDENTITY
    if not identity:
        raise SystemExit(
            "EDGAR_IDENTITY env var is unset. SEC requires 'Name <email>' "
            "for User-Agent. See .env.example."
        )
    set_identity(identity)  # idempotent; safe to call repeatedly
```

### Example 2: VCP pivot detection with argrelextrema

```python
# Source: scipy.signal docs + docs/methodology.md §"Pattern Detection — VCP and Flag"
# CITED: scipy 1.17 reference manual
import numpy as np
from scipy.signal import argrelextrema

ORDER: Final[int] = 5  # CONTEXT.md §Specifics default; tune via golden files

def find_pivots(highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return indices of local maxima/minima with `ORDER` bars of context each side.

    Edge effect: peaks within ORDER bars of the start/end are NOT detected
    (see Pitfalls §2). For Phase 6 the most-recent-bar breakout detection
    runs as a separate predicate (close > pivot_price) on the most recent
    confirmed pivot, NOT as a fresh argrelextrema call on the last 5 bars.
    """
    highs_idx = argrelextrema(highs, np.greater_equal, order=ORDER)[0]
    lows_idx = argrelextrema(lows, np.less_equal, order=ORDER)[0]
    return highs_idx, lows_idx
```

### Example 3: Continuation flag with tolerant higher-lows

```python
# Source: docs/methodology.md §"Flag / Continuation pattern"
# Recommendation: tolerant comparison per CONTEXT.md Claude's Discretion
def detect_flag(
    panel_slice: pd.DataFrame,
    bars: int = 15,  # 5–25 range per PAT-03; pick middle
    atr_tolerance: float = 0.5,  # 0.5×ATR slop on higher-lows
) -> dict | None:
    """Detect a 5-25 bar consolidation along rising 10/20/50 SMA.

    PAT-03 criteria:
      - range tightness: each bar's high-low < 1.0 × ATR(20)
      - higher lows: lows[i] >= lows[i-1] - atr_tolerance × atr[i]
      - volume contracting: mean(vol[last_third]) < mean(vol[first_third])
      - close stays above 10-day OR 20-day SMA
    """
    if len(panel_slice) < bars:
        return None
    sl = panel_slice.tail(bars)
    atr = sl["atr_14"]
    # 1. Range tightness
    if not ((sl["high"] - sl["low"]) < atr).all():
        return None
    # 2. Tolerant higher lows
    lows = sl["low"].values
    higher_lows = all(
        lows[i] >= lows[i-1] - atr_tolerance * atr.iloc[i]
        for i in range(1, len(lows))
    )
    if not higher_lows:
        return None
    # 3. Volume contraction
    n3 = bars // 3
    if sl["volume"].iloc[-n3:].mean() >= sl["volume"].iloc[:n3].mean():
        return None
    # 4. MA anchor
    if not (sl["close"] >= sl[["sma_10", "sma_20"]].min(axis=1)).all():
        return None
    return {
        "type": "flag",
        "flag_bars": bars,
        "range_tightness": float(((sl["high"] - sl["low"]) / atr).mean()),
        "vol_contraction_ratio": float(sl["volume"].iloc[-n3:].mean() / sl["volume"].iloc[:n3].mean()),
        "ma_anchor": "10/20/50",
        "pivot_price": float(sl["high"].max()),
    }
```

### Example 4: Finnhub earnings calendar fetch (date-range + 24h cache)

```python
# Source: Finnhub docs https://finnhub.io/docs/api/company-eps-estimates
# CITED: response schema includes `hour` field with values {bmo, amc, dmh}
import finnhub
import requests_cache
import pandas as pd
from datetime import date, timedelta
from screener.config import get_settings

# 24h cache per docs/data-architecture.md §7 + CONTEXT.md D-07
_session = requests_cache.CachedSession(
    "data/cache/finnhub.sqlite",
    expire_after=timedelta(hours=24),
)

def fetch_earnings_calendar(start: date, end: date) -> pd.DataFrame:
    """Fetch ALL upcoming earnings in [start, end] in a single API call.

    Returns DataFrame with columns: symbol, date, hour ('bmo'|'amc'|'dmh'),
    quarter, year, epsActual (nullable), epsEstimate (nullable).
    Universe filter happens at the caller — Finnhub returns all US tickers.
    """
    client = finnhub.Client(api_key=get_settings().FINNHUB_API_KEY)
    # Note: finnhub-python uses _from (leading underscore) because `from` is a Python keyword
    payload = client.earnings_calendar(
        _from=start.isoformat(),
        to=end.isoformat(),
        symbol="",
        international=False,
    )
    rows = payload.get("earningsCalendar", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["hour"] = df["hour"].fillna("unknown").astype(str)
    return df
```

### Example 5: knowable_from filter at persistence read (D-13b lag enforcement)

```python
# Source: D-13b verbatim; pattern is the structural defense of the 45-day lag
import pandas as pd
from pathlib import Path
from screener.persistence import validate_at_read

def read_fundamentals(as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    """Read fundamentals filtered to knowable rows only.

    Signals MUST go through this read path (architecture test enforces).
    Filters `WHERE knowable_from <= as_of_date` so the CANSLIM signal
    cannot accidentally consume same-quarter EPS that fund managers won't
    know about for another 45 days.
    """
    as_of = pd.Timestamp(as_of_date)
    base = Path("data/fundamentals")
    frames = []
    for p in base.glob("*.parquet"):
        df = pd.read_parquet(p)
        df = df[df["knowable_from"] <= as_of]
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "ticker", "fiscal_quarter_end", "eps_actual", "eps_yoy_growth",
            "knowable_from", "next_earnings_date", "next_earnings_hour",
        ])
    full = pd.concat(frames, ignore_index=True)
    return validate_at_read(FundamentalsSchema, full)
```

### Example 6: Qullamaggie Setup A scan (pure)

```python
# Source: CLAUDE.md §"Qullamaggie Breakout (canonical)" SCAN line verbatim
# Uses existing panel columns: rs_rating, adr_pct, volume, close
def passes_qullamaggie_setup_a(panel: pd.DataFrame) -> pd.DataFrame:
    """SIG-02 verbatim: top 1-2% performers over 1m/3m/6m AND ADV > $1.5M AND ADR%(20) >= 4.

    Top 1-2% interpreted as percentile rank (CONTEXT.md Discretion default).
    """
    out = panel.copy()
    # 1m/3m/6m percentile rank — uses close-to-close returns
    grouped = panel.groupby(level="ticker")["close"]
    ret_1m = grouped.pct_change(21)
    ret_3m = grouped.pct_change(63)
    ret_6m = grouped.pct_change(126)
    # Cross-sectional rank within each date
    pct_1m = ret_1m.groupby(level="date").rank(pct=True)
    pct_3m = ret_3m.groupby(level="date").rank(pct=True)
    pct_6m = ret_6m.groupby(level="date").rank(pct=True)
    top_2pct = (pct_1m >= 0.98) | (pct_3m >= 0.98) | (pct_6m >= 0.98)

    # Dollar volume threshold
    dollar_volume = (panel["close"] * panel["volume"]).groupby(level="ticker").rolling(20).mean().droplevel(0)
    liquid = dollar_volume > 1_500_000

    # ADR% threshold
    high_adr = panel["adr_pct"] >= 4.0

    out["qullamaggie_score"] = (top_2pct & liquid & high_adr).astype(int)
    return out
```

### Example 7: CANSLIM C — earnings component (D-18)

```python
# Source: docs/methodology.md §3 CANSLIM C verbatim + D-18 de-dup logic
def score_earnings_component(panel: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.Series:
    """C only — boolean: 1.0 if EPS YoY >= 25% AND knowable, else 0.0.

    L (RS >= 80) is already in rs_component; M (Confirmed Uptrend) is already
    in the regime soft gate. Double-counting would inflate beyond pre-registered
    25% RS weight and the regime multiplier.
    """
    # Take most recent knowable row per ticker
    latest = fundamentals.sort_values("fiscal_quarter_end").groupby("ticker").tail(1)
    latest = latest.set_index("ticker")
    panel_tickers = panel.index.get_level_values("ticker")
    yoy = panel_tickers.map(lambda t: latest["eps_yoy_growth"].get(t, float("nan")))
    component = (yoy >= 0.25).astype(float)
    return pd.Series(component, index=panel.index, name="earnings_component")
```

### Example 8: Playbook tagger with D-14 tie-breaker

```python
# Source: D-12, D-13, D-14, D-15 (all locked decisions)
QULL_MAX_BARS: Final[int] = 25
QULL_MIN_ADR_PCT: Final[float] = 5.0
MINERVINI_MIN_BARS: Final[int] = 25
MINERVINI_MAX_FINAL_CONTRACTION_PCT: Final[float] = 8.0
LEADER_MIN_RS: Final[int] = 90

def tag_playbook(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute playbook_tag + 3 binary scores per pick.

    Tie-breaker (D-14): Qullamaggie wins over Minervini when both fire.
    """
    out = panel.copy()
    # Extract pattern_diagnostics fields safely
    diag = out["pattern_diagnostics"].apply(decode_pattern_diagnostics)
    pattern_type = diag.apply(lambda d: d.get("type", "none"))
    pattern_bars = diag.apply(lambda d: d.get("days_in_consolidation", d.get("flag_bars", 0)))
    final_contraction = diag.apply(lambda d: d.get("final_contraction_depth", 1.0))

    qull = (
        (pattern_type.isin(["vcp", "flag"]))
        & (pattern_bars < QULL_MAX_BARS)
        & (out["adr_pct"] >= QULL_MIN_ADR_PCT)
    )
    minervini = (
        (pattern_type == "vcp")
        & ((pattern_bars >= MINERVINI_MIN_BARS) | (final_contraction * 100 <= MINERVINI_MAX_FINAL_CONTRACTION_PCT))
    )
    leader = (
        out["passes_trend_template"]
        & (out["rs_rating"] >= LEADER_MIN_RS)
        & (pattern_type == "none")
    )
    out["qullamaggie_score"] = qull.astype(int)
    out["minervini_score"] = minervini.astype(int)
    out["leader_hold_score"] = leader.astype(int)

    # Primary tag — D-14: Qullamaggie wins on overlap
    out["playbook_tag"] = "none"
    out.loc[leader & ~qull & ~minervini, "playbook_tag"] = "leader_hold"
    out.loc[minervini, "playbook_tag"] = "minervini_vcp"
    out.loc[qull, "playbook_tag"] = "qullamaggie_continuation"  # last assignment wins → D-14
    return out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `yfinance.Ticker(t).quarterly_earnings` for EPS | `yfinance.Ticker(t).quarterly_income_stmt` filtered to "Diluted EPS" | yfinance 0.2.6 (2023) | CONTEXT.md D-07 mentions both as alternatives — research recommends defaulting to `quarterly_income_stmt` |
| `scipy.signal.argrelextrema` for peak finding | `scipy.signal.find_peaks` with richer parameters | scipy 1.1 (2018; argrelextrema still works in 1.17) | PAT-01 names argrelextrema verbatim — keep, but fall back to `find_peaks` if golden files fail to converge |
| Direct `requests.get('https://data.sec.gov/...')` for EDGAR | `edgartools` with auto-rate-limit + XBRL parsing | edgartools 1.0 (2022); current 5.30.x | `data/insider.py` uses edgartools exclusively |
| `pandas-ta` (PyPI; unmaintained) | `pandas-ta-classic` (fork, actively maintained) | 2024 (per CLAUDE.md "Never use") | Already enforced in Phase 3 |
| Alpha Vantage for fundamentals | Finnhub free tier (60/min) + yfinance + EDGAR | 2024 (Alpha Vantage tightened to ~25/day) | Critical Pitfall #9; CONTEXT.md D-07 locks |
| TA-Lib C for indicators | pandas-ta-classic (pure Python) | Streamlit Cloud incompatibility 2023 | Existing Phase 3 constraint |

**Deprecated/outdated:**
- `Ticker.earnings` (annual): per yfinance docs, "deprecated as not available via API" → use `Ticker.income_stmt` and extract "Net Income"
- `Ticker.quarterly_earnings`: same deprecation path → `Ticker.quarterly_income_stmt`
- IEX Cloud (shut down Aug 2024 per CLAUDE.md) — never an option

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `argrelextrema(order=5)` starting point will converge on all 4 golden files with tuning | Code Examples §2; CONTEXT.md §Specifics | If wrong: planner spends extra wave iterating; fallback to `find_peaks(prominence=...)` is documented |
| A2 | yfinance `quarterly_income_stmt` provides "Diluted EPS" row reliably for ~70-85% of Russell 1000 | Pitfall 5 | If lower coverage: catalyst component still scores 0 for missing; report shows "EPS unavailable" honestly; no incorrect signals |
| A3 | SQLite with `julianday(transaction_date)` numeric RANGE will work on Python 3.11's bundled sqlite3 (3.41+) | Pitfall 7, Code Examples Recommendation A | If wrong: Python rolling-window fallback documented (Option B); functionally equivalent, slightly slower |
| A4 | Phase 6's snapshot schema extension (9 new columns) does not break Phase 5 backfill snapshots IF `make backfill-snapshots` is re-run | D-22 + Pitfall area | If not re-run: Phase 5 harness reads old schema and BCK-04 attribution still shows leader_hold-only stub. Document in CHANGELOG. |
| A5 | `make fundamentals` nightly job completes within GitHub Actions free-tier 6h limit (~25 min for yfinance EPS + ~5 min for Finnhub + ~10 min for EDGAR Form 4 bulk = ~40 min total) | Architecture diagram timing estimate | If exceeded: Phase 8 GitHub Actions workflow may need to split fundamentals into a separate job from rank/report; design today preserves that option |
| A6 | `pattern_diagnostics` JSON string in Parquet column survives pandera strict + coerce=False with `Series[str]` annotation | Pattern 4 example | If wrong: planner adds `@pa.check` custom validator that calls `json.loads()` per row; well-defined fallback |
| A7 | `edgartools.set_filings(form="4", filing_date="YYYY-MM-DD:")` returns ALL Form 4 filings in the date range, not just the most recent N | Code Examples §1 context | If wrong: pagination required; edgartools handles transparently per docs |

**This table is non-empty:** 7 assumptions flagged. The discuss-phase already covered most of the design space — these are tactical implementation assumptions the planner can verify quickly in Wave 0 (a one-day spike on assumption A1 alone may save a full wave of iteration).

## Open Questions

1. **Exact `order` parameter for `argrelextrema`**
   - What we know: start at 5; tune against 4 golden files
   - What's unclear: whether a single `order` works for both VCP (longer consolidation) and flag (5-25 bars)
   - Recommendation: ship two constants — `VCP_PIVOT_ORDER: Final[int] = 5` and `FLAG_PIVOT_ORDER: Final[int] = 3` — let golden files dictate
2. **Whether to include `pattern_diagnostics` JSON in `RankingSnapshotSchema` strict mode**
   - What we know: D-05 stores ~150 bytes/pick as JSON-encoded dict
   - What's unclear: pandera `strict=True` allows it as `Series[str]`, but a custom `@pa.check` validator that calls `json.loads()` per row may slow the write
   - Recommendation: ship without custom validator (treat as opaque string); add validator only if a bug surfaces
3. **Coverage of yfinance EPS data across Russell 1000**
   - What we know: Pitfall 5 documents yfinance brittleness
   - What's unclear: actual coverage % until first production `make fundamentals` run
   - Recommendation: structured-log per-ticker EPS-missing event; emit `eps_coverage_pct` in pipeline_complete event; alert if <70%
4. **Whether `data/insider/form4.sqlite` should be gitignored or committed**
   - What we know: STATE.md "Quick Tasks Completed" deferred this decision for Phase 7 journal.sqlite
   - What's unclear: insider Form 4 is historical SEC data — committing gives reproducible analysis but bloats repo (~100MB/year of accumulated filings)
   - Recommendation: GITIGNORE Phase 6; revisit if Phase 7 commits journal.sqlite (consistency)
5. **EDGAR rate limit during peak nightly hours**
   - What we know: edgartools auto-enforces 10 req/sec
   - What's unclear: SEC may apply stricter limits during peak (per their "new rate control limits" announcement)
   - Recommendation: add `set_rate_limit(5)` defensively in Phase 6; bump to 10 if Phase 8 production runs show no throttling

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scipy (incl. `signal.argrelextrema`) | `indicators/patterns.py` (PAT-01) | ✓ | 1.17.1 [VERIFIED via `uv run python`] | — |
| pandas-ta-classic | reuse of dryup_ratio in flag detection | ✓ | 0.4.47 | — |
| edgar (from edgartools) | `data/insider.py` (CAT-04) | ✓ | declared in pyproject ≥5.30,<6 [VERIFIED imports — module is `edgar`] | None — Finnhub `/insider-transactions` is v1.x deferred |
| finnhub-python | `data/fundamentals.py` (CAT-01, DAT-05) | ✓ | 2.4.28+ [VERIFIED via venv] | None — replacing source breaks DAT-05 |
| yfinance | EPS via `Ticker.quarterly_income_stmt` | ✓ | 1.3.0 | Treat missing as `eps_actual = NaN` → `earnings_component = 0` |
| pandera | 4 new schemas | ✓ | 0.31.1 | — |
| requests-cache | 24h Finnhub cache | ✓ | ≥1.3 (pyproject) | — |
| tenacity | retry on 429 | ✓ | ≥9.1 (pyproject) | — |
| sqlite3 (stdlib) | insider event log | ✓ | Python 3.11.x (SQLite ≥3.41) | — |
| `FINNHUB_API_KEY` env var | Finnhub auth | depends on `.env` | per-machine | None — required for DAT-05 |
| `EDGAR_IDENTITY` env var | SEC User-Agent | depends on `.env` | per-machine | None — fail loud at startup (D-08) |

**Missing dependencies with no fallback:**
- `FINNHUB_API_KEY` and `EDGAR_IDENTITY` env vars are blockers if unset on the operator's machine. **Phase 6 should update `.env.example` to document both as REQUIRED.**

**Missing dependencies with fallback:**
- yfinance EPS coverage gap (Pitfall 5) — handled by treating missing data as `earnings_component = 0`. Honest reflection in report.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + hypothesis 6.x (existing; per pyproject.toml) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] (existing) |
| Quick run command | `uv run pytest tests/test_patterns_golden.py tests/test_canslim_lag.py tests/test_playbook_tagger.py -x` |
| Full suite command | `uv run pytest --no-cov -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DAT-05 | `make fundamentals` runs end-to-end with 45-day lag enforced | integration | `uv run pytest tests/test_canslim_lag.py -x` | ❌ Wave 0 |
| PAT-01 | VCP detector identifies pivots via argrelextrema | unit + golden | `uv run pytest tests/test_patterns_golden.py::test_nvda_2023_vcp -x` | ❌ Wave 0 |
| PAT-02 | VCP threshold criteria (depths, contractions, breakout vol) enforced | unit | `uv run pytest tests/test_patterns_golden.py::test_vcp_thresholds -x` | ❌ Wave 0 |
| PAT-03 | Flag detector recognizes 5-25 bar consolidation, higher lows | unit + golden | `uv run pytest tests/test_patterns_golden.py::test_nvda_2023_flag -x` | ❌ Wave 0 |
| PAT-04 | Post-gap-continuation boolean flag (D-04) | unit | `uv run pytest tests/test_patterns_golden.py::test_post_gap_continuation -x` | ❌ Wave 0 |
| PAT-05 | Pivot re-derived from adjusted closes; survives split | unit | `uv run pytest tests/test_patterns_split.py::test_nvda_2024_split_pivot_continuity -x` | ❌ Wave 0 |
| PAT-06 | Golden-file tests for ≥3 historical setups | regression | `uv run pytest tests/test_patterns_golden.py -x` (4 tests) | ❌ Wave 0 |
| SIG-02 | Qullamaggie Setup A scan filters correctly | unit | `uv run pytest tests/test_qullamaggie.py -x` | ❌ Wave 0 |
| SIG-03 | CANSLIM C+L+M additive; L/M not double-counted | unit | `uv run pytest tests/test_canslim.py::test_no_double_count -x` | ❌ Wave 0 |
| CMP-01 | Composite weights unchanged from Phase 4; sum to 1.0 | unit (existing) | `uv run pytest tests/test_signals_composite.py::test_weights_sum_to_one -x` | ✅ |
| CMP-02 | Each pick emits `playbook_tag` ∈ {qullamaggie_continuation, minervini_vcp, leader_hold, none} | unit | `uv run pytest tests/test_playbook_tagger.py::test_tag_values_valid -x` | ❌ Wave 0 |
| CMP-03 | Tie-breaker matrix (D-14 — Qullamaggie wins on overlap) | unit | `uv run pytest tests/test_playbook_tagger.py::test_d14_tiebreaker -x` | ❌ Wave 0 |
| CMP-04 | `tag_playbook` lives in `signals/composite.py` (co-located) | architectural | `uv run pytest tests/test_architecture.py -x` (existing extended for D-23) | ✅ (extended) |
| CMP-05 | Per-pick component breakdown matches D-19 format | unit | `uv run pytest tests/test_publishers_report.py::test_d19_breakdown_format -x` | ❌ Wave 0 (extend existing) |
| CAT-01 | `days_to_next_earnings` + BMO/AMC populated | unit | `uv run pytest tests/test_fundamentals_io.py::test_earnings_calendar_normalize -x` | ❌ Wave 0 |
| CAT-02 | `crossed_52w_high_within_60d` populated correctly | unit | `uv run pytest tests/test_publishers_snapshot.py::test_52w_high_60d_flag -x` | ❌ Wave 0 (extend existing) |
| CAT-03 | Insider cluster-buy (≥2 insiders in 5-day rolling window over 30 days) | unit | `uv run pytest tests/test_insider_cluster_buy.py -x` | ❌ Wave 0 |
| CAT-04 | `edgartools.set_identity()` called at CLI startup; fails loud if missing | integration | `uv run pytest tests/test_cli_smoke.py::test_edgar_identity_required -x` | ❌ Wave 0 (extend existing) |
| D-13b (lag) | 45-day lag enforced at persistence read; signal cannot bypass | unit | `uv run pytest tests/test_canslim_lag.py::test_lag_enforcement_30d_then_16d -x` | ❌ Wave 0 |
| D-06 (breakout_strength) | `clip((vol/sma50 - 1.0) / 1.5, 0, 1)` graded formula | unit | `uv run pytest tests/test_breakout_strength.py -x` | ❌ Wave 0 |
| D-16 (PHASE_4_ZEROED shrink) | After Phase 6, `PHASE_4_ZEROED == frozenset()` | unit | `uv run pytest tests/test_signals_composite.py::test_phase_4_zeroed_empty -x` | ✅ (extend existing) |
| D-23 (architecture) | `signals/` and `indicators/` cannot import `data/` | architectural | `uv run pytest tests/test_architecture.py::test_layer_import_contract -x` | ✅ (existing already enforces) |
| FND-04 (no-look-ahead) | Phase 5 gate remains green after Phase 6 changes to `signals/` | CI gate | `.github/workflows/no-lookahead-gate.yml` (existing) | ✅ |
| BCK-04 (per-playbook attribution) | Phase 5 harness picks up new playbook tags from snapshots | manual (after backfill) | `make backfill-snapshots && make backtest` | partial (existing harness) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_patterns_golden.py tests/test_canslim_lag.py tests/test_playbook_tagger.py tests/test_breakout_strength.py -x` (~10s, runs the four most load-bearing Phase 6 gates)
- **Per wave merge:** `uv run pytest --no-cov -q` (full suite — ~30s based on 149 tests at end of Phase 5)
- **Phase gate:** Full suite green + `uv run pytest tests/test_backtest_no_lookahead.py` (FND-04 gate must remain green) + manual `make fundamentals && make report` smoke test against live data

### Wave 0 Gaps

- [ ] `tests/test_patterns_golden.py` — 4 golden-file tests (D-02)
- [ ] `tests/test_patterns_split.py` — NVDA 2024-06-10 10:1 split pivot continuity (PAT-05; D-25 regression gate)
- [ ] `tests/test_qullamaggie.py` — Setup A scan synthetic-panel coverage
- [ ] `tests/test_canslim.py` — C-only additive scoring + L/M de-dup verification (D-18)
- [ ] `tests/test_canslim_lag.py` — 45-day lag enforcement (D-13b verbatim)
- [ ] `tests/test_fundamentals_io.py` — Finnhub + yfinance EPS fetch (responses-mocked)
- [ ] `tests/test_insider_io.py` — Form 4 fetch + SQLite write (edgar-mocked)
- [ ] `tests/test_insider_cluster_buy.py` — cluster query against synthetic Form 4 fixture
- [ ] `tests/test_composite_full.py` — all components active; PHASE_4_ZEROED shrink to empty (D-16)
- [ ] `tests/test_playbook_tagger.py` — D-14 tie-breaker matrix (4x4 covering qull/minervini overlap, leader-hold isolation, none-tag pickup)
- [ ] `tests/test_breakout_strength.py` — D-06 graded formula + NaN/0 edge cases (Pitfall 10)
- [ ] Test fixtures: `tests/fixtures/patterns/nvda_2023_vcp.parquet`, `aapl_2020_vcp.parquet`, `nvda_2024_split.parquet`, `nvda_2023_flag.parquet` (extract from existing `data/ohlcv/` or commit small slices)
- [ ] Synthetic fundamentals fixture: `tests/fixtures/fundamentals/` for lag-enforcement test
- [ ] Synthetic Form 4 fixture: `tests/fixtures/form4_cluster.sqlite` for cluster-query test

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (low — API keys, no user auth) | `FINNHUB_API_KEY` + `EDGAR_IDENTITY` via env var; never in code; `.env` gitignored |
| V3 Session Management | no | No user sessions in v1 |
| V4 Access Control | no | Single-user personal-trading tool; no multi-tenant |
| V5 Input Validation | yes | Pandera schemas at every I/O boundary; ticker regex `^[A-Z][A-Z0-9\-]{0,9}$`; snapshot_date regex `^\d{4}-\d{2}-\d{2}$` (existing path-traversal defenses in persistence.py) |
| V6 Cryptography | no | No secret storage beyond env vars; no signing |
| V7 Error Handling | yes | structlog JSON logging; no `print()`; fail-loud for EDGAR identity (D-08); fail-loud for D-13b lag violation (can't actually happen due to structural defense, but documented) |
| V8 Data Protection | yes (low) | API keys not logged; pandera schema rejects malformed Form 4 / earnings rows at write boundary |
| V9 Communication | yes | All API calls use HTTPS (yfinance, Finnhub, edgartools all default HTTPS); `requests-cache` honors HTTPS |
| V10 Malicious Code | yes (low) | All deps pinned with version range in pyproject.toml; no eval/exec |
| V12 Files & Resources | yes | Atomic-write pattern (Phase 2 D-11) prevents half-written files; `_assert_safe_ticker` + `_assert_safe_snapshot_date` block path traversal |
| V13 API & Web Service | yes | EDGAR rate limit auto-enforced by edgartools (10 req/sec); Finnhub 60/min self-enforced via 24h `requests-cache` + date-range queries |

### Known Threat Patterns for Phase 6 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via ticker name in `data/fundamentals/<ticker>.parquet` | Tampering / Info Disclosure | `_assert_safe_ticker()` (existing) — refuses `/`, `\`, `..` before path construction |
| Path traversal via snapshot date in pattern_audit | Tampering | `_assert_safe_snapshot_date()` (existing) — strict `YYYY-MM-DD` regex |
| SEC EDGAR IP block from missing `set_identity()` | DoS (self-inflicted) | D-08: startup hook fails loud BEFORE any subcommand |
| SEC EDGAR IP block from exceeding 10 req/sec | DoS (self-inflicted) | edgartools auto-enforces; `set_rate_limit(5)` defensively |
| Finnhub API key leaked via log | Info Disclosure | structlog default does not log Settings; never pass `api_key=` as a keyword in a logged event |
| Pandera schema bypass via `coerce=True` silently downcasting bad data | Tampering | Repo policy: `coerce=False, strict=True` on all schemas (existing Phase 2 D-15) |
| JSON injection in `pattern_diagnostics` column (malformed dict from buggy encoder) | Tampering | `encode_pattern_diagnostics()` uses `json.dumps(d)` only on validated dicts; consumer side `json.loads()` wrapped in try/except; broken row treated as `{"type": "none"}` |
| SQLite SQL injection in insider cluster-buy query | Tampering | Use parameterized queries (`?` placeholders); never f-string ticker values into SQL |
| In-sample threshold tuning to game backtest | Process / Integrity | D-03 + D-13 lock thresholds as `Final[...]`; D-21 preregistration CI gate prevents drift |
| Survivorship-biased Sharpe quoted without disclosure | Reputational | Critical Pitfall #7; BCK-06 disclosure header already shipped in Phase 5 |

## Sources

### Primary (HIGH confidence)

- **scipy.signal docs** [CITED: Context7 `/scipy/scipy`] — `argrelextrema` and `find_peaks` API
- **edgartools docs** [CITED: Context7 `/dgunning/edgartools`] — Form 4 `get_filings`, `get_ownership_summary`, `set_identity`, `set_rate_limit`
- **Finnhub API docs** [CITED: Context7 `/websites/finnhub_io_api` — https://finnhub.io/docs/api/company-eps-estimates] — `/calendar/earnings` schema with `hour` (bmo/amc/dmh) field
- **pandera docs** [CITED: Context7 `/unionai-oss/pandera`] — `DataFrameModel`, `pa.check`, custom logical dtypes
- **Project CLAUDE.md** — VCP thresholds, Qullamaggie formula, IBD RS, ADR%, critical pitfalls
- **docs/methodology.md** — full VCP/flag algorithm narrative
- **docs/data-architecture.md** — catalyst sources matrix, FinBERT/EDGAR/Reddit splits, 45-day lag rationale
- **`.planning/phases/06-pattern-detection-full-signal-stack-playbook-tagging/06-CONTEXT.md`** — 25 locked decisions
- **`src/screener/`** — Phase 1-5 existing code (persistence, indicators, signals/composite, publishers, data/ohlcv, tests/test_architecture)

### Secondary (MEDIUM confidence)

- **SQLite window functions docs** [VERIFIED: WebSearch — sqlite.org/windowfunctions.html] — confirmed RANGE BETWEEN INTERVAL NOT supported on date columns
- **caniuse modern-sql** [VERIFIED: WebSearch — modern-sql.com/caniuse/over_range_between_(datetime)] — cross-database support matrix confirms SQLite lacks date-interval RANGE
- **yfinance GitHub issues** [VERIFIED: WebSearch — github.com/ranaroussi/yfinance/issues/1345] — documented `quarterly_income_stmt` instability + `.quarterly_earnings` deprecation
- **EdgarTools SEC compliance docs** [VERIFIED: WebSearch — edgartools.readthedocs.io/en/stable/resources/sec-compliance/] — 10 req/sec default rate limit; `set_rate_limit(N)` override

### Tertiary (LOW confidence)

- yfinance EPS coverage % across Russell 1000 — extrapolated from issue threads; first production `make fundamentals` run will yield empirical number

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified in venv; all libraries either named by locked decisions or repo dependencies
- Architecture: HIGH — Phase 1-5 has established every pattern Phase 6 needs (atomic write, pandera, pure-function signal, Final-constant locking, weights-iterating composite)
- Pitfalls: MEDIUM-HIGH — 10 pitfalls documented; SQLite RANGE INTERVAL limitation discovered in research (NOT in CONTEXT.md); yfinance EPS reliability flagged for verification at first production run

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (30 days — stable libraries; revisit if Finnhub/edgartools/scipy ship a breaking release)

---

## RESEARCH COMPLETE
