"""gitignore carve-out tests — OPS-02 / OPS-05 / CONTEXT D-04 / CONTEXT D-11.

Plan 08-02 (Wave 1) fills these test bodies. They run `git check-ignore -q
<path>` as a subprocess and assert exit code 1 (= NOT ignored) for the
files Phase 8 needs to commit:
  - data/runs.jsonl   (D-04: relocated from /runs.jsonl)
  - data/heartbeat.txt (D-11)
  - reports/*.md       (Pitfall #4 fix: /reports/ was silently blocking OPS-02)

Also asserts the OLD `/runs.jsonl` line at repo-root has been REMOVED.

No network. No test data writes outside tmp_path.
"""

# Wave: 0  (named-stub skeletons; bodies filled by Plan 08-02 — see 08-VALIDATION.md "New test files")

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runs_jsonl_not_ignored() -> None:
    """OPS-05 / D-04: data/runs.jsonl must be committable — git check-ignore
    must return exit code 1 (= NOT ignored)."""
    pytest.skip("body filled by Plan 08-02 (Wave 1)")


def test_heartbeat_txt_not_ignored() -> None:
    """OPS-03 / D-11: data/heartbeat.txt must be committable — git check-ignore
    must return exit code 1."""
    pytest.skip("body filled by Plan 08-02 (Wave 1)")


def test_reports_md_not_ignored() -> None:
    """OPS-02 / Pitfall #4: reports/*.md MUST be committable after Phase 8
    carve-out. The pre-Phase-8 /reports/ line silently blocked OPS-02 —
    this test enforces the fix. git check-ignore on reports/2026-05-19.md
    must return exit code 1."""
    pytest.skip("body filled by Plan 08-02 (Wave 1)")


def test_old_root_runs_jsonl_line_removed() -> None:
    """D-04: the old `/runs.jsonl` line at repo root MUST be removed from
    .gitignore (the file relocates to data/runs.jsonl). A stale root-level
    line would cause grep noise + future confusion."""
    pytest.skip("body filled by Plan 08-02 (Wave 1)")
