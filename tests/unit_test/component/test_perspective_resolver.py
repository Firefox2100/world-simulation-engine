from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.simulator.perspective_resolver import PerspectiveResolver
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Character, CurrentActivity, Location, Simulation, World


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
        version=1,
        language=SupportedLanguage.ENGLISH,
    )


def make_simulation() -> Simulation:
    return Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def make_character() -> Character:
    return Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="A character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )


async def test_resolve_graph_omits_callbacks_when_langfuse_handler_is_none():
    world = make_world()
    simulation = make_simulation()
    observer = make_character()
    location = Location(id="location_1", name="Room", description="A room")
    resolver = PerspectiveResolver(database=Mock(), langfuse_handler=None)
    resolver._resolve_graph = Mock()
    resolver._resolve_graph.ainvoke = AsyncMock(
        return_value={
            "world": world.model_dump(),
            "simulation": simulation.model_dump(),
            "observer": observer.model_dump(),
            "location": location.model_dump(),
            "perceived_characters": [],
            "perceived_background_characters": [],
            "perceived_items": [],
            "perceived_equipment": [],
            "perceived_containers": [],
            "perceived_landmarks": [],
        }
    )

    await resolver._resolve_perceived_entity_in_graph(
        world=world,
        simulation=simulation,
        observer=observer,
        location=location,
    )

    config = resolver._resolve_graph.ainvoke.await_args.kwargs["config"]
    assert config["callbacks"] is None
