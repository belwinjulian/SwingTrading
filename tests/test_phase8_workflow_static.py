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

REPO_ROOT = Path(__file__).resolve().parents[1]
REFRESH_YML = REPO_ROOT / ".github" / "workflows" / "refresh.yml"
HEARTBEAT_YML = REPO_ROOT / ".github" / "workflows" / "heartbeat.yml"

# Match: "owner/repo@<40-hex-sha>  # vMAJOR.MINOR.PATCH" — the existing ci.yml
# pinning convention (lines 22 + 25). Two-space gap + `# vX.Y.Z` is required.
PINNED_HASH_RE = re.compile(r"[\w-]+/[\w-]+@[0-9a-f]{40}\s+#\s+v\d+\.\d+\.\d+")

# Required action SHAs (verified via `git ls-remote` 2026-05-19):
#   actions/checkout v4.2.2                  -> 11bd71901bbe5b1630ceea73d27597364c9af683
#   astral-sh/setup-uv v6.8.0                -> d0cc045d04ccac9d8b7881df0226f9e82c39688e
#   actions/cache v4.3.0                     -> 0057852bfaa89a56745cba8c7296529d2fc39830
#   stefanzweifel/git-auto-commit-action v5.2.0 -> b863ae1933cb653a53c021fe36dbb774e1fb9403


# === refresh.yml assertions (filled by Plan 08-06) ===


def test_refresh_workflow_exists_and_yaml_valid() -> None:
    """OPS-01: .github/workflows/refresh.yml exists and parses as valid YAML."""
    import yaml

    assert REFRESH_YML.exists(), f"missing file: {REFRESH_YML}"
    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"YAML root is not a mapping: {type(data)!r}"
    assert data.get("name") == "refresh", f"name != 'refresh': {data.get('name')!r}"


def test_refresh_cron_schedule() -> None:
    """OPS-01: refresh.yml schedules on cron '30 22 * * 1-5' (UTC, weekdays)."""
    import yaml

    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    # PyYAML parses bareword `on:` as boolean True.
    on_block = data.get(True, data.get("on"))
    assert isinstance(on_block, dict), f"`on:` block missing: {on_block!r}"
    schedule = on_block.get("schedule", [])
    crons = [entry.get("cron") for entry in schedule if isinstance(entry, dict)]
    assert "30 22 * * 1-5" in crons, (
        f"refresh.yml cron must be '30 22 * * 1-5' (OPS-01); got {crons!r}"
    )


def test_refresh_has_workflow_dispatch() -> None:
    """OPS-04: refresh.yml has `workflow_dispatch:` for manual re-runs."""
    import yaml

    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    on_block = data.get(True, data.get("on"))
    assert isinstance(on_block, dict), f"`on:` block missing: {on_block!r}"
    assert "workflow_dispatch" in on_block, (
        f"refresh.yml must declare workflow_dispatch (OPS-04); on: keys = {list(on_block.keys())!r}"
    )


def test_refresh_workflow_pins_actions_by_sha() -> None:
    """OPS-02 / T-08-supply-chain: every `uses:` in refresh.yml pins a 40-char
    commit SHA with a `# vX.Y.Z` trailing comment. Asserts the four required
    pins (checkout v4.2.2, setup-uv v6.8.0, cache v4.3.0, git-auto-commit v5.2.0)
    are present."""
    text = REFRESH_YML.read_text(encoding="utf-8")
    pins = PINNED_HASH_RE.findall(text)
    # checkout(1) + setup-uv(1) + cache(1) + git-auto-commit(2 — success + failure)
    assert len(pins) >= 5, (
        f"refresh.yml must pin at least 5 action references by SHA; got {len(pins)}: {pins!r}"
    )
    required = {
        "11bd71901bbe5b1630ceea73d27597364c9af683": "actions/checkout v4.2.2",
        "d0cc045d04ccac9d8b7881df0226f9e82c39688e": "astral-sh/setup-uv v6.8.0",
        "0057852bfaa89a56745cba8c7296529d2fc39830": "actions/cache v4.3.0",
        "b863ae1933cb653a53c021fe36dbb774e1fb9403": "stefanzweifel/git-auto-commit-action v5.2.0",
    }
    for sha, name in required.items():
        assert sha in text, f"refresh.yml missing required SHA pin for {name}: {sha!r}"


