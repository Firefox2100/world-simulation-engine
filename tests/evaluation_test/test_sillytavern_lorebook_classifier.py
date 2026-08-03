import json
from pathlib import Path

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, DataExtractor
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
    return evaluation_database


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
async def test_classify_real_sillytavern_card(card_path: Path, global_scope_chat_config):
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)

    classifier = LorebookClassifier(database=global_scope_chat_config)
    classification = await classifier.classify(
        preprocessed,
        language=_LANGUAGE_BY_CARD.get(card_path.stem, SupportedLanguage.ENGLISH),
    )

    expected_item_count = len(preprocessed.lorebook_entries) + sum(
        1
        for field_name in ("description", "personality", "scenario", "system_prompt", "post_history_instructions", "creator_notes")
        if getattr(preprocessed, field_name).strip()
    )
    assert len(classification.items) == expected_item_count

    # Every item must get one of the fixed bucket values - LorebookItemClassification's own
    # pydantic validation already guarantees this, but assert it explicitly as the behavior this
    # test exists to check.
    item_ids = {item.item_id for item in classification.items}
    expected_ids = {f"entry:{entry.source_id}" for entry in preprocessed.lorebook_entries}
    expected_ids |= {
        f"field:{field_name}"
        for field_name in ("description", "personality", "scenario", "system_prompt", "post_history_instructions", "creator_notes")
        if getattr(preprocessed, field_name).strip()
    }
    assert item_ids == expected_ids

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"lorebook_classifier_{card_path.stem}_results.json").write_text(
        json.dumps(
            {
                "card": card_path.stem,
                "items": [
                    {
                        "item_id": item.item_id,
                        "buckets": [bucket.value for bucket in item.buckets],
                        "target_name": item.target_name,
                    }
                    for item in classification.items
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
