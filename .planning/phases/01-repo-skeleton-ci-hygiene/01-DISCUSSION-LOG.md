# Phase 1: Repo Skeleton & CI Hygiene - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 1-Repo Skeleton & CI Hygiene
**Areas discussed:** pyproject.toml shape & extras; CI shape & dev-loop guardrails; Source-tree scaffolding depth

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Makefile placeholder behavior | What `make data && make rank && make report && make backtest` does in Phase 1. | |
| Source-tree scaffolding depth | Empty `__init__.py` vs stubbed signatures vs hybrid. | ✓ |
| pyproject.toml shape & extras | Flat single `[project]` vs hybrid extras vs aggressive split. | ✓ |
| CI shape & dev-loop guardrails | Job split, triggers, pre-commit, branch protection, uv setup. | ✓ |

**User's choice:** pyproject.toml shape & extras + CI shape & dev-loop guardrails (initial); Source-tree scaffolding depth (added in the second-pass area exploration).

---

## pyproject.toml shape & extras

### Q1 — Dependency organization

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: core + dev + ml extras (Recommended) | Runtime in `[project.dependencies]`; `[dev]` for QA tools; `[ml]` reserved empty for M2. | ✓ |
| Flat single `[project]` | Everything including ruff/mypy/pytest in one list. Simplest config; no test/dev separation. | |
| Extras-heavy: core + dev + backtest + ml + cron | Aggressive split (vectorbt in `[backtest]`, etc.). Maximum future flexibility, most boilerplate. | |

**User's choice:** Hybrid: core + dev + ml extras.
**Notes:** Confirms STACK.md's hybrid pattern; preserves M2 Streamlit-Cloud lean install path; the empty `[ml]` extra is a deliberate seam, not dead config.

### Q2 — Version constraint style

| Option | Description | Selected |
|--------|-------------|----------|
| Compat-style + uv.lock (Recommended) | `>=X,<X+1` ranges in pyproject; commit `uv.lock` for reproducibility. | ✓ |
| Exact pins (==) for everything | No ambiguity, no lockfile needed. High dependabot churn. | |
| Lower-bound only (>=) + uv.lock | Most permissive; trusts uv.lock entirely; risk of `pandas 3` silently landing on `uv lock --upgrade`. | |

**User's choice:** Compat-style + uv.lock.
**Notes:** Matches STACK.md's "Known Sharp Edges" recommendation; human-readable constraints + byte-reproducible installs.

### Q3 — `requires-python`

| Option | Description | Selected |
|--------|-------------|----------|
| `==3.11.*` (lock to 3.11) (Recommended) | STACK.md flags 3.12+ as risky for Numba-dependent libs. Easiest to debug. | ✓ |
| `>=3.11,<3.13` | Permits 3.11 and 3.12 via CI matrix. More CI minutes, more support surface. | |
| `>=3.11` (open upper bound) | Anything 3.11+ resolves. Risk of contributor 3.13 breakage CI doesn't catch. | |

**User's choice:** `==3.11.*` (lock to 3.11).
**Notes:** Bump deliberately later; CI runs 3.11 only.

### Q4 — Build backend + console-script setup

| Option | Description | Selected |
|--------|-------------|----------|
| hatchling + `screener` console script (Recommended) | Modern uv-native default; src/ layout; `[project.scripts] screener = "screener.cli:app"`. | ✓ |
| setuptools + `screener` console script | Conventional setuptools backend with `[tool.setuptools.packages.find]`. More boilerplate. | |
| hatchling, no console script (call via `python -m`) | Skip `[project.scripts]`; invoke as `python -m screener.cli`. | |

**User's choice:** hatchling + `screener` console script.

---

## CI shape & dev-loop guardrails

### Q1 — Workflow structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single workflow, parallel jobs (Recommended) | One `ci.yml` with three parallel jobs: lint / typecheck / test. | ✓ |
| Single workflow, single job (sequential) | One job runs `ruff && mypy && pytest`. Simpler, slower, hides downstream feedback. | |
| Separate workflow files | One file per gate. Cleanest concern split, triple-duplicates setup. | |

**User's choice:** Single workflow, parallel jobs.

### Q2 — CI triggers

| Option | Description | Selected |
|--------|-------------|----------|
| PR + push to main (Recommended) | Both PR and post-merge regressions surface. Public repo = unlimited free minutes. | ✓ |
| PR only | Strict letter of FND-03; risk of force-push or hot-fix bypass. | |
| PR + push to all branches | Heaviest minute usage; mostly noise for solo dev. | |

**User's choice:** PR + push to main.

### Q3 — Pre-commit hooks

| Option | Description | Selected |
|--------|-------------|----------|
| ruff + mypy --quick, no pytest (Recommended) | Fast feedback loop; pytest is CI-only. | ✓ |
| All three (ruff + mypy + pytest) | Mirror CI exactly; every commit pays pytest cost. | |
| CI only — no pre-commit | Zero local setup; round-trip through CI for lint/type errors. | |
| ruff only | Lightest pre-commit; catches most common issue (style). | |

**User's choice:** ruff + mypy --quick, no pytest.

### Q4 — Branch protection + uv setup

| Option | Description | Selected |
|--------|-------------|----------|
| Branch protection ON + setup-uv@v6 with caching (Recommended) | Required CI checks, PR-required, no force-push; uv-cache cuts CI from ~3 min to ~30 s. | ✓ |
| Convention only now, branch protection in Phase 8 | Defers admin click; trusts solo-dev discipline. | |
| Branch protection ON + manual uv install | Loses cache plumbing; full cold install every CI run. | |
| Convention only + manual uv install | Lightest-touch; no admin click, no third-party action. | |