def test_refresh_permissions_contents_write() -> None:
    """T-08-overscope-perms / D-09: refresh.yml declares
    `permissions: contents: write` at workflow level (not job level), no
    additional scopes."""
    import yaml

    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    perms = data.get("permissions")
    assert isinstance(perms, dict), f"permissions block missing or wrong shape: {perms!r}"
    assert perms.get("contents") == "write", (
        f"refresh.yml permissions.contents must be 'write' (D-09); got {perms!r}"
    )
    # Defense: no extra over-scoped permissions slipped in.
    assert set(perms.keys()) <= {"contents"}, (
        f"refresh.yml has unexpected extra permission scopes: {set(perms.keys())!r}; "
        f"only 'contents: write' should be present"
    )


def test_refresh_timeout_120_minutes() -> None:
    """D-07: refresh.yml job sets `timeout-minutes: 120`."""
    import yaml

    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    job = data.get("jobs", {}).get("refresh", {})
    assert job.get("timeout-minutes") == 120, (
        f"refresh job timeout-minutes must be 120 (D-07 cold-cache headroom); "
        f"got {job.get('timeout-minutes')!r}"
    )


def test_refresh_cancel_in_progress_false() -> None:
    """Pitfall #3: refresh.yml concurrency block has `cancel-in-progress: false`
    (long cold-cache runs must not be killed by manual workflow_dispatch)."""
    import yaml

    data = yaml.safe_load(REFRESH_YML.read_text(encoding="utf-8"))
    concurrency = data.get("concurrency", {})
    assert isinstance(concurrency, dict), f"concurrency block missing: {concurrency!r}"
    assert concurrency.get("cancel-in-progress") is False, (
        f"refresh.yml concurrency.cancel-in-progress must be False (Pitfall #3); "
        f"got {concurrency!r}"
    )


def test_refresh_no_github_event_interpolation_in_run_blocks() -> None:
    """T-08-script-injection: NO `${{ github.event.* }}` interpolation in
    `run:` blocks (would be a code-injection vector). Only safe contexts
    permitted: ${{ runner.os }}, ${{ secrets.* }}, ${{ github.run_number }},
    ${{ steps.*.outputs.* }}."""
    text = REFRESH_YML.read_text(encoding="utf-8")
    import re

    # Find every interpolation expression in the file.
    interpolations = re.findall(r"\$\{\{\s*([^}]+?)\s*\}\}", text)
    forbidden = [
        expr
        for expr in interpolations
        if "github.event." in expr or expr.strip().startswith("github.event")
    ]
    assert not forbidden, (
        f"refresh.yml contains forbidden `${{{{ github.event.* }}}}` interpolation "
        f"(T-08-script-injection vector): {forbidden!r}"
    )


def test_refresh_two_step_commit_pattern() -> None:
    """OPS-02 + D-05: refresh.yml has TWO git-auto-commit steps with mutually
    exclusive guards — `if: success()` for full artifact commit, `if: failure()`
    for runs.jsonl-only failure commit. Defense-in-depth: walks parsed YAML
    steps and asserts exactly one auto-commit step is guarded by `success()`
    and exactly one by `failure()` (W-04 from gsd-plan-checker — replaces the
    earlier SHA-count heuristic with a structural assertion)."""
    import yaml

    text = REFRESH_YML.read_text(encoding="utf-8")
    # Coarse SHA-count guard (cheap, catches obvious regressions).
    sha_count = text.count("b863ae1933cb653a53c021fe36dbb774e1fb9403")
    assert sha_count == 2, (
        f"refresh.yml must have exactly 2 stefanzweifel/git-auto-commit-action SHA pins "
        f"(success + failure); got {sha_count}"
    )
    # Structural assertion: walk every step, count auto-commit steps by `if:` guard.
    data = yaml.safe_load(text)
    AUTO_COMMIT_SHA = (
        "stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403"
    )
    success_steps = []
    failure_steps = []
    for job_name, job in data.get("jobs", {}).items():
        for step in job.get("steps", []) or []:
            uses = step.get("uses", "") or ""
            if AUTO_COMMIT_SHA in uses:
                guard = step.get("if", "") or ""
                if "success()" in guard:
                    success_steps.append((job_name, step.get("name", "?")))
                elif "failure()" in guard:
                    failure_steps.append((job_name, step.get("name", "?")))
    assert len(success_steps) == 1, (
        f"expected exactly 1 auto-commit step guarded by `if: success()`; "
        f"got {len(success_steps)}: {success_steps!r}"
    )
    assert len(failure_steps) == 1, (
        f"expected exactly 1 auto-commit step guarded by `if: failure()`; "
        f"got {len(failure_steps)}: {failure_steps!r}"
    )
    # Sanity belt-and-suspenders: text-level checks still hold.
    assert "if: success()" in text, (
        "refresh.yml missing explicit `if: success()` guard on success-path commit "
        "(Pitfall #2 — be explicit even though it's the default)"
    )
    assert text.count("if: failure()") >= 2, (
        f"refresh.yml needs `if: failure()` on BOTH write-record + failure-commit steps; "
        f"got {text.count('if: failure()')} occurrences"
    )


