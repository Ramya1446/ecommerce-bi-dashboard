import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecombi.db import build_database  # noqa: E402
from ecombi.generate import generate  # noqa: E402


@pytest.fixture(scope="session")
def dataset():
    return generate(n_customers=1500, seed=7)


@pytest.fixture(scope="session")
def db_path(dataset, tmp_path_factory):
    return build_database(dataset, tmp_path_factory.mktemp("db") / "test.db")
