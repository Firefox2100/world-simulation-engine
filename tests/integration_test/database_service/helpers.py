from uuid import uuid4

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, Character, CurrentActivity, World
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.world_store import WorldStore


def make_author() -> Author:
    return Author(
        id=str(uuid4()),
        name="Test Author",
        url="https://example.com/authors/test",
    )


def make_world() -> World:
    return World(
        id=str(uuid4()),
        name="Test World",
        description="A test world",
        version=1,
        url="https://example.com/worlds/test",
        language=SupportedLanguage.ENGLISH,
    )


def make_character(name: str = "Test Character") -> Character:
    return Character(
        id=str(uuid4()),
        name=name,
        age=30,
        gender="non-binary",
        appearance="Simple clothes",
        description="A test character",
        public_state="Standing",
        private_state="Calm",
        current_activity=CurrentActivity(name="idle"),
    )


async def create_world(clean_neo4j) -> World:
    store = WorldStore(clean_neo4j)
    author = make_author()
    world = make_world()
    await store.create_author(author)
    await store.create_world(world, author.id)
    return world


async def create_character(clean_neo4j, source_id: str, name: str = "Test Character") -> Character:
    character = make_character(name)
    await CharacterStore(clean_neo4j).create_character(character, source_id)
    return character
