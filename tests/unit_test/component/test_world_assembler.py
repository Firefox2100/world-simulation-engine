from uuid import uuid4

from world_simulation_engine.component.sillytavern_converter import CharacterExtraction, \
    CharacterExtractionResult, ExtractedCharacter, ExtractedEvent, ExtractedIntent, ExtractedLocation, \
    ExtractedMemory, ExtractedRelationship, ExtractedVariable, IntentExtraction, LocationExtraction, \
    NarrativeExtraction, PreprocessedCard, VariableSchemaExtraction, WorldAssembler, WorldLoreExtraction
from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType, SupportedLanguage
from world_simulation_engine.model import BackgroundCharacter, Character, EntityRelationship, \
    EntityVariableSet, Event, Intent, Location, MemoryAtom, Turn, World
from world_simulation_engine.model.variable import VariableValueType


def make_character(
        name: str, char_id: str, *, user_controlled: bool = False,
        description: str = "A character.", public_state: str = "Present",
) -> ExtractedCharacter:
    return ExtractedCharacter(
        id=char_id,
        target_name=name,
        source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="Plain", description=description,
            public_state=public_state, private_state="Thinking", current_activity="idle",
            speech_style="calm", user_controlled=user_controlled,
        ),
    )


def make_card(name: str = "Kiki Mora", first_message: str = "Hi there.") -> PreprocessedCard:
    return PreprocessedCard(name=name, first_message=first_message)


