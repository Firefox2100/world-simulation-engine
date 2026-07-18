from datetime import UTC, datetime, timedelta
from uuid import uuid4

from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType, TurnType
from world_simulation_engine.model import Event, Intent, Turn
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.intent_store import IntentStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


def make_intent(name: str,
                status: IntentStatus = IntentStatus.ACTIVE,
                priority: float = 0.5,
                urgency: float = 0.5,
                deadline: datetime | None = None,
                embedding: list[float] | None = None,
                ) -> Intent:
    return Intent(
        id=str(uuid4()),
        type=IntentType.QUEST,
        name=name,
        description=f"{name} description",
        keywords=name.lower().split(),
        embedding=embedding,
        priority=priority,
        urgency=urgency,
        status=status,
        desired_state=f"{name} done",
        success_conditions=[f"{name} succeeds"],
        failure_conditions=[f"{name} fails"],
        maintenance_conditions=[f"{name} maintained"],
        deadline=deadline,
        horizon=IntentHorizon.SHORT,
        constraints=[f"{name} constraint"],
        current_plan=[f"{name} plan"],
        next_action_biases=[f"{name} next"],
        blockers=[f"{name} blocker"],
        open_threads=[f"{name} thread"],
    )


async def test_create_intent_attaches_to_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    store = IntentStore(clean_neo4j)
    intent = make_intent(
        "Buy coffee",
        priority=0.8,
        urgency=0.7,
        deadline=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
        embedding=[0.1, 0.2],
    )

    assert await store.create_intent(intent, character.id) == intent
    assert await store.get_intent(intent.id) == intent
    assert await store.list_intents(character_id=character.id) == [intent]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[:HOLDS]->(intent:Intent {id: $intent_id})
        RETURN intent
        """,
        parameters_={
            "character_id": character.id,
            "intent_id": intent.id,
        },
    )

    stored = result.records[0]["intent"]
    assert stored["name"] == intent.name
    assert stored["type"] == IntentType.QUEST
    assert stored["status"] == IntentStatus.ACTIVE
    assert stored["priority"] == 0.8
    assert stored["urgency"] == 0.7
    assert stored["embedding"] == [0.1, 0.2]
    assert stored["success_conditions"] == intent.success_conditions
    assert stored["current_plan"] == intent.current_plan


async def test_list_update_and_delete_intent(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    store = IntentStore(clean_neo4j)
    intent = make_intent("Buy coffee")

    await store.create_intent(intent, character.id)

    assert await store.list_intents() == [intent]
    assert await store.list_intents(character_id=character.id) == [intent]

    updated_intent = await store.update_intent(
        intent_id=intent.id,
        properties={
            "status": IntentStatus.PAUSED,
            "priority": 0.9,
            "current_plan": ["wait"],
        },
    )

    assert updated_intent == intent.model_copy(
        update={
            "status": IntentStatus.PAUSED,
            "priority": 0.9,
            "current_plan": ["wait"],
        }
    )
    assert await store.delete_intent(intent.id) is True
    assert await store.get_intent(intent.id) is None
    assert await store.delete_intent(intent.id) is False


async def test_event_relationships_to_intent(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    second_character = await create_character(clean_neo4j, world.id, name="Blair")
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="A long meeting happened",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Long meeting",
        summary="Alex had a long meeting.",
    )
    intent = make_intent("Buy coffee")
    intent_store = IntentStore(clean_neo4j)

    await TurnStore(clean_neo4j).create_turn(turn, source_id=world.id)
    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await intent_store.create_intent(intent, character.id)
    assert await intent_store.add_event_contribution(event.id, intent.id) == intent
    assert await intent_store.add_event_creation(event.id, intent.id) == intent
    assert await intent_store.list_intents(event_id=event.id) == [intent]
    assert await intent_store.list_intents(character_id=character.id, event_id=event.id) == [intent]
    assert await intent_store.move_intent_to_character(intent.id, second_character.id) == intent
    assert await intent_store.list_intents(character_id=character.id) == []
    assert await intent_store.list_intents(character_id=second_character.id) == [intent]
    assert await intent_store.replace_event_contributions(intent.id, [event.id]) == intent

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Event {id: $event_id})-[contributes:CONTRIBUTES_TO]->(:Intent {id: $intent_id})
        MATCH (:Event {id: $event_id})-[creates:CREATES]->(:Intent {id: $intent_id})
        RETURN count(contributes) AS contributes_count, count(creates) AS creates_count
        """,
        parameters_={
            "event_id": event.id,
            "intent_id": intent.id,
        },
    )

    assert result.records[0]["contributes_count"] == 1
    assert result.records[0]["creates_count"] == 1
    assert await intent_store.remove_event_creation(intent.id) is True
    assert await intent_store.remove_event_contributions(intent.id, [event.id]) is True
    assert await intent_store.list_intents(event_id=event.id) == []
    assert await intent_store.remove_event_creation(str(uuid4())) is False
    assert await intent_store.remove_event_contributions(str(uuid4()), [event.id]) is False


