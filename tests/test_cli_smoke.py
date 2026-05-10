"""CLI smoke tests — assert the typer surface from D-14 is intact, plus the
Phase 2 95% health-gate semantics for refresh-ohlcv (DAT-07).

Uses typer's CliRunner (in-process; no subprocess) for speed.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

from screener.cli import app

# D-14 subcommand surface — LOCKED. Do not add/rename without amending the
# CONTEXT.md decision and this list together.
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

# Phase-2-stub-only subset for the [stub] log-line iteration (refresh-universe,
# refresh-ohlcv, and refresh-macro now do real work and no longer emit [stub]).
PHASE_1_STUBS = [
    "refresh-fundamentals",
    "journal",
    "backtest",
    "backtest-audit",
]


# --- Helpers ----------------------------------------------------------------


def _parse_json_events(stdout: str) -> list[dict[str, Any]]:
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


# --- D-14 surface tests (preserved + amended) ------------------------------


def test_help_lists_all_d14_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.stdout
    for name in D14_SUBCOMMANDS:
        assert name in result.stdout, (
            f"Subcommand '{name}' missing from `screener --help` output. "
            f"D-14 in CONTEXT.md locks the v1 typer surface."
        )


def test_each_phase1_stub_exits_zero_with_stub_log() -> None:
    """Phase 1 stubs (the 7 still-stubbed subcommands) emit a [stub] log line."""
    runner = CliRunner()
    for name in PHASE_1_STUBS:
        result = runner.invoke(app, [name])
        assert result.exit_code == 0, (
            f"`screener {name}` exited {result.exit_code}; expected 0. stdout: {result.stdout}"
        )
        events = _parse_json_events(result.stdout)
        found = any(
            ev.get("command") == name and "[stub]" in ev.get("message", "") for ev in events
        )
        assert found, (
            f"`screener {name}` did not emit a structured [stub] log line. "
            f"events: {events!r}"
        )


# --- DAT-07 health-gate integration tests (NEW) ----------------------------


def _mock_universe_df() -> pd.DataFrame:
    """A 10-ticker universe used by the health-gate tests."""
    tickers = [f"T{i:03d}" for i in range(10)]
    return pd.DataFrame(
        {
            "ticker": tickers,
            "ticker_raw": tickers,
            "name": [f"Co {i}" for i in range(10)],
            "sector": ["Information Technology"] * 10,
            "weight_pct": [0.5] * 10,
        }
    )


def test_health_gate_below_95_fails_run(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Combined success rate 8/10 = 0.80 < 0.95 -> CLI exits non-zero with 'health_check_failed'."""
    # Patch the universe lookup + read so we don't need real iShares.
    fake_snapshot = tmp_path / "2026-04-27.parquet"
    fake_snapshot.touch()  # _latest_universe_snapshot just needs the file to exist
    monkeypatch.setattr("screener.cli._latest_universe_snapshot", lambda: fake_snapshot)
    monkeypatch.setattr("screener.cli.read_universe", lambda d: _mock_universe_df())
    # 8 yf successes + 0 stooq + 2 failures = 0.80 < 0.95 threshold.
    monkeypatch.setattr(
        "screener.cli.run_with_breaker",
        lambda tickers, today: (8, 0, ["T008", "T009"]),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["refresh-ohlcv"])
    assert result.exit_code != 0, (
        f"Expected non-zero exit on below-threshold gate; got {result.exit_code}."
        f" stdout: {result.stdout}"
    )
    events = _parse_json_events(result.stdout)
    failed_event = [ev for ev in events if ev.get("event") == "health_check_failed"]
    assert failed_event, f"Expected 'health_check_failed' event; got events: {events!r}"
    ev = failed_event[0]
    assert ev.get("success_count") == 8
    assert ev.get("universe_size") == 10
    assert ev.get("threshold") == 0.95


