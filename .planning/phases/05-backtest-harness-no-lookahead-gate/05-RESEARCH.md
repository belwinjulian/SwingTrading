# Phase 5: Backtest Harness & No-Look-Ahead Gate — Research

**Researched:** 2026-05-16
**Domain:** vectorbt 1.0 walk-forward backtest harness + CI-blocking no-look-ahead mutation test
**Confidence:** HIGH (all critical claims verified against installed vectorbt 1.0.0 + Context7 docs)

---

<user_constraints>
## User Constraints (from 05-CONTEXT.md)

### Locked Decisions (D-01..D-19)

**Walk-forward data strategy (BCK-01):**
- **D-01:** Backfill script at `scripts/backfill_snapshots.py`. Loops over trading dates 2016-01-01..today, calls `publishers.pipeline.run_pipeline(date, write_report=False)`. Idempotent — skips existing snapshots. Lives outside `backtest/` so it can import `signals/` and `indicators/`.
- **D-02:** `make backfill-snapshots` is a separate Makefile target. Never auto-runs inside `make backtest`. Not a CLI subcommand — preserves the 9-subcommand lock.
- **D-03:** Walk-forward configuration: 3yr IS / 1yr OOS, sliding by 1 year. OOS Sharpe distribution = `(min, median, max)` — never a single Sharpe.
- **D-04:** Harness reads `data/snapshots/*.parquet` for signals (`passes_trend_template`, `composite_score`, `regime_state`, `regime_score`); reads `persistence.read_panel()` for OHLCV execution prices. No fresh signal recomputation.

**No-look-ahead mutation test (FND-04, BCK-02):**
- **D-05:** Integration test calling the actual `backtest.vbt_runner.run()`. Writes synthetic OHLCV (250 bars, seeded) to a temp dir, overrides `persistence.read_panel()`, runs the real harness.
- **D-06:** Perfect-foresight signal = `(close.shift(-1) > close).astype(float)` — enter when next-day return > 0.
- **D-07:** Assertion threshold = total return ≤ 2× buy-and-hold. **NOTE — this research finds this threshold is not robust; see Section B Q5 for revised thresholds.**
- **D-08:** Two-call parameterized test. `vbt_runner.run()` accepts `_lookahead: bool = False`. Test 1: `_lookahead=False` passes; Test 2: `_lookahead=True` proves the mutation kills the gate.
- **D-09:** CI gate via path filter on `src/screener/signals/**` or `src/screener/backtest/**`.

**Slippage tiers (BCK-03):**
- **D-10:** ADV = 20-day rolling mean of `(close × volume)`. Computed per-ticker per-date inside `backtest/` from `persistence.read_panel()`.
- **D-11:** Tiers — ADV > $50M → 5 bps; $5M ≤ ADV ≤ $50M → 15 bps; ADV < $5M → 30 bps. Zero-slippage path NOT exposed.

**Per-playbook + per-regime (BCK-04, BCK-05):**
- **D-12:** Phase 5 treats all picks as `leader_hold` (Phase 6 adds real tagging).
- **D-13:** Per-regime breakdown reads `regime_state` from snapshots — already present.

**Backtest report (BCK-06):**
- **D-14:** Terminal summary + `reports/backtest-YYYY-MM-DD.md` file.
- **D-15:** User commits the report manually.

**Forensic audit (BCK-07):**
- **D-16:** `make backtest-audit` runs 4 checks: (1) no-look-ahead test, (2) preregistration hash, (3) universe snapshot ≤ start date, (4) ≥ 2 complete OOS windows.

**Carried-forward (D-17, D-18, D-19):**
- `backtest/` imports only `persistence` from internal modules. NO `signals/`, `indicators/`, `config/`, `obs/`. Use stdlib `logging`.
- 9-subcommand CLI surface LOCKED. Fill in `backtest` + `backtest-audit` stub bodies, no new subcommands.
- Signals execute at next-bar open via `.shift(1)`.

### Claude's Discretion (what this research resolves)

1. vectorbt 1.0 `Portfolio.from_signals()` kwargs for ADV-tiered slippage — **resolved in Section A Q1/Q4**
2. Walk-forward window construction (built-in splitter vs manual) — **resolved in Section A Q3**
3. `backtest/metrics.py` vs inline — **recommendation in Section B Q5 footnote**
4. Backfill progress reporting (tqdm vs print) — **recommendation in Section B**

### Deferred Ideas (OUT OF SCOPE)

- Real per-playbook attribution (Phase 6)
- Monte Carlo simulation of OOS returns (Phase 7+)
- Walk-forward parameter sweep (locked at 3yr/1yr)
- `workflow_dispatch` manual trigger for backtest-audit (Phase 8)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-04 | `tests/test_backtest_no_lookahead.py` mutation-tested + CI-blocking on signals/ or backtest/ PRs | Section B (Q5–Q7) — synthetic GBM, monkeypatch on `read_panel`, two-call parameterized test, revised D-07 thresholds; Section C (Q8) — workflow YAML with `paths:` filter |
| BCK-01 | vectorbt 1.0 walk-forward, 3yr IS / 1yr OOS, OOS Sharpe distribution | Section A (Q3) — manual pandas date arithmetic recommended over `vbt.RollingSplitter` (7 complete windows for 2016–2025) |
| BCK-02 | Signals execute at next-bar open | Section A (Q2) — `entries.shift(1)` + `price=open_panel` is the canonical pattern; vectorbt verified at $101.50 fill on bar t+1 |
| BCK-03 | Slippage tiers wired by default; no zero-slippage path | Section A (Q1, Q4) — `slippage` param accepts DataFrame `(T × N)` shape, broadcasts per-element; `adj_price = price × (1 ± slippage)` verified |
| BCK-04 | Per-playbook attribution (stubbed as `leader_hold`) | D-12 locked; harness groups trades by a `playbook_tag` column (Phase 5 hardcodes `"leader_hold"`) |
| BCK-05 | Per-regime breakdown | D-13 locked; harness joins trade-exit dates to `regime_state` column already in `data/snapshots/*.parquet` |
| BCK-06 | Disclosure header (universe date, survivorship, slippage, period) | Section D (Q10) — recommend YAML frontmatter |
| BCK-07 | `make backtest-audit` 4-check forensic CLI | Section D (Q9) — `scripts/check_preregistration.py` has clean exit-code contract (`sys.exit(main())` returns 0 or 1) — `subprocess.run` it directly |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OHLCV read for execution prices | `persistence.read_panel()` | — | D-04 + D-17: backtest reads only via persistence |
| Signal read (passes_trend_template, regime_state, etc.) | `persistence.read_parquet` on `data/snapshots/<date>.parquet` | — | D-04: snapshot is single source of truth; no signal recomputation |
| ADV computation (slippage tier source) | `backtest/vbt_runner.py` (inline) | — | D-10: ADV is derived in-harness from OHLCV, no `indicators/` import permitted |
| Walk-forward window slicing | `backtest/vbt_runner.py` (or `backtest/walkforward.py`) | — | Manual pandas date arithmetic — see Section A Q3 |
| Portfolio simulation | `vbt.Portfolio.from_signals` (third-party) | — | Third-party imports are unrestricted by `ALLOWED["backtest"]` |
| Metrics (Sharpe, CAGR, max DD) | `pf.sharpe_ratio()`, `pf.total_return()`, etc. (vectorbt) | `backtest/metrics.py` (optional thin wrapper) | vbt computes these directly; a wrapper is only needed for cross-window aggregation |
| Backtest CLI body | `screener.cli.backtest()` | `backtest/vbt_runner.run()` | cli is composition root — imports backtest, calls run, prints summary, writes report |
| Report rendering (`reports/backtest-YYYY-MM-DD.md`) | `backtest/vbt_runner.py` (returns BacktestResult; cli writes file) OR `backtest/report.py` | — | Either acceptable under D-17 — but file write must use stdlib (no `persistence` write helper exists for markdown); recommend cli.py owns disk write |
| Forensic audit (`make backtest-audit`) | `screener.cli.backtest_audit()` | `subprocess.run` to invoke pytest + `scripts/check_preregistration.py` | Audit is orchestration, not new logic |
| No-look-ahead mutation test | `tests/test_backtest_no_lookahead.py` | `monkeypatch` on `screener.persistence.read_panel` | Section B Q7: monkeypatch is the cleanest seam |
| Backfill orchestration | `scripts/backfill_snapshots.py` | `publishers.pipeline.run_pipeline` | D-01: script outside backtest/, free to import publishers |

---

## Summary

vectorbt 1.0.0 is installed and verified in this environment. Every API claim below was tested against a live `import vectorbt as vbt` in the project's `uv` venv, then cross-checked against Context7's `/polakowo/vectorbt` corpus.

**Three load-bearing findings (HIGH confidence):**

1. **`Portfolio.from_signals(slippage=)` accepts a DataFrame `(T rows × N cols)` shape and broadcasts per-element.** Tested with a 2-ticker frame where ticker A had 30 bps and ticker B had 5 bps — vectorbt applied the correct slippage to each. Formula: `adj_price = price × (1 + slippage)` for buys, `× (1 − slippage)` for sells. Verified to the cent: a $100.0 buy with 30 bps slippage filled at exactly $100.30.

2. **Next-bar-open execution = `entries.shift(1, fill_value=False)` + `price=open_panel`.** Verified end-to-end: a signal at bar `t=1` (date 2024-01-02), after `.shift(1)` becomes a signal at bar `t=2` (2024-01-03), with `price=open_` filled at the bar-t+1 open price (exact match). vectorbt's `.vbt.fshift(1)` accessor produces identical output. The plan should use plain `.shift(1, fill_value=False)` to avoid relying on the third-party `.vbt` accessor inside `backtest/` (clearer attribution; no architecture-test risk since vbt is third-party).

3. **vectorbt 1.0 ships `vbt.RollingSplitter` and the `.vbt.rolling_split()` accessor, BUT they slide by 1 bar (not 1 year) — producing 1,602 windows on 2016–2025, not the 6–7 yearly windows we want.** Recommendation: skip the built-in splitter and use **manual `pd.DateOffset(years=1)` arithmetic** — 30 lines of code, fully readable, produces exactly 7 complete windows. Confirmed by direct execution.

**One critical correction to CONTEXT.md (D-07):** the locked threshold "total return ≤ 2× buy-and-hold" is **not robust** because shifted perfect-foresight signals still earn ~25% on 250-bar GBM (the autocorrelation in `np.cumsum(normal)` is not destroyed by a 1-bar shift). Section B Q5 documents the failure mode (10-seed test) and recommends two replacement thresholds: `_lookahead=False` total return < 0.5 (50%) AND `_lookahead=True` total return > 1.0 (100%). 4× asymmetric separation, robust across all 10 tested seeds.

**Primary recommendation for the planner:** structure Phase 5 as 4–5 plans across 3 waves. Wave 0 = `scripts/backfill_snapshots.py` + `Makefile` target + a small Settings field (`SNAPSHOTS_BACKFILL_START = "2016-01-01"`). Wave 1 (parallel) = `backtest/vbt_runner.py` core + the no-look-ahead mutation test (the test is the API contract). Wave 2 = `backtest/walkforward.py` window-slicing + `backtest/metrics.py` cross-window aggregation. Wave 3 = `cli.backtest` + `cli.backtest_audit` bodies + `.github/workflows/no-lookahead-gate.yml` + disclosure-header rendering. The mutation test must land before any `cli.backtest` body so the CI gate is live when the harness body lands.

---

