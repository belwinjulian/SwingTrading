"""publishers — thin (ranked_df) -> file_artifact functions.

Three publishers fan out from the same ranked DataFrame: report (Markdown),
journal (SQLite, the v2 ML training contract), snapshot (Parquet ranking
history for backtest). Implementation lands in Phase 4+.
"""
