# Phase 2: Data Foundation - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 18 (8 CREATE + 10 MODIFY)
**Analogs found:** 18 / 18 (every file has at least one Phase-1 sibling that establishes module/test conventions; Phase 2 introduces three brand-new idioms — atomic-write, pandera DataFrameModel, tenacity wrapper — sourced from RESEARCH.md §"Pattern 1/2/5" since no Phase 1 analog exists)

---

## File Classification

### CREATE

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/screener/data/universe.py` | data-fetcher (HTTP) | request-response → file-I/O | `src/screener/obs.py` (module shape) + RESEARCH.md §"Pattern 6" (logic) | role-match |
| `src/screener/data/ohlcv.py` | data-fetcher + orchestrator | request-response → file-I/O | `src/screener/obs.py` (module shape) + RESEARCH.md §"Pattern 2/3/4" (logic) | role-match |
| `src/screener/data/stooq.py` | data-fetcher (adapter) | request-response → transform | `src/screener/obs.py` (module shape) + RESEARCH.md §"Pattern 4" pitfalls | role-match |
| `tests/test_data_universe.py` | test (unit) | mocked HTTP → assert | `tests/test_architecture.py` (AST/file-walk style) + `tests/test_cli_smoke.py` (CliRunner shape) | role-match |
| `tests/test_data_ohlcv.py` | test (unit + golden-file) | fixture → assert | `tests/test_cli_smoke.py` (loop-over-cases idiom) | role-match |
| `tests/test_data_stooq.py` | test (unit) | fixture → adapter → assert | `tests/test_cli_smoke.py` | role-match |
| `tests/test_persistence.py` | test (unit) | DataFrame → schema → assert | `tests/test_architecture.py` (assert-collection style) | role-match |
| (n/a — fixtures live in conftest extension) | | | | |

### MODIFY

| File | Role | Data Flow | Closest Analog (already in repo) | Match Quality |
|------|------|-----------|-----------------------------------|---------------|
| `src/screener/persistence.py` | schema + atomic-writer module | DataFrame I/O | `src/screener/config.py` (Settings extension shape) + RESEARCH.md §"Pattern 5" (pandera) | exact (file already exists, docstring already says "Pandera schemas land in Phase 2") |
| `src/screener/config.py` | typed config | n/a | `src/screener/config.py` itself (existing fields are the template) | exact (additive extension only) |
| `src/screener/cli.py` | CLI dispatcher | typer command → data/ call | `src/screener/cli.py` itself (D-14 stub bodies are the template to replace) | exact |
| `src/screener/data/__init__.py` | barrel/re-export | import → re-export | `src/screener/__init__.py` (module-marker style) | exact (currently 6-line docstring; extension adds re-exports) |
| `tests/conftest.py` | shared fixtures | yield/return DataFrame | `tests/conftest.py` itself (`repo_root`, `src_screener` are the template) | exact |
| `tests/test_cli_smoke.py` | integration test | CliRunner → assert | `tests/test_cli_smoke.py` itself (existing two tests are the template) | exact |
| `pyproject.toml` | manifest | n/a | `pyproject.toml` itself (existing `[project.dependencies]` is the template) | exact |
| `.gitignore` | repo policy | n/a | `.gitignore` itself (existing `/data/` rule with comment is the template) | exact |
| `README.md` | docs | n/a | (no analog content yet — additive section) | no analog |
| `.env.example` | env-var skeleton | n/a | (file may not yet exist — created if missing, mirrors `Settings` field-by-field) | no analog |

---

## Pattern Assignments

### `src/screener/persistence.py` (MODIFY — schemas + atomic-writers)

**Role:** the only owner of disk-format details (per existing docstring).
**Analog:** `src/screener/config.py` for module-shape; **RESEARCH.md §"Pattern 1" + §"Pattern 5"** for the new idioms.

**Existing module docstring already declares the seam** (`src/screener/persistence.py` lines 1–5):

```python
"""persistence — Parquet/SQLite read+write helpers and pandera schemas.

The only module that owns disk-format details. Pandera schemas land in Phase 2
(DAT-09); this Phase 1 placeholder reserves the seam.
"""
```

**Imports pattern to add** (mirror the lean style used in `src/screener/config.py` lines 13–15 — stdlib first, then third-party, no wildcard, no extras):

```python
# pattern from config.py: stdlib-first, third-party-second, no wildcard
from functools import lru_cache              # config.py line 13 idiom

from pydantic_settings import BaseSettings, SettingsConfigDict   # config.py line 15
```

For Phase 2, the equivalent block in `persistence.py` becomes:

```python
import os
import tempfile
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Index, Series

from screener.config import get_settings
```

**Pandera DataFrameModel pattern (NEW IDIOM — no Phase 1 analog).** Source: RESEARCH.md §"Pattern 5" lines 467–569. Quote verbatim from RESEARCH.md (this is the planner's template):

```python
class OhlcvPanelSchema(pa.DataFrameModel):
    ticker: Index[str] = pa.Field(check_name=True)
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)

    class Config:
        multiindex_strict = True
        multiindex_coerce = False
        strict = True
        coerce = False
```

The same shape applies to `UniverseSchema` and `SplitsSchema` (RESEARCH.md lines 505–536).

**Atomic-write pattern (NEW IDIOM).** Source: RESEARCH.md §"Pattern 1" lines 263–303. Phase 1 has no `tempfile + os.replace` analog — this is the canonical excerpt the planner copies into `_write_parquet_atomic()`:

```python
target.parent.mkdir(parents=True, exist_ok=True)
tmp = tempfile.NamedTemporaryFile(
    dir=target.parent,                  # MUST be same dir → same FS → atomic
    prefix=f".{target.name}.",
    suffix=".tmp",
    delete=False,
)
tmp_path = Path(tmp.name)
try:
    tmp.close()
    df.to_parquet(tmp_path, engine="pyarrow", index=True)
    os.replace(tmp_path, target)        # atomic on same FS
