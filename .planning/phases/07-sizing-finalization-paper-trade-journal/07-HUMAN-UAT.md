---
status: partial
phase: 07-sizing-finalization-paper-trade-journal
source: [07-VERIFICATION.md]
started: 2026-05-18T00:00:00Z
updated: 2026-05-18T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-End Pipeline Smoke Test
expected: Run `screener score` or `screener report` on a date with cached OHLCV data, then query `sqlite3 data/journal.sqlite "SELECT ticker, composite_score, playbook_tag, shares FROM picks ORDER BY composite_score DESC LIMIT 5;"` — rows present with composite_score >= 50, valid playbook_tag, non-zero shares for non-rejected picks, and per-pick blocks with **Entry:**, **Stop:**, **Trail:**, **Shares:**, **Zone:** in the report
result: [pending]

### 2. Journal CLI Idempotency on Live Snapshot
expected: After `screener score`, run `screener journal` twice — first invocation emits `journal_catchup_complete` with n_inserted > 0; second emits n_inserted=0 and n_idempotent_skip == n_attempted; both exit 0; no `[stub]` log line
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
