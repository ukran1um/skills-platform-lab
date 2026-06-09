"""Workspace-wide pytest fixtures.

`fixtures_parquet` owns the deterministic synthetic warehouse so individual skill
tests don't import lab_data directly (keeps skills standalone-extractable for M4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_data.fixtures import write_parquet


@pytest.fixture(scope="session")
def fixtures_parquet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("warehouse") / "prices.parquet"
    return write_parquet(path)
