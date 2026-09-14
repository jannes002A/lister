"""Tests for the shopping_list view (``/list``)."""


def test_get_renders_the_page(client):
    response = client.get("/list")
    assert response.status_code == 200
    assert b"Shopping list" in response.data


def test_an_empty_run_produces_no_items(client):
    assert client.get("/list").data.count(b'type="checkbox"') == 0


def test_ingredients_of_selected_recipes_are_listed(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")]))
    assert b"2 pieces Noodles" in client.get("/list").data


def test_an_ingredient_without_an_amount_still_shows_its_unit(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "", "pieces")]))
    assert b"pieces Noodles" in client.get("/list").data


def test_extras_are_listed(client, db):
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert b"Milk" in client.get("/list").data


def test_extras_are_sorted_in_among_the_ingredients(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")]))
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    body = client.get("/list").data.decode()
    assert body.index("Milk") < body.index("Noodles")


def test_items_are_sorted_alphabetically_across_recipes(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")]))
    select_recipe(make_recipe("Gnocchi", ingredients=[("Aubergine", "1", "kg")]))
    body = client.get("/list").data.decode()
    assert body.index("Aubergine") < body.index("Noodles")


def test_items_are_sorted_alphabetically_within_one_recipe(client, make_recipe, select_recipe):
    select_recipe(
        make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces"), ("Miso", "1", "kg")])
    )
    body = client.get("/list").data.decode()
    assert body.index("Miso") < body.index("Noodles")


def test_sorting_ignores_case(client, db):
    for name in ("banana", "Apple", "cherry"):
        db.execute("INSERT INTO list_extras (name) VALUES (?)", (name,))
    body = client.get("/list").data.decode()
    assert body.index("Apple") < body.index("banana") < body.index("cherry")


def test_ingredients_of_unselected_recipes_are_left_out(client, make_recipe):
    make_recipe("Gnocchi", ingredients=[("Potatoes", "1", "kg")])
    assert b"Potatoes" not in client.get("/list").data


def test_a_recipe_selected_twice_sums_its_ingredients(client, make_recipe, select_recipe):
    recipe_id = make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")])
    select_recipe(recipe_id)
    select_recipe(recipe_id)
    body = client.get("/list").data
    assert body.count(b"Noodles") == 1
    assert b"4 pieces Noodles" in body


def test_the_same_ingredient_from_two_recipes_is_summed(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Onion", "2", "pieces")]))
    select_recipe(make_recipe("Curry", ingredients=[("Onion", "3", "pieces")]))
    assert b"5 pieces Onion" in client.get("/list").data


def test_the_same_ingredient_with_different_units_stays_separate(client, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Onion", "2", "pieces")]))
    select_recipe(make_recipe("Curry", ingredients=[("Onion", "1", "kg")]))
    body = client.get("/list").data
    assert b"1 kg Onion" in body and b"2 pieces Onion" in body


def test_duplicate_extras_are_merged(client, db):
    for _ in range(2):
        db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert client.get("/list").data.count(b"Milk") == 1


def test_an_extra_does_not_merge_with_an_ingredient_of_the_same_name(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Milk", "1", "kg")]))
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert client.get("/list").data.count(b"Milk") == 2


def test_every_item_gets_a_checkbox(client, db, make_recipe, select_recipe):
    select_recipe(make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")]))
    db.execute("INSERT INTO list_extras (name) VALUES (?)", ("Milk",))
    assert client.get("/list").data.count(b'type="checkbox"') == 2


def test_merged_items_get_one_checkbox_each(client, make_recipe, select_recipe):
    recipe_id = make_recipe("Ramen", ingredients=[("Noodles", "2", "pieces")])
    select_recipe(recipe_id)
    select_recipe(recipe_id)
    assert client.get("/list").data.count(b'type="checkbox"') == 1
