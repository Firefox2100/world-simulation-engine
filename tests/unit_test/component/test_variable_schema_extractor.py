from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, \
    PreprocessedLorebookEntry, VariableScriptCandidate
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.component.sillytavern_converter.variable_schema_extractor import \
    VariableFieldCandidate, VariableSchemaCandidates, VariableSchemaExtractor, \
    _CHUNK_TARGET_LINES, _MAX_VARIABLES_PER_SOURCE
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
        first_message="<UpdateVariable>\n<initvar>\n示例角色:\n  好感度: 50\n</initvar>\n</UpdateVariable>",
    )
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="示例角色", name="好感度", value_type=VariableValueType.INTEGER,
                default_value=50, description="Affection towards the user.",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) == 1
    variable = extraction.variables[0]
    assert variable.owner_hint == "示例角色"
    assert variable.name == "好感度"
    assert variable.default_value == 50
    assert variable.source_item_ids == ["first_message"]
    prompt_call = extractor._prepare_global_prompt.await_args
    assert prompt_call.kwargs["prompt_name"] == "st_variable_initial_value_extractor"


async def test_extract_flags_a_source_that_hits_the_per_call_cap():
    # A source whose call returns exactly the cap is likely truncated - the real content probably
    # defines more variables than a single bounded structured-output call can return - so it must
    # be surfaced for the conversion report rather than silently treated as complete.
    card = make_card(variable_schema_candidates=[
        VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="z.object({...})"),
    ])
    capped_batch = VariableSchemaCandidates(variables=[
        VariableFieldCandidate(
            owner_hint="world", name=f"field_{i}", value_type=VariableValueType.STRING,
            default_value="", description="Generated field.",
        )
        for i in range(_MAX_VARIABLES_PER_SOURCE)
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=capped_batch),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) == _MAX_VARIABLES_PER_SOURCE
    assert extraction.capped_source_ids == ["script:0"]


async def test_extract_does_not_flag_a_source_under_the_cap():
    card = make_card(variable_schema_candidates=[
        VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="z.object({...})"),
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="self", name="hp", value_type=VariableValueType.INTEGER,
                default_value=100, description="Health points.",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.capped_source_ids == []


def test_chunk_content_leaves_small_content_unchanged():
    content = "field_one: string\nfield_two: integer"

    assert VariableSchemaExtractor._chunk_content(content) == [content]


def test_chunk_content_splits_large_content_along_blank_line_boundaries():
    # Real card content (Zod schemas, JSON-pointer path indexes, YAML-style rule docs) is reliably
    # blank-line-delimited between logical groups - synthesize the same shape here rather than
    # depending on any real (unlicensed, not-checked-in) card asset.
    blocks = [f"block_{i}:\n" + "\n".join(f"  field_{i}_{j}: string" for j in range(6)) for i in range(20)]
    content = "\n\n".join(blocks)

    chunks = VariableSchemaExtractor._chunk_content(content)

    assert len(chunks) > 1
    for chunk in chunks:
        non_blank_lines = [line for line in chunk.splitlines() if line.strip()]
        assert len(non_blank_lines) <= _CHUNK_TARGET_LINES
    # No block is split mid-way - every block's lines stay contiguous within exactly one chunk.
    for block in blocks:
        assert sum(block in chunk for chunk in chunks) == 1
    # Re-joining every chunk recovers every original block (order preserved, nothing dropped).
    assert "\n\n".join(chunks) == content


def test_chunk_content_keeps_an_oversized_single_block_whole():
    # A block with no internal blank lines can't be split without risking a mid-field cut - it's
    # kept as one (larger) chunk; the per-call cap/capped_source_ids reporting is the backstop.
    content = "\n".join(f"field_{i}: string" for i in range(_CHUNK_TARGET_LINES * 2))

    assert VariableSchemaExtractor._chunk_content(content) == [content]


async def test_extract_dispatches_one_call_per_chunk_for_a_source_that_needs_chunking():
    blocks = [f"block_{i}:\n" + "\n".join(f"  field_{i}_{j}: string" for j in range(6)) for i in range(20)]
    card = make_card(variable_schema_candidates=[
        VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="\n\n".join(blocks)),
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    service = Mock()
    service.invoke_structured_with_repair = AsyncMock(return_value=VariableSchemaCandidates(variables=[]))
    extractor._prepare_global_llm_service = AsyncMock(return_value=service)

    await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    call_count = service.invoke_structured_with_repair.await_count
    assert call_count > 1
    # Concurrent fan-out doesn't guarantee call order, so check the set of "part i of N" markers
    # rather than positional order.
    labels = [call.kwargs["data"]["label"] for call in service.invoke_structured_with_repair.await_args_list]
    for i in range(1, call_count + 1):
        marker = f"part {i} of {call_count}"
        assert any(marker in label for label in labels), f"missing {marker!r} in {labels}"


async def test_extract_tags_every_chunk_of_a_source_with_the_original_item_id():
    blocks = [f"block_{i}:\n" + "\n".join(f"  field_{i}_{j}: string" for j in range(6)) for i in range(20)]
    card = make_card(variable_schema_candidates=[
        VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="\n\n".join(blocks)),
    ])
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    call_index = 0

    async def fake_invoke(*, output_model, messages, data, repair_instruction, run_name):
        nonlocal call_index
        call_index += 1
        return VariableSchemaCandidates(variables=[
            VariableFieldCandidate(
                owner_hint="world", name=f"field_{call_index}", value_type=VariableValueType.STRING,
                default_value="", description="Generated field.",
            ),
        ])

    service = Mock()
    service.invoke_structured_with_repair = AsyncMock(side_effect=fake_invoke)
    extractor._prepare_global_llm_service = AsyncMock(return_value=service)

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.variables) > 1
    assert all(variable.source_item_ids == ["script:0"] for variable in extraction.variables)


async def test_extract_orders_first_message_variables_after_schema_source_variables():
    card = make_card(
        variable_schema_candidates=[
            VariableScriptCandidate(source="tavern_helper_script", name="Schema", content="z.object({...})"),
        ],
        first_message="<UpdateVariable><initvar>示例角色:\n  好感度: 50\n</initvar></UpdateVariable>",
    )
    extractor = VariableSchemaExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    async def fake_invoke(*, output_model, messages, data, repair_instruction, run_name):
        if run_name == "variable_schema_extractor.extract_first_message":
            return VariableSchemaCandidates(variables=[
                VariableFieldCandidate(
                    owner_hint="示例角色", name="好感度", value_type=VariableValueType.INTEGER,
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
        ("示例角色", ["first_message"]),
    ]
