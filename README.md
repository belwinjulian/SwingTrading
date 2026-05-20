# Momentum Swing Screener

A long-only, end-of-day swing-trading screener that scans the Russell 1000 every evening and produces a ranked list of stocks worth buying the next morning. Each pick declares which playbook it fits — Minervini VCP, Qullamaggie continuation flag, or leader-hold — and surfaces a concrete entry, stop, and position size.

**Status:** Operational. Nightly pipeline runs automatically on GitHub Actions (weekdays 22:30 UTC). Latest report: [`reports/2026-05-20.md`](./reports/2026-05-20.md)

---

## How to use it

### Nightly report (no setup needed)

The GitHub Action runs every weekday evening at **22:30 UTC (6:30 PM ET)** and commits the day's report to [`reports/`](./reports/). Open the latest file — that's your watchlist for tomorrow morning.

Each report has two sections:

**Regime** — tells you whether to be long at all:

| State | Action |
|-------|--------|
| `Uptrend` | Full size, trade all setups |
| `Uptrend Under Pressure` | Half size or be selective |
| `Correction` | No new longs — stay in cash |

**Top 15 Picks** — ranked by composite score (RS + trend template + VCP pattern + volume + catalyst):

- **in-zone** → stock is at or near a buyable pivot right now
- **chase, skip** → stock already ran past the entry point; wait for the next base
- **Entry / Stop** — next-day open entry price and initial stop loss
- **Playbook** — which setup it fits (`minervini_vcp`, `qullamaggie_flag`, `leader_hold`)

Focus on `in-zone` picks when the regime is `Uptrend` or `Uptrend Under Pressure`.

### Run locally

```bash
# one-time setup
uv sync --extra dev
cp .env.example .env   # fill in API keys (see below)

# nightly pipeline (same as what GitHub Actions runs)
uv run screener refresh-universe
uv run screener refresh-ohlcv
uv run screener refresh-macro
uv run screener refresh-fundamentals
uv run screener score
uv run screener report     # writes reports/YYYY-MM-DD.md
uv run screener journal    # appends picks to data/journal.sqlite

# shortcuts
uv run screener score      # recompute scores only (no report file)
uv run screener report     # full pipeline + write report
uv run screener backtest   # walk-forward backtest (3-yr IS / 1-yr OOS)
```

### API keys (`.env`)

```
FINNHUB_API_KEY=your_key               # free at finnhub.io — news, earnings calendar
EDGAR_IDENTITY=Name email@example.com  # required by SEC EDGAR fair-use policy
FRED_API_KEY=your_key                  # free at fred.stlouisfed.org — macro data
ACCOUNT_VALUE=25000                    # optional — enables real share-count sizing
```

---

## How it works

**Universe:** Russell 1000 (iShares IWB), refreshed weekly.

**Signal stack — all eight must pass for a full Trend Template score:**
1. Close > SMA150 and Close > SMA200
2. SMA150 > SMA200
3. SMA200 rising for at least 1 month
4. SMA50 > SMA150 and SMA50 > SMA200
5. Close > SMA50
6. Close ≥ 30% above 52-week low
7. Close within 25% of 52-week high
8. RS Rating ≥ 70

**VCP detection:** prior uptrend ≥ 30%, 2–6 contractions each ≥ 15% tighter than the last, final contraction ≤ 12%, volume drying up through the base, breakout volume ≥ 1.5× 50-day average.

**Regime gate:** composite of SPY/QQQ trend, VIX level, NYSE advance/decline, and FRED yield spread. No new longs in `Correction` — the screener enforces this automatically.

**Execution rule:** signals computed at bar close `t` execute at open of bar `t+1`. No same-bar execution.

---

## Repository layout

```
src/screener/
  config.py           # pydantic-settings — all params in one place
  data/               # all external I/O (ohlcv, fundamentals, macro, universe)
  indicators/         # SMA, ATR, RS, OBV, Bollinger Bands (pure functions)
  signals/            # Minervini, Qullamaggie, CANSLIM, composite scorer
  regime.py           # market regime score + state
  catalysts/          # sentiment (FinBERT), insider activity (EDGAR Form 4)
  backtest/           # vectorbt walk-forward + metrics
  sizing.py           # position sizing + stop rules
  persistence.py      # Parquet + SQLite I/O with pandera schema validation
  publishers/         # report renderer, run log, pipeline orchestrator
  cli.py              # typer CLI
reports/              # nightly Markdown reports (auto-committed by CI)
data/
  universe/           # weekly Russell 1000 snapshots (committed)
  ohlcv/              # per-ticker prices.parquet (gitignored) + splits.parquet (committed)
  journal.sqlite      # paper-trade history — the ML training contract
  runs.jsonl          # nightly pipeline run log
  heartbeat.txt       # weekly CI heartbeat (prevents GitHub idle-disable)
.github/workflows/
  refresh.yml         # nightly pipeline (22:30 UTC weekdays)
  heartbeat.yml       # weekly heartbeat (Sundays)
  ci.yml              # lint + typecheck + tests on every push
```

---

## Data notes

**First run backfill:** `screener refresh-ohlcv` against the full Russell 1000 takes ~30–60 min and produces ~5 GB under `data/ohlcv/`. Subsequent nightly runs are incremental (~17 min). The cache covers back to 2005-01-01 (includes 2008, 2020-Q1, 2022-H1 for regime tests).

**Survivorship-bias disclosure:** the universe is the *current* Russell 1000. Delisted or removed tickers are not retroactively included; backtests carry an estimated +1–2% CAGR survivorship bias. Weekly universe snapshots committed under `data/universe/` accumulate a real point-in-time membership record — once 13+ weekly snapshots exist, walk-forward backtests can use a survivorship-corrected universe at each rebalance.

**Stooq fallback:** if yfinance success rate drops below 80% in the first 50 tickers, the pipeline trips a circuit breaker and routes remaining tickers through Stooq (pandas-datareader). The run fails if combined coverage falls below 95%.

**Atomic writes:** every Parquet artifact is written via `tempfile.NamedTemporaryFile` + `os.replace()` — POSIX-atomic on the same filesystem, so a crash mid-write never leaves a partial file.

---

## Tech stack

| Package | Version | Role |
|---------|---------|------|
| Python | 3.11 | Runtime |
| pandas-ta-classic | 0.4.47 | Technical indicators (pure Python, no C deps) |
| vectorbt | 1.0.x | Vectorized backtest + walk-forward |
| yfinance | ≥1.3.0 | Primary OHLCV source |
| edgartools | 5.30.x | SEC Form 4 insider filings |
| finnhub-python | 2.4.28 | News, earnings calendar |
| fredapi | 0.5.2 | FRED macro data |
| pandera | 0.31.1 | DataFrame schema validation at every IO boundary |
| pydantic-settings | 2.14.x | Typed config |
| structlog | 25.5.x | Structured JSON logging |
| uv | 0.11.x | Package manager |

**$0/month** — all data sources are free tier. No paid feeds, no cloud SaaS beyond GitHub Actions free tier.

---

## References

- [`CLAUDE.md`](./CLAUDE.md) — full methodology, signal formulas, coding conventions
- [`.planning/ROADMAP.md`](./.planning/ROADMAP.md) — 8-phase roadmap with success criteria
- [`docs/methodology.md`](./docs/methodology.md) — Minervini/Qullamaggie/CANSLIM rules in full
- [`docs/backtesting.md`](./docs/backtesting.md) — walk-forward setup, metrics, bias disclosures

## License

MIT — see [`LICENSE`](./LICENSE).
