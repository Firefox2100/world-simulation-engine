from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import EventInvolvement, TurnType
from world_simulation_engine.model import Event, Turn
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_create_event_attaches_to_turns(clean_neo4j):
    world = await create_world(clean_neo4j)
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
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
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )

    await turn_store.create_turn(first, source_id=world.id)
    await turn_store.create_turn(second, source_id=world.id, previous_turn_id=first.id)
    assert await event_store.create_event(event, turn_ids=[first.id, second.id]) == event
    assert await event_store.get_event(event.id) == event
    assert await event_store.list_events(turn_id=first.id) == [event]

    result = await clean_neo4j.execute_query(
        """
        MATCH (turn:Turn)-[:PART_OF]->(event:Event {id: $event_id})
        RETURN event.name AS name, collect(turn.id) AS turn_ids
        """,
        parameters_={"event_id": event.id},
    )

    assert result.records[0]["name"] == event.name
    assert set(result.records[0]["turn_ids"]) == {first.id, second.id}


async def test_list_update_and_delete_event(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )

    await turn_store.create_turn(turn, source_id=world.id)
    await event_store.create_event(event, turn_ids=[turn.id])
    await event_store.add_character_involvement(event.id, character.id, EventInvolvement.PARTICIPATE)

    assert await event_store.list_events() == [event]
    assert await event_store.list_events(character_id=character.id) == [event]
    assert await event_store.list_events(character_id=character.id, turn_id=turn.id) == [event]

    updated_event = await event_store.update_event(
        event.id,
        name="Updated greeting",
        summary="An updated greeting exchange",
    )

    assert updated_event == Event(
        id=event.id,
        name="Updated greeting",
        summary="An updated greeting exchange",
    )
    assert await event_store.delete_event(event.id) is True
    assert await event_store.get_event(event.id) is None
    assert await event_store.delete_event(event.id) is False


async def test_add_turn_to_event(clean_neo4j):
    world = await create_world(clean_neo4j)
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
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
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )

    await turn_store.create_turn(first, source_id=world.id)
    await turn_store.create_turn(second, source_id=world.id)
    await event_store.create_event(event, turn_ids=[first.id])
    await event_store.add_turn_to_event(event.id, second.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (turn:Turn)-[:PART_OF]->(:Event {id: $event_id})
        RETURN collect(turn.id) AS turn_ids
        """,
        parameters_={"event_id": event.id},
    )

    assert set(result.records[0]["turn_ids"]) == {first.id, second.id}


async def test_add_character_involvement(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )

    await turn_store.create_turn(turn, source_id=world.id)
    await event_store.create_event(event, turn_ids=[turn.id])
    await event_store.add_character_involvement(
        event.id,
        character.id,
        EventInvolvement.PARTICIPATE,
    )

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Event {id: $event_id})-[relationship:INVOLVES]->(:Character {id: $character_id})
        RETURN relationship.involvement AS involvement
        """,
        parameters_={
            "event_id": event.id,
            "character_id": character.id,
        },
    )

    assert result.records[0]["involvement"] == EventInvolvement.PARTICIPATE


async def test_copy_events_preserves_turn_and_character_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
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
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )
    target_world = await create_world(clean_neo4j)
    copied_character = await create_character(clean_neo4j, target_world.id, name="Copied Alex")

    await turn_store.create_turn(first, source_id=world.id)
    await turn_store.create_turn(second, source_id=world.id, previous_turn_id=first.id)
    _, turn_pairs = await turn_store.copy_turns(world.id, target_world.id)
    await event_store.create_event(event, turn_ids=[first.id, second.id])
    await event_store.add_character_involvement(event.id, character.id, EventInvolvement.PARTICIPATE)

    copied_events, event_pairs = await event_store.copy_events(
        turn_pairs=turn_pairs,
        character_pairs=[
            {
                "source_id": character.id,
                "copy_id": copied_character.id,
            }
        ],
    )

    assert len(copied_events) == 1
    copied_event = copied_events[0]
    assert copied_event.id != event.id
    assert copied_event.model_copy(update={"id": event.id}) == event
    assert event_pairs == [
        {
            "source_id": event.id,
            "copy_id": copied_event.id,
        }
    ]

    result = await clean_neo4j.execute_query(
        """
        MATCH (turn:Turn)-[:PART_OF]->(:Event {id: $event_id})-[:INVOLVES]->(:Character {id: $character_id})
        RETURN collect(turn.id) AS turn_ids
        """,
        parameters_={
            "event_id": copied_event.id,
            "character_id": copied_character.id,
        },
    )

    assert set(result.records[0]["turn_ids"]) == {
        pair["copy_id"]
        for pair in turn_pairs
    }
