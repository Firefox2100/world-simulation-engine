import json
from pathlib import Path
from uuid import uuid4

import pytest

from world_simulation_engine.component.sillytavern_converter import BackgroundCharacterExtractor, \
    CardPreprocessor, CharacterExtractor, DataExtractor, EquipmentExtractor, IntentExtractor, \
    ItemExtractor, LocationExtractor, NarrativeExtractor, OpeningNarrativeExtractor, \
    OpeningTurnExtractor, PrivateKnowledgeExtractor, SpatialStateExtractor, VariableSchemaExtractor, \
    WorldAssembler, WorldLoreExtractor
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier
from world_simulation_engine.component.sillytavern_converter.narrative_extractor import NarrativeExtraction
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.model import BackgroundCharacter, Character, EntityRelationship, \
    EntityVariableSet, Equipment, Event, Intent, Item, ItemStack, Location, MemoryAtom, \
    SubjectiveEntityClaim, Turn, World


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/output")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []

def _language_from_card_path(card_path: Path) -> SupportedLanguage:
    """Card filenames encode the extraction language as their final dot-segment (e.g.
    "01.en.png") - the same language the SillyTavern import UI's language selector picks for this
    card, so each card's evaluation output is generated with the prompt set it would actually use
    in production."""
    return SupportedLanguage(card_path.stem.rsplit(".", 1)[-1])

_ALL_COMPONENTS = (
    ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_CHARACTER_EXTRACTOR,
    ComponentType.ST_BACKGROUND_CHARACTER_EXTRACTOR,
    ComponentType.ST_LOCATION_EXTRACTOR, ComponentType.ST_WORLD_LORE_EXTRACTOR,
    ComponentType.ST_NARRATIVE_EXTRACTOR, ComponentType.ST_INTENT_EXTRACTOR,
    ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR, ComponentType.ST_ITEM_EXTRACTOR,
    ComponentType.ST_EQUIPMENT_EXTRACTOR, ComponentType.ST_OPENING_TURN_EXTRACTOR,
    ComponentType.ST_SPATIAL_STATE_EXTRACTOR, ComponentType.ST_PRIVATE_KNOWLEDGE_EXTRACTOR,
    ComponentType.ST_OPENING_NARRATIVE_EXTRACTOR,
)


@pytest.fixture
async def global_scope_chat_config(evaluation_database, evaluation_connection_config, evaluation_chat_model_config):
    await evaluation_database.config.create_connection(evaluation_connection_config)
    await evaluation_database.config.create_chat(evaluation_chat_model_config)
    await evaluation_database.config.link_connection(evaluation_chat_model_config.id, evaluation_connection_config.id)
    for component in _ALL_COMPONENTS:
        await evaluation_database.config.link_global_chat(evaluation_chat_model_config.id, component)
    return evaluation_database


