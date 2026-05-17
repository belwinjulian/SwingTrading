"""Split-adjusted pivot continuity — PAT-05 / D-25 / Pitfall 1.

Separate from tests/test_patterns_golden.py to make the Pitfall 1 regression
(pre-split pivot = post-split bar => false breakout) explicit and discoverable
in CI failure summaries.

Plan 06-02 (Wave 1) replaces the pytest.skip with the real assertion against
`tests/fixtures/patterns/nvda_2024_split.parquet` (which spans the 2024-06-10
10:1 split). Pivot prices MUST be re-derived from auto_adjust=True closes;
storing a pre-split pivot causes a false breakout signal on the post-split bar.
"""

# Wave: 1  (body filled by Plan 06-02 — see 06-VALIDATION.md "New test files")

import pytest


def test_nvda_2024_split_pivot_continuity() -> None:
    pytest.skip(
        "Phase 6 Wave 1 stub — Plan 06-02 fills body. "
        "Validates PAT-05 / D-25 / CLAUDE.md Pitfall 3: NVDA 2024 OHLCV "
        "fixture spans the 2024-06-10 10:1 split; pivot_price computed on "
        "auto_adjust=True closes must remain consistent across the split "
        "boundary (pre-split pivot rebased into post-split price units)."
    )
