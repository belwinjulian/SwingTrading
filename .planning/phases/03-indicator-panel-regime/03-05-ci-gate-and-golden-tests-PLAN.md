---
phase: 03-indicator-panel-regime
plan: 05
type: execute
wave: 3
depends_on:
  - 03-03
  - 03-04
files_modified:
  - .github/workflows/ci.yml
  - tests/test_regime_golden.py
  - tests/test_ci_ema_grep_gate.py
autonomous: true
requirements:
  - IND-02
  - REG-04
tags:
  - ci
  - regime-golden-files
  - sma-not-ema-gate

must_haves:
  truths:
    - "CI workflow `.github/workflows/ci.yml` has a `SMA-not-EMA gate (IND-02)` step inside the existing `lint` job; the step runs `grep -ilE \"ema\" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null` and exits non-zero if any match is found (IND-02)."
    - "The grep gate uses POSIX `grep` (NOT `rg`) per RESEARCH Environment Availability — ripgrep is not preinstalled on ubuntu-latest runners; the `2>/dev/null` redirect makes the gate resilient to `signals/minervini.py` not existing yet (Phase 4 ships it; RESEARCH Pitfall 6 + Assumption A5)."
    - "Mutation test `test_ema_grep_fails_on_mutation` writes a temp file containing 'ema' and asserts the grep command would fail — proves the gate catches regressions."
    - "Three regime golden-file tests pass: 2008-Q4, 2020-Q1, 2022-H1 each classify at least one date as `Correction` (REG-04). Tests use synthetic SPY+VIX series with deterministic distribution-day positions per RESEARCH §Validation Architecture 'Golden-file fixture design'."
    - "After all Phase 3 plans complete, `uv run pytest -m 'not slow and not integration'` is green; `uv run ruff check` is green; `uv run mypy --strict` (per pyproject) on indicators/ + signals/ + regime.py is green; CI grep gate would fail if `ema` were ever introduced into trend.py."
  artifacts:
    - path: ".github/workflows/ci.yml"
      provides: "SMA-not-EMA grep step inside the existing lint job; portable POSIX grep with stderr-redirected file-missing tolerance"
      contains: "SMA-not-EMA gate (IND-02), grep -ilE"
    - path: "tests/test_regime_golden.py"
      provides: "3 golden-file tests for 2008-Q4, 2020-Q1, 2022-H1 — each must classify ≥1 date as Correction"
      exports: ["test_2008q4_correction", "test_2020q1_correction", "test_2022h1_correction"]
    - path: "tests/test_ci_ema_grep_gate.py"
      provides: "Mutation test that writes a temp file with 'ema' and asserts the grep gate would catch it"
      exports: ["test_ema_grep_fails_on_mutation", "test_ema_grep_passes_when_clean"]
  key_links:
    - from: ".github/workflows/ci.yml lint job"
      to: "src/screener/indicators/trend.py + src/screener/signals/minervini.py"
      via: "grep -ilE 'ema' over the two SMA-only files"
      pattern: "grep -ilE .ema. src/screener/signals/minervini\\.py src/screener/indicators/trend\\.py"
    - from: "tests/test_regime_golden.py"
      to: "src/screener.regime.compute_for_date"
      via: "synthetic SPY/VIX fixtures driving regime classification"
      pattern: "compute_for_date\\("
    - from: "tests/test_ci_ema_grep_gate.py"
      to: ".github/workflows/ci.yml grep step"
      via: "subprocess invocation of the same grep command CI runs"
      pattern: "subprocess\\.run.*grep -ilE"
---

<objective>
Close out Phase 3 with the two CI-gate requirements that Plans 03-01..03-04 deferred:
1. **IND-02** — CI grep gate that fails the build when `ema` (case-insensitive) is found in `src/screener/signals/minervini.py` or `src/screener/indicators/trend.py`. The mutation test in this plan proves the gate works.
2. **REG-04** — Golden-file tests for 2008-Q4, 2020-Q1, 2022-H1 that classify at least one date as `Correction` using synthetic SPY/VIX series.

