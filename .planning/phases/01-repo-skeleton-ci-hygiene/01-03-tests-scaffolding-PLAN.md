---
phase: 01-repo-skeleton-ci-hygiene
plan: 03
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - tests/__init__.py
  - tests/conftest.py
  - tests/test_architecture.py
  - tests/test_cli_smoke.py
autonomous: true
requirements: [FND-03]
must_haves:
  truths:
    - "Running `uv run pytest` exits 0 from a clean checkout (architecture test passes; CLI smoke test passes)"
    - "tests/test_architecture.py uses ast.parse + ast.walk to enforce the one-way layered DAG (D-16) — no third-party import-linter dependency"
    - "tests/test_cli_smoke.py asserts `screener --help` lists all 9 D-14 subcommands and that each subcommand exits 0"
    - "Adding a forbidden import (e.g., `from screener.publishers import ...` inside `src/screener/indicators/`) causes test_architecture.py to fail"
    - "Coverage gate (--cov-fail-under=80) is trivially satisfied at Phase 1 because signals/+indicators/ have no executable lines (only module docstrings)"
  artifacts:
    - path: "tests/__init__.py"
      provides: "Test package marker (empty)"
    - path: "tests/conftest.py"
      provides: "Shared pytest fixtures and configuration; Phase 1 minimal"
    - path: "tests/test_architecture.py"
      provides: "Hand-rolled AST-based DAG enforcement (D-16)"
      contains: "ast.parse"
    - path: "tests/test_cli_smoke.py"
      provides: "Smoke tests for the typer CLI surface (D-14)"
      contains: "screener --help"
  key_links:
    - from: "tests/test_architecture.py"
      to: "src/screener/**/*.py"
      via: "ast.walk over imports"
      pattern: "ast\\.parse"
    - from: "tests/test_cli_smoke.py"
      to: "src/screener/cli.py"
      via: "subprocess.run(['screener', ...]) or typer CliRunner"
      pattern: "(CliRunner|subprocess)"
---

<objective>
Establish the pytest scaffolding and ship the two foundational tests Phase 1 owns:
1. `tests/test_architecture.py` — the hand-rolled (no `import-linter` dep) AST-based test that enforces the one-way layered DAG per D-16. This is the architectural contract that prevents future PRs from violating the layer rules silently.
2. `tests/test_cli_smoke.py` — asserts the typer CLI surface from Plan 02 exposes all 9 D-14 subcommands and each exits 0.

Purpose: FND-03 requires CI to run pytest; Phase 1 needs at least one meaningful test to satisfy the architectural-contract goal. The architecture test is the single most valuable Phase 1 test — it locks the DAG so later phases cannot accidentally invert dependencies.

Output: A `tests/` directory that, on `uv run pytest`, exits 0 (with the coverage gate trivially satisfied because signals/+indicators/ have only docstrings) and would FAIL if any layer rule from D-16 were violated.
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
  <name>Task 1: Create tests package scaffolding (tests/__init__.py and tests/conftest.py)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-11 — pytest config; markers)
    - pyproject.toml (just authored — confirms `[tool.pytest.ini_options]` with markers and coverage gate)
    - CLAUDE.md §10.5 (Testing strategy)
  </read_first>
  <files>tests/__init__.py, tests/conftest.py</files>
  <action>
Create `tests/__init__.py` (empty file is fine; presence makes pytest treat `tests/` as a package and prevents test name collisions later).

Create `tests/conftest.py` with a minimal Phase 1 baseline. Phase 2+ will add OHLCV fixtures, golden-file loaders, etc. Phase 1 only needs the pytest plumbing to discover tests cleanly.

**`tests/__init__.py`**:
```python
"""tests — pytest suite for screener."""
```

