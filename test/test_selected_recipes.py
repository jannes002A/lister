"""Tests for the selected_recipes view (``/selected``)."""


def test_get_renders_the_page(client):
    response = client.get("/selected")
    assert response.status_code == 200
    assert b"Selected recipes" in response.data


def test_get_shows_the_selected_recipes(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", source="noodle book"))
    body = client.get("/selected").data
    assert b"Ramen" in body and b"noodle book" in body


def test_get_hides_unselected_recipes(client, make_recipe):
    make_recipe("Gnocchi")
    assert b"Gnocchi" not in client.get("/selected").data


def test_get_keeps_the_order_the_recipes_were_selected_in(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen"))
    select_recipe(make_recipe("Gnocchi"))
    body = client.get("/selected").data.decode()
    assert body.index("Ramen") < body.index("Gnocchi")


def test_get_shows_the_extra_items(client, db):
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert b"Milk" in client.get("/selected").data


def test_clear_removes_the_selections(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen"))
    client.post("/selected", data={"action": "clear"})
    assert db.count("selections") == 0


def test_clear_removes_the_extras_of_this_run(client, db):
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    client.post("/selected", data={"action": "clear"})
    assert db.count("list_extras") == 0


def test_clear_keeps_the_saved_recipes(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")]))
    client.post("/selected", data={"action": "clear"})
    assert db.count("recipes") == 1
    assert db.count("ingredients") == 1


def test_clear_keeps_the_remembered_quick_add_items(client, db):
    client.post("/build", data={"action": "add_extra", "extra_name": "Milk"})
    client.post("/selected", data={"action": "clear"})
    assert db.count("saved_extras") == 1


def test_clear_redirects_back_to_the_page(client):
    response = client.post("/selected", data={"action": "clear"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/selected")


def test_a_post_with_another_action_clears_nothing(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen"))
    response = client.post("/selected", data={"action": "nonsense"})
    assert response.status_code == 200
    assert db.count("selections") == 1


def test_a_post_without_an_action_clears_nothing(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen"))
    client.post("/selected", data={})
    assert db.count("selections") == 1
