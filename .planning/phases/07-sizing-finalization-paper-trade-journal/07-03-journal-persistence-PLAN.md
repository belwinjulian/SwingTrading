---
phase: 07-sizing-finalization-paper-trade-journal
plan: "03"
type: execute
wave: 1
depends_on: ["07-01"]
files_modified:
  - src/screener/persistence.py
  - tests/test_journal.py
autonomous: true
requirements: [OUT-04, OUT-05, OUT-06]
requirements_addressed: [OUT-04, OUT-05, OUT-06]
tags: [phase-7, persistence, sqlite, picks-table, immutability-trigger, idempotent-append, pandera-schema]

must_haves:
  truths:
    - "src/screener/persistence.py exposes _PICKS_DDL (Final[str]) containing TABLE + 2 INDEXes + immutability TRIGGER, ALL inside one executescript per RESEARCH Pitfall 1"
    - "src/screener/persistence.py exposes _journal_db_path() resolver (mirrors _insider_db_path idiom)"
    - "src/screener/persistence.py exposes _ensure_picks_schema(db_path=None) → Path (idempotent: CREATE ... IF NOT EXISTS on table + indexes + trigger)"
    - "src/screener/persistence.py exposes append_picks_rows(rows, db_path=None) → int — INSERT OR IGNORE on UNIQUE(ticker, snapshot_date); returns cur.rowcount inserted"
    - "src/screener/persistence.py exposes read_picks_for_date(snapshot_date, db_path=None) → pd.DataFrame (mirrors read_insider_cluster_buy idiom)"
    - "src/screener/persistence.py exposes PicksSchema (pandera DataFrameModel) — pre-insert validation contract for the picks SQLite table"
    - "Decision columns (12 NOT NULL + ingested_at + 1 nullable: pivot_distance_atr_breakout) immutable via trigger; outcome columns (6 nullable) explicitly NOT in trigger OF-list"
    - "9 of 10 tests in tests/test_journal.py have real bodies and pass; test_journal_cli_idempotent remains pytest.skip('Plan 07-05')"
  artifacts:
    - path: "src/screener/persistence.py"
      provides: "_PICKS_DDL + _journal_db_path + _ensure_picks_schema + append_picks_rows + read_picks_for_date + PicksSchema"
      contains: "CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols"
    - path: "tests/test_journal.py"
      provides: "9 real test bodies + 1 skeleton skipped for Plan 07-05"
      contains: "sqlite3.IntegrityError"
  key_links:
    - from: "src/screener/persistence._ensure_picks_schema"
      to: "data/journal.sqlite SQLite file"
      via: "conn.executescript(_PICKS_DDL)"
      pattern: "executescript\\(_PICKS_DDL\\)"
    - from: "src/screener/persistence.append_picks_rows"
      to: "picks table"
      via: "INSERT OR IGNORE INTO picks ... VALUES (:ticker, :snapshot_date, ...)"
      pattern: "INSERT OR IGNORE INTO picks"
    - from: "src/screener/persistence.PicksSchema"
      to: "publishers/pipeline._build_journal_rows_df (Plan 07-04)"
      via: "validate_at_write(PicksSchema, df) before append_picks_rows"
      pattern: "class PicksSchema"

user_setup: []
---

<objective>
Wave 1 implementation of the journal persistence layer in `src/screener/persistence.py`: ship `_PICKS_DDL` (table + 2 indexes + immutability trigger, all in one executescript per Pitfall 1), `_journal_db_path`, `_ensure_picks_schema`, `append_picks_rows`, `read_picks_for_date`, and `PicksSchema` (pandera DataFrameModel). Land real bodies in 9 of 10 skeletons in `tests/test_journal.py` (test_journal_cli_idempotent waits for Plan 07-05).

Purpose: OUT-04..06 SQLite layer. Plan 07-04 (pipeline wiring) calls `append_picks_rows`; Plan 07-05 (CLI body) uses `read_picks_for_date`. Parallel-safe with Plan 07-02 (zero file overlap — persistence.py + test_journal.py vs sizing.py + test_sizing.py).

Output: ~150 net new lines in persistence.py, 9 passing tests + 1 deferred skip in test_journal.py, FND-04 gate still green, D-24 surface lock unchanged.

**Revision iteration 1 Warning #5:** PicksSchema column `pivot_distance_atr` renamed to `pivot_distance_atr_breakout` for self-consistency — Plan 07-04 populates the column from sizing.py's `pivot_distance_atr_breakout` value ((close - pivot)/atr; the breakout sign convention), which is structurally different from Phase 4's snapshot `pivot_distance_atr` ((high_52w - close)/atr; the 52w-high distance). Renaming eliminates the cross-file value/name mismatch. The column is now nullable (some actionable picks — e.g. leader_hold — have no breakout pivot).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-01-foundation-settings-schemas-fixtures-PLAN.md
@.planning/phases/02-data-foundation/02-CONTEXT.md
@CLAUDE.md
@src/screener/persistence.py