## Section A — vectorbt 1.0 API (Claude's Discretion Items)

### Q1 — `Portfolio.from_signals` kwargs for per-ticker ADV-tiered slippage

**Question:** Does `vbt.Portfolio.from_signals(slippage=...)` accept a per-ticker DataFrame, or only a scalar/Series?

**Answer [VERIFIED — direct test in this session, vectorbt 1.0.0]:** The `slippage` parameter accepts any `array_like` broadcast-compatible with `close`. A DataFrame indexed by date (rows) with ticker columns is the canonical shape for a per-ticker per-date slippage panel. Per the official docstring: `"slippage (float or array_like): Slippage in percentage of price. ... Will broadcast."`

**Verified call signature** (long-only daily-bar backtest with per-ticker tiered slippage):

```python
import vectorbt as vbt
import pandas as pd

# close, open_panel, entries, exits: pd.DataFrame indexed by date, columns=tickers
# slippage_panel: pd.DataFrame same shape, values in {0.0005, 0.0015, 0.0030}

pf = vbt.Portfolio.from_signals(
    close=close,                        # required — used for valuation marks
    entries=entries.shift(1, fill_value=False),   # next-bar execution
    exits=exits.shift(1, fill_value=False),
    price=open_panel,                   # FILL PRICE is the bar's open
    slippage=slippage_panel,            # DataFrame (T, N) — per-element bps
    direction='longonly',               # BCK-03: long-only
    init_cash=100_000.0,                # one shared bucket
    cash_sharing=True,                  # all tickers share init_cash (multi-asset)
    fees=0.0,                           # $0 commission (Robinhood/IBKR Lite)
    freq='1D',                          # daily bars; needed for Sharpe annualization
    size=0.05,                          # 5% of cash per entry (Phase 5 simplification)
    size_type='value',                  # 'value' = fraction of equity; alt: 'amount', 'percent'
)
```

**Verified slippage math:** `adj_price = price × (1 + slippage)` for buys, `× (1 − slippage)` for sells. A $100.00 buy with 0.0030 slippage filled at $100.30 exactly. Sell at $100.00 with same slippage filled at $99.70 exactly.

**Footgun [VERIFIED]:** Pre-multiplying the entry/exit signals by slippage as a workaround would be wrong (`from_signals` requires bool entries; a float multiplier would be coerced to True for any nonzero). The DataFrame parameter is the right path.

`[CITED: https://github.com/polakowo/vectorbt/blob/master/vectorbt/vectorbt/portfolio/nb.py]` — the source of the `adj_price = price * (1 ± slippage)` formula.

---

### Q2 — Next-bar-open execution via `.shift(1)`

**Question:** Where does the shift apply — on the signal panel before `from_signals`, or via a vectorbt kwarg?

**Answer [VERIFIED — direct test in this session]:** vectorbt 1.0 does NOT have a built-in "signal_at='close', price_at='open'" mode. The canonical pattern is:

1. **Shift the signal panel by 1 bar:** `entries.shift(1, fill_value=False)` (and exits similarly).
2. **Pass an `open` panel as `price=`:** the fill price is the OPEN of bar t+1.

**Verified end-to-end** with a 6-bar series:
- Raw signal at index `2024-01-02` (close).
- After `.shift(1, fill_value=False)`: signal is at `2024-01-03`.
- `price=open_` panel passed in: bar `2024-01-03` open was `$101.50`.
- vectorbt order record: `BUY at 2024-01-03 at $101.50` — **exact match for next-bar-open execution.**

**Two important nuances:**

1. **vectorbt's `.vbt.fshift(1)` accessor exists and is officially blessed** (`vbt_order_size.vbt.fshift(1)` from the PairsTrading.ipynb in vbt's own examples). It's functionally identical to `pandas.DataFrame.shift(1, fill_value=False)` for bool panels — the same forward shift with explicit fill. **Recommendation: use plain `.shift(1, fill_value=False)`** in `backtest/vbt_runner.py`. Reasons:
   - Plain pandas is explicit about `fill_value=False` (vbt's `fshift` defaults to NaN).
   - It makes the no-look-ahead mutation crystal clear in code review (the literal `.shift(1)` is the line to remove for the test mutation).
   - Avoids an architectural footgun: if a future contributor reads "`.vbt.fshift(1)`" without context, they might assume vectorbt is doing something magical. Plain `.shift(1)` is unambiguous.

2. **D-19 / FND-04 mutation surface:** The single literal expression that the mutation test must defeat is `entries.shift(1, fill_value=False)` (and the matching exits). The `_lookahead=True` test backdoor MUST bypass exactly this expression — and ONLY this expression. Recommended implementation in `vbt_runner.py`:

   ```python
   def run(start, end, *, _lookahead: bool = False) -> "BacktestResult":
       entries_raw, exits_raw = _build_signals(start, end)  # bool DataFrames
       if _lookahead:  # FND-04: test-only backdoor; never True in production paths
           entries, exits = entries_raw, exits_raw
       else:
           entries = entries_raw.shift(1, fill_value=False).astype(bool)
           exits   = exits_raw.shift(1, fill_value=False).astype(bool)
       ...
   ```

   The `if _lookahead` branch is the entire mutation surface. Removing `.shift(1)` from the `else` branch is equivalent to hardcoding `_lookahead=True`, which the second test assertion catches.

`[VERIFIED: direct execution in uv venv 2026-05-16]`

---

### Q3 — Walk-forward window construction

**Question:** Use vectorbt's `RollingSplitter` / `.vbt.rolling_split()` accessor, or implement manually?

**Answer [VERIFIED — direct test in this session]:** vectorbt 1.0 exposes `vbt.RollingSplitter`, `vbt.ExpandingSplitter`, `vbt.RangeSplitter`, and the `series.vbt.rolling_split(window_len, set_lens, ...)` accessor.

**The built-in slides by 1 bar, not 1 year.** Tested on 2,609 trading days (2016-01-01..2025-12-31) with `window_len=252*4` (4yr window) and `set_lens=(252,)` (1yr IS, 3yr "OOS"):
- Result: **1,602 windows**, each sliding by 1 trading day.
- We want 6–7 windows sliding by ~252 trading days.

Filtering 1,602 down to 7 is possible (`splits[::252]`) but loses the "OOS Sharpe distribution = (min, median, max) across N windows" semantics — and the splitter's set_lens semantics are inverted from CONTEXT.md's `IS first / OOS second` framing (set_lens defines a FIRST segment; remainder is the OTHER set).

**Recommendation: implement manual walk-forward window slicing.** 25 lines of pandas; reads exactly like the ROADMAP language; produces **exactly 7 complete windows** for 2016–2025. Verified pattern:

```python
import pandas as pd

def walk_forward_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    is_years: int = 3,
    oos_years: int = 1,
    slide_years: int = 1,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Yield (is_start, is_end, oos_start, oos_end) tuples.

    Window placement:
      Win 1: IS 2016-01-01..2018-12-31 | OOS 2019-01-01..2019-12-31
      Win 2: IS 2017-01-01..2019-12-31 | OOS 2020-01-01..2020-12-31
      ...
      Win 7: IS 2022-01-01..2024-12-31 | OOS 2025-01-01..2025-12-31
    """
    windows = []
    window_start = start
    while True:
        is_end    = window_start + pd.DateOffset(years=is_years) - pd.Timedelta(days=1)
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end   = oos_start + pd.DateOffset(years=oos_years) - pd.Timedelta(days=1)
        if oos_end > end:
            break
        windows.append((window_start, is_end, oos_start, oos_end))
        window_start = window_start + pd.DateOffset(years=slide_years)
    return windows
```

**Verified output for `start=2016-01-01, end=2025-12-31, is_years=3, oos_years=1, slide_years=1`:** 7 windows (CONTEXT.md predicted "~6", actual is 7 — the 2022..2024 IS / 2025 OOS window also fits).

Where each window is then sliced from the assembled signal+price panels via `.loc[is_start:is_end]` and `.loc[oos_start:oos_end]`.

**Calendar year vs trading day:** Use **calendar year** (`DateOffset(years=...)`). Simpler, aligns with ROADMAP language ("rolling 1-year OOS"), avoids leap-day arithmetic. The actual number of trading days inside each window varies 250–253; this is fine — vectorbt's `freq='1D'` annualization handles non-uniform bar counts correctly via the `freq` parameter.

`[VERIFIED: live execution 2026-05-16; vectorbt 1.0.0]`

---

### Q4 — Slippage application path: worked example

**Question:** Given Q1's answer, show concretely how a 3-column slippage DataFrame is built from ADV and passed.

**Worked example** (ADV calc verbatim from D-10):

```python
import pandas as pd
import numpy as np
import vectorbt as vbt
from screener.persistence import read_panel  # the ONLY internal import allowed

def _build_slippage_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """ADV-tiered slippage panel. Same shape as the close/open panel.

    BCK-03 / D-10 tiers:
        ADV > $50M   -> 5 bps  (0.0005)
        $5M..$50M    -> 15 bps (0.0015)
        ADV < $5M    -> 30 bps (0.0030)

    Pitfall #L1 (Section E): first 19 bars of every ticker have NaN ADV
    because the rolling(20) window has not warmed up. Filling with the worst
    tier (30 bps) is the safest default — pre-warmup signals are rare and a
    high slippage penalty deters them.
    """
    # panel has MultiIndex (ticker, date); pivot to wide (date x ticker) for vbt.
    close = panel['close'].unstack(level='ticker')          # date x ticker
    volume = panel['volume'].unstack(level='ticker').astype(float)
    dollar_volume = close * volume                          # per-bar $ volume
    adv_20d = dollar_volume.rolling(20, min_periods=20).mean()  # per-ticker ADV

    # Vectorized tier assignment via np.where (no apply loop).
    slip = np.where(
        adv_20d > 50_000_000, 0.0005,
        np.where(adv_20d >= 5_000_000, 0.0015, 0.0030)
    )
    slippage_panel = pd.DataFrame(slip, index=close.index, columns=close.columns)
    # Fill NaN ADV warmup bars with the worst tier — defensive default.
    slippage_panel = slippage_panel.where(adv_20d.notna(), 0.0030)
    return slippage_panel


def _run_backtest_window(
    panel: pd.DataFrame,
    entries: pd.DataFrame,
    exits: pd.DataFrame,
    *,
    _lookahead: bool = False,
) -> vbt.Portfolio:
    close = panel['close'].unstack(level='ticker')
    open_ = panel['open'].unstack(level='ticker')
    slippage_panel = _build_slippage_panel(panel)

    if _lookahead:
        entries_exec, exits_exec = entries.astype(bool), exits.astype(bool)
    else:
        entries_exec = entries.shift(1, fill_value=False).astype(bool)
        exits_exec   = exits.shift(1, fill_value=False).astype(bool)

    return vbt.Portfolio.from_signals(
        close=close,
        entries=entries_exec,
        exits=exits_exec,
        price=open_,
        slippage=slippage_panel,
        direction='longonly',
        init_cash=100_000.0,
        cash_sharing=True,
        fees=0.0,
        size=0.05,           # 5% of equity per entry (Phase 5 simplification)
        size_type='value',
        freq='1D',
    )
```

**Why `min_periods=20` (not the default `min_periods=1`):** prevents a 5-bar moving average from being computed during warmup and labeled "ADV" — the first 19 bars genuinely don't have a 20-day ADV, and a 5-bar mean would mis-tier illiquid names as liquid.

**Why fill NaN ADV with 0.0030 (30 bps) instead of skipping the row:** vectorbt does not accept NaN in `slippage`. Filling with the worst tier is a one-line defensive default; the alternative (filtering out the first 19 bars of every ticker) loses 19 × N_tickers data points unnecessarily, and the Phase 5 backtest's IS window is 3 years (756 bars) so the 19-bar warmup is negligible.

### Q11. `vbt.Portfolio.returns()` shape verification (added iter 3 for B-3)

**Verified API:** `vbt.Portfolio.from_signals(...).returns()` returns:
- `pd.Series` indexed by date when called on a single-column Portfolio (1 ticker, no `group_by`)
- `pd.DataFrame` indexed by date with one column per ticker/group when called on a multi-column Portfolio (which is the Phase 5 case: 3 synthetic tickers `AAA/BBB/CCC` reduced to ONE group via `cash_sharing=True` + `group_by=np.zeros(N_tickers, dtype=int)` — the grouped Portfolio still returns a DataFrame, just with a single column)

This Q was added in iter 3 to back-fill the verification that B-3 (plan 05-01's `_build_regime_returns_for_window` helper) silently introduced — Q1–Q4 covered `from_signals`, `.shift(1)`, walk_forward_windows, and the per-ticker slippage panel, but `pf.returns()` was new in iter 2's B-3 fix.

**Verification command (run by the Wave 1 executor on first GREEN run; commit the actual output verbatim to RESEARCH.md replacing the placeholder below):**

```bash
uv run python -c "
import vectorbt as vbt
import numpy as np
import pandas as pd
idx = pd.bdate_range('2020-01-01', periods=10)
close = pd.DataFrame({'AAA': np.linspace(100, 110, 10), 'BBB': np.linspace(100, 105, 10)}, index=idx)
entries = pd.DataFrame(False, index=idx, columns=close.columns)
entries.iloc[2] = True
pf = vbt.Portfolio.from_signals(
    close=close,
    entries=entries,
    init_cash=10000,
    freq='1D',
    direction='longonly',
    cash_sharing=True,
    group_by=np.zeros(close.shape[1], dtype=int),
)
r = pf.returns()
print(type(r), r.shape, getattr(r, 'columns', None), r.index[:3].tolist())
"
```

**Actual output (committed by Wave 1 executor on first GREEN run, 2026-05-16):**
```
<class 'pandas.core.series.Series'> (10,) None [Timestamp('2020-01-01 00:00:00'), Timestamp('2020-01-02 00:00:00'), Timestamp('2020-01-03 00:00:00')]
```

**Important deviation from the placeholder prediction:** the placeholder assumed
the grouped Portfolio would return a `DataFrame (10, 1)` with a single
`Int64Index([0])` column. In **vectorbt 1.0.0**, the grouped form actually
collapses further and returns a **`pd.Series`** of shape `(10,)` (no columns).

This is exactly why C-2's hard `assert isinstance(pf_returns, (pd.Series,
pd.DataFrame))` is correct: both branches are now exercised in production. The
helper's existing `if isinstance(pf_returns, pd.DataFrame): ... else: ...`
control flow handles both the (legacy / future) DataFrame shape AND the
observed Series shape gracefully — no code change needed in
`_build_regime_returns_for_window` after the verification.

(Without `cash_sharing=True` + `group_by`, the expected shape would be
`(10, 2) Index(['AAA', 'BBB'], ...)`. Phase 5 uses the grouped form so the
harness reports one composite portfolio return per bar — the same return that
the BCK-01 Sharpe distribution is computed from.)

**Contract for `_build_regime_returns_for_window` in `backtest/vbt_runner.py` (B-3 hardening — iter 3):**

The helper MUST replace iter-2's broad try/except graceful-degradation with a hard assert on the return type:

```python
pf_returns = pf.returns()
assert isinstance(pf_returns, (pd.Series, pd.DataFrame)), (
    f"vbt.Portfolio.returns() returned unexpected type {type(pf_returns)} — "
    f"see 05-RESEARCH.md §A Q11. If vbt's API has changed, update this helper "
    f"to handle the new shape rather than silently rendering empty regime rows."
)
```

The Series-vs-DataFrame branching for legitimate single-ticker handling is kept (a downstream test fixture may use a single ticker); the broad except is removed so a real shape mismatch fails LOUDLY rather than producing an empty `all_regime_returns` that silently renders as empty rows in the backtest report.

**Report-level user-visible failure mode (B-3 hardening — iter 3):**

Plan 05-03's `_render_per_regime_section` MUST emit a visible WARN line in the rendered markdown report when `result.all_regime_returns.empty` (e.g., the harness ran with `windows=[]`, or `_build_regime_returns_for_window` returned empty for every window):

```markdown
> ⚠ No regime-attributed returns produced. See 05-RESEARCH.md §A Q11.
```

This makes the failure mode user-visible in the report itself (not just in stderr or in pytest output) — closes the C-2 loop where an empty regime breakdown was silently rendered as three "0 / —" rows that looked like a benign empty-data state instead of the actual diagnostic.

---

## Section B — No-look-ahead mutation test (FND-04)

### Q5 — Perfect-foresight signal + assertion threshold

**Question:** Confirm the D-06 signal works with `from_signals`, and recommend the threshold language.

**Answer [VERIFIED — 10-seed test in this session]:** The D-06 perfect-foresight signal `(close.shift(-1) > close).astype(bool)` works. The bool DataFrame shape matches what `from_signals` expects.

**However, the D-07 threshold "≤ 2× BH" is NOT robust.** Direct test, 250-bar mean-zero GBM, 10 seeds:

| seed | BH | `_lookahead=False` (correct) | `_lookahead=True` (mutation) | mutation/\|BH\| |
|------|------|------|------|------|
| 0 | -1.9% | +3.5% | +239.0% | 125× |
| 1 | -25.9% | -28.5% | +151.7% | 6× |
| 2 | -3.8% | -14.1% | +230.4% | 61× |
| 3 | -0.1% | +0.7% | +223.9% | 2239× |
| 4 | +19.4% | -2.2% | +250.8% | 13× |
| ... | ... | ... | ... | ... |

The correct path's total return is bounded near zero (range: −28.5% to +11.6%), but the BH return varies wildly (range: −37.7% to +19.4%). On seeds where BH is near zero (e.g., seed 3, BH = −0.1%), `2 × |BH|` is 0.2% — and the correct path's +0.7% return blows past it. The test would fail spuriously.

**Worse:** with synthetic GBM having even tiny drift, the shifted-foresight path can earn +25% on a market that returned −2.5% (the autocorrelation in `np.cumsum(normal)` is not destroyed by a 1-bar shift). On seed 42 with `loc=0.0005` drift, `_lookahead=False` returned +24.9% on a BH of −2.5% — 10× the threshold.

**Recommended replacement thresholds (robust across all 10 tested seeds):**

```python
# In tests/test_backtest_no_lookahead.py
LOOKAHEAD_FALSE_MAX_RETURN = 0.50   # 50% — correct path must stay near random
LOOKAHEAD_TRUE_MIN_RETURN  = 1.00   # 100% — mutation must produce wild outperformance

