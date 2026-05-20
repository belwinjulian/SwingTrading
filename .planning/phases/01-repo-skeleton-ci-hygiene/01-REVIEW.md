---
phase: 01-repo-skeleton-ci-hygiene
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 28
files_reviewed_list:
  - pyproject.toml
  - uv.lock
  - .gitignore
  - LICENSE
  - README.md
  - .env.example
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
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_architecture.py
  - tests/test_cli_smoke.py
  - Makefile
  - docs/strategy_v1_preregistration.md
  - docs/branch_protection.md
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
findings:
  critical: 0
  warning: 4
  info: 8
  total: 12
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-05-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 28
**Status:** issues_found

## Summary

Phase 1 ships a clean, well-thought-out scaffold: layered DAG seams, an AST-based architecture test, three-job parallel CI, pre-commit with strict-scoped mypy, a typer composition root, structured logging, and a frozen `pandas-ta-classic` dependency (correctly avoiding the deprecated `pandas-ta`). No BLOCKER defects were found. No secrets leak; no command-injection paths in the Makefile; no architecture violations; the forbidden-dep list (TA-Lib C, Alpha Vantage primary, IEX Cloud, vectorbt PRO, pandas-ta) is honored.

The defects below are all WARNING/INFO class. The two most material warnings are: (a) **eager `Settings()` instantiation at `config.py` import time**, which makes any future malformed `.env` an import-time failure rather than a callable-time failure — fragile for tests and downstream tools; (b) **third-party GitHub Actions are pinned to floating major tags (`@v4`, `@v6`) rather than commit SHAs**, leaving CI exposed to upstream supply-chain compromise of `actions/checkout` and `astral-sh/setup-uv`. The pre-commit `mypy` `additional_dependencies` list also drifts from `pyproject.toml` (missing `pyarrow`, `scipy`, `requests-cache`, `tenacity`), which is dormant today but will silently diverge once math modules import those libs.

## Warnings

### WR-01: `Settings()` instantiated at module import time — fragile failure mode

**File:** `src/screener/config.py:33`
**Issue:** `settings = Settings()` runs at module import. Any code path that imports `screener.config` (directly or transitively via future `screener.persistence`, `screener.indicators`, etc.) eagerly evaluates pydantic-settings, reads `.env`, and validates types. If `.env` later contains a malformed value (e.g., `RISK_PCT_PER_TRADE=abc` or `ACCOUNT_EQUITY=` with a stray value), every importer fails at *collection time* with a `ValidationError`, including pytest collection — masking the real test failure under an import error. It also couples test fixtures to the working directory (pydantic-settings resolves `env_file=".env"` relative to CWD), which can cause flaky behavior when tests are run from a subdirectory.

Today no module imports `config` (verified via grep across `src/` and `tests/`), so this is dormant — but it's wired in such a way that the first downstream consumer in Phase 2 inherits the fragility.