<interfaces>
<!-- Key types and contracts extracted from the codebase. Use these directly. -->

Existing SQLite-helpers analog in src/screener/persistence.py:

- `_FORM4_DDL: Final[str]` at lines 891-906 — Form 4 table DDL
- `_FORM4_IDX: Final[str]` — index DDL (single CREATE INDEX line)
- `_insider_db_path()` at lines 461-464 — path resolver via `getattr(get_settings(), ...)`
- `_ensure_insider_schema(db_path: "Path | None" = None) -> Path` at lines 909-916 — idempotent setup
- `append_form4_rows(db_path, rows)` at lines 919-944 — append-only via `ON CONFLICT(filing_id) DO NOTHING`
- `read_insider_cluster_buy(...)` at lines ~1001-1006 — read pattern using `pd.read_sql_query`

Existing pandera DataFrameModel analog (InsiderSchema, lines 306-326):
```python
class InsiderSchema(pa.DataFrameModel):
    filing_id: Series[str] = pa.Field(nullable=False, unique=True)
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    insider: Series[str] = pa.Field(nullable=False)
    transaction_date: Series[str] = pa.Field(nullable=False, str_matches=r"^\d{4}-\d{2}-\d{2}$")
    type: Series[str] = pa.Field(nullable=False, isin=["P", "S"])
    shares: Series[float] = pa.Field(ge=0.0, nullable=False)
    value_usd: Series[float] = pa.Field(ge=0.0, nullable=False)
    ingested_at: Series[str] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False
```

Existing imports at top of persistence.py (already in scope):
- `import sqlite3`, `import tempfile`, `from pathlib import Path`
- `import pandas as pd`, `import pandera as pa`
- `from pandera.typing import Series`
- `import structlog`; `log = structlog.get_logger(__name__)`
- `from screener.config import get_settings`
- `from typing import Any, Final` (Any used by _insider_db_path; Final is also imported)

Settings field available (Plan 07-01 Task 1):
- `settings.JOURNAL_DB_PATH: Path = Path("data/journal.sqlite")`

Empirically-verified SQLite behavior (RESEARCH §Code Examples Pattern 4, executed 2026-05-18 against sqlite 3.51.0):
- `BEFORE UPDATE OF <col>` trigger column-list order is NOT semantically significant
- `INSERT OR IGNORE` returns the actual insert count via `cur.rowcount`
- UPDATE on a column NOT in the OF list succeeds without trigger fire
- AUTOINCREMENT id gaps appear on idempotent re-runs (Pitfall 2)

Existing validate_at_write helper (persistence.py:356):
```python
def validate_at_write(schema_cls: type[pa.DataFrameModel], df: pd.DataFrame) -> pd.DataFrame:
    """Eager validation (lazy=False): fail on first error. Use at write boundary."""
    return schema_cls.validate(df, lazy=False)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _PICKS_DDL + _journal_db_path + _ensure_picks_schema + PicksSchema to persistence.py</name>
  <files>src/screener/persistence.py</files>
  <read_first>
    - src/screener/persistence.py lines 306-330 (existing InsiderSchema — analog for PicksSchema)
    - src/screener/persistence.py lines 460-470 (existing _insider_db_path — analog for _journal_db_path)
    - src/screener/persistence.py lines 880-945 (existing _FORM4_DDL + _ensure_insider_schema + append_form4_rows — analog for journal helpers)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Code Examples" Pattern 1 (full DDL verbatim) + Pattern 4 (empirical SQLite verification)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/persistence.py — Journal SQLite helpers"
  </read_first>
  <behavior>
    - `from screener.persistence import _PICKS_DDL, _journal_db_path, _ensure_picks_schema, PicksSchema` succeeds
    - `_PICKS_DDL` contains exactly: `CREATE TABLE IF NOT EXISTS picks`, `CREATE INDEX IF NOT EXISTS idx_picks_snapshot_date`, `CREATE INDEX IF NOT EXISTS idx_picks_ticker`, `CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols`
    - `_journal_db_path()` returns `Path("data/journal.sqlite")` by default
    - `_ensure_picks_schema(tmp_path / "j.sqlite")` creates the SQLite file with the table, both indexes, and the trigger; second call is a no-op
    - `PicksSchema.validate(...)` rejects invalid playbook_tag and invalid atr_zone with pandera SchemaError
  </behavior>
  <action>
**A. PicksSchema DataFrameModel** — append AFTER `InsiderSchema` at line 326 in `src/screener/persistence.py`:

```python


