from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, \
    PreprocessedLorebookEntry, VariableScriptCandidate
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.component.sillytavern_converter.variable_schema_extractor import \
    VariableFieldCandidate, VariableSchemaCandidates, VariableSchemaExtractor
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage
from world_simulation_engine.model.variable import VariableValueType


def make_card(*, variable_schema_candidates=None, lorebook_entries=None) -> PreprocessedCard:
    return PreprocessedCard(
        name="Card",
        variable_schema_candidates=variable_schema_candidates or [],
        lorebook_entries=lorebook_entries or [],
    )


async def test_extract_dispatches_one_call_per_script_candidate():
    card = make_card(variable_schema_candidates=[
        VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="z.object({...})"),
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="self", name="hp", value_type=VariableValueType.INTEGER,
                default_value=100, description="Health points.", minimum=0, maximum=100,
            ),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) == 1
    variable = extraction.variables[0]
    assert variable.name == "hp"
    assert variable.value_type == VariableValueType.INTEGER
    assert variable.source_item_ids == ["script:0"]


async def test_extract_dispatches_one_call_per_variable_meta_item():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="变量列表", content="生命值：0-100，默认100"),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.VARIABLE_META]),
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="self", name="生命值", value_type=VariableValueType.INTEGER,
                default_value=100, description="生命值", minimum=0, maximum=100,
            ),
        ])),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) == 1
    assert extraction.variables[0].source_item_ids == ["entry:1"]


async def test_extract_returns_empty_without_calling_llm_when_no_sources():
    card = make_card()
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.variables == []
    extractor._prepare_global_llm_service.assert_not_awaited()
