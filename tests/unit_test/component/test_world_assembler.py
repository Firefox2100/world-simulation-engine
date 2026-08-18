from uuid import uuid4

from world_simulation_engine.component.sillytavern_converter import CharacterExtraction, \
    CharacterExtractionResult, EquipmentExtraction, ExtractedCharacter, ExtractedContainer, \
    ExtractedEquipment, ExtractedEvent, ExtractedIntent, ExtractedItem, ExtractedLandmark, \
    ExtractedLocation, ExtractedMemory, \
    ExtractedRelationship, ExtractedVariable, IntentExtraction, ItemExtraction, LocationExtraction, \
    NarrativeExtraction, PreprocessedCard, VariableSchemaExtraction, WorldAssembler, WorldLoreExtraction
from world_simulation_engine.component.sillytavern_converter import ExtractedOpeningTurn, \
    ExtractedOpeningTurnBlock, ExtractedPrivateKnowledgeClaim, ExtractedSpatialPlacement, \
    OpeningTurnExtraction, PrivateKnowledgeExtraction, SpatialEntityType, SpatialStateExtraction
from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType, SupportedLanguage
from world_simulation_engine.model import BackgroundCharacter, Character, EntityRelationship, \
    EntityVariableSet, Equipment, Event, Intent, Item, ItemStack, Location, MemoryAtom, \
    NarrationProposal, SubjectiveEntityClaim, Turn, World
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


def make_card(name: str = "Example Character", first_message: str = "Hi there.") -> PreprocessedCard:
    return PreprocessedCard(name=name, first_message=first_message)


def test_assemble_resolves_self_via_card_name_and_rewrites_placeholders():
    card = make_card(name="Example Character", first_message="Hi, character['user']!")
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example", description="A fictional resident, character['self']."),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    character_row = assembled.sections["characters"][0]
    assert character_row["id"] == "id-example"
    assert character_row["description"] == "A fictional resident, character['id-example']."
    messages = [entry.message for entry in assembled.report.entries]
    assert not any("Could not identify a single primary character" in message for message in messages)
    assert any("has no inferred initial location" in message for message in messages)
    assert any("No explicit starting-time variable" in message for message in messages)

    turn_row = assembled.sections["turns"][0]
    assert assembled.sections["background_characters"] == []
    stub_row = next(row for row in assembled.sections["characters"] if row["user_controlled"])
    # A system_response turn's content is always NarrationProposal JSON (matching a live turn's
    # Narrator.serialize_content output), never plain prose - see world_assembler.py's
    # _narration_content.
    narration = NarrationProposal.model_validate_json(turn_row["content"])
    assert len(narration.blocks) == 1
    assert narration.blocks[0].text == f"Hi, character['{stub_row['id']}']!"


def test_assemble_notes_unresolved_self_when_card_name_matches_no_character():
    card = make_card(name="Example World")
    characters = CharacterExtraction(characters=[make_character("Taylor", "id-taylor")])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert any("Could not identify a single primary character" in entry.message for entry in assembled.report.entries)


def test_assemble_uses_user_controlled_character_instead_of_a_stub():
    card = make_card()
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example"),
        make_character("The Guest", "id-guest", user_controlled=True),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.sections["background_characters"] == []


def test_assemble_builds_turn_from_first_message_with_fallback_when_empty():
    card = make_card(first_message="")
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    turn_row = assembled.sections["turns"][0]
    assert turn_row["sequence"] == 0
    assert turn_row["type"] == "system_response"
    assert turn_row["content"]


def test_assemble_uses_extracted_opening_turn_sequence_and_keeps_user_action_separate():
    assembler = WorldAssembler()
    assembled = assembler.assemble(
        make_card(first_message="unsplit source"), language=SupportedLanguage.ENGLISH,
        characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(),
        items=ItemExtraction(), equipment=EquipmentExtraction(),
        opening_turns=OpeningTurnExtraction(turns=[
            ExtractedOpeningTurn(type="user_input", content="I open the door."),
            ExtractedOpeningTurn(type="system_response", content="The host looks up."),
        ]),
    )

    user_row, system_row = assembled.sections["turns"]
    assert (user_row["sequence"], user_row["type"], user_row["content"]) == (
        0, "user_input", "I open the door.",
    )
    # user_input content is always plain text (matches world_simulator.py's commit_user_actions,
    # which stores state.user_input verbatim - no NarrationProposal wrapping).
    assert (system_row["sequence"], system_row["type"]) == (1, "system_response")
    narration = NarrationProposal.model_validate_json(system_row["content"])
    assert [block.text for block in narration.blocks] == ["The host looks up."]


