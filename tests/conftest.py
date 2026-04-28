"""Shared pytest configuration."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to `tests/fixtures/` directory."""
    return Path(__file__).parent / "fixtures"
