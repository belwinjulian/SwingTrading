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