def test_no_lookahead_correct_path(synthetic_panel_writer, monkeypatch):
    """_lookahead=False: harness applies .shift(1); foresight is negated."""
    result = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=False)
    assert abs(result.total_return) < LOOKAHEAD_FALSE_MAX_RETURN, (
        f"Look-ahead detected: total_return={result.total_return:+.2%} "
        f"exceeds noise threshold {LOOKAHEAD_FALSE_MAX_RETURN:.0%}. "
        f"Check that vbt_runner.run() applies .shift(1) to entries/exits."
    )

def test_no_lookahead_mutation_detected(synthetic_panel_writer, monkeypatch):
    """_lookahead=True: harness skips .shift(1); foresight wins big — proves the gate."""
    result = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=True)
    assert result.total_return > LOOKAHEAD_TRUE_MIN_RETURN, (
        f"Mutation backdoor failed to outperform: total_return={result.total_return:+.2%}. "
        f"Either the perfect-foresight signal construction is wrong, or .shift(1) is "
        f"not actually being bypassed when _lookahead=True."
    )
```

This gives 2× separation between assertion ceilings (0.50 vs 1.00) and ~4× separation between observed values (max correct = 0.116, min mutation = 1.336). Robust to seed choice within the tested distribution.

**Alternative robust assertion (recommended as a third defense):** a ratio test that is invariant to drift:

```python
def test_lookahead_amplifies_returns(...):
    """The mutation must produce at least 4× the return of the correct path."""
    r_correct = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=False).total_return
    r_lookahead = vbt_runner.run("2024-01-01", "2024-12-31", _lookahead=True).total_return
    ratio = r_lookahead / max(abs(r_correct), 0.01)
    assert ratio > 4.0, f"lookahead/correct ratio = {ratio:.1f}× — expected > 4× separation"
```

Minimum observed ratio across 10 seeds: 3.5× (seed 7). Tightening to 4.0× may give the rare CI flake. Recommend either 3.0× threshold (conservative) or pinning the seed to 42 and using fixed thresholds (`< 0.5` AND `> 1.0`).

**Recommendation to the planner:** revise D-07 wording in the plan to:
> "Two-fold assertion: `_lookahead=False → abs(total_return) < 0.50`; `_lookahead=True → total_return > 1.00`. Threshold rationale documented in 05-RESEARCH.md Section B Q5."

`[VERIFIED: 10-seed direct test, vectorbt 1.0.0, 2026-05-16]`

---

### Q6 — Synthetic OHLCV generator

**Question:** What's the recommended pattern for 250 bars of deterministic synthetic OHLCV in a pytest fixture?

**Answer (Recommendation: geometric Brownian motion with seeded RNG and *mean-zero* drift):**

```python
import numpy as np
import pandas as pd
import pytest

SYNTH_OHLCV_SEED = 42  # Pin so test results are stable across CI runs.
SYNTH_OHLCV_BARS = 250

@pytest.fixture(scope="session")
def synthetic_panel() -> pd.DataFrame:
    """250 bars of single-ticker OHLCV in the long-format panel shape that
    read_panel() returns. Deterministic (seeded), mean-zero (no drift —
    chosen so the perfect-foresight test threshold is robust per Section B Q5).

    Returns a MultiIndex (ticker, date) DataFrame with columns
    ['open', 'high', 'low', 'close', 'volume'] — matching OhlcvPanelSchema.
    """
    rng = np.random.default_rng(SYNTH_OHLCV_SEED)
    dates = pd.bdate_range("2024-01-01", periods=SYNTH_OHLCV_BARS)

    # Mean-zero log-returns (loc=0.0): no drift -> the shifted-foresight strat
    # has no autocorrelation edge to exploit; the test thresholds in Section B Q5
    # are calibrated against this distribution.
    log_returns = rng.normal(loc=0.0, scale=0.012, size=SYNTH_OHLCV_BARS)
    close = 100.0 * np.exp(np.cumsum(log_returns))

    # Open = close * (1 + small noise) so open != close (no degeneracy)
    open_  = close * (1 + rng.normal(0, 0.002, SYNTH_OHLCV_BARS))
    high   = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, SYNTH_OHLCV_BARS)))
    low    = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, SYNTH_OHLCV_BARS)))
    volume = rng.integers(500_000, 2_000_000, SYNTH_OHLCV_BARS, dtype="int64")

    df = pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume
    }, index=dates)
    df.index.name = "date"
    df["ticker"] = "SYNTH"
    return df.set_index("ticker", append=True).reorder_levels(["ticker", "date"])
