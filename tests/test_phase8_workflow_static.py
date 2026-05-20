"""GitHub Actions workflow static-assertion tests — OPS-01 / OPS-02 / OPS-03 /
OPS-04 + threat-model T-08-{secrets,script-injection,supply-chain,
overscope-perms,commit-loop}.

Plan 08-04 (Wave 1) fills heartbeat.yml assertions; Plan 08-06 (Wave 3) fills
refresh.yml assertions. Tests parse YAML via pyyaml (transitive dep through
pandera + structlog) and assert structural properties:
  - cron schedules (OPS-01, OPS-03)
  - workflow_dispatch present on refresh.yml (OPS-04)
  - actions pinned by 40-char commit SHA (OPS-02 / T-08-supply-chain)
  - permissions scoped correctly (T-08-overscope-perms)
  - NO ${{ github.event.* }} interpolation in run: blocks (T-08-script-injection)
  - two-step commit pattern (success path + failure path) on refresh.yml
  - heartbeat writes data/heartbeat.txt (OPS-03)

No network. Pure file-system parse.
"""

# Wave: 0  (named-stub skeletons; bodies filled by Plans 08-04 + 08-06 — see 08-VALIDATION.md)

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REFRESH_YML = REPO_ROOT / ".github" / "workflows" / "refresh.yml"
HEARTBEAT_YML = REPO_ROOT / ".github" / "workflows" / "heartbeat.yml"

# Match: "owner/repo@<40-hex-sha>  # vMAJOR.MINOR.PATCH" — the existing ci.yml
# pinning convention (lines 22 + 25). Two-space gap + `# vX.Y.Z` is required.
PINNED_HASH_RE = re.compile(
    r"[\w-]+/[\w-]+@[0-9a-f]{40}\s+#\s+v\d+\.\d+\.\d+"
)

# Required action SHAs (verified via `git ls-remote` 2026-05-19):
#   actions/checkout v4.2.2                  -> 11bd71901bbe5b1630ceea73d27597364c9af683
#   astral-sh/setup-uv v6.8.0                -> d0cc045d04ccac9d8b7881df0226f9e82c39688e
#   actions/cache v4.3.0                     -> 0057852bfaa89a56745cba8c7296529d2fc39830
#   stefanzweifel/git-auto-commit-action v5.2.0 -> b863ae1933cb653a53c021fe36dbb774e1fb9403


# === refresh.yml assertions (filled by Plan 08-06) ===

def test_refresh_workflow_exists_and_yaml_valid() -> None:
    """OPS-01: .github/workflows/refresh.yml exists and parses as valid YAML."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_cron_schedule() -> None:
    """OPS-01: refresh.yml schedules on cron '30 22 * * 1-5' (UTC, weekdays)."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_has_workflow_dispatch() -> None:
    """OPS-04: refresh.yml has `workflow_dispatch:` for manual re-runs."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_workflow_pins_actions_by_sha() -> None:
    """OPS-02 / T-08-supply-chain: every `uses:` in refresh.yml pins a 40-char
    commit SHA with a `# vX.Y.Z` trailing comment. Asserts the four required
    pins (checkout v4.2.2, setup-uv v6.8.0, cache v4.3.0, git-auto-commit v5.2.0)
    are present."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_permissions_contents_write() -> None:
    """T-08-overscope-perms / D-09: refresh.yml declares
    `permissions: contents: write` at workflow level (not job level), no
    additional scopes."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_timeout_120_minutes() -> None:
    """D-07: refresh.yml job sets `timeout-minutes: 120`."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_cancel_in_progress_false() -> None:
    """Pitfall #3: refresh.yml concurrency block has `cancel-in-progress: false`
    (long cold-cache runs must not be killed by manual workflow_dispatch)."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_no_github_event_interpolation_in_run_blocks() -> None:
    """T-08-script-injection: NO `${{ github.event.* }}` interpolation in
    `run:` blocks (would be a code-injection vector). Only safe contexts
    permitted: ${{ runner.os }}, ${{ secrets.* }}, ${{ github.run_number }},
    ${{ steps.*.outputs.* }}."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_two_step_commit_pattern() -> None:
    """OPS-02 + D-05: refresh.yml has TWO git-auto-commit steps with mutually
    exclusive guards — `if: success()` for full artifact commit, `if: failure()`
    for runs.jsonl-only failure commit."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


def test_refresh_file_pattern_includes_reports_and_runs_jsonl() -> None:
    """OPS-02: the success-path commit's `file_pattern` includes
    `data/runs.jsonl`, `data/snapshots/`, `data/universe/`, `data/journal.sqlite`,
    `data/ohlcv/**/splits.parquet`, and `reports/`. The failure-path commit's
    `file_pattern` is `data/runs.jsonl` ONLY."""
    pytest.skip("body filled by Plan 08-06 (Wave 3)")


# === heartbeat.yml assertions (filled by Plan 08-04) ===

def test_heartbeat_workflow_exists_and_yaml_valid() -> None:
    """OPS-03: .github/workflows/heartbeat.yml exists and parses as valid YAML."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_cron_schedule() -> None:
    """OPS-03 / D-11: heartbeat.yml schedules on cron '0 9 * * 1' (Monday 09:00 UTC)."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_permissions_contents_write() -> None:
    """Pitfall #8: heartbeat.yml MUST use `permissions: contents: write` to
    commit data/heartbeat.txt. NOTE: deviates from CONTEXT D-09 which says
    `contents: read` — D-09 is a slip; heartbeat cannot commit without write.
    This deviation is documented in the plan's must_haves.truths."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_workflow_pins_actions_by_sha() -> None:
    """OPS-03 / T-08-supply-chain: heartbeat.yml pins actions/checkout v4.2.2
    + stefanzweifel/git-auto-commit-action v5.2.0 by 40-char commit SHA with
    `# vX.Y.Z` trailing comment."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_writes_data_heartbeat_txt() -> None:
    """OPS-03 / D-11: heartbeat.yml writes an ISO timestamp to
    `data/heartbeat.txt` (the file_pattern in the auto-commit step matches
    this path)."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_no_github_event_interpolation_in_run_blocks() -> None:
    """T-08-script-injection: NO `${{ github.event.* }}` interpolation in
    heartbeat.yml `run:` blocks. Regression guard so a future edit that
    inlines `${{ github.event.* }}` into a run: block is caught by pytest,
    not only by the one-shot grep in Plan 08-04 Task 1's verify command."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")


def test_heartbeat_no_set_x() -> None:
    """T-08-secrets: NO `set -x` in any heartbeat.yml `run:` block.
    `set -x` would echo every command (and its expanded environment) to the
    workflow log, defeating GitHub's secret-masking pre-mask window. `set -e`
    is allowed and required for chain-abort semantics."""
    pytest.skip("body filled by Plan 08-04 (Wave 1)")
