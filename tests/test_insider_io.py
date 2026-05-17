"""EDGAR Form 4 data adapter tests — CAT-04.

Plan 06-03 (Wave 1) replaces every pytest.skip with mocked assertions over
data/insider.py (edgartools bulk Form 4 fetch + SQLite append-only event log
per D-10). InsiderSchema validation runs BEFORE the SQLite insert.
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import pytest


def test_form4_bulk_fetch_idempotent() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates D-10: second invocation of insider.refresh_form4() with "
        "the same filings inserts ZERO rows (ON CONFLICT(filing_id) DO "
        "NOTHING preserves append-only history)."
    )


def test_form4_schema_validated_before_sqlite_insert() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-03 fills body. "
        "Validates CAT-04 / D-10: a malformed Form 4 row (e.g., shares=-1) "
        "is rejected by InsiderSchema.validate BEFORE the SQLite INSERT — "
        "the DB stays clean and the run fails loud at the boundary."
    )
