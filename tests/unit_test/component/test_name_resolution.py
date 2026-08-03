from world_simulation_engine.component.sillytavern_converter.name_resolution import resolve_name, resolve_names


def test_resolve_name_falls_back_to_substring_match():
    # Regression for a real bug found on card 02: a relationship about "艾琳·莫里亚蒂" resolved to
    # zero relationships because the model returned "艾琳" (a shorter surface form), which failed
    # exact-match resolution against the full roster name.
    id_by_name = {"艾琳·莫里亚蒂": "id-irene", "陌白·福尔摩斯": "id-mobai"}

    assert resolve_name("艾琳", id_by_name) == "id-irene"
    assert resolve_name("艾琳·莫里亚蒂", id_by_name) == "id-irene"


def test_resolve_name_returns_none_for_ambiguous_partial_match():
    id_by_name = {"Anna Smith": "id-anna-smith", "Anna Jones": "id-anna-jones"}

    assert resolve_name("Anna", id_by_name) is None


def test_resolve_name_never_matches_below_minimum_length():
    id_by_name = {"凛": "id-lin"}

    assert resolve_name("凛", id_by_name) == "id-lin"  # exact match still works
    assert resolve_name("神代凛霜", id_by_name) is None  # no fuzzy absorption of a longer unrelated name


def test_resolve_names_drops_unresolved_and_preserves_order():
    id_by_name = {"Alice": "id-alice", "Bob": "id-bob"}

    assert resolve_names(["Bob", "Ghost", "Alice"], id_by_name) == ["id-bob", "id-alice"]
