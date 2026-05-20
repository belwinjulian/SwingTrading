# Phase 8: GitHub Actions Cron & Operations - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 9 (7 CREATE + 2 MODIFY)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.github/workflows/refresh.yml` | workflow (CI/CD) | event-driven (cron + dispatch) | `.github/workflows/ci.yml` | role-match (no scheduled analog) |
| `.github/workflows/heartbeat.yml` | workflow (CI/CD) | event-driven (cron) | `.github/workflows/no-lookahead-gate.yml` + `ci.yml` | role-match (minimal subset) |
| `src/screener/publishers/run_log.py` | publisher (file I/O) | file-append (JSONL) | `src/screener/publishers/snapshot.py` (publisher shape) + `src/screener/persistence.py:_write_parquet_atomic` (atomic write) | exact (publisher) / contrast (atomic vs append) |
| `tests/test_run_log.py` | test (unit) | tmp_path + monkeypatch on module path | `tests/test_insider_io.py` (monkeypatch env on `_INSIDER_DB`) | exact |
| `tests/test_phase8_gitignore.py` | test (static/subprocess) | subprocess on `git check-ignore` | `tests/test_ci_ema_grep_gate.py` (subprocess + REPO_ROOT pattern) | role-match (subprocess on shell tool) |
| `tests/test_phase8_workflow_static.py` | test (static YAML parse) | file read + parse | `tests/test_ci_ema_grep_gate.py` (REPO_ROOT-anchored file reads) | role-match (no YAML-parse analog exists) |
| `tests/test_pipeline_emits_run_log.py` | test (integration) | tmp_path + monkeypatch + `run_pipeline()` | `tests/test_pipeline_journal.py` | exact |
| `.gitignore` | config | declarative | `.gitignore` lines 37-46 (existing data/ carve-out block) | exact (extend in place) |
| `src/screener/publishers/pipeline.py` | publisher (orchestrator) | try/finally + structlog | `src/screener/publishers/pipeline.py:run_pipeline` (lines 538-550 — existing `log.info("pipeline_complete", ...)`) | exact (extend in place) |

---

## Pattern Assignments

### `.github/workflows/refresh.yml` (workflow, event-driven cron + dispatch)

**Analog:** `.github/workflows/ci.yml` (uv-setup + pinned-hash + concurrency stanza)
**Supplementary analog:** `.github/workflows/no-lookahead-gate.yml` (path-filtered minimal job demonstrating pinned-hash convention)

**Header + concurrency + permissions pattern** (from `ci.yml` lines 1-15):
```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

# Cancel superseded runs on the same branch.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
```