def test_assemble_resolves_self_via_card_name_and_rewrites_placeholders():
    card = make_card(name="Kiki Mora", first_message="Hi, character['user']!")
    characters = CharacterExtraction(characters=[
        make_character("Kiki Mora", "id-kiki", description="A streamer, character['self']."),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    character_row = assembled.sections["characters"][0]
    assert character_row["id"] == "id-kiki"
    assert character_row["description"] == "A streamer, character['id-kiki']."
    # No {{char}}-resolution issue to report for this card - only the always-present
    # no-explicit-starting-time note (no variables supplied in this test).
    assert [entry.message for entry in assembled.report.entries] == [
        "No explicit starting-time variable found on this card - defaulted to the import "
        "time; review and adjust before starting a simulation from this world.",
    ]

    turn_row = assembled.sections["turns"][0]
    stub_id = assembled.sections["background_characters"][0]["id"]
    assert turn_row["content"] == f"Hi, character['{stub_id}']!"


def test_assemble_notes_unresolved_self_when_card_name_matches_no_character():
    card = make_card(name="尸变纪元 v0.5")
    characters = CharacterExtraction(characters=[make_character("马库斯", "id-marcus")])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    assert any("Could not identify a single primary character" in entry.message for entry in assembled.report.entries)


def test_assemble_uses_user_controlled_character_instead_of_a_stub():
    card = make_card()
    characters = CharacterExtraction(characters=[
        make_character("Kiki Mora", "id-kiki"),
        make_character("The Guest", "id-guest", user_controlled=True),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    assert assembled.sections["background_characters"] == []


def test_assemble_builds_turn_from_first_message_with_fallback_when_empty():
    card = make_card(first_message="")
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    turn_row = assembled.sections["turns"][0]
    assert turn_row["sequence"] == 0
    assert turn_row["type"] == "system_response"
    assert turn_row["content"]


def test_assemble_locations_carry_parent_id_through():
    card = make_card()
    locations = LocationExtraction(locations=[
        ExtractedLocation(id="loc-1", name="City", description="A city."),
        ExtractedLocation(id="loc-2", name="House", description="A house.", parent_id="loc-1"),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=locations, world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    by_id = {row["id"]: row for row in assembled.sections["locations"]}
    assert by_id["loc-2"]["parent_location_id"] == "loc-1"
    assert by_id["loc-1"]["parent_location_id"] is None


def test_assemble_events_memories_and_relationships_reference_the_same_turn_and_ids():
    card = make_card()
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"), make_character("Bob", "id-bob"),
    ])
    narrative = NarrativeExtraction(
        events=[ExtractedEvent(id="evt-1", name="The War", summary="They fought.", involved_character_ids=["id-alice", "id-bob"])],
        memories=[ExtractedMemory(id="mem-1", event_id="evt-1", summary="We fought.", keywords=["war"], character_ids=["id-alice"])],
        relationships=[ExtractedRelationship(
            id="rel-1", source_character_id="id-alice", target_character_id="id-bob",
            label="rivals", description="Old rivals.",
        )],
    )
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=narrative, intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    turn_id = assembled.sections["turns"][0]["id"]
    event_row = assembled.sections["events"][0]
    assert event_row["turn_ids"] == [turn_id]
    assert {inv["character_id"] for inv in event_row["involved_characters"]} == {"id-alice", "id-bob"}
    assert all(inv["involvement"] == "participate" for inv in event_row["involved_characters"])

    memory_row = assembled.sections["memories"][0]
    assert memory_row["event_id"] == "evt-1"
    assert memory_row["support_type"] == "direct"
    assert memory_row["character_links"][0]["character_id"] == "id-alice"
    assert memory_row["character_links"][0]["stance"] == "remember"

    relationship_row = assembled.sections["entity_relationships"][0]
    assert relationship_row["source"] == {"type": "character", "id": "id-alice", "name": None}
    assert relationship_row["target"] == {"type": "character", "id": "id-bob", "name": None}
    assert relationship_row["public_description"] == "Old rivals."


def test_assemble_intent_row_carries_character_id_and_defaults():
    card = make_card()
    intents = IntentExtraction(intents=[
        ExtractedIntent(
            id="int-1", character_id="id-alice", name="Solve the case", type=IntentType.QUEST,
            description="Find the truth.", priority=0.9, urgency=0.5, status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.LONG,
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=intents, variables=VariableSchemaExtraction(),
    )

    intent_row = assembled.sections["intents"][0]
    assert intent_row["character_id"] == "id-alice"
    assert intent_row["type"] == IntentType.QUEST
    assert intent_row["created_by_event_id"] is None


def test_assemble_variables_group_by_resolved_owner_and_dedupe_across_sources():
    card = make_card(name="Kiki Mora")
    characters = CharacterExtraction(characters=[make_character("Kiki Mora", "id-kiki")])
    locations = LocationExtraction(locations=[ExtractedLocation(id="loc-1", name="Bedroom", description="A room.")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="Kiki Mora", name="hp", value_type=VariableValueType.INTEGER, default_value=100,
            description="Health.", source_item_ids=["script:0"],
        ),
        ExtractedVariable(
            owner_hint="Kiki Mora", name="hp", value_type=VariableValueType.INTEGER, default_value=999,
            description="Duplicate from another source.", source_item_ids=["entry:1"],
        ),
        ExtractedVariable(
            owner_hint="Bedroom", name="cleanliness", value_type=VariableValueType.STRING,
            default_value="tidy", description="How clean the room is.", source_item_ids=["entry:2"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=locations, world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables,
    )

    variable_sets = {row["owner_id"]: row for row in assembled.sections["entity_variable_sets"]}
    assert set(variable_sets) == {"id-kiki", "loc-1"}
    kiki_vars = variable_sets["id-kiki"]
    assert kiki_vars["owner_type"] == "character"
    assert len(kiki_vars["variables"]) == 1  # duplicate "hp" from the second source dropped
    assert kiki_vars["variables"][0]["value"] == 100  # first occurrence wins

    location_vars = variable_sets["loc-1"]
    assert location_vars["owner_type"] == "location"
    assert location_vars["variables"][0]["name"] == "cleanliness"


def test_assemble_self_hinted_variable_maps_to_user_controlled_character():
    card = make_card(name="Kiki Mora")
    characters = CharacterExtraction(characters=[
        make_character("Kiki Mora", "id-kiki"),
        make_character("The Guest", "id-guest", user_controlled=True),
    ])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="self", name="hp", value_type=VariableValueType.INTEGER, default_value=100,
            description="Health.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=variables,
    )

    variable_sets = assembled.sections["entity_variable_sets"]
    assert len(variable_sets) == 1
    assert variable_sets[0]["owner_id"] == "id-guest"


def test_assemble_self_hinted_variable_maps_to_synthesized_user_stub_when_no_persona_exists():
    # Real finding: an MVU-style variable schema's "self"/"自身" section conventionally tracks the
    # player's own stats, not the card's named protagonist - confirmed on a real survival-RPG card
    # where every "self"-hinted variable (name/age/hp/inventory/...) was clearly the player's own
    # state, and the card had no single protagonist for card.name to match against at all.
    card = make_card(name="尸变纪元 v0.5")
    characters = CharacterExtraction(characters=[make_character("马库斯", "id-marcus")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="self", name="hp", value_type=VariableValueType.INTEGER, default_value=100,
            description="Health.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.CHINESE, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=variables,
    )

    stub_id = assembled.sections["background_characters"][0]["id"]
    variable_sets = assembled.sections["entity_variable_sets"]
    assert len(variable_sets) == 1
    assert variable_sets[0]["owner_id"] == stub_id


def test_assemble_drops_variable_with_unresolvable_owner_hint():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="world", name="current_date", value_type=VariableValueType.STRING,
            default_value="2024-01-01", description="Date.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables,
    )

    assert assembled.sections["entity_variable_sets"] == []
    assert any("current_date" in entry.message for entry in assembled.report.entries)


def test_assemble_drops_variable_with_inconsistent_value_type():
    card = make_card(name="Kiki Mora")
    characters = CharacterExtraction(characters=[make_character("Kiki Mora", "id-kiki")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="self", name="hp", value_type=VariableValueType.INTEGER,
            default_value="not a number", description="Health.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables,
    )

    assert assembled.sections["entity_variable_sets"] == []
    assert any("hp" in entry.message and entry.low_confidence for entry in assembled.report.entries)


def test_assemble_world_row_uses_card_name_and_world_lore_description():
    card = make_card(name="Kiki Mora")
    world_lore = WorldLoreExtraction(description="A cursed village.", source_item_ids=["entry:1"])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=world_lore,
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    assert assembled.world["name"] == "Kiki Mora"
    assert assembled.world["description"] == "A cursed village."


def test_assemble_world_row_has_no_description_when_no_world_lore():
    card = make_card()
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
    )

    assert assembled.world["description"] is None


def test_assembled_rows_validate_against_the_real_domain_models():
    """Every row WorldAssembler produces must actually construct the real pydantic model
    WorldImportService will validate it against at persistence time - shape drift here would only
    surface as an obscure ValidationError deep inside stage 4, so it's cheaper to catch here."""
    card = make_card(name="Kiki Mora", first_message="Hi, character['user']!")
    characters = CharacterExtraction(characters=[
        make_character("Kiki Mora", "id-kiki", description="A streamer, character['self']."),
        make_character("Bob", "id-bob"),
    ])
    locations = LocationExtraction(locations=[
        ExtractedLocation(id="loc-1", name="City", description="A city."),
        ExtractedLocation(id="loc-2", name="House", description="A house.", parent_id="loc-1"),
    ])
    narrative = NarrativeExtraction(
        events=[ExtractedEvent(
            id="evt-1", name="The War", summary="They fought.",
            involved_character_ids=["id-kiki", "id-bob"],
        )],
        memories=[ExtractedMemory(
            id="mem-1", event_id="evt-1", summary="We fought.", keywords=["war"],
            character_ids=["id-kiki"],
        )],
        relationships=[ExtractedRelationship(
            id="rel-1", source_character_id="id-kiki", target_character_id="id-bob",
            label="rivals", description="Old rivals.",
        )],
    )
    intents = IntentExtraction(intents=[
        ExtractedIntent(
            id="int-1", character_id="id-kiki", name="Solve the case", type=IntentType.QUEST,
            description="Find the truth.", priority=0.9, urgency=0.5, status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.LONG,
        ),
    ])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="self", name="hp", value_type=VariableValueType.INTEGER, default_value=100,
            description="Health.", minimum=0, maximum=100, source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=locations, world_lore=WorldLoreExtraction(description="Lore."),
        narrative=narrative, intents=intents, variables=variables,
    )

    World.model_validate({**assembled.world, "id": str(uuid4())})

    for row in assembled.sections["characters"]:
        Character.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["background_characters"]:
        BackgroundCharacter.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["locations"]:
        Location.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["turns"]:
        Turn.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["events"]:
        Event.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["memories"]:
        MemoryAtom.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["intents"]:
        Intent.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["entity_relationships"]:
        EntityRelationship.model_validate({
            **row,
            "id": str(uuid4()),
            "scope_type": "world",
            "scope_id": "world-1",
            "source": {**row["source"], "id": row["source"]["id"]},
            "target": {**row["target"], "id": row["target"]["id"]},
            "perspective_character_id": row["perspective_character_id"],
            "evidence_memory_ids": row["evidence_memory_ids"],
            "version": 1,
        })
    for row in assembled.sections["entity_variable_sets"]:
        EntityVariableSet.model_validate({
            **row, "id": str(uuid4()), "source_id": "world-1", "owner_id": row["owner_id"], "version": 1,
        })


def test_assemble_infers_starting_time_from_explicit_world_date_and_time_variables():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="world", name="当前日期", value_type=VariableValueType.STRING,
            default_value="2024年03月15日", description="世界当前的日期", source_item_ids=["script:0"],
        ),
        ExtractedVariable(
            owner_hint="world", name="当前时间", value_type=VariableValueType.STRING,
            default_value="08:30", description="世界当前的时间", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.CHINESE, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=variables,
    )

    assert assembled.world["starting_time"] == "2024-03-15T08:30:00+00:00"
    assert any("Starting time inferred" in entry.message for entry in assembled.report.entries)


def test_assemble_infers_starting_time_from_date_only_variable_defaulting_to_midnight():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="world", name="current_date", value_type=VariableValueType.STRING,
            default_value="2024-01-01", description="The current date.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=variables,
    )

    assert assembled.world["starting_time"] == "2024-01-01T00:00:00+00:00"


def test_assemble_ignores_non_world_or_unparseable_date_variables_and_flags_the_default():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        # Not "world"-scoped - a character's own birthdate is not the simulation clock.
        ExtractedVariable(
            owner_hint="self", name="出生日期", value_type=VariableValueType.STRING,
            default_value="1998年05月01日", description="角色的出生日期", source_item_ids=["script:0"],
        ),
        # "world"-scoped but the value doesn't actually contain a parseable date.
        ExtractedVariable(
            owner_hint="world", name="世界现状", value_type=VariableValueType.STRING,
            default_value="秩序崩坏", description="Current world date and situation.",
            source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.CHINESE, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=variables,
    )

    assert any(
        "No explicit starting-time variable found" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )
