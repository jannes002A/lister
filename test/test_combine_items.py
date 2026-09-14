"""Tests for the shopping-list helpers: parse_amount, format_amount, combine_items."""

import pytest

from src.app import combine_items, format_amount, parse_amount


# ------------------------------------------------------------ parse_amount

@pytest.mark.parametrize(
    "text, expected",
    [
        ("2", 2.0),
        ("0", 0.0),
        ("1.5", 1.5),
        ("1,5", 1.5),          # German-style decimal comma
        ("  3  ", 3.0),
        ("1/2", 0.5),
        ("3 / 4", 0.75),
        ("1 1/2", 1.5),        # mixed number
        ("2 3/4", 2.75),
    ],
)
def test_parse_amount_reads_numbers(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "   ", None, "a pinch", "some", "2 packs", "1/0", "-"])
def test_parse_amount_returns_none_for_anything_else(text):
    assert parse_amount(text) is None


# ----------------------------------------------------------- format_amount

@pytest.mark.parametrize(
    "value, expected",
    [(3.0, "3"), (0.0, "0"), (1.5, "1.5"), (1.50, "1.5"), (2.25, "2.25"), (0.5, "0.5")],
)
def test_format_amount_drops_trailing_zeros(value, expected):
    assert format_amount(value) == expected


# ----------------------------------------------------------- combine_items

def labels(rows):
    return [item["label"] for item in combine_items(rows)]


def test_no_rows_gives_no_items():
    assert combine_items([]) == []


def test_a_single_row_keeps_its_label():
    assert labels([("Noodles", "2", "pieces")]) == ["2 pieces Noodles"]


def test_rows_with_the_same_name_and_unit_are_summed():
    assert labels([("Onion", "2", "pieces"), ("Onion", "3", "pieces")]) == ["5 pieces Onion"]


def test_a_different_unit_is_not_summed():
    assert labels([("Onion", "2", "pieces"), ("Onion", "1", "kg")]) == [
        "1 kg Onion",
        "2 pieces Onion",
    ]


def test_a_different_name_is_not_summed():
    assert labels([("Onion", "2", "pieces"), ("Garlic", "1", "pieces")]) == [
        "1 pieces Garlic",
        "2 pieces Onion",
    ]


def test_merging_ignores_case_and_surrounding_whitespace():
    assert labels([("Onion", "2", "pieces"), ("  onion ", "3", " PIECES ")]) == [
        "5 pieces Onion"
    ]


def test_the_first_spelling_is_the_one_displayed():
    assert labels([("ONION", "1", "pieces"), ("onion", "1", "pieces")]) == ["2 pieces ONION"]


def test_fractions_are_summed():
    assert labels([("Milk", "1/2", "kg"), ("Milk", "1/4", "kg")]) == ["0.75 kg Milk"]


def test_decimal_commas_are_summed():
    assert labels([("Milk", "1,5", "kg"), ("Milk", "0,5", "kg")]) == ["2 kg Milk"]


def test_items_are_sorted_alphabetically():
    assert [i["name"] for i in combine_items(
        [("Zucchini", "1", "kg"), ("Apple", "1", "kg"), ("Milk", "1", "kg")]
    )] == ["Apple", "Milk", "Zucchini"]


def test_sorting_ignores_case():
    assert [i["name"] for i in combine_items(
        [("banana", "1", "kg"), ("Apple", "1", "kg"), ("Cherry", "1", "kg")]
    )] == ["Apple", "banana", "Cherry"]


def test_an_empty_amount_leaves_just_the_unit_and_name():
    assert labels([("Noodles", "", "pieces")]) == ["pieces Noodles"]


def test_empty_amounts_merge_without_inventing_a_number():
    assert labels([("Noodles", "", "pieces"), ("Noodles", "", "pieces")]) == ["pieces Noodles"]


def test_an_empty_unit_leaves_just_the_name():
    assert labels([("Milk", "", "")]) == ["Milk"]


def test_an_amount_without_a_unit_keeps_the_amount():
    assert labels([("Milk", "2", "")]) == ["2 Milk"]


def test_an_unparsable_amount_is_carried_over_untouched():
    assert labels([("Salt", "a pinch", "pieces")]) == ["a pinch pieces Salt"]


def test_unparsable_amounts_are_listed_next_to_the_sum():
    assert labels([("Salt", "2", "pieces"), ("Salt", "a pinch", "pieces")]) == [
        "2 + a pinch pieces Salt"
    ]


def test_two_different_unparsable_amounts_are_both_kept():
    assert labels([("Salt", "a pinch", "pieces"), ("Salt", "a dash", "pieces")]) == [
        "a pinch + a dash pieces Salt"
    ]


def test_a_repeated_unparsable_amount_is_only_listed_once():
    assert labels([("Salt", "a pinch", "pieces"), ("Salt", "a pinch", "pieces")]) == [
        "a pinch pieces Salt"
    ]


def test_an_empty_amount_does_not_disturb_a_sum():
    assert labels([("Onion", "2", "pieces"), ("Onion", "", "pieces")]) == ["2 pieces Onion"]


def test_each_item_reports_its_name_and_unit():
    item = combine_items([("Onion", "2", "pieces")])[0]
    assert item["name"] == "Onion" and item["unit"] == "pieces"
