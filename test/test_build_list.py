"""Tests for the build_list view (``/build``)."""

import pytest


@pytest.fixture
def selected_ramen(make_recipe, select_recipe):
    recipe_id = make_recipe(
        "Ramen", ingredients=[("Noodles", "2", "pieces"), ("Miso", "1", "kg")]
    )
    select_recipe(recipe_id)
    return recipe_id


def test_get_renders_the_page(client):
    response = client.get("/build")
    assert response.status_code == 200
    assert b"Build list" in response.data


def test_get_shows_the_ingredients_of_selected_recipes(client, selected_ramen):
    body = client.get("/build").data
    assert b"Noodles" in body and b"Miso" in body


def test_get_names_the_recipe_each_ingredient_comes_from(client, selected_ramen):
    assert b"Ramen" in client.get("/build").data


def test_get_hides_ingredients_of_unselected_recipes(client, make_recipe):
    make_recipe("Gnocchi", ingredients=[("Potatoes", "1", "kg")])
    assert b"Potatoes" not in client.get("/build").data


def test_get_lists_an_ingredient_once_per_selection(client, make_recipe, select_recipe):
    recipe_id = make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")])
    select_recipe(recipe_id)
    select_recipe(recipe_id)
    assert client.get("/build").data.count(b"Noodles") == 2


def test_add_extra_puts_the_item_on_the_list(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    assert [r["name"] for r in db.query("SELECT name FROM list_extras")] == ["Milk"]


def test_add_extra_remembers_the_item_for_later_runs(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    assert [r["name"] for r in db.query("SELECT name FROM saved_extras")] == ["Milk"]


def test_add_extra_strips_whitespace(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "  Milk  "})
    assert db.scalar("SELECT name FROM list_extras") == "Milk"


def test_add_extra_ignores_an_empty_name(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "   "})
    assert db.count("list_extras") == 0
    assert db.count("saved_extras") == 0


def test_add_extra_twice_remembers_the_item_only_once(client, db):
    for _ in range(2):
        client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    assert db.count("saved_extras") == 1
    assert db.count("list_extras") == 2


def test_add_extra_redirects_back_to_build(client):
    response = client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/build")


def test_quick_add_puts_the_item_on_the_list(client, db):
    client.post("/build", data={"action": "quick_add", "extra_name": "Milk"})
    assert db.scalar("SELECT name FROM list_extras") == "Milk"


def test_quick_add_does_not_remember_the_item(client, db):
    client.post("/build", data={"action": "quick_add", "extra_name": "Milk"})
    assert db.count("saved_extras") == 0


def test_quick_add_ignores_an_empty_name(client, db):
    client.post("/build", data={"action": "quick_add", "extra_name": ""})
    assert db.count("list_extras") == 0


def test_remembered_extras_are_offered_on_the_page(client, db):
    db.execute("INSERT INTO saved_extras (name) VALUES (?)", ("Coffee",))
    assert b"Coffee" in client.get("/build").data


def test_remembered_extras_are_offered_in_alphabetical_order(client, db):
    for name in ("Milk", "Bread", "Coffee"):
        db.execute("INSERT INTO saved_extras (name) VALUES (?)", (name,))
    body = client.get("/build").data.decode()
    assert body.index("Bread") < body.index("Coffee") < body.index("Milk")


def test_extras_on_the_current_list_are_shown(client, db):
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert b"Milk" in client.get("/build").data


def test_remove_extra_deletes_the_item(client, db):
    extra_id = db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    client.post("/build", data={"action": "remove_extra", "extra_id": extra_id})
    assert db.count("list_extras") == 0


def test_remove_extra_keeps_the_remembered_item(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    extra_id = db.scalar("SELECT id FROM list_extras")
    client.post("/build", data={"action": "remove_extra", "extra_id": extra_id})
    assert db.count("saved_extras") == 1


def test_remove_extra_only_deletes_the_named_item(client, db):
    keep = db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    drop = db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Bread",))
    client.post("/build", data={"action": "remove_extra", "extra_id": drop})
    assert [r["id"] for r in db.query("SELECT id FROM list_extras")] == [keep]


def test_create_redirects_to_the_shopping_list(client):
    response = client.post("/build", data={"action": "create"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/list")


def test_an_unknown_action_redirects_back_to_build(client, db):
    response = client.post("/build", data={"action": "nonsense"})
    assert response.headers["Location"].endswith("/build")
    assert db.count("list_extras") == 0