except Exception:
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    raise
```

**Settings access pattern** — match `config.py` line 40–48: never call `Settings()` directly; always go through the cached factory:

```python
# config.py lines 40–48 (existing, mandatory entry point)
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

In `persistence.py`, every settings-dependent function calls `settings = get_settings()` at the top of its body — never imports a module-level `settings` (that would defeat the lazy-load contract Phase 1 WR-01 introduced).

**Validation policy split** — D-16 mandates `lazy=False` at write, `lazy=True` at read. Encode as two helpers, exactly as RESEARCH.md lines 539–546:

```python
def validate_at_write(schema_cls, df: pd.DataFrame) -> pd.DataFrame:
    return schema_cls.validate(df, lazy=False)


def validate_at_read(schema_cls, df: pd.DataFrame) -> pd.DataFrame:
    return schema_cls.validate(df, lazy=True)
```

---

### `src/screener/config.py` (MODIFY — additive D-20 fields)

**Role:** typed env-driven config (already exists). Phase 2 ADDS 8 fields per CONTEXT.md D-20.
**Analog:** the file itself — extend the `Settings` class.

**Settings extension pattern** (verbatim from `src/screener/config.py` lines 18–37). Match the EXACT field-declaration style — CAPS naming, `: Type = default` syntax, blank line between logical groups, leading-comment heading per group:

```python
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
```

**Phase 2 additions (D-20)** insert AFTER the existing groups and BEFORE the closing of the class. Use a new comment heading per CONTEXT.md taxonomy. Type hints use `Path` from stdlib (import alongside `from functools import lru_cache`):

```python
# Phase 2 additions (D-20) — keep ordering: paths, then date-string, then thresholds, then pacing.
from pathlib import Path                       # add to import block

# inside class Settings:
    # Phase 2 — data-layer paths and policy
    OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
    UNIVERSE_CACHE_DIR: Path = Path("data/universe")
    OHLCV_BACKFILL_START: str = "2005-01-01"
    UNIVERSE_HEALTH_THRESHOLD: float = 0.95
    STOOQ_BREAKER_PROBE_N: int = 50
    STOOQ_BREAKER_THRESHOLD: float = 0.80
    OHLCV_FETCH_SLEEP_MIN_S: float = 0.5
    OHLCV_FETCH_SLEEP_MAX_S: float = 1.5
```

**Cache-clear discipline** — the docstring at `config.py` lines 1–11 already documents the test contract: "Tests can override env vars and call `get_settings.cache_clear()` to force re-evaluation." Phase 2 tests that monkey-patch settings (e.g., `OHLCV_CACHE_DIR=tmp_path`) MUST follow this same pattern.

---

### `src/screener/cli.py` (MODIFY — replace stub bodies for `refresh-universe` / `refresh-ohlcv`)

**Role:** typer composition root.
**Analog:** the file itself — `cli.py` lines 23–38 establish the canonical subcommand shape. Phase 2 REPLACES the `_stub("refresh-universe")` body and the `_stub("refresh-ohlcv")` body, leaving the other 7 stubs intact.

**Stub idiom to preserve elsewhere** (`src/screener/cli.py` lines 23–27):

```python
def _stub(command: str) -> None:
    """Log a structured [stub] line and return (exit 0)."""
    configure_logging()
    log.info("stub", command=command, message=f"[stub] {command} not yet implemented")
```

**Existing decorator + signature pattern** to MATCH for any new option flags (`src/screener/cli.py` lines 29–38):

```python
@app.command("refresh-universe")
def refresh_universe() -> None:
    """Refresh the Russell 1000 universe (Wikipedia + iShares IWB); weekly Parquet snapshot."""
    _stub("refresh-universe")


@app.command("refresh-ohlcv")
def refresh_ohlcv() -> None:
    """Refresh OHLCV via yfinance (Stooq fallback); incremental per-ticker Parquet append."""
    _stub("refresh-ohlcv")
```

**Phase 2 fills these bodies. Pattern to copy** — keep the kebab-case `@app.command(...)` registration, keep the snake_case Python function, keep the docstring as the typer help string. For the new `--force` and `--ticker` flags use Typer's `Option` and `Annotated` syntax:

```python
import typer
from typing import Annotated

@app.command("refresh-universe")
def refresh_universe(
    force: Annotated[bool, typer.Option("--force", help="Re-write today's snapshot even if this ISO week's file exists.")] = False,
) -> None:
    """Refresh the Russell 1000 universe; weekly Parquet snapshot (D-01, D-02)."""
    configure_logging()
    # delegate to data/universe.py — never inline business logic in cli.py
    ...

@app.command("refresh-ohlcv")
def refresh_ohlcv(
    ticker: Annotated[str | None, typer.Option("--ticker", help="Single-ticker debug fetch; bypasses universe loop.")] = None,
) -> None:
    """Refresh per-ticker OHLCV via yfinance (Stooq fallback)."""
    configure_logging()
    ...
```

**Two contracts the planner MUST preserve** (verified by `tests/test_cli_smoke.py`):