def test_refresh_file_pattern_includes_reports_and_runs_jsonl() -> None:
    """OPS-02: the success-path commit's `file_pattern` includes
    `data/runs.jsonl`, `data/snapshots/`, `data/universe/`, `data/journal.sqlite`,
    `data/ohlcv/**/splits.parquet`, and `reports/`. The failure-path commit's
    `file_pattern` is `data/runs.jsonl` ONLY."""
    text = REFRESH_YML.read_text(encoding="utf-8")
    required_paths_success_path = [
        "data/runs.jsonl",
        "data/snapshots/",
        "data/universe/",
        "data/journal.sqlite",
        "data/ohlcv/**/splits.parquet",
        "reports/",
    ]
    for path in required_paths_success_path:
        assert path in text, (
            f"refresh.yml success file_pattern missing {path!r} "
            f"(OPS-02); see RESEARCH §Implementation Approach refresh.yml skeleton"
        )
    # Failure path commits ONLY data/runs.jsonl — the trailing
    # `file_pattern: data/runs.jsonl` must appear (the success path has it
    # in a multi-line block, the failure path inlines it).
    assert "file_pattern: data/runs.jsonl" in text, (
        "refresh.yml failure-path commit must declare `file_pattern: data/runs.jsonl` "
        "(D-05: failure path commits ONLY runs.jsonl, no partial artifacts)"
    )


# === heartbeat.yml assertions (filled by Plan 08-04) ===


