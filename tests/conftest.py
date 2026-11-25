from __future__ import annotations

import pytest

from counselgrid.db import SQLiteDatabase


@pytest.fixture()
def db(tmp_path):
    return SQLiteDatabase(tmp_path / "counselgrid-test.db")
