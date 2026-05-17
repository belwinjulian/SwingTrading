"""insider — EDGAR Form 4 bulk fetch + SQLite append-only event log (CAT-03/CAT-04).

Nightly bulk ingest of SEC Form 4 (insider transactions) into
``data/insider/form4.sqlite`` via ``persistence.append_form4_rows``.

Leverages ``edgartools`` to fetch EDGAR full-text index for the last
``lookback_days`` days and extracts per-transaction activities via
``.obj().get_transaction_activities()``.

Design constraints (D-08 / D-10):
- Append-only event log: ``INSERT ... ON CONFLICT(filing_id) DO NOTHING``.
  Re-running the same lookback window is safe and idempotent.
- ``edgartools.set_identity(...)`` MUST be called at CLI startup (Plan 05
  ``_ensure_edgar_identity`` hook). This module does NOT call
  ``set_identity`` — it expects identity to be set by the time the nightly
  cron hits ``refresh_insider``. Tests mock ``edgar.get_filings`` directly.
- InsiderSchema pandera validation runs BEFORE any SQLite insert
  (Pattern B / T-06-12 mitigation). A malformed filing row (invalid ``type``,
  negative ``shares``) raises ``pa.errors.SchemaError`` before the DB is
  touched — the DB stays clean.

Layered-DAG contract (Phase 1 D-16 / tests/test_architecture.py):
imports only stdlib, third-party, ``screener.persistence``,
``screener.config``. DOES NOT import ``screener.indicators`` or
``screener.signals``.

Structured-log event names:
- insider_fetch_start: {lookback_days, today}
- insider_fetch_success: {new_rows, total_rows}
- insider_fetch_fail: {error_type}
- insider_filing_parse_skip: {filing_id, error_type}
- insider_rows_inserted: {n}
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import edgar
import pandas as pd
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from screener import persistence
from screener.config import get_settings

log = structlog.get_logger(__name__)
# tenacity's before_sleep_log requires a stdlib logger — structlog's
# make_filtering_bound_logger is incompatible with tenacity's .log() call.
_stdlib_log = logging.getLogger(__name__)

# Defensively set EDGAR rate limit if the attribute is present (Open Question 5).
# edgartools >= 5.28.x exports set_rate_limit; earlier versions may not.
if hasattr(edgar, "set_rate_limit"):
    edgar.set_rate_limit(5)  # type: ignore[attr-defined]


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def refresh_insider(today: date, lookback_days: int = 35) -> int:
    """Bulk EDGAR Form 4 ingest for the last ``lookback_days`` days.

    Returns the number of new rows inserted (after ON CONFLICT DO NOTHING).

    NOTE: ``edgar.set_identity()`` MUST have been called at CLI startup
    (Plan 05 ``_ensure_edgar_identity`` hook) before this function is
    invoked. This function does NOT call ``set_identity`` — allowing tests
    to mock ``edgar.get_filings`` directly without triggering identity
    validation.

    Security note (T-06-11): EDGAR may include sensitive identifiers in
    exception messages. Every ``except`` block uses
    ``error_type=type(e).__name__`` only, NEVER ``error=str(e)``.
    """
    log.info("insider_fetch_start", lookback_days=lookback_days, today=str(today))

    try:
        filings = edgar.get_filings(form="4", filing_date=f"-{int(lookback_days)}d:")
    except Exception as e:
        log.error("insider_fetch_fail", error_type=type(e).__name__)
        raise

    if not filings:
        log.info("insider_fetch_success", new_rows=0, total_rows=0)
        return 0

    rows: list[dict] = []
    for filing in filings:
        try:
            form4 = filing.obj()
            for activity in form4.get_transaction_activities():
                rows.append({
                    "filing_id": str(filing.accession_no),
                    "ticker": str(activity.ticker).upper(),
                    "insider": str(activity.insider_name),
                    "transaction_date": (
                        pd.Timestamp(activity.transaction_date).isoformat()[:10]
                    ),
                    "type": "BUY" if activity.is_acquisition else "SELL",
                    "shares": float(activity.shares),
                    "value_usd": float(activity.value_usd or 0.0),
                    "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
                })
        except Exception as e:
            log.warning(
                "insider_filing_parse_skip",
                filing_id=getattr(filing, "accession_no", "?"),
                error_type=type(e).__name__,
            )
            continue

    if not rows:
        log.info("insider_fetch_success", new_rows=0, total_rows=0)
        return 0

    df = pd.DataFrame(rows)

    # Pandera schema validation BEFORE SQLite insert (T-06-12 / Pattern B).
    # SchemaError raised here blocks the insert; DB stays clean.
    # transaction_date must be Timestamp for InsiderSchema validation.
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True).dt.tz_localize(None)
    validated = persistence.validate_at_write(persistence.InsiderSchema, df)

    # Convert transaction_date back to ISO string for SQLite storage (D-10 schema).
    validated_records = validated.copy()
    validated_records["transaction_date"] = validated_records["transaction_date"].dt.strftime(
        "%Y-%m-%d"
    )
    validated_records["ingested_at"] = validated_records["ingested_at"].astype(str)

    inserted = persistence.append_form4_rows(None, validated_records.to_dict(orient="records"))
    log.info("insider_fetch_success", new_rows=inserted, total_rows=len(validated))
    log.info("insider_rows_inserted", n=inserted)
    return inserted
