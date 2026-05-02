---
phase: 01-repo-skeleton-ci-hygiene
plan: 02
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - src/screener/__init__.py
  - src/screener/cli.py
  - src/screener/config.py
  - src/screener/obs.py
  - src/screener/persistence.py
  - src/screener/regime.py
  - src/screener/sizing.py
  - src/screener/data/__init__.py
  - src/screener/indicators/__init__.py
  - src/screener/signals/__init__.py
  - src/screener/publishers/__init__.py
  - src/screener/backtest/__init__.py
  - src/screener/catalysts/__init__.py
  - src/screener/ml/__init__.py
autonomous: true
requirements: [FND-01, FND-02]
must_haves:
  truths:
    - "Every layer directory under src/screener/ exists with a one-line module-docstring __init__.py declaring its role and import policy"
    - "src/screener/cli.py exposes a typer app with all 9 v1 subcommands per D-14 (refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit), each logging a [stub] line via structlog and exiting 0"
    - "src/screener/config.py defines a Settings(BaseSettings) class with all 7 D-15 fields and SettingsConfigDict(env_file='.env')"
    - "src/screener/obs.py provides a configure() helper that wires structlog to JSON output on stdout"
    - "Running `screener --help` (after uv sync) lists all 9 subcommands"
    - "Running each `screener <subcommand>` exits 0 and emits a structured [stub] log line"
  artifacts:
    - path: "src/screener/__init__.py"
      provides: "Package marker"
    - path: "src/screener/cli.py"
      provides: "Typer composition root with full v1 subcommand surface (D-14)"
      contains: "app = typer.Typer"
    - path: "src/screener/config.py"
      provides: "pydantic-settings Settings class with all v1 env fields (D-15)"
      contains: "class Settings(BaseSettings)"
    - path: "src/screener/obs.py"
      provides: "structlog JSON-output configuration helper"
      contains: "def configure"
    - path: "src/screener/persistence.py"
      provides: "Module-docstring placeholder (D-13); pandera schemas land in Phase 2"
    - path: "src/screener/regime.py"
      provides: "Module-docstring placeholder (D-13); regime logic lands in Phase 3"
    - path: "src/screener/sizing.py"
      provides: "Module-docstring placeholder (D-13); sizing logic lands in Phase 7"
    - path: "src/screener/data/__init__.py"
      provides: "Layer marker; the only I/O layer (D-13)"
    - path: "src/screener/indicators/__init__.py"
      provides: "Layer marker; pure-function indicator panel (D-13)"
    - path: "src/screener/signals/__init__.py"
      provides: "Layer marker; pure-function signal stack (D-13)"
    - path: "src/screener/publishers/__init__.py"
      provides: "Layer marker; report/journal/snapshot fan-out (D-13)"
    - path: "src/screener/backtest/__init__.py"
      provides: "Layer marker; reads disk artifacts only, never network (D-13)"
    - path: "src/screener/catalysts/__init__.py"
      provides: "Layer marker; M2 reserve seam (D-13)"
    - path: "src/screener/ml/__init__.py"
      provides: "Layer marker; M2 ML reserve seam (D-13)"
  key_links:
    - from: "src/screener/cli.py"
      to: "src/screener/obs.py"
      via: "configure() called at startup"
      pattern: "obs\\.configure\\("
    - from: "src/screener/cli.py"
      to: "src/screener/config.py"
      via: "settings imported for command bodies (Phase 2+ usage)"
      pattern: "from screener\\.config import"
    - from: "Makefile (Plan 04)"
      to: "src/screener/cli.py"
      via: "make data/rank/report/backtest shell out to typer subcommands"
      pattern: "screener (refresh-universe|score|report|backtest)"
---

<objective>
Scaffold the full src/screener/ source tree per the architectural DAG (CLAUDE.md §10.1, ARCHITECTURE.md), with module-docstring-only layer markers (D-13), a real Settings class (D-15), a structlog JSON-output configuration helper, and a typer CLI exposing every v1 subcommand as a logging no-op (D-14).

Purpose: Lock the architectural seams on day one. Every later phase fills in module bodies; this plan fixes the layer set and the CLI contract that the Makefile and `tests/test_architecture.py` depend on.

