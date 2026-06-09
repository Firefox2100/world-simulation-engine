"""
Experiment file to assist in designing the world generator agent.
"""

import asyncio
import json

from world_simulation_engine.service.world_agent.world_generator_agent import WorldGeneratorAgent

from agent_configuration import world_generator_agent
from example_simulation import example_simulation, example_simulation_state, example_locations, \
    example_characters, example_inventory


async def generate_location(agent: WorldGeneratorAgent):
    goal = "Generate a location inside the old mine."
    trigger = ("Arthur Moore clears debris from a partially collapsed passage inside the old mine. A previously "
               "unknown area becomes accessible.")
    constraints = [
        "It should provide clues but not answers.",
        "It must feel consistent with a 1912 mining operation.",
        "Do not reveal Harlan's fate.",
    ]

    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]
    existing_items = []
    for _, inventory in example_inventory.items():
        existing_items.extend(inventory["items"])

    location = await agent.generate_location(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=example_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    print("Location generation result:")
    print(json.dumps(location.model_dump(), indent=2))


async def generate_item(agent: WorldGeneratorAgent):
    goal = "Generate an item in the hidden compartment of a wardrobe."
    trigger = "A hidden compartment is discovered."
    constraints = [
        "Generate a clue item.",
        "The clue should deepen the mystery.",
        "The clue must not reveal the culprit.",
        "The clue should connect to an existing mystery thread.",
    ]

    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]
    existing_items = []
    for _, inventory in example_inventory.items():
        existing_items.extend(inventory["items"])

    item = await agent.generate_item(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=example_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    print("Item generation result:")
    print(json.dumps(item.model_dump(), indent=2))


async def generate_world_entry(agent: WorldGeneratorAgent):
    goal = "Generate a world entry that introduces a new mystery about the old mine."
    trigger = "A local resident mentions an old story about the mine."
    constraints = [
        "Generate a world entry.",
        "This should be a rumour.",
        "Confidence should be below 0.8.",
        "Visibility should be suspected or perceived.",
    ]

    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]
    existing_items = []
    for _, inventory in example_inventory.items():
        existing_items.extend(inventory["items"])

    world_entry = await agent.generate_world_entry(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=example_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    print("World entry generation result:")
    print(json.dumps(world_entry.model_dump(), indent=2))


async def generate_entity(agent: WorldGeneratorAgent):
    goal = "Generate an entity inside the room, behind the shelf."
    trigger = "Arthur discovers something hidden behind one shelf."
    constraints = [
        "Generate a physical entity.",
        "The entity must fit the room.",
        "It should be interactable.",
        "It should provide a potential clue.",
    ]

    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]
    existing_items = []
    for _, inventory in example_inventory.items():
        existing_items.extend(inventory["items"])

    entity = await agent.generate_entity(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=example_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
        entity_types=example_simulation.data_preset.entity_types.keys(),
    )

    print("Entity generation result:")
    print(json.dumps(entity.model_dump(), indent=2))


async def experiment_world_generator(agent: WorldGeneratorAgent):
    await generate_location(agent)
    await generate_item(agent)
    await generate_world_entry(agent)
    await generate_entity(agent)


def main():
    asyncio.run(experiment_world_generator(world_generator_agent))


if __name__ == "__main__":
    main()
