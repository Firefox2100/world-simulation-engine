from world_simulation_engine.component.sillytavern_converter.name_resolution import resolve_name, resolve_names


def test_resolve_name_falls_back_to_substring_match():
    id_by_name = {"Riley Bennett": "id-riley", "Casey Morgan": "id-casey"}

    assert resolve_name("Riley", id_by_name) == "id-riley"
    assert resolve_name("Riley Bennett", id_by_name) == "id-riley"


def test_resolve_name_returns_none_for_ambiguous_partial_match():
    id_by_name = {"Anna Smith": "id-anna-smith", "Anna Jones": "id-anna-jones"}

    assert resolve_name("Anna", id_by_name) is None


def test_resolve_name_never_matches_below_minimum_length():
    id_by_name = {"A": "id-short"}

    assert resolve_name("A", id_by_name) == "id-short"  # exact match still works
    assert resolve_name("Ada", id_by_name) is None  # no fuzzy absorption of a longer unrelated name


def test_resolve_names_drops_unresolved_and_preserves_order():
    id_by_name = {"Alice": "id-alice", "Bob": "id-bob"}

    assert resolve_names(["Bob", "Ghost", "Alice"], id_by_name) == ["id-bob", "id-alice"]
