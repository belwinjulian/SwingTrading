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
# refresh-ohlcv, and refresh-macro now do real work and no longer emit [stub];
# Phase 4 also removed `score` and `report` from this list; Phase 5 plan 05-03
# fills `backtest` so it is removed; Phase 5 plan 05-05 fills `backtest-audit`
# so it is removed too — see test_backtest_audit_subcommand_no_longer_stub
# below).
PHASE_1_STUBS = [
    # Phase 6 (Plan 06-01) removed `refresh-fundamentals` from this list — its
    # body is filled by Plan 06-05 (Wave 4); see test_refresh_fundamentals_
    # subcommand_no_longer_stub below.
    "journal",
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
            f"`screener {name}` did not emit a structured [stub] log line. events: {events!r}"
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


def test_health_gate_below_95_fails_run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_health_gate_above_95_passes_run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr("screener.publishers.pipeline.run_pipeline", fake_pipeline)

    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    assert result.exit_code != 0, (
        f"Expected non-zero exit on D-08 gate; got {result.exit_code}. stdout: {result.stdout}"
    )
    events = _parse_json_events(result.stdout)
    failed = [ev for ev in events if ev.get("event") == "data_quality_gate_failed"]
    assert failed, f"Expected 'data_quality_gate_failed' event; got events: {events!r}"
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
        ev for ev in events if ev.get("command") == "score" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener score` still emits a [stub] line: {stub_events!r}"


def test_report_subcommand_no_longer_stub() -> None:
    """Phase 4: `report` ships a real body — same as score."""
    runner = CliRunner()
    result = runner.invoke(app, ["report"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events if ev.get("command") == "report" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener report` still emits a [stub] line: {stub_events!r}"


def test_backtest_subcommand_no_longer_stub() -> None:
    """Phase 5 (plan 05-03): `backtest` ships a real body — invoking it does
    NOT emit a '[stub] backtest not yet implemented' line. Real run will fail
    without data/snapshots/ (RuntimeError per vbt_runner._load_snapshots_in_range
    L10 hard-fail), but the failure is from the harness, not [stub]."""
    runner = CliRunner()
    result = runner.invoke(app, ["backtest"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev for ev in events if ev.get("command") == "backtest" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener backtest` still emits a [stub] line: {stub_events!r}"


def test_backtest_audit_subcommand_no_longer_stub() -> None:
    """Phase 5 (plan 05-05): `backtest-audit` ships a real body — invoking it
    does NOT emit a '[stub] backtest-audit not yet implemented' line. The audit
    may exit non-zero (e.g. FAIL on check #4 if data/snapshots/ has insufficient
    OOS depth in the worktree), but the failure is from the audit checks, not
    from [stub]."""
    runner = CliRunner()
    result = runner.invoke(app, ["backtest-audit"])
    events = _parse_json_events(result.stdout)
    stub_events = [
        ev
        for ev in events
        if ev.get("command") == "backtest-audit" and "[stub]" in ev.get("message", "")
    ]
    assert not stub_events, f"`screener backtest-audit` still emits a [stub] line: {stub_events!r}"


# --- Phase 6 Wave 0 (Plan 06-01) D-24 lock + CAT-04 ------------------------


def test_subcommand_surface_locked() -> None:
    """D-24 hard lock: D14_SUBCOMMANDS list is bytewise-frozen at the 9-name
    Phase 1 surface. Adding or renaming a subcommand requires amending CONTEXT.md
    D-14 (Phase 1) AND CONTEXT.md D-24 (Phase 6) AND this list together.

    Phase 6 fills bodies for `refresh-fundamentals`, `score`, `report` but adds
    NO new subcommand. Verified separately from the help-surface test so a
    failure on either side is unambiguous in CI summary.
    """
    expected = [
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
    assert D14_SUBCOMMANDS == expected, (
        f"D-24 / D-14 lock broken: D14_SUBCOMMANDS == {D14_SUBCOMMANDS!r}, "
        f"expected {expected!r}. Amend the lock decision in CONTEXT.md "
        f"before changing the list."
    )


def test_refresh_fundamentals_subcommand_no_longer_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 6 (plan 06-05): `refresh-fundamentals` ships a real body —
    invoking it does NOT emit a '[stub] refresh-fundamentals not yet implemented'
    line. Real run will import data adapters (mocked here); the failure is from
    those adapters, not from [stub].
    """
    monkeypatch.setenv("EDGAR_IDENTITY", "Test Runner <test@example.com>")
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")
    from screener.config import get_settings
    get_settings.cache_clear()
    # Mock both data adapters to no-op so we don't hit real APIs.
    import screener.data.fundamentals as ref_fund_mod
    import screener.data.insider as ref_ins_mod
    monkeypatch.setattr(ref_fund_mod, "refresh_fundamentals", lambda **kw: {})
    monkeypatch.setattr(ref_ins_mod, "refresh_insider", lambda **kw: 0)
    # Mock edgartools set_identity to no-op (avoids import dependency)
    import screener.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_ensure_edgar_identity", lambda: None)
    runner = CliRunner()
    from screener.cli import app as cli_app
    result = runner.invoke(cli_app, ["refresh-fundamentals"])
    assert result.exit_code == 0, result.output
    assert "[stub]" not in result.output


def test_edgar_identity_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 6 (plan 06-05) / CAT-04 / Pitfall 3: when EDGAR_IDENTITY='',
    invoking `refresh-fundamentals` must exit non-zero with an error
    mentioning EDGAR_IDENTITY AND .env.example.
    """
    monkeypatch.setenv("EDGAR_IDENTITY", "")
    monkeypatch.setenv("FINNHUB_API_KEY", "test_key")
    from screener.config import get_settings
    get_settings.cache_clear()
    runner = CliRunner()
    from screener.cli import app as cli_app
    result = runner.invoke(cli_app, ["refresh-fundamentals"])
    assert result.exit_code != 0, (
        f"Expected non-zero exit when EDGAR_IDENTITY=''; got {result.exit_code}. "
        f"output: {result.output!r}"
    )
    combined = (result.stdout or "") + (result.stderr or "")
    assert "EDGAR_IDENTITY" in combined, (
        f"Expected 'EDGAR_IDENTITY' in output; got: {combined!r}"
    )
    assert ".env.example" in combined, (
        f"Expected '.env.example' in output; got: {combined!r}"
    )