**`tests/conftest.py`**:
```python
"""Shared pytest configuration and fixtures.

Phase 1 ships only the fixtures Phase 1 tests need. Phase 2+ will add OHLCV
fixtures, regime golden-files, etc.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root (parent of `tests/`)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_screener(repo_root: Path) -> Path:
    """Absolute path to src/screener/."""
    return repo_root / "src" / "screener"
```
  </action>
  <verify>
    <automated>test -f tests/__init__.py &amp;&amp; test -f tests/conftest.py &amp;&amp; uv run pytest --collect-only --quiet 2>&amp;1 | grep -qE "(collected 0 items|no tests ran)" || true; uv run python -c "import sys; sys.path.insert(0, '.'); from tests.conftest import repo_root, src_screener"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/__init__.py` exists
    - `tests/conftest.py` exists with `repo_root` and `src_screener` fixtures
    - `uv run pytest --collect-only --quiet` succeeds (collects 0 items at this point because no test files exist yet, but pytest exits cleanly)
    - `grep -F 'def repo_root' tests/conftest.py` matches
    - `grep -F 'def src_screener' tests/conftest.py` matches
  </acceptance_criteria>
  <done>pytest discovers `tests/` as a package; the two session-scoped path fixtures are available for the architecture test.</done>
</task>

<task type="auto">
  <name>Task 2: Create tests/test_architecture.py — AST-based one-way DAG enforcement (D-16)</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-16 — full layer-import contract)
    - .planning/research/ARCHITECTURE.md (Component Responsibilities + structure rationale)
    - All 13 files from Plan 02: src/screener/__init__.py, cli.py, config.py, obs.py, persistence.py, regime.py, sizing.py, data/__init__.py, indicators/__init__.py, signals/__init__.py, publishers/__init__.py, backtest/__init__.py, catalysts/__init__.py, ml/__init__.py
  </read_first>
  <files>tests/test_architecture.py</files>
  <action>
Create the hand-rolled AST-based architecture test that enforces the one-way layered DAG per D-16. The test scans every `.py` file under `src/screener/` (excluding `__pycache__`) using `ast.parse` + `ast.walk`, extracts every `import screener.X` and `from screener.X import ...` statement, and asserts each layer imports only from its allowed peers.

The contract (verbatim from D-16, with `cli` and `config` and `persistence` and `obs` treated as widely-importable utility modules):

| Layer file/dir | Allowed internal imports |
|----------------|--------------------------|
| `data/*` | `persistence`, `config`, `obs` |
| `indicators/*` | `persistence`, `config`, `obs` |
| `signals/*` | `indicators`, `regime`, `persistence`, `config`, `obs` |
| `regime` | `data`, `indicators`, `persistence`, `config`, `obs` |
| `sizing` | `signals`, `regime`, `config`, `obs` |
| `publishers/*` | `signals`, `sizing`, `regime`, `persistence`, `config`, `obs` |
| `backtest/*` | `persistence` ONLY (D-16 verbatim: persistence + stdlib only, no `data`, no `config`, no `obs` — keeps backtest airtight against network/API-key access) |
| `catalysts/*` | (Phase 1: stub seam — allow `persistence`, `config`, `obs` only; downstream rules reserved for Phase 6+/M2) |
| `ml/*` | (Phase 1: M2 reserve — allow `persistence`, `config`, `obs` only) |
| `cli` | any (composition root) |
| `config` | (no internal imports) |
| `persistence` | `config`, `obs` only |
| `obs` | (no internal imports) |

The test classifies each file by its layer (top-level package directory or top-level module file), enumerates every imported `screener.*` symbol, and asserts each import target is in the allowed set for that layer.

```python
"""Architecture test — hand-rolled AST-based one-way DAG enforcement (D-16).

Scans every src/screener/**/*.py file and asserts each module imports only
from its allowed peer modules per the layered-architecture contract in
.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-16) and
.planning/research/ARCHITECTURE.md.

