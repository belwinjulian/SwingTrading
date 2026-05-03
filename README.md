# Momentum Swing Screener

A long-only, end-of-day swing-trading screener that scans the Russell 1000 every evening and produces a ranked list of stocks worth buying tomorrow. Each pick declares which playbook it fits — Qullamaggie continuation flag, Minervini VCP, or leader-hold — and surfaces a concrete entry, stop, and position size for that playbook.

**Status:** Phase 1 — repository scaffolding. No data fetching, indicators, or backtests yet.

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
cp .env.example .env       # then fill in API keys
uvx pre-commit install
```

## Usage

All workflows run through `make`:

```bash
make help        # list available targets
make setup       # uv sync + pre-commit install
make data        # refresh universe + ohlcv + macro + fundamentals (stub in Phase 1)
make rank        # compute composite scores (stub in Phase 1)
make report      # render the daily markdown report (stub in Phase 1)
make backtest    # run the walk-forward backtest (stub in Phase 1)
```

## Project layout

- `src/screener/` — package source; layered DAG (data → indicators → signals → regime → sizing → publishers → backtest)
- `tests/` — pytest suite, including the architecture test that enforces the import DAG
- `docs/` — methodology, pre-registration documents
- `.planning/` — GSD planning artifacts (CONTEXT.md, ROADMAP.md, REQUIREMENTS.md, phase plans)

## Data layer

Phase 2 ships a free-tier OHLCV cache and a Russell 1000 universe builder. After running `make data` (or `screener refresh-universe && screener refresh-ohlcv`):

**Layout**

Per-ticker path: `data/ohlcv/<TICKER>/{prices,splits}.parquet`. Universe snapshots at `data/universe/<iso-monday>.parquet`.

```
data/
├── universe/
│   └── 2026-04-27.parquet          # one Parquet per ISO-week-Monday; committed to git
└── ohlcv/
    ├── AAPL/
    │   ├── prices.parquet          # 20-year adjusted OHLCV; gitignored
    │   └── splits.parquet          # corp-action ledger; committed to git
    └── ...
```

**Backfill**

The first `screener refresh-ohlcv` run against the Russell 1000 takes ~30–60 minutes wall-clock and produces ~5 GB of per-ticker Parquet under `data/ohlcv/`. Subsequent nightly runs only fetch from `last_cached_date + 1` and append, so they complete in ~17 minutes for the same universe. Backfill start is `2005-01-01` (covers 2008-Q4, 2020-Q1, 2022-H1 for downstream regime tests).

**Stooq fallback**

If the first 50 yfinance fetches in a run produce a success rate below 80%, the pipeline trips a circuit breaker, emits a structured `breaker_tripped` event, and routes the remaining tickers through Stooq (via pandas-datareader). The 95% combined-coverage health gate still applies — the run fails loud (non-zero exit, no commit) if `(yf_ok + stooq_ok) / universe_size < 0.95`. Implementation reference: D-12 in `.planning/phases/02-data-foundation/02-CONTEXT.md`.

**Survivorship-bias disclosure**

This pipeline pulls the *current* Russell 1000 from the iShares IWB CSV. Tickers that have been delisted or removed from the index are not retroactively included; backtests run against this dataset are subject to a survivorship bias estimated at +1–2% CAGR (see [`CLAUDE.md` §5.3](./CLAUDE.md#53-survivorship-bias)). Mitigation: every weekly snapshot is committed under `data/universe/`, accumulating a real point-in-time membership dataset going forward; once the cache holds 13+ weekly snapshots, walk-forward backtests can stitch them into a survivorship-corrected universe at each rebalance.

**Atomic writes**

Every Parquet artifact is written via `tempfile.NamedTemporaryFile(dir=target.parent, ...)` + `os.replace()` — POSIX-atomic on the same filesystem. A crash mid-write never leaves a partial Parquet at the target path. The contract lives in `src/screener/persistence.py::_write_parquet_atomic`.

## References

- [`CLAUDE.md`](./CLAUDE.md) — full methodology, repo conventions, AI-pairing brief
- [`.planning/ROADMAP.md`](./.planning/ROADMAP.md) — 8-phase roadmap with success criteria
- [`.planning/REQUIREMENTS.md`](./.planning/REQUIREMENTS.md) — 64 v1 requirements (FND/DAT/IND/PAT/SIG/REG/CMP/SIZ/CAT/OUT/BCK/OPS)

## License

MIT — see [`LICENSE`](./LICENSE).
