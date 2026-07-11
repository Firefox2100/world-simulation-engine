import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType
from world_simulation_engine.model import Intent, Simulation
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.database.intent_store import IntentStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_character, create_world


class FakeEmbedService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


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
        desired_state=None,
        success_conditions=[],
        failure_conditions=[],
        maintenance_conditions=[],
        deadline=deadline,
        horizon=IntentHorizon.SHORT,
        constraints=[],
        current_plan=[],
        next_action_biases=[],
        blockers=[],
        open_threads=[],
    )


async def create_simulation(clean_neo4j, world_id: str, current_time: datetime) -> Simulation:
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=current_time,
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world_id)
    return simulation


async def test_recall_intents_includes_active_or_paused_pressing_intents(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await create_simulation(
        clean_neo4j,
        world.id,
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    character = await create_character(clean_neo4j, world.id, name="Alex")
    intent_store = IntentStore(clean_neo4j)
    near_deadline = make_intent(
        "Near deadline",
        deadline=simulation.current_time + timedelta(hours=2),
    )
    paused_high_urgency = make_intent(
        "Paused urgent",
        status=IntentStatus.PAUSED,
        urgency=0.8,
    )
    completed_high_priority = make_intent(
        "Completed priority",
        status=IntentStatus.COMPLETED,
        priority=0.9,
    )

    for intent in [near_deadline, paused_high_urgency, completed_high_priority]:
        await intent_store.create_intent(intent, character.id)

    simulator = CharacterSimulator(DatabaseService(clean_neo4j), langfuse_handler=None)

    recalled = await simulator._recall_intents(
        simulation=simulation,
        character=character,
        user_input="",
    )

    by_id = {
        entry.intent.id: entry
        for entry in recalled
    }
    assert set(by_id) == {near_deadline.id, paused_high_urgency.id}
    assert by_id[near_deadline.id].recall_sources == ["active_filter"]
    assert by_id[paused_high_urgency.id].recall_sources == ["active_filter"]


async def test_recall_intents_embedding_match_overrides_status(clean_neo4j, monkeypatch):
    world = await create_world(clean_neo4j)
    simulation = await create_simulation(
        clean_neo4j,
        world.id,
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    character = await create_character(clean_neo4j, world.id, name="Alex")
    intent_store = IntentStore(clean_neo4j)
    completed_match = make_intent(
        "Completed coffee",
        status=IntentStatus.COMPLETED,
        embedding=[1.0, 0.0],
    )
    active_match = make_intent(
        "Active coffee",
        urgency=0.8,
        embedding=[1.0, 0.0],
    )
    abandoned_weak_match = make_intent(
        "Abandoned errand",
        status=IntentStatus.ABANDONED,
        embedding=[0.4, 0.6],
    )
    completed_zero_match = make_intent(
        "Completed unrelated",
        status=IntentStatus.COMPLETED,
        embedding=[0.0, 1.0],
    )

    for intent in [completed_match, active_match, abandoned_weak_match, completed_zero_match]:
        await intent_store.create_intent(intent, character.id)

    simulator = CharacterSimulator(DatabaseService(clean_neo4j), langfuse_handler=None)

    async def fake_prepare_embed_service(simulation_id: str):
        return FakeEmbedService()

    monkeypatch.setattr(simulator, "_prepare_embed_service", fake_prepare_embed_service)

    recalled = await simulator._recall_intents(
        simulation=simulation,
        character=character,
        user_input="coffee",
    )

    by_id = {
        entry.intent.id: entry
        for entry in recalled
    }
    assert completed_match.id in by_id
    assert "embedding_match" in by_id[completed_match.id].recall_sources
    assert by_id[completed_match.id].similarity == 1.0
    assert by_id[active_match.id].recall_sources == ["active_filter", "embedding_match"]
    assert by_id[active_match.id].similarity == 1.0
    assert completed_zero_match.id not in by_id
