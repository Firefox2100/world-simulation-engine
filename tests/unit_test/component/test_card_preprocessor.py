from world_simulation_engine.component.sillytavern_converter import CardPreprocessor
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3


def make_card(data_overrides: dict | None = None) -> SillyTavernCardV3:
    data = {
        "name": "Example",
        "description": "{{char}} is friends with {{user}}.",
        "personality": "",
        "scenario": "",
        "first_mes": "Hi {{user}}, I'm <BOT>!",
        "mes_example": "",
        "creator_notes": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "alternate_greetings": [],
        "character_book": None,
        "tags": [],
        "creator": "",
        "character_version": "",
        "extensions": {},
    }
    data.update(data_overrides or {})
    return SillyTavernCardV3.model_validate({
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": data,
    })


def test_normalizes_char_and_user_macros():
    card = make_card()
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.description == "{{ character['self'].name }} is friends with {{ character['user'].name }}."
    assert preprocessed.first_message == "Hi {{ character['user'].name }}, I'm {{ character['self'].name }}!"


def test_only_first_mes_is_used_and_alternate_greetings_are_logged():
    card = make_card({
        "first_mes": "The primary opening.",
        "alternate_greetings": ["Alt 1", "Alt 2"],
        "group_only_greetings": ["Group greeting"],
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.first_message == "The primary opening."
    assert any("2 alternate greeting" in entry for entry in preprocessed.discarded)
    assert any("1 group-only greeting" in entry for entry in preprocessed.discarded)


def test_splits_mes_example_on_start_marker_and_normalizes_macros():
    card = make_card({
        "mes_example": "<START>\n{{user}}: Hi\n{{char}}: Hello\n<START>\n{{user}}: Bye",
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert len(preprocessed.example_dialogue) == 2
    assert "character['user'].name" in preprocessed.example_dialogue[0]
    assert "character['self'].name" in preprocessed.example_dialogue[0]
    assert preprocessed.example_dialogue[1] == "{{ character['user'].name }}: Bye"


def test_disabled_lorebook_entries_are_dropped_and_enabled_ones_are_reduced():
    card = make_card({
        "character_book": {
            "name": "book",
            "entries": [
                {
                    "keys": ["Clara"],
                    "content": "{{char}} trusts Clara.",
                    "enabled": True,
                    "insertion_order": 0,
                    "id": 1,
                    "comment": "Clara bio",
                    "constant": True,
                    "position": "before_char",
                    "use_regex": False,
                },
                {
                    "keys": ["Ghost"],
                    "content": "A disabled entry that must not appear.",
                    "enabled": False,
                    "insertion_order": 1,
                    "id": 2,
                    "constant": False,
                    "position": "before_char",
                    "use_regex": False,
                },
            ],
        },
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert len(preprocessed.lorebook_entries) == 1
    entry = preprocessed.lorebook_entries[0]
    assert entry.source_id == "1"
    assert entry.name == "Clara bio"
    assert entry.keys == ["Clara"]
    assert entry.constant is True
    assert entry.content == "{{ character['self'].name }} trusts Clara."


def test_lorebook_entry_falls_back_to_comment_when_id_is_missing():
    card = make_card({
        "character_book": {
            "name": "book",
            "entries": [
                {
                    "keys": [],
                    "content": "Some lore.",
                    "enabled": True,
                    "insertion_order": 0,
                    "comment": "world_lore_1",
                    "constant": True,
                    "position": "before_char",
                    "use_regex": False,
                },
            ],
        },
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.lorebook_entries[0].source_id == "world_lore_1"


def test_always_discarded_extension_keys_are_logged_and_dropped():
    card = make_card({
        "extensions": {
            "talkativeness": "0.5",
            "fav": False,
            "world": "",
            "depth_prompt": {"prompt": "", "depth": 4, "role": "system"},
            "aicc-site": {"aicc-site-card-id": "AICC-1"},
            "regex_scripts": [{"scriptName": "status bar"}],
        },
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.variable_schema_candidates == []
    junk_log = next(entry for entry in preprocessed.discarded if "runtime metadata" in entry)
    for key in ("talkativeness", "fav", "world", "depth_prompt", "aicc-site", "regex_scripts"):
        assert key in junk_log


def test_variable_schema_script_is_forwarded_not_discarded():
    schema_script = (
        "export const Schema = z.object({\n"
        "  health: z.coerce.number().describe('HP').prefault(100),\n"
        "});"
    )
    card = make_card({
        "extensions": {
            "tavern_helper": {
                "scripts": [
                    {"type": "script", "enabled": True, "name": "MVU", "content": "import 'mvu.js';"},
                    {"type": "script", "enabled": True, "name": "ZOD", "content": schema_script},
                    {"type": "script", "enabled": False, "name": "Disabled", "content": schema_script},
                ],
            },
        },
    })
    preprocessed = CardPreprocessor.preprocess(card)

    assert len(preprocessed.variable_schema_candidates) == 1
    candidate = preprocessed.variable_schema_candidates[0]
    assert candidate.name == "ZOD"
    assert candidate.content == schema_script
    assert candidate.source == "tavern_helper_script"

    discarded_log = " ".join(preprocessed.discarded)
    assert "MVU" in discarded_log
    assert "Disabled" not in discarded_log  # the disabled script is skipped entirely, not logged


def test_unrecognized_extension_keys_are_logged_not_silently_dropped():
    card = make_card({"extensions": {"some_future_field": {"nested": True}}})
    preprocessed = CardPreprocessor.preprocess(card)

    assert any("some_future_field" in entry for entry in preprocessed.discarded)


def test_tags_pass_through_unchanged():
    card = make_card({"tags": ["Horror", "Slice of Life"]})
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.tags == ["Horror", "Slice of Life"]


def test_text_without_macros_is_unaffected():
    card = make_card({"description": "A plain description with no macros at all."})
    preprocessed = CardPreprocessor.preprocess(card)

    assert preprocessed.description == "A plain description with no macros at all."