Output: A package that imports cleanly, exposes `screener` as a console script, and where every v1 subcommand exits 0 with a structured [stub] log line. The structure of the codebase is now stable for the rest of v1.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md
@.planning/research/ARCHITECTURE.md
@CLAUDE.md
@pyproject.toml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create config.py (Settings) and obs.py (structlog config)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-15 — exact Settings field set; Claude's Discretion — structlog baseline)
    - CLAUDE.md §10.2 (Configuration pattern)
    - CLAUDE.md §10.4 (Logging / observability)
    - pyproject.toml (confirms pydantic-settings and structlog are pinned)
  </read_first>
  <files>src/screener/__init__.py, src/screener/config.py, src/screener/obs.py</files>
  <action>
Create the package marker `src/screener/__init__.py` and the two foundational modules.

**`src/screener/__init__.py`** (single docstring; no exports):
```python
"""screener — long-only EOD momentum swing-trading screener for Russell 1000.

Architecture: layered DAG (data → indicators → signals → regime → sizing →
publishers → backtest). See .planning/research/ARCHITECTURE.md and
tests/test_architecture.py for the import contract.
"""
```

**`src/screener/config.py`** (full Settings class per D-15):
```python
"""Typed application settings (env-driven via pydantic-settings).

Loads from `.env` at the repo root; values can be overridden by environment
variables. Phase 1 ships the seven fields the v1 stack will consume; later
phases extend the Settings class additively.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """v1 application settings.

    Fields below are populated from `.env` (gitignored) or process env vars.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # External-service credentials
    FINNHUB_API_KEY: str = ""
    FRED_API_KEY: str = ""
    EDGAR_IDENTITY: str = ""

    # Universe selection
    UNIVERSE: str = "russell1000"

    # Indicator + sizing parameters
    RS_LOOKBACK_DAYS: int = 252
    RISK_PCT_PER_TRADE: float = 0.0075
    ACCOUNT_EQUITY: float = 100_000.0


settings = Settings()
```

**`src/screener/obs.py`** (structlog JSON-output helper; named obs.py to avoid shadowing stdlib `logging`):
```python
"""Observability — structured JSON logging via structlog.

`configure()` wires structlog to JSON output on stdout with timestamping and
log-level binding. Called at CLI startup; importing modules use
`structlog.get_logger(__name__)` to obtain a logger.
"""

import logging
import sys

import structlog


def configure(level: str = "INFO") -> None:
    """Configure structlog for JSON output on stdout.

    Idempotent — safe to call multiple times.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```
  </action>
  <verify>
    <automated>uv run python -c "from screener.config import Settings, settings; s = Settings(); assert s.UNIVERSE == 'russell1000' and s.RS_LOOKBACK_DAYS == 252 and s.RISK_PCT_PER_TRADE == 0.0075 and s.ACCOUNT_EQUITY == 100_000.0" &amp;&amp; uv run python -c "from screener.obs import configure; configure(); import structlog; structlog.get_logger().info('ok', test=1)"</automated>
  </verify>
  <acceptance_criteria>
    - `src/screener/__init__.py`, `src/screener/config.py`, `src/screener/obs.py` all exist
    - `grep -F 'class Settings(BaseSettings)' src/screener/config.py` matches
    - All 7 D-15 fields appear in config.py: `grep -E '(FINNHUB_API_KEY|FRED_API_KEY|EDGAR_IDENTITY|UNIVERSE|RS_LOOKBACK_DAYS|RISK_PCT_PER_TRADE|ACCOUNT_EQUITY)' src/screener/config.py | wc -l` is at least 7
    - `grep -F 'env_file=".env"' src/screener/config.py` matches
    - `grep -F 'def configure' src/screener/obs.py` matches
    - `grep -F 'JSONRenderer' src/screener/obs.py` matches
    - `uv run python -c "from screener.config import Settings; s = Settings()"` exits 0
    - `uv run python -c "from screener.obs import configure; configure()"` exits 0
  </acceptance_criteria>
  <done>Settings class loads from .env with all 7 D-15 fields and sensible defaults; obs.configure() wires structlog to JSON output without shadowing stdlib logging.</done>
</task>

<task type="auto">
  <name>Task 2: Create layer markers (__init__.py docstrings) and standalone module placeholders</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-13 — layer set; module-docstring-only; no signatures, no NotImplementedError)
    - .planning/research/ARCHITECTURE.md (Component Responsibilities table; layer-import contract)
  </read_first>
  <files>src/screener/persistence.py, src/screener/regime.py, src/screener/sizing.py, src/screener/data/__init__.py, src/screener/indicators/__init__.py, src/screener/signals/__init__.py, src/screener/publishers/__init__.py, src/screener/backtest/__init__.py, src/screener/catalysts/__init__.py, src/screener/ml/__init__.py</files>
  <action>
