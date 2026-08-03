import json
from pathlib import Path
from uuid import uuid4

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, CharacterExtractor, \
    DataExtractor, IntentExtractor, LocationExtractor, NarrativeExtractor, VariableSchemaExtractor, \
    WorldAssembler, WorldLoreExtractor
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.model import BackgroundCharacter, Character, EntityRelationship, \
    EntityVariableSet, Event, Intent, Location, MemoryAtom, Turn, World


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/output")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []

_LANGUAGE_BY_CARD = {
    "01": SupportedLanguage.ENGLISH,
    "02": SupportedLanguage.CHINESE,
    "03": SupportedLanguage.CHINESE,
    "04": SupportedLanguage.CHINESE,
}

_ALL_COMPONENTS = (
    ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_CHARACTER_EXTRACTOR,
    ComponentType.ST_LOCATION_EXTRACTOR, ComponentType.ST_WORLD_LORE_EXTRACTOR,
    ComponentType.ST_NARRATIVE_EXTRACTOR, ComponentType.ST_INTENT_EXTRACTOR,
    ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR,
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
    language = _LANGUAGE_BY_CARD.get(card_path.stem, SupportedLanguage.ENGLISH)
    db = global_scope_chat_config

    classification = await LorebookClassifier(database=db).classify(preprocessed, language=language)
    characters = await CharacterExtractor(database=db).extract(preprocessed, classification, language=language)
    locations = await LocationExtractor(database=db).extract(preprocessed, classification, language=language)
    world_lore = await WorldLoreExtractor(database=db).extract(preprocessed, classification, language=language)
    narrative = await NarrativeExtractor(database=db).extract(preprocessed, classification, characters, language=language)
    intents = await IntentExtractor(database=db).extract(characters, language=language)
    variables = await VariableSchemaExtractor(database=db).extract(preprocessed, classification, language=language)

    assembled = WorldAssembler().assemble(
        preprocessed, language=language, characters=characters, locations=locations, world_lore=world_lore,
        narrative=narrative, intents=intents, variables=variables,
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