Purpose: Lock in the SMA-not-EMA invariant so any future PR introducing EMA to the Trend Template fails CI before merge. Lock in the regime classifier behavior on the three canonical historical corrections so any future regression in `_classify_state` or `_compute_distribution_days` fails a specific named test.

Output:
- `.github/workflows/ci.yml` modified — `SMA-not-EMA gate (IND-02)` step added to existing `lint` job
- `tests/test_regime_golden.py` (new) — 3 golden-file tests using synthetic series
- `tests/test_ci_ema_grep_gate.py` (new) — mutation test on the grep gate
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-indicator-panel-regime/03-CONTEXT.md
@.planning/phases/03-indicator-panel-regime/03-RESEARCH.md
@.planning/phases/03-indicator-panel-regime/03-PATTERNS.md
@.planning/phases/03-indicator-panel-regime/03-VALIDATION.md
@.planning/phases/03-indicator-panel-regime/03-01-SUMMARY.md
@.planning/phases/03-indicator-panel-regime/03-02-SUMMARY.md
@.planning/phases/03-indicator-panel-regime/03-03-SUMMARY.md
@.planning/phases/03-indicator-panel-regime/03-04-SUMMARY.md

@.github/workflows/ci.yml
@src/screener/regime.py

<interfaces>
<!-- From src/screener/regime.py (Plan 03-04 added): -->
def compute_for_date(date: pd.Timestamp, panel: pd.DataFrame) -> pd.Series:
    """Returns Series with 6 fields: spy_above_200d, breadth_pct,
    distribution_days, vix_level, regime_state, regime_score."""

<!-- IND-02 grep gate command (RESEARCH Pitfall 6, Assumption A5): -->
# Files: src/screener/signals/minervini.py (Phase 4 ships) + src/screener/indicators/trend.py (Plan 03-03 ships)
# Tooling: POSIX grep (rg NOT preinstalled on ubuntu-latest)
# Resilient to missing files via 2>/dev/null (signals/minervini.py doesn't exist yet)
# Step body:
if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
  echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
  exit 1
fi

