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
    100% fidelity - see SILLYTAVERN_IMPORT_PLAN.md §5). None of the 4 sample cards' opening
    messages contain an `<UpdateVariable>`/`<initvar>` block either, so the newer
    first-message-initial-values path (§5) isn't exercised by this parametrization - a card with
    one would additionally need its variables' owner_hint to resolve to a real character name
    rather than being dropped."""
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)
    language = _language_from_card_path(card_path)

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
