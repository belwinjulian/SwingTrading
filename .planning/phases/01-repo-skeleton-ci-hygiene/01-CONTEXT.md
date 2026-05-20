# Phase 1: Repo Skeleton & CI Hygiene - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 ships an empty-but-runnable engineering scaffold: a `uv`-managed `pyproject.toml` pinning the v1 stack, a typed Python `src/screener/` source tree with no real implementations, a Makefile that orchestrates the four-target DAG (`make data && make rank && make report && make backtest`) by routing through no-op typer subcommands, GitHub Actions CI gates (ruff + mypy `--strict` on the math modules + pytest) wired to PR + push-to-main, branch protection on `main` with required status checks, and the `docs/strategy_v1_preregistration.md` placeholder containing the literal token `<weights frozen at Phase 4 completion>`.

The phase delivers structure and gates only — no data fetching, no indicators, no signals, no patterns, no backtest harness. Every later phase fills in module bodies; Phase 1 fixes the architectural seams and the QA toolchain that everything plugs into.

Requirements covered: **FND-01** (uv + pinned v1 stack), **FND-02** (Makefile DAG runs end-to-end), **FND-03** (CI runs ruff/mypy/pytest on every PR).

</domain>

<decisions>
## Implementation Decisions

### pyproject.toml shape, versions, and entry point

- **D-01: Hybrid dependency layout.** `[project.dependencies]` carries the nightly-pipeline runtime stack: `pandas`, `pandas-ta-classic` (NOT `pandas-ta`), `yfinance`, `vectorbt`, `edgartools`, `finnhub-python`, `fredapi`, `pydantic-settings`, `pandera`, `structlog`, `typer`, `requests-cache`, `tenacity`, `pyarrow`, `numpy`, `scipy` (needed by `argrelextrema` in Phase 6 — but adding it here keeps the import-linter contract simple). `[project.optional-dependencies].dev` carries QA tools (`ruff`, `mypy`, `pytest`, `hypothesis`, `pre-commit`, plus type stubs as needed). `[project.optional-dependencies].ml` ships as a deliberately empty extra reserved for M2 (`lightgbm`, `mlflow`, `shap`) — its presence locks the M2 install seam without adding deps now.
- **D-02: Compat-style version constraints + `uv.lock` committed.** Declarations in `pyproject.toml` use `>=X,<X+1` ranges per `research/STACK.md` (e.g., `pandas>=2.2,<3`, `yfinance>=1.3.0,<2`, `pandas-ta-classic>=0.4.47,<0.5`, `numpy>=2,<3`, `vectorbt>=1.0,<2`, `pydantic-settings>=2.14,<3`, `pandera>=0.31.1,<0.32`, `structlog>=25.5,<26`, `typer>=0.25,<0.26`, `requests-cache>=1.3,<2`, `tenacity>=9.1,<10`, `edgartools>=5.30,<6`, `finnhub-python>=2.4.28,<3`, `fredapi>=0.5.2,<0.6`, `pyarrow>=17,<18`). `uv.lock` is committed for byte-reproducible installs across CI and local.
- **D-03: `requires-python = "==3.11.*"`.** Locked to 3.11 for v1. STACK.md flags Numba-dependent libs (vectorbt, pandas-ta-classic) as occasionally lagging on 3.12+. CI runs 3.11 only; cron uses 3.11 only. Bump deliberately later, not opportunistically.
- **D-04: Build backend = `hatchling`, src/ layout, `[project.scripts] screener = "screener.cli:app"`.** Modern uv-native default; `tool.hatch.build.targets.wheel.packages = ["src/screener"]`; `screener` console-script invocation works after `uv sync` so `uv run screener report` and `screener report` (in active venv) both work.

### CI shape, triggers, and dev-loop guardrails