def test_assemble_preserves_narration_and_speech_blocks_in_a_system_turn():
    card = make_card(name="Example Character", first_message="unused")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])

    assembled = WorldAssembler().assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters,
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
        opening_turns=OpeningTurnExtraction(turns=[
            ExtractedOpeningTurn(
                type="system_response",
                content='Example Character steps forward. "Welcome," they say.',
                blocks=[
                    ExtractedOpeningTurnBlock(type="narration", text="Example Character steps forward."),
                    ExtractedOpeningTurnBlock(
                        type="speech", text="Welcome.", character_id="id-example",
                        character_name="Example Character",
                    ),
                ],
            ),
        ]),
    )

    turn_row = assembled.sections["turns"][0]
    narration = NarrationProposal.model_validate_json(turn_row["content"])
    assert [block.type for block in narration.blocks] == ["narration", "speech"]
    assert narration.blocks[0].text == "Example Character steps forward."
    assert narration.blocks[1].character_id == "id-example"
    assert narration.blocks[1].character_name == "Example Character"
    assert narration.blocks[1].text == "Welcome."


def test_assemble_attaches_opening_event_and_memory_to_existing_opening_turn():
    characters = CharacterExtraction(characters=[make_character("Jacob", "id-jacob")])
    opening_narrative = NarrativeExtraction(
        events=[ExtractedEvent(
            id="evt-fish", name="Swallowed by the fish",
            summary="A great fish swallowed Jacob.",
            outcome="Jacob decided to obey.", opening_turn_index=0,
            involved_character_ids=["id-jacob"],
        )],
        memories=[ExtractedMemory(
            id="mem-fish", event_id="evt-fish",
            summary="Being swallowed persuaded Jacob to obey.",
            keywords=["fish", "obey"], character_ids=["id-jacob"],
        )],
    )

    assembled = WorldAssembler().assemble(
        make_card(first_message="A great fish swallows Jacob."),
        language=SupportedLanguage.ENGLISH, characters=characters,
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(),
        equipment=EquipmentExtraction(),
        opening_turns=OpeningTurnExtraction(turns=[
            ExtractedOpeningTurn(type="system_response", content="A great fish swallows Jacob."),
        ]),
        opening_narrative=opening_narrative,
    )

    assert len(assembled.sections["turns"]) == 1
    assert assembled.sections["events"][0]["turn_ids"] == [assembled.sections["turns"][0]["id"]]
    assert assembled.sections["events"][0]["outcome"] == "Jacob decided to obey."
    assert assembled.sections["memories"][0]["event_id"] == "evt-fish"
    assert assembled.sections["memories"][0]["character_links"][0]["character_id"] == "id-jacob"


def test_assemble_applies_spatial_placement_to_character():
    character = make_character("Alice", "id-alice")
    assembled = WorldAssembler().assemble(
        make_card(), language=SupportedLanguage.ENGLISH,
        characters=CharacterExtraction(characters=[character]),
        locations=LocationExtraction(locations=[
            ExtractedLocation(id="loc-room", name="Room", description="A room."),
        ]),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
        spatial_state=SpatialStateExtraction(placements=[ExtractedSpatialPlacement(
            entity_type=SpatialEntityType.CHARACTER, entity_name="Alice",
            location_id="loc-room", position="near the door",
        )]),
    )

    assert assembled.sections["characters"][0]["location_id"] == "loc-room"
    assert assembled.sections["characters"][0]["position"] == "near the door"


