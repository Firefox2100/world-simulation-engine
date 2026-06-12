from uuid import uuid4
from langgraph.graph.state import CompiledStateGraph
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
import pytest

from world_simulation_engine.component import TurnGenerator, TurnGeneratorState


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                mock_simulation_state_1,
                mock_locations,
                mock_characters,
                mock_tasks,
                mock_world_entries,
                mock_items_0,
                mock_items_1,
                mock_items_2,
                mock_items_3,
                mock_items_4,
                mock_equipments_0,
                mock_equipments_1,
                mock_equipments_2,
                mock_equipments_3,
                mock_equipments_4,
                mock_factions,
                mock_faction_relationships,
                mock_llm_connection_create,
                ):
    await db.connection.llm.create(mock_llm_connection_create)
    await db.simulation.create(mock_simulation)
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    await db.state.create(mock_simulation_state_1)
    for character in mock_characters:
        await db.character.create(character=character, simulation_id=1)

    for task in mock_tasks:
        await db.task.create(task=task)
    for world_entry in mock_world_entries:
        await db.entry.create(world_entry=world_entry, simulation_id=1)
    for item in mock_items_0:
        await db.item.create(item=item, simulation_id=1)
    for item in mock_items_1:
        await db.item.create(item=item, simulation_id=1, character_id=1)
    for item in mock_items_2:
        await db.item.create(item=item, simulation_id=1, character_id=2)
    for item in mock_items_3:
        await db.item.create(item=item, simulation_id=1, character_id=3)
    for item in mock_items_4:
        await db.item.create(item=item, simulation_id=1, character_id=4)
    for equipment in mock_equipments_0:
        await db.equipment.create(equipment=equipment, simulation_id=1)
    for equipment in mock_equipments_1:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=1)
    for equipment in mock_equipments_2:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=2)
    for equipment in mock_equipments_3:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=3)
    for equipment in mock_equipments_4:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=4)

    for faction in mock_factions:
        await db.faction.create(faction=faction, simulation_id=1)
    for relationship in mock_faction_relationships:
        await db.faction_relationship.create(relationship=relationship)


async def test_compile_graph(db):
    turn_generator = TurnGenerator(db)

    graph = turn_generator.build_graph()

    assert isinstance(graph, CompiledStateGraph)


async def test_run_turn(db):
    turn_generator = TurnGenerator(db)

    graph = turn_generator.build_graph()
    langfuse = Langfuse()
    langfuse_handler = CallbackHandler()

    result = await graph.ainvoke(
        TurnGeneratorState(
            run_id="1",
            simulation_id=1,
            user_input="Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
                       "before Harlan vanished.",
        ),
        config={
            "callbacks": [langfuse_handler],
            "run_name": "turn_generator",
            "metadata": {
                "simulation_id": 1,
            },
            "configurable": {
                "thread_id": str(uuid4()),
            },
            "tags": ["turn-generator", "simulation"],
        },
    )

    result_obj = TurnGeneratorState.model_validate(result)