- **D-05: Single `.github/workflows/ci.yml` with three parallel jobs.** Jobs: `lint` (ruff format --check + ruff check), `typecheck` (mypy `--strict` on the math modules — see D-10), `test` (pytest `-m 'not slow'`). All three are required status checks. Parallelism shortens wall-clock vs sequential.
- **D-06: Triggers = `pull_request` + `push` to `main`.** PR runs catch issues pre-merge (FND-03); push-to-main runs catch direct/hot-fix landings post-merge. Public repo → unlimited free Actions minutes; the doubled trigger cost is irrelevant.
- **D-07: Pre-commit = ruff + mypy --quick (no pytest).** `.pre-commit-config.yaml` runs `ruff format`, `ruff check`, and `mypy --no-incremental` over staged files within the strict-mypy scope (D-10). Pytest is CI-only — keeps the local commit loop fast. Install via `uvx pre-commit install` (documented in README setup steps).
- **D-08: Branch protection on `main` ON in Phase 1.** Required status checks = `lint`, `typecheck`, `test`. Require PR before merge. No force-push. Linear history not required (allows squash-merge or merge-commit). Documented in README so a future contributor (or Belwin a year later) sees why direct-to-main is blocked. One-time admin click; locks the gate forever.
- **D-09: `astral-sh/setup-uv@v6` with `enable-cache: true` keyed on `uv.lock`.** Vectorbt + pandas-ta-classic cold install is slow (Numba warmup); cache cuts CI from ~3 min to ~30 s. `setup-uv` handles uv install + cache plumbing; CI step is `uv sync --frozen --extra dev`.
- **D-10: mypy `--strict` scope = `signals/`, `indicators/`, `regime`, `sizing`, `composite`.** Wider than the literal FND-03 wording (which says signals + indicators), reflecting the reality that `regime.py`, `sizing.py`, and `signals/composite.py` are pure-function math modules with the same correctness profile. `[[tool.mypy.overrides]]` blocks loosen `data/`, `publishers/`, `cli.py`, and `backtest/` (third-party stubs are weak there). One mypy invocation per CI run, scoped via `mypy src/screener/{indicators,signals,regime.py,sizing.py}` (composite lives inside signals/).
- **D-11: `tests/` at repo root + markers (`slow`, `integration`) + pytest-cov gate `≥80%` on `signals/+indicators/`.** `tests/` mirrors CLAUDE.md §10.1. `[tool.pytest.ini_options]` registers the markers; CI runs `pytest -m 'not slow'`. `pytest-cov` is configured with `--cov=src/screener/signals --cov=src/screener/indicators --cov-fail-under=80`. Caveat: gate is trivially satisfied while modules are empty (Phase 1) and becomes binding from Phase 3 once real signals/indicators code lands. Documented in CONTEXT.md so the planner doesn't treat 100% Phase 1 coverage as meaningful.
- **D-12: Ruff curated rule set, line-length 100.** `select = ["E", "F", "I", "B", "UP", "N", "SIM", "RUF", "PD", "NPY"]` — pyflakes + pycodestyle errors + imports + bugbear + pyupgrade + naming + simplify + ruff-specific + **pandas-vet (PD)** + **numpy-specific (NPY)**. PD + NPY catch panda/numpy idioms that bite quant code (chained indexing, deprecated dtypes). `line-length = 100`. Configured in `pyproject.toml` `[tool.ruff]` section (no separate `ruff.toml`).

### Source-tree scaffolding depth

