from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType
from world_simulation_engine.service.database.intent_store import IntentStore


class FakeNeo4jDateTime:
    def __init__(self, value: datetime):
        self.value = value

    def to_native(self):
        return self.value


def make_intent_node(**overrides):
    node = {
        "id": "intent_1",
        "type": IntentType.QUEST,
        "name": "Find the key",
        "description": "Find the brass key.",
        "keywords": ("key", "brass"),
        "embedding": (0.1, 0.2),
        "priority": 0.8,
        "urgency": 0.7,
        "status": IntentStatus.ACTIVE,
        "desired_state": "The key is found.",
        "success_conditions": ("key found",),
        "failure_conditions": (),
        "maintenance_conditions": (),
        "deadline": FakeNeo4jDateTime(datetime(2026, 1, 1, 18, tzinfo=UTC)),
        "horizon": IntentHorizon.SHORT,
        "constraints": ("stay quiet",),
        "current_plan": ("search the desk",),
        "next_action_biases": ("look under papers",),
        "blockers": ("locked drawer",),
        "open_threads": ("who hid the key",),
    }
    node.update(overrides)
    return node


def test_intent_from_node_converts_optional_sequences_and_datetime():
    intent = IntentStore.intent_from_node(make_intent_node())

    assert intent.deadline == datetime(2026, 1, 1, 18, tzinfo=UTC)
    assert intent.keywords == ["key", "brass"]
    assert intent.embedding == [0.1, 0.2]
    assert intent.success_conditions == ["key found"]
    assert intent.blockers == ["locked drawer"]


async def test_update_intent_skips_empty_updates():
    driver = SimpleNamespace(execute_query=AsyncMock())
    store = IntentStore(driver)

    await store.update_intent(
        intent_id="intent_1",
        properties={
            "status": None,
            "priority": None,
        },
    )

    driver.execute_query.assert_not_called()


async def test_update_intent_strips_none_values_before_writing():
    driver = SimpleNamespace(execute_query=AsyncMock())
    store = IntentStore(driver)

    await store.update_intent(
        intent_id="intent_1",
        properties={
            "status": IntentStatus.PAUSED,
            "priority": None,
            "current_plan": ["wait"],
        },
    )

    assert driver.execute_query.await_args.kwargs["parameters_"] == {
        "intent_id": "intent_1",
        "properties": {
            "status": IntentStatus.PAUSED,
            "current_plan": ["wait"],
        },
    }


async def test_get_active_intent_candidates_passes_thresholds_and_cutoff():
    current_time = datetime(2026, 1, 1, 12, tzinfo=UTC)
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "intent": make_intent_node(
                            deadline=datetime(2026, 1, 1, 13, tzinfo=UTC),
                            embedding=None,
                        )
                    }
                ]
            )
        )
    )
    store = IntentStore(driver)

    intents = await store.get_active_intent_candidates(
        character_id="character_1",
        current_time=current_time,
        deadline_delta=timedelta(hours=6),
        priority_threshold=0.5,
        urgency_threshold=0.6,
    )

    assert intents[0].id == "intent_1"
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["statuses"] == [IntentStatus.ACTIVE, IntentStatus.PAUSED]
    assert parameters["deadline_cutoff"] == current_time + timedelta(hours=6)
    assert parameters["priority_threshold"] == 0.5
    assert parameters["urgency_threshold"] == 0.6
