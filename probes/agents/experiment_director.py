"""
Experiment file to assist in designing the director agent.
"""

import asyncio
import json

from world_simulation_engine.model import WorldEntry, Task
from world_simulation_engine.service import DirectorAgent, WorldGeneratorAgent, EmbeddingService
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks, example_locations
from agent_configuration import embedding_service, world_generator_agent, director_agent


def filter_world_entries(entries: list[WorldEntry]) -> list[WorldEntry]:
    """
    Filter the world entries for the director. This should be done with the database, but this is mocked
    :param entries: The entries to filter
    :return: Trimmed entries that are scoped to the director
    """
    selected = []
    present_character_ids = set([
        c.id for c in example_characters if c.location == example_simulation_state.scene
    ])

    for entry in entries:
        if 0 in entry.scope:
            selected.append(entry)
            continue

        if bool(set(entry.scope) & present_character_ids):
            selected.append(entry)
            continue

    return selected


def filter_tasks(tasks: list[Task]) -> list[Task]:
    """
    Filter the tasks for the director. This should be done with the database, but this is mocked
    :param tasks: The tasks to filter
    :return: Trimmed tasks that are scoped to the present character
    """
    selected = []
    present_character_ids = set([
        c.id for c in example_characters if c.location == example_simulation_state.scene
    ])

    for task in tasks:
        if bool(set(task.character_ids) & present_character_ids):
            selected.append(task)
            continue

    return selected


async def experiment_director_agent(director: DirectorAgent,
                                    generator: WorldGeneratorAgent,
                                    embedding_service: EmbeddingService,
                                    ):
    filtered_entries = filter_world_entries(example_world_entries)
    recaller = WorldEntryRecaller(
        embedding_service=embedding_service,
    )
    filtered_tasks = filter_tasks(example_tasks)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]
    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    generator_tools = generator.get_tools()

    print("Testing direct generation")
    user_input = "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied before Harlan vanished."
    recalled_entries = await recaller.recall(
        query=user_input,
        entries=filtered_entries,
        language=example_simulation.language,
    )
    result = await director.plan_turn(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        relevant_tasks=filtered_tasks,
        recalled_world_entries=recalled_entries,
        generation_tools=generator_tools,
    )
    print(json.dumps(result.model_dump(), indent=2))


def main():
    asyncio.run(experiment_director_agent(
        director=director_agent,
        generator=world_generator_agent,
        embedding_service=embedding_service,
    ))


if __name__ == "__main__":
    main()
