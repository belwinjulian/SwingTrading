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

## References

- [`CLAUDE.md`](./CLAUDE.md) — full methodology, repo conventions, AI-pairing brief
- [`.planning/ROADMAP.md`](./.planning/ROADMAP.md) — 8-phase roadmap with success criteria
- [`.planning/REQUIREMENTS.md`](./.planning/REQUIREMENTS.md) — 64 v1 requirements (FND/DAT/IND/PAT/SIG/REG/CMP/SIZ/CAT/OUT/BCK/OPS)

## License

MIT — see [`LICENSE`](./LICENSE).