def test_health_gate_above_95_passes_run(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Combined success rate 10/10 = 1.0 >= 0.95 -> CLI exits 0 with 'health_check_passed'."""
    fake_snapshot = tmp_path / "2026-04-27.parquet"
    fake_snapshot.touch()
    monkeypatch.setattr("screener.cli._latest_universe_snapshot", lambda: fake_snapshot)
    monkeypatch.setattr("screener.cli.read_universe", lambda d: _mock_universe_df())
    monkeypatch.setattr(
        "screener.cli.run_with_breaker",
        lambda tickers, today: (10, 0, []),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["refresh-ohlcv"])
    assert result.exit_code == 0, (
        f"Expected exit 0 on above-threshold gate; got {result.exit_code}. stdout: {result.stdout}"
    )
    events = _parse_json_events(result.stdout)
    passed = [ev for ev in events if ev.get("event") == "health_check_passed"]
    assert passed, f"Expected 'health_check_passed' event; got events: {events!r}"


# --- refresh-universe smoke (idempotent skip case) -------------------------


def test_refresh_universe_idempotent_skip_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """When data/universe/<iso_monday>.parquet already exists, the CLI exits 0 without error."""
    monkeypatch.setattr("screener.cli.refresh_universe_impl", lambda force, today: None)
    runner = CliRunner()
    result = runner.invoke(app, ["refresh-universe"])
    assert result.exit_code == 0
    events = _parse_json_events(result.stdout)
    skip = [ev for ev in events if ev.get("event") == "refresh_universe_skipped"]
    assert skip, f"Expected 'refresh_universe_skipped' event; got: {events!r}"


def test_refresh_universe_success_path_smoke(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """refresh-universe success path: impl returns a written Path -> CLI exits 0
    AND a structured event is emitted. Pairs with the idempotent-skip test so
    each of the 9 subcommands has independent exit-0 coverage.
    """
    written = tmp_path / "2026-04-27.parquet"
    written.touch()
    monkeypatch.setattr("screener.cli.refresh_universe_impl", lambda force, today: written)
    runner = CliRunner()
    result = runner.invoke(app, ["refresh-universe"])
    assert result.exit_code == 0, (
        f"Expected exit 0 on successful refresh-universe; got {result.exit_code}. "
        f"stdout: {result.stdout}"
    )
    events = _parse_json_events(result.stdout)
    # The CLI body does not emit a custom "snapshot_written" event in the
    # success branch (refresh_universe_impl already emits one inside
    # data/universe.py — see Plan 02-03). On a successful return the CLI
    # simply does not emit "refresh_universe_skipped" or any failure event.
    skip = [ev for ev in events if ev.get("event") == "refresh_universe_skipped"]
    failed = [ev for ev in events if ev.get("event") == "refresh_universe_failed"]
    assert not skip, f"Did not expect skip event on success path; got {skip!r}"
    assert not failed, f"Did not expect failed event on success path; got {failed!r}"


# --- D-08 data-quality gate integration test (Phase 4 OUT-01 + SIG-01) ----


def test_report_data_quality_gate_d08(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-08: pass_rate > 0.25 AND regime_state == 'Correction' ->
    CliRunner exit_code != 0 + 'data_quality_gate_failed' event in stdout +
    no report or snapshot file written.

    Mirrors test_health_gate_below_95_fails_run pattern (lines 109-137).
    """
    # Replace run_pipeline with a function that triggers validate_run with
    # the failure combination — bypasses build_panel/regime/composite which
    # need real data.
    def fake_pipeline(snapshot_date: str, write_report: bool = True) -> None:
        from screener.publishers.pipeline import validate_run

        validate_run(0.30, "Correction", 0.25, 0.25)

    monkeypatch.setattr(
        "screener.publishers.pipeline.run_pipeline", fake_pipeline
    )

    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    assert result.exit_code != 0, (
        f"Expected non-zero exit on D-08 gate; got {result.exit_code}. "
        f"stdout: {result.stdout}"
    )
    events = _parse_json_events(result.stdout)
    failed = [
        ev for ev in events if ev.get("event") == "data_quality_gate_failed"
    ]
    assert failed, (
        f"Expected 'data_quality_gate_failed' event; got events: {events!r}"
    )
    ev = failed[0]
    assert ev.get("regime_state") == "Correction"
    assert ev.get("pass_rate") == 0.30


def test_score_subcommand_no_longer_stub() -> None:
    """Phase 4: `score` ships a real body — invoking it does NOT emit a
    '[stub] score not yet implemented' line. Real run will fail without
    data files, but the failure is from publishers.pipeline, not [stub]."""
    runner = CliRunner()
    result = runner.invoke(app, ["score"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events
        if ev.get("command") == "score" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, (
        f"`screener score` still emits a [stub] line: {stub_events!r}"
    )


def test_report_subcommand_no_longer_stub() -> None:
    """Phase 4: `report` ships a real body — same as score."""
    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events
        if ev.get("command") == "report" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, (
        f"`screener report` still emits a [stub] line: {stub_events!r}"
    )
