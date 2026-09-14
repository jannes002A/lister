"""Tests for the plan view (``/plan``)."""


def test_get_renders_the_page(client):
    response = client.get("/plan")
    assert response.status_code == 200
    assert b"Pick recipes" in response.data


def test_get_offers_every_recipe(client, make_recipe):
    make_recipe("Ramen")
    make_recipe("Gnocchi")
    body = client.get("/plan").data
    assert b"Ramen" in body and b"Gnocchi" in body


def test_get_offers_recipes_ordered_by_name(client, make_recipe):
    for name in ("Ramen", "Gnocchi", "Borscht"):
        make_recipe(name)
    body = client.get("/plan").data.decode()
    assert body.index("Borscht") < body.index("Gnocchi") < body.index("Ramen")


def test_add_selects_the_recipe(client, db, make_recipe):
    recipe_id = make_recipe("Ramen")
    client.post("/plan", data={"action": "add", "recipe_id": recipe_id})
    assert db.scalar("SELECT recipe_id FROM selections") == recipe_id


def test_add_redirects_back_to_plan(client, make_recipe):
    recipe_id = make_recipe("Ramen")
    response = client.post("/plan", data={"action": "add", "recipe_id": recipe_id})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/plan")


def test_add_records_a_timestamp(client, db, make_recipe):
    client.post("/plan", data={"action": "add", "recipe_id": make_recipe("Ramen")})
    assert db.scalar("SELECT selected_at FROM selections") is not None


def test_add_without_a_recipe_id_selects_nothing(client, db):
    client.post("/plan", data={"action": "add"})
    assert db.count("selections") == 0


def test_add_can_select_the_same_recipe_twice(client, db, make_recipe):
    recipe_id = make_recipe("Ramen")
    for _ in range(2):
        client.post("/plan", data={"action": "add", "recipe_id": recipe_id})
    assert db.count("selections") == 2


def test_selected_recipes_are_shown(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", source="noodle book"))
    body = client.get("/plan").data
    assert b"Ramen" in body and b"noodle book" in body


def test_remove_deletes_the_selection(client, db, make_recipe, select_recipe):
    selection_id = select_recipe(make_recipe("Ramen"))
    client.post("/plan", data={"action": "remove", "selection_id": selection_id})
    assert db.count("selections") == 0


def test_remove_keeps_the_recipe_itself(client, db, make_recipe, select_recipe):
    selection_id = select_recipe(make_recipe("Ramen"))
    client.post("/plan", data={"action": "remove", "selection_id": selection_id})
    assert db.count("recipes") == 1


def test_remove_only_deletes_the_named_selection(client, db, make_recipe, select_recipe):
    keep = select_recipe(make_recipe("Ramen"))
    drop = select_recipe(make_recipe("Gnocchi"))
    client.post("/plan", data={"action": "remove", "selection_id": drop})
    assert [r["id"] for r in db.query("SELECT id FROM selections")] == [keep]


def test_remove_redirects_back_to_plan(client, make_recipe, select_recipe):
    selection_id = select_recipe(make_recipe("Ramen"))
    response = client.post("/plan", data={"action": "remove", "selection_id": selection_id})
    assert response.headers["Location"].endswith("/plan")


def test_create_redirects_to_the_build_page(client):
    response = client.post("/plan", data={"action": "create"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/build")


def test_an_unknown_action_redirects_back_to_plan(client, db):
    response = client.post("/plan", data={"action": "nonsense"})
    assert response.headers["Location"].endswith("/plan")
    assert db.count("selections") == 0


def test_a_post_without_an_action_redirects_back_to_plan(client):
    assert client.post("/plan", data={}).headers["Location"].endswith("/plan")
