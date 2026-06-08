"""
Experiment file to assist in designing the world generator agent.
"""

import asyncio
import json

from world_simulation_engine.service.world_agent.world_generator_agent import WorldGeneratorAgent

from agent_configuration import world_generator_agent


async def generate_location(agent: WorldGeneratorAgent):
    context = """
Setting: Blackwater Ridge, 1912.

Director Harlan disappeared three weeks ago.

The old mine is connected to the mystery.

The player is exploring the abandoned mine.

Known facts:
- A hidden tunnel may exist.
- Nobody has yet discovered the underground chamber.
- The mystery must not be solved.
"""
    trigger = """
Arthur Moore clears debris from a partially collapsed passage inside the old mine.
A previously unknown area becomes accessible.
"""
    constraints = [
        "Generate a location inside the old mine.",
        "It should provide clues but not answers.",
        "It must feel consistent with a 1912 mining operation.",
        "Do not reveal Harlan's fate.",
    ]

    location = await agent.generate_location(
        context=context,
        trigger=trigger,
        constraints=constraints,
    )

    print("Location generation result:")
    print(json.dumps(location.model_dump(), indent=2))


async def generate_item(agent: WorldGeneratorAgent):
    context = """
Arthur is searching Director Harlan's office.

Current clues:
- Missing notebook
- Altered property records
- Unknown visitor

Arthur searches a locked drawer.
"""
    trigger = """
A hidden compartment is discovered.
"""
    constraints = [
        "Generate a clue item.",
        "The clue should deepen the mystery.",
        "The clue must not reveal the culprit.",
        "The clue should connect to an existing mystery thread.",
    ]

    item = await agent.generate_item(
        context=context,
        trigger=trigger,
        constraints=constraints,
    )

    print("Item generation result:")
    print(json.dumps(item.model_dump(), indent=2))


async def generate_world_entry(agent: WorldGeneratorAgent):
    context = """
The player has interviewed several townspeople.

Nobody knows what happened to Harlan.

Rumours are common.
"""
    trigger = """
A local resident mentions an old story about the mine.
"""
    constraints = [
        "Generate a world entry.",
        "This should be a rumour.",
        "Confidence should be below 0.8.",
        "Visibility should be suspected or perceived.",
    ]

    world_entry = await agent.generate_world_entry(
        context=context,
        trigger=trigger,
        constraints=constraints,
    )

    print("World entry generation result:")
    print(json.dumps(world_entry.model_dump(), indent=2))


async def generate_entity(agent: WorldGeneratorAgent):
    context = """
Location:
Town Hall Records Room

Existing entities:
- Property Record Shelves
- Survey Archive Cabinet

Arthur is searching for evidence.
"""
    trigger = """
Arthur discovers something hidden behind one shelf.
"""
    constraints = [
        "Generate a physical entity.",
        "The entity must fit the room.",
        "It should be interactable.",
        "It should provide a potential clue.",
    ]

    entity = await agent.generate_entity(
        context=context,
        trigger=trigger,
        constraints=constraints,
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
