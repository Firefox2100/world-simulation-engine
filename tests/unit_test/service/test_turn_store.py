from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import Turn
from world_simulation_engine.service.database.turn_store import TurnStore


class FakeNeo4jDateTime:
    def __init__(self, value: datetime):
        self.value = value

    def to_native(self):
        return self.value


def test_turn_from_node_converts_neo4j_datetime():
    start_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    turn = TurnStore.turn_from_node(
        {
            "id": "turn_1",
            "sequence": 3,
            "type": TurnType.USER_INPUT,
            "content": "I open the door.",
            "start_time": FakeNeo4jDateTime(start_time),
        }
    )

    assert turn.start_time == start_time
    assert turn.type == TurnType.USER_INPUT


async def test_create_next_turn_returns_created_turn():
    turn_node = {
        "id": "turn_1",
        "sequence": 2,
        "type": "system_response",
        "content": "The scene continues.",
        "start_time": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    }
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "turn": turn_node,
                    }
                ]
            )
        )
    )
    store = TurnStore(driver)

    result = await store.create_next_turn(
        source_id="simulation_1",
        turn=Turn(
            id="turn_1",
            sequence=0,
            type=TurnType.SYSTEM_RESPONSE,
            content="The scene continues.",
            start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
    )

    assert result.id == "turn_1"
    assert result.sequence == 2
    assert result.type == TurnType.SYSTEM_RESPONSE
    assert driver.execute_query.await_args.kwargs["parameters_"]["source_id"] == "simulation_1"
