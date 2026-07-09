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