<!-- Existing lint job structure (.github/workflows/ci.yml lines 17-40): -->
lint:
  name: lint
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@...
    - name: Install uv
      uses: astral-sh/setup-uv@...
    - name: Set up Python from pyproject
      run: uv python install
    - name: Install dependencies (frozen)
      run: uv sync --frozen --extra dev
    - name: ruff format --check
      run: uv run ruff format --check .
    - name: ruff check
      run: uv run ruff check .
    # ← Insert new step here: "SMA-not-EMA gate (IND-02)"
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer PR → CI lint job | Developer may inadvertently add EMA-based code to the Trend Template; the grep gate is the static-analysis trust boundary. |
| synthetic test data → regime classifier | REG-04 golden-file tests use synthetic series; the test trust boundary is "deterministic distribution-day injection produces deterministic classification." |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 | Tampering | CI lint job EMA grep | mitigate | Mutation test (test_ema_grep_fails_on_mutation) writes a temp file containing 'ema' to a copied tree and runs the same grep command CI runs; asserts the gate would have failed. Prevents "gate present but doesn't actually catch regressions" silent-failure mode. |
| T-3-04 | Tampering | regime classifier behavior | mitigate | Three golden-file tests (REG-04) freeze the classifier behavior on canonical historical corrections (2008-Q4, 2020-Q1, 2022-H1); any change to _classify_state thresholds or _compute_distribution_days idiom fails a specific named test. |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add SMA-not-EMA grep step to ci.yml + write mutation test</name>
  <files>.github/workflows/ci.yml, tests/test_ci_ema_grep_gate.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/.github/workflows/ci.yml (full file — single-job structure; ruff check step is the insertion-point predecessor)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Pitfall 6 lines 489-506 — exact CI step body with `2>/dev/null` rationale; Assumption A5 lines 819 — Phase 4 file may not exist; Environment Availability table line 866 — rg not on ubuntu-latest)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 765-808 — ci.yml step pattern; cautions about file-existence edge case)
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/indicators/trend.py (Plan 03-03 — verify zero `ema` matches)
  </read_first>
  <behavior>
    - Test: `bash -c "grep -ilE \"ema\" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null"` exits 1 (no matches; signals/minervini.py doesn't exist yet, trend.py is clean) — gate passes for current state.
    - Test: When a temp copy of trend.py is created with `# ema reference` injected and the same grep command is run on it, the command exits 0 (match found) — proves the mutation would fail CI.
    - Test: When a temp copy of trend.py is created with no ema content (clean), the same grep command exits 1.
    - Test: `.github/workflows/ci.yml` contains the `SMA-not-EMA gate (IND-02)` step name and the verbatim grep command from RESEARCH Pitfall 6.
    - Test: The grep step is positioned within the existing `lint` job (not a new job — keeps single-runner invariant).
  </behavior>
  <action>
**Step A — Add the grep step to `.github/workflows/ci.yml`.**

Open the file and locate the `lint` job (around line 17). Find the `ruff check` step (around line 40, the last step in lint). Insert the new step DIRECTLY AFTER `ruff check`, BEFORE the next job (`typecheck` or whatever comes next):

```yaml
      - name: SMA-not-EMA gate (IND-02)
        run: |
          if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
            echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
            exit 1
          fi
```

CRITICAL details (RESEARCH Pitfall 6 + Assumption A5):
- `2>/dev/null` REQUIRED — `signals/minervini.py` doesn't exist until Phase 4; without stderr redirect, `grep` exits with status 2 (file not found) and CI fails spuriously.
- `-i` for case-insensitive (catches `EMA`, `Ema`, `ema`).
- `-l` lists matched filenames (changes exit-status-on-match semantics: 0 if any match found, 1 if none).
- `-E` for extended regex (forward-compatible if pattern grows).
- Use POSIX `grep`, NOT `rg` — ripgrep is not preinstalled on `ubuntu-latest` (RESEARCH Environment Availability line 866).
- The `if grep ...; then exit 1; fi` shell guard interprets exit 0 (match found) as the failure path.

Indent under `steps:` to match the existing pattern. The step name MUST be exactly `SMA-not-EMA gate (IND-02)` so cross-references in docs and future grep gates can find it.

**Step B — Create `tests/test_ci_ema_grep_gate.py`** (mutation test):

```python
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

import pytest

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
        f"grep -ilE \"ema\" {' '.join(str(p) for p in TARGETS)} 2>/dev/null",
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
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_ci_ema_grep_gate.py -x -q && bash -c 'if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then echo "FAIL: ema match found"; exit 1; else echo "PASS: gate clean"; fi'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "SMA-not-EMA gate (IND-02)" .github/workflows/ci.yml` returns 1.
    - `grep -c 'grep -ilE "ema"' .github/workflows/ci.yml` returns 1.
    - `grep -c "2>/dev/null" .github/workflows/ci.yml` returns at least 1 (stderr redirect for the gate step).
    - The grep step is contained within the `lint:` job — confirmed by the YAML structure (no new top-level job added). Verify by `grep -c "^  lint:" .github/workflows/ci.yml` returning 1 and `grep -c "^  typecheck:\\|^  test:" .github/workflows/ci.yml` unchanged from before this plan.
    - `tests/test_ci_ema_grep_gate.py` exists with 3 tests.
    - `grep -c "^def test_ema_grep_passes_when_clean" tests/test_ci_ema_grep_gate.py` returns 1.
    - `grep -c "^def test_ema_grep_fails_on_mutation" tests/test_ci_ema_grep_gate.py` returns 1.
    - `grep -c "^def test_ema_grep_fails_on_uppercase_mutation" tests/test_ci_ema_grep_gate.py` returns 1.
    - `uv run pytest tests/test_ci_ema_grep_gate.py -x -q` exits 0 (all 3 mutation tests pass).
    - On the current clean codebase, `bash -c 'if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then exit 1; else exit 0; fi'` exits 0 (gate clean).
    - `uv run ruff check tests/test_ci_ema_grep_gate.py` exits 0.
    - YAML is well-formed: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0.
  </acceptance_criteria>
  <done>CI grep step added to existing lint job (single runner — no new jobs); mutation test confirms gate catches lowercase + uppercase mutations; gate passes on current clean code; YAML well-formed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write 3 REG-04 golden-file tests using synthetic SPY/VIX fixtures</name>
  <files>tests/test_regime_golden.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-CONTEXT.md ("Claude's Discretion" lines 97-99 — 3 fixture date ranges: 2008-Q4 (2008-10-01 to 2009-03-01), 2020-Q1 (2020-02-15 to 2020-04-15), 2022-H1 (2022-01-01 to 2022-07-01); each must include ≥1 Correction)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Open Question 4 lines 840-843 — recommendation: synthetic series with deterministic dist-day positions; Validation Architecture lines 913-915 — golden-file test signatures)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 1054-1080 — synthetic SPY+VIX fixture pattern)
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/regime.py (Plan 03-04 — confirm compute_for_date signature and the 6 output fields)
  </read_first>
  <behavior>
    - Test: `synthetic_spy_2008q4` fixture has dates spanning 2008-10-01 to 2009-03-01 with SPY close crossing below 200d SMA and elevated distribution days.
    - Test: `synthetic_spy_2020q1` fixture has dates 2020-02-15 to 2020-04-15 with a sharp drop below 200d SMA and ≥9 dist days at some point (COVID crash).
    - Test: `synthetic_spy_2022h1` fixture has dates 2022-01-01 to 2022-07-01 with SPY drifting below 200d SMA + dist day buildup.
    - Test: `synthetic_vix_2008q4` / `synthetic_vix_2020q1` / `synthetic_vix_2022h1` fixtures have at least one date with VIX ≥ 30 (Correction trigger D-01).
    - Test: `test_2008q4_correction` — for at least one date in the 2008-Q4 range, `compute_for_date(date, panel).regime_state == "Correction"`.
    - Test: `test_2020q1_correction` — same for 2020-Q1.
    - Test: `test_2022h1_correction` — same for 2022-H1.
  </behavior>
  <action>