class PicksSchema(pa.DataFrameModel):
    """Pre-insert validation contract for the picks SQLite table (Phase 7 / OUT-04..05).

    Caller (publishers/pipeline._build_journal_rows_df in Plan 07-04, and
    cli.journal in Plan 07-05) MUST validate the DataFrame view through this
    schema BEFORE invoking persistence.append_picks_rows — mirrors the
    InsiderSchema "Pattern B" contract documented on append_form4_rows.

    The schema covers the 13 decision columns required by INSERT OR IGNORE
    plus ingested_at (the 14th NOT NULL column in the table). The 6 outcome
    columns (entry_filled, exit_price, exit_date, hold_days, mfe, mae) are
    NOT part of this schema — they are NULL on initial insert and updated by
    the deferred v1.x journal-update flow (CONTEXT D-10).

    Pandera regex on snapshot_date is the path-traversal defense (T-06-25
    carry-forward) — there is no separate _assert_safe call.
    """

    ticker: Series[str] = pa.Field(
        nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$"
    )
    snapshot_date: Series[str] = pa.Field(
        nullable=False, str_matches=r"^\d{4}-\d{2}-\d{2}$"
    )
    playbook_tag: Series[str] = pa.Field(
        isin=["qullamaggie_continuation", "minervini_vcp", "leader_hold"],
        nullable=False,
    )
    composite_score: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=False)
    regime_state: Series[str] = pa.Field(
        isin=["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"],
        nullable=False,
    )
    entry_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    stop_price: Series[float] = pa.Field(gt=0.0, nullable=False)
    shares: Series[int] = pa.Field(ge=0, nullable=False)
    risk_per_share: Series[float] = pa.Field(ge=0.0, nullable=False)
    atr_zone: Series[str] = pa.Field(
        isin=["in-zone", "extended", "chase, skip"], nullable=False,
    )
    # Phase 7 revision iteration 1 Warning #5: column name aligned with the
    # value source (sizing.py emits `pivot_distance_atr_breakout` = (close - pivot)/atr;
    # this is the breakout sign convention, distinct from Phase 4's snapshot
    # `pivot_distance_atr` which is (high_52w - close)/atr).
    pivot_distance_atr_breakout: Series[float] = pa.Field(nullable=True)
    features_json: Series[str] = pa.Field(nullable=False)
    ingested_at: Series[str] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = False
```

**B. _PICKS_DDL + _journal_db_path + _ensure_picks_schema** — append AFTER the existing `_ensure_insider_schema` function (search for `def _ensure_insider_schema` in persistence.py to find the location; the Phase 7 block goes immediately after the function body, before any other helper):

```python


# --- Phase 7: picks journal table (CONTEXT D-01 / D-02 / OUT-04..06) -----

_PICKS_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Decision columns (NOT NULL, immutable via trigger below)
    ticker TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    playbook_tag TEXT NOT NULL CHECK (playbook_tag IN
        ('qullamaggie_continuation', 'minervini_vcp', 'leader_hold')),
    composite_score REAL NOT NULL,
    regime_state TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_price REAL NOT NULL,
    shares INTEGER NOT NULL,
    risk_per_share REAL NOT NULL,
    atr_zone TEXT NOT NULL CHECK (atr_zone IN ('in-zone', 'extended', 'chase, skip')),
    pivot_distance_atr_breakout REAL,
    features_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    -- Outcome columns (nullable, updatable — explicitly excluded from trigger)
    entry_filled INTEGER,
    exit_price REAL,
    exit_date TEXT,
    hold_days INTEGER,
    mfe REAL,
    mae REAL,
    -- Idempotency key for INSERT OR IGNORE (CONTEXT D-01).
    -- Note: AUTOINCREMENT id WILL have gaps on idempotent re-runs (Pitfall 2);
    -- use (ticker, snapshot_date) as the natural key for any downstream queries.
    UNIQUE (ticker, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_picks_snapshot_date ON picks (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_picks_ticker ON picks (ticker);
CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols
BEFORE UPDATE OF
    ticker, snapshot_date, playbook_tag, composite_score, regime_state,
    entry_price, stop_price, shares, risk_per_share, atr_zone,
    pivot_distance_atr_breakout, features_json, ingested_at
ON picks
BEGIN
    SELECT RAISE(ABORT, 'decision column immutable');
END;
"""


def _journal_db_path() -> Path:
    """Resolve the picks journal SQLite path (Phase 7 D-01/D-02), with fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "JOURNAL_DB_PATH", "data/journal.sqlite"))


