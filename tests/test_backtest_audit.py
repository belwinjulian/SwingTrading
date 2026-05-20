"""BCK-07: Forensic audit CLI tests (4-check checklist).

Phase 5 Wave 3 — body filled (Wave 0 stub replaced).

Tests monkeypatch CWD into tmp_path so the audit's Path('data/...') lookups
resolve to fixture dirs. Subprocess calls (Check 1: pytest; Check 2:
check_preregistration.py) are monkeypatched to control returncode without
spawning real subprocesses.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from screener.cli import app


@dataclass
class _FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess used by audit."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


def _parse_json_events(stdout: str) -> list[dict[str, Any]]:
    """Extract structlog JSON event lines from CLI stdout."""
    out: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _seed_snapshots(snap_dir: Path, n_years: int = 6) -> None:
    """Create empty parquet files for daily date stems across n_years."""
    snap_dir.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    dates = pd.bdate_range("2018-01-01", periods=252 * n_years)
    for d in dates:
        (snap_dir / f"{d.strftime('%Y-%m-%d')}.parquet").touch()


def _seed_universe(uni_dir: Path, stem: str = "2015-01-01") -> None:
    """Create one empty universe parquet file."""
    uni_dir.mkdir(parents=True, exist_ok=True)
    (uni_dir / f"{stem}.parquet").touch()


def _fake_subprocess_factory(
    return_codes: dict[str, int],
) -> Any:
    """Build a fake subprocess.run that returns custom codes based on argv contents."""

    def _fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        joined = " ".join(argv)
        if "test_backtest_no_lookahead" in joined:
            return _FakeCompletedProcess(returncode=return_codes.get("nla", 0))
        if "check_preregistration" in joined:
            return _FakeCompletedProcess(returncode=return_codes.get("prereg", 0))
        return _FakeCompletedProcess(returncode=0)

    return _fake_run


def test_audit_all_checks_pass_returns_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: all 4 checks PASS -> exit 0 + 'AUDIT PASSED' in stdout."""
    monkeypatch.chdir(tmp_path)
    _seed_snapshots(tmp_path / "data" / "snapshots", n_years=6)
    _seed_universe(tmp_path / "data" / "universe", stem="2015-01-01")
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_factory({"nla": 0, "prereg": 0}))
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}; stdout={result.stdout}"
    assert "AUDIT PASSED" in result.stdout


def test_audit_empty_snapshots_dir_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No data/snapshots/ -> check #4 FAIL -> exit 1."""
    monkeypatch.chdir(tmp_path)
    _seed_universe(tmp_path / "data" / "universe", stem="2015-01-01")
    # Do NOT create data/snapshots/
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_factory({"nla": 0, "prereg": 0}))
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    assert result.exit_code != 0, "expected non-zero exit for empty snapshots"
    assert "AUDIT FAILED" in result.stdout
    events = _parse_json_events(result.stdout)
    audit_checks = [e for e in events if e.get("event") == "audit_check"]
    oos_check = next((e for e in audit_checks if "OOS" in str(e.get("check", ""))), None)
    assert oos_check is not None, "expected an OOS-window audit_check event"
    assert oos_check["result"] == "FAIL", f"expected OOS check FAIL, got {oos_check['result']}"


def test_audit_empty_universe_dir_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No data/universe/ -> check #3 FAIL (REVISED: FAIL only when missing entirely) -> exit 1."""
    monkeypatch.chdir(tmp_path)
    _seed_snapshots(tmp_path / "data" / "snapshots", n_years=6)
    # Do NOT create data/universe/
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_factory({"nla": 0, "prereg": 0}))
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    assert result.exit_code != 0, "expected non-zero exit for missing universe"
    assert "AUDIT FAILED" in result.stdout
    events = _parse_json_events(result.stdout)
    audit_checks = [e for e in events if e.get("event") == "audit_check"]
    uni_check = next((e for e in audit_checks if "universe" in str(e.get("check", ""))), None)
    assert uni_check is not None, "expected a universe audit_check event"
    assert uni_check["result"] == "FAIL", f"expected universe FAIL, got {uni_check['result']}"


def test_audit_preregistration_failure_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preregistration subprocess returns 1 -> check #2 FAIL -> exit 1."""
    monkeypatch.chdir(tmp_path)
    _seed_snapshots(tmp_path / "data" / "snapshots", n_years=6)
    _seed_universe(tmp_path / "data" / "universe", stem="2015-01-01")
    monkeypatch.setattr(subprocess, "run", _fake_subprocess_factory({"nla": 0, "prereg": 1}))
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    assert result.exit_code != 0, "expected non-zero exit for preregistration drift"
    assert "AUDIT FAILED" in result.stdout
    events = _parse_json_events(result.stdout)
    audit_checks = [e for e in events if e.get("event") == "audit_check"]
    prereg = next((e for e in audit_checks if "preregistration" in str(e.get("check", ""))), None)
    assert prereg is not None, "expected a preregistration audit_check event"
    assert prereg["result"] == "FAIL", f"expected preregistration FAIL, got {prereg['result']}"
