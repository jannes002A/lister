"""Shared fixtures for the test suite.

The app is imported as the installed ``src`` package (see the packaging
configured in ``pyproject.toml``), so no path juggling is needed here.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src import app as app_module

# ``app.py`` calls ``init_db()`` at import time, which creates a database next to
# the package. Remove it again if the import was what created it, so running the
# tests never leaves anything behind in the source tree.
_STRAY_DB = Path(app_module.__file__).parent / "shopping.db"
if _STRAY_DB.exists():
    _STRAY_DB.unlink()


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The Flask app, wired to a fresh SQLite database per test."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "shopping.db")
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


class DB:
    """Test-side database access, independent of the request context."""

    def __init__(self, path):
        self.path = path

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql, params=()):
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        with closing(self._connect()) as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid

    def scalar(self, sql, params=()):
        return self.query(sql, params)[0][0]

    def count(self, table):
        return self.scalar(f"SELECT COUNT(*) FROM {table}")


@pytest.fixture
def db(app):
    return DB(app_module.DB_PATH)


@pytest.fixture
def make_recipe(db):
    """Insert a recipe plus ingredients; returns the new recipe id."""

    def _make(name="Pancakes", source="", ingredients=()):
        recipe_id = db.execute(
            "INSERT INTO recipes (name, source) VALUES (?, ?)", (name, source)
        )
        for ing_name, amount, unit in ingredients:
            db.execute(
                "INSERT INTO ingredients (recipe_id, name, amount, unit)"
                " VALUES (?, ?, ?, ?)",
                (recipe_id, ing_name, amount, unit),
            )
        return recipe_id

    return _make


@pytest.fixture
def select_recipe(db):
    """Put a recipe into the current selection; returns the selection id."""

    def _select(recipe_id):
        return db.execute(
            "INSERT INTO selections (recipe_id) VALUES (?)", (recipe_id,)
        )

    return _select
