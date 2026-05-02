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