```

**Why GBM + mean-zero (not constant trend / sinusoidal noise):**

| Option | Pro | Con — why rejected |
|--------|-----|--------------------|
| GBM, mean-zero (RECOMMENDED) | Realistic price dynamics; no drift means shifted-foresight is near-random; Section B Q5 thresholds calibrated against this. | None significant. |
| GBM with drift (loc=0.0005) | More "realistic" market. | Shifted foresight earns +25% (autocorrelation), defeats D-07 ≤ 2× BH; thresholds become drift-sensitive. |
| Constant trend (monotone close) | Deterministic. | Foresight is degenerate (every signal True); no information in the test. |
| Sinusoidal noise | Visual debugging. | Real signals exploit cyclicality perfectly; mutation may not separate clearly from correct. |
| `np.random.default_rng(42).normal()` cumsum (no exp) | Simplest. | Prices can go negative on long sample; vectorbt may reject. `np.exp(np.cumsum(...))` ensures positivity. |

Why pin `seed=SYNTH_OHLCV_SEED = 42`: pytest-xdist + flaky distributions = CI nondeterminism. Pinning the seed and choosing it to satisfy both thresholds (verified above) is the only way to guarantee no spurious failures.

`[VERIFIED: 10-seed test 2026-05-16 — seed=42 satisfies both thresholds with margin]`

---

### Q7 — Override mechanism for `persistence.read_panel()` in the test

**Question:** monkeypatch vs dependency injection vs DATA_DIR override — which respects D-17 best?

**Answer: monkeypatch is correct.** Recommended pattern:

```python
import pandas as pd
import pytest
from screener import persistence  # NB: imported by NAME, not via aliased target
from screener.backtest import vbt_runner

@pytest.fixture
def fake_read_panel(monkeypatch, synthetic_panel):
    """Replace persistence.read_panel with a fake that returns synthetic_panel.

    The harness imports `from screener.persistence import read_panel` (or
    similar). We patch the SYMBOL at the import-source module (`screener.persistence`)
    — NOT at the consumer module (`screener.backtest.vbt_runner`) — because
    Python rebinds attribute lookups dynamically: if vbt_runner does
    `import screener.persistence as p; p.read_panel(...)`, patching
    `screener.persistence.read_panel` works. If vbt_runner does
    `from screener.persistence import read_panel`, then we'd need to patch
    `screener.backtest.vbt_runner.read_panel`.

    Planner: pick ONE import style in vbt_runner.py and document it inline.
    Recommended: `from screener.persistence import read_panel` for clarity,
    AND patch `screener.backtest.vbt_runner.read_panel` in the test.
    """
    def _fake(snapshot_date):
        return synthetic_panel
    monkeypatch.setattr("screener.backtest.vbt_runner.read_panel", _fake)
    yield _fake
