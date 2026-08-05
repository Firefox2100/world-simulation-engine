import json
from pathlib import Path

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, DataExtractor
from world_simulation_engine.component.sillytavern_converter.equipment_extractor import EquipmentExtractor
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/output")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []

_LANGUAGE_BY_CARD = {
    "01": SupportedLanguage.ENGLISH,
    "02": SupportedLanguage.CHINESE,
    "03": SupportedLanguage.CHINESE,
    "04": SupportedLanguage.CHINESE,
}


@pytest.fixture
async def global_scope_chat_config(evaluation_database, evaluation_connection_config, evaluation_chat_model_config):
    await evaluation_database.config.create_connection(evaluation_connection_config)
    await evaluation_database.config.create_chat(evaluation_chat_model_config)
    await evaluation_database.config.link_connection(evaluation_chat_model_config.id, evaluation_connection_config.id)
    await evaluation_database.config.link_global_chat(
        evaluation_chat_model_config.id, ComponentType.ST_LOREBOOK_CLASSIFIER,
    )
    await evaluation_database.config.link_global_chat(
        evaluation_chat_model_config.id, ComponentType.ST_EQUIPMENT_EXTRACTOR,
    )
    return evaluation_database


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
async def test_extract_equipment_from_real_sillytavern_card(card_path: Path, global_scope_chat_config):
    """Claude does not run this suite itself (see CLAUDE.md) - the user runs it against a real LLM
    and shares output; Claude only verifies it collects (`pytest tests/evaluation_test
    --collect-only`). This extractor only sources from lorebook entries the classifier routes into
    the `item` bucket, plus an opening-message `<UpdateVariable><initvar>` block if present
    (SILLYTAVERN_IMPORT_PLAN.md §5) - a card with neither is expected to yield zero equipment, not
    an error. None of the 4 bundled sample cards' opening messages contain such a block."""
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)
    language = _LANGUAGE_BY_CARD.get(card_path.stem, SupportedLanguage.ENGLISH)

    classification = await LorebookClassifier(database=global_scope_chat_config).classify(
        preprocessed, language=language,
    )
    extraction = await EquipmentExtractor(database=global_scope_chat_config).extract(
        preprocessed, classification, language=language,
    )

    for equipment in extraction.equipment:
        assert equipment.name.strip()
        assert equipment.description.strip()
        assert equipment.source_item_ids

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"equipment_extractor_{card_path.stem}_results.json").write_text(
        json.dumps(
            {
                "card": card_path.stem,
                "equipment": [equipment.model_dump() for equipment in extraction.equipment],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