def _ensure_picks_schema(db_path: "Path | None" = None) -> Path:
    """Idempotent picks table + indexes + immutability trigger.

    All four DDL statements (table, 2 indexes, trigger) run inside ONE
    `executescript` so a future table-rebuild migration (DROP + CREATE)
    cannot leave the trigger missing (RESEARCH Pitfall 1). All four
    statements use `CREATE ... IF NOT EXISTS` so re-invocation is a no-op.
    """
    path = Path(db_path) if db_path is not None else _journal_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_PICKS_DDL)
    return path
```

If `from typing import Any, Final` is not already in persistence.py's imports, add it. (It should be — `_insider_db_path` uses `Any`, and other constants use `Final`.)

DO NOT add `append_picks_rows` or `read_picks_for_date` in this task — they land in Task 2 to keep the diff focused.
  </action>
  <verify>
    <automated>uv run python -c "import tempfile, sqlite3; from pathlib import Path; from screener.persistence import _PICKS_DDL, _journal_db_path, _ensure_picks_schema, PicksSchema; assert 'CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols' in _PICKS_DDL; assert 'UNIQUE (ticker, snapshot_date)' in _PICKS_DDL; assert 'CREATE INDEX IF NOT EXISTS idx_picks_snapshot_date' in _PICKS_DDL; assert 'CREATE INDEX IF NOT EXISTS idx_picks_ticker' in _PICKS_DDL; tmp = Path(tempfile.mkdtemp()) / 'j.sqlite'; p = _ensure_picks_schema(tmp); p2 = _ensure_picks_schema(tmp); assert p == p2 == tmp; assert p.exists(); conn = sqlite3.connect(p); rows = conn.execute(\"SELECT name FROM sqlite_master WHERE type IN ('table','index','trigger') ORDER BY name\").fetchall(); names = [r[0] for r in rows]; assert 'picks' in names; assert 'idx_picks_snapshot_date' in names; assert 'idx_picks_ticker' in names; assert 'picks_immutable_decision_cols' in names; print('PICKS schema OK:', names)"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE "^_PICKS_DDL: Final\[str\]" src/screener/persistence.py` outputs `1`
    - `grep -cE "^def _journal_db_path\(" src/screener/persistence.py` outputs `1`
    - `grep -cE "^def _ensure_picks_schema\(" src/screener/persistence.py` outputs `1`
    - `grep -cE "^class PicksSchema\(" src/screener/persistence.py` outputs `1`
    - `grep -c "CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols" src/screener/persistence.py` outputs `1`
    - `grep -c "UNIQUE (ticker, snapshot_date)" src/screener/persistence.py` outputs `1`
    - `grep -c "CREATE INDEX IF NOT EXISTS idx_picks_snapshot_date" src/screener/persistence.py` outputs `1`
    - `grep -c "CREATE INDEX IF NOT EXISTS idx_picks_ticker" src/screener/persistence.py` outputs `1`
    - Python smoke check (verify command above) prints `PICKS schema OK: [...]` with all four object names present
    - `uv run pytest tests/test_architecture.py -x --no-cov` passes (D-23 ALLOWED dict unchanged)
    - `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov` passes (D-24 lock intact)
  </acceptance_criteria>
  <done>
    persistence.py has _PICKS_DDL constant, _journal_db_path resolver, _ensure_picks_schema function, PicksSchema DataFrameModel. SQLite file creation is idempotent (Pitfall 1 mitigation). All four schema objects (table + 2 indexes + trigger) created in one executescript. No existing test regressions.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add append_picks_rows + read_picks_for_date to persistence.py + land bodies in 9 of 10 test_journal.py skeletons</name>
  <files>src/screener/persistence.py, tests/test_journal.py</files>
  <read_first>
    - src/screener/persistence.py (file after Task 1 — _PICKS_DDL + _ensure_picks_schema + PicksSchema exist)
    - src/screener/persistence.py lines 919-944 (existing `append_form4_rows` — analog for append_picks_rows)
    - src/screener/persistence.py lines ~1001-1006 (existing `read_insider_cluster_buy` — analog for read_picks_for_date)
    - tests/test_journal.py (10 pytest.skip skeletons from Plan 07-01 Task 3)
    - tests/test_insider_io.py (analog for the tmp_path + monkeypatch + get_settings.cache_clear test idiom — see RESEARCH §"tests/test_journal.py")
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Code Examples" Pattern 2 (append_picks_rows verbatim) + Pattern 4 (empirical SQLite test to base test_immutability_trigger + test_idempotent_append on)
  </read_first>
  <behavior>
    - `append_picks_rows(rows, db_path)` returns the count of rows actually inserted (silent skip on UNIQUE violation)
    - `append_picks_rows([])` returns 0 immediately (early-return on empty list)
    - `read_picks_for_date(snapshot_date, db_path)` returns a pd.DataFrame ordered by composite_score DESC; empty DataFrame when no rows match
    - 9 of 10 tests in tests/test_journal.py pass (test_journal_cli_idempotent remains pytest.skip('Plan 07-05'))
    - test_immutability_trigger: UPDATE on any of the 13 decision columns raises sqlite3.IntegrityError with message 'decision column immutable'
    - test_outcome_column_updatable: UPDATE on exit_price (or any of the 5 other outcome cols) succeeds and persists
    - test_outcome_col_not_in_trigger: UPDATE on exit_price succeeds AND a subsequent SELECT returns the new value
    - test_idempotent_append: mixed batch [insertable, duplicate, duplicate] → cur.rowcount == 1; SELECT COUNT(*) afterwards == sum of unique
    - test_features_json_roundtrip: features_json column is preserved verbatim as TEXT; json.loads(value) returns the original dict
    - test_features_json_includes_diagnostics: features_json embeds the full Phase 6 D-05 pattern_diagnostics keys when present
    - test_schema_idempotent_recreates_trigger: DROP TABLE picks + re-call _ensure_picks_schema + INSERT row + try UPDATE on ticker → raises IntegrityError
    - test_picks_schema_rejects_invalid_playbook_tag: PicksSchema.validate(df with bad playbook_tag) raises pandera SchemaError
    - test_picks_schema_rejects_invalid_atr_zone: PicksSchema.validate(df with bad atr_zone) raises pandera SchemaError
  </behavior>
  <action>
