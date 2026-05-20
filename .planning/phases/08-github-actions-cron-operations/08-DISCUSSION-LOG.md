# Phase 8: GitHub Actions Cron & Operations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 8-github-actions-cron-operations
**Areas discussed:** OHLCV cache persistence, runs.jsonl gitignore conflict, Workflow timeout duration

---

## OHLCV cache persistence

### Q1: How should the nightly workflow persist prices.parquet files between runs?

| Option | Description | Selected |
|--------|-------------|----------|
| actions/cache | Cache data/ohlcv/ between runs with weekly-keyed cache. Standard GHA pattern, keeps git history clean, up to 10GB free. | ✓ |
| Commit prices.parquet to git | Add !/data/ohlcv/**/prices.parquet carve-out. Simplest operationally but commits 1000+ binary files daily — git history bloats to GBs. | |
| Re-download nightly | Accept full re-download each run. Not viable at 1000 tickers. | |

**User's choice:** actions/cache (Recommended)

---

### Q2: Cache key strategy for data/ohlcv/?

| Option | Description | Selected |
|--------|-------------|----------|
| Week-number key | Key: ohlcv-{year}-{week-number}. Refreshes Monday, covers Fri→Mon gap. | |
| Daily key with weekly fallback | Key: ohlcv-{date}, restore-keys: ohlcv-{year}-{week}. Tries today first, falls back to most recent weekly. | ✓ |

**User's choice:** Daily key with weekly fallback

---

### Q3: Should macro data (data/macro/*.parquet) also be cached?

| Option | Description | Selected |
|--------|-------------|----------|
| Cache macro data too | Include data/macro/ in cache entry. Avoids repeat FRED API calls. | |
| Re-fetch macro fresh each night | Only 5 tickers, fast. Ensures regime detection always uses latest bar. | ✓ |

**User's choice:** Re-fetch macro fresh each night

---

### Q4: Should fundamentals and insider data be cached?

| Option | Description | Selected |
|--------|-------------|----------|
| Cache fundamentals + insider | Rate-limited sources (Finnhub 60 calls/min, EDGAR). Update infrequently; caching avoids wasteful API calls. | ✓ |
| Re-fetch fundamentals nightly | Already cached via requests-cache SQLite (24h TTL). | |

**User's choice:** Cache fundamentals + insider (Recommended)

---

## runs.jsonl gitignore conflict

### Q1: Where should runs.jsonl live?

| Option | Description | Selected |
|--------|-------------|----------|
| Root runs.jsonl + add !/runs.jsonl carve-out | Keep at repo root, remove /runs.jsonl ignore line. | |
| Move to data/runs.jsonl | Relocate to data/, add !/data/runs.jsonl carve-out. Groups observability data with other data artifacts. | ✓ |

**User's choice:** Move to data/runs.jsonl

---

### Q2: What should be written to data/runs.jsonl on health check failure?

| Option | Description | Selected |
|--------|-------------|----------|
| Commit the failure entry only | Write failure JSON record, commit only runs.jsonl. No report/snapshot/journal committed. | ✓ |
| Commit nothing on failure | Skip auto-commit entirely. Cleaner history but no failure record. | |

**User's choice:** Commit the failure entry only (Recommended)

---

## Workflow timeout duration

### Q1: What should the nightly refresh workflow's timeout-minutes be?

| Option | Description | Selected |
|--------|-------------|----------|
| 120 minutes | Covers cold-cache runs with headroom. Worst-case cost well under free-tier cap. | ✓ |
| 90 minutes | Tighter. Cold-cache runs may exceed this after long weekends. | |
| 60 minutes | Too aggressive for cold-cache scenarios. | |

**User's choice:** 120 minutes (Recommended)

---

### Q2: Should CI workflow timeout be raised for Phase 6+ tests?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 10 minutes for CI | CI must stay fast. Over-10-min tests are a test design problem. | ✓ |
| Raise CI to 15 minutes | More headroom for golden-file and pattern tests. | |

**User's choice:** Keep 10 minutes for CI (Recommended)

---

## Claude's Discretion

- Exact `actions/cache` YAML key expression (daily + weekly-fallback format)
- How `data/runs.jsonl` is written — module-internal call from `run_pipeline` vs. `scripts/` helper
- Heartbeat commit author (default GitHub Actions bot is fine)
- Heartbeat artifact content format

## Deferred Ideas

- **Slack/Discord failure notification** — default GitHub Actions email is sufficient for v1; can add `slackapi/slack-github-action` in v1.x
- **Per-ticker fetch timing stats in runs.jsonl** — richer observability; deferred to v1.x
- **Retry failed tickers in second pass** — re-attempt tickers that failed before the 95% health check; deferred to v1.x
