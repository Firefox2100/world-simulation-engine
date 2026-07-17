from uuid import uuid4

from world_simulation_engine.misc.enums import MediaType
from world_simulation_engine.model import Location, MediaFile, Simulation
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.media_store import MediaStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


async def test_create_get_and_link_cover_images(clean_neo4j):
    world = await create_world(clean_neo4j)
    media_store = MediaStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    simulation = await simulation_store.create_simulation(
        Simulation(
            id=str(uuid4()),
            name="Simulation",
            description="A simulation",
            current_time=world.starting_time,
        ),
        world.id,
    )
    location = Location(
        id=str(uuid4()),
        name="Market",
        description="A busy market",
    )
    first_media = MediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title="First Cover",
        hash="a" * 64,
        filename="first-cover",
    )
    second_media = MediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title="Second Cover",
        hash="b" * 64,
        filename="second-cover",
    )

    await location_store.create_location(location, source_id=world.id)
    assert await media_store.create_media(first_media) == first_media
    assert await media_store.create_media(second_media) == second_media
    assert await media_store.get_media(first_media.id) == first_media

    assert await media_store.set_cover_image(world.id, first_media.id) == first_media
    assert await media_store.get_cover_image(world.id) == first_media
    assert await media_store.set_cover_image(world.id, second_media.id) == second_media
    assert await media_store.get_cover_image(world.id) == second_media
    assert await media_store.set_cover_image(simulation.id, first_media.id) == first_media
    assert await media_store.get_cover_image(simulation.id) == first_media
    assert await media_store.set_cover_image(location.id, first_media.id) == first_media
    assert await media_store.get_cover_image(location.id) == first_media
    assert await media_store.remove_cover_image(location.id) is True
    assert await media_store.get_cover_image(location.id) is None

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $world_id})-[cover:HAS_COVER]->(:Media)
        RETURN count(cover) AS cover_count
        """,
        parameters_={"world_id": world.id},
    )

    assert result.records[0]["cover_count"] == 1
    assert await media_store.get_media(str(uuid4())) is None
    assert await media_store.set_cover_image(str(uuid4()), first_media.id) is None
    assert await media_store.set_cover_image(world.id, str(uuid4())) is None
    assert await media_store.get_cover_image(str(uuid4())) is None


async def test_delete_media_removes_record_and_reports_hash_references(clean_neo4j):
    media_store = MediaStore(clean_neo4j)
    first_media = MediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title="First",
        hash="a" * 64,
        filename="first",
    )
    second_media = MediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title="Second",
        hash=first_media.hash,
        filename="second",
    )

    await media_store.create_media(first_media)
    await media_store.create_media(second_media)

    assert await media_store.delete_media(first_media.id) == (first_media, 1)
    assert await media_store.get_media(first_media.id) is None
    assert await media_store.get_media(second_media.id) == second_media
    assert await media_store.delete_media(second_media.id) == (second_media, 0)
    assert await media_store.delete_media(second_media.id) is None