def test_heartbeat_workflow_exists_and_yaml_valid() -> None:
    """OPS-03: .github/workflows/heartbeat.yml exists and parses as valid YAML."""
    import yaml  # transitive dep via pandera/structlog stack

    assert HEARTBEAT_YML.exists(), f"missing file: {HEARTBEAT_YML}"
    data = yaml.safe_load(HEARTBEAT_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"YAML root is not a mapping: {type(data)!r}"
    assert data.get("name") == "heartbeat", f"name != 'heartbeat': {data.get('name')!r}"


def test_heartbeat_cron_schedule() -> None:
    """OPS-03 / D-11: heartbeat.yml schedules on cron '0 9 * * 1' (Monday 09:00 UTC)."""
    import yaml

    data = yaml.safe_load(HEARTBEAT_YML.read_text(encoding="utf-8"))
    # PyYAML parses bareword `on:` as boolean True (the "Norway problem" cousin).
    # Look up by both keys for compatibility across yaml dialects.
    on_block = data.get(True, data.get("on"))
    assert isinstance(on_block, dict), f"`on:` block missing or wrong shape: {on_block!r}"
    schedule = on_block.get("schedule", [])
    crons = [entry.get("cron") for entry in schedule if isinstance(entry, dict)]
    assert "0 9 * * 1" in crons, (
        f"heartbeat.yml cron must be '0 9 * * 1' (Monday 09:00 UTC per D-11); got {crons!r}"
    )


def test_heartbeat_permissions_contents_write() -> None:
    """Pitfall #8 + T-08-overscope-perms: heartbeat.yml MUST use
    `permissions: contents: write` to commit data/heartbeat.txt AND MUST NOT
    declare any other scopes. NOTE: deviates from CONTEXT D-09 which says
    `contents: read` — D-09 is a slip; heartbeat cannot commit without write."""
    import yaml

    data = yaml.safe_load(HEARTBEAT_YML.read_text(encoding="utf-8"))
    perms = data.get("permissions")
    assert isinstance(perms, dict), f"permissions block missing or wrong shape: {perms!r}"
    assert perms.get("contents") == "write", (
        f"heartbeat permissions.contents must be 'write' (Pitfall #8 / Open Question A); "
        f"got {perms!r}"
    )
    # T-08-overscope-perms regression guard: no other scopes may be granted
    # (no pull-requests:, no issues:, no packages:, no id-token:).
    assert set(perms.keys()) <= {"contents"}, (
        f"heartbeat.yml has unexpected extra permission scopes: {set(perms.keys())!r}; "
        f"only 'contents: write' should be present (T-08-overscope-perms regression guard)"
    )


def test_heartbeat_workflow_pins_actions_by_sha() -> None:
    """OPS-03 / T-08-supply-chain: heartbeat.yml pins actions/checkout v4.2.2
    + stefanzweifel/git-auto-commit-action v5.2.0 by 40-char commit SHA with
    `# vX.Y.Z` trailing comment."""
    text = HEARTBEAT_YML.read_text(encoding="utf-8")
    pins = PINNED_HASH_RE.findall(text)
    assert len(pins) >= 2, (
        f"heartbeat.yml must pin at least 2 actions by 40-char SHA; matched {len(pins)}: {pins!r}"
    )
    # Required exact SHAs (verified via `git ls-remote` 2026-05-19):
    assert "11bd71901bbe5b1630ceea73d27597364c9af683" in text, (
        "heartbeat.yml missing actions/checkout v4.2.2 SHA "
        "(11bd71901bbe5b1630ceea73d27597364c9af683)"
    )
    assert "b863ae1933cb653a53c021fe36dbb774e1fb9403" in text, (
        "heartbeat.yml missing stefanzweifel/git-auto-commit-action v5.2.0 SHA "
        "(b863ae1933cb653a53c021fe36dbb774e1fb9403)"
    )


def test_heartbeat_writes_data_heartbeat_txt() -> None:
    """OPS-03 / D-11: heartbeat.yml writes an ISO timestamp to
    `data/heartbeat.txt` (the file_pattern in the auto-commit step matches
    this path)."""
    text = HEARTBEAT_YML.read_text(encoding="utf-8")
    assert "data/heartbeat.txt" in text, (
        f"heartbeat.yml must reference data/heartbeat.txt at least once; file contents: {text!r}"
    )
    # Specifically, the auto-commit file_pattern must target it.
    assert "file_pattern: data/heartbeat.txt" in text, (
        "heartbeat.yml auto-commit step must declare `file_pattern: data/heartbeat.txt`"
    )


def test_heartbeat_no_github_event_interpolation_in_run_blocks() -> None:
    """T-08-script-injection: no untrusted `${{ github.event.* }}` context in
    heartbeat.yml `run:` blocks. Walks every step's `run:` body via parsed
    YAML — stronger than the one-shot grep in Plan 08-04 Task 1 verify,
    because it gates every future heartbeat.yml edit at pytest time."""
    import yaml

    text = HEARTBEAT_YML.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    for job_name, job in data.get("jobs", {}).items():
        for step in job.get("steps", []) or []:
            run_block = step.get("run", "") or ""
            assert "${{ github.event" not in run_block, (
                f"heartbeat.yml job '{job_name}' step '{step.get('name', '?')}' "
                f"interpolates `${{{{ github.event.* }}}}` in a run: block "
                f"(T-08-script-injection regression). run: contents: {run_block!r}"
            )


def test_heartbeat_no_set_x() -> None:
    """T-08-secrets: `set -x` in any heartbeat.yml `run:` block would echo
    every command (and any expanded environment such as GITHUB_TOKEN) to the
    workflow log BEFORE GitHub's secret-masking pre-mask window closes.
    `set -e` is allowed (and required for chain-abort semantics)."""
    import yaml

    text = HEARTBEAT_YML.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    for job_name, job in data.get("jobs", {}).items():
        for step in job.get("steps", []) or []:
            run_block = step.get("run", "") or ""
            # `set -e` is allowed; `set -x` is not. Matching as a bare token
            # avoids false positives on e.g. `set -eu` or `set -euxo` (also
            # forbidden because they include -x — explicit substring match).
            assert "set -x" not in run_block, (
                f"heartbeat.yml job '{job_name}' step '{step.get('name', '?')}' "
                f"uses `set -x` — secret-leak risk (T-08-secrets). "
                f"run: contents: {run_block!r}"
            )
