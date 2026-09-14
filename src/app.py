import re
import sqlite3
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, url_for

DB_PATH = Path(__file__).parent / "shopping.db"

app = Flask(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    amount TEXT DEFAULT '',
    unit TEXT DEFAULT 'pieces'
);

-- Recipes currently picked for cooking (the "run" of the app)
CREATE TABLE IF NOT EXISTS selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom ingredients ever typed in; persist across runs as quick-add buttons
CREATE TABLE IF NOT EXISTS saved_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Extra ingredients added to the current shopping list
CREATE TABLE IF NOT EXISTS list_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


# ---------------------------------------------------------------- recipes

@app.route("/", methods=["GET", "POST"])
def create_recipe():
    db = get_db()
    message = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        source = request.form.get("source", "").strip()
        ing_names = request.form.getlist("ing_name")
        ing_amounts = request.form.getlist("ing_amount")
        ing_units = request.form.getlist("ing_unit")
        if name:
            cur = db.execute(
                "INSERT INTO recipes (name, source) VALUES (?, ?)", (name, source)
            )
            recipe_id = cur.lastrowid
            for n, a, u in zip(ing_names, ing_amounts, ing_units):
                n = n.strip()
                if n:
                    db.execute(
                        "INSERT INTO ingredients (recipe_id, name, amount, unit)"
                        " VALUES (?, ?, ?, ?)",
                        (recipe_id, n, a.strip(), u if u in ("pieces", "kg") else "pieces"),
                    )
            db.commit()
            message = f"Recipe “{name}” saved."
    recipes = db.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    return render_template("create_recipe.html", recipes=recipes, message=message)


# ---------------------------------------------------------- pick recipes

@app.route("/plan", methods=["GET", "POST"])
def plan():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            recipe_id = request.form.get("recipe_id")
            if recipe_id:
                db.execute("INSERT INTO selections (recipe_id) VALUES (?)", (recipe_id,))
                db.commit()
        elif action == "remove":
            db.execute("DELETE FROM selections WHERE id = ?", (request.form.get("selection_id"),))
            db.commit()
        elif action == "create":
            return redirect(url_for("build_list"))
        return redirect(url_for("plan"))

    recipes = db.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    selected = db.execute(
        "SELECT s.id AS selection_id, r.name, r.source"
        " FROM selections s JOIN recipes r ON r.id = s.recipe_id"
        " ORDER BY s.id"
    ).fetchall()
    return render_template("plan.html", recipes=recipes, selected=selected)


# ------------------------------------------------------ build the list

@app.route("/build", methods=["GET", "POST"])
def build_list():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_extra":
            name = request.form.get("extra_name", "").strip()
            if name:
                db.execute("INSERT INTO list_extras (name) VALUES (?)", (name,))
                db.execute(
                    "INSERT OR IGNORE INTO saved_extras (name) VALUES (?)", (name,)
                )
                db.commit()
        elif action == "quick_add":
            name = request.form.get("extra_name", "").strip()
            if name:
                db.execute("INSERT INTO list_extras (name) VALUES (?)", (name,))
                db.commit()
        elif action == "remove_extra":
            db.execute("DELETE FROM list_extras WHERE id = ?", (request.form.get("extra_id"),))
            db.commit()
        elif action == "create":
            return redirect(url_for("shopping_list"))
        return redirect(url_for("build_list"))

    ingredients = db.execute(
        "SELECT i.name, i.amount, i.unit, r.name AS recipe_name"
        " FROM selections s"
        " JOIN recipes r ON r.id = s.recipe_id"
        " JOIN ingredients i ON i.recipe_id = r.id"
        " ORDER BY s.id, i.id"
    ).fetchall()
    extras = db.execute("SELECT * FROM list_extras ORDER BY id").fetchall()
    saved = db.execute("SELECT * FROM saved_extras ORDER BY name").fetchall()
    return render_template(
        "build_list.html", ingredients=ingredients, extras=extras, saved=saved
    )


# ------------------------------------------------------- shopping list

# Amounts are free text, so "2", "1,5", "1/2" and "1 1/2" are all understood as
# numbers; anything else ("a pinch") is carried over to the list untouched.
_FRACTION = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")
_MIXED = re.compile(r"(\d+)\s+(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")


def parse_amount(text):
    """Return the numeric value of an amount, or None if it is not a number."""
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    m = _MIXED.fullmatch(text)
    if m:
        whole, num, den = (float(x) for x in m.groups())
        return whole + num / den if den else None
    m = _FRACTION.fullmatch(text)
    if m:
        num, den = (float(x) for x in m.groups())
        return num / den if den else None
    try:
        return float(text)
    except ValueError:
        return None


def format_amount(value):
    """Render a summed amount without trailing zeros: 3.0 -> "3", 1.50 -> "1.5"."""
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def combine_items(rows):
    """Merge (name, amount, unit) rows that share a name and unit.

    Numeric amounts are summed; amounts that are not numbers are kept side by
    side. The result is sorted alphabetically by name.
    """
    groups = {}
    for name, amount, unit in rows:
        name, unit = (name or "").strip(), (unit or "").strip()
        key = (name.casefold(), unit.casefold())
        group = groups.setdefault(
            key, {"name": name, "unit": unit, "total": None, "texts": []}
        )
        value = parse_amount(amount)
        if value is not None:
            group["total"] = value if group["total"] is None else group["total"] + value
        elif (amount or "").strip():
            text = amount.strip()
            if text not in group["texts"]:
                group["texts"].append(text)

    items = []
    for group in groups.values():
        parts = []
        if group["total"] is not None:
            parts.append(format_amount(group["total"]))
        parts.extend(group["texts"])
        amount_label = " + ".join(parts)
        label = " ".join(p for p in (amount_label, group["unit"], group["name"]) if p)
        items.append({"label": label, "name": group["name"], "unit": group["unit"]})

    items.sort(key=lambda item: (item["name"].casefold(), item["unit"].casefold()))
    return items


@app.route("/list")
def shopping_list():
    db = get_db()
    ingredients = db.execute(
        "SELECT i.name, i.amount, i.unit"
        " FROM selections s"
        " JOIN ingredients i ON i.recipe_id = s.recipe_id"
        " ORDER BY s.id, i.id"
    ).fetchall()
    extras = db.execute("SELECT name FROM list_extras ORDER BY id").fetchall()
    rows = [(i["name"], i["amount"], i["unit"]) for i in ingredients]
    rows += [(e["name"], "", "") for e in extras]
    return render_template("shopping_list.html", items=combine_items(rows))


# ------------------------------------------------- selected recipe page

@app.route("/selected", methods=["GET", "POST"])
def selected_recipes():
    db = get_db()
    if request.method == "POST" and request.form.get("action") == "clear":
        db.execute("DELETE FROM selections")
        db.execute("DELETE FROM list_extras")
        db.commit()
        return redirect(url_for("selected_recipes"))
    selected = db.execute(
        "SELECT r.name, r.source, s.selected_at"
        " FROM selections s JOIN recipes r ON r.id = s.recipe_id"
        " ORDER BY s.id"
    ).fetchall()
    extras = db.execute("SELECT name FROM list_extras ORDER BY id").fetchall()
    return render_template("selected.html", selected=selected, extras=extras)


init_db()


def main():
    """Entry point for the ``shopping`` console script and ``main.py``."""
    app.run(debug=True)


if __name__ == "__main__":
    main()