**A. Append `append_picks_rows` and `read_picks_for_date` to persistence.py** — place AFTER `_ensure_picks_schema` (from Task 1):

```python


def append_picks_rows(rows: list[dict], db_path: "Path | None" = None) -> int:
    """Idempotent append — INSERT OR IGNORE on UNIQUE(ticker, snapshot_date).

    Caller MUST pandera-validate as PicksSchema BEFORE calling (Pattern B —
    same contract documented on append_form4_rows). This function trusts that
    validation has already run and performs only the SQL insert.

    Returns the rowcount actually inserted (0 on a full-duplicate batch);
    skipped duplicates are silent (Pitfall 2 — AUTOINCREMENT id WILL still
    advance for skipped rows; do NOT rely on id semantically).

    Args:
        rows: list of dicts with the 13 decision keys required by INSERT OR
            IGNORE INTO picks plus ingested_at. Each row's keys must match
            the named placeholders exactly.
        db_path: optional path override (test fixtures pass `tmp_path / 'j.sqlite'`).
    """
    if not rows:
        return 0
    path = _ensure_picks_schema(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.executemany(
            """INSERT OR IGNORE INTO picks
               (ticker, snapshot_date, playbook_tag, composite_score,
                regime_state, entry_price, stop_price, shares,
                risk_per_share, atr_zone, pivot_distance_atr_breakout,
                features_json, ingested_at)
               VALUES (:ticker, :snapshot_date, :playbook_tag, :composite_score,
                       :regime_state, :entry_price, :stop_price, :shares,
                       :risk_per_share, :atr_zone, :pivot_distance_atr_breakout,
                       :features_json, :ingested_at)""",
            rows,
        )
        conn.commit()
        n_inserted = cur.rowcount
    log.info(
        "journal_appended",
        n_attempted=len(rows),
        n_inserted=n_inserted,
        n_idempotent_skip=len(rows) - n_inserted,
    )
    return n_inserted


def read_picks_for_date(
    snapshot_date: str, db_path: "Path | None" = None
) -> pd.DataFrame:
    """Read picks rows for a single snapshot_date, ordered by composite_score DESC.

    Returns an empty DataFrame (with the picks table columns) if no rows match.
    Mirrors `read_insider_cluster_buy`'s `pd.read_sql_query` idiom.
    """
    path = _ensure_picks_schema(db_path)
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM picks WHERE snapshot_date = ? ORDER BY composite_score DESC",
            conn,
            params=(snapshot_date,),
        )
```

**B. Replace 9 of 10 pytest.skip skeletons in tests/test_journal.py** with real bodies (test_journal_cli_idempotent stays as pytest.skip('Plan 07-05')). Below is the COMPLETE replacement file:

