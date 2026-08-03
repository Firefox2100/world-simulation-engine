import json
from pathlib import Path

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, DataExtractor
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier
from world_simulation_engine.component.sillytavern_converter.variable_schema_extractor import \
    VariableSchemaExtractor
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
    for component in (ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR):
        await evaluation_database.config.link_global_chat(evaluation_chat_model_config.id, component)
    return evaluation_database


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
async def test_extract_variable_schema_from_real_sillytavern_card(card_path: Path, global_scope_chat_config):
    """Claude does not run this suite itself (see CLAUDE.md) - the user runs it against a real LLM
    and shares output; Claude only verifies it collects (`pytest tests/evaluation_test
    --collect-only`). Only card 03 is expected to yield anything - the others have no variable
    schema script or variable_meta lorebook entries at all (a meaningful, best-effort pass, not
    100% fidelity - see SILLYTAVERN_IMPORT_PLAN.md §5)."""
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)
    language = _LANGUAGE_BY_CARD.get(card_path.stem, SupportedLanguage.ENGLISH)

    classification = await LorebookClassifier(database=global_scope_chat_config).classify(
        preprocessed, language=language,
    )
    extraction = await VariableSchemaExtractor(database=global_scope_chat_config).extract(
        preprocessed, classification, language=language,
    )

    for variable in extraction.variables:
        assert variable.name.strip()
        assert variable.owner_hint.strip()
        assert variable.source_item_ids

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"variable_schema_extractor_{card_path.stem}_results.json").write_text(
        json.dumps(
            {
                "card": card_path.stem,
                "variables": [variable.model_dump() for variable in extraction.variables],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
