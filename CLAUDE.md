# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                      # create .venv, install project (editable) + dev deps
uv run main.py               # start the dev server on http://127.0.0.1:5000
uv run shopping              # same thing, via the console script
uv run pytest                # full suite (145 tests)
uv run pytest test/test_db.py::test_close_db_actually_closes_the_connection   # one test
uv run pytest -k "combine"   # by name
```

```bash
docker compose up -d --build   # deploy on http://127.0.0.1:8000
docker compose logs -f         # follow gunicorn's output
```

There is no linter or build step configured. `requirements.txt` is a leftover —
`pyproject.toml` is the source of truth for dependencies.

## Packaging: `src/` *is* the package

Imports are `from src.app import ...`, not `from app import ...`. `pyproject.toml`
declares `packages = ["src"]` and `uv sync` installs it editable, which is what makes
`src.app` importable from `main.py` and from the tests.

Two consequences worth knowing before editing:

- **Never add `sys.path` manipulation.** It was deliberately removed; the editable
  install replaces it.
- **`src/__init__.py` must stay docstring-only.** Adding `from src.app import app`
  there rebinds the `app` attribute on the package from the *submodule* to the Flask
  *object*, so `from src import app as app_module` would silently return the wrong thing.

The layout was previously `src/shopping/`; it was flattened by choice. The tradeoff is
that a built wheel's top-level package is literally named `src`, which would collide if
this were ever published.

## Deployment

`Dockerfile` + `compose.yaml` run the app under gunicorn (`gunicorn.conf.py`), never
Flask's dev server — `app.run(debug=True)` in `main()` is for local work only, since the
Werkzeug debugger is a remote code execution console.

Two constraints the container puts on the code:

- **The code directory is read-only at runtime.** Nothing may write next to the package.
  `DB_PATH` therefore honours `LISTER_DB_PATH`, which compose points at `/data` on a
  volume. Keep any new writable path configurable the same way.
- **One gunicorn worker, several threads.** Multiple *processes* writing the one SQLite
  file contend for a whole-file lock and fail with "database is locked". Don't raise
  `workers` in `gunicorn.conf.py`.

`.dockerignore` is a deny-by-default allowlist: a new file the build genuinely needs has
to be added there explicitly, which is what keeps `src/shopping.db` and stray secrets out
of the image.

## Architecture

Everything lives in `src/app.py` — schema, connection handling, all five routes, and the
list-merging helpers. No blueprints, no ORM, no models layer.

### Per-run state vs. permanent state

This is the central concept, and it's the reason there are five tables:

| Table | Lifetime |
| --- | --- |
| `recipes`, `ingredients` | permanent library |
| `selections` | **current run** — recipes picked for this shop |
| `list_extras` | **current run** — ad-hoc items typed in |
| `saved_extras` | permanent — every extra ever typed, offered as quick-add buttons forever |

The "clear" action on `/selected` wipes `selections` and `list_extras` only. Recipes,
ingredients, and `saved_extras` survive. `/build` reflects this split directly:
`add_extra` writes to both `list_extras` and `saved_extras` (`INSERT OR IGNORE`), while
`quick_add` writes only to `list_extras`.

The user flow is a pipeline: `/` (create recipes) → `/plan` (pick) → `/build` (add
extras) → `/list` (final list), with `/selected` as the reset point.

### Database connection

`DB_PATH` is a module-level global read *inside* `get_db()` at call time, not captured at
import. Tests depend on this: they monkeypatch `src.app.DB_PATH` to a `tmp_path` file.
Don't inline it or bind it at import time.

Connections are cached on Flask's `g` and closed by a `teardown_appcontext` hook, so one
connection is reused per request and never leaks across them.

`init_db()` is called at **module import time** (bottom of `app.py`), meaning merely
importing `src.app` creates `src/shopping.db` as a side effect. `test/conftest.py` deletes
that stray file after import.

### Amounts are free text

`ingredients.amount` is a TEXT column holding whatever the user typed, so any arithmetic
has to parse first:

- `parse_amount` understands `2`, `1.5`, `1,5` (decimal comma), `1/2`, `1 1/2`; anything
  else (`"a pinch"`) returns `None`.
- `combine_items` groups rows by *(casefolded name, casefolded unit)*, sums the numeric
  amounts, and appends unparsable ones after a `+` rather than discarding them
  (`"5 + a pinch pieces Salt"`). Output is sorted alphabetically, case-insensitively.

Only `/list` merges. `/build` deliberately shows ingredients ungrouped in selection order,
because it labels which recipe each one came from.

Same name + different unit stays separate — there is no unit conversion. Extras carry an
empty unit, so an extra `Milk` never merges with an ingredient `1 kg Milk`.

`unit` is constrained at write time in `create_recipe`: anything other than `"kg"` is
coerced to `"pieces"`.

## Tests

`test/` is a package; pytest runs with `--import-mode=importlib` and `testpaths = ["test"]`.

Fixtures in `test/conftest.py`:

- `app` — monkeypatches `DB_PATH` to a fresh `tmp_path` DB and runs `init_db()`, so every
  test gets an isolated database.
- `client` — Flask test client. **Route behaviour is tested over HTTP**, not by calling
  view functions directly.
- `db` — assertion helper (`query` / `execute` / `scalar` / `count`) that opens a *fresh*
  connection per call, deliberately independent of the request-context connection.
- `make_recipe`, `select_recipe` — data builders.

`test_combine_items.py` unit-tests the helpers directly; the rest go through the client.

When changing list ordering or merging, expect `test_shopping_list.py` to fail loudly —
several tests exist specifically to pin ordering and de-duplication behaviour.