Zero third-party dependencies — chose stdlib `ast` over `import-linter` to
avoid an extra trust point and keep the contract self-contained.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Layer → allowed internal-module-name set. Internal here = "screener.X" or
# "from screener.X import ...". `cli` is the composition root (any import
# allowed). D-16 (CONTEXT.md) is the source of truth for these sets.
#
# `obs` is added to every non-backtest layer as a Claude's-Discretion
# expansion of D-16: structured logging is universally needed and CONTEXT.md
# introduced `obs.py` under Discretion. `backtest` is the explicit exception:
# D-16 says "persistence + stdlib only — never publishers/, never makes
# network calls." Allowing `config` or `obs` in backtest would let it reach
# API keys (config) or pull a logger that depends on env (obs), weakening the
# "backtest is airtight" invariant. Backtest uses stdlib `logging` if needed.
ALLOWED: dict[str, set[str]] = {
    "data": {"persistence", "config", "obs"},
    "indicators": {"persistence", "config", "obs"},
    "signals": {"indicators", "regime", "persistence", "config", "obs"},
    "regime": {"data", "indicators", "persistence", "config", "obs"},
    "sizing": {"signals", "regime", "config", "obs"},
    "publishers": {"signals", "sizing", "regime", "persistence", "config", "obs"},
    "backtest": {"persistence"},  # D-16 verbatim: persistence + stdlib only, never network
    "catalysts": {"persistence", "config", "obs"},
    "ml": {"persistence", "config", "obs"},
    "persistence": {"config", "obs"},
    "config": set(),
    "obs": set(),
    # cli imports anything (composition root); no entry here means we skip checks.
}


def _classify(path: Path, src_root: Path) -> str | None:
    """Return the layer name for a given source file, or None for `cli` (composition root)."""
    rel = path.relative_to(src_root)
    parts = rel.parts
    # parts[0] is either a file like "cli.py" or a directory like "data".
    if parts[0] == "__init__.py":
        return None  # package-level __init__.py for `screener` itself
    if parts[0].endswith(".py"):
        # Top-level module file: cli.py / config.py / obs.py / persistence.py /
        # regime.py / sizing.py
        return parts[0][:-3]
    # Directory: parts[0] is the layer
    return parts[0]


def _internal_imports(tree: ast.AST) -> set[str]:
    """Extract every `screener.<X>` internal import target from an AST.

    Returns the set of top-level layer names referenced. E.g.
    `from screener.indicators.trend import sma50` -> {"indicators"}.
    `import screener.persistence as p` -> {"persistence"}.
    Imports of `screener` itself or `screener.cli` are returned as "cli"/"_self".
    """
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "screener" or not mod.startswith("screener."):
                if mod == "screener":
                    # `from screener import X` — X is the layer name
                    for alias in node.names:
                        targets.add(alias.name)
                continue
            # mod looks like "screener.indicators.trend"
            tail = mod[len("screener.") :]
            top = tail.split(".", 1)[0]
            targets.add(top)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "screener" or not name.startswith("screener."):
                    continue
                tail = name[len("screener.") :]
                top = tail.split(".", 1)[0]
                targets.add(top)
    return targets


def _iter_source_files(src_root: Path) -> list[Path]:
    """Yield every src/screener/**/*.py file (excluding __pycache__)."""
    return sorted(
        p
        for p in src_root.rglob("*.py")
        if "__pycache__" not in p.parts and p.is_file()
    )


def test_layer_import_contract(src_screener: Path) -> None:
    """Every src/screener/**/*.py imports only from its allowed peer layers."""
    violations: list[str] = []
    for path in _iter_source_files(src_screener):
        layer = _classify(path, src_screener)
        if layer is None or layer == "cli":
            # Skip the package-level __init__.py and cli.py (composition root).
            continue
        # Strip layer files like "regime.py" -> "regime"; dirs already match.
        # `_classify` returns "regime" for both `regime.py` and (hypothetically)
        # `regime/`; same for sizing, persistence, etc.
        allowed = ALLOWED.get(layer)
        if allowed is None:
            violations.append(
                f"{path}: layer '{layer}' has no entry in ALLOWED — extend "
                f"the test contract before adding new layers."
            )
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            violations.append(f"{path}: SyntaxError {e}")
            continue
        imports = _internal_imports(tree)
        # `cli` is the only module allowed to import anything — and we skip it.
        # Every other layer must satisfy: imports ⊆ allowed ∪ {layer itself}.
        forbidden = {imp for imp in imports if imp not in allowed and imp != layer}
        if forbidden:
            violations.append(
                f"{path}: layer '{layer}' imports forbidden peer(s) "
                f"{sorted(forbidden)}; allowed = {sorted(allowed)}"
            )

    assert not violations, "Layer-import contract violations:\n" + "\n".join(violations)


