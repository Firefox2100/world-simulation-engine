import pytest

from world_simulation_engine.model import ProposedLocation
from world_simulation_engine.service import WorldGeneratorAgent


@pytest.fixture
def world_generator_agent(mock_llm_connection,
                          mock_world_generator_profile,
                          ) -> WorldGeneratorAgent:
    return WorldGeneratorAgent(
        profile=mock_world_generator_profile,
        connection=mock_llm_connection,
    )


async def test_generate_location(world_generator_agent,
                                 mock_locations,
                                 mock_characters,
                                 mock_simulation,
                                 mock_simulation_state_1,
                                 mock_items_0,
                                 mock_items_1,
                                 mock_items_2,
                                 mock_items_3,
                                 mock_items_4,
                                 ):
    goal = "Generate a location inside the old mine."
    trigger = ("Arthur Moore clears debris from a partially collapsed passage inside the old mine. A previously "
               "unknown area becomes accessible.")
    constraints = [
        "It should provide clues but not answers.",
        "It must feel consistent with a 1912 mining operation.",
        "Do not reveal Harlan's fate.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    location = await world_generator_agent.generate_location(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    assert isinstance(location, ProposedLocation)


async def test_generate_item(world_generator_agent,
                             mock_locations,
                             mock_characters,
                             mock_simulation,
                             mock_simulation_state_1,
                             mock_items_0,
                             mock_items_1,
                             mock_items_2,
                             mock_items_3,
                             mock_items_4,
                             ):
    goal = "Generate an item in the hidden compartment of a wardrobe."
    trigger = "A hidden compartment is discovered."
    constraints = [
        "Generate a clue item.",
        "The clue should deepen the mystery.",
        "The clue must not reveal the culprit.",
        "The clue should connect to an existing mystery thread.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    item = await world_generator_agent.generate_item(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )


async def test_generate_world_entry(world_generator_agent,
                                    mock_locations,
                                    mock_characters,
                                    mock_simulation,
                                    mock_simulation_state_1,
                                    mock_items_0,
                                    mock_items_1,
                                    mock_items_2,
                                    mock_items_3,
                                    mock_items_4,
                                    ):
    goal = "Generate a world entry that introduces a new mystery about the old mine."
    trigger = "A local resident mentions an old story about the mine."
    constraints = [
        "Generate a world entry.",
        "This should be a rumour.",
        "Confidence should be below 0.8.",
        "Visibility should be suspected or perceived.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    world_entry = await world_generator_agent.generate_world_entry(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )


async def test_generate_entity(world_generator_agent,
                               mock_locations,
                               mock_characters,
                               mock_simulation,
                               mock_simulation_state_1,
                               mock_items_0,
                               mock_items_1,
                               mock_items_2,
                               mock_items_3,
                               mock_items_4,
                               ):
    goal = "Generate an entity inside the room, behind the shelf."
    trigger = "Arthur discovers something hidden behind one shelf."
    constraints = [
        "Generate a physical entity.",
        "The entity must fit the room.",
        "It should be interactable.",
        "It should provide a potential clue.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    entity = await world_generator_agent.generate_entity(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
        entity_types=mock_simulation.data_preset.entity_types.keys(),
    )
