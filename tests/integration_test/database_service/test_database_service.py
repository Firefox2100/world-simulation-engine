from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import Character, CurrentActivity, Location, Simulation
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


def _character(name: str) -> Character:
    return Character(
        id=str(uuid4()),
        name=name,
        age=30,
        gender="unknown",
        appearance="Plain",
        description="A test character",
        public_state="Present",
        private_state="Attentive",
        current_activity=CurrentActivity(name="idle"),
    )


async def test_perception_queries_share_nested_location_scope(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)

    location_store = LocationStore(clean_neo4j)
    hall = Location(id=str(uuid4()), name="Hall", description="A large hall")
    alcove = Location(id=str(uuid4()), name="Alcove", description="Part of the hall")
    street = Location(id=str(uuid4()), name="Street", description="Outside")
    await location_store.create_location(hall, simulation.id)
    await location_store.create_location(alcove, simulation.id, contained_in=hall.id)
    await location_store.create_location(street, simulation.id)

    character_store = CharacterStore(clean_neo4j)
    hall_observer = _character("Hall Observer")
    alcove_actor = _character("Alcove Actor")
    street_character = _character("Street Character")
    for character in (hall_observer, alcove_actor, street_character):
        await character_store.create_character(character, simulation.id)
    await character_store.move_to_location(hall_observer.id, hall.id)
    await character_store.move_to_location(alcove_actor.id, alcove.id)
    await character_store.move_to_location(street_character.id, street.id)

    database = DatabaseService(clean_neo4j)
    perceived = await database.get_characters_perceivable_by(hall_observer.id)
    observers = await database.get_characters_that_can_perceive_characters(
        simulation_id=simulation.id,
        character_ids=[alcove_actor.id],
    )

    assert [entry[0].id for entry in perceived] == [alcove_actor.id]
    assert {character.id for character in observers} == {hall_observer.id, alcove_actor.id}
    assert street_character.id not in {character.id for character in observers}