Create one file per layer with a single one-line module docstring stating the layer's role and import policy. Do NOT add functions, signatures, or `NotImplementedError`.

**`src/screener/persistence.py`**:
```python
"""persistence — Parquet/SQLite read+write helpers and pandera schemas.

The only module that owns disk-format details. Pandera schemas land in Phase 2
(DAT-09); this Phase 1 placeholder reserves the seam.
"""
```

**`src/screener/regime.py`**:
```python
"""regime — universe-wide market-regime gate (one row per date).

Emits a discrete state in {Confirmed Uptrend, Uptrend Under Pressure,
Correction} plus a continuous regime_score in [0, 1]. Imports `data/` and
`indicators/`; consumed by `sizing` and `publishers/`. Implementation lands in
Phase 3 (REG-01..REG-04).
"""
```

**`src/screener/sizing.py`**:
```python
"""sizing — per-playbook entry/stop/shares dispatched by playbook tag.

Pure function: takes the ranked DataFrame plus the indicator panel and returns
the same DataFrame with sizing columns appended. Imports `signals/`, `regime`,
`config`. Implementation lands in Phase 7 (SIZ-01..SIZ-05).
"""
```

**`src/screener/data/__init__.py`**:
```python
"""data — the ONLY layer permitted to make network I/O.

Owns yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes
Parquet/SQLite via `persistence`. Downstream layers consume DataFrames and
never call back into `data/` from inside indicators/signals/regime/sizing.
"""
```

**`src/screener/indicators/__init__.py`**:
```python
"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""
```

**`src/screener/signals/__init__.py`**:
```python
"""signals — pure-function signal stack; consumes the indicator panel.

Includes minervini (Trend Template), qullamaggie (Setup A scan), canslim
(C+L+M overlay), and composite (the single M2 extension point — takes a
weights dict, emits playbook tag). Imports only `indicators/`, `regime`,
`persistence`, `config`. Never reads OHLCV directly.
"""
```

**`src/screener/publishers/__init__.py`**:
```python
"""publishers — thin (ranked_df) -> file_artifact functions.

Three publishers fan out from the same ranked DataFrame: report (Markdown),
journal (SQLite, the v2 ML training contract), snapshot (Parquet ranking
history for backtest). Implementation lands in Phase 4+.
"""
```

**`src/screener/backtest/__init__.py`**:
```python
"""backtest — offline-only; reads disk artifacts, never makes network calls.

vectorbt 1.0 walk-forward harness, no-look-ahead test target, slippage tiers.
Imports `persistence` + stdlib only. The no-look-ahead test gate (FND-04)
lands here in Phase 5.
"""
```

**`src/screener/catalysts/__init__.py`**:
```python
"""catalysts — M2 reserve seam (FinBERT sentiment, EDGAR insider flags).

v1 ships this directory empty; the seam exists so M2 can plug in catalyst
features without refactoring composite scoring. Implementation in Phase 6
(CAT-01..CAT-04 limited subset) and M2.
"""
```

**`src/screener/ml/__init__.py`**:
```python
"""ml — M2 ML reserve seam (LightGBM probability, SHAP explainability).

v1 ships this directory empty; v2 adds `predict.py`, `features.py`, `train.py`
that read the journal.sqlite training set and emit an `ml_probability` column
that composite.py adds as one weight key.
"""
```
  </action>
  <verify>
    <automated>for f in src/screener/persistence.py src/screener/regime.py src/screener/sizing.py src/screener/data/__init__.py src/screener/indicators/__init__.py src/screener/signals/__init__.py src/screener/publishers/__init__.py src/screener/backtest/__init__.py src/screener/catalysts/__init__.py src/screener/ml/__init__.py; do test -f "$f" || { echo "MISSING: $f"; exit 1; }; done &amp;&amp; uv run python -c "import screener.data, screener.indicators, screener.signals, screener.publishers, screener.backtest, screener.catalysts, screener.ml, screener.persistence, screener.regime, screener.sizing"</automated>
  </verify>
  <acceptance_criteria>
    - All 10 files exist
    - Every file's content is exactly ONE module docstring (verifiable by `python -c "import ast; mod=ast.parse(open('PATH').read()); assert len(mod.body)==1 and isinstance(mod.body[0], ast.Expr) and isinstance(mod.body[0].value, ast.Constant)"`)
    - `uv run python -c "import screener.data, screener.indicators, screener.signals, screener.publishers, screener.backtest, screener.catalysts, screener.ml, screener.persistence, screener.regime, screener.sizing"` exits 0
    - No file contains `NotImplementedError`, function `def`, or class `class` — verify with `! grep -rn -E '(NotImplementedError|^def |^class )' src/screener/persistence.py src/screener/regime.py src/screener/sizing.py src/screener/*/__init__.py`
  </acceptance_criteria>
  <done>Every layer marker exists with a single role-stating docstring; the architectural DAG is structurally locked; later phases fill in the bodies.</done>