async def test_copy_intents_preserves_character_and_event_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    target_world = await create_world(clean_neo4j)
    source_character = await create_character(clean_neo4j, world.id, name="Alex")
    copy_character = await create_character(clean_neo4j, target_world.id, name="Copied Alex")
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="A long meeting happened",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Long meeting",
        summary="Alex had a long meeting.",
    )
    copy_event = Event(
        id=str(uuid4()),
        name="Copied long meeting",
        summary="A copied meeting.",
    )
    intent = make_intent("Buy coffee")
    intent_store = IntentStore(clean_neo4j)

    await TurnStore(clean_neo4j).create_turn(turn, source_id=world.id)
    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await EventStore(clean_neo4j).create_event(copy_event, turn_ids=[turn.id])
    await intent_store.create_intent(intent, source_character.id)
    await intent_store.add_event_creation(event.id, intent.id)
    await intent_store.add_event_contribution(event.id, intent.id)

    copied_intents, intent_pairs = await intent_store.copy_intents(
        character_pairs=[
            {
                "source_id": source_character.id,
                "copy_id": copy_character.id,
            }
        ],
        event_pairs=[
            {
                "source_id": event.id,
                "copy_id": copy_event.id,
            }
        ],
    )

    assert len(copied_intents) == 1
    copied_intent = copied_intents[0]
    assert copied_intent.id != intent.id
    assert copied_intent.model_copy(update={"id": intent.id}) == intent
    assert intent_pairs == [
        {
            "source_id": intent.id,
            "copy_id": copied_intent.id,
        }
    ]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[:HOLDS]->(:Intent {id: $intent_id})
        MATCH (:Event {id: $event_id})-[:CREATES]->(:Intent {id: $intent_id})
        MATCH (:Event {id: $event_id})-[:CONTRIBUTES_TO]->(:Intent {id: $intent_id})
        RETURN count(*) AS relationship_count
        """,
        parameters_={
            "character_id": copy_character.id,
            "event_id": copy_event.id,
            "intent_id": copied_intent.id,
        },
    )

    assert result.records[0]["relationship_count"] == 1


async def test_get_active_intent_candidates_filters_by_deadline_priority_and_urgency(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    store = IntentStore(clean_neo4j)
    current_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    near_deadline = make_intent(
        "Near deadline",
        deadline=current_time + timedelta(hours=3),
    )
    high_priority = make_intent(
        "High priority",
        status=IntentStatus.PAUSED,
        priority=0.9,
    )
    high_urgency = make_intent(
        "High urgency",
        urgency=0.9,
    )
    inactive_high_priority = make_intent(
        "Inactive high priority",
        status=IntentStatus.COMPLETED,
        priority=0.95,
    )
    far_low = make_intent(
        "Far low",
        deadline=current_time + timedelta(days=7),
    )

    for intent in [near_deadline, high_priority, high_urgency, inactive_high_priority, far_low]:
        await store.create_intent(intent, character.id)

    candidates = await store.get_active_intent_candidates(
        character_id=character.id,
        current_time=current_time,
        deadline_delta=timedelta(hours=24),
        priority_threshold=0.7,
        urgency_threshold=0.7,
    )

    assert {intent.id for intent in candidates} == {
        near_deadline.id,
        high_priority.id,
        high_urgency.id,
    }
