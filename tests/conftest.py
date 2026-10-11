from __future__ import annotations
import pytest
from fieldcraft.database import Database
from fieldcraft.seed import seed


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / 'example.sqlite3')
    seed(database)
    return database