def _assert_rows_validate(assembled, world_id: str) -> None:
    """Every row must actually construct the real domain model WorldImportService will validate
    it against at persistence time - shape drift here would otherwise only surface as an obscure
    ValidationError deep inside stage 4."""
    World.model_validate({**assembled.world, "id": str(uuid4())})
    for row in assembled.sections["characters"]:
        Character.model_validate(row)
    for row in assembled.sections["background_characters"]:
        BackgroundCharacter.model_validate(row)
    for row in assembled.sections["locations"]:
        Location.model_validate(row)
    for row in assembled.sections["turns"]:
        Turn.model_validate(row)
    for row in assembled.sections["events"]:
        Event.model_validate(row)
    for row in assembled.sections["memories"]:
        MemoryAtom.model_validate(row)
    for row in assembled.sections["intents"]:
        Intent.model_validate(row)
    for row in assembled.sections["entity_relationships"]:
        EntityRelationship.model_validate({
            **row,
            "id": str(uuid4()),
            "scope_type": "world",
            "scope_id": world_id,
            "perspective_character_id": row["perspective_character_id"],
            "evidence_memory_ids": row["evidence_memory_ids"],
            "version": 1,
        })
    for row in assembled.sections["entity_variable_sets"]:
        EntityVariableSet.model_validate({
            **row, "id": str(uuid4()), "source_id": world_id, "owner_id": row["owner_id"], "version": 1,
        })
    for row in assembled.sections["items"]:
        Item.model_validate(row)
    for row in assembled.sections["item_stacks"]:
        ItemStack.model_validate(row)
    for row in assembled.sections["equipment"]:
        Equipment.model_validate(row)
    for row in assembled.sections["subjective_entity_claims"]:
        SubjectiveEntityClaim.model_validate({**row, "world_id": world_id})


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
async def test_assemble_world_from_real_sillytavern_card(card_path: Path, global_scope_chat_config):
    """Claude does not run this suite itself (see CLAUDE.md) - the user runs it against a real LLM
    and shares output; Claude only verifies it collects (`pytest tests/evaluation_test
    --collect-only`). WorldAssembler itself has no LLM calls, but everything feeding it does, so
    this still follows the same rule as every other ST-import evaluation test."""
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)
    language = _language_from_card_path(card_path)
    db = global_scope_chat_config

    classification = await LorebookClassifier(database=db).classify(preprocessed, language=language)
    characters = await CharacterExtractor(database=db).extract(preprocessed, classification, language=language)
    # Mirrors WorldReconstructor's node order: background_characters needs characters (it only
    # extracts names CharacterExtractor left orphaned - see background_character_extractor.py),
    # and narrative/opening_narrative need background_characters so an event/relationship
    # mentioning only a background character (a guard, a bartender) resolves instead of being
    # silently dropped the same way a main-character reference would be.
    background_characters = await BackgroundCharacterExtractor(database=db).extract(
        preprocessed, classification, characters, language=language,
    )
    locations = await LocationExtractor(database=db).extract(preprocessed, classification, language=language)
    world_lore = await WorldLoreExtractor(database=db).extract(preprocessed, classification, language=language)
    narrative = await NarrativeExtractor(database=db).extract(
        preprocessed, classification, characters, background_characters, language=language,
    )
    intents = await IntentExtractor(database=db).extract(characters, language=language)
    variables = await VariableSchemaExtractor(database=db).extract(preprocessed, classification, language=language)
    items = await ItemExtractor(database=db).extract(preprocessed, classification, language=language)
    equipment = await EquipmentExtractor(database=db).extract(preprocessed, classification, language=language)
    # Mirror WorldReconstructor's node order/dependencies exactly (world_reconstructor.py's
    # _build_graph): opening_turns needs characters; spatial_state needs
    # characters/locations/items/equipment; opening_narrative needs opening_turns/characters;
    # private_knowledge needs the combined (history + opening) narrative. Previously this eval
    # test only ran the first 8 extractors, leaving item_stacks/equipment spatial placement and
    # subjective_entity_claims structurally untested by every real eval run.
    opening_turns = await OpeningTurnExtractor(database=db).extract(
        preprocessed, characters, background_characters, language=language,
    )
    spatial_state = await SpatialStateExtractor(database=db).extract(
        preprocessed, characters, locations, items, equipment, language=language,
    )
    opening_narrative = await OpeningNarrativeExtractor(database=db).extract(
        opening_turns, characters, background_characters, language=language,
    )
    combined_narrative = NarrativeExtraction(
        events=[*narrative.events, *opening_narrative.events],
        memories=[*narrative.memories, *opening_narrative.memories],
        relationships=[*narrative.relationships, *opening_narrative.relationships],
    )
    private_knowledge = await PrivateKnowledgeExtractor(database=db).extract(
        characters, locations, items, equipment, combined_narrative, language=language,
    )

    assembled = WorldAssembler().assemble(
        preprocessed, language=language, characters=characters, locations=locations, world_lore=world_lore,
        narrative=narrative, intents=intents, variables=variables, items=items, equipment=equipment,
        background_characters=background_characters, opening_turns=opening_turns,
        spatial_state=spatial_state, private_knowledge=private_knowledge,
        opening_narrative=opening_narrative,
    )

    _assert_rows_validate(assembled, world_id="evaluation-world")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"world_assembler_{card_path.stem}_results.json").write_text(
        json.dumps(
            {
                "card": card_path.stem,
                "world": assembled.world,
                "section_counts": {name: len(rows) for name, rows in assembled.sections.items()},
                "report": [entry.model_dump() for entry in assembled.report.entries],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