**User's choice:** Branch protection ON now + `astral-sh/setup-uv@v6` with caching.

### Q5 — mypy `--strict` scope

| Option | Description | Selected |
|--------|-------------|----------|
| signals/ + indicators/ only (Recommended) | Matches FND-03 verbatim; loosen `data/`, `publishers/`, `cli.py`. | |
| Expand to signals/ + indicators/ + regime/ + sizing/ + composite | Strict on every pure-function math module. Slightly more friction. | ✓ |
| Strict everywhere except `data/` | Maximum coverage; risk of typer + pandas + Plotly stub friction. | |
| Strict on whole codebase | Most disciplined; most likely to fight third-party stubs in early phases. | |

**User's choice:** Expand to signals/ + indicators/ + regime/ + sizing/ + composite.
**Notes:** Wider than FND-03's literal wording, but reflects the reality that those four modules share the same pure-function correctness profile as signals/indicators.

### Q6 — pytest configuration

| Option | Description | Selected |
|--------|-------------|----------|
| tests/ at root, markers (slow/integration), no coverage gate (Recommended) | Coverage added in Phase 3+ once real tests exist. | |
| tests/ at root + markers + coverage gate (≥80% on signals/+indicators/) | Aspirational gate; trivially satisfied in Phase 1, binding in Phase 3+. | ✓ |
| tests/ at root, no markers, no coverage | Minimal config. | |
| src/screener/tests/ co-located | Less common in Python; complicates shared fixtures. | |

**User's choice:** tests/ at root + markers + coverage gate (≥80% on signals/+indicators/).
**Notes:** Captured in CONTEXT.md that the gate is trivially satisfied in Phase 1 and becomes binding from Phase 3.

### Q7 — Ruff lint rule selection

| Option | Description | Selected |
|--------|-------------|----------|
| Pragmatic curated set (Recommended) | `E, F, I, B, UP, N, SIM, RUF, PD, NPY` + line-length 100. PD/NPY catch quant idioms. | ✓ |
| ALL with explicit ignores | Maximally strict; portfolio-credibility signal; tuning overhead. | |
| Default ruff rules only | Just `E, F`. Misses pandas/numpy idioms that matter here. | |

**User's choice:** Pragmatic curated set.

---

## Source-tree scaffolding depth

### Q1 — Scaffold depth

| Option | Description | Selected |
|--------|-------------|----------|
| CLI + module docstrings, otherwise empty (Recommended) | Layer `__init__.py` with role docstring; `cli.py` real typer; `config.py` real Settings. | ✓ |
| Empty __init__.py only | No code anywhere; lightest scaffold; defers every design decision. | |
| Full stub signatures with NotImplementedError | Lock public API everywhere. Heavy commitment; risk of premature contracts. | |
| CLI + persistence stub + module docstrings | Adds typed but body-less `persistence.py` interface. | |

**User's choice:** CLI + module docstrings, otherwise empty.

### Q2 — typer subcommand surface

| Option | Description | Selected |
|--------|-------------|----------|
| Full v1 surface, all no-op (Recommended) | All later-phase subcommands ship as stubs that log + exit 0. | ✓ |
| Only what FND-02 needs (`data`, `rank`, `report`, `backtest`) | Match the four Makefile targets exactly. | |
| Just `screener --version` + a `hello` smoke command | Bare minimum; defers CLI design entirely. | |

**User's choice:** Full v1 surface, all no-op.
**Notes:** Implicitly resolves the Makefile-placeholder gray area — Makefile targets shell out to the real (stubbed) typer subcommands; the artifact pipeline is structurally present from day one.

### Q3 — Architectural-boundary enforcement test

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — import-linter config in pyproject.toml (Recommended) | Third-party tool; one contract file; locks DAG forever. | |
| Yes — hand-rolled `tests/test_architecture.py` | Plain pytest using `ast` walks. No new dependency. | ✓ |
| Defer — layer rule in CLAUDE.md only, no test | Trust convention; add test in Phase 2. | |

**User's choice:** Hand-rolled `tests/test_architecture.py`.
**Notes:** Same guarantees as `import-linter` with no third-party trust point and one less dep to maintain.

---

## Claude's Discretion

The user did not call these out explicitly; the planner has flexibility within the locked decisions above:

- Makefile target dependencies, `.PHONY` declarations, `help` target self-documentation pattern, `setup` target.
- `.gitignore` contents (standard Python + uv + macOS layout, plus output dirs).
- LICENSE choice (MIT vs Apache-2.0).
- README skeleton structure (minimal Phase 1; evolves per CLAUDE.md §12.1).
- `.env.example` contents (mirror Settings fields with placeholder values).
- Pre-registration doc surrounding scaffold (the literal token must appear verbatim; the rest of the file is a template stub).
- Exact filename for the structlog configuration helper module (avoid shadowing `logging` stdlib).

---

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Pre-registration token CI grep gate → Phase 4 (FND-05).
- `make backtest-audit` forensic checklist → Phase 5 (BCK-07).
- Pandera schema definitions → Phase 2 (DAT-09).
- `runs.jsonl` structured run log → Phase 8 (OPS-05).
- EMA-vs-SMA CI grep → Phase 3 (IND-02).
- Coverage gate becomes binding → Phase 3 (once real signals/indicators exist).
- Streamlit config / dashboard → M2 (DASH-01).
- Dependabot / Renovate → out of scope for v1.
- CONTRIBUTING.md / CODEOWNERS / issue+PR templates → portfolio polish; defer.
- `data/` commit policy → Phase 2 planning per STATE.md.
- `journal.sqlite` commit policy → Phase 7 planning per STATE.md.
