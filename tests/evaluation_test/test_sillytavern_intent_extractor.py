import json
from pathlib import Path

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, DataExtractor
from world_simulation_engine.component.sillytavern_converter.character_extractor import CharacterExtractor
from world_simulation_engine.component.sillytavern_converter.intent_extractor import IntentExtractor
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/output")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []

def _language_from_card_path(card_path: Path) -> SupportedLanguage:
    """Card filenames encode the extraction language as their final dot-segment (e.g.
    "01.en.png") - the same language the SillyTavern import UI's language selector picks for this
    card, so each card's evaluation output is generated with the prompt set it would actually use
    in production."""
    return SupportedLanguage(card_path.stem.rsplit(".", 1)[-1])


@pytest.fixture
async def global_scope_chat_config(evaluation_database, evaluation_connection_config, evaluation_chat_model_config):
    await evaluation_database.config.create_connection(evaluation_connection_config)
    await evaluation_database.config.create_chat(evaluation_chat_model_config)
    await evaluation_database.config.link_connection(evaluation_chat_model_config.id, evaluation_connection_config.id)
    for component in (
            ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_CHARACTER_EXTRACTOR,
            ComponentType.ST_INTENT_EXTRACTOR,
    ):
        await evaluation_database.config.link_global_chat(evaluation_chat_model_config.id, component)
    return evaluation_database


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
async def test_extract_intents_from_real_sillytavern_card(card_path: Path, global_scope_chat_config):
    """Claude does not run this suite itself (see CLAUDE.md) - the user runs it against a real LLM
    and shares output; Claude only verifies it collects (`pytest tests/evaluation_test
    --collect-only`)."""
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)
    language = _language_from_card_path(card_path)

    classification = await LorebookClassifier(database=global_scope_chat_config).classify(
        preprocessed, language=language,
    )
    characters = await CharacterExtractor(database=global_scope_chat_config).extract(
        preprocessed, classification, language=language,
    )
    extraction = await IntentExtractor(database=global_scope_chat_config).extract(characters, language=language)

    known_ids = {character.id for character in characters.characters}
    for intent in extraction.intents:
        assert intent.character_id in known_ids
        assert intent.name.strip()
        assert intent.description.strip()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"intent_extractor_{card_path.stem}_results.json").write_text(
        json.dumps(
            {
                "card": card_path.stem,
                "intents": [intent.model_dump() for intent in extraction.intents],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