**Fix:** Make settings lazy via a cached accessor:
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```
Callers do `from screener.config import get_settings; cfg = get_settings()`. This (1) defers `.env` reads until first use, (2) makes it trivial to override in tests via `get_settings.cache_clear()` + monkey-patched env, and (3) keeps the import graph cheap.

---

### WR-02: GitHub Actions third-party actions pinned to floating tags, not SHAs

**File:** `.github/workflows/ci.yml:22, 25, 50, 71` (`actions/checkout@v4`, `astral-sh/setup-uv@v6`)
**Issue:** Both third-party actions used in CI are pinned to floating major-version tags. Tags are mutable; if the upstream repo (or a compromised maintainer account) re-points `v4` / `v6` to a malicious commit, every subsequent CI run executes the new code with whatever permissions the workflow grants — including, in Phase 2+, access to `secrets.FINNHUB_API_KEY`, `secrets.FRED_API_KEY`, etc. The Tj-actions/changed-files compromise (March 2025) is the canonical example: tags were silently retargeted across thousands of repos. GitHub's own security guidance says to pin third-party actions to a full commit SHA.

For a portfolio piece that explicitly markets data-engineering competence, leaving this on floating tags is a visible miss to a security-aware reviewer.

**Fix:** Pin every third-party action to a 40-char commit SHA, with the human tag in a comment:
```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
- uses: astral-sh/setup-uv@e92bafb6253dcd438e0484186d7669ea7a8ca1cc  # v6.0.1
```
Use Dependabot's `package-ecosystem: github-actions` to keep the SHAs current. GitHub's own first-party `actions/*` are lower risk than community actions but the same hygiene applies.

---

### WR-03: Pre-commit mypy `additional_dependencies` drifts from `pyproject.toml` runtime deps

**File:** `.pre-commit-config.yaml:24-32`
**Issue:** The pre-commit `mypy` hook lists `additional_dependencies` to give mypy real type info. The list includes pandas/numpy/pydantic-settings/pandera/structlog/typer/pandas-stubs/types-requests, but **omits** four runtime dependencies declared in `pyproject.toml` lines 23-36: `scipy`, `pyarrow`, `requests-cache`, and `tenacity`. Phase 1's strict-scope modules (`indicators/`, `signals/`, `regime.py`, `sizing.py`) do not yet import any of those, so the hook is currently green. But:

1. `scipy.signal.argrelextrema` is the canonical pivot detector for VCP (CLAUDE.md §3.4) — Phase 6 indicators *will* import scipy.
2. The Phase 5 backtest no-look-ahead test target may end up exercised through a math-scope helper.

When that import lands, pre-commit will fail with `Cannot find implementation or library stub for module named "scipy"` while CI's mypy job (which uses `uv sync --frozen --extra dev` and gets the real package) will continue passing — exactly the kind of "works on CI, fails on commit" trap that erodes trust in the hook.

**Fix:** Mirror every runtime dep mypy might encounter in the strict scope into `additional_dependencies`. At minimum add `scipy>=1.13,<2`. Better: factor the dep list into a constant in `pyproject.toml` (e.g., a `[tool.mypy-additional]` table the hook reads) or generate the pre-commit list from `uv export --extras dev` so the two cannot drift. Cheapest fix that preserves Phase 1 scope:
```yaml
additional_dependencies:
  - pandas>=2.2,<3
  - numpy>=2,<3
  - scipy>=1.13,<2          # add — needed by indicators in Phase 6
  - pyarrow>=17,<18         # add — persistence boundary type stubs
  - pydantic-settings>=2.14,<3
  - pandera>=0.31.1,<0.32
  - structlog>=25.5,<26
  - typer>=0.25,<0.26
  - tenacity>=9.1,<10       # add — retry decorators surface in math callers
  - pandas-stubs
  - types-requests
```

---

### WR-04: Pre-commit mypy `files` regex is unanchored at the end — over-matches

**File:** `.pre-commit-config.yaml:36`
**Issue:** `files: ^src/screener/(indicators|signals|regime\.py|sizing\.py)` lacks a closing anchor. Verified behavior:

| Path | Match? | Should match? |
|---|---|---|
| `src/screener/regime.py` | yes | yes |
| `src/screener/regime.pyi` | yes | no |
| `src/screener/regime.pyc` | yes | no |
| `src/screener/regime.py.bak` | yes | no |
| `src/screener/sizing.py.bak` | yes | no |
| `src/screener/indicatorsfoo/x.py` | yes | no |
| `src/screener/sizing/foo.py` | no | n/a (sizing is a file today) |

Today this is harmless (none of the over-matched paths exist), but if Phase 4 stub-files a `regime.pyi` for type narrowing, pre-commit will hand it to mypy and the strict scope expands silently.

**Fix:** Anchor the alternation properly. Use one of:
```yaml
files: ^src/screener/(indicators/|signals/|regime\.py$|sizing\.py$)
```
or split the file/dir cases:
```yaml
files: ^src/screener/(indicators|signals)/.*\.py$|^src/screener/(regime|sizing)\.py$
```
The second form is the most explicit and matches the `tool.mypy.files` list in `pyproject.toml` exactly.

---

## Info

### IN-01: `obs.configure()` re-runs `logging.basicConfig` per CLI invocation; level changes are silently ignored

**File:** `src/screener/obs.py:14-39`, `src/screener/cli.py:25` (`_stub` calls `configure_logging()` every time)
**Issue:** `logging.basicConfig` is a no-op once the root logger has handlers (Python stdlib behavior, unless `force=True` is passed). `_stub` calls `configure()` on every subcommand. The structlog reconfigure path is fine (idempotent by design), but if the level argument ever changes between calls, `basicConfig` will silently keep the original level. The docstring claims "Idempotent — safe to call multiple times", which is technically true today (level is hardcoded "INFO") but masks a footgun.

**Fix:** Either pass `force=True` to `logging.basicConfig` so re-configuration actually applies, OR move `configure_logging()` to a single `app.callback()` on the typer `app` so it runs exactly once per CLI invocation rather than once per subcommand:
```python
@app.callback()
def _root(verbose: bool = False) -> None:
    configure_logging("DEBUG" if verbose else "INFO")
```
Then drop the `configure_logging()` call from `_stub`.

---

### IN-02: `obs.configure()` snapshots `sys.stdout` reference inside `basicConfig(stream=...)` — breaks late stdout swaps

**File:** `src/screener/obs.py:22`
**Issue:** `logging.basicConfig(stream=sys.stdout, ...)` captures the *current* `sys.stdout` object. typer's `CliRunner` patches `sys.stdout` *before* invoking the command, so this works in tests today. But pytest plugins (capsys, pytest-xdist) and any future code that reassigns `sys.stdout` *after* `configure()` runs will route logs to the original stream. Combined with structlog's `PrintLoggerFactory` (which re-resolves `sys.stdout` lazily), you'd see two sinks behaving differently.

**Fix:** Either drop the redundant stdlib `logging.basicConfig` (structlog's `PrintLoggerFactory` already writes to stdout — verify with the CLI smoke test which passes today), or pass nothing (defaults to `sys.stderr`, then structlog and stdlib agree by source).

---

### IN-03: `Settings` field names are SCREAMING_SNAKE_CASE — non-Pythonic attribute access

**File:** `src/screener/config.py:20-30`
**Issue:** Pydantic-settings field names become Python attributes — `settings.FINNHUB_API_KEY` rather than `settings.finnhub_api_key`. PEP 8 reserves SCREAMING_SNAKE for module-level constants. Pydantic-settings supports lowercase field names with case-insensitive env mapping (default), so the env var `FINNHUB_API_KEY` still binds correctly.

**Fix:**
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    finnhub_api_key: str = ""
    fred_api_key: str = ""
    edgar_identity: str = ""
    universe: str = "russell1000"
    rs_lookback_days: int = 252
    risk_pct_per_trade: float = 0.0075
    account_equity: float = 100_000.0
```
Cheap to do in Phase 1 (zero callers); painful to refactor in Phase 5+ once dozens of `cfg.RISK_PCT_PER_TRADE` references exist.

---

### IN-04: CI workflow doesn't expose `workflow_dispatch` — manual re-runs require a no-op commit

**File:** `.github/workflows/ci.yml:3-6`
**Issue:** Triggers are `pull_request` and `push: branches: [main]` only. If a flaky test surfaces or CI was skipped (e.g., the GitHub Actions cron-throttle behavior CLAUDE.md warns about for the upcoming nightly refresh workflow), Belwin cannot re-trigger CI without an empty commit or a force-push.

**Fix:** Add a `workflow_dispatch:` trigger so the Actions tab shows a "Run workflow" button:
```yaml
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
```
Free, no security cost, useful when the nightly refresh workflow ships in M2.

---

### IN-05: Loop-variable shadowing in CLI smoke test

**File:** `tests/test_cli_smoke.py:48-50`
**Issue:** `for line in result.stdout.splitlines(): line = line.strip()` shadows the loop variable. Ruff `B007` would flag this if `B007` were enabled (the project's ruff config selects `B`, so it likely will be flagged on next run — verify with `uv run ruff check tests/`).

**Fix:**
```python
for raw in result.stdout.splitlines():
    line = raw.strip()
    if not line.startswith("{"):
        continue
    ...
```

---

### IN-06: `_iter_source_files` does not exclude `.venv`, `build`, or `dist` directories under `src_root`

**File:** `tests/test_architecture.py:96-97`
**Issue:** The helper excludes `__pycache__` but not `.venv`, `build`, `dist`, `.eggs`. None of these *should* live under `src/screener/`, but a stray `pip install -e .` failure or `hatchling` build artifact could deposit `.py` files there. The architecture test would then scan vendored dependency code and either (a) emit a "layer 'X' has no entry in ALLOWED" error and fail on benign noise, or (b) misclassify and pass when it shouldn't.

**Fix:** Tighten the exclusion list:
```python
EXCLUDED = {"__pycache__", ".venv", "venv", "build", "dist", ".eggs", ".mypy_cache", ".pytest_cache"}
return sorted(p for p in src_root.rglob("*.py")
              if not (set(p.parts) & EXCLUDED) and p.is_file())
```

---

### IN-07: Pre-commit mypy hook missing the `language_version` pin

**File:** `.pre-commit-config.yaml:18-36`
**Issue:** Pre-commit defaults the mypy hook's interpreter to whatever `python3` resolves to on the developer machine. If a contributor has 3.12 system Python and the project requires 3.11 (`pyproject.toml:16`), pre-commit may silently install mypy + dependencies into a 3.12 venv and produce different results than CI (which uses `uv python install` -> 3.11). Adding `language_version: python3.11` makes the local hook environment match CI exactly.

**Fix:**
```yaml
- id: mypy
  language_version: python3.11
  ...
```
Same applies to the ruff hook for full hygiene, though ruff is a single binary so the impact is smaller.

---

### IN-08: `pyproject.toml` `[tool.ruff.lint]` selects `PD` (pandas-vet) but Phase 1 has no pandas usage to check

**File:** `pyproject.toml:64`
**Issue:** Not a defect today; flagged because `PD` includes some opinionated rules (e.g., `PD901` "df is a bad variable name") that are noisy in financial-DataFrame code where `df` is genuinely the canonical name. Worth deciding before Phase 2 lands real DataFrame code, otherwise a wave of `# noqa: PD901` will appear or the rule will get retroactively disabled with a follow-up commit. Suggest pre-emptively listing rule-level ignores Phase 2 will need:
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM", "RUF", "PD", "NPY"]
ignore = ["PD901"]  # `df` is the canonical name for the indicator panel
```

---

_Reviewed: 2026-05-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
