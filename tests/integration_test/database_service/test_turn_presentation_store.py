from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import (
    PresentationBlockType,
    PresentationCompletion,
    Turn,
    TurnPresentationBlock,
    TurnPresentationRendering,
)
from world_simulation_engine.service.database.turn_presentation_store import TurnPresentationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_world


NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def test_rendering_variants_do_not_mutate_canonical_turn_and_filter_streaming(clean_neo4j):
    world = await create_world(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="canonical-result",
        start_time=NOW,
    )
    await TurnStore(clean_neo4j).create_turn(turn, source_id=world.id)
    store = TurnPresentationStore(clean_neo4j)
    default = TurnPresentationRendering(
        turn_id=turn.id,
        blocks=[
            TurnPresentationBlock(
                turn_id=turn.id,
                sequence=0,
                type=PresentationBlockType.NARRATION,
                text="Rendered prose.",
                created_at=NOW,
                updated_at=NOW,
            ),
            TurnPresentationBlock(
                turn_id=turn.id,
                sequence=1,
                type=PresentationBlockType.SPEECH,
                text="Partial speech",
                speaker_id="character_1",
                completion=PresentationCompletion.STREAMING,
                created_at=NOW,
                updated_at=NOW,
            ),
        ],
    )
    alternate = TurnPresentationRendering(
        turn_id=turn.id,
        rendering_id="compact",
        locale="en-GB",
        blocks=[TurnPresentationBlock(
            turn_id=turn.id,
            rendering_id="compact",
            locale="en-GB",
            sequence=0,
            type=PresentationBlockType.SYSTEM_NOTICE,
            text="Compact rendering.",
            created_at=NOW,
            updated_at=NOW,
        )],
    )

    assert await store.replace_rendering(default) == default
    assert await store.replace_rendering(alternate) == alternate
    complete = await store.list_blocks(
        turn_ids=[turn.id],
        include_incomplete=False,
    )
    assert [entry.text for entry in complete] == ["Rendered prose."]
    assert await store.list_blocks(
        turn_ids=[turn.id],
        rendering_id="compact",
        locale="en-GB",
    ) == alternate.blocks
    assert await TurnStore(clean_neo4j).get_turn(turn.id) == turn


async def test_copy_presentations_remaps_turn_and_speaker_without_rewriting_content(clean_neo4j):
    source = await create_world(clean_neo4j)
    target = await create_world(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="canonical",
        start_time=NOW,
    )
    turn_store = TurnStore(clean_neo4j)
    await turn_store.create_turn(turn, source_id=source.id)
    presentation_store = TurnPresentationStore(clean_neo4j)
    rendering = TurnPresentationRendering(
        turn_id=turn.id,
        blocks=[TurnPresentationBlock(
            turn_id=turn.id,
            sequence=0,
            type=PresentationBlockType.SPEECH,
            text="Hello.",
            speaker_id="source_character",
            created_at=NOW,
            updated_at=NOW,
        )],
    )
    await presentation_store.replace_rendering(rendering)
    copied_turns, turn_pairs = await turn_store.copy_turns(source.id, target.id)

    copied_count = await presentation_store.copy_presentations(
        turn_pairs=turn_pairs,
        entity_pairs=[{"source_id": "source_character", "copy_id": "copied_character"}],
        copied_at=NOW,
    )
    copied_blocks = await presentation_store.list_blocks(
        turn_ids=[copied_turns[0].id],
    )

    assert copied_count == 1
    assert copied_blocks[0].turn_id == copied_turns[0].id
    assert copied_blocks[0].speaker_id == "copied_character"
    assert copied_turns[0].content == "canonical"