</task>

<task type="auto">
  <name>Task 3: Create cli.py with the full v1 typer subcommand surface (no-op stubs per D-14)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-14 — exact subcommand list; structured [stub] log line; exit 0; D-15 — Settings)
    - src/screener/obs.py (just authored — configure())
    - pyproject.toml (confirms `screener = "screener.cli:app"` console-script)
  </read_first>
  <files>src/screener/cli.py</files>
  <action>
Create `src/screener/cli.py` with a typer app exposing all 9 v1 subcommands. Each subcommand:
1. Calls `obs.configure()` (idempotent) to ensure structlog is wired.
2. Logs a structured `[stub] <command> not yet implemented` line via structlog.
3. Exits 0 (no `raise typer.Exit(1)`).

The Makefile (Plan 04) shells out to these subcommands, so the names below are the contract. Do NOT add a `__main__` block — the console-script entry-point declared in pyproject.toml's `[project.scripts]` handles invocation.

```python
"""cli — typer composition root for the screener console script.

Exposes the v1 subcommand surface (D-14). Phase 1 ships every subcommand as a
structured-logging no-op; later phases fill in the bodies. The Makefile in
Plan 04 shells out to these subcommands.
"""

import typer
import structlog

from screener.obs import configure as configure_logging

app = typer.Typer(
    name="screener",
    help="Long-only EOD momentum swing-trading screener (Russell 1000).",
    no_args_is_help=True,
    add_completion=False,
)

log = structlog.get_logger(__name__)


def _stub(command: str) -> None:
    """Log a structured [stub] line and return (exit 0)."""
    configure_logging()
    log.info("stub", command=command, message=f"[stub] {command} not yet implemented")


@app.command("refresh-universe")
def refresh_universe() -> None:
    """Refresh the Russell 1000 universe (Wikipedia + iShares IWB CSV); writes weekly Parquet snapshot."""
    _stub("refresh-universe")


@app.command("refresh-ohlcv")
def refresh_ohlcv() -> None:
    """Refresh OHLCV via yfinance (with Stooq fallback); incrementally append per-ticker Parquet."""
    _stub("refresh-ohlcv")


@app.command("refresh-macro")
def refresh_macro() -> None:
    """Refresh macro inputs (SPY, ^IXIC, ^VIX, NYSE A/D, FRED yields)."""
    _stub("refresh-macro")


@app.command("refresh-fundamentals")
def refresh_fundamentals() -> None:
    """Refresh fundamentals (Finnhub earnings calendar + EPS); 45-day post-quarter-end lag enforced."""
    _stub("refresh-fundamentals")


@app.command("score")
def score() -> None:
    """Compute composite scores + playbook tags over the universe; write data/snapshots/YYYY-MM-DD.parquet."""
    _stub("score")


@app.command("report")
def report() -> None:
    """Render the daily Markdown report to reports/YYYY-MM-DD.md."""
    _stub("report")


@app.command("journal")
def journal() -> None:
    """Append actionable picks to data/journal.sqlite (the v2 ML training contract)."""
    _stub("journal")


@app.command("backtest")
def backtest() -> None:
    """Run vectorbt walk-forward backtest (3-yr IS / 1-yr OOS rolling windows)."""
    _stub("backtest")


@app.command("backtest-audit")
def backtest_audit() -> None:
    """Run the forensic checklist (no-look-ahead, weight-pre-registration hash, universe snapshot date)."""
    _stub("backtest-audit")
```
  </action>
  <verify>
    <automated>uv run screener --help | grep -E "(refresh-universe|refresh-ohlcv|refresh-macro|refresh-fundamentals|score|report|journal|backtest|backtest-audit)" | wc -l | grep -q '^[[:space:]]*9$' &amp;&amp; for cmd in refresh-universe refresh-ohlcv refresh-macro refresh-fundamentals score report journal backtest backtest-audit; do uv run screener "$cmd" || { echo "FAILED: $cmd"; exit 1; }; done</automated>
  </verify>
  <acceptance_criteria>
    - `src/screener/cli.py` exists
    - `grep -F 'app = typer.Typer' src/screener/cli.py` matches
    - All 9 subcommand names appear via `@app.command(...)`: `grep -cE '@app\.command\("(refresh-universe|refresh-ohlcv|refresh-macro|refresh-fundamentals|score|report|journal|backtest|backtest-audit)"\)' src/screener/cli.py` returns 9
    - `uv run screener --help` lists all 9 subcommands
    - Each `uv run screener <subcommand>` exits 0
    - Each subcommand emits a JSON line containing `"command": "<subcommand>"` and `"message": "[stub] <subcommand> not yet implemented"` to stdout (verifiable via: `uv run screener score 2>&1 | grep -F '"command": "score"'`)
    - No subcommand calls `typer.Exit(1)` or `raise` — verify: `! grep -E 'typer\.Exit\(1\)|raise [A-Z]' src/screener/cli.py`
  </acceptance_criteria>
  <done>typer CLI exposes the full v1 surface; every subcommand exits 0 with a structured [stub] log line; the Makefile in Plan 04 has stable subcommand names to shell out to.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| stdin-CLI ↔ python-process | typer parses argv; user-provided arg values flow into log messages |