**Step A — Define golden-file SPY/VIX fixtures inside `tests/test_regime_golden.py`** (NOT in conftest — keeps Plan 03-05's `files_modified` orthogonal to Plan 03-04's, removing the same-wave file-overlap; the fixtures are only used by REG-04 tests so module-local scope is correct):

```python
def _make_synthetic_spy_for_correction(
    start: str, end: str, sma_break_dates: list[str],
) -> pd.DataFrame:
    """Build a synthetic SPY OHLCV series whose close crosses below 200d SMA
    at known dates and has injected distribution days. Deterministic — used
    by REG-04 golden-file tests.
    """
    # Pre-pad with 250 calendar days of stable price so SMA200 is well-defined
    # at the start of the test window.
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    idx = pd.bdate_range(start=pad_start, end=end)
    close = np.full(len(idx), 100.0)
    volume = np.full(len(idx), 1_000_000, dtype="int64")
    for d in sma_break_dates:
        ts = pd.Timestamp(d)
        if ts in idx:
            i = idx.get_loc(ts)
            close[i:] *= 0.7  # 30% drop persisting forward
    # Inject 10 strict-IBD distribution days uniformly across the post-break window.
    if sma_break_dates:
        first_break = pd.Timestamp(sma_break_dates[0])
        post = idx[idx >= first_break]
        if len(post) >= 12:
            for offset in (1, 3, 5, 7, 9, 11, 13, 15, 17, 19):
                if offset < len(post):
                    j = idx.get_loc(post[offset])
                    if j > 0:
                        close[j] = close[j - 1] * 0.99   # 1% drop > 0.2%
                        volume[j] = int(volume[j - 1] * 1.5)  # higher volume
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": volume,
        },
        index=pd.DatetimeIndex(idx, name="date"),
    )


def _make_synthetic_vix_for_correction(
    start: str, end: str, panic_dates: list[str], panic_level: float = 35.0,
) -> pd.DataFrame:
    """VIX with calm baseline (15) + panic spikes (>=30) on specified dates."""
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    idx = pd.bdate_range(start=pad_start, end=end)
    close = np.full(len(idx), 15.0)
    for d in panic_dates:
        ts = pd.Timestamp(d)
        if ts in idx:
            i = idx.get_loc(ts)
            # 5-day panic plateau
            for k in range(min(5, len(idx) - i)):
                close[i + k] = panic_level
    return pd.DataFrame(
        {"close": close},
        index=pd.DatetimeIndex(idx, name="date"),
    )


@pytest.fixture(scope="session")
def synthetic_spy_2008q4() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2008-10-01", end="2009-03-01",
        sma_break_dates=["2008-10-06"],
    )


@pytest.fixture(scope="session")
def synthetic_spy_2020q1() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2020-02-15", end="2020-04-15",
        sma_break_dates=["2020-02-25"],
    )


@pytest.fixture(scope="session")
def synthetic_spy_2022h1() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2022-01-01", end="2022-07-01",
        sma_break_dates=["2022-01-20"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2008q4() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2008-10-01", end="2009-03-01",
        panic_dates=["2008-10-10", "2008-11-20"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2020q1() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2020-02-15", end="2020-04-15",
        panic_dates=["2020-03-09", "2020-03-16"],
    )


@pytest.fixture(scope="session")
def synthetic_vix_2022h1() -> pd.DataFrame:
    return _make_synthetic_vix_for_correction(
        start="2022-01-01", end="2022-07-01",
        panic_dates=["2022-02-24", "2022-06-13"],
    )
```

