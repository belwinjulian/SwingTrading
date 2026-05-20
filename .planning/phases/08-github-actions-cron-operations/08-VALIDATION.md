---
phase: 8
slug: github-actions-cron-operations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md §Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run pytest tests/test_run_log.py tests/test_phase8_gitignore.py tests/test_phase8_workflow_static.py -v` |
| **Full suite command** | `uv run pytest -m "not slow" -v` (matches ci.yml) |
| **Estimated runtime** | Quick: ~5s · Full: ~30s |

---

## Sampling Rate

- **After every task commit:** Run quick command (Phase 8 unit tests — ~5s)
- **After every plan wave:** Run full suite (`uv run pytest -m "not slow" -v`)
- **Before `/gsd-verify-work`:** Full suite green PLUS checkpoint:human-verify task to manually trigger `refresh.yml` via Actions tab `workflow_dispatch` post-merge
- **Max feedback latency:** 30s (full suite) · 5s (quick)

---

## Per-Task Verification Map

> Filled by planner; this table seeds the structure. Task IDs follow `08-{plan}-{task}` once PLAN.md files exist.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | run-log | 0 | OPS-05 | T-08-secrets | Run log never echoes secrets; fsync after each append | unit | `uv run pytest tests/test_run_log.py::test_append_record_writes_valid_jsonl_with_fsync` | ❌ W0 | ⬜ pending |
| TBD | run-log | 0 | OPS-05 SC#5 | — | Failure path writes `status: "failed"` with `error_reason` | unit | `uv run pytest tests/test_run_log.py::test_cli_failure_entry_writes_failure_record` | ❌ W0 | ⬜ pending |
| TBD | gitignore | 0 | OPS-05 / OPS-02 | — | `data/runs.jsonl` not ignored | unit | `uv run pytest tests/test_phase8_gitignore.py::test_runs_jsonl_not_ignored` | ❌ W0 | ⬜ pending |
| TBD | gitignore | 0 | OPS-03 | — | `data/heartbeat.txt` not ignored | unit | `uv run pytest tests/test_phase8_gitignore.py::test_heartbeat_txt_not_ignored` | ❌ W0 | ⬜ pending |
| TBD | gitignore | 0 | OPS-02 | — | `reports/*.md` not ignored (carve-out fixes silent block) | unit | `uv run pytest tests/test_phase8_gitignore.py::test_reports_md_not_ignored` | ❌ W0 | ⬜ pending |
| TBD | refresh.yml | 1 | OPS-01 | T-08-script-injection | refresh.yml schedules cron `30 22 * * 1-5` UTC | static | `uv run pytest tests/test_phase8_workflow_static.py::test_refresh_cron_schedule` | ❌ W0 | ⬜ pending |
| TBD | refresh.yml | 1 | OPS-02 | T-08-supply-chain | Auto-commit action pinned by 40-char SHA | static | `uv run pytest tests/test_phase8_workflow_static.py::test_refresh_workflow_pins_actions` | ❌ W0 | ⬜ pending |
| TBD | refresh.yml | 1 | OPS-04 | — | `workflow_dispatch` trigger present | static | `uv run pytest tests/test_phase8_workflow_static.py::test_refresh_has_workflow_dispatch` | ❌ W0 | ⬜ pending |
| TBD | heartbeat.yml | 1 | OPS-03 | T-08-supply-chain | heartbeat.yml exists with cron + auto-commit | static | `uv run pytest tests/test_phase8_workflow_static.py::test_heartbeat_workflow_exists_and_pinned` | ❌ W0 | ⬜ pending |
| TBD | pipeline-hook | 2 | OPS-05 | — | `run_pipeline()` writes a record to `data/runs.jsonl` | integration | `uv run pytest tests/test_pipeline_emits_run_log.py` | ❌ W0 | ⬜ pending |
| TBD | regression | — | FND-04 | — | No-lookahead test still green | unit (existing) | `uv run pytest tests/test_backtest_no_lookahead.py` | ✅ exists | ⬜ pending |
| TBD | regression | — | D-06 (D-24 lock) | — | CLI surface remains 9 subcommands | unit (existing) | `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_run_log.py` — covers OPS-05 schema, fsync, success vs failure records (new file)
- [ ] `tests/test_phase8_gitignore.py` — asserts gitignore carve-outs via `git check-ignore -v <path>` exit-code 1 (new file)
- [ ] `tests/test_phase8_workflow_static.py` — parses YAML files via `pyyaml`, asserts pinned action SHAs, cron schedules, conditional structure (new file)
- [ ] `tests/test_pipeline_emits_run_log.py` — integration test that `run_pipeline()` writes a JSONL record to `tmp_path` (new file)
- [ ] `src/screener/publishers/run_log.py` — the writer module (new file; D-06 locks this NOT being a 10th typer subcommand)
- [ ] No new fixtures needed — use `tmp_path` + `monkeypatch` on the module's `_RUNS_PATH` constant

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nightly cron actually fires at `30 22 * * 1-5` UTC | OPS-01 | GitHub Actions cron behavior cannot be unit-tested; depends on GitHub's scheduler | After merge to `main`, wait for first scheduled run OR trigger via `workflow_dispatch` from Actions tab. Confirm job appears in Actions history. |
| Heartbeat keeps cron alive past 60 days | OPS-03 | Real-world time-based behavior | Track in calendar: confirm nightly is still firing on day 70 after last meaningful repo activity. |
| Auto-commit pushes artifacts without breaking `main` branch protection | OPS-02 | Depends on repo branch-protection config (unknown at planning time) | First manual `workflow_dispatch` run: confirm commit lands on `main` and ci.yml runs green on it. |
| Failure path surfaces in Actions Summary tab | OPS-05 SC#5 | Requires forcing a real failure | Manually trigger `workflow_dispatch` after introducing a temporary low coverage threshold; confirm summary tab shows the failure record. (Revert after test.) |
| GitHub Secrets `FINNHUB_API_KEY` + `EDGAR_IDENTITY` are configured in repo Settings | OPS-01 (precondition) | Cannot be asserted from a unit test | Verify `gh secret list` shows both secrets present before first scheduled run. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (5 new files listed above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (full) / < 5s (quick)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner fills task IDs)

**Approval:** pending — planner fills task IDs, then orchestrator flips `nyquist_compliant: true`.
