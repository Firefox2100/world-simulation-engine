from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.simulator.perspective_resolver import (
    CueCandidate,
    CuePerception,
    CuePerceptionResult,
    PerspectiveResolver,
    ResolvePerceivedCueState,
)
from world_simulation_engine.misc.enums import SupportedLanguage, Visibility
from world_simulation_engine.model import Character, CurrentActivity, Location, Simulation, World


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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


async def test_resolve_perceived_cues_rehydrates_description_and_consumes_delivered_ones():
    world = make_world()
    simulation = make_simulation()
    observer = make_character()
    location = Location(id="location_1", name="Room", description="A room")
    resolver = PerspectiveResolver(database=Mock(), langfuse_handler=None)
    resolver._prepare_prompt = AsyncMock(return_value=[])
    resolver._mark_trigger_activations_consumed = AsyncMock()
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(return_value=CuePerceptionResult(cues=[
        CuePerception(activation_id="activation_visible", visibility=Visibility.AUDIBLE),
        CuePerception(activation_id="activation_invisible", visibility=Visibility.INVISIBLE),
    ])))
    resolver._prepare_llm_service = AsyncMock(return_value=llm)

    result = await resolver._resolve_perceived_cues(ResolvePerceivedCueState(
        world=world, simulation=simulation, observer=observer, observer_location=location,
        cues=[
            CueCandidate(activation_id="activation_visible", description="A ring left on the table."),
            CueCandidate(activation_id="activation_invisible", description="A distant argument."),
        ],
    ))

    cues = result["perceived_cues"]
    assert len(cues) == 2
    visible = next(cue for cue in cues if cue.activation_id == "activation_visible")
    assert visible.description == "A ring left on the table."
    assert visible.visibility == Visibility.AUDIBLE
    # Only the activation actually delivered with real visibility gets marked consumed - the
    # invisible one must stay pending for a future attempt.
    resolver._mark_trigger_activations_consumed.assert_awaited_once_with(["activation_visible"])


async def test_resolve_perceived_cues_never_forwards_anything_but_the_candidate_description():
    """The only trigger-authored content in a PerceivedCueEffect that may reach this prompt is
    each candidate's own description - never a trigger id, name, or the rest of the effect."""
    world = make_world()
    simulation = make_simulation()
    observer = make_character()
    location = Location(id="location_1", name="Room", description="A room")
    resolver = PerspectiveResolver(database=Mock(), langfuse_handler=None)
    resolver._prepare_prompt = AsyncMock(return_value=[])
    resolver._mark_trigger_activations_consumed = AsyncMock()
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(return_value=CuePerceptionResult(cues=[])))
    resolver._prepare_llm_service = AsyncMock(return_value=llm)

    await resolver._resolve_perceived_cues(ResolvePerceivedCueState(
        world=world, simulation=simulation, observer=observer, observer_location=location,
        cues=[CueCandidate(activation_id="activation_1", description="A ring left on the table.")],
    ))

    call_data = llm.invoke_structured_with_repair.await_args.kwargs["data"]
    assert call_data["cues"] == [CueCandidate(activation_id="activation_1", description="A ring left on the table.")]
