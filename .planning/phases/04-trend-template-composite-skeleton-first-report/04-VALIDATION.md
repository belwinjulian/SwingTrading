---
phase: 4
slug: trend-template-composite-skeleton-first-report
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-10
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> Detailed validation architecture is in `04-RESEARCH.md` §11. This file is the
> Nyquist sampling contract used by execute-phase / verify-work.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis 6.x (already installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (slow / integration markers; pytest-cov gate ≥80% on `src/screener/signals` and `src/screener/indicators`) |
| **Quick run command** | `pytest -m "not slow and not integration" -x` |
| **Full suite command** | `pytest` (CI runs `pytest -m "not slow" -v`) |
| **Estimated runtime** | ~12s full suite (Phase 3 baseline); ~3s focused signals/publishers slice |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_signals_minervini.py tests/test_signals_composite.py tests/test_publishers_pipeline.py -x`
- **After every plan wave:** Run `pytest -m "not slow"`
- **Before `/gsd-verify-work`:** `pytest && uv run mypy src/screener/indicators/ src/screener/signals/ && uv run ruff check && uv run python scripts/check_preregistration.py` — all green
- **Max feedback latency:** 12 seconds

---

## Per-Task Verification Map

> Authoritative source is the per-plan PLAN.md `<task>` blocks. This table is the cross-cutting Nyquist map; the planner fills in concrete Plan/Task IDs in the gsd-planner step. Until plans land, this is the requirement-keyed index.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| FND-05 | Preregistration script catches weight mismatch | unit | `pytest tests/test_preregistration_check.py -x` | ❌ Wave 0 | ⬜ pending |
| FND-05 | CI runs preregistration step on every PR | integration (CI YAML inspection) | `grep -q 'check_preregistration' .github/workflows/ci.yml` | covered by ci.yml edit | ⬜ pending |
| SIG-01 | All 8 conditions evaluate correctly on synthetic ticker | unit | `pytest tests/test_signals_minervini.py -k test_eight_conditions -x` | ❌ Wave 0 | ⬜ pending |
| SIG-01 | trend_template_score is 0–8 Int64 | unit | `pytest tests/test_signals_minervini.py -k test_score_dtype_and_range -x` | ❌ Wave 0 | ⬜ pending |
| SIG-01 | Tickers with insufficient history fail without exception (NaN-safe) | unit | `pytest tests/test_signals_minervini.py -k test_short_history_safe -x` | ❌ Wave 0 | ⬜ pending |
| SIG-01 | Pass rate on synthetic universe is in expected sanity range | unit (smoke) | `pytest tests/test_signals_minervini.py -k test_pass_rate_smoke -x` | ❌ Wave 0 | ⬜ pending |
| SIG-01 | EMA-grep CI gate still passes after adding minervini.py | CI step (already exists) | covered by `.github/workflows/ci.yml` SMA-not-EMA gate | covered | ⬜ pending |
| SIG-04 | Composite scorer rejects unknown weight keys | unit | `pytest tests/test_signals_composite.py -k test_unknown_weight_key_raises -x` | ❌ Wave 0 | ⬜ pending |
| SIG-04 | Composite scorer requires weights to sum to 1.0 | unit | `pytest tests/test_signals_composite.py -k test_weight_sum_assertion -x` | ❌ Wave 0 | ⬜ pending |
| SIG-04 | composite_score in [0, 100] post regime gate | property test (hypothesis) | `pytest tests/test_signals_composite.py -k test_score_range_property -x` | ❌ Wave 0 | ⬜ pending |
| SIG-04 | Phase-4-zeroed components contribute 0 to score | unit | `pytest tests/test_signals_composite.py -k test_zeroed_components -x` | ❌ Wave 0 | ⬜ pending |
| SIG-04 | M2 extension seam — adding `ml_probability` key works | unit | `pytest tests/test_signals_composite.py -k test_extension_seam -x` | ❌ Wave 0 | ⬜ pending |
| SIG-04 | Soft regime gate multiplies composite_score | unit | `pytest tests/test_publishers_pipeline.py -k test_soft_regime_gate -x` | ❌ Wave 0 | ⬜ pending |
| OUT-01 | `make report` produces a Markdown file at expected path | integration | `pytest tests/test_publishers_report.py -k test_report_file_written -x` | ❌ Wave 0 | ⬜ pending |
| OUT-01 | Report contains regime banner + top-N + per-pick + footer sections | unit (string match) | `pytest tests/test_publishers_report.py -k test_report_sections_present -x` | ❌ Wave 0 | ⬜ pending |
| OUT-02 | Per-pick block contains 6-component breakdown with placeholders | unit | `pytest tests/test_publishers_report.py -k test_per_pick_breakdown_format -x` | ❌ Wave 0 | ⬜ pending |
| OUT-02 | pivot_zone shows "in-zone" / "chase, skip" / "unknown" (3rd state for NaN ATR / high_52w — see Pitfall 5 in RESEARCH §13) | unit | `pytest tests/test_publishers_report.py -k test_pivot_zone_labels -x` | ❌ Wave 0 | ⬜ pending |
| OUT-03 | Snapshot Parquet written at expected path with required columns | integration | `pytest tests/test_publishers_snapshot.py -k test_snapshot_written_atomic -x` | ❌ Wave 0 | ⬜ pending |
| OUT-03 | RankingSnapshotSchema validates well-formed snapshot | unit | `pytest tests/test_persistence.py -k test_ranking_snapshot_schema -x` | extend existing | ⬜ pending |
| OUT-03 | Snapshot rejects malformed frame (missing column) | unit | `pytest tests/test_persistence.py -k test_ranking_snapshot_rejects_bad_shape -x` | extend existing | ⬜ pending |
| D-07 | Pass rate > 0.25 emits structlog warning | unit | `pytest tests/test_publishers_pipeline.py -k test_pass_rate_warns -x` | ❌ Wave 0 | ⬜ pending |
| D-08 | Pass rate > 0.25 AND Correction → exit 1, no report, no snapshot | integration (CliRunner) | `pytest tests/test_cli_smoke.py -k test_report_data_quality_gate -x` | extend existing | ⬜ pending |
| Architecture | `signals/composite.py` only imports allowed peers | architecture | covered by `tests/test_architecture.py` | covered | ⬜ pending |
| Architecture | `publishers/report.py` only imports allowed peers | architecture | covered by `tests/test_architecture.py` | covered | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_signals_minervini.py` — 4 tests for SIG-01 (8-condition behavior, score dtype, short-history NaN-safety, pass-rate smoke)
- [ ] `tests/test_signals_composite.py` — 5 tests for SIG-04 (unknown key, sum assertion, range property, zeroed components, extension seam)
- [ ] `tests/test_publishers_pipeline.py` — 3 tests (soft regime gate, pass-rate warning, data-quality hard fail at unit level)
- [ ] `tests/test_publishers_report.py` — 4 tests for OUT-01/02 (file written, sections present, per-pick format, pivot-zone labels)
- [ ] `tests/test_publishers_snapshot.py` — 2 tests for OUT-03 (atomic write integration; full-pipeline snapshot)
- [ ] `tests/test_preregistration_check.py` — 3 tests for FND-05 (matching weights pass, mismatched fail with formatted message, missing weight in doc fails)
- [ ] `tests/test_cli_smoke.py` — extend with 1 integration test for D-08 hard fail
- [ ] `tests/test_persistence.py` — extend with 2 tests for `RankingSnapshotSchema` + `write_snapshot_atomic`
- [ ] `tests/conftest.py` — add fixtures: `synthetic_panel_for_trend_template` (with high_52w/low_52w columns), `synthetic_scored_panel` (post-composite, for publisher tests), `synthetic_high_pass_rate_panel` (for D-08 trigger)
- [ ] Framework install: NONE — pytest already installed; fixtures pattern already exists.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual review of `reports/YYYY-MM-DD.md` rendered Markdown (table widths, regime banner readability, per-pick block scanability) | OUT-01, OUT-02 | Markdown rendering across editors/GitHub is subjective; automated tests assert structure/strings, not aesthetic | After first `make report`: open the produced file in VS Code preview AND in GitHub web view; confirm table fits, regime banner stands out, per-pick blocks are scannable |
| `Frozen at commit: <sha>` line in `docs/strategy_v1_preregistration.md` is the actual commit that froze the weights | FND-05 (D-10) | The hash is set in the same commit; pre-commit hooks can't compute their own hash | After running the freeze script: `git log -1 --format=%H docs/strategy_v1_preregistration.md` and `grep "Frozen at commit:" docs/strategy_v1_preregistration.md` agree |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner must wire each task to a row above)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all ❌ Wave 0 references above
- [ ] No watch-mode flags (CI uses `pytest -m "not slow" -v`, not `pytest --watch`)
- [ ] Feedback latency < 12s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner maps every task to a verification row)

**Approval:** pending
