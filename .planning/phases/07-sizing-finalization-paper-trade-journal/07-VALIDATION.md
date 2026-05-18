---
phase: 7
slug: sizing-finalization-paper-trade-journal
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-18
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Extracted from 07-RESEARCH.md §"Validation Architecture" for Nyquist gate compliance.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already configured) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py tests/test_architecture.py tests/test_cli_smoke.py tests/test_backtest_no_lookahead.py -x --no-cov` |
| **Full suite command** | `uv run pytest --no-cov -q` |
| **Estimated runtime** | ~10s quick · ~30s full local · CI adds `--cov-fail-under=80` |

---

## Sampling Rate

- **After every task commit:** Run the quick command above (Phase 7 surface + FND-04 mutation gate + structural-lock tests, ~10s).
- **After every plan wave:** Run `uv run pytest --no-cov -q` (~30s).
- **Before `/gsd-verify-work`:** Full suite must be green; CI passes including `ruff` + `mypy --strict` on touched files.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 0 | SIZ-01, OUT-04..06 | T-07-01 | Settings additive; secrets not introduced | unit | `uv run pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --collect-only` | ❌ W0 (stubs created here) | ⬜ pending |
| 07-01-02 | 01 | 0 | SIZ-01, SIZ-05, OUT-04..06 | T-07-02 | Pandera enforces nullable sentinels; no silent dtype drift | unit | `uv run pytest tests/test_persistence_schema.py -x --no-cov` | ✅ extends existing | ⬜ pending |
| 07-01-03 | 01 | 0 | OUT-04 | T-07-03 | `.gitignore` allowlist for `data/journal.sqlite` | manual+grep | `grep -E "^!data/journal\\.sqlite$" .gitignore` | ❌ NEW | ⬜ pending |
| 07-02-01 | 02 | 1 | SIZ-01, SIZ-02, SIZ-05 | T-07-04 | Division guard on `entry==stop`; non-negative shares | unit | `uv run pytest tests/test_sizing.py::test_shares_formula tests/test_sizing.py::test_zero_regime_score_zero_shares tests/test_sizing.py::test_adr_reject_boundary tests/test_sizing.py::test_atr_zone_boundaries -x` | ❌ NEW | ⬜ pending |
| 07-02-02 | 02 | 1 | SIZ-03, SIZ-04 | T-07-05 | Per-playbook helper dispatch (no fallthrough) | unit | `uv run pytest tests/test_sizing.py::test_stop_dispatch_per_playbook tests/test_sizing.py::test_trail_label_dispatch -x` | ❌ NEW | ⬜ pending |
| 07-03-01 | 03 | 1 | OUT-04, OUT-05 | T-07-06 | SQLite `BEFORE UPDATE OF` trigger raises on decision-col mutation | unit | `uv run pytest tests/test_journal.py::test_immutability_trigger tests/test_journal.py::test_features_json_roundtrip tests/test_journal.py::test_schema_idempotent_recreates_trigger -x` | ❌ NEW | ⬜ pending |
| 07-03-02 | 03 | 1 | OUT-06 | T-07-07 | Outcome columns mutable; trigger excludes them | unit | `uv run pytest tests/test_journal.py::test_outcome_column_updatable tests/test_journal.py::test_outcome_col_not_in_trigger -x` | ❌ NEW | ⬜ pending |
| 07-04-01 | 04 | 2 | SIZ-01..05, OUT-04, OUT-05 | T-07-08 | `validate_run` runs BEFORE sizing split; snapshot retains full universe | integration | `uv run pytest tests/test_pipeline_journal.py::test_pipeline_writes_journal tests/test_pipeline_journal.py::test_rejected_picks_not_in_journal tests/test_pipeline_journal.py::test_journal_disabled -x` | ❌ NEW | ⬜ pending |
| 07-04-02 | 04 | 2 | OUT-02 | T-07-09 | Report renders trail/stop/zone fields + `## Skipped Picks` footer | unit | `uv run pytest tests/test_publishers_report.py -k "trail or stop or zone or skipped" -x` | ❌ NEW | ⬜ pending |
| 07-04-03 | 04 | 2 | SC-1 (golden) | T-07-10 | Full pipeline run; deterministic row count + features_json shape | golden | `uv run pytest tests/test_pipeline_journal.py::test_golden_pipeline_journal -x` | ❌ NEW | ⬜ pending |
| 07-05-01 | 05 | 3 | OUT-04 | T-07-11 | `journal` CLI body; `PHASE_1_STUBS == []` | unit | `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked tests/test_cli_smoke.py::test_journal_subcommand_no_longer_stub -x` | ❌ NEW + ✅ existing | ⬜ pending |
| 07-05-02 | 05 | 3 | OUT-04 | T-07-12 | Idempotent re-run inserts 0 rows | integration | `uv run pytest tests/test_journal.py::test_journal_cli_idempotent -x` | ❌ NEW | ⬜ pending |
| 07-05-03 | 05 | 3 | All | (human gate) | Operator confirms `screener report && screener journal` produces stable journal | checkpoint:human-verify | `uv run screener report --date 2026-05-15 && uv run screener journal --date 2026-05-15` (operator inspects journal row count + features_json) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sizing.py` — 11 pytest.skip stubs (SIZ-01..05) created by Plan 07-01 Task 1
- [ ] `tests/test_journal.py` — 9 pytest.skip stubs (OUT-04..06 + regression) created by Plan 07-01 Task 1
- [ ] `tests/test_pipeline_journal.py` — 5 pytest.skip stubs (integration + golden) created by Plan 07-01 Task 1
- [ ] `tests/conftest.py` — `sized_input_cross()` fixture added by Plan 07-01 Task 1
- [ ] `src/screener/sizing.py` — module exists (filled in Plan 07-02)
- [ ] `src/screener/persistence.py` — PicksSchema + `_PICKS_DDL` + `_ensure_picks_schema` + `append_picks_rows` + `read_picks_for_date` (Plan 07-03)
- [x] Framework (pytest 8.x) already installed via uv; no install needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end paper-trade journal review | SC-4, SC-5 (Phase 7) | Operator must visually confirm features_json blob matches the day's picks | `uv run screener report --date {today}` then `sqlite3 data/journal.sqlite "SELECT ticker, playbook_tag, composite_score, json_extract(features_json, '$.pattern_diagnostics.type') FROM picks WHERE snapshot_date='{today}';"` |
| `screener journal` idempotent catch-up | SC-4 | Verifies the operator's catch-up workflow after a missed cron | `uv run screener journal --date {today}` twice; second run logs `journal_idempotent_skip` with `inserted_rows=0` |
| 21d EMA numeric in report (Q4 from RESEARCH) | (UAT feedback) | Display-only preference; defer until operator sees first report | Operator inspects `Trail: 21d EMA` line in report; opens issue if numeric value is desired |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test files seeded as skip stubs in Plan 07-01)
- [x] No watch-mode flags (`-x` fail-fast; no `--lf` or `-w`)
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — set to `approved 2026-MM-DD` after Wave 0 lands and all stubs are green-or-skipped.
