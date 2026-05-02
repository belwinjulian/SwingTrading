"""Shared pytest configuration and fixtures.

Phase 1 ships only the fixtures Phase 1 tests need. Phase 2+ will add OHLCV
fixtures, regime golden-files, etc.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root (parent of `tests/`)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_screener(repo_root: Path) -> Path:
    """Absolute path to src/screener/."""
    return repo_root / "src" / "screener"
