"""tests/test_pipeline_journal.py — Phase 7 pipeline + journal integration.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-04 (Wave 2).
"""
from __future__ import annotations

import pytest


def test_pipeline_writes_journal() -> None:
    """OUT-04: run_pipeline(..., write_journal=True) appends rows to data/journal.sqlite."""
    pytest.skip("Plan 07-04")


def test_journal_disabled() -> None:
    """D-01: run_pipeline(..., write_journal=False) emits 'journal_skipped' event, writes zero rows."""
    pytest.skip("Plan 07-04")


def test_rejected_picks_not_in_journal() -> None:
    """SIZ-02 / D-06: ADR-rejected picks excluded from BOTH the snapshot top-N AND the journal."""
    pytest.skip("Plan 07-04")


def test_golden_pipeline_journal() -> None:
    """SC-1: full pipeline run produces deterministic row count + features_json shape."""
    pytest.skip("Plan 07-04")
