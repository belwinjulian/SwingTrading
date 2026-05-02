"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""