- **D-13: Module-docstring scaffolding, no signatures.** Every layer directory under `src/screener/` ships an `__init__.py` whose only content is a one-line module docstring stating the layer's role and import policy — e.g., `"""data/ — the only I/O layer; everything downstream consumes DataFrames."""`. No function signatures, no `NotImplementedError` stubs. Locks the architectural boundaries on day one without committing to public-API shapes that Phase 2+ may want to revise. Layer set: `data/`, `indicators/`, `signals/`, `regime.py` (file, not dir), `sizing.py`, `publishers/`, `backtest/`, `catalysts/`, `ml/` (directory exists with `__init__.py` reserved for M2; empty otherwise).
- **D-14: `cli.py` ships the full v1 typer surface, all no-op.** Subcommands: `refresh-universe`, `refresh-ohlcv`, `refresh-macro`, `refresh-fundamentals`, `score`, `report`, `journal`, `backtest`, `backtest-audit`. Each logs `[stub] <command> not yet implemented` via `structlog` and exits 0. The Makefile targets (`make data`, `make rank`, `make report`, `make backtest`) shell out to the relevant typer subcommand(s) — e.g., `make data` runs `screener refresh-universe && screener refresh-ohlcv && screener refresh-macro && screener refresh-fundamentals`. This implicitly resolves the Makefile-placeholder gray area: targets are wired through the real CLI, the CLI stubs log structured "not yet implemented" lines, the artifact pipeline is structurally present from day one even though it produces no artifacts.
- **D-15: `config.py` ships a real `Settings` class.** `pydantic-settings.BaseSettings` declaring the env vars later phases will consume: `FINNHUB_API_KEY`, `FRED_API_KEY`, `EDGAR_IDENTITY` (name + email per SEC policy), `UNIVERSE` (default `"russell1000"`), `RS_LOOKBACK_DAYS` (default `252`), `RISK_PCT_PER_TRADE` (default `0.0075`), `ACCOUNT_EQUITY` (default `100_000`). Loads from `.env` via `model_config = SettingsConfigDict(env_file=".env")`. Phase 2+ adds fields as needed (validates incrementally).
- **D-16: Hand-rolled `tests/test_architecture.py` enforces the one-way DAG.** Pytest test using `ast.parse` + `ast.walk` to scan every `src/screener/**/*.py` import statement and assert the layered-architecture rules (CLAUDE.md §10.1):
  - `data/` imports nothing from `src/screener/` except `persistence` and `config`.
  - `indicators/` imports only `persistence` + `config` (plus stdlib + numpy/pandas/scipy/pandas-ta-classic externally).
  - `signals/` imports only `indicators/` + `regime` + `persistence` + `config`.
  - `regime` imports `data/` + `indicators/` (regime is one-row-per-date, may consume macro data).
  - `sizing` imports `signals/` + `regime` + `config`.
  - `publishers/` imports `signals/` + `sizing/` + `regime` + `persistence` + `config`.
  - `backtest/` imports `persistence` + stdlib only — never `publishers/`, never makes network calls.
  - `catalysts/` and `ml/` are stubs in Phase 1; the contract reserves their downstream-import slots.
  Test runs as part of the standard `pytest` invocation in CI (no separate job). Zero external dependency. The `import-linter` package was considered but rejected — same guarantees with no third-party trust point and one less dep to maintain.

### Claude's Discretion

The user did not call these out explicitly; the planner can finalize standard answers consistent with the locked decisions above:

- **Makefile target dependencies and `.PHONY` declarations.** Standard pattern: every target `.PHONY`, no real file dependencies until later phases. `help` target prints a target list. A `setup` target runs `uv sync --extra dev && pre-commit install`.
- **`.gitignore` contents.** Standard Python + uv + macOS layout: `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.egg-info/`, `.env`, `.DS_Store`, plus `data/` + `reports/` + `runs.jsonl` (output dirs that downstream phases will populate; never commit data artifacts in v1 — Phase 8 may revise the policy for committed nightly reports).
- **LICENSE.** MIT is the default for portfolio repos; Apache-2.0 is the alternative. Planner picks one and commits — not a v1-blocking decision.
- **README.md skeleton.** Minimal: project one-liner, status badge placeholders, setup steps (`uv sync --extra dev`, `cp .env.example .env`, `pre-commit install`), `make help` reference, link to `CLAUDE.md` and `.planning/`. Hero/screenshots/honest-backtest sections defer to later phases (the README evolves per CLAUDE.md §12.1).
- **`.env.example`.** Mirror the Settings class fields from D-15 with placeholder values and inline comments pointing at how each is used. CONTRIBUTING.md / CODEOWNERS / issue templates are not v1-blocking — defer.
- **Pre-registration doc scaffold.** `docs/strategy_v1_preregistration.md` ships with: title, "**Status:** Placeholder — weights frozen at Phase 4 completion" line, the literal token `<weights frozen at Phase 4 completion>`, an empty weights table with TBD rows (RS / Trend / Pattern / Volume / Earnings / Catalyst), a `**Frozen at git hash:** <to be filled at Phase 4 completion>` line, and a methodology-summary stub. A grep-style CI check that the literal token still exists is **deferred to Phase 4** — the token's job in Phase 1 is to mark the file as a placeholder, not to be a CI gate yet.
- **`structlog` baseline configuration.** `cli.py` calls a `screener.logging.configure()` helper at startup that wires structlog to JSON output on stdout, with timestamping and log-level bound. The helper lives in a small `src/screener/logging.py` (file, not the `logging` stdlib name — call it `obs.py` or `logconfig.py` to avoid shadowing). Planner picks the exact filename.
- **`Makefile` `help` target message.** Standard self-documenting Makefile pattern (parse `## help text` comments after target names).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project intent and scope
- `.planning/PROJECT.md` — what the screener is, who it's for, the $0 / EOD-only / SMA-not-EMA / next-bar-open / 45-day-fundamentals-lag constraints
- `.planning/REQUIREMENTS.md` — FND-01, FND-02, FND-03 (the three Phase 1 requirements) plus the v1 traceability table
- `.planning/STATE.md` — accumulated decisions, composite-score weights pre-registration table, open calibration questions

