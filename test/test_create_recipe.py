"""Tests for the create_recipe view (``/``)."""


def post_recipe(client, **form):
    return client.post("/", data=form)


def test_get_renders_the_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"New recipe" in response.data


def test_get_lists_existing_recipes(client, make_recipe):
    make_recipe("Lasagne")
    assert b"Lasagne" in client.get("/").data


def test_get_lists_recipes_ordered_by_name(client, make_recipe):
    for name in ("Zucchini bake", "Apple pie", "Miso soup"):
        make_recipe(name)
    body = client.get("/").data.decode()
    assert body.index("Apple pie") < body.index("Miso soup") < body.index("Zucchini bake")


def test_post_saves_the_recipe(client, db):
    post_recipe(client, name="Pesto", source="grandma")
    row = db.query("SELECT * FROM recipes")[0]
    assert row["name"] == "Pesto"
    assert row["source"] == "grandma"


def test_post_saves_the_ingredients(client, db):
    post_recipe(
        client,
        name="Pesto",
        ing_name=["Basil", "Pine nuts"],
        ing_amount=["100", "50"],
        ing_unit=["pieces", "kg"],
    )
    rows = db.query("SELECT * FROM ingredients ORDER BY id")
    assert [(r["name"], r["amount"], r["unit"]) for r in rows] == [
        ("Basil", "100", "pieces"),
        ("Pine nuts", "50", "kg"),
    ]


def test_post_links_ingredients_to_their_recipe(client, db):
    post_recipe(client, name="Pesto", ing_name=["Basil"], ing_amount=["1"], ing_unit=["kg"])
    recipe_id = db.scalar("SELECT id FROM recipes")
    assert db.scalar("SELECT recipe_id FROM ingredients") == recipe_id


def test_post_strips_whitespace_from_the_fields(client, db):
    post_recipe(
        client,
        name="  Pesto  ",
        source="  book  ",
        ing_name=["  Basil  "],
        ing_amount=["  100  "],
        ing_unit=["kg"],
    )
    recipe = db.query("SELECT * FROM recipes")[0]
    ingredient = db.query("SELECT * FROM ingredients")[0]
    assert recipe["name"] == "Pesto"
    assert recipe["source"] == "book"
    assert ingredient["name"] == "Basil"
    assert ingredient["amount"] == "100"


def test_post_without_a_name_saves_nothing(client, db):
    post_recipe(client, name="   ", ing_name=["Basil"], ing_amount=["1"], ing_unit=["kg"])
    assert db.count("recipes") == 0
    assert db.count("ingredients") == 0


def test_post_skips_ingredients_with_a_blank_name(client, db):
    post_recipe(
        client,
        name="Pesto",
        ing_name=["Basil", "   ", ""],
        ing_amount=["100", "1", "2"],
        ing_unit=["kg", "kg", "kg"],
    )
    assert [r["name"] for r in db.query("SELECT name FROM ingredients")] == ["Basil"]


def test_post_falls_back_to_pieces_for_an_unknown_unit(client, db):
    post_recipe(client, name="Pesto", ing_name=["Basil"], ing_amount=["1"], ing_unit=["litres"])
    assert db.scalar("SELECT unit FROM ingredients") == "pieces"


def test_post_keeps_kg_as_a_unit(client, db):
    post_recipe(client, name="Pesto", ing_name=["Basil"], ing_amount=["1"], ing_unit=["kg"])
    assert db.scalar("SELECT unit FROM ingredients") == "kg"


def test_post_ignores_ingredient_rows_without_a_matching_amount_or_unit(client, db):
    # zip() stops at the shortest list, so trailing names without a unit are dropped.
    post_recipe(client, name="Pesto", ing_name=["Basil", "Garlic"], ing_amount=["1"], ing_unit=["kg"])
    assert [r["name"] for r in db.query("SELECT name FROM ingredients")] == ["Basil"]


def test_post_allows_a_recipe_without_ingredients(client, db):
    post_recipe(client, name="Toast")
    assert db.count("recipes") == 1
    assert db.count("ingredients") == 0


def test_post_defaults_the_source_to_an_empty_string(client, db):
    post_recipe(client, name="Toast")
    assert db.scalar("SELECT source FROM recipes") == ""


def test_post_confirms_the_save_on_the_page(client):
    response = post_recipe(client, name="Pesto")
    assert "Recipe “Pesto” saved." in response.data.decode()


def test_post_shows_the_new_recipe_in_the_list(client):
    assert b"Pesto" in post_recipe(client, name="Pesto").data


def test_get_shows_no_message(client):
    assert "saved." not in client.get("/").data.decode()


def test_post_allows_two_recipes_with_the_same_name(client, db):
    post_recipe(client, name="Pesto")
    post_recipe(client, name="Pesto")
    assert db.count("recipes") == 2
