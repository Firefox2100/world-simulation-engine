from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import Turn
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_world


async def test_create_turn_attaches_to_source(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = TurnStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )

    await store.create_turn(turn, source_id=world.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(turn:Turn {id: $turn_id})
        RETURN turn.sequence AS sequence, turn.type AS type, turn.content AS content
        """,
        parameters_={
            "source_id": world.id,
            "turn_id": turn.id,
        },
    )

    assert result.records[0]["sequence"] == turn.sequence
    assert result.records[0]["type"] == turn.type
    assert result.records[0]["content"] == turn.content


async def test_create_turn_links_previous_turn(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = TurnStore(clean_neo4j)
    first = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    second = Turn(
        id=str(uuid4()),
        sequence=2,
        type=TurnType.SYSTEM_RESPONSE,
        content="Hi",
        start_time=datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
    )

    await store.create_turn(first, source_id=world.id)
    await store.create_turn(second, source_id=world.id, previous_turn_id=first.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Turn {id: $first_id})-[:NEXT]->(:Turn {id: $second_id})
        RETURN count(*) AS link_count
        """,
        parameters_={
            "first_id": first.id,
            "second_id": second.id,
        },
    )

    assert result.records[0]["link_count"] == 1


async def test_list_turns_returns_latest_first_with_limit_and_skip(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = TurnStore(clean_neo4j)
    turns = [
        Turn(
            id=str(uuid4()),
            sequence=sequence,
            type=TurnType.USER_INPUT,
            content=f"Turn {sequence}",
            start_time=datetime(2026, 1, 1, 9, sequence, tzinfo=UTC),
        )
        for sequence in range(5)
    ]

    previous_turn_id = None
    for turn in turns:
        await store.create_turn(turn, source_id=world.id, previous_turn_id=previous_turn_id)
        previous_turn_id = turn.id

    assert await store.list_turns(source_id=world.id, limit=3) == [
        turns[4],
        turns[3],
        turns[2],
    ]
    assert await store.list_turns(source_id=world.id, limit=2, skip=1) == [
        turns[3],
        turns[2],
    ]


async def test_get_turn_by_sequence(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = TurnStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=42,
        type=TurnType.USER_INPUT,
        content="The answer",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )

    await store.create_turn(turn, source_id=world.id)

    assert await store.get_turn(turn.id) == turn
    assert await store.get_turn_by_sequence(world.id, 42) == turn
    assert await store.get_turn_by_sequence(world.id, 41) is None
