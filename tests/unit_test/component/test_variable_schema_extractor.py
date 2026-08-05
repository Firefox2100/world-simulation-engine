from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, \
    PreprocessedLorebookEntry, VariableScriptCandidate
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.component.sillytavern_converter.variable_schema_extractor import \
    VariableFieldCandidate, VariableSchemaCandidates, VariableSchemaExtractor
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage
from world_simulation_engine.model.variable import VariableValueType


def make_card(
        *, variable_schema_candidates=None, lorebook_entries=None, first_message="",
) -> PreprocessedCard:
    return PreprocessedCard(
        name="Card",
        variable_schema_candidates=variable_schema_candidates or [],
        lorebook_entries=lorebook_entries or [],
        first_message=first_message,
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


async def test_extract_returns_empty_without_calling_llm_when_first_message_has_no_marker():
    # Plain narrative opening messages (the common case) shouldn't spend an LLM call - only
    # <UpdateVariable>/<initvar>-style blocks are plausible signal.
    card = make_card(first_message="He walked into the room and smiled at her.")
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.variables == []
    extractor._prepare_global_llm_service.assert_not_awaited()


async def test_extract_dispatches_a_call_for_a_first_message_initial_value_block():
    card = make_card(
        first_message="<UpdateVariable>\n<initvar>\n小雨:\n  好感度: 50\n</initvar>\n</UpdateVariable>",
    )
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="小雨", name="好感度", value_type=VariableValueType.INTEGER,
                default_value=50, description="Affection towards the user.",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) == 1
    variable = extraction.variables[0]
    assert variable.owner_hint == "小雨"
    assert variable.name == "好感度"
    assert variable.default_value == 50
    assert variable.source_item_ids == ["first_message"]
    prompt_call = extractor._prepare_global_prompt.await_args
    assert prompt_call.kwargs["prompt_name"] == "st_variable_initial_value_extractor"


async def test_extract_orders_first_message_variables_after_schema_source_variables():
    card = make_card(
        variable_schema_candidates=[
            VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="z.object({...})"),
        ],
        first_message="<UpdateVariable><initvar>小雨:\n  好感度: 50\n</initvar></UpdateVariable>",
    )
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    async def fake_invoke(*, output_model, messages, data, repair_instruction, run_name):
        if run_name == "variable_schema_extractor.extract_first_message":
            return VariableSchemaCandidates(variables=[
                VariableFieldCandidate(
                    owner_hint="小雨", name="好感度", value_type=VariableValueType.INTEGER,
                    default_value=50, description="Affection towards the user.",
                ),
            ])
        return VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="owner_column", name="好感度", value_type=VariableValueType.INTEGER,
                default_value=0, description="Schema-described, no real owner.",
            ),
        ])

    service = Mock()
    service.invoke_structured_with_repair = AsyncMock(side_effect=fake_invoke)
    extractor._prepare_global_llm_service = AsyncMock(return_value=service)

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert [(v.owner_hint, v.source_item_ids) for v in extraction.variables] == [
        ("owner_column", ["script:0"]),
        ("小雨", ["first_message"]),
    ]