**Step B — Create `tests/test_regime_golden.py`:**

```python
"""REG-04 golden-file regime tests.

Each of the three canonical historical corrections (2008-Q4, 2020-Q1, 2022-H1)
must classify at least one date in its window as 'Correction'. Tests use
synthetic SPY/VIX series with deterministic distribution-day and SMA-break
positions per RESEARCH Open Question 4 recommendation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from screener.regime import compute_for_date


def _setup_macro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
) -> None:
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    spy_df.to_parquet(macro_dir / "spy.parquet", engine="pyarrow", index=True)
    vix_df.to_parquet(macro_dir / "vix.parquet", engine="pyarrow", index=True)


def _trivial_panel(date: pd.Timestamp, n_tickers: int = 5) -> pd.DataFrame:
    """A trivial indicator-panel with 5 tickers, all close > sma_200 (high
    breadth). Real Correction signal has to come from SPY-below-200d, VIX≥30,
    or dist-days, not breadth.
    """
    tickers = [f"TKR{i}" for i in range(n_tickers)]
    rows = []
    idx_pairs = []
    for t in tickers:
        idx_pairs.append((t, date))
        rows.append({"close": 110.0, "sma_200": 100.0})
    return pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"]),
    )


def _scan_for_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    window_start: str,
    window_end: str,
) -> bool:
    """Walk dates in [window_start, window_end] and return True on first Correction."""
    _setup_macro(tmp_path, monkeypatch, spy_df, vix_df)
    candidate_dates = [
        d for d in spy_df.index
        if pd.Timestamp(window_start) <= d <= pd.Timestamp(window_end)
    ]
    for d in candidate_dates:
        panel = _trivial_panel(d)
        out = compute_for_date(d, panel)
        if out["regime_state"] == "Correction":
            return True
    return False


def test_2008q4_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2008q4: pd.DataFrame,
    synthetic_vix_2008q4: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path, monkeypatch,
        synthetic_spy_2008q4, synthetic_vix_2008q4,
        "2008-10-01", "2009-03-01",
    )
    assert found, "2008-Q4 fixture must classify at least one date as Correction"


def test_2020q1_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2020q1: pd.DataFrame,
    synthetic_vix_2020q1: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path, monkeypatch,
        synthetic_spy_2020q1, synthetic_vix_2020q1,
        "2020-02-15", "2020-04-15",
    )
    assert found, "2020-Q1 fixture must classify at least one date as Correction"


def test_2022h1_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_2022h1: pd.DataFrame,
    synthetic_vix_2022h1: pd.DataFrame,
) -> None:
    found = _scan_for_correction(
        tmp_path, monkeypatch,
        synthetic_spy_2022h1, synthetic_vix_2022h1,
        "2022-01-01", "2022-07-01",
    )
    assert found, "2022-H1 fixture must classify at least one date as Correction"
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_regime_golden.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_regime_golden.py` exists with 3 tests.
    - `grep -c "^def test_2008q4_correction" tests/test_regime_golden.py` returns 1.
    - `grep -c "^def test_2020q1_correction" tests/test_regime_golden.py` returns 1.
    - `grep -c "^def test_2022h1_correction" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_spy_2008q4" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_spy_2020q1" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_spy_2022h1" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_vix_2008q4" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_vix_2020q1" tests/test_regime_golden.py` returns 1.
    - `grep -c "synthetic_vix_2022h1" tests/test_regime_golden.py` returns 1.
    - `uv run pytest tests/test_regime_golden.py -x -q` exits 0 (all 3 tests pass — at least one Correction per window).
    - `uv run ruff check tests/test_regime_golden.py` exits 0.
    - `uv run pytest -m "not slow and not integration" -x -q` exits 0 (full Phase 3 suite green).
  </acceptance_criteria>
  <done>3 REG-04 golden-file tests pass with deterministic synthetic SPY/VIX fixtures defined inside test_regime_golden.py (no conftest modification — fixtures scoped to this test module); ruff clean; full quick suite green.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_regime_golden.py tests/test_ci_ema_grep_gate.py -x -q` exits 0
- Full Phase 3 quick suite: `uv run pytest -m "not slow and not integration" -x -q` exits 0
- `uv run ruff check src/ tests/ .github/` exits 0 (note: ruff doesn't lint YAML; included for completeness)
- `uv run mypy --config-file pyproject.toml src/screener/indicators/ src/screener/regime.py` exits 0
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0 (YAML well-formed)
- `bash -c 'if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then exit 1; else exit 0; fi'` exits 0 (gate clean on current state)
- IND-02 gate would catch a regression — `tests/test_ci_ema_grep_gate.py::test_ema_grep_fails_on_mutation` passes
- All Phase 1+2+3 tests green
</verification>

<success_criteria>
- IND-02 CI gate (`SMA-not-EMA gate (IND-02)`) added to existing `lint` job in `.github/workflows/ci.yml` — uses POSIX grep with `2>/dev/null` for file-existence resilience
- Mutation test `test_ema_grep_fails_on_mutation` proves the gate catches lowercase + uppercase EMA regressions
- 3 REG-04 golden-file tests pass: `test_2008q4_correction`, `test_2020q1_correction`, `test_2022h1_correction` — each scans its date range and asserts ≥1 day classifies as Correction
- 6 synthetic SPY/VIX fixtures in tests/test_regime_golden.py (deterministic SMA-break + panic-VIX + dist-day injection) — sufficient for REG-04 without requiring real macro Parquets at test time; module-local scope keeps the file ownership orthogonal to other plans
- Full Phase 3 test suite green: indicators + macro + regime + golden-file + ema-mutation
- ruff + mypy clean; YAML well-formed
- Phase 3 ROADMAP success criterion 3 satisfied: `rg "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` (or POSIX grep equivalent) returns zero matches; introducing an EMA reference fails CI
- Phase 3 ROADMAP success criterion 4 satisfied: regime golden-file tests pass for 2008-Q4 / 2020-Q1 / 2022-H1
</success_criteria>

<output>
After completion, create `.planning/phases/03-indicator-panel-regime/03-05-SUMMARY.md` documenting the IND-02 grep gate (step name, exact command, file-existence safeguard, mutation-test coverage) and the REG-04 golden-file approach (synthetic-series rationale, fixture deterministic constants, verified ≥1 Correction per window). Note any deviations and confirm Phase 3 is ready for `/gsd-verify-phase`.
</output>
