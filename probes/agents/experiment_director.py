"""
Experiment file to assist in designing the director agent.
"""

import os
import asyncio

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model import LlmConnectionProfile, OllamaAgentProfile, EmbeddingProfile, WorldEntry, \
    Task
from world_simulation_engine.service import DirectorAgent, EmbeddingService
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks

OLLAMA_URL = os.getenv("EXP_OLLAMA_URL")
OLLAMA_MODEL = os.getenv("EXP_OLLAMA_MODEL")
OLLAMA_MODEL_EMBED = os.getenv("EXP_OLLAMA_MODEL_EMBED")


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


async def experiment_director_agent(agent: DirectorAgent,
                                    embedding_service: EmbeddingService,
                                    ):
    user_input = ""

    filtered_entries = filter_world_entries(example_world_entries)
    recaller = WorldEntryRecaller(
        embedding_service=embedding_service,
    )
    recalled_entries = await recaller.recall(
        query=user_input,
        entries=filtered_entries,
        language=example_simulation.language,
    )
    filtered_tasks = filter_tasks(example_tasks)
    present_characters = [
        c for c in example_characters if c.location == example_simulation_state.scene
    ]


def main():
    director_agent = DirectorAgent(
        profile=OllamaAgentProfile(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
            temperature=0.4,
            context_window=65536,
            prompts=[],
        ),
    )

    embedding_service = EmbeddingService(
        profile=EmbeddingProfile(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL_EMBED,
            dimensions=1024,
        ),
    )

    asyncio.run(experiment_director_agent(
        agent=director_agent,
        embedding_service=embedding_service,
    ))