```python
"""tests/test_journal.py — Phase 7 OUT-04..06 SQLite + trigger tests (Plan 07-03 bodies)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pandera as pa
import pytest

from screener import persistence
from screener.persistence import (
    PicksSchema,
    _ensure_picks_schema,
    append_picks_rows,
    read_picks_for_date,
)


def _make_row(
    ticker: str = "AAPL",
    snapshot_date: str = "2026-05-18",
    playbook_tag: str = "minervini_vcp",
    composite_score: float = 75.0,
    regime_state: str = "Confirmed Uptrend",
    entry_price: float = 180.0,
    stop_price: float = 175.0,
    shares: int = 50,
    risk_per_share: float = 5.0,
    atr_zone: str = "in-zone",
    pivot_distance_atr_breakout: float = 0.41,
    features_json: str | None = None,
    ingested_at: str = "2026-05-18T22:30:00Z",
) -> dict:
    """Factory for a complete picks row dict (13 decision cols + ingested_at)."""
    if features_json is None:
        features_json = json.dumps({
            "rs_rating": 92, "trend_template_score": 8,
            "pattern_diagnostics": {
                "type": "vcp", "n_contractions": 3,
                "depth_sequence": [0.25, 0.15, 0.08],
                "first_leg_depth": 0.25, "final_contraction_depth": 0.08,
                "breakout_vol_multiple": 1.7, "breakout_strength": 0.85,
                "pivot_price": 175.5, "days_in_consolidation": 18,
            },
            "features_json_version": "v1.0",
        })
    return {
        "ticker": ticker, "snapshot_date": snapshot_date,
        "playbook_tag": playbook_tag, "composite_score": composite_score,
        "regime_state": regime_state, "entry_price": entry_price,
        "stop_price": stop_price, "shares": shares,
        "risk_per_share": risk_per_share, "atr_zone": atr_zone,
        "pivot_distance_atr_breakout": pivot_distance_atr_breakout,
        "features_json": features_json, "ingested_at": ingested_at,
    }


def test_immutability_trigger(tmp_path: Path) -> None:
    """OUT-05: UPDATE on a decision column raises sqlite3.IntegrityError with 'decision column immutable'."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            conn.execute("UPDATE picks SET ticker = 'MSFT' WHERE id = 1")
        assert "decision column immutable" in str(excinfo.value)
        # Spot-check 3 more decision cols.
        for col in ("composite_score", "stop_price", "features_json"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f"UPDATE picks SET {col} = ? WHERE id = 1", ("X",))


def test_outcome_col_not_in_trigger(tmp_path: Path) -> None:
    """OUT-06: UPDATE on exit_price does NOT fire the trigger."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        # No exception expected.
        conn.execute("UPDATE picks SET exit_price = ? WHERE id = 1", (185.50,))
        conn.commit()
        val = conn.execute("SELECT exit_price FROM picks WHERE id = 1").fetchone()[0]
        assert val == 185.50


def test_outcome_column_updatable(tmp_path: Path) -> None:
    """OUT-06: all 6 outcome cols are nullable and updatable."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    updates = {
        "entry_filled": 1, "exit_price": 200.0, "exit_date": "2026-06-01",
        "hold_days": 14, "mfe": 25.5, "mae": -3.2,
    }
    with sqlite3.connect(db) as conn:
        # Initial NULL state.
        for col in updates:
            v = conn.execute(f"SELECT {col} FROM picks WHERE id = 1").fetchone()[0]
            assert v is None, f"{col} should start NULL"
        # All six updates succeed.
        for col, val in updates.items():
            conn.execute(f"UPDATE picks SET {col} = ? WHERE id = 1", (val,))
        conn.commit()
        for col, val in updates.items():
            v = conn.execute(f"SELECT {col} FROM picks WHERE id = 1").fetchone()[0]
            assert v == val, f"{col}: {v!r} != {val!r}"


def test_idempotent_append(tmp_path: Path) -> None:
    """OUT-04: INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) — mixed batch."""
    db = tmp_path / "j.sqlite"
    # First insert: 2 rows.
    n1 = append_picks_rows(
        [_make_row(ticker="AAPL"), _make_row(ticker="MSFT")], db_path=db,
    )
    assert n1 == 2
    # Second insert: 1 duplicate (AAPL), 1 new (NVDA), 1 duplicate (AAPL again).
    n2 = append_picks_rows(
        [_make_row(ticker="AAPL"), _make_row(ticker="NVDA"), _make_row(ticker="AAPL")],
        db_path=db,
    )
    assert n2 == 1, f"Expected 1 NVDA insert; got {n2}"
    # Total row count == 3 (AAPL + MSFT + NVDA).
    with sqlite3.connect(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        assert total == 3
    # Empty-batch early-return path.
    assert append_picks_rows([], db_path=db) == 0


def test_features_json_roundtrip(tmp_path: Path) -> None:
    """OUT-05: features_json column round-trips cleanly via json.loads."""
    db = tmp_path / "j.sqlite"
    expected = {"rs_rating": 92, "composite_score": 75.0, "extra": {"k": [1, 2, 3]}}
    append_picks_rows([_make_row(features_json=json.dumps(expected))], db_path=db)
    df = read_picks_for_date("2026-05-18", db_path=db)
    assert len(df) == 1
    loaded = json.loads(df.iloc[0]["features_json"])
    assert loaded == expected


def test_features_json_includes_diagnostics(tmp_path: Path) -> None:
    """OUT-05 / D-03: features_json embeds full pattern_diagnostics dict (Phase 6 D-05 keys)."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)  # _make_row default includes diagnostics
    df = read_picks_for_date("2026-05-18", db_path=db)
    loaded = json.loads(df.iloc[0]["features_json"])
    diag = loaded["pattern_diagnostics"]
    for required_key in (
        "type", "n_contractions", "depth_sequence", "first_leg_depth",
        "final_contraction_depth", "breakout_vol_multiple", "breakout_strength",
        "pivot_price", "days_in_consolidation",
    ):
        assert required_key in diag, f"pattern_diagnostics missing {required_key}"


def test_schema_idempotent_recreates_trigger(tmp_path: Path) -> None:
    """RESEARCH Pitfall 1: DROP TABLE picks + re-call _ensure_picks_schema → trigger STILL fires."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        conn.executescript("DROP TABLE picks;")  # cascades the trigger
    _ensure_picks_schema(db)  # re-create
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            conn.execute("UPDATE picks SET ticker = 'X' WHERE id = 1")
        assert "decision column immutable" in str(excinfo.value)


def test_picks_schema_rejects_invalid_playbook_tag() -> None:
    """PicksSchema isin enum rejects 'none' or any tag not in the locked set."""
    bad = pd.DataFrame([_make_row(playbook_tag="none")])
    # Drop schema-irrelevant cols if _make_row adds any in future; today the
    # dict keys are exactly the PicksSchema fields.
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad, lazy=False)
    bad2 = pd.DataFrame([_make_row(playbook_tag="day_trade")])
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad2, lazy=False)


def test_picks_schema_rejects_invalid_atr_zone() -> None:
    """PicksSchema isin enum rejects atr_zone not in {in-zone, extended, chase, skip}."""
    bad = pd.DataFrame([_make_row(atr_zone="chase-skip")])  # missing space + comma
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad, lazy=False)


def test_journal_cli_idempotent() -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows (filled by Plan 07-05)."""
    pytest.skip("Plan 07-05")
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_journal.py --no-cov -q 2>&1 | tail -3 | grep -E "9 passed.*1 skipped|9 passed, 1 skipped" && uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q && uv run pytest tests/test_architecture.py -x --no-cov -q && uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE "^def append_picks_rows\(" src/screener/persistence.py` outputs `1`
    - `grep -cE "^def read_picks_for_date\(" src/screener/persistence.py` outputs `1`
    - `grep -c "INSERT OR IGNORE INTO picks" src/screener/persistence.py` outputs `1`
    - `grep -c "^def test_" tests/test_journal.py` outputs `10`
    - `grep -c "pytest\.skip" tests/test_journal.py` outputs `1` (only test_journal_cli_idempotent remains)
    - `uv run pytest tests/test_journal.py --no-cov -q 2>&1 | tail -3` shows `9 passed, 1 skipped` (no failures, no errors)
    - `uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q` passes (FND-04 mutation gate green)
    - `uv run pytest tests/test_architecture.py -x --no-cov -q` passes (D-23 unchanged)
    - `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x --no-cov -q` passes (D-24 unchanged)
    - `uv run pytest tests/test_insider_io.py --no-cov -q` passes (Phase 6 InsiderSchema tests still green — no regressions from PicksSchema neighbor)
    - persistence.py uses no `print()`: `grep -c "^\s*print(" src/screener/persistence.py` outputs `0`
  </acceptance_criteria>
  <done>
    persistence.py exposes append_picks_rows + read_picks_for_date. Nine test_journal.py tests pass; one deferred to Plan 07-05. Pitfall 1 (DROP+re-create), Pitfall 2 (id gaps documented), and full immutability trigger semantics all validated. FND-04 gate, D-23, D-24 all green.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| python dict → SQLite via INSERT OR IGNORE | Caller-supplied rows become persistent records; the trigger + UNIQUE constraint defend integrity at the DB level |