def test_assemble_locations_carry_parent_id_through():
    card = make_card()
    locations = LocationExtraction(locations=[
        ExtractedLocation(id="loc-1", name="City", description="A city."),
        ExtractedLocation(id="loc-2", name="House", description="A house.", parent_id="loc-1"),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=locations, world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    by_id = {row["id"]: row for row in assembled.sections["locations"]}
    assert by_id["loc-2"]["parent_location_id"] == "loc-1"
    assert by_id["loc-1"]["parent_location_id"] is None


def test_assemble_builds_landmark_and_container_relationship_rows():
    characters = CharacterExtraction(characters=[make_character("Alice", "id-alice")])
    locations = LocationExtraction(
        locations=[ExtractedLocation(id="loc-vault", name="Vault", description="A vault.")],
        landmarks=[ExtractedLandmark(
            id="landmark-altar", name="Stone Altar", description="A fixed altar.",
            location_id="loc-vault",
        )],
    )
    items = ItemExtraction(
        items=[ExtractedItem(
            id="item-key", name="Brass key", description="A small key.", unique=True,
            quantity=1, holder_hint="Alice",
        )],
        containers=[ExtractedContainer(
            id="container-chest", name="Chest", description="A locked chest.", state="locked",
            owner_hint="Alice", location_hint="Vault", position="beneath the altar",
            unlocking_item_names=["Brass key"],
        )],
    )

    assembled = WorldAssembler().assemble(
        make_card(), language=SupportedLanguage.ENGLISH, characters=characters,
        locations=locations, world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=items,
        equipment=EquipmentExtraction(),
    )

    assert assembled.sections["landmarks"][0]["location_id"] == "loc-vault"
    container = assembled.sections["containers"][0]
    assert container["owner_id"] == "id-alice"
    assert container["location_id"] == "loc-vault"
    assert container["unlocking_item_ids"] == ["item-key"]


def test_assemble_events_memories_and_relationships_reference_the_same_turn_and_ids():
    card = make_card()
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"), make_character("Bob", "id-bob"),
    ])
    narrative = NarrativeExtraction(
        events=[ExtractedEvent(
            id="evt-1", name="The Project", summary="They collaborated.",
            outcome="The prototype worked.", involved_character_ids=["id-alice", "id-bob"],
        )],
        memories=[ExtractedMemory(id="mem-1", event_id="evt-1", summary="We collaborated.", keywords=["project"], character_ids=["id-alice"])],
        relationships=[ExtractedRelationship(
            id="rel-1", source_character_id="id-alice", target_character_id="id-bob",
            label="colleagues", description="Former colleagues.",
        )],
    )
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=narrative, intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    history_turn = assembled.sections["turns"][0]
    opening_turn = assembled.sections["turns"][1]
    turn_id = history_turn["id"]
    history_narration = NarrationProposal.model_validate_json(history_turn["content"])
    assert [block.text for block in history_narration.blocks] == [
        "They collaborated.\n\nOutcome: The prototype worked.",
    ]
    opening_narration = NarrationProposal.model_validate_json(opening_turn["content"])
    assert [block.text for block in opening_narration.blocks] == [card.first_message]
    event_row = assembled.sections["events"][0]
    assert event_row["turn_ids"] == [turn_id]
    assert event_row["outcome"] == "The prototype worked."
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
    assert relationship_row["public_description"] == "Former colleagues."


def test_assemble_private_knowledge_is_positive_evidence_backed_world_import_data():
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"), make_character("Bob", "id-bob"),
    ])
    claim = ExtractedPrivateKnowledgeClaim(
        id="claim-1", observer_character_id="id-alice", subject_id="id-bob",
        subject_type="character", category="history", statement="Bob survived the fire.",
        stance="believes", confidence=.9, supporting_memory_ids=["mem-1"],
    )
    assembled = WorldAssembler().assemble(
        make_card(), language=SupportedLanguage.ENGLISH, characters=characters,
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
        private_knowledge=PrivateKnowledgeExtraction(claims=[claim]),
    )

    row = assembled.sections["subjective_entity_claims"][0]
    validated = SubjectiveEntityClaim.model_validate({**row, "world_id": "world-1"})
    assert validated.observer_character_id == "id-alice"
    assert validated.subject.id == "id-bob"
    assert validated.supporting_memory_ids == ["mem-1"]


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
        narrative=NarrativeExtraction(), intents=intents, variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    intent_row = assembled.sections["intents"][0]
    assert intent_row["character_id"] == "id-alice"
    assert intent_row["type"] == IntentType.QUEST
    assert intent_row["created_by_event_id"] is None