### Phase 1 specifics
- `.planning/ROADMAP.md` §"Phase 1: Repo Skeleton & CI Hygiene" — phase goal, dependencies (none), success criteria 1–4
- `.planning/ROADMAP.md` §"Pitfall-Prevention Mapping" — pitfall #14 (Streamlit deploy debt) maps to Phase 1: pandas-ta-classic locked, no TA-Lib in pyproject

### Stack and architecture (research-time decisions)
- `.planning/research/STACK.md` — full version pin matrix, "What NOT to Use" list (the pandas-ta vs pandas-ta-classic correction is the highest-stakes line in this doc), known sharp edges, alternatives considered
- `.planning/research/SUMMARY.md` §"Recommended Stack" + §"Phase 0: Repo Skeleton" — confirms hybrid extras pattern, 3.11 lock, console-script entry point, hatchling default
- `.planning/research/ARCHITECTURE.md` — one-way DAG layered model that `tests/test_architecture.py` enforces (D-16)
- `.planning/research/PITFALLS.md` — pitfall #14 (Streamlit deploy debt) and pitfall #4 (EMA-vs-SMA confusion, scaffolded module docstrings call this out)

### Methodology (project-wide context)
- `CLAUDE.md` §10.1 (Repository layout) — the source-tree shape `tests/test_architecture.py` enforces
- `CLAUDE.md` §10.2 (Configuration) — `pydantic-settings` + `.env` pattern that D-15 codifies
- `CLAUDE.md` §10.3 (Tooling) — uv + ruff + mypy --strict + pytest + hypothesis + pre-commit
- `CLAUDE.md` §10.4 (Logging / observability) — structlog JSON output pattern
- `CLAUDE.md` §11 (CLAUDE.md best practices) — informs README and docs structure
- `CLAUDE.md` §13.6 (Common pitfalls) — what later phases must enforce; Phase 1 just lays the groundwork

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

The repository contains **no source code** — only `CLAUDE.md` (the methodology + AI-pairing brief) and `.planning/` (planning artifacts). Phase 1 *is* establishing the codebase.

### Established Patterns

None yet. Phase 1's primary deliverable is the *patterns themselves*:
- The `data/ → indicators/ → signals/ → regime → sizing → publishers/` layered DAG (D-16 enforces).
- Pure-function math modules with no I/O (CLAUDE.md §10.1 + ARCHITECTURE.md).
- typed `pydantic-settings` for config (D-15).
- Structured JSON logging via structlog (Claude's Discretion).
- pandera schema enforcement at I/O boundaries — *contract reserved by D-13's docstring in `persistence.py`*; actual schemas land in Phase 2 (DAT-09).

### Integration Points

- The Makefile is the single user-facing entry point. Every later phase fills in CLI subcommand bodies; the Makefile contract does not change.
- `src/screener/cli.py` is the typer composition root. Later phases register additional subcommands or add `--flag` options here.
- `src/screener/config.py` `Settings` class accumulates env-var fields phase-by-phase. Adding a field is non-breaking.
- `tests/test_architecture.py` is the gate that any new module placement must pass. Adding `src/screener/foo/` requires extending the contract first.

</code_context>

<specifics>
## Specific Ideas

- **The literal token `<weights frozen at Phase 4 completion>` MUST appear verbatim** in `docs/strategy_v1_preregistration.md` (Phase 1 success criterion 4). Phase 4 will replace it with the actual weights and a git hash; Phase 1 only ships the placeholder.
- **`pandas-ta-classic`, NOT `pandas-ta`.** STACK.md flags this as the single most consequential dependency line in the entire stack. The original `pandas-ta` GitHub repo was removed in 2024–2025; the PyPI package is now beta with murky provenance. Importing `pandas_ta` in code (the module name is the same) works for both, but the `pyproject.toml` declaration must be `pandas-ta-classic`. The planner should add a CI grep or comment in `pyproject.toml` reminding future contributors of this.
- **No TA-Lib in v1.** TA-Lib's C dependency breaks Streamlit Cloud (M2). Even though pandas-ta-classic supports `[talib]` extra, do not enable it in v1.
- **No `pandas-ta` from PyPI.** Same reason — the renamed/beta PyPI package has changed maintainer.
- **`scipy` IS in core dependencies** — Phase 6 needs `scipy.signal.argrelextrema` for VCP pivot detection. Adding it now (Phase 1) keeps the import-linter / architecture-test contract simple from day one rather than introducing a major dep mid-project.

</specifics>

<deferred>
## Deferred Ideas

These came up during analysis but explicitly belong outside Phase 1:

- **Pre-registration token CI grep gate.** The grep that fails CI if `<weights frozen at Phase 4 completion>` is removed without a git hash filling its place is a **Phase 4** deliverable (FND-05 territory). Phase 1 just creates the placeholder.
- **`make backtest-audit`'s forensic checklist.** The CLI subcommand stub exists in Phase 1 (D-14); the actual checklist (no-look-ahead test passing, weight-pre-registration hash match, universe snapshot ≤ backtest start date) is Phase 5 (BCK-07).
- **Pandera schema definitions.** Phase 2 (DAT-09). Phase 1 creates the `persistence.py` module-docstring placeholder only.
- **`runs.jsonl` structured run log.** Phase 8 (OPS-05). Phase 1 stubs do not write to it.
- **EMA-vs-SMA CI grep.** Phase 3 (IND-02). Phase 1 doesn't ship `signals/minervini.py` for it to police.
- **Coverage gate becomes binding.** Phase 3 once `signals/` and `indicators/` have real code. Phase 1 trivially passes 100% on empty modules.
- **`.streamlit/config.toml` and Streamlit-specific config.** M2 milestone (DASH-01). Not in v1.
- **Docs site / README hero-GIF / honest-backtest section.** Evolves through later phases per CLAUDE.md §12.1; Phase 1 ships a minimal README only.
- **Dependabot / Renovate / version-bump automation.** Out of scope for v1; revisit after the milestone closes.
- **CONTRIBUTING.md / CODEOWNERS / issue+PR templates.** Portfolio polish; defer to milestone close or M2.

### Reviewed Todos (not folded)

The `/gsd-discuss-phase` cross-reference-todos step found three open todos in `STATE.md`:

- **"Plan Phase 1 (`/gsd-plan-phase 1`)"** — folded implicitly: this CONTEXT.md *is* the input to that command.
- **"Decide on `data/` directory commit policy (gitignore vs commit Parquet snapshots)"** — explicitly deferred to **Phase 2** planning per STATE.md.
- **"Decide whether to commit `journal.sqlite` to repo"** — explicitly deferred to **Phase 7** planning per STATE.md.

</deferred>

---

*Phase: 1-Repo Skeleton & CI Hygiene*
*Context gathered: 2026-04-28*