| outcome columns updates → DB | Future v1.x journal-update flow will UPDATE outcome cols; the trigger explicitly does NOT cover these, by design |
| snapshot_date string → file path / SQL | Pandera regex defends against path traversal at write boundary |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-11 | Tampering | UPDATE on a decision column | mitigate | SQLite `BEFORE UPDATE OF <col-list>` trigger raises `sqlite3.IntegrityError('decision column immutable')` for all 13 decision cols. Tested via test_immutability_trigger (4 cols spot-checked) + test_schema_idempotent_recreates_trigger (Pitfall 1 — trigger survives DROP + re-CREATE). |
| T-07-12 | Tampering | DROP TABLE picks + INSERT/UPDATE bypasses trigger (RESEARCH Pitfall 1) | mitigate | _ensure_picks_schema runs CREATE TABLE + CREATE TRIGGER + CREATE INDEX inside ONE executescript, all with `IF NOT EXISTS` semantics. Re-call after DROP regenerates the trigger atomically. Tested via test_schema_idempotent_recreates_trigger. |
| T-07-13 | Repudiation | Double-insert via race condition or bad caller | mitigate | UNIQUE(ticker, snapshot_date) + INSERT OR IGNORE means double-inserts are silent no-ops with cur.rowcount==0 (verified empirically). No false-positive "row inserted" log. Tested via test_idempotent_append. |
| T-07-14 | Information disclosure | features_json blob may contain composite + components | accept | Composite scores and indicator values are NOT secrets; they are derived from public OHLCV + free fundamental data. No API keys, no PII. The `features_json_version` key (v1.0) supports future migration to a versioned redacted schema if needed. |
| T-07-15 | Denial of service | Unbounded features_json size (Pitfall 4) | accept | Worst-case ~1 KB per row × 30 picks/day × 365 days × 5 years = 55 MB total — trivial for SQLite. RESEARCH §Pitfall 4 documents the upper bound and rationale. |
| T-07-16 | Elevation of privilege | snapshot_date with path-traversal characters | mitigate | PicksSchema regex `^\d{4}-\d{2}-\d{2}$` at validation boundary rejects any non-ISO string before it reaches SQL parameter binding (which is parameterized anyway, blocking SQL injection by construction). |