def test_assemble_variables_group_by_resolved_owner_and_dedupe_across_sources():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    locations = LocationExtraction(locations=[ExtractedLocation(id="loc-1", name="Bedroom", description="A room.")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="Example Character", name="hp", value_type=VariableValueType.INTEGER, default_value=100,
            description="Health.", source_item_ids=["script:0"],
        ),
        ExtractedVariable(
            owner_hint="Example Character", name="hp", value_type=VariableValueType.INTEGER, default_value=999,
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
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    variable_sets = {row["owner_id"]: row for row in assembled.sections["entity_variable_sets"]}
    assert set(variable_sets) == {"id-example", "loc-1"}
    example_vars = variable_sets["id-example"]
    assert example_vars["owner_type"] == "character"
    assert len(example_vars["variables"]) == 1  # duplicate "hp" from the second source dropped
    assert example_vars["variables"][0]["value"] == 100  # first occurrence wins

    location_vars = variable_sets["loc-1"]
    assert location_vars["owner_type"] == "location"
    assert location_vars["variables"][0]["name"] == "cleanliness"


def test_assemble_variable_with_multiple_slash_separated_owner_names_attaches_to_each():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[
        make_character("Avery", "id-avery"),
        make_character("Blair", "id-blair"),
        make_character("Casey", "id-casey"),
    ])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="Avery/Blair/Casey", name="好感度", value_type=VariableValueType.INTEGER,
            default_value=0, description="Affection.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.CHINESE, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    variable_sets = {row["owner_id"]: row for row in assembled.sections["entity_variable_sets"]}
    assert set(variable_sets) == {"id-avery", "id-blair", "id-casey"}
    for owner_id in ("id-avery", "id-blair", "id-casey"):
        assert variable_sets[owner_id]["owner_type"] == "character"
        assert variable_sets[owner_id]["variables"][0]["name"] == "好感度"


def test_assemble_attaches_non_clock_global_state_to_world_variable_set():
    variables = VariableSchemaExtraction(variables=[ExtractedVariable(
        owner_hint="world", name="weather", value_type=VariableValueType.STRING,
        default_value="stormy", description="The world's current weather condition.",
    )])

    assembled = WorldAssembler().assemble(
        make_card(), language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables,
        items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    variable_set = assembled.sections["entity_variable_sets"][0]
    assert variable_set["owner_type"] == "world"
    assert variable_set["owner_id"] == assembled.world["id"]
    assert variable_set["variables"][0]["name"] == "weather"


def test_assemble_notes_a_variable_source_that_hit_the_extraction_cap():
    # Real finding (evaluation run on a content-rich card): a single variable source can define
    # more tracked variables than one bounded structured-output call is allowed to return, and the
    # extractor stage has no way to tell the assembler apart from "the source only had this many" -
    # it just flags the source id. WorldAssembler must turn that into a visible report note rather
    # than silently treating a capped result as complete.
    variables = VariableSchemaExtraction(
        variables=[ExtractedVariable(
            owner_hint="world", name="weather", value_type=VariableValueType.STRING,
            default_value="stormy", description="The world's current weather condition.",
            source_item_ids=["script:0"],
        )],
        capped_source_ids=["script:0"],
    )

    assembled = WorldAssembler().assemble(
        make_card(), language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables,
        items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert any(
        "script:0" in entry.message and "cap" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )


def test_assemble_drops_time_tracking_variables_regardless_of_owner():
    # Real finding: the simulation manages its own clock (World.starting_time) - a per-owner
    # "time_passed"/"current_date" style tracked variable would drift from it, so these are dropped
    # outright rather than imported, whether or not their owner_hint would otherwise have resolved.
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="Example Character", name="time_passed", value_type=VariableValueType.INTEGER,
            default_value=0, description="Turns elapsed.", source_item_ids=["script:0"],
        ),
        ExtractedVariable(
            owner_hint="world", name="current_date", value_type=VariableValueType.STRING,
            default_value="not a date", description="Tracked date.", source_item_ids=["script:0"],
        ),
        ExtractedVariable(
            owner_hint="Example Character", name="hp", value_type=VariableValueType.INTEGER,
            default_value=100, description="Health.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    example_vars = assembled.sections["entity_variable_sets"][0]["variables"]
    assert [variable["name"] for variable in example_vars] == ["hp"]
    assert any(
        "time_passed" in entry.message and "clock" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )
    assert any(
        "current_date" in entry.message and "clock" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )


def test_assemble_self_hinted_variable_maps_to_user_controlled_character():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example"),
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
        variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    variable_sets = assembled.sections["entity_variable_sets"]
    assert len(variable_sets) == 1
    assert variable_sets[0]["owner_id"] == "id-guest"


def test_assemble_self_hinted_variable_maps_to_synthesized_user_stub_when_no_persona_exists():
    # A schema owner of "self" maps to the player's tracked state.
    card = make_card(name="Example World")
    characters = CharacterExtraction(characters=[make_character("Taylor", "id-taylor")])
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
        variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    stub_row = next(row for row in assembled.sections["characters"] if row["user_controlled"])
    assert assembled.sections["background_characters"] == []
    variable_sets = assembled.sections["entity_variable_sets"]
    assert len(variable_sets) == 1
    assert variable_sets[0]["owner_id"] == stub_row["id"]


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
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.sections["entity_variable_sets"] == []
    assert any("current_date" in entry.message for entry in assembled.report.entries)


def test_assemble_drops_variable_with_inconsistent_value_type():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="self", name="hp", value_type=VariableValueType.INTEGER,
            default_value="not a number", description="Health.", source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.sections["entity_variable_sets"] == []
    assert any("hp" in entry.message and entry.low_confidence for entry in assembled.report.entries)


def test_assemble_items_resolve_holder_and_location_hints():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    locations = LocationExtraction(locations=[ExtractedLocation(id="loc-1", name="Bedroom", description="A room.")])
    items = ItemExtraction(items=[
        ExtractedItem(
            name="Locket", description="A silver locket.", unique=True, quantity=1,
            holder_hint="Example Character", source_item_ids=["entry:1"],
        ),
        ExtractedItem(
            name="Old chair", description="A wooden chair.", unique=False, quantity=1,
            location_hint="Bedroom", source_item_ids=["entry:2"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=locations,
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=items, equipment=EquipmentExtraction(),
    )

    item_rows = {row["name"]: row for row in assembled.sections["items"]}
    stack_rows = {row["item_id"]: row for row in assembled.sections["item_stacks"]}
    assert set(item_rows) == {"Locket", "Old chair"}

    locket_stack = stack_rows[item_rows["Locket"]["id"]]
    assert locket_stack["holder_id"] == "id-example"
    assert locket_stack["location_id"] is None

    chair_stack = stack_rows[item_rows["Old chair"]["id"]]
    assert chair_stack["holder_id"] is None
    assert chair_stack["location_id"] == "loc-1"


def test_assemble_self_hinted_item_maps_to_user_controlled_character():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example"),
        make_character("The Guest", "id-guest", user_controlled=True),
    ])
    items = ItemExtraction(items=[
        ExtractedItem(
            name="Wallet", description="A worn leather wallet.", unique=False, quantity=1,
            holder_hint="self", source_item_ids=["entry:1"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=items, equipment=EquipmentExtraction(),
    )

    stack_row = assembled.sections["item_stacks"][0]
    assert stack_row["holder_id"] == "id-guest"


def test_assemble_retains_item_type_without_stack_when_placement_is_unknown():
    card = make_card()
    items = ItemExtraction(items=[
        ExtractedItem(
            name="Mystery box", description="Nobody knows whose it is.", unique=False, quantity=1,
            holder_hint="Nobody Here", location_hint="Nowhere Real", source_item_ids=["entry:1"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=items, equipment=EquipmentExtraction(),
    )

    assert assembled.sections["items"][0]["name"] == "Mystery box"
    assert assembled.sections["item_stacks"] == []
    assert any(
        "retained existence as an Item type only" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )


def test_assemble_drops_second_item_of_the_same_name():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    items = ItemExtraction(items=[
        ExtractedItem(
            name="Locket", description="First mention.", unique=True, quantity=1,
            holder_hint="Example Character", source_item_ids=["entry:1"],
        ),
        ExtractedItem(
            name="Locket", description="Duplicate mention from another entry.", unique=True,
            quantity=1, holder_hint="Example Character", source_item_ids=["entry:2"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=items, equipment=EquipmentExtraction(),
    )

    assert len(assembled.sections["items"]) == 1
    assert assembled.sections["items"][0]["description"] == "First mention."  # first occurrence wins


def test_assemble_equipment_resolves_holder_hint():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    equipment = EquipmentExtraction(equipment=[
        ExtractedEquipment(
            name="Travel cloak", description="A wool cloak.", quality="worn", holder_hint="Example Character",
            slot="outerwear", source_item_ids=["entry:1"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=equipment,
    )

    equipment_row = assembled.sections["equipment"][0]
    assert equipment_row["name"] == "Travel cloak"
    assert equipment_row["holder_id"] == "id-example"
    assert equipment_row["equipped"] is True
    assert equipment_row["equipped_position"] == "outerwear"


def test_assemble_self_hinted_equipment_maps_to_user_controlled_character():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example"),
        make_character("The Guest", "id-guest", user_controlled=True),
    ])
    equipment = EquipmentExtraction(equipment=[
        ExtractedEquipment(
            name="Reading glasses", description="Thin wire frames.", holder_hint="self",
            source_item_ids=["entry:1"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=equipment,
    )

    assert assembled.sections["equipment"][0]["holder_id"] == "id-guest"


def test_assemble_imports_equipment_unassigned_when_holder_hint_is_unresolvable():
    card = make_card()
    equipment = EquipmentExtraction(equipment=[
        ExtractedEquipment(
            name="Mystery ring", description="Nobody claims it.", holder_hint="Nobody Here",
            source_item_ids=["entry:1"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(),
        equipment=equipment,
    )

    # Unlike an item stack, equipment has no "must be placed somewhere" constraint - it's still
    # imported, just unassigned, with a low-confidence note rather than being dropped.
    assert len(assembled.sections["equipment"]) == 1
    assert assembled.sections["equipment"][0]["holder_id"] is None
    assert any(
        "Mystery ring" in entry.message and entry.low_confidence for entry in assembled.report.entries
    )


def test_assemble_drops_second_equipment_of_the_same_name():
    card = make_card(name="Example Character")
    characters = CharacterExtraction(characters=[make_character("Example Character", "id-example")])
    equipment = EquipmentExtraction(equipment=[
        ExtractedEquipment(
            name="Locket necklace", description="First mention.", holder_hint="Example Character",
            source_item_ids=["entry:1"],
        ),
        ExtractedEquipment(
            name="Locket necklace", description="Duplicate mention from another entry.",
            holder_hint="Example Character", source_item_ids=["entry:2"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=LocationExtraction(),
        world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(), intents=IntentExtraction(),
        variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=equipment,
    )

    assert len(assembled.sections["equipment"]) == 1
    assert assembled.sections["equipment"][0]["description"] == "First mention."


def test_assemble_world_row_uses_card_name_and_world_lore_description():
    card = make_card(name="Example Character")
    world_lore = WorldLoreExtraction(description="A coastal town.", source_item_ids=["entry:1"])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=world_lore,
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["name"] == "Example Character"
    assert assembled.world["description"] == "A coastal town."


def test_assemble_world_row_fills_metadata_from_card():
    card = PreprocessedCard(
        name="Example Character",
        first_message="Hi there.",
        creator_notes="Works best with a warm, gentle tone.",
        tags=["fantasy", "slice-of-life"],
        creator="Example Creator",
        character_version="1.2",
        source=["https://example.com/cards/example-character"],
    )
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["metadata"] == {
        "author": "Example Creator",
        "resource_url": "https://example.com/cards/example-character",
        "comment": "Works best with a warm, gentle tone.",
        "version": "1.2",
        "tags": ["fantasy", "slice-of-life"],
    }


def test_assemble_world_row_leaves_metadata_unfilled_when_card_has_none():
    card = make_card()
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["metadata"] == {
        "author": None,
        "resource_url": None,
        "comment": None,
        "version": None,
        "tags": [],
    }


def test_assemble_world_row_has_no_description_when_no_world_lore():
    card = make_card()
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=CharacterExtraction(), locations=LocationExtraction(), world_lore=WorldLoreExtraction(),
        narrative=NarrativeExtraction(), intents=IntentExtraction(), variables=VariableSchemaExtraction(), items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["description"] is None


def test_assembled_rows_validate_against_the_real_domain_models():
    """Every row WorldAssembler produces must actually construct the real pydantic model
    WorldImportService will validate it against at persistence time - shape drift here would only
    surface as an obscure ValidationError deep inside stage 4, so it's cheaper to catch here."""
    card = make_card(name="Example Character", first_message="Hi, character['user']!")
    characters = CharacterExtraction(characters=[
        make_character("Example Character", "id-example", description="A fictional resident, character['self']."),
        make_character("Bob", "id-bob"),
    ])
    locations = LocationExtraction(locations=[
        ExtractedLocation(id="loc-1", name="City", description="A city."),
        ExtractedLocation(id="loc-2", name="House", description="A house.", parent_id="loc-1"),
    ])
    narrative = NarrativeExtraction(
        events=[ExtractedEvent(
            id="evt-1", name="The Project", summary="They collaborated.",
            involved_character_ids=["id-example", "id-bob"],
        )],
        memories=[ExtractedMemory(
            id="mem-1", event_id="evt-1", summary="We collaborated.", keywords=["project"],
            character_ids=["id-example"],
        )],
        relationships=[ExtractedRelationship(
            id="rel-1", source_character_id="id-example", target_character_id="id-bob",
            label="colleagues", description="Former colleagues.",
        )],
    )
    intents = IntentExtraction(intents=[
        ExtractedIntent(
            id="int-1", character_id="id-example", name="Solve the case", type=IntentType.QUEST,
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
    items = ItemExtraction(items=[
        ExtractedItem(
            name="Locket", description="A silver locket.", unique=True, quantity=1,
            holder_hint="Example Character", source_item_ids=["entry:1"],
        ),
    ])
    equipment = EquipmentExtraction(equipment=[
        ExtractedEquipment(
            name="Travel cloak", description="A wool cloak.", quality="worn", holder_hint="Example Character",
            slot="outerwear", source_item_ids=["entry:2"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.ENGLISH, characters=characters, locations=locations, world_lore=WorldLoreExtraction(description="Lore."),
        narrative=narrative, intents=intents, variables=variables, items=items, equipment=equipment,
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
    for row in assembled.sections["items"]:
        Item.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["item_stacks"]:
        ItemStack.model_validate(row).model_copy(update={"id": str(uuid4())})
    for row in assembled.sections["equipment"]:
        Equipment.model_validate(row).model_copy(update={"id": str(uuid4())})


def test_assemble_infers_starting_time_from_explicit_world_date_and_time_variables():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        ExtractedVariable(
            owner_hint="world", name="当前日期", value_type=VariableValueType.STRING,
            default_value="2030年06月10日", description="世界当前的日期", source_item_ids=["script:0"],
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
        intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["starting_time"] == "2030-06-10T08:30:00+00:00"
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
        intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert assembled.world["starting_time"] == "2024-01-01T00:00:00+00:00"


def test_assemble_ignores_non_world_or_unparseable_date_variables_and_flags_the_default():
    card = make_card()
    variables = VariableSchemaExtraction(variables=[
        # Not "world"-scoped - a character's own birthdate is not the simulation clock.
        ExtractedVariable(
            owner_hint="self", name="出生日期", value_type=VariableValueType.STRING,
            default_value="2000年01月01日", description="角色的出生日期", source_item_ids=["script:0"],
        ),
        # "world"-scoped but the value doesn't actually contain a parseable date.
        ExtractedVariable(
            owner_hint="world", name="世界现状", value_type=VariableValueType.STRING,
            default_value="状态稳定", description="Current world date and situation.",
            source_item_ids=["script:0"],
        ),
    ])
    assembler = WorldAssembler()

    assembled = assembler.assemble(
        card, language=SupportedLanguage.CHINESE, characters=CharacterExtraction(),
        locations=LocationExtraction(), world_lore=WorldLoreExtraction(), narrative=NarrativeExtraction(),
        intents=IntentExtraction(), variables=variables, items=ItemExtraction(), equipment=EquipmentExtraction(),
    )

    assert any(
        "No explicit starting-time variable found" in entry.message and entry.low_confidence
        for entry in assembled.report.entries
    )
