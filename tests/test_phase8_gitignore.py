"""gitignore carve-out tests — OPS-02 / OPS-05 / CONTEXT D-04 / CONTEXT D-11.

Asserts the three Phase 8 carve-outs (data/runs.jsonl, data/heartbeat.txt,
reports/*.md) are committable past .gitignore via `git check-ignore -q`
exit-code 1, and that the old root-level `/runs.jsonl` line is removed.

No network. No file writes.
"""

# Wave: 1  (bodies filled by Plan 08-02 — see 08-VALIDATION.md "New test files")

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _check_ignore(relative_path: str) -> int:
    """Return git check-ignore exit code.

    Exit codes:
      0 = path IS ignored
      1 = path is NOT ignored (the assertion target for Phase 8 carve-outs)
      128 = git error (treat as test failure)
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", relative_path],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def test_runs_jsonl_not_ignored() -> None:
    """OPS-05 / D-04: data/runs.jsonl must be committable past .gitignore.

    The pre-Phase-8 root-level `/runs.jsonl` ignore was removed; the new
    `!/data/runs.jsonl` carve-out lets the relocated file be committed.
    """
    rc = _check_ignore("data/runs.jsonl")
    assert rc == 1, (
        f"data/runs.jsonl is ignored (rc={rc!r}); expected 1 (NOT ignored). "
        f"Carve-out `!/data/runs.jsonl` missing from .gitignore? "
        f"See 08-RESEARCH.md §.gitignore Diff (D-04 + D-11)."
    )


def test_heartbeat_txt_not_ignored() -> None:
    """OPS-03 / D-11: data/heartbeat.txt must be committable past .gitignore.

    The carve-out `!/data/heartbeat.txt` is what lets the weekly
    heartbeat.yml workflow's auto-commit step pick the file up.
    """
    rc = _check_ignore("data/heartbeat.txt")
    assert rc == 1, (
        f"data/heartbeat.txt is ignored (rc={rc!r}); expected 1 (NOT ignored). "
        f"Carve-out `!/data/heartbeat.txt` missing from .gitignore? "
        f"See 08-CONTEXT.md §D-11."
    )


def test_reports_md_not_ignored() -> None:
    """OPS-02 / Pitfall #4: reports/<date>.md MUST be committable.

    The pre-Phase-8 `/reports/` line silently blocked every markdown report
    from being committed by the refresh.yml auto-commit step (silent OPS-02
    failure). Phase 8 fixes this with `!/reports/` + `!/reports/*.md`
    carve-outs.
    """
    rc = _check_ignore("reports/2026-05-19.md")
    assert rc == 1, (
        f"reports/2026-05-19.md is ignored (rc={rc!r}); expected 1 (NOT ignored). "
        f"Carve-outs `!/reports/` + `!/reports/*.md` missing? "
        f"See 08-RESEARCH.md §Pitfall #4 /reports/ silently breaks OPS-02."
    )


def test_old_root_runs_jsonl_line_removed() -> None:
    """D-04: the obsolete root-level `/runs.jsonl` line MUST be removed.

    The file relocated to data/runs.jsonl; a stale ignore line at repo root
    creates grep noise and future confusion. Asserts the EXACT regex
    `^/runs\\.jsonl$` does not appear anywhere in .gitignore.
    """
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    matching_lines = [
        line for line in gitignore_text.splitlines()
        if line.strip() == "/runs.jsonl"
    ]
    assert matching_lines == [], (
        f"Obsolete root-level `/runs.jsonl` line still present in .gitignore "
        f"({matching_lines!r}); D-04 says the file relocated to data/runs.jsonl. "
        f"Remove the old line."
    )