ASVS L1 applicable controls: V5.3.4 (parameterized queries — sqlite3 named placeholders), V8.3.2 (sensitive data classification — features_json T-07-14 mitigation), V13.1.4 (API enforces input schema — PicksSchema at write boundary). No high-risk threats.
</threat_model>

<verification>
```bash
# Phase 7 Plan 03 verification suite (~10s)
uv run pytest tests/test_journal.py --no-cov -q                     # 9 passed, 1 skipped
uv run pytest tests/test_insider_io.py --no-cov -q                  # Phase 6 regression
uv run pytest tests/test_architecture.py --no-cov -q                # D-23 unchanged
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q  # D-24 unchanged
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q       # FND-04 mutation gate

# Schema + DDL sanity
uv run python -c "from screener.persistence import _PICKS_DDL, PicksSchema; assert 'CREATE TRIGGER' in _PICKS_DDL; print(len(PicksSchema.to_schema().columns), 'PicksSchema columns')"
# Expected: 13 PicksSchema columns

uv run ruff check src/screener/persistence.py
```
</verification>

<success_criteria>
- persistence.py has _PICKS_DDL constant, _journal_db_path resolver, _ensure_picks_schema, append_picks_rows, read_picks_for_date, PicksSchema (6 new artifacts).
- _PICKS_DDL is a single Final string containing TABLE + 2 INDEXes + TRIGGER; all use CREATE ... IF NOT EXISTS.
- Trigger fires on UPDATE OF any of 13 decision cols; does NOT fire on UPDATE of the 6 outcome cols.
- INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) returns cur.rowcount inserted only.
- append_picks_rows([]) early-returns 0.
- read_picks_for_date returns DataFrame ordered by composite_score DESC.
- PicksSchema is a strict pandera DataFrameModel with 13 fields (12 decision + ingested_at); rejects invalid playbook_tag and atr_zone.
- 9 of 10 tests in tests/test_journal.py pass; test_journal_cli_idempotent remains pytest.skip('Plan 07-05').
- Phase 6 InsiderSchema tests still green (no regression from PicksSchema neighbor).
- FND-04 no-look-ahead mutation gate STILL GREEN.
- D-23 architecture ALLOWED dict UNCHANGED.
- D-24 9-subcommand CLI surface STILL LOCKED.
</success_criteria>

<output>
After completion, create `.planning/phases/07-sizing-finalization-paper-trade-journal/07-03-SUMMARY.md` per the standard template.
</output>
