"""screener — long-only EOD momentum swing-trading screener for Russell 1000.

Architecture: layered DAG (data → indicators → signals → regime → sizing →
publishers → backtest). See .planning/research/ARCHITECTURE.md and
tests/test_architecture.py for the import contract.
"""