| process-env ↔ Settings | pydantic-settings reads `.env`; values include API keys |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | Settings logs API keys | mitigate | obs.py uses structured JSON renderer; Phase 2+ MUST avoid logging Settings as a whole. Phase 1 stubs do not access `settings.FINNHUB_API_KEY` etc., so leak surface is zero today. |
| T-02-02 | Tampering | typer subcommand surface | mitigate | All 9 subcommand names locked by D-14 and verified by Plan 03's `tests/test_cli_smoke.py`. Adding/removing a subcommand without updating the test fails CI. |
| T-02-03 | Spoofing | console-script entry point | accept | hatchling builds the wheel; `screener` executable is registered via `[project.scripts]`. Standard packaging — no realistic spoofing surface for a personal-trading tool. |
| T-02-04 | Denial of Service | infinite loop in CLI stub | mitigate | Each stub is 2 lines (configure + log) — no loops, no I/O. Plan 03's smoke test asserts each subcommand exits within seconds. |

</threat_model>

<verification>
After all three tasks complete:
1. `uv run python -c "from screener.config import settings; from screener.obs import configure; configure(); import screener.data, screener.indicators, screener.signals, screener.publishers, screener.backtest, screener.catalysts, screener.ml, screener.persistence, screener.regime, screener.sizing"` exits 0
2. `uv run screener --help` lists all 9 v1 subcommands
3. Each `uv run screener <subcommand>` exits 0 with a structured `[stub]` log line on stdout
4. No file in src/screener/persistence.py, regime.py, sizing.py, or any */__init__.py contains `def `, `class `, or `NotImplementedError`
</verification>

<success_criteria>
- All 13 source files (`__init__.py`, `cli.py`, `config.py`, `obs.py`, `persistence.py`, `regime.py`, `sizing.py`, plus 7 layer `__init__.py` files) exist with the content specified
- Settings(BaseSettings) class declares all 7 D-15 fields and loads from `.env`
- structlog `configure()` produces JSON output on stdout when invoked
- The typer CLI exposes all 9 v1 subcommands per D-14
- Layer-marker docstrings declare the architectural role and import policy each layer must obey (the contract `tests/test_architecture.py` enforces in Plan 03)
- No "real" logic ships in this plan — only seams (D-13)
</success_criteria>

<output>
After completion, create `.planning/phases/01-repo-skeleton-ci-hygiene/01-02-SUMMARY.md` with:
- File tree under src/screener/
- Confirmation that `uv run screener --help` lists all 9 subcommands
- Confirmation that `uv run python -c "import screener.<every layer>"` exits 0
- Notes on any docstring wording adjustments
</output>
