"""Golden-file pattern regression tests — PAT-01..04, PAT-06, D-02 / D-04.

Plan 06-02 (Wave 1) replaces every pytest.skip body with a real assertion
against the committed `tests/fixtures/patterns/*.parquet` fixtures. Until
then, these stubs document the canonical test names so other Phase 6 plans
have a stable verify target.
"""

# Wave: 1  (body filled by Plan 06-02 — see 06-VALIDATION.md "New test files")

import pytest


def test_nvda_2023_vcp() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-02 / PAT-01..03 / PAT-06: NVDA 2023-04..07 fixture must "
        "trip vcp_passes=True on the AI-rally breakout bar (golden file)."
    )


def test_aapl_2020_vcp() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-02 / PAT-06: AAPL 2020 COVID-recovery VCP fixture must "
        "trip vcp_passes=True on its breakout bar."
    )


def test_nvda_2024_split_pivot_continuity() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-02 / PAT-05 / D-25 / Pitfall 1: NVDA 2024 OHLCV spans the "
        "2024-06-10 10:1 split; pivot_price must be derived from "
        "auto_adjust=True closes so pre-split pivot continuity holds."
    )


def test_nvda_2023_flag() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-02 / PAT-03: NVDA 2023-05-25..06-12 fixture must trip "
        "flag_passes=True on the post-earnings continuation breakout along "
        "the rising 10-SMA."
    )


def test_post_gap_continuation() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-04 / PAT-04 boolean: post_gap_continuation True when "
        "gap >= 8% AND volume > 1.5 x SMA50 AND close in upper third of "
        "the D-0 high-low range (NOT (open, high)) — exact D-04 wording."
    )


def test_vcp_thresholds() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates D-03 + CLAUDE.md verbatim: prior_uptrend >= 30%, "
        "n_contractions in [2,6], depth ratio <= 0.85, first leg <= 35%, "
        "final <= 12%, breakout vol >= 1.5x SMA50, all declared as "
        "module-level Final constants in indicators/patterns.py."
    )
