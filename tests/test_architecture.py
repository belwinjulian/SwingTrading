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