1. The 9-subcommand surface from D-14 — Phase 2 does NOT add or rename any subcommand. The existing 9 names listed in `tests/test_cli_smoke.py` lines 14–24 are locked.
2. Every subcommand calls `configure_logging()` at the top. Phase 1's stub idiom routes through `_stub(...)` which calls `configure_logging()` itself; Phase 2's filled-in bodies must call `configure_logging()` directly (the first line of the function) to preserve the per-invocation idempotent-config contract documented in `01-02-SUMMARY.md` "Stub idempotence."

**Health-gate exit pattern** — when `(yf_ok + stooq_ok) / universe_size < UNIVERSE_HEALTH_THRESHOLD`, the CLI must exit non-zero. Idiom (matches the typer convention; no Phase 1 analog because all current bodies are stubs):

```python
log.error("health_check_failed", n_pass=combined_ok, n_total=n, threshold=settings.UNIVERSE_HEALTH_THRESHOLD)
raise typer.Exit(code=1)
```

The test harness (`test_cli_smoke.py` Phase 2 additions) asserts on this exact event name `health_check_failed` / `health_check_passed` per the Discretion section of CONTEXT.md "Structured logging events."

---

### `src/screener/data/universe.py` (CREATE)

**Role:** iShares IWB CSV fetcher + parser + `normalize_ticker()` + weekly snapshot writer.
**Analog:** No Phase 1 sibling has logic. Closest module-shape analogs are `src/screener/obs.py` (single-purpose helper module) and `src/screener/data/__init__.py` (the layer-marker docstring that establishes the layer's import policy). Logic is sourced from RESEARCH.md §"Pattern 6" lines 571–673.

**Module-docstring style to mirror** (`src/screener/obs.py` lines 1–6):

```python
"""Observability — structured JSON logging via structlog.

`configure()` wires structlog to JSON output on stdout with timestamping and
log-level binding. Called at CLI startup; importing modules use
`structlog.get_logger(__name__)` to obtain a logger.
"""
```

For `data/universe.py` the equivalent header — short, role-stating, points at the canonical reference:

```python
"""Universe — iShares IWB CSV fetcher, parser, normalizer, and weekly snapshot writer.

The Russell 1000 source of truth (D-01). Implements the IWB AJAX CSV path
and the BRKB/BFB/BFA allowlist (D-03 amended). See RESEARCH.md §"Pattern 6"
for verified-live live parsing constants and §"Pitfall 5/6" for sharp edges.
"""
```

**structlog import + per-module logger pattern** (mirrors `src/screener/cli.py` line 20):

```python
import structlog

log = structlog.get_logger(__name__)
```

**Allowed imports per layer contract** (`tests/test_architecture.py` lines 30–32):

```python
ALLOWED["data"] = {"persistence", "config", "obs"}
```

So `data/universe.py` may import:
- stdlib (`io`, `re`, `datetime`)
- `pandas`, `requests`, `requests_cache` (third-party network/transform — explicitly allowed for `data/`)
- `screener.persistence` (write helpers)
- `screener.config` (`get_settings`)
- `structlog` (logger only — `obs.configure()` is called at CLI entry, not in modules)

**MUST NOT import:** `screener.indicators`, `screener.signals`, `screener.regime`, `screener.sizing`, `screener.publishers`. The architecture test will fail the build if it does.

**iShares parsing constants and parser body** — RESEARCH.md §"Pattern 6" lines 582–672 is the verbatim template. Key excerpts the planner copies:

```python
ISHARES_IWB_URL = (
    "https://www.ishares.com/us/products/239707/"
    "ishares-russell-1000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWB_holdings&dataType=fund"
)
ISHARES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
ISHARES_SKIPROWS = 9
ISHARES_ENCODING = "utf-8-sig"   # strips the BOM
```

**`normalize_ticker` allowlist** (RESEARCH.md lines 639–658, after D-03 amendment):

```python
ALLOWLIST = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A"}

def normalize_ticker(raw: str) -> str:
    return ALLOWLIST.get(raw, raw)
```

**Sanity check pattern** (RESEARCH.md lines 661–672) — raises `ValueError` on row count or missing columns, NOT a custom exception. Phase 1 has no exception-class precedent; default to stdlib `ValueError` for parser failures and a custom `StaleOrEmptyError` (RESEARCH.md §"Pattern 2") for fetch failures.

---

### `src/screener/data/ohlcv.py` (CREATE)

**Role:** yfinance fetcher + tenacity wrapper + circuit-breaker orchestrator + invariant gate + atomic writer caller.
**Analog:** no Phase 1 logic sibling. Module-shape mirrors `src/screener/obs.py`. Logic sourced from RESEARCH.md §"Pattern 2" (lines 305–369), §"Pattern 3" (lines 374–413), §"Pattern 4" (lines 415–465).

**tenacity wrapper pattern (NEW IDIOM)** — RESEARCH.md §"Pattern 2" lines 334–363 verbatim. The `before_sleep_log(log, "warning")` is the structlog-compatible variant; this is the canonical Phase 2 retry incantation:

```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(log, "warning"),
    reraise=True,
)
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,            # D-17
        progress=False,
        threads=False,               # D-10 — NO batch/parallel
        actions=False,               # splits via Ticker.actions
        multi_level_index=False,     # yf 1.3.x default is True; flatten
    )
    if df is None or df.empty:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if df["Close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")
    return df
```

**Pacing pattern** (RESEARCH.md lines 366–369) — sequential sleep, never `yf.download(threads=True)`:

```python
def fetch_ohlcv_with_pacing(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = fetch_ohlcv(ticker, start, today)
    time.sleep(random.uniform(settings.OHLCV_FETCH_SLEEP_MIN_S, settings.OHLCV_FETCH_SLEEP_MAX_S))
    return df
```

**Sentinel-bar refetch pattern (D-07)** — RESEARCH.md §"Pattern 3" lines 379–413 is the canonical template. Critical: re-fetch from `last_cached_date` (not `last+1`) so the response includes the sentinel bar to compare against the cache; on mismatch, full-refetch from `OHLCV_BACKFILL_START`.

**Circuit-breaker pattern (D-12)** — RESEARCH.md §"Pattern 4" lines 421–464. Probe at exactly `i + 1 == STOOQ_BREAKER_PROBE_N`, compare `yf_ok / probe_n` to `STOOQ_BREAKER_THRESHOLD`, route remainder through `screener.data.stooq.fetch_ohlcv` on trip.

**Structured-log event names (per CONTEXT.md "Structured logging events" Discretion):**
- `fetch_start`, `fetch_success`, `fetch_fail` (per ticker)
- `breaker_tripped` (once per run)
- `health_check_passed` / `health_check_failed`
- `snapshot_written`

These are the exact event names Phase 8 (OPS-05) will route to `runs.jsonl`. Don't rename them.

---

### `src/screener/data/stooq.py` (CREATE)

**Role:** pandas-datareader Stooq adapter; column normalization; ascending-index reorder; D-08 invariant gate.
**Analog:** no Phase 1 sibling. Module-shape mirrors `src/screener/obs.py`. Logic sourced from RESEARCH.md §"Pitfall 3/4" lines 763–775.

**Stooq adapter contract** (per CONTEXT.md "specifics" lines 170–171):

> Stooq returns `Open / High / Low / Close / Volume` (PascalCase, sometimes with a leading `Date` index column). Map to lowercase canonical names in `data/stooq.py` before the pandera validation runs; the panel schema (D-15.1) is lowercase.

**Column-normalize idiom** (no Phase 1 analog; canonical pandas idiom):

```python
import pandas_datareader.data as pdr

def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = pdr.DataReader(ticker, "stooq", start=str(start))
    if df is None or df.empty:
        raise StaleOrEmptyError(f"stooq returned empty for {ticker}")
    df = df.sort_index(ascending=True)              # Stooq returns descending (Pitfall 4)
    df = df.rename(columns=str.lower)               # PascalCase → lowercase canonical (D-15.1)
    # Re-apply the same D-08 four-invariant gate as yfinance.
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale via stooq")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} stooq null close")
    return df
```

Note: lower-case is applied here to satisfy `OhlcvPanelSchema`; the yfinance path uses CapitalCase columns and `persistence.write_ohlcv_atomic()` should normalize to lowercase before validation. Either both paths emit lowercase here, OR `persistence` does the rename — pick one and document it. Recommendation: lowercase at the data/ → persistence boundary so persistence is dialect-agnostic.

---

### `src/screener/data/__init__.py` (MODIFY — re-exports)

**Role:** layer barrel + role-stating docstring (already exists, 6 lines).
**Analog:** the file itself.

**Existing docstring** (`src/screener/data/__init__.py` lines 1–6) — KEEP verbatim:

```python
"""data — the ONLY layer permitted to make network I/O.

Owns yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes
Parquet/SQLite via `persistence`. Downstream layers consume DataFrames and
never call back into `data/` from inside indicators/signals/regime/sizing.
"""
```

**Re-export pattern (additive)** — Python convention; no Phase 1 sibling has re-exports yet, so use the minimal canonical form. After the docstring add an `__all__` list and explicit imports so consumers can do `from screener.data import fetch_ohlcv, fetch_universe, normalize_ticker`:

```python
from screener.data.universe import fetch_ishares_iwb_csv, normalize_ticker, parse_ishares_iwb_csv
from screener.data.ohlcv import fetch_ohlcv, run_with_breaker
from screener.data.stooq import fetch_ohlcv as fetch_stooq_ohlcv

__all__ = [
    "fetch_ishares_iwb_csv",
    "fetch_ohlcv",
    "fetch_stooq_ohlcv",
    "normalize_ticker",
    "parse_ishares_iwb_csv",
    "run_with_breaker",
]
```

The architecture test (`tests/test_architecture.py` lines 30–32) treats `data` as a layer that may import `persistence`, `config`, `obs`. These intra-layer re-exports (`screener.data.universe` → `screener.data.__init__`) are allowed because the import target is still `data` itself.

**Optional: requests-cache session helper** — RESEARCH.md §"Pattern 7" lines 696–704 puts `get_cached_session()` in `data/__init__.py`. The planner can choose to land it here OR create a dedicated `src/screener/data/_http.py` module. Recommendation: keep `__init__.py` lean (just re-exports); put `get_cached_session()` in `data/universe.py` since iShares is the only HTTP-cache consumer in v1.

---

### `tests/conftest.py` (MODIFY — add 10 synthetic fixtures)

**Role:** shared pytest fixtures.
**Analog:** the file itself.

**Existing fixture style** (`tests/conftest.py` lines 12–21) — session-scoped, return-style (not yield), single-purpose docstring:

```python
@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root (parent of `tests/`)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_screener(repo_root: Path) -> Path:
    """Absolute path to src/screener/."""
    return repo_root / "src" / "screener"
```

**Phase 2 fixtures (per VALIDATION.md lines 87–96).** Style guidance derived from the existing pattern:

- **Scope:** Use `scope="session"` for read-only DataFrames built from constants (no per-test mutation). Use the default function scope only when the fixture mutates a tmp_path.
- **Return vs yield:** Existing fixtures use plain `return`. New fixtures that materialize DataFrames should also `return` (no teardown needed — pandas DataFrames are GC'd). `yield` only when the fixture creates filesystem state via `tmp_path` that should be cleaned (in practice pytest's `tmp_path` already handles this, so plain `return` is preferred).
- **Naming:** snake_case, descriptive of shape — `synthetic_ohlcv_valid_df`, `synthetic_ohlcv_empty_df` (matches VALIDATION.md naming).
- **Type hints:** mandatory — match the existing `-> Path` annotation discipline.

**Template for a Phase 2 fixture:**

```python
@pytest.fixture(scope="session")
def synthetic_ohlcv_valid_df() -> pd.DataFrame:
    """252 daily bars passing all 4 D-08 invariants (non-empty, recent, monotonic, no null close)."""
    idx = pd.bdate_range(end=pd.Timestamp.today(), periods=252)
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000},
        index=idx,
    )
```

The 10 fixtures listed in VALIDATION.md lines 87–96 all follow this shape.

---

### `tests/test_cli_smoke.py` (MODIFY — extend with 2 health-gate integration tests)

**Role:** CLI integration test (CliRunner).
**Analog:** the file itself.

**Existing test pattern** (`tests/test_cli_smoke.py` lines 27–62) — use `CliRunner().invoke(app, [...])`, parse JSON log lines from stdout, assert event-name + payload:

```python
def test_each_subcommand_exits_zero_with_stub_log() -> None:
    runner = CliRunner()
    for name in D14_SUBCOMMANDS:
        result = runner.invoke(app, [name])
        assert result.exit_code == 0, (...)
        found = False
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("command") == name and "[stub]" in payload.get("message", ""):
                found = True
                break
        assert found, (...)
```

**Phase 2 health-gate test template** — same parse-JSON-from-stdout idiom, different event name and exit-code expectation:

```python
def test_health_gate_below_95_fails_run(monkeypatch, tmp_path) -> None:
    # Setup: monkey-patch the universe + ohlcv loops so combined success rate is < 0.95.
    # Use settings cache_clear() per config.py docstring contract.
    ...
    runner = CliRunner()
    result = runner.invoke(app, ["refresh-ohlcv"])
    assert result.exit_code != 0, "Health gate should fail run when < 95%"
    found = False
    for line in result.stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        payload = json.loads(line)
        if payload.get("event") == "health_check_failed":
            found = True
            break
    assert found
```

**Subcommand list import** — `D14_SUBCOMMANDS` at `tests/test_cli_smoke.py` lines 14–24 must NOT be mutated. Phase 2 adds tests; it does not change the locked surface.

---

### `tests/test_data_universe.py` (CREATE)

**Role:** unit tests for `data/universe.py`.
**Analog:** `tests/test_architecture.py` for the file-walk + assert-list pattern; `tests/test_cli_smoke.py` for fixture-injection style.

**Test-file header style** to match (`tests/test_architecture.py` lines 1–11):

```python
"""Architecture test — hand-rolled AST-based one-way DAG enforcement (D-16).

Scans every src/screener/**/*.py file and asserts each module imports only
from its allowed peer modules per the layered-architecture contract...
"""
```

For `test_data_universe.py`, header should reference DAT-01/DAT-02/DAT-06 and the 02-VALIDATION.md row IDs.

**`from __future__ import annotations`** — `tests/test_architecture.py` line 12 uses this; it's the project convention for test files. Match it.

**Assert-style** — match existing pattern: clear failure message that includes the violation, no bare `assert`. From `tests/test_architecture.py` line 133:

```python
assert not violations, "Layer-import contract violations:\n" + "\n".join(violations)
```

**Test-naming** — the 7 tests are pre-named by VALIDATION.md lines 45–73:

```python
def test_parse_ishares_csv_happy_path(synthetic_ishares_csv_bytes): ...
def test_normalize_ticker_allowlist(): ...
def test_parse_ishares_csv_undersized_fails(synthetic_ishares_csv_undersized_bytes): ...
def test_parse_ishares_csv_unknown_sector_fails(synthetic_ishares_csv_bad_sector_bytes): ...
def test_snapshot_iso_monday_keying(tmp_path, ...): ...
def test_snapshot_idempotent_same_week(tmp_path, ...): ...
def test_snapshot_force_overwrites(tmp_path, ...): ...
def test_requests_cache_hit(): ...   # mocked
```

---

### `tests/test_data_ohlcv.py` (CREATE)

**Role:** unit tests + golden-file tests for `data/ohlcv.py`.
**Analog:** same as `test_data_universe.py`.

**Mocking yfinance** — no Phase 1 precedent. Standard pattern:

```python
import unittest.mock as mock

def test_fetch_empty_raises_after_retries(monkeypatch, synthetic_ohlcv_empty_df):
    with mock.patch("screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_empty_df):
        with pytest.raises(StaleOrEmptyError):
            fetch_ohlcv("FAKE", "2020-01-01", date.today())
```

**Golden-file tests** for NVDA 2024-06-10 (10:1) and AAPL 2020-08-31 (4:1) splits — VALIDATION.md lines 68–69 mark these as `golden-file`. Read a checked-in fixture Parquet (committed under `tests/data/golden/`); assert the ratio. No live network in tests.

**Tests are marked `slow`/`integration`** if they touch network. CI runs `uv run pytest -m "not slow and not integration"` per VALIDATION.md line 22 — golden-file tests use checked-in fixtures and stay in the default suite.

---

### `tests/test_data_stooq.py` (CREATE) and `tests/test_persistence.py` (CREATE)

**Role:** unit tests for adapter and schema rejection.
**Analog:** same shapes as `test_data_universe.py` and `test_data_ohlcv.py`.

**Schema rejection pattern** — pandera raises `pa.errors.SchemaError` (eager) or `pa.errors.SchemaErrors` (lazy). Test idiom:

```python
def test_panel_schema_rejects_null_close():
    bad_df = build_panel_with_null_close()
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(OhlcvPanelSchema, bad_df)


def test_lazy_collects_multiple_errors():
    bad_df = build_panel_with_negative_open_AND_null_close()
    with pytest.raises(pa.errors.SchemaErrors) as exc_info:
        validate_at_read(OhlcvPanelSchema, bad_df)
    # SchemaErrors aggregates; assert > 1 failure case present
    assert len(exc_info.value.failure_cases) >= 2
```

**Atomic-write crash test** — VALIDATION.md line 58 names `test_atomic_write_crash_no_partial`. Pattern: monkey-patch `df.to_parquet` to raise mid-write, then assert that `target` does not exist and a `.tmp` file was unlinked.

```python
def test_atomic_write_crash_no_partial(tmp_path, monkeypatch):
    target = tmp_path / "x.parquet"
    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_oserror)
    with pytest.raises(OSError):
        _write_parquet_atomic(some_df, target)
    assert not target.exists()
    # No half-written tmp left over either:
    assert list(tmp_path.glob(".x.parquet*.tmp")) == []
```

---

### `pyproject.toml` (MODIFY — add `pandas-datareader>=0.10`)

**Role:** project manifest.
**Analog:** the file itself — `[project.dependencies]` at lines 20–37 is the template.

**Existing dependency style** (`pyproject.toml` lines 20–37) — pinned lower bound, capped upper bound, alphabetized loosely by group:

```toml
dependencies = [
  "pandas>=2.2,<3",
  "numpy>=2,<3",
  "scipy>=1.13,<2",
  "pyarrow>=17,<18",
  "pandas-ta-classic>=0.4.47,<0.5",
  "yfinance>=1.3.0,<2",
  ...
]
```

**Phase 2 addition** — add to the existing list, no new section:

```toml
  "pandas-datareader>=0.10,<0.11",
```

Also add to the mypy ignore-imports list at line 100–102 (since pandas-datareader has no maintained stubs):

```toml
[[tool.mypy.overrides]]
module = ["yfinance", "yfinance.*", "vectorbt", ..., "pandas_datareader", "pandas_datareader.*"]
ignore_missing_imports = true
```

**Mypy strict-files extension** — VALIDATION.md line 26 notes that `persistence.py` should join the strict-files list. The current `[tool.mypy] files` list at line 72 is:

```toml
files = ["src/screener/indicators", "src/screener/signals", "src/screener/regime.py", "src/screener/sizing.py"]
```

Phase 2 extends to:

```toml
files = ["src/screener/indicators", "src/screener/signals", "src/screener/regime.py", "src/screener/sizing.py", "src/screener/persistence.py"]
```

`screener.data.*` STAYS in the ignore-overrides at lines 76–78 (third-party-stub-poor).

---

### `.gitignore` (MODIFY — selective carve-out for splits.parquet)

**Role:** repo policy.
**Analog:** the file itself — existing rule at lines 31–36 is the template.

**Existing rule with rationale comment** (`.gitignore` lines 31–36) — the leading-`/` anchor pattern + inline comment is the precedent Phase 2 must respect:

```
# Output directories (populated by later phases; never committed in v1)
# NOTE: anchored to repo root with leading "/" so source-layer dirs like
# `src/screener/data/` are NOT ignored.
/data/
/reports/
/runs.jsonl
```

**Phase 2 amendment** (per CONTEXT.md "Amendment 2026-05-02" lines 282–292) — replaces the single `/data/` line with a selective carve-out. KEEP the explanatory comment block above; it's the existing precedent for documenting non-obvious gitignore rules.

```
# Output directories — selective carve-out for committed audit artifacts.
# Anchored to repo root so source-layer dirs (src/screener/data/) are NOT
# ignored. Universe Parquet snapshots and per-ticker splits ledgers ARE
# committed (small, audit-relevant); per-ticker prices.parquet stays local.
/data/*
!/data/universe/
!/data/universe/.gitkeep
!/data/ohlcv/
/data/ohlcv/**/prices.parquet
!/data/ohlcv/**/splits.parquet
!/data/ohlcv/**/.gitkeep
/reports/
/runs.jsonl
```

The `.gitkeep` files inside `data/universe/` and `data/ohlcv/` placeholder directories must be created so git tracks the carve-out before any data lands. (Phase 1 created no such files; Phase 2 creates them.)

---

### `README.md` (MODIFY — add "Data layer" section)

**Role:** docs.
**Analog:** none — this is a new section. Style guidance from `CLAUDE.md` directives elsewhere in the project.

**Section to add** — three subheads:

1. **Layout** — `data/universe/<iso_monday>.parquet` and `data/ohlcv/<TICKER>/{prices,splits}.parquet`.
2. **Backfill** — first run takes 30–60 min; covers 20y from 2005-01-01.
3. **Stooq fallback** — circuit-breaker semantics, reference D-12.
4. **Survivorship-bias disclosure** — link to `CLAUDE.md` §5.3.

No Phase 1 README content exists yet to mirror; planner inherits the standard project README idiom (markdown headings, code blocks for paths, no emojis per project policy).

---

### `.env.example` (MODIFY/CREATE — D-20 placeholders)

**Role:** env-var skeleton consumed by pydantic-settings.
**Analog:** `Settings` class itself — every field gets one line in `.env.example` with a placeholder and short comment.

**Pattern** — mirror the field declaration order in `config.py`:

```
# .env.example — copy to .env and fill in values.
# External-service credentials (used in later phases)
FINNHUB_API_KEY=
FRED_API_KEY=
EDGAR_IDENTITY=

# Universe selection
UNIVERSE=russell1000

# Indicator + sizing parameters
RS_LOOKBACK_DAYS=252
RISK_PCT_PER_TRADE=0.0075
ACCOUNT_EQUITY=100000.0

# Phase 2 — data-layer paths and policy (D-20)
OHLCV_CACHE_DIR=data/ohlcv
UNIVERSE_CACHE_DIR=data/universe
OHLCV_BACKFILL_START=2005-01-01
UNIVERSE_HEALTH_THRESHOLD=0.95
STOOQ_BREAKER_PROBE_N=50
STOOQ_BREAKER_THRESHOLD=0.80
OHLCV_FETCH_SLEEP_MIN_S=0.5
OHLCV_FETCH_SLEEP_MAX_S=1.5
```

Defaults match `config.py` so a developer who copies `.env.example` to `.env` gets identical behavior to the unset state.

---

## Shared Patterns

### Pattern: Layered DAG Import Discipline

**Source:** `tests/test_architecture.py` lines 30–44 (the `ALLOWED` dict)
**Apply to:** every Phase 2 source file in `src/screener/`

The architecture test enforces a one-way import graph. For `data/`:

```python
ALLOWED["data"] = {"persistence", "config", "obs"}
```

In code: `data/universe.py`, `data/ohlcv.py`, `data/stooq.py` may import:
- stdlib (any)
- third-party (any — `requests`, `yfinance`, `pandas_datareader`, `pandas`, `pandera`, `tenacity`, `requests_cache`, `structlog`)
- `screener.persistence` (write helpers, schemas)
- `screener.config` (`get_settings`, `Settings`)

They MUST NOT import `screener.indicators`, `screener.signals`, `screener.regime`, `screener.sizing`, `screener.publishers`, `screener.catalysts`, `screener.ml`. Test failure surfaces with line `f"{path}: layer 'data' imports forbidden peer(s) ...".

For `persistence.py`:

```python
ALLOWED["persistence"] = {"config", "obs"}
```

`persistence.py` may NOT import any `data/*` module — it's strictly downstream of network I/O. Schema definitions live there but the network layer (`data/`) calls IN to `persistence` for writers, not the other way.

---

### Pattern: structlog Per-Module Logger

**Source:** `src/screener/cli.py` line 20
**Apply to:** every Phase 2 module that emits structured events (`data/universe.py`, `data/ohlcv.py`, `data/stooq.py`, `persistence.py`)

```python
import structlog

log = structlog.get_logger(__name__)
```

Module-level logger; never call `obs.configure()` inside library modules (that's a CLI-entry-only call per `01-02-SUMMARY.md` "Stub idempotence" decision).

---

### Pattern: Cached Settings Access

**Source:** `src/screener/config.py` lines 40–48 (the `get_settings()` factory) + the docstring contract at lines 7–11.
**Apply to:** every Phase 2 function that consumes a Settings field.

```python
from screener.config import get_settings

def some_function() -> None:
    settings = get_settings()
    cache_dir = settings.OHLCV_CACHE_DIR
    ...
```

NEVER do `from screener.config import settings` (that no longer exists per Phase 1 WR-01 fix) — always go through the cached factory. Tests must call `get_settings.cache_clear()` after monkey-patching env vars.

---

### Pattern: Atomic Parquet Write (NEW IDIOM, Phase 2 introduces)

**Source:** RESEARCH.md §"Pattern 1" lines 263–303 (no Phase 1 analog)
**Apply to:** every `persistence.write_*_atomic()` function and any future disk artifact

Tempfile in same directory as target → `os.replace()` for POSIX-atomic same-FS rename. See full excerpt above under `persistence.py`. Document in the docstring of `_write_parquet_atomic` so it doesn't get re-litigated in later phases (per CONTEXT.md "specifics" line 169).

---

### Pattern: pandera DataFrameModel + Two-Mode Validation (NEW IDIOM)

**Source:** RESEARCH.md §"Pattern 5" lines 467–569 (no Phase 1 analog)
**Apply to:** all three Phase 2 schemas (`OhlcvPanelSchema`, `UniverseSchema`, `SplitsSchema`)

Class-based `pa.DataFrameModel` with `Series[T]` and `Index[T]` typing. `Config` enables `strict=True` + `coerce=False` + `multiindex_strict=True` (where applicable). Validation split: eager at write (`lazy=False`), lazy at read (`lazy=True`).

---

### Pattern: tenacity Retry with structlog Hook (NEW IDIOM)

**Source:** RESEARCH.md §"Pattern 2" lines 334–342 (no Phase 1 analog)
**Apply to:** every external HTTP/API call in `data/`

```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(log, "warning"),
    reraise=True,
)
```

Critical: `retry_if_exception_type` MUST list the failure types (not `Exception`); avoid retrying on `KeyError`/`ValueError` from genuinely-bad input. `reraise=True` ensures the original exception surfaces after retries exhaust (instead of tenacity's `RetryError` wrapper).

---

### Pattern: Test File Header + Path Fixtures

**Source:** `tests/test_architecture.py` lines 1–17 + `tests/conftest.py` lines 12–21
**Apply to:** every new test file in Phase 2

- Test-file docstring states the requirement IDs covered (mirrors `tests/test_architecture.py` "D-16" reference).
- `from __future__ import annotations` (line 12).
- Type hints on every fixture and test parameter (existing convention).
- Use `repo_root` / `src_screener` fixtures from `conftest.py` instead of hard-coded relative paths (per `01-03-SUMMARY.md` "Pattern: pytest fixtures for repo paths").

---

### Pattern: No `print()` Anywhere

**Source:** `CLAUDE.md` §10.4 ("no print → use `structlog`")
**Apply to:** all Phase 2 source modules

Even debug output goes through `log.debug(...)`. Phase 1 has zero `print()` calls; Phase 2 maintains the contract.

---

## No Analog Found (Phase 2 Introduces)

The following idioms have no Phase 1 sibling and are introduced for the first time in Phase 2. The planner uses RESEARCH.md as the canonical template instead of an in-repo file:

| Idiom | First-time location | Source-of-truth |
|-------|---------------------|-----------------|
| Atomic Parquet write (tempfile + `os.replace`) | `src/screener/persistence.py` | RESEARCH.md §"Pattern 1" |
| pandera `DataFrameModel` schemas | `src/screener/persistence.py` | RESEARCH.md §"Pattern 5" |
| tenacity retry on `StaleOrEmptyError` | `src/screener/data/ohlcv.py` | RESEARCH.md §"Pattern 2" |
| Sentinel-bar refetch for incremental append | `src/screener/data/ohlcv.py` | RESEARCH.md §"Pattern 3" |
| Whole-run circuit-breaker (yfinance → Stooq) | `src/screener/data/ohlcv.py` | RESEARCH.md §"Pattern 4" |
| iShares CSV parsing (UA + skiprows + BOM) | `src/screener/data/universe.py` | RESEARCH.md §"Pattern 6" |
| `requests_cache.CachedSession` factory | `src/screener/data/universe.py` (or `data/__init__.py`) | RESEARCH.md §"Pattern 7" |
| Custom `StaleOrEmptyError` exception class | `src/screener/data/ohlcv.py` | RESEARCH.md §"Pattern 2" line 330 |
| `from __future__ import annotations` in src modules | (new for Phase 2 source files; tests already use it) | tests/test_architecture.py line 12 |
| Mocking yfinance via `unittest.mock.patch` | `tests/test_data_ohlcv.py` | (stdlib idiom; no analog) |
| pandera `SchemaError` / `SchemaErrors` assertion | `tests/test_persistence.py` | pandera docs (cited in RESEARCH.md) |
| Crash-mid-write filesystem assertion | `tests/test_persistence.py::test_atomic_write_crash_no_partial` | (no analog; pattern shown above) |

---

## Metadata

**Analog search scope:** `src/screener/**/*.py`, `tests/**/*.py`, `pyproject.toml`, `Makefile`, `.gitignore`, `.planning/phases/01-repo-skeleton-ci-hygiene/01-*-SUMMARY.md`
**Files scanned:** 17 (Phase 1 source + tests + config + 5 Phase 1 plan summaries)
**Pattern extraction date:** 2026-05-02

**Phase-2-specific notes:**

1. Phase 1 left every file Phase 2 needs as either a docstring-only stub OR a fully-formed file with extension hooks (Settings additive, conftest additive, cli.py body-replacement). The architectural seams are exact; no refactors required.
2. The `data/` layer has zero Phase 1 logic — `data/universe.py`, `data/ohlcv.py`, `data/stooq.py` are greenfield. The closest Phase 1 sibling is `obs.py` (single-purpose helper module) for module shape.
3. Three idioms are introduced for the first time in Phase 2 (atomic write, pandera schemas, tenacity wrapper). For these, RESEARCH.md §"Pattern 1/2/5" is the canonical template the planner copies into PLAN action sections.
4. The architecture test (`tests/test_architecture.py`) is the most important Phase-1 sibling — it enforces the import graph that Phase 2 must respect. Adding any cross-layer import in Phase 2 will fail this test loud.
5. `pyproject.toml` mypy-strict scope extends to `persistence.py` (per VALIDATION.md note); `data/*` STAYS in ignore-overrides since the third-party stubs are weak.

## PATTERN MAPPING COMPLETE

**Phase:** 2 - Data Foundation
**Files classified:** 18 (8 CREATE + 10 MODIFY)
**Analogs found:** 18 / 18

### Coverage
- Files with exact analog (file already exists): 10
- Files with role-match analog (sibling module establishes shape): 7
- Files with no analog (introduced in Phase 2 — README and .env.example): 1 + 1 (with established in-repo conventions to follow)
- Idioms introduced for the first time in Phase 2 (sourced from RESEARCH.md): 3 (atomic write, pandera DataFrameModel, tenacity wrapper)

### Key Patterns Identified
- All Phase 2 source files follow `obs.py` module-shape: short role-stating docstring, stdlib-first imports, single-purpose helpers, structlog per-module logger.
- All Settings extensions are additive to `config.py` and accessed via the cached `get_settings()` factory; tests call `cache_clear()` to override.
- All test files inherit from `tests/test_architecture.py` and `tests/test_cli_smoke.py` conventions: typed fixtures, `from __future__ import annotations`, descriptive assert messages, JSON-log parsing for CLI smoke tests.
- The architecture test enforces the import graph at every commit — `data/` may import only `persistence`, `config`, `obs` from the screener package; `persistence.py` may import only `config`, `obs`. Phase 2 respects this exactly.
- Three new idioms (atomic write, pandera DataFrameModel, tenacity wrapper) are sourced verbatim from RESEARCH.md and become the template for Phase 3+ data-layer extensions.

### File Created
`/Users/belwinjulian/Desktop/SwingTrading/.planning/phases/02-data-foundation/02-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files; every action that touches a Phase 1 file has a concrete excerpt to copy from, and every brand-new idiom (atomic write, pandera schemas, tenacity) is pinned to a line range in RESEARCH.md.
