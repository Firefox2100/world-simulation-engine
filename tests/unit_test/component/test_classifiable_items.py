from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.classifiable_items import classifiable_items, \
    content_by_item_id


def make_card() -> PreprocessedCard:
    return PreprocessedCard(
        name="Example",
        description="Example is a fictional resident.",
        personality="",
        scenario="",
        first_message="Hi!",
        system_prompt="",
        post_history_instructions="",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="Stage 1", keys=["seal"], content="The seal breaks."),
            PreprocessedLorebookEntry(source_id="2", name=None, keys=[], content="Empty-named entry."),
        ],
    )


def test_classifiable_items_covers_nonempty_fields_and_all_lorebook_entries():
    card = make_card()

    items = classifiable_items(card)

    item_ids = {item.item_id for item in items}
    assert item_ids == {"field:description", "entry:1", "entry:2"}
    # Empty fields (personality, scenario, system_prompt, post_history_instructions) are skipped.
    assert not any(item_id.startswith("field:personality") for item_id in item_ids)
    description_item = next(item for item in items if item.item_id == "field:description")
    assert description_item.content == "Example is a fictional resident."
    assert description_item.card_name == "Example"
    entry_item = next(item for item in items if item.item_id == "entry:1")
    assert entry_item.label == "Stage 1"
    assert entry_item.keys == ["seal"]
    unnamed_entry_item = next(item for item in items if item.item_id == "entry:2")
    assert unnamed_entry_item.label == "2"  # falls back to source_id when name is None


def test_classifiable_items_empty_card_yields_no_items():
    card = PreprocessedCard(name="Empty", first_message="Hi")

    items = classifiable_items(card)

    assert items == []


def test_content_by_item_id_indexes_the_same_items():
    card = make_card()

    index = content_by_item_id(card)

    assert index == {
        "field:description": "Example is a fictional resident.",
        "entry:1": "The seal breaks.",
        "entry:2": "Empty-named entry.",
    }
