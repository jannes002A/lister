# lister — a recipe & shopping list app

A small Flask app with a SQLite database for planning what to cook and generating a shopping list.

## Run it

```bash
uv sync          # creates .venv and installs the project (editable) + dev deps
uv run main.py   # or: uv run shopping
```

Then open http://127.0.0.1:5000 in your browser. The database file `shopping.db` is created automatically on first run, next to the package in `src/`.

## Test it

```bash
uv run pytest    # 145 tests
```

## Pages

1. **New recipe** (`/`) — create recipes with a name, a free-text source (book or website), and any number of ingredients. Each ingredient has a free-text amount field and a unit dropdown (pieces / kg). Use "+ Add ingredient" for more rows, "✕" to drop one. Saved recipes are listed underneath.
2. **Pick recipes** (`/plan`) — a dropdown of all recipes. Selected recipes appear in a list below with a Remove button; the same recipe can be added twice if you want double the ingredients. "Create shopping list" continues to the next step.
3. **Build list** (`/build`) — shows all ingredients of the selected recipes, one row each, labelled with the recipe they came from (nothing is merged here on purpose). A free-text field adds extra ingredients; everything you add is stored in the database and shows up on future runs as a click-to-add button. Extras added to the current list can be removed again. "Create shopping list" generates the final list.
4. **Shopping list** (`/list`) — a to-do style list with a checkbox next to each item. Ticking a box crosses the item out and moves it to the bottom; unticking brings it back up. This is the only page that merges duplicates — see below.
5. **Selected recipes** (`/selected`) — shows the recipes (with the time they were picked) and extra items chosen in this run. The button at the bottom clears all selected recipes and the extra ingredients of this run. Saved recipes and the remembered quick-add ingredients are kept.

## How the final list is put together

Amounts are free text, so `/list` parses before it adds anything up:

- `2`, `1.5`, `1,5` (decimal comma), `1/2` and `1 1/2` are all understood as numbers.
- Anything else — `a pinch`, `to taste` — is kept verbatim rather than dropped.

Items are then grouped by name *and* unit, ignoring case. Numeric amounts are summed,
and unparsable ones are appended after a `+`, so three recipes wanting `2 pieces Salt`,
`3 pieces Salt` and `a pinch pieces Salt` produce one line: `5 + a pinch pieces Salt`.
The list is sorted alphabetically, case-insensitively.

There is no unit conversion: the same name with a different unit stays on its own line.
Extra items carry no unit at all, so an extra `Milk` never merges with an ingredient
`1 kg Milk`.

## What survives a "clear"

The app distinguishes the current shopping run from your permanent library:

| Kept forever | Wiped by "Clear" on `/selected` |
| --- | --- |
| recipes and their ingredients | the recipes picked for this run |
| every extra item ever typed, offered as a quick-add button | the extras added to this run's list |

That is why adding an extra on `/build` writes it in two places, while clicking a
quick-add button only adds it to the current list.

## Files

```
main.py                      Entry point (starts the dev server)
pyproject.toml               Project metadata, dependencies, packaging, pytest config
src/app.py                   Flask routes, SQLite schema, amount parsing & merging
src/templates/               Jinja2 templates (one per page, plus base.html)
src/static/style.css         Styling
test/conftest.py             Fixtures: isolated temp DB, test client, assertion helpers
test/                        Test suite (pytest)
```

`src/` is itself the installable package, so both the app and the tests import it
as `src.app` with no `sys.path` tricks. `uv sync` installs it in editable mode.
`requirements.txt` is a leftover; `pyproject.toml` is the source of truth for dependencies.