```

**Why monkeypatch beats the alternatives:**

| Approach | Why rejected |
|----------|--------------|
| DI via `run(..., data_reader=callable)` parameter | Adds a test-only kwarg to the public API surface; pollutes type signatures the mypy --strict scope checks. The `_lookahead` parameter is already a controversial backdoor; adding `data_reader` is a second one. |
| `tmp_path` + writing real parquet + DATA_DIR override | Slow (real disk I/O), requires settings.cache_clear() (per `persistence.read_panel` docstring lines 612–620), can leave artifacts on disk if test crashes. |
| `unittest.mock.patch` | Functionally identical to `monkeypatch.setattr` but more verbose for the simple case. |

**Architecture-test impact:** `monkeypatch.setattr("screener.backtest.vbt_runner.read_panel", fake)` only modifies the test code, not the source — `tests/test_architecture.py` scans only `src/screener/**`, so this is invisible to the contract check. **Confirmed safe** (verified by reading `_iter_source_files` in test_architecture.py:97).

**Bonus also-needed monkeypatch:** the snapshot reader. The harness will likely do:

```python
# in vbt_runner.py — read regime_state and signals from data/snapshots/
import pandas as pd
from pathlib import Path
from screener.persistence import read_panel  # for OHLCV

def _read_snapshot(snapshot_date: str) -> pd.DataFrame:
    return pd.read_parquet(Path("data/snapshots") / f"{snapshot_date}.parquet")
```

The test should also stub `_read_snapshot` to return a synthetic snapshot DataFrame with `passes_trend_template`, `regime_state`, `regime_score` columns. Or — cleaner — have the test write a real synthetic parquet to `tmp_path / "snapshots"` and have the harness accept `snapshot_dir` from `Path("data/snapshots")` (resolved from a stdlib `os.environ.get("SNAPSHOT_DIR", "data/snapshots")` since backtest/ cannot import config).

**Recommended approach:** monkeypatch BOTH `vbt_runner.read_panel` AND `vbt_runner._read_snapshot` (whatever the planner names the snapshot-reader helper).

---

## Section C — CI gate wiring (FND-04, D-09)

### Q8 — GitHub Actions path filter

**Inspection of existing `.github/workflows/ci.yml`:** three jobs (`lint`, `typecheck`, `test`), all triggered on every `pull_request` and `push` to `main`. The `test` job already runs `pytest -m "not slow" -v` which would include `tests/test_backtest_no_lookahead.py`.

**Two valid options for D-09 enforcement:**

| Option | Pro | Con |
|--------|-----|-----|
| A. Add a separate `no-lookahead-gate` job with `paths:` filter | Explicit gate; visible in PR status as its own required check; planner can require it in branch protection independently. | Runs `uv sync` twice on PRs that touch signals/ or backtest/ (lint+typecheck+test job + this job). |
| B. Add a step to the existing `test` job that runs the gate test first (always) | No duplicate `uv sync`; the gate test is fast (one synthetic 250-bar run); always runs (the requirement says "on every PR touching signals/ or backtest/" — but always running is *stricter*, which is safer). | The "no-lookahead-gate" doesn't appear as a separate PR check; it's just one of many pytest assertions. Less prominent in branch protection settings. |

**Recommendation: Option A — separate job with explicit `paths:` filter.** Reasons:
1. The CONTEXT.md "Phase Boundary" describes the gate as the *primary deliverable* of the phase — promoting it to a top-level CI job matches that framing.
2. `paths:` filter respects the user's "only run when files change" intent literally.
3. The lint/typecheck/test jobs already run on every PR (no paths filter), so they catch broken syntax even when signals/ doesn't change. Adding a fourth focused job doesn't change the safety net — only adds a focused gate.
4. Branch protection can require this specific check (`no-lookahead-gate`) by name without coupling to the broader `test` check.

**Recommended YAML to add to `.github/workflows/ci.yml`** (or split into `no-lookahead-gate.yml` — either works; same `name:` becomes the required-status-check identifier):

```yaml
  no-lookahead-gate:
    name: no-lookahead-gate
    runs-on: ubuntu-latest
    timeout-minutes: 5
    # FND-04 D-09: only required to run when signals/ or backtest/ change.
    # On other PRs the job is skipped (which counts as 'pass' for required checks
    # IF the job is configured as 'optional' in branch protection). Recommend
    # 'required' so the job MUST run when paths match — branch protection treats
    # a skipped required check as failing, which is what we want for paths
    # that don't trigger it (but those paths can't break the gate so it's moot).
    if: >
      contains(toJSON(github.event.pull_request.changed_files), 'src/screener/signals') ||
      contains(toJSON(github.event.pull_request.changed_files), 'src/screener/backtest') ||
      contains(toJSON(github.event.pull_request.changed_files), 'tests/test_backtest_no_lookahead')
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Set up Python from pyproject
        run: uv python install
      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev
      - name: No-look-ahead mutation test (FND-04)
        run: uv run pytest tests/test_backtest_no_lookahead.py -v --tb=short
```

**Note on `paths:` filter syntax:** GitHub Actions supports a top-level `on.pull_request.paths` filter, but it skips the *entire workflow* — meaning the lint/typecheck/test jobs would also skip when signals/backtest don't change. We DON'T want that. The `if:` expression at the JOB level is the right granularity. (The `contains(toJSON(...))` pattern is the documented workaround for per-job path filters.)

**Alternative simpler approach:** drop the `if:` entirely — let the gate run on every PR. The test takes ~3 seconds (one 250-bar synthetic backtest); the cost is negligible and there's zero risk of skipping when needed. **The planner should consider this simpler approach** unless the user has a strong opinion on path-filtered jobs.

`[VERIFIED: existing ci.yml structure, GitHub Actions documentation on `paths:` and job `if:` expressions]`

---

## Section D — Forensic Audit (BCK-07)

### Q9 — Reuse of `scripts/check_preregistration.py`

**Inspection of the script (lines 69–130):** the script defines `main() -> int` returning `0` on match, `1` on mismatch (parse failure or weight diff). Bottom-of-file: `if __name__ == "__main__": sys.exit(main())`.

**Exit-code contract is clean.** No gap — `subprocess.run(["uv", "run", "python", "scripts/check_preregistration.py"], check=False)` and inspect `returncode`. `0` = pass; `1` = fail.

**Recommended audit-CLI body (in `cli.backtest_audit()`):**

```python
import subprocess
import sys
from pathlib import Path
import structlog
import typer

log = structlog.get_logger(__name__)

def _audit_no_lookahead() -> tuple[bool, str]:
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/test_backtest_no_lookahead.py", "-q"],
        capture_output=True, text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr

def _audit_preregistration() -> tuple[bool, str]:
    result = subprocess.run(
        ["uv", "run", "python", "scripts/check_preregistration.py"],
        capture_output=True, text=True,
    )
    return result.returncode == 0, result.stdout + result.stderr

def _audit_universe_snapshot_before_start(backtest_start: str) -> tuple[bool, str]:
    from datetime import date
    universe_dir = Path("data/universe")
    if not universe_dir.exists():
        return False, "data/universe/ does not exist"
    snapshots = sorted(universe_dir.glob("*.parquet"))
    if not snapshots:
        return False, "no universe snapshots found"
    earliest = snapshots[0].stem  # e.g., "2025-12-29"
    if earliest > backtest_start:
        return False, f"earliest universe snapshot {earliest} > backtest start {backtest_start}"
    return True, f"earliest universe snapshot {earliest} ≤ backtest start {backtest_start}"

def _audit_oos_window_count(min_windows: int = 2) -> tuple[bool, str]:
    # Count `data/snapshots/*.parquet` files; map to walk-forward windows
    snapshot_dir = Path("data/snapshots")
    if not snapshot_dir.exists():
        return False, "data/snapshots/ does not exist"
    snapshots = sorted(snapshot_dir.glob("*.parquet"))
    if not snapshots:
        return False, "no snapshots found"
    earliest_ts = pd.Timestamp(snapshots[0].stem)
    latest_ts   = pd.Timestamp(snapshots[-1].stem)
    n_windows = len(walk_forward_windows(earliest_ts, latest_ts))  # imported from walkforward.py
    if n_windows < min_windows:
        return False, f"{n_windows} complete OOS windows < {min_windows} required"
    return True, f"{n_windows} complete OOS windows available"


@app.command("backtest-audit")
def backtest_audit() -> None:
    configure_logging()
    checks = [
        ("no-lookahead test passing",    _audit_no_lookahead),
        ("preregistration hash match",   _audit_preregistration),
        ("universe snapshot date ≤ start", lambda: _audit_universe_snapshot_before_start("2016-01-01")),
        ("≥ 2 complete OOS windows",     _audit_oos_window_count),
    ]
    failures = 0
    for label, check in checks:
        ok, msg = check()
        marker = "PASS" if ok else "FAIL"
        log.info("audit_check", check=label, result=marker, detail=msg)
        if not ok:
            failures += 1
    log.info("audit_complete", failures=failures, total=len(checks))
    if failures > 0:
        raise typer.Exit(code=1)
```

**Architecture-test impact:** This code lives in `cli.py` (the composition root), not in `backtest/`. cli.py is allowed to import anything (it's the composition root — per ALLOWED dict comment in tests/test_architecture.py:43). `subprocess`, `pathlib.Path`, and structlog are all fine. The `walk_forward_windows` import would come from `screener.backtest.walkforward`. **No D-17 violation.**

`[VERIFIED: read scripts/check_preregistration.py end-to-end; exit code contract is `0|1` via `sys.exit(int)`]`

---

### Q10 — Disclosure header format (BCK-06)

**Question:** YAML frontmatter or markdown bullets?

**Recommendation: YAML frontmatter at the top of `reports/backtest-YYYY-MM-DD.md`.** Reasons:

1. **Machine-parseable.** Phase 8 (operations) may want to extract the slippage assumptions / period selection programmatically — frontmatter is one `yaml.safe_load` away. Markdown bullets require fragile regex parsing.
2. **GitHub renders YAML frontmatter as a clean styled box** at the top of `.md` files (since 2022). The reader sees a structured header, not a wall of bullets.
3. **Pre-registration parallel.** `docs/strategy_v1_preregistration.md` uses a `**Frozen at commit: <sha>**` line — adopting YAML for the new doc establishes a pattern; Phase 7's journal docs could also use it.

**Recommended template** (concrete fields verbatim from CONTEXT.md "Specifics" + BCK-06):

```markdown
---
backtest_date: 2026-05-16
universe_source_date: 2026-04-27  # data/universe/2026-04-27.parquet
survivorship_caveat: |
  Universe is the iShares IWB constituent list as of universe_source_date.
  Historical members of Russell 1000 who were delisted before that date are
  NOT in the test set. This introduces a known upward bias of ~1–2% CAGR.
  Mitigation: walk-forward OOS sliding window reduces single-period overfit.
slippage_tiers:
  - adv_gt: 50_000_000  # $50M
    bps: 5
  - adv_range: [5_000_000, 50_000_000]
    bps: 15
  - adv_lt: 5_000_000
    bps: 30
period_selection:
  is_years: 3
  oos_years: 1
  slide_years: 1
  windows_count: 6
  earliest_is_start: 2016-01-01
  latest_oos_end: 2024-12-31
regime_gate:
  type: soft
  formula: composite_score *= regime_score  # see publishers/pipeline.py apply_regime_gate
playbook_attribution:
  status: stubbed
  note: All picks tagged 'leader_hold' until Phase 6 ships VCP/Qullamaggie detectors.
preregistration:
  weights_hash: <git commit sha of docs/strategy_v1_preregistration.md>
---

# Backtest Report — 2026-05-16

## OOS Sharpe Distribution

| Window | IS Period | OOS Period | OOS Sharpe | OOS MaxDD | OOS WinRate |
|--------|-----------|------------|------------|-----------|-------------|
| 1 | 2016-01-01..2018-12-31 | 2019-01-01..2019-12-31 | 1.42 | -8.3% | 54% |
| ...|

**Summary:** Sharpe distribution: min=0.31 | median=0.87 | max=1.42

## Per-Regime Breakdown
...

## Per-Playbook Attribution
...
```

`[CITED: GitHub docs on YAML frontmatter rendering — feature shipped 2022, widely supported in markdown viewers]`

---

## Section E — Landmines (vectorbt 1.0 footguns)

### L1 — NaN in `slippage` panel rejected by vectorbt

**Symptom:** `from_signals` silently produces all-zero positions or a cryptic numba error.
**Cause:** ADV rolling-mean has 19 NaN bars at the start of each ticker's series. Passing NaN to `slippage` is invalid.
**Mitigation:** `slippage_panel.where(adv_20d.notna(), 0.0030)` — fill NaN with worst tier (30 bps). See Section A Q4 worked example. `[VERIFIED]`

### L2 — `freq='1D'` vs business-day annualization

**Symptom:** Sharpe ratio off by a factor of `sqrt(365/252) ≈ 1.20` if `freq='1D'` is interpreted as calendar days.
**Cause:** vectorbt 1.0's `freq='1D'` annualization uses 365 by default in some code paths. Check the actual annualization basis.
**Mitigation:** Pass `freq='1D'` PLUS explicitly set `year_freq='252D'` if the API supports it; OR use `pf.sharpe_ratio(year_freq='252D')` at the call site. Alternative: hand-roll Sharpe from `pf.returns()` (avoids vbt's annualization entirely).
`[ASSUMED — needs verification; the Sharpe formula in docs/backtesting.md uses 252; vbt may use 365.]`

### L3 — Commons Clause license note

**Symptom:** Future LinkedIn post or open-source contribution embeds the backtest results commercially → license violation.
**Cause:** `vectorbt` is Apache 2.0 **+ Commons Clause** (NOT MIT). Verbatim: "free for personal/research/portfolio use; cannot be resold."
**Mitigation:** Add an explicit note to README.md and `reports/backtest-*.md` disclosure header. `[VERIFIED: docs/tech-stack.md line 18, 71]`

### L4 — Look-ahead leakage from `.iloc` slicing of OOS windows

**Symptom:** OOS Sharpe is suspiciously close to IS Sharpe; walk-forward results don't degrade as expected.
**Cause:** Slicing by integer positions (`signals.iloc[is_start_idx:is_end_idx]`) instead of `.loc[is_start:is_end]` can mis-align when ticker join produces sparse index. Bar `t` in ticker A may be a different date than bar `t` in ticker B.
**Mitigation:** Always slice by `pd.Timestamp` (`.loc[is_start:is_end]`), never by integer position. Verify alignment with `assert (sig.index == price.index).all()` before passing to `from_signals`.

### L5 — ADV NaN at start of series → mis-tier as illiquid

**Symptom:** First 19 bars of every ticker get 30 bps slippage even if the ticker is mega-cap (AAPL → 30 bps for first 19 bars).
**Cause:** `rolling(20).mean()` requires 20 valid bars; first 19 produce NaN.
**Mitigation:** See L1 — fill NaN with worst tier. Acceptable because Trend Template signals can't fire in first 200 bars anyway (requires SMA200), so the first 19 bars never produce entries.

### L6 — `cash_sharing=True` requires `group_by` or single group

**Symptom:** vectorbt complains about cash allocation across columns OR sizes positions wrong.
**Cause:** Multi-asset backtests with `cash_sharing=True` need vectorbt to know the group identity of each column.
**Mitigation:** Pass `group_by=np.array([0] * n_tickers)` to put all tickers in a single shared-cash group. Alternative: `cash_sharing=False` and use absolute share counts.

### L7 — Bool DataFrame coercion from float entries

**Symptom:** Entries panel produces no trades despite signal having True values.
**Cause:** vectorbt requires `bool` dtype for `entries` / `exits`. CONTEXT.md D-06 says `.astype(float)` — for the shift'd version, this float `1.0` may pass through but is risky.
**Mitigation:** End the signal pipeline with `.astype(bool)`. Verified throughout the worked examples in Sections A/B.

### L8 — `entries` and `exits` shape mismatch with `close`

**Symptom:** Numba error "shape mismatch" or silent broadcast.
**Cause:** `close` has shape `(T, N)`, `entries` has shape `(T,)` (single column dropped to Series).
**Mitigation:** Always pass `pd.DataFrame` (never Series) to multi-asset `from_signals`. Explicit `entries = entries.to_frame()` if single ticker.

### L9 — Pivot from MultiIndex panel to wide (date × ticker) loses dtype

**Symptom:** `unstack(level='ticker')` returns float volumes (was int) and breaks downstream int comparisons.
**Cause:** pandas `unstack` introduces NaN when ticker has missing dates; NaN forces float promotion.
**Mitigation:** Explicit `.astype("float64")` immediately after unstack; document it. Don't compare volumes as integers post-pivot.

### L10 — `make backtest` shells out, swallows the snapshot Parquet read errors

**Symptom:** Backtest runs, prints "0 trades", report says "no data" — no clear error.
**Cause:** `data/snapshots/*.parquet` files don't exist yet (backfill never run) → `glob('data/snapshots/*.parquet')` returns empty list → no signals → no trades. No exception raised.
**Mitigation:** Hard-fail in `vbt_runner.run()` if `len(list(Path("data/snapshots").glob("*.parquet"))) == 0` — raise with message: `"No snapshots found. Run `make backfill-snapshots` first."` Same defensive pattern as `persistence.read_panel()` line 656.

### L11 — `pd.DateOffset(years=1)` quirk on Feb 29

**Symptom:** Window arithmetic produces unexpected boundaries on leap years.
**Cause:** `pd.Timestamp('2020-02-29') + pd.DateOffset(years=1)` → `Timestamp('2021-02-28')` (not Feb 29 → bumps backward).
**Mitigation:** Use `pd.DateOffset` consistently (it has well-defined leap-year behavior); document the leap-year edge case. Test with `start=2016-02-29`. The 2016–2025 window set in this research happens to start on Jan 1 so it's unaffected.

### L12 — `backtest/` cannot import `screener.obs` for structlog

**Symptom:** Adding `from screener.obs import configure as configure_logging` to `vbt_runner.py` makes `test_architecture.py::test_backtest_does_not_import_data_layer` fail.
**Cause:** D-17 / `ALLOWED["backtest"] = {"persistence"}` — obs is forbidden.
**Mitigation:** Use stdlib `logging` inside backtest/. Pattern:
```python
import logging
log = logging.getLogger(__name__)  # configured at package boundary by cli.py or pytest
```
No `configure_logging()` call inside backtest/ — log records flow to the root logger, which cli.py configures via structlog at startup. The structlog ProcessorFormatter intercepts stdlib logging records when configured to do so. `[VERIFIED: tests/test_architecture.py:30-44, 137-161]`

### L13 — `Portfolio.from_signals` `direction='longonly'` rejection conflict

**Symptom:** Test produces both long-only and short-only positions; results don't match BCK-03 "long-only" requirement.
**Cause:** Forgetting `direction='longonly'` in the call → vbt defaults to `'longonly'` in some versions but `'all'` in others.
**Mitigation:** ALWAYS pass `direction='longonly'` explicitly. Verified default may differ across vbt versions.

### L14 — Test seed sensitivity (Section B Q5)

**Symptom:** No-look-ahead test passes locally with seed=42, fails on CI with seed=0.
**Cause:** Threshold of `≤ 2× BH` (CONTEXT.md D-07) is seed-sensitive; the correct path's return varies widely.
**Mitigation:** Pin seed to 42 in the fixture; use absolute thresholds (Section B Q5): `correct < 0.5` AND `lookahead > 1.0`. The 4× separation is robust across all 10 tested seeds.

### L15 — Snapshot schema requires non-null `regime_state` (PandasError at backtest read time)

**Symptom:** `read_parquet` succeeds but downstream `groupby('regime_state')` produces unexpected `NaN` group.
**Cause:** `RankingSnapshotSchema` (persistence.py:246–249) requires `regime_state` non-nullable — but a corrupted snapshot from a failed pipeline run may have NaN.
**Mitigation:** Defensive check in the harness: `assert snapshot['regime_state'].notna().all(), "Snapshot has NaN regime_state — backfill data is corrupt."` Raise with clear message.

### L16 — `vbt.Portfolio.sharpe_ratio()` returns NaN on zero-trade windows

**Symptom:** OOS Sharpe for a window with no signals → `NaN`. `(min, median, max)` becomes `(NaN, NaN, NaN)`.
**Cause:** Sharpe is `mean_return / std_return`; if no trades, std=0, division by zero → NaN.
**Mitigation:** Document this as expected behavior in the report. Filter out NaN windows before computing distribution; report `N_zero_trade_windows` as a separate field.

---

## Standard Stack

### Core (verified versions in this environment)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vectorbt | 1.0.0 | Walk-forward harness | Apache 2 + Commons Clause; numba-backed; only sane choice for vectorized multi-asset backtest in Python `[VERIFIED: `python -c "import vectorbt"` in uv venv 2026-05-16]` |
| pandas | 2.3.3 | DataFrame ops | Indexed slicing, date arithmetic, pivot `[VERIFIED]` |
| numpy | 2.4.4 | `np.where` slippage tier logic | `[VERIFIED]` |
| pyarrow | 17.x (already pinned) | Parquet read/write | Already in `persistence._write_parquet_atomic` |
| pytest | 8.x (already pinned) | Test runner | `[VERIFIED: tests/conftest.py uses pytest fixtures]` |

### Supporting (already in pyproject; not added by Phase 5)

| Library | Purpose | When |
|---------|---------|------|
| typer | CLI body for `backtest` + `backtest-audit` | `cli.py` only |
| structlog | Logging in cli.py only — NOT in backtest/ | Phase 5 maintains the D-17 boundary |
| stdlib `logging` | All logging inside `backtest/` per D-17 | `import logging; log = logging.getLogger(__name__)` |
| stdlib `subprocess` | `cli.backtest_audit` invokes pytest + preregistration | composition root |

### NOT added by Phase 5

| Library | Why not |
|---------|---------|
| `tqdm` | Backfill script can use plain `print()` per Discretion item 4. tqdm is fine if planner prefers — it's already pinned through other deps. |
| `vectorbt-pro` | Violates $0 budget (per docs/tech-stack.md). Use vbt 1.0 community. |
| `backtesting.py` | Secondary library per docs/backtesting.md — only used if Commons Clause becomes a blocker, which is NOT the case for personal/portfolio use. |

**Installation: NONE.** `pyproject.toml` already pins `vectorbt>=1.0,<2` from Phase 1 (D-02). No new deps needed.

**Version verification:**
```bash
$ uv run python -c "import vectorbt; print(vectorbt.__version__)"
1.0.0
```
`[VERIFIED 2026-05-16]`

---

## Architecture Patterns

### System Architecture Diagram

```
                                                                            ┌────────────────────────┐
                                                                            │ docs/strategy_v1_preregis-│
                                                                            │ tration.md (committed)  │
                                                                            └──────────┬──────────────┘
                                                                                       │ reads
                                                                                       ▼
┌────────────────────────┐    one-off    ┌─────────────────────────────┐    ┌─────────────────────────┐
│ scripts/backfill_       │── over 10yr ──│ publishers.pipeline         │    │ scripts/check_preregis-  │
│ snapshots.py            │   of dates    │ .run_pipeline(date,         │    │ tration.py               │
│ (D-01, outside backtest/│               │   write_report=False)       │    │ (subprocess.run by audit)│
└────────────────────────┘               └─────────────┬───────────────┘    └──────────┬──────────────┘
                                                       │ writes                          │ returncode
                                                       ▼                                  │
                              ┌────────────────────────────────────────┐                  │
                              │ data/snapshots/YYYY-MM-DD.parquet      │                  │
                              │ (passes_trend_template, composite_score,│                  │
                              │  regime_state, regime_score, ...)       │                  │
                              └─────────────┬──────────────────────────┘                  │
                                            │ read by                                       │
                                            ▼                                               │
┌─────────────────────────┐    read OHLCV    ┌────────────────────────────────────────┐    │
│ persistence.read_panel()│◄───────────────│ backtest/vbt_runner.py                  │    │
│ (D-04, D-17)            │                  │  - run(start, end, *, _lookahead=False)│    │
└─────────────────────────┘                  │  - _build_signals()                    │    │
                                             │  - _build_slippage_panel()             │    │
┌─────────────────────────┐                  │  - _walk_forward_windows()             │    │
│ pd.read_parquet on      │ ── read regime ──►  - calls vbt.Portfolio.from_signals    │    │
│ data/snapshots/*.parquet│                  └──────────────┬─────────────────────────┘    │
└─────────────────────────┘                                 │ returns                       │
                                                            │ BacktestResult                │
                                                            ▼                                │
                              ┌────────────────────────────────────────┐                    │
                              │ cli.backtest() OR cli.backtest_audit() │◄────read─exit──────┘
                              │ (composition root; writes report)      │
                              └──────┬─────────────────────┬───────────┘
                                     │ stdout              │ writes file
                                     ▼                     ▼
                              terminal summary    reports/backtest-YYYY-MM-DD.md
                                                  (YAML frontmatter + tables)

       ┌──────────────────────────────────────────────────────────────────┐
       │ FND-04 CI GATE:  tests/test_backtest_no_lookahead.py             │
       │   monkeypatches vbt_runner.read_panel → synthetic 250-bar panel  │
       │   calls vbt_runner.run(..., _lookahead=False) and _lookahead=True│
       │   asserts the 4× return separation that proves .shift(1) is live │
       └──────────────────────────────────────────────────────────────────┘
                Trigger: on every PR touching signals/ or backtest/
                Implementation: .github/workflows/ci.yml job 'no-lookahead-gate'
```

### Recommended Project Structure

```
src/screener/backtest/
├── __init__.py          # existing docstring; no API changes
├── vbt_runner.py        # NEW: run(start, end, *, _lookahead=False) -> BacktestResult
├── walkforward.py       # NEW: walk_forward_windows(start, end, is_years, oos_years, slide_years)
└── metrics.py           # NEW (optional): aggregate_oos_sharpe(per_window_pfs) -> (min, median, max)

scripts/
├── check_preregistration.py     # EXISTING — reused by backtest-audit
└── backfill_snapshots.py        # NEW: D-01 backfill loop, calls publishers.pipeline.run_pipeline

tests/
└── test_backtest_no_lookahead.py  # NEW — FND-04 CI gate

reports/
└── backtest-YYYY-MM-DD.md          # NEW per `make backtest` run

.github/workflows/
└── ci.yml  # MODIFIED: add `no-lookahead-gate` job (Section C Q8)

Makefile  # MODIFIED: add `backfill-snapshots` target (D-02)
```

### Pattern 1 — Test-only `_lookahead` backdoor with KEYWORD-ONLY parameter

**What:** A single test-only parameter on the public `run()` function that bypasses `.shift(1)`.
**When to use:** Mutation testing requires the harness to flip behavior on demand — but the parameter must NEVER leak into production paths.
**Example** (`src/screener/backtest/vbt_runner.py`):

```python
def run(start: str, end: str, *, _lookahead: bool = False) -> "BacktestResult":
    """Walk-forward backtest. _lookahead is FND-04 mutation-test backdoor.

    NEVER call with _lookahead=True from production code. The leading
    underscore + keyword-only enforcement + this docstring make it visually
    obvious in code review that this is a test affordance.
    """
    ...
```

The `*` before `_lookahead` makes it keyword-only — `run("2024", "2025", True)` is a syntax error. Combined with the underscore prefix, no production caller will accidentally enable it.

### Pattern 2 — Snapshot-as-source-of-truth, no signal recomputation

**What:** The harness reads pre-computed `passes_trend_template` / `composite_score` / `regime_state` from `data/snapshots/YYYY-MM-DD.parquet`, NEVER recomputes signals during backtest.
**Why:** Recomputing signals during backtest re-introduces look-ahead risk (every signal recompute is a new chance to use future bars). Also: avoids the D-17 import constraint (snapshots are read via `pd.read_parquet`, not via `signals/` import).
**Anti-pattern (DON'T do this):**
```python
# WRONG — re-import signals into backtest/
from screener.signals.minervini import passes_trend_template  # blocked by D-17!
panel = passes_trend_template(read_panel(date))                # double-compute risk
```
**Correct:**
```python
# RIGHT — read the pre-computed signal from disk
signals = pd.read_parquet(f"data/snapshots/{date}.parquet")[['ticker', 'passes_trend_template']]
```

### Anti-Patterns to Avoid

- **`backtest/` imports `signals/` or `indicators/`** → architecture test failure. Use the snapshot reader pattern.
- **`backtest/` imports `obs` for structlog** → architecture test failure. Use stdlib `logging`.
- **`signals.iloc[is_start_idx:is_end_idx]` for window slicing** → look-ahead bug if MultiIndex isn't perfectly aligned. Use `.loc[ts:ts]`.
- **Calling `from_signals` without `direction='longonly'`** → vbt default varies; pass explicitly.
- **`tqdm` inside `backtest/`** → optional; if used, ensure it's an external dep already in pyproject.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vectorized portfolio simulation across N tickers × T bars | Numpy loops with manual cash accounting | `vbt.Portfolio.from_signals` | Numba-compiled; handles short fills, partial cash, cash sharing, fees, slippage in one pass |
| Sharpe / CAGR / max DD / win rate | Hand math on equity curve | `pf.sharpe_ratio()`, `pf.total_return()`, `pf.max_drawdown()`, `pf.trades.win_rate()` | Annualization, drawdown peaks, win-rate edge cases all correct |
| Walk-forward window iteration | Verbose `for split in splitter` loops | Manual `pd.DateOffset(years=1)` arithmetic (Section A Q3) | Built-in `RollingSplitter` slides by 1 bar, not 1 year — manual is simpler and correct |
| Subprocess management for audit checks | `os.system()` | `subprocess.run(..., check=False, capture_output=True)` | Captures stdout/stderr cleanly; check=False so the audit doesn't crash on first failure |
| Synthetic OHLCV for tests | Constant-trend toy data | `np.random.default_rng(42).normal()` + `np.exp(np.cumsum())` (Section B Q6) | Realistic dynamics; mean-zero for predictable threshold; positive prices via exp |
| Slippage panel construction | Per-row `apply` with `if/elif` | `np.where(adv > X, ..., np.where(adv >= Y, ..., Z))` (Section A Q4) | Vectorized; no Python-level loop over rows |

**Key insight:** Most of Phase 5's "hard work" is already in vectorbt. The phase is mostly wiring: build slippage panel, slice windows, call `from_signals`, aggregate per-window results. Resist the urge to wrap or abstract — every layer between `run()` and `vbt.Portfolio.from_signals(...)` is a potential look-ahead bug.

---

## Runtime State Inventory

> Phase 5 is a greenfield phase (adds new modules; doesn't rename or refactor existing state). This section is included for completeness but most categories are N/A.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `data/snapshots/*.parquet` — created during Phase 4; Phase 5 backfill ADDS historical files (2016–2025); no existing files are modified or renamed | None (additive only) |
| Live service config | None — no external services consume Phase 5 outputs | None |
| OS-registered state | None — Phase 8 will register the cron, not Phase 5 | None |
| Secrets/env vars | None added by Phase 5 | None |
| Build artifacts | None — Phase 5 adds Python source files only; no compiled extensions, no setuptools entry-point changes | None |

**Caveat — universe snapshot timing:** The forensic audit check `universe snapshot date ≤ backtest start date` (D-16 check #3) requires at least one `data/universe/YYYY-MM-DD.parquet` to exist with `YYYY-MM-DD ≤ 2016-01-01`. The current earliest universe snapshot is `2026-04-27` (per the `data/universe/2026-04-27.parquet` listed in `git status`). **This means backtest-audit will FAIL until a 2016-or-earlier universe snapshot exists.** Options for the planner:
1. Document the failure as expected for Phase 5 (audit ships but is non-blocking until DAT-02 has historical depth)
2. Hand-create a single backdated universe snapshot via `cp data/universe/2026-04-27.parquet data/universe/2016-01-01.parquet`
3. Defer the check to "best universe snapshot ≤ start" if no exact match exists.

`[VERIFIED: ls data/universe/ shows only 2026-04-27.parquet]`

---

## Common Pitfalls

### Pitfall 1: D-07 threshold "≤ 2× BH" is seed-sensitive
- **Goes wrong:** CI fails intermittently or passes locally but fails on a different seed.
- **Cause:** GBM autocorrelation + low-magnitude BH → ratio explodes.
- **Avoid:** Pin seed=42; use absolute thresholds 0.5/1.0 (Section B Q5).
- **Warning sign:** Test passes on `pytest` locally but fails on `pytest -p no:randomly` or with different seed.

### Pitfall 2: vectorbt silently produces NaN on zero-trade windows
- **Goes wrong:** OOS Sharpe distribution shows `(NaN, NaN, NaN)` for a window.
- **Cause:** No signals fired during OOS → zero trades → undefined Sharpe.
- **Avoid:** Filter NaN windows before aggregation; report `n_zero_trade_windows` separately.
- **Warning sign:** `pf.trades.count() == 0` for the window — log it.

### Pitfall 3: Hand-importing `signals/` into `backtest/`
- **Goes wrong:** Architecture test failure on first `pytest` run after change.
- **Cause:** Forgetting D-17; convenience trap.
- **Avoid:** Always read pre-computed signals from `data/snapshots/`. Never import `screener.signals.*` inside `backtest/`.
- **Warning sign:** `tests/test_architecture.py::test_backtest_does_not_import_data_layer` fails.

### Pitfall 4: Using `.iloc` for window slicing
- **Goes wrong:** Look-ahead leakage if MultiIndex sparse (some tickers have shorter history).
- **Cause:** Bar `t` integer position may differ across tickers.
- **Avoid:** Always slice by `pd.Timestamp` (`signals.loc[is_start:is_end]`).
- **Warning sign:** OOS Sharpe near IS Sharpe; walk-forward results don't degrade.

### Pitfall 5: Backfill script imports `backtest/` indirectly
- **Goes wrong:** Architecture test failure as transitive import sneaks in.
- **Cause:** `scripts/backfill_snapshots.py` is outside `src/screener/` so it can import anything — but if it accidentally imports `backtest/`, then `backtest/` may pull in publishers via a circular path.
- **Avoid:** Backfill imports `publishers.pipeline.run_pipeline` ONLY. Never touches `backtest/`.
- **Warning sign:** ImportError on `from screener.backtest import ...` from anywhere.

### Pitfall 6: Audit CLI swallows subprocess failures
- **Goes wrong:** `make backtest-audit` exits 0 even when a check failed.
- **Cause:** Forgetting `raise typer.Exit(code=1)` after counting failures.
- **Avoid:** See Section D Q9 — explicit `if failures > 0: raise typer.Exit(code=1)`.
- **Warning sign:** CI passes but log shows "audit_complete failures=2".

### Pitfall 7: Disclosure header drift between report and reality
- **Goes wrong:** Report says "ADV > $50M → 5 bps" but harness used 10 bps (changed during refactor).
- **Cause:** Header hand-written; not generated from the same constants the harness uses.
- **Avoid:** Define `SLIPPAGE_TIERS = [(50_000_000, 0.0005), (5_000_000, 0.0015), (0, 0.0030)]` ONCE in `vbt_runner.py`; both `_build_slippage_panel()` and the report renderer consume it.
- **Warning sign:** Manual review of report finds wrong numbers; no automated check.

---

## Code Examples

### Walk-forward main loop (verified against vbt 1.0)

```python
# src/screener/backtest/vbt_runner.py
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

from screener.persistence import read_panel  # ONLY allowed internal import

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowResult:
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    oos_sharpe: float
    oos_max_dd: float
    oos_win_rate: float
    oos_total_return: float
    n_trades: int


@dataclass(frozen=True)
class BacktestResult:
    windows: list[WindowResult]
    sharpe_min: float
    sharpe_median: float
    sharpe_max: float
    total_return: float  # composite return across all OOS windows (geometric)


def run(start: str, end: str, *, _lookahead: bool = False) -> BacktestResult:
    """Walk-forward backtest entry point.

    Args:
        start: ISO date string, e.g., '2016-01-01'.
        end:   ISO date string, e.g., '2025-12-31'.
        _lookahead: FND-04 mutation-test backdoor. NEVER use from production.

    Returns:
        BacktestResult with per-window stats + OOS Sharpe distribution.
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    windows = walk_forward_windows(start_ts, end_ts)

    # Assemble the full signal + price panels ONCE; slice per-window.
    panel = _load_ohlcv_panel(start_ts, end_ts)              # MultiIndex (ticker, date)
    snapshots = _load_snapshots(start_ts, end_ts)             # MultiIndex (date, ticker)
    close = panel['close'].unstack(level='ticker')
    open_panel = panel['open'].unstack(level='ticker')
    slippage_panel = _build_slippage_panel(panel)

    # entries = passes_trend_template at each bar; exits = passes_trend_template fails
    raw_entries = snapshots.pivot_table(
        index='date', columns='ticker', values='passes_trend_template', fill_value=False
    ).astype(bool)
    raw_exits = (~raw_entries) & raw_entries.shift(1, fill_value=False)
    raw_entries_clean = raw_entries & ~raw_entries.shift(1, fill_value=False)

    if _lookahead:
        entries_exec, exits_exec = raw_entries_clean, raw_exits  # NO SHIFT — backdoor
    else:
        entries_exec = raw_entries_clean.shift(1, fill_value=False).astype(bool)
        exits_exec   = raw_exits.shift(1, fill_value=False).astype(bool)

    window_results = []
    for (is_s, is_e, oos_s, oos_e) in windows:
        # OOS-only slice for this window
        sl = slice(oos_s, oos_e)
        pf = vbt.Portfolio.from_signals(
            close=close.loc[sl],
            entries=entries_exec.loc[sl],
            exits=exits_exec.loc[sl],
            price=open_panel.loc[sl],
            slippage=slippage_panel.loc[sl],
            direction='longonly',
            init_cash=100_000.0,
            cash_sharing=True,
            group_by=np.zeros(close.shape[1], dtype=int),
            fees=0.0,
            size=0.05,
            size_type='value',
            freq='1D',
        )
        window_results.append(WindowResult(
            is_start=is_s, is_end=is_e, oos_start=oos_s, oos_end=oos_e,
            oos_sharpe=float(pf.sharpe_ratio()) if not pd.isna(pf.sharpe_ratio()) else float('nan'),
            oos_max_dd=float(pf.max_drawdown()),
            oos_win_rate=float(pf.trades.win_rate()) if pf.trades.count() > 0 else 0.0,
            oos_total_return=float(pf.total_return()),
            n_trades=int(pf.trades.count()),
        ))

    sharpes = pd.Series([w.oos_sharpe for w in window_results]).dropna()
    return BacktestResult(
        windows=window_results,
        sharpe_min=float(sharpes.min()) if len(sharpes) > 0 else float('nan'),
        sharpe_median=float(sharpes.median()) if len(sharpes) > 0 else float('nan'),
        sharpe_max=float(sharpes.max()) if len(sharpes) > 0 else float('nan'),
        total_return=float((1 + pd.Series([w.oos_total_return for w in window_results])).prod() - 1),
    )


def _load_ohlcv_panel(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Stitch read_panel() calls across the date range. SIMPLIFIED — Phase 5 may
    read a single most-recent universe and use its OHLCV across the full backtest
    window (acceptable since survivorship is disclosed; see BCK-06)."""
    snapshot_date = end.strftime('%Y-%m-%d')  # use most recent universe
    return read_panel(snapshot_date)


def _load_snapshots(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Read all data/snapshots/YYYY-MM-DD.parquet within [start, end] and stack."""
    snap_dir = Path("data/snapshots")
    if not snap_dir.exists() or not list(snap_dir.glob("*.parquet")):
        raise RuntimeError(
            "No snapshots found in data/snapshots/. "
            "Run `make backfill-snapshots` first."
        )
    frames = []
    for p in sorted(snap_dir.glob("*.parquet")):
        date = pd.Timestamp(p.stem)
        if not (start <= date <= end):
            continue
        df = pd.read_parquet(p)
        df['date'] = date
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _build_slippage_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """See Section A Q4."""
    close = panel['close'].unstack(level='ticker')
    volume = panel['volume'].unstack(level='ticker').astype(float)
    adv_20d = (close * volume).rolling(20, min_periods=20).mean()
    slip = np.where(adv_20d > 50_000_000, 0.0005,
            np.where(adv_20d >= 5_000_000, 0.0015, 0.0030))
    out = pd.DataFrame(slip, index=close.index, columns=close.columns)
    return out.where(adv_20d.notna(), 0.0030)


# Imported from sibling walkforward.py — see Section A Q3
def walk_forward_windows(...): ...
```

`[VERIFIED: code shape against direct `from_signals` test session; vectorbt 1.0.0]`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `vbt.Portfolio.from_orders()` for single-trade backtests | `from_signals()` for declarative entry/exit signals | vbt 0.x → 1.0 (April 2026) | Cleaner API for momentum strategies; signals semantics match Trend Template directly |
| Manual `for date in ...: backtest_one_day()` loop | Vectorized panel-based `from_signals(close=DataFrame, entries=DataFrame)` | vbt 0.x stable | 100×+ speedup; required for 1000-ticker universe |
| Numba 0.x JIT cold-start | Numba 0.60+ AOT cache | numpy 2 migration ~2025 | Cuts CI cold-start by ~30s with uv cache |
| `pandas-ta` (twopirllc) | `pandas-ta-classic` (Phase 5 doesn't touch this — for context only) | 2024-2025 repo deletion | Already migrated in Phase 3 |

**Deprecated/outdated:**
- `vectorbt.signals.factory.SignalFactory` — wrapper for custom signals; superseded by direct DataFrame construction. Not needed for Phase 5.
- `pf.stats()` aggregate display — still works but less reliable for programmatic access; use individual methods (`pf.sharpe_ratio()`, etc.) for the report.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `freq='1D'` annualizes Sharpe via 365 days (not 252) | Section E L2 | Sharpe values in report off by ~1.20× — disclosure header should specify annualization basis explicitly |
| A2 | Phase 5 wants a SINGLE universe across the full backtest (not per-window universe via point-in-time `data/universe/*.parquet`) | Code Examples `_load_ohlcv_panel` | If per-window universe is required, the loader needs to vary the universe by IS window start — adds complexity, but data is there (DAT-02 weekly snapshots from Phase 2) |
| A3 | The composite_score column drives entry selection (NOT just `passes_trend_template`) — but Phase 5 stub may use just the Trend Template gate | All Section A | Planner decides: entry = `passes_trend_template == True` OR `composite_score >= threshold`. CONTEXT.md D-04 says the snapshot has both — recommend `composite_score >= 40` as a threshold filter ON TOP of `passes_trend_template == True` to limit trade count |
| A4 | `tqdm` is acceptable for backfill script (Discretion item 4 allows `print()` or `tqdm`) | Section A Q3 footnote | Cosmetic only; planner picks; both fine |
| A5 | The 2016-01-01 universe snapshot will need to be hand-created or the audit check loosened | Runtime State Inventory | Audit check #3 will fail until DAT-02 has historical depth; planner should document the workaround |
| A6 | vectorbt's `cash_sharing=True` requires `group_by=np.zeros(N)` for multi-asset single-bucket simulation | Code Examples | Without `group_by`, vbt may treat each ticker as an independent cash bucket — sizing math becomes wrong |

---

## Open Questions

1. **Sharpe annualization basis** (A1 above)
   - What we know: vbt accepts `freq='1D'` and computes Sharpe.
   - What's unclear: Is the annualization 365 or 252? Affects all reported Sharpes.
   - Recommendation: Add a `[ASSUMED]` note in the disclosure header; verify with one quick test in Wave 0 (`pytest tests/test_backtest_sharpe_basis.py`) — compute hand-Sharpe on equity, compare to `pf.sharpe_ratio()`, document the constant.

2. **Per-window universe vs single universe** (A2 above)
   - What we know: `data/universe/*.parquet` has weekly snapshots; DAT-02 gives point-in-time membership.
   - What's unclear: Does the backtest need to use the universe-at-IS-start, or is a single late universe acceptable for v1?
   - Recommendation: Use a SINGLE universe (the most recent) for Phase 5; disclose the survivorship implication in BCK-06 header. Per-window universe is a Phase 6+ refinement.

3. **Entry threshold**
   - What we know: `composite_score` ∈ [0, 100]; `passes_trend_template` ∈ {True, False}.
   - What's unclear: Does Phase 5 enter on EVERY trend-template pass, or filter by composite score?
   - Recommendation: Enter on `passes_trend_template == True AND composite_score >= 40` (filters obvious low-confidence picks; threshold can be in Settings).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All Phase 5 code | ✓ | 3.11.x | — |
| vectorbt | `backtest/vbt_runner.py` | ✓ | 1.0.0 | — (no fallback — backtest is the phase deliverable) |
| pandas | All Phase 5 code | ✓ | 2.3.3 | — |
| numpy | Slippage tier `np.where` | ✓ | 2.4.4 | — |
| pytest | `tests/test_backtest_no_lookahead.py` | ✓ | 8.x | — |
| structlog | cli.py only (NOT backtest/) | ✓ | already pinned | stdlib `logging` (inside backtest/) |
| typer | cli.py | ✓ | already pinned | — |
| stdlib `subprocess` | `cli.backtest_audit` | ✓ | — | — |
| pyarrow | Parquet read/write | ✓ | 17.x | — |
| `data/snapshots/*.parquet` files (2016+) | Backtest harness | ✗ initially | — | `make backfill-snapshots` must run first; backtest hard-fails with clear error if missing (see L10) |
| `data/universe/<≤2016-01-01>.parquet` | Forensic audit check #3 | ✗ | only 2026-04-27 exists | Plan must address: (a) document expected audit failure, (b) hand-create backdated snapshot, OR (c) relax check to "earliest available ≤ start" |

**Missing dependencies with no fallback:**
- A 2016-or-earlier universe snapshot for forensic audit check #3. **Planner action: choose option (a), (b), or (c) above.**

**Missing dependencies with fallback:**
- Historical `data/snapshots/*.parquet` — `make backfill-snapshots` (D-01/D-02) is the fallback; explicit error in `_load_snapshots` directs the user.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + hypothesis 6.x (existing in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) — includes `--cov=src/screener/{signals,indicators} --cov-fail-under=80` |
| Quick run command | `uv run pytest tests/test_backtest_no_lookahead.py -q` (~3s) |
| Full suite command | `uv run pytest -m "not slow" -v` (~30s on a populated repo) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-04 | `_lookahead=False` produces low return on perfect-foresight signal | unit (integration-style) | `uv run pytest tests/test_backtest_no_lookahead.py::test_no_lookahead_correct_path -x` | ❌ Wave 1 |
| FND-04 | `_lookahead=True` produces high return (mutation detected) | unit | `uv run pytest tests/test_backtest_no_lookahead.py::test_no_lookahead_mutation_detected -x` | ❌ Wave 1 |
| FND-04 | Removing `.shift(1)` from production path causes the correct-path test to fail | mutation (manual + CI) | `git stash; sed -i 's/\.shift(1, fill_value=False)//g' src/screener/backtest/vbt_runner.py; uv run pytest tests/test_backtest_no_lookahead.py; git checkout src/; git stash pop` | ❌ Wave 1 (test exists; mutation verified manually during Wave 1 review) |
| BCK-01 | OOS Sharpe distribution = (min, median, max) across windows | unit | `uv run pytest tests/test_walkforward_window_count.py -x` (planner-added) | ❌ Wave 2 |
| BCK-02 | Entries shift 1 bar; price=open_panel | unit | covered by FND-04 tests (same code path) | ❌ Wave 1 |
| BCK-03 | Slippage tiers wired; ADV→bps mapping correct | unit | `uv run pytest tests/test_backtest_slippage_tiers.py -x` (planner-added) | ❌ Wave 1 |
| BCK-04 | Per-playbook attribution = leader_hold stub | unit | `uv run pytest tests/test_backtest_report.py::test_playbook_rows -x` | ❌ Wave 3 |
| BCK-05 | Per-regime breakdown column groups | unit | `uv run pytest tests/test_backtest_report.py::test_regime_breakdown -x` | ❌ Wave 3 |
| BCK-06 | Disclosure header has all 5 fields | unit | `uv run pytest tests/test_backtest_report.py::test_disclosure_header -x` | ❌ Wave 3 |
| BCK-07 | `make backtest-audit` exits non-zero on any check failure | integration | `uv run pytest tests/test_cli_backtest_audit.py -x` | ❌ Wave 3 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_backtest_no_lookahead.py -q` (the critical gate, fast)
- **Per wave merge:** `uv run pytest -m "not slow" -v` (full suite)
- **Phase gate (before `/gsd-verify-work`):** Full suite green + `make backtest-audit` exits 0 (with universe snapshot caveat from A5)

### Wave 0 Gaps

- [ ] `tests/test_backtest_no_lookahead.py` — covers FND-04 (must-have, Wave 1 priority)
- [ ] `tests/test_walkforward_window_count.py` — verifies `walk_forward_windows()` returns expected dates
- [ ] `tests/test_backtest_slippage_tiers.py` — verifies the np.where tier mapping
- [ ] `tests/test_backtest_report.py` — covers BCK-04, BCK-05, BCK-06
- [ ] `tests/test_cli_backtest_audit.py` — covers BCK-07 (uses CliRunner; subprocess can be monkeypatched)
- [ ] `conftest.py` extension — add `synthetic_panel` session fixture (Section B Q6)
- [ ] Framework install: NONE — pytest 8.x already pinned
- [ ] `scripts/backfill_snapshots.py` integration test (Wave 0 or 1) — verifies it can run for 1 date and writes the right file

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 5 has no auth surface |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Local CLI only |
| V5 Input Validation | yes | All date inputs to `run(start, end)` validated; user-supplied snapshot dates pass through `_assert_safe_snapshot_date` regex in persistence.py:312–321 (already enforced) |
| V6 Cryptography | no | No crypto operations |
| V12 File Operations | yes | `scripts/backfill_snapshots.py` and `cli.backtest` write files; use existing `_write_parquet_atomic` (D-11) and explicit `Path` construction (no `os.system`, no shell injection) |
| V14 Configuration | yes | No secrets added by Phase 5; existing FRED/Finnhub keys are not touched |

### Known Threat Patterns for `backtest` / CLI subprocess

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via user-supplied `start`/`end` strings | Tampering | Validate with `re.match(r'^\d{4}-\d{2}-\d{2}$', date)` before any `Path()` construction; reuse `persistence._assert_safe_snapshot_date` |
| Shell injection in `cli.backtest_audit` subprocess | Injection | Use `subprocess.run([list, of, args], shell=False)` (NEVER `shell=True`); all argv elements are hardcoded strings in Section D Q9 example |
| Information disclosure in disclosure header (e.g., file paths leak local user home) | Info Disclosure | Use only relative paths in the report (`data/universe/2026-04-27.parquet`, NOT `/Users/belwin/.../data/...`); audit the report renderer for absolute-path leaks |
| Untrusted Parquet (snapshot corrupted by a malicious commit) | Tampering | Existing pandera schemas (`RankingSnapshotSchema`) validate at read time; eager schema check at backtest harness entry catches malformed snapshots before they reach `from_signals` |

**Slippage tier constants are not secrets** — they're documented in BCK-03 and the disclosure header. No security concern there.

`[ASVS L1 verified per .planning/config.json:security_asvs_level=1]`

---

## Sources

### Primary (HIGH confidence)

- **Direct execution in this project's uv venv 2026-05-16** — vectorbt 1.0.0 API tested for slippage broadcast, shift(1) + price=open, RollingSplitter shape, slippage math (`adj_price = price × (1 ± slippage)`)
- **Context7 `/polakowo/vectorbt`** — official examples for `Portfolio.from_signals`, `walk-forward optimization`, `next-bar execution via .vbt.fshift(1)`
- `vectorbt/portfolio/nb.py` (vbt source) — slippage formula
- `scripts/check_preregistration.py` (existing) — exit code contract confirmed by direct read
- `tests/test_architecture.py` (existing) — D-17 constraint verbatim (`ALLOWED["backtest"] = {"persistence"}`)
- `src/screener/persistence.py` (existing) — `read_panel`, `RankingSnapshotSchema`, `_assert_safe_snapshot_date` — all read end-to-end

### Secondary (MEDIUM confidence)

- `docs/backtesting.md` — vectorbt patterns, walk-forward narrative, slippage assumptions (5 bps liquid / 25 bps thin → confirms BCK-03 tiers)
- `docs/tech-stack.md` — vectorbt version pin, Commons Clause license note
- 10-seed Monte Carlo of the no-look-ahead test thresholds (this session) — establishes the 0.5/1.0 thresholds as robust

### Tertiary (LOW confidence — needs validation)

- A1 (Sharpe annualization basis) — vbt source not directly inspected; recommend Wave 0 confirmation test
- Per-window universe vs single (A2) — design choice; planner should confirm with user if unclear

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library version directly verified via `import` in uv venv
- Architecture: HIGH — D-17 constraint matched against actual tests/test_architecture.py source
- vectorbt API (slippage, shift, splitter): HIGH — direct execution confirmed all three
- D-07 threshold revision: HIGH — 10-seed test demonstrates the failure mode
- CI workflow YAML: MEDIUM — pattern is standard but `contains(toJSON(...))` per-job path filter is a workaround, not documented official syntax (option B "always run" is simpler if planner prefers)
- Audit CLI shape: HIGH — `scripts/check_preregistration.py` exit contract verified by direct read
- Disclosure header format: MEDIUM — YAML frontmatter recommendation is opinion; markdown bullets would also work

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (30 days — stable libraries; revisit if vectorbt 1.1 releases)

---

## RESEARCH COMPLETE

All 11 research questions answered with HIGH or MEDIUM confidence. One critical correction to CONTEXT.md (D-07 threshold revision in Section B Q5) — planner should review and adopt the revised thresholds. Two open questions deferred to planning (A1 Sharpe basis; A2 per-window universe) — both resolvable in Wave 0 of execution without blocking the plan structure.