**Conventions to replicate for refresh.yml:**
- `name: refresh` (lowercase, matches filename — every workflow in this repo follows this).
- `concurrency` stanza is ALWAYS present (both existing workflows have it).
  - **OVERRIDE for refresh.yml:** use `cancel-in-progress: false` (Pitfall #3 — long cron runs must not be killed by manual dispatch).
  - `group: refresh-${{ github.ref }}` (deviation from `${{ github.workflow }}-${{ github.ref }}` is acceptable; group naming is local discretion).
- `permissions:` block ALWAYS declared at workflow level (security defense — never inherit).
  - **OVERRIDE for refresh.yml:** `contents: write` (needs to commit artifacts; ci.yml uses `read`).
- Trailing-comment pattern: `# OPS-XX` or `# D-XX` references after each non-obvious decision (mirror the "# Cancel superseded runs..." comment style from ci.yml line 8).

**Pinned action hash pattern** (verbatim from `ci.yml` lines 22-28):
```yaml
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
```

**Conventions to replicate verbatim:**
- 40-char commit SHA + TWO spaces + `# vX.Y.Z` trailing comment (verifier scans for this exact pattern).
- `enable-cache: true` and `cache-dependency-glob: "uv.lock"` on every setup-uv invocation.
- REUSE the exact two SHAs above — do NOT re-pin checkout or setup-uv to newer versions (consistency lock).
- NEW pins required for Phase 8: `actions/cache@<v4.3.0-sha>  # v4.3.0` and `stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0` (resolve actions/cache SHA via `git ls-remote` at commit time).

**Job body pattern — uv install + Python + deps** (verbatim from `ci.yml` lines 21-34, repeated identically across all three jobs in ci.yml):
```yaml
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev
```

**Conventions to replicate:**
- 4-step setup is ALWAYS this exact order and these exact step names — do not rename them.
- `uv sync --frozen --extra dev` (NOT `--no-dev`, NOT `pip install`).

**Job-level metadata pattern** (from `ci.yml` lines 17-20):
```yaml
jobs:
  lint:
    name: lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
```

**Conventions to replicate:**
- Job name == filename stem (`refresh` for refresh.yml; matches `lint`/`typecheck`/`test` for ci.yml).
- `runs-on: ubuntu-latest` is the project default (every existing job uses it).
- `timeout-minutes: 120` for refresh.yml (D-07; ci.yml uses 10, no-lookahead-gate.yml uses 5 — Phase 8 is the outlier).

**Inline bash gate pattern** (from `ci.yml` lines 42-47 — for reference if any inline-bash assertions are needed):
```yaml
      - name: SMA-not-EMA gate (IND-02)
        run: |
          if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
            echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
            exit 1
          fi
```

**Convention to replicate:** trailing-comment naming `(REQ-XX)` on every step that enforces a requirement.

---

### `.github/workflows/heartbeat.yml` (workflow, event-driven cron weekly)

**Analog:** `.github/workflows/no-lookahead-gate.yml` (single-job, minimal-step workflow with the standard pinned-hash + concurrency stanza)

**Minimal-job pattern** (verbatim from `no-lookahead-gate.yml` lines 19-32):
```yaml
# Cancel superseded runs on the same branch.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  no-lookahead-gate:
    name: no-lookahead-gate
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

**Conventions to replicate for heartbeat.yml:**
- Single job, `timeout-minutes: 5` (heartbeat is trivially fast — match no-lookahead-gate's timeout).
- `concurrency.cancel-in-progress: true` is the right default for a weekly heartbeat (no risk of killing a long-running job).
- **OVERRIDE:** `permissions: contents: write` (heartbeat MUST commit `data/heartbeat.txt`; CONTEXT.md D-09 says `read` but that's a slip — see RESEARCH §Pitfall #8 / Open Question A).
- NO `uv` setup needed (heartbeat doesn't run Python). Body is just `mkdir -p data && date -u +%Y-%m-%dT%H:%M:%SZ > data/heartbeat.txt` + the auto-commit action.

---

### `src/screener/publishers/run_log.py` (publisher, file-append JSONL)

**Primary analog:** `src/screener/publishers/snapshot.py` (publisher module shape — thin caller, single side-effecting public function, structlog at module level).
**Secondary analog:** `src/screener/persistence.py:_write_parquet_atomic` lines 472-494 (file-I/O contract style — but Phase 8 uses simpler `open('a') + flush + fsync`, NOT atomic-rename, per RESEARCH §Don't Hand-Roll).

**Module docstring + imports pattern** (verbatim shape from `snapshot.py` lines 1-20):
```python
"""publishers.snapshot — thin caller for the daily ranking-snapshot Parquet write.

The atomic-write helper lives in persistence.write_snapshot_atomic (D-15/D-16
schema-at-IO contract; D-11 atomic-write contract). This publisher exists so
the orchestrator (publishers/pipeline.py) can compose snapshot + report
uniformly under publishers/.

Architecture (D-16): publishers/ may import persistence, config, obs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog

from screener.persistence import write_snapshot_atomic

log = structlog.get_logger(__name__)
```

**Conventions to replicate:**
- `"""publishers.<name> — <one-line purpose>."""` opening line; multi-paragraph docstring that names the relevant D-XX decisions.
- `from __future__ import annotations` ALWAYS at the top (every publisher + persistence module has it).
- Two-block import order: stdlib first, then third-party, then `from screener.*` — separated by blank lines.
- `log = structlog.get_logger(__name__)` at module level (NEVER inside a function).
- Closing line of docstring names the architecture import-allowlist (`publishers/ may import persistence, config, obs`); Phase 8 should add the same line and confirm `publishers/run_log.py` imports ONLY stdlib + structlog (no `screener.*` deps needed — D-23 / D-06 architecture lock).

**Public-function signature pattern** (from `snapshot.py` lines 23-38):
```python
def write_snapshot(scored_panel: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write the full ranked snapshot.

    Args:
        scored_panel: cross-section frame (one row per ticker) conforming
            to RankingSnapshotSchema (16 columns including ticker, rank,
            composite_score, all *_component cols, passes_trend_template,
            pivot_zone, regime_state, regime_score).
        snapshot_date: ISO YYYY-MM-DD string.

    Returns:
        Path to the written Parquet (data/snapshots/<date>.parquet).
    """
    target = write_snapshot_atomic(scored_panel, snapshot_date)
    log.info("publisher_snapshot_complete", path=str(target))
    return target
```

**Conventions to replicate:**
- Google-style docstring with `Args:` and `Returns:` sections.
- Single `log.info(<event_name>, key=value, ...)` line on the SUCCESS path (event names are `snake_case` past-tense — e.g. `publisher_snapshot_complete`, `journal_appended`, `snapshot_written`, `run_log_appended`).
- Public function returns the target `Path` so callers can chain (Phase 8: `append_record` may return `None` — fine, but if it returns anything, return the Path).

**Structlog event-name convention** (mined from `pipeline.py`, `persistence.py`):
| Event | Usage |
|-------|-------|
| `<action>_<noun>` past-tense | `snapshot_written`, `journal_appended`, `fundamentals_written`, `macro_snapshot_written` |
| Fields are `snake_case` keys | `path=str(target)`, `n_rows=len(validated)`, `snapshot_date=snapshot_date` |
| `error_type=type(e).__name__` on caught exceptions | `pipeline.py:539`, `persistence.py:961` |
| `reason="<short_snake_case>"` for skip/no-op events | `pipeline.py:508` (`reason="no_actionable_picks_above_threshold"`), `pipeline.py:511` (`reason="write_journal=False"`) |

For Phase 8 `run_log.py`, use:
- `log.info("run_log_appended", status=record.get("status"), path=str(_RUNS_PATH))` (matches the analog event-naming).

**File-I/O pattern with flush + fsync** (NEW — no exact analog; closest is `persistence._write_parquet_atomic` which uses `os.replace` for atomic rename, NOT append). RESEARCH §Pitfall 5 specifies the JSONL pattern verbatim:
```python
def append_record(record: RunLogRecord) -> None:
    _RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    with open(_RUNS_PATH, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())  # force OS write — critical for the failure path
    log.info("run_log_appended", status=record.get("status"), path=str(_RUNS_PATH))
```

**Conventions to replicate:**
- `parent.mkdir(parents=True, exist_ok=True)` BEFORE any write (every writer in persistence.py does this — see `_write_parquet_atomic` line 480, `_ensure_insider_schema` line 1015, `_ensure_picks_schema` line 1083).
- `encoding="utf-8"` is explicit on every text-mode open (consistent with the Python 3.11 style used throughout).
- `json.dumps(record, sort_keys=True)` — sort_keys for deterministic record shape (mirrors pandera's strict column-order semantics in persistence.py).

**Module-level path constant pattern** (from `persistence.py` lines 523-573 — every dir/path is resolved by a `_<name>_dir()` helper that reads `get_settings()` with a getattr fallback):
```python
def _ohlcv_dir() -> Path:
    """Resolve the OHLCV cache directory, with a hard-coded fallback for the
    Wave-1 race against 02-02 (which adds OHLCV_CACHE_DIR to Settings).
    """
    s: Any = get_settings()
    return Path(getattr(s, "OHLCV_CACHE_DIR", "data/ohlcv"))
```

**Decision for Phase 8:** RESEARCH explicitly chose a module-level `_RUNS_PATH = Path("data/runs.jsonl")` constant (not a `_runs_path()` helper) to keep tests' `monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", ...)` simple. This deviates from the `persistence.py` getattr-on-Settings pattern but matches the simpler RESEARCH §Run-log Python Module skeleton (lines 400-415). Document the deviation in a `# REVIEW:` comment.

**`__main__` entrypoint pattern** (NEW — no existing analog in `src/screener/`; closest is `scripts/check_preregistration.py` which is a standalone). Use the RESEARCH §Run-log Python Module skeleton verbatim:
```python
if __name__ == "__main__":
    # Entry: python -m screener.publishers.run_log {success|failure}
    if len(sys.argv) != 2 or sys.argv[1] not in ("success", "failure"):
        print("usage: ...", file=sys.stderr)
        raise SystemExit(2)
    _cli_failure_entry("failed" if sys.argv[1] == "failure" else "success")
```

**Convention note:** This is the ONE place in the codebase where `print(..., file=sys.stderr)` is acceptable — CLAUDE.md's "no print()" rule applies to runtime logging (use structlog), but a `python -m` entrypoint's argument-validation error message is allowed (mirrors `scripts/check_preregistration.py` exit-1 idiom).

---

### `tests/test_run_log.py` (test, unit — tmp_path + monkeypatch on module path)

**Analog:** `tests/test_insider_io.py` (monkeypatch on `INSIDER_CACHE_PATH` env var to redirect a module-level path constant to `tmp_path`)

**Test pattern** (excerpt from `test_insider_io.py` lines 90-130):
```python
def test_<behavior>(
    tmp_path: pytest.TempPathFactory,  # type: ignore[type-arg]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """<docstring referencing the REQ-ID being tested>."""
    db_path = str(tmp_path / "form4.sqlite")
    monkeypatch.setenv("INSIDER_CACHE_PATH", db_path)
    # ... act + assert
```

**Conventions to replicate:**
- Type-annotate `tmp_path: Path` and `monkeypatch: pytest.MonkeyPatch` on EVERY test fixture parameter.
- Docstring opens with the REQ-ID being tested (e.g. `"""OPS-05: append_record writes a valid JSONL line."""`).
- Tests prefixed `test_<verb>_<noun>_<condition>` (e.g. `test_append_record_writes_valid_jsonl_with_fsync`, `test_cli_failure_entry_writes_failure_record`).

**Path-redirection for Phase 8 run_log.py:**
Phase 8 chose a module-level `_RUNS_PATH` constant (not env-backed). Monkeypatch directly:
```python
monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", tmp_path / "runs.jsonl")
```

This mirrors the `monkeypatch.setattr(_pers, "write_pattern_audit_atomic", ...)` shape from `test_pipeline_journal.py` line 139.

**Import-pattern excerpt** (from `test_insider_io.py` lines 1-21):
```python
"""EDGAR Form 4 data adapter tests — CAT-04.

Plan 06-03 (Wave 1) fills the test bodies with mocked assertions over
``data/insider.py`` (edgartools bulk Form 4 fetch + SQLite append-only
event log per D-10). InsiderSchema validation runs BEFORE the SQLite insert.
No real EDGAR network calls are made in any test.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pandera.errors as pa_errors
import pytest

from screener import persistence
```

**Conventions to replicate:**
- Module docstring opens with `"""<area> tests — <REQ-ID>."""` and one paragraph naming the modules under test.
- `# Wave: N  (body filled by Plan XX-YY — see YY-VALIDATION.md "New test files")` marker comment (every Phase 6+ test file has this).
- Three-block import order: stdlib, third-party, `from screener.*`.

---

### `tests/test_phase8_gitignore.py` (test, static — subprocess on `git check-ignore`)

**Analog:** `tests/test_ci_ema_grep_gate.py` (the only test file in the project that shells out to a system tool via `subprocess.run` and asserts on `returncode`; uses the `REPO_ROOT = Path(__file__).resolve().parents[1]` idiom).

**REPO_ROOT pattern + subprocess shape** (verbatim from `test_ci_ema_grep_gate.py` lines 14-35):
```python
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
```

**Conventions to replicate:**
- `REPO_ROOT = Path(__file__).resolve().parents[1]` is the canonical project-anchor (search for it across all tests).
- `subprocess.run([...], capture_output=True, text=True)` (always `capture_output=True` to silence stdout, always `text=True` for str return).
- A private `_run_<tool>(*args) -> int` helper centralizes the command construction.

**For Phase 8 gitignore tests, the equivalent helper is:**
```python
def _check_ignore(path: str) -> int:
    """Return git check-ignore exit code: 0 = ignored, 1 = NOT ignored."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", path],
        capture_output=True,
        text=True,
    )
    return proc.returncode

# A path is NOT ignored when rc == 1.
def test_runs_jsonl_not_ignored() -> None:
    """OPS-05: data/runs.jsonl must be committable past .gitignore."""
    assert _check_ignore("data/runs.jsonl") == 1
```

**Assertion-error-message style** (verbatim from `test_ci_ema_grep_gate.py` line 48):
```python
assert proc.returncode != 0, (
    f"grep matched 'ema' in {TARGETS} unexpectedly; output: {proc.stdout!r}"
)
```

**Convention to replicate:** Every assert in tests has a `f"<expected>; got <observed> (state: {...!r})"` failure message. The `!r` on captured output is consistent.

---

### `tests/test_phase8_workflow_static.py` (test, static — YAML parse + structural assertions)

**Analog (closest):** `tests/test_ci_ema_grep_gate.py` (REPO_ROOT-anchored file-system tests — but it does NOT parse YAML; Phase 8 introduces YAML parsing). No exact YAML-parsing analog exists in the test suite.

**Use REPO_ROOT pattern from `test_ci_ema_grep_gate.py` lines 14-24:**
```python
REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    REPO_ROOT / ".github" / "workflows" / "refresh.yml",
    REPO_ROOT / ".github" / "workflows" / "heartbeat.yml",
)
```

**YAML-parse pattern (NEW, but `pyyaml` IS available via uv.lock transitive deps — verified line 1408):**
```python
import yaml  # transitive dep via pandera/structlog stack

def _parse(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
```

**Conventions to replicate (from `test_ci_ema_grep_gate.py`):**
- Anchor every file lookup on `REPO_ROOT`.
- One assertion per test (test names spell out the property: `test_refresh_workflow_pins_actions`, `test_refresh_has_workflow_dispatch`, `test_heartbeat_workflow_exists_and_pinned`).
- Failure message includes the file path: `f"refresh.yml missing pinned hash for actions/cache; uses block: {step!r}"`.

**Pinned-hash regex assertion (NEW pattern unique to Phase 8 — derived from the `# vX.Y.Z` comment-marker convention in `ci.yml` line 22):**
```python
import re

# Match: "owner/repo@<40-hex-sha>  # vMAJOR.MINOR.PATCH"
PINNED_HASH_RE = re.compile(
    r"[\w-]+/[\w-]+@[0-9a-f]{40}\s+#\s+v\d+\.\d+\.\d+"
)
```

---

### `tests/test_pipeline_emits_run_log.py` (test, integration — `run_pipeline` writes a record)

**Analog:** `tests/test_pipeline_journal.py` (the EXACT same shape: stub-out every `run_pipeline` dependency, point a module-level path constant at `tmp_path`, assert the side effect landed on disk).

**Settings setup helper pattern** (verbatim from `test_pipeline_journal.py` lines 180-191):
```python
def _setup_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point JOURNAL_DB_PATH + SNAPSHOT_DIR at tmp_path; clear Settings cache."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JOURNAL_DB_PATH", str(tmp_path / "journal.sqlite"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    monkeypatch.setenv("JOURNAL_THRESHOLD", "50.0")
    monkeypatch.setenv("RISK_PCT", "0.01")
    monkeypatch.setenv("ACCOUNT_EQUITY", "100000")
    from screener.config import get_settings
    get_settings.cache_clear()
```

**Conventions to replicate for Phase 8:**
- ALWAYS call `get_settings.cache_clear()` after `monkeypatch.setenv` on a Settings field — pydantic-settings caches at import (see persistence.py:864 "REVIEW IN-01 iter 2" docstring).
- ADD `monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", tmp_path / "runs.jsonl")` to redirect the JSONL write.

**Pipeline-mock helper pattern** (verbatim from `test_pipeline_journal.py` lines 87-142):
```python
def _install_pipeline_mocks(monkeypatch: pytest.MonkeyPatch, panel: pd.DataFrame) -> None:
    # Module-level imports in pipeline.py — patch the pipeline module attr.
    monkeypatch.setattr("screener.publishers.pipeline.build_panel", lambda d: panel)
    monkeypatch.setattr("screener.publishers.pipeline.passes_trend_template", lambda p: p)
    monkeypatch.setattr("screener.publishers.pipeline.score", lambda p, w: p)
    monkeypatch.setattr("screener.publishers.pipeline.compute_for_date",
        lambda ts, p: pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82}),
    )
    monkeypatch.setattr("screener.publishers.pipeline.validate_run", lambda *a, **kw: None)
    # Inline-imported inside run_pipeline — patch the source module.
    monkeypatch.setattr("screener.signals.qullamaggie.passes_qullamaggie_setup_a", lambda p: p)
    monkeypatch.setattr("screener.signals.canslim.canslim_c_overlay", lambda p, f, ts: p)
    monkeypatch.setattr("screener.signals.composite.tag_playbook", lambda p: p)
    import screener.sizing as _sizing
    monkeypatch.setattr(_sizing, "compute_sizing", lambda cross, panel, **kw: _stub_sizing(cross))
    # ... etc
```

**Conventions to replicate:**
- Distinguish between MODULE-LEVEL imports in `pipeline.py` (patched via `"screener.publishers.pipeline.<name>"`) and INLINE imports inside `run_pipeline()` (patched via the SOURCE module path — `"screener.signals.qullamaggie.passes_qullamaggie_setup_a"`).
- Phase 8: re-use the entire `_install_pipeline_mocks` + `_stub_sizing` + `_make_synthetic_multiindex_panel` helper set (copy from `test_pipeline_journal.py` lines 18-178). Likely import them rather than duplicate.

**Test body pattern** (verbatim from `test_pipeline_journal.py` lines 193-209):
```python
def test_pipeline_writes_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OUT-04: run_pipeline(..., write_journal=True) appends rows to data/journal.sqlite."""
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    db = tmp_path / "journal.sqlite"
    assert db.exists()
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT ticker, composite_score FROM picks").fetchall()
```

**For Phase 8, the equivalent shape is:**
```python
def test_pipeline_emits_run_log_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OPS-05: run_pipeline writes a success record to data/runs.jsonl."""
    _setup_settings(tmp_path, monkeypatch)
    monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", tmp_path / "runs.jsonl")
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=False)

    runs = tmp_path / "runs.jsonl"
    assert runs.exists()
    record = json.loads(runs.read_text().strip())
    assert record["status"] == "success"
    assert record["regime_state"] == "Confirmed Uptrend"
    assert record["picks_count"] is not None
```

---

### `.gitignore` (config, declarative — extend existing carve-out block in place)

**Analog:** `.gitignore` lines 31-46 (existing data/ carve-out block, with its own header comment).

**Existing carve-out block** (verbatim from `.gitignore` lines 31-48):
```
# Output directories — selective carve-out for committed audit artifacts.
# Anchored to repo root so source-layer dirs (src/screener/data/) are NOT
# ignored. Universe Parquet snapshots and per-ticker splits ledgers ARE
# committed (small, audit-relevant); per-ticker prices.parquet stays local.
# Phase 1 originally said `/data/`; Phase 2 (D-19 reconciled with D-06 per
# Amendment 2026-05-02) carves out two committed paths.
/data/*
!/data/universe/
!/data/universe/.gitkeep
!/data/ohlcv/
/data/ohlcv/**/prices.parquet
!/data/ohlcv/**/splits.parquet
!/data/ohlcv/**/.gitkeep
!/data/snapshots/
/data/snapshots/*.parquet
!/data/snapshots/.gitkeep
/reports/
/runs.jsonl
```

**Conventions to replicate for Phase 8 edits:**
- Multi-line `#` header comment naming the Phase and the D-XX decision that introduced the rule (mirror lines 31-36, 50-54, 68-69).
- Allowlist-style ordering: deny rule (`/data/<dir>/*` or `/data/<file>`) IMMEDIATELY followed by carve-out rule (`!/data/<dir>/.gitkeep` or `!/data/<file>`).
- Phase 7 line 70 (`!/data/journal.sqlite`) is the closest analog for a single-file carve-out at root of `/data/*`.

**Required edits (per CONTEXT D-04 + RESEARCH §.gitignore Diff):**
1. REMOVE line 48: `/runs.jsonl` (file relocated to `data/runs.jsonl`).
2. ADD inside the data/ carve-out block (after line 46 `!/data/snapshots/.gitkeep`):
   ```
   # Phase 8 (OPS-05 / D-04 / D-11): observability artifacts.
   !/data/runs.jsonl
   !/data/heartbeat.txt
   ```
3. REPLACE line 47 `/reports/` with:
   ```
   # Phase 8 (OPS-02 fix): reports/<date>.md MUST be committable past the
   # blanket `/reports/` ignore — mirror the data/universe/ carve-out idiom.
   !/reports/
   !/reports/*.md
   ```

**Style note:** Every carve-out comment in this file names the Phase and decision ID — Phase 8 edits must follow suit.

---

### `src/screener/publishers/pipeline.py` (publisher orchestrator — MODIFY `run_pipeline`)

**Analog:** `run_pipeline()` itself (lines 298-550 — the function being modified is its own best analog for the surrounding-context coding style).

**End-of-function structlog event pattern** (verbatim from `pipeline.py` lines 541-550):
```python
    log.info(
        "pipeline_complete",
        snapshot_date=snapshot_date,
        n_tickers=len(today_panel),
        pass_rate=pass_rate,
        regime_state=regime_state_value,
        regime_score=regime_score_value,
        wrote_report=write_report,
        wrote_journal=write_journal,
    )
```

**Conventions to replicate for the run_log append insertion:**
- The new `append_record(...)` call MUST be the LAST statement in `run_pipeline` (after `log.info("pipeline_complete", ...)`) — symmetry with how `journal_appended` is emitted at the end of `append_picks_rows` in persistence.py:1124.
- Use existing locals as the source of truth (no new computation):
  - `start_time` ← captured via `_t_start = time.perf_counter()` + `_start_iso = datetime.now(UTC).isoformat(timespec="seconds")` at the TOP of `run_pipeline` (after line 326 `settings = get_settings()`).
  - `regime_state` ← `regime_state_value` (already a local at line 381).
  - `picks_count` ← `int((today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD).sum())` (mirrors the threshold filter already used at line 472).
  - `fetch_success_rate` ← `len(today_panel) / max(1, len(panel.index.get_level_values("ticker").unique()))` (RESEARCH §Integration Points).
  - `n_429_responses: 0` placeholder (Open Question B — accepted v1 stub).

**Try/finally pattern (NEW — `run_pipeline` currently has NO try/finally; this is the structural change Phase 8 introduces):**

There is no existing try/finally analog inside `run_pipeline`. The closest analog is the small try/except around `_build_pattern_audit_df` at pipeline.py lines 534-539:
```python
    try:
        pattern_audit_df = _build_pattern_audit_df(panel, snap_ts)
        if not pattern_audit_df.empty:
            persistence.write_pattern_audit_atomic(pattern_audit_df, snapshot_date)
    except Exception as e:
        log.warning("pattern_audit_write_failed", error_type=type(e).__name__)
```

**Convention to replicate:**
- The try/finally wrapper for Phase 8 should NOT swallow exceptions (the failure path is `python -m run_log failure` from the workflow YAML, NOT from inside `run_pipeline` — D-05 explicit).
- Capture `_t_start` BEFORE the try, write success record on the SUCCESS path only (raise re-raises to the CLI). Per RESEARCH §Integration Points: "single append at the end is atomic on disk".
- DECISION (from RESEARCH §Implementation Approach): Do NOT wrap in try/finally inside `run_pipeline`. Write the success record on the success-only path; the workflow YAML's `if: failure()` invokes `python -m run_log failure` from bash for the failure case. This avoids the dual-write problem.

**Import-injection pattern at top of run_pipeline** (mine the inline-import idiom from pipeline.py lines 336-348, 443, 454, 484-488):
```python
    # === Phase 8 (OPS-05): run-log append at end of pipeline ===
    from screener.publishers.run_log import append_record
    # ... use append_record at the end of the function ...
```

**Conventions to replicate:**
- Inline imports inside `run_pipeline` are the established pattern for Phase-extension code (lines 336, 343, 348, 362, 395, 443, 454, 484-488 are all inline imports added by Phase 6/7).
- Section banner comment: `# === Phase N (REQ-ID): <summary> ===` (mirrors lines 384, 423, 465, 512).
- End with a matching `# === END Phase N step X.Y ===` comment (lines 423, 512).

---

## Shared Patterns

### Pinned action hashes (cross-cutting workflow security)
**Source:** `.github/workflows/ci.yml` lines 22, 25, 54, 57, 76, 79
**Apply to:** Both refresh.yml AND heartbeat.yml
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
```
Plus NEW (resolve SHA at commit time via `git ls-remote`):
- `actions/cache@<v4.3.0-sha>  # v4.3.0` (refresh.yml only)
- `stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0` (both)

### Concurrency + permissions stanzas (cross-cutting workflow shape)
**Source:** `.github/workflows/no-lookahead-gate.yml` lines 19-25; `ci.yml` lines 9-14
**Apply to:** Every workflow YAML (existing pattern — no Phase 8 deviation except `cancel-in-progress: false` for refresh.yml long-cron).
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true   # OR false for refresh.yml (long cron)

permissions:
  contents: read              # OR write for refresh + heartbeat (auto-commit)
```

### Structlog logger initialization (cross-cutting Python module shape)
**Source:** `src/screener/publishers/snapshot.py` lines 19-20; `src/screener/persistence.py` line 41; `src/screener/publishers/pipeline.py` line 50
**Apply to:** `src/screener/publishers/run_log.py`
```python
import structlog
log = structlog.get_logger(__name__)
```
**Convention:** Module-level binding (NOT function-level), `__name__` argument (never a hardcoded string).

### `from __future__ import annotations` (cross-cutting Python module shape)
**Source:** Every `src/screener/**/*.py` file (universal — checked via `grep -L`).
**Apply to:** `src/screener/publishers/run_log.py` (first non-docstring line).

### Test module preamble (cross-cutting test shape)
**Source:** `tests/test_insider_io.py` lines 1-9, `tests/test_publishers_snapshot.py` lines 1-2, `tests/test_pipeline_journal.py`
**Apply to:** All 4 NEW test files in Phase 8.
```python
"""<area> tests — <REQ-ID(s)>.

Plan 08-XX (Wave N) fills the test bodies with mocked assertions over
``<module under test>``. <relevant decision references>.
No real network calls are made in any test.
"""

# Wave: N  (body filled by Plan 08-XX — see 08-VALIDATION.md "New test files")
```

### Settings cache clear after monkeypatch (cross-cutting test pattern)
**Source:** `tests/test_pipeline_journal.py` lines 189-190; `src/screener/persistence.py:864` (REVIEW IN-01 iter 2 docstring documents the rationale)
**Apply to:** `tests/test_pipeline_emits_run_log.py` and any other test that monkeypatches env vars read by Settings.
```python
from screener.config import get_settings
get_settings.cache_clear()
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All Phase 8 files have at least a role-match analog in the codebase. The YAML-parsing test (`test_phase8_workflow_static.py`) has the weakest match (no existing YAML-parse test exists), but the REPO_ROOT pattern from `test_ci_ema_grep_gate.py` covers the file-anchoring half. The `__main__` entrypoint in `run_log.py` has no analog in `src/screener/` (it's a publisher-with-CLI hybrid forced by D-06 / D-24), but the RESEARCH skeleton is concrete enough to use verbatim. |

---

## Metadata

**Analog search scope:**
- `.github/workflows/` (2 files)
- `src/screener/publishers/` (3 files)
- `src/screener/persistence.py`
- `tests/` (45 files; deep-read on test_ci_ema_grep_gate, test_insider_io, test_pipeline_journal, test_publishers_snapshot, test_cli_smoke, test_fundamentals_io)
- `.gitignore`
- `src/screener/obs.py` (structlog convention reference)

**Files scanned:** ~55
**Pattern extraction date:** 2026-05-19

---

## PATTERN MAPPING COMPLETE

**Phase:** 8 — GitHub Actions Cron & Operations
**Files classified:** 9 (7 CREATE + 2 MODIFY)
**Analogs found:** 9 / 9

### Coverage
- Files with exact analog: 5 (`run_log.py` shape, `test_run_log.py`, `test_pipeline_emits_run_log.py`, `.gitignore`, `pipeline.py` modify)
- Files with role-match analog: 4 (`refresh.yml`, `heartbeat.yml`, `test_phase8_gitignore.py`, `test_phase8_workflow_static.py`)
- Files with no analog: 0

### Key Patterns Identified
- Workflows use the 4-step uv install block verbatim from `ci.yml` lines 22-34; pinned-hash convention is 40-char SHA + two spaces + `# vX.Y.Z` trailing comment (verifier scans this).
- Publishers are thin modules: `"""publishers.<name> — <purpose>"""` docstring, `from __future__ import annotations`, three-block imports, module-level `log = structlog.get_logger(__name__)`, single public function with Google-style docstring + `log.info("<event_past_tense>", ...)` on success.
- Tests use `REPO_ROOT = Path(__file__).resolve().parents[1]`, `tmp_path` + `monkeypatch.setenv` / `monkeypatch.setattr` on module path constants, then `get_settings.cache_clear()` to defeat pydantic-settings' `@lru_cache(maxsize=1)`; failure messages always include `!r` on observed state.
- Existing `_install_pipeline_mocks` + `_setup_settings` helpers in `tests/test_pipeline_journal.py` can be reused (import or copy) for the integration test.
- `.gitignore` follows allowlist style: deny rule immediately followed by `!`-carve-out, with multi-line `# Phase N (D-XX)` header comments on each block.

### File Created
`.planning/phases/08-github-actions-cron-operations/08-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns and concrete code excerpts (with file paths + line numbers) in PLAN.md files.