def test_backtest_does_not_import_data_layer(src_screener: Path) -> None:
    """backtest/ MUST NOT import data/, config, or obs (D-16: persistence + stdlib only)."""
    bt_dir = src_screener / "backtest"
    if not bt_dir.exists():
        pytest.skip("backtest/ directory not present (Phase 1 stub may be empty)")
    forbidden_internal = {"data", "config", "obs", "publishers", "catalysts", "ml",
                          "indicators", "signals", "regime", "sizing"}
    for path in _iter_source_files(bt_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = _internal_imports(tree)
        leaked = imports & forbidden_internal
        assert not leaked, (
            f"{path}: backtest/ imports forbidden internal module(s) {sorted(leaked)} — "
            f"D-16 says backtest reads `persistence` + stdlib only, never config "
            f"(API keys), never obs (env-coupled logger), never network."
        )


def test_indicators_signals_pure_no_io_imports(src_screener: Path) -> None:
    """indicators/ and signals/ MUST NOT import requests/yfinance/finnhub/edgartools/sqlite3/etc."""
    forbidden_external = {
        "requests",
        "yfinance",
        "finnhub",
        "edgar",
        "edgartools",
        "fredapi",
        "sqlite3",
        "urllib",
        "urllib3",
        "httpx",
        "requests_cache",
    }
    for layer in ("indicators", "signals"):
        layer_dir = src_screener / layer
        if not layer_dir.exists():
            continue
        for path in _iter_source_files(layer_dir):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    assert name not in forbidden_external, (
                        f"{path}: layer '{layer}' imports I/O package "
                        f"'{name}' — pure-function discipline violated "
                        f"(D-13, ARCHITECTURE.md Pattern 2)."
                    )
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_architecture.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_architecture.py` exists
    - `grep -F 'ast.parse' tests/test_architecture.py` matches (uses stdlib AST, not import-linter)
    - `grep -F 'import_linter\|importlinter' tests/test_architecture.py` returns NO matches
    - `uv run pytest tests/test_architecture.py -v` exits 0 (all three tests pass against the Plan 02 source tree)
    - The ALLOWED dict contains entries for all 9 layers from D-16 plus `persistence`, `config`, `obs`: verify with `grep -cE '"(data|indicators|signals|regime|sizing|publishers|backtest|catalysts|ml|persistence|config|obs)":' tests/test_architecture.py` returns at least 12
    - Manual mutation check (NOT a CI gate, but verify locally): temporarily add `from screener.publishers import report  # noqa` to `src/screener/indicators/__init__.py` → re-run `uv run pytest tests/test_architecture.py` → MUST FAIL with a layer-violation message → revert the mutation
  </acceptance_criteria>
  <done>The hand-rolled AST DAG test passes against the Plan 02 source tree and would fail loudly if any layer violation were introduced. No third-party import-linter dependency.</done>
</task>

<task type="auto">
  <name>Task 3: Create tests/test_cli_smoke.py — verify all 9 D-14 subcommands</name>
  <read_first>
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md (D-14 — exact subcommand list)
    - src/screener/cli.py (just authored in Plan 02)
    - typer documentation patterns: typer's CliRunner is the recommended in-process test harness
  </read_first>
  <files>tests/test_cli_smoke.py</files>
  <action>
Create the CLI smoke test using typer's `CliRunner` (in-process, fast, no subprocess overhead). Asserts:
1. `screener --help` lists all 9 D-14 subcommand names.
2. Each of the 9 subcommands runs and exits 0.
3. Each subcommand emits a JSON line containing `"command": "<name>"` and the literal string `[stub]`.

```python
"""CLI smoke tests — assert the typer surface from D-14 is intact.

Uses typer's CliRunner (in-process; no subprocess) for speed.
"""

from __future__ import annotations

import json
from typer.testing import CliRunner

from screener.cli import app

D14_SUBCOMMANDS = [
    "refresh-universe",
    "refresh-ohlcv",
    "refresh-macro",
    "refresh-fundamentals",
    "score",
    "report",
    "journal",
    "backtest",
    "backtest-audit",
]


def test_help_lists_all_d14_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.stdout
    for name in D14_SUBCOMMANDS:
        assert name in result.stdout, (
            f"Subcommand '{name}' missing from `screener --help` output. "
            f"D-14 in CONTEXT.md locks the v1 typer surface."
        )


def test_each_subcommand_exits_zero_with_stub_log() -> None:
    runner = CliRunner()
    for name in D14_SUBCOMMANDS:
        result = runner.invoke(app, [name])
        assert result.exit_code == 0, (
            f"`screener {name}` exited {result.exit_code}; expected 0. "
            f"stdout: {result.stdout}"
        )
        # Each invocation should emit at least one JSON log line containing
        # the subcommand name and the literal "[stub]" marker.
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
        assert found, (
            f"`screener {name}` did not emit a structured [stub] log line. "
            f"stdout was: {result.stdout!r}"
        )
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_cli_smoke.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_cli_smoke.py` exists
    - `grep -F 'from typer.testing import CliRunner' tests/test_cli_smoke.py` matches
    - The `D14_SUBCOMMANDS` list contains exactly the 9 names from D-14
    - `uv run pytest tests/test_cli_smoke.py -v` exits 0 (both tests pass)
    - `uv run pytest` (whole suite) exits 0
  </acceptance_criteria>
  <done>The CLI smoke test passes against Plan 02's cli.py; adding/removing a D-14 subcommand without updating the test list fails CI loudly.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer-PR ↔ test-suite | Tests are the gate that prevents regressions; a bypass is a bypass of every architectural invariant |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Tampering | Architecture test bypass | mitigate | Plan 05 wires `pytest` as a required CI status check (D-08); branch protection on `main` requires all status checks to pass before merge. Disabling the test on a branch fails the `test` job. |
| T-03-02 | Tampering | Layer contract drift | mitigate | The ALLOWED dict in test_architecture.py is the single source of truth; future PRs that add a new layer (e.g., `screener/streaming/`) must extend ALLOWED → diff is visible in code review. |
| T-03-03 | Spoofing | typer CliRunner stdout capture | accept | CliRunner runs in-process; stdout is captured deterministically. No realistic spoofing surface. |
| T-03-04 | Information Disclosure | Test logs in CI | accept | Phase 1 stubs do not access real Settings values, so test stdout contains no secrets. Phase 2+ will need to revisit. |

</threat_model>

<verification>
After all three tasks complete:
1. `uv run pytest -v` exits 0
2. `uv run pytest tests/test_architecture.py::test_layer_import_contract` exits 0
3. `uv run pytest tests/test_architecture.py::test_backtest_does_not_import_data_layer` exits 0
4. `uv run pytest tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` exits 0
5. `uv run pytest tests/test_cli_smoke.py -v` exits 0
6. Coverage report shows `signals/` and `indicators/` at ≥ 80% (trivially satisfied — empty modules report 100% / no executable lines)
</verification>

<success_criteria>
- `tests/__init__.py`, `tests/conftest.py`, `tests/test_architecture.py`, `tests/test_cli_smoke.py` all exist
- The hand-rolled D-16 layer-import contract is encoded in the test (no `import-linter` dependency)
- All three architecture sub-tests pass against the Plan 02 source tree
- The CLI smoke test confirms all 9 D-14 subcommands are present and each exits 0 with a structured [stub] log line
- `uv run pytest` exits 0 from a clean checkout (with the `--cov-fail-under=80` gate trivially satisfied)
</success_criteria>

<output>
After completion, create `.planning/phases/01-repo-skeleton-ci-hygiene/01-03-SUMMARY.md` with:
- Tests created
- Confirmation that `uv run pytest` exits 0
- Confirmation that the architecture test would fail under a deliberate violation (manual local mutation check, not committed)
- Coverage gate result for Phase 1 (signals/+indicators/ have no executable lines so the gate is trivially satisfied)
</output>
