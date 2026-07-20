from uuid import uuid4

from world_simulation_engine.misc.enums import ComponentType, MediaType
from world_simulation_engine.model import Location, MediaFile, PromptMediaFile, Simulation
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
    assert await media_store.list_media() == [first_media, second_media]
    assert await media_store.list_media(media_type=MediaType.PNG) == [first_media, second_media]
    assert await media_store.list_media(limit=1) == [first_media]
    assert await media_store.list_media(limit=1, skip=1) == [second_media]
    assert await media_store.list_media(world_id=world.id) == []
    assert await media_store.list_media(simulation_id=simulation.id) == []

    assert await media_store.set_cover_image(world.id, first_media.id) == first_media
    assert await media_store.get_cover_image(world.id) == first_media
    assert await media_store.set_cover_image(world.id, second_media.id) == second_media
    assert await media_store.get_cover_image(world.id) == second_media
    assert await media_store.set_cover_image(simulation.id, first_media.id) == first_media
    assert await media_store.get_cover_image(simulation.id) == first_media
    assert await media_store.set_cover_image(location.id, first_media.id) == first_media
    assert await media_store.get_cover_image(location.id) == first_media
    assert await media_store.list_media(world_id=world.id) == [first_media, second_media]
    assert await media_store.list_media(simulation_id=simulation.id) == [first_media]
    assert await media_store.list_media(world_id=world.id, simulation_id=simulation.id) == [first_media]
    assert await media_store.list_media(world_id=world.id, limit=1, skip=1) == [second_media]
    assert await media_store.list_source_media(world.id) == [first_media, second_media]
    assert await media_store.remove_cover_image(location.id) is True
    assert await media_store.get_cover_image(location.id) is None

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $world_id})-[cover:HAS_COVER]->(:Media)
        OPTIONAL MATCH (:World {id: $world_id})-[media:HAS_MEDIA]->(:Media)
        RETURN count(DISTINCT cover) AS cover_count, count(DISTINCT media) AS media_count
        """,
        parameters_={"world_id": world.id},
    )

    assert result.records[0]["cover_count"] == 1
    assert result.records[0]["media_count"] == 2
    assert await media_store.get_media(str(uuid4())) is None
    assert await media_store.set_cover_image(str(uuid4()), first_media.id) is None
    assert await media_store.set_cover_image(world.id, str(uuid4())) is None
    assert await media_store.get_cover_image(str(uuid4())) is None


async def test_add_and_remove_generic_media_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    media_store = MediaStore(clean_neo4j)
    media = MediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title="Scene image",
        hash="d" * 64,
        filename="scene",
    )

    await media_store.create_media(media)
    assert await media_store.add_media(world.id, media.id) == media
    assert await media_store.add_media(world.id, media.id) == media
    assert await media_store.list_source_media(world.id) == [media]
    assert await media_store.remove_media(world.id, media.id) is True
    assert await media_store.list_source_media(world.id) == []

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $world_id})-[media:HAS_MEDIA]->(:Media {id: $media_id})
        RETURN count(media) AS media_count
        """,
        parameters_={
            "world_id": world.id,
            "media_id": media.id,
        },
    )

    assert result.records[0]["media_count"] == 0


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


async def test_copy_prompt_media_relationships_reuses_world_prompt_media(clean_neo4j):
    world = await create_world(clean_neo4j)
    media_store = MediaStore(clean_neo4j)
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
    prompt_media = PromptMediaFile(
        id=str(uuid4()),
        title="Narrator prompt",
        hash="c" * 64,
        filename="narrator",
        prompt_name="narrator",
        language=world.language,
        component=ComponentType.NARRATOR,
    )

    await media_store.create_media(prompt_media)
    assert await media_store.set_prompt_media(world.id, prompt_media.id) == (prompt_media, None)
    assert await media_store.copy_prompt_media_relationships(world.id, simulation.id) == [prompt_media]
    assert await media_store.copy_prompt_media_relationships(world.id, simulation.id) == [prompt_media]
    assert await media_store.list_prompt_media(simulation_id=simulation.id) == [prompt_media]

    result = await clean_neo4j.execute_query(
        """
        MATCH (media:Media {id: $media_id})
        OPTIONAL MATCH (:Simulation {id: $simulation_id})-[prompt:USE_PROMPT]->(media)
        RETURN count(DISTINCT media) AS media_count, count(prompt) AS prompt_count
        """,
        parameters_={
            "media_id": prompt_media.id,
            "simulation_id": simulation.id,
        },
    )

    assert result.records[0]["media_count"] == 1
    assert result.records[0]["prompt_count"] == 1
