"""Tests for the database helpers: init_db, get_db and close_db."""

import sqlite3

import pytest
from flask import g

from src import app as app_module

TABLES = {"recipes", "ingredients", "selections", "saved_extras", "list_extras"}


def test_init_db_creates_the_database_file(app, tmp_path):
    assert (tmp_path / "shopping.db").exists()


def test_init_db_creates_every_table(app, db):
    names = {
        row["name"]
        for row in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert TABLES <= names


def test_init_db_is_idempotent_and_keeps_data(app, db, make_recipe):
    make_recipe("Soup")
    app_module.init_db()
    assert db.count("recipes") == 1


def test_get_db_returns_a_connection(app):
    with app.app_context():
        assert isinstance(app_module.get_db(), sqlite3.Connection)


def test_get_db_reuses_the_connection_within_one_app_context(app):
    with app.app_context():
        assert app_module.get_db() is app_module.get_db()


def test_get_db_uses_a_new_connection_per_app_context(app):
    with app.app_context():
        first = app_module.get_db()
    with app.app_context():
        assert app_module.get_db() is not first


def test_get_db_stores_the_connection_on_g(app):
    with app.app_context():
        conn = app_module.get_db()
        assert g.db is conn


def test_get_db_uses_a_row_factory_allowing_access_by_column_name(app, make_recipe):
    make_recipe("Chili", source="Book")
    with app.app_context():
        row = app_module.get_db().execute("SELECT * FROM recipes").fetchone()
    assert row["name"] == "Chili"
    assert row["source"] == "Book"


def test_get_db_enables_foreign_key_enforcement(app):
    with app.app_context():
        assert app_module.get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_get_db_honours_a_changed_db_path(app, tmp_path, monkeypatch):
    other = tmp_path / "other.db"
    monkeypatch.setattr(app_module, "DB_PATH", other)
    app_module.init_db()
    with app.app_context():
        app_module.get_db().execute("SELECT 1")
    assert other.exists()


def test_close_db_removes_the_connection_from_g(app):
    with app.app_context():
        app_module.get_db()
        app_module.close_db(None)
        assert "db" not in g


def test_close_db_actually_closes_the_connection(app):
    with app.app_context():
        conn = app_module.get_db()
        app_module.close_db(None)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_close_db_is_a_noop_when_no_connection_was_opened(app):
    with app.app_context():
        app_module.close_db(None)  # must not raise


def test_close_db_ignores_the_exception_argument(app):
    with app.app_context():
        conn = app_module.get_db()
        app_module.close_db(RuntimeError("boom"))
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_leaving_the_app_context_closes_the_connection(app):
    with app.app_context():
        conn = app_module.get_db()
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_deleting_a_recipe_cascades_to_its_ingredients(app, make_recipe):
    recipe_id = make_recipe("Curry", ingredients=[("Rice", "1", "kg")])
    with app.app_context():
        conn = app_module.get_db()
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] == 0
