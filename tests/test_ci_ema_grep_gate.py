"""CI EMA-grep-gate mutation test (IND-02).

Replicates the exact `grep` invocation `.github/workflows/ci.yml` runs and
asserts:
  1. On the current clean codebase, the grep command exits non-zero (gate passes).
  2. When 'ema' is injected into a temp copy of trend.py, the grep command
     exits zero (gate would catch the mutation and fail CI).

This is the only mutation test in the project for the grep gate — without it,
the gate could silently break (e.g., wrong path, wrong flags) and still 'pass'
because there's nothing to match.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    REPO_ROOT / "src" / "screener" / "signals" / "minervini.py",
    REPO_ROOT / "src" / "screener" / "indicators" / "trend.py",
)


def _run_grep(*paths: Path) -> int:
    """Run the same grep command as the CI step; return exit code."""
    proc = subprocess.run(
        ["grep", "-ilE", "ema", *[str(p) for p in paths]],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def test_ema_grep_passes_when_clean() -> None:
    """Current codebase: trend.py has no `ema`; minervini.py may not exist yet.
    The grep command should exit non-zero (no matches across present files).
    """
    # Mimic the CI shell guard: redirect stderr so missing files are silent.
    proc = subprocess.run(
        f'grep -ilE "ema" {" ".join(str(p) for p in TARGETS)} 2>/dev/null',
        shell=True,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"grep matched 'ema' in {TARGETS} unexpectedly; output: {proc.stdout!r}"
    )


def test_ema_grep_fails_on_mutation(tmp_path: Path) -> None:
    """Inject 'ema' into a temp copy of trend.py; the grep command must
    exit 0 (match found) — proving the gate would catch the mutation."""
    real = REPO_ROOT / "src" / "screener" / "indicators" / "trend.py"
    fake_dir = tmp_path / "src" / "screener" / "indicators"
    fake_dir.mkdir(parents=True, exist_ok=True)
    fake_trend = fake_dir / "trend.py"
    shutil.copy(real, fake_trend)
    # Append a line containing 'ema' (lowercase — most likely mutation form).
    with fake_trend.open("a", encoding="utf-8") as f:
        f.write("\n# regression: ema reference\n")
    rc = _run_grep(fake_trend)
    assert rc == 0, f"expected grep to find 'ema' in mutated copy; got rc={rc}"


def test_ema_grep_fails_on_uppercase_mutation(tmp_path: Path) -> None:
    """Case-insensitive flag — uppercase EMA must also fail the gate."""
    real = REPO_ROOT / "src" / "screener" / "indicators" / "trend.py"
    fake_dir = tmp_path / "src" / "screener" / "indicators"
    fake_dir.mkdir(parents=True, exist_ok=True)
    fake_trend = fake_dir / "trend.py"
    shutil.copy(real, fake_trend)
    with fake_trend.open("a", encoding="utf-8") as f:
        f.write("\n# regression: EMA reference\n")
    rc = _run_grep(fake_trend)
    assert rc == 0, "uppercase EMA must also be caught by case-insensitive grep"
