from world_simulation_engine.misc.placeholder import PlaceholderContext, PlaceholderEntity, render_placeholders


def _context() -> PlaceholderContext:
    context = PlaceholderContext()
    context.add("character", id="character_1", name="Arthur Moore")
    context.add("character", id="character_2", name="Clara Whitlock")
    context.add("location", id="location_1", name="Iron Stag Inn")
    return context


def test_renders_known_character_reference():
    text = "{{ character['character_2'].name }} works behind the bar."
    assert render_placeholders(text, _context()) == "Clara Whitlock works behind the bar."


def test_renders_multiple_groups_in_one_string():
    text = "{{ character['character_1'].name }} arrives at {{ location['location_1'].name }}."
    assert render_placeholders(text, _context()) == "Arthur Moore arrives at Iron Stag Inn."


def test_text_without_placeholder_syntax_is_returned_unchanged():
    text = "A plain sentence with no template syntax at all."
    assert render_placeholders(text, _context()) is text


def test_unknown_id_renders_as_empty_rather_than_raising():
    text = "Hello, {{ character['does_not_exist'].name }}!"
    assert render_placeholders(text, _context()) == "Hello, !"


def test_unknown_group_renders_as_empty_rather_than_raising():
    text = "{{ item['sword_1'].name }}"
    assert render_placeholders(text, _context()) == ""


def test_malformed_template_syntax_fails_open_and_returns_original_text():
    text = "Broken {{ character['character_1'].name syntax"
    assert render_placeholders(text, _context()) == text


def test_sandboxed_environment_blocks_arbitrary_python_execution():
    # The sandbox must not allow reaching outside the supplied context (e.g. via __class__
    # traversal to __globals__); a blocked attribute resolves to empty, same as a missing
    # reference, rather than executing anything or raising with the attempted payload attached.
    text = "{{ character.__class__.__init__.__globals__ }}"
    assert render_placeholders(text, _context()) == ""


def test_does_not_leak_fields_other_than_id_and_name():
    # PlaceholderEntity only ever carries id/name, so there is no attribute path from a
    # placeholder reference back to another entity's personality, state, or other free text.
    assert set(PlaceholderEntity.model_fields) == {"id", "name"}
