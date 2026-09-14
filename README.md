# grocer — a recipe & shopping list app

A small Flask app with a SQLite database for planning what to cook and generating a shopping list.

## Run it

```bash
uv sync          # creates .venv and installs the project (editable) + dev deps
uv run main.py   # or: uv run shopping
```

Then open http://127.0.0.1:5000 in your browser. The database file `shopping.db` is created automatically on first run, next to the package in `src/`.

## Test it

```bash
uv run pytest
```

## Pages

1. **New recipe** (`/`) — create recipes with a name, a free-text source (book or website), and any number of ingredients. Each ingredient has a free-text amount field and a unit dropdown (pieces / kg). Use "+ Add ingredient" for more rows.
2. **Pick recipes** (`/plan`) — a dropdown of all recipes. Selected recipes appear in a list below with a Remove button. "Create shopping list" continues to the next step.
3. **Build list** (`/build`) — shows all ingredients of the selected recipes. A free-text field adds extra ingredients; everything you add is stored in the database and shows up on future runs as a click-to-add button. "Create shopping list" generates the final list.
4. **Shopping list** (`/list`) — a to-do style list with a checkbox next to each item. Ticking a box crosses the item out and moves it to the bottom; unticking brings it back up.
5. **Selected recipes** (`/selected`) — shows the recipes (and extra items) chosen in this run. The button at the bottom clears all selected recipes and the extra ingredients of this run. Saved recipes and the remembered quick-add ingredients are kept.

## Files

```
main.py                      Entry point (starts the dev server)
pyproject.toml               Project metadata, dependencies, packaging, pytest config
src/app.py                   Flask routes + SQLite schema
src/templates/               Jinja2 templates (one per page)
src/static/style.css         Styling
test/                        Test suite (pytest)
```

`src/` is itself the installable package, so both the app and the tests import it
as `src.app` with no `sys.path` tricks. `uv sync` installs it in editable mode.
