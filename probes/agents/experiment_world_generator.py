"""
Experiment file to assist in designing the world generator agent.
"""

import os
import asyncio
import json

from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model import LlmConnectionProfile, OllamaAgentProfile, PromptMessage
from world_simulation_engine.service.world_agent.world_generator_agent import WorldGeneratorAgent


OLLAMA_URL = os.getenv("EXP_OLLAMA_URL")
OLLAMA_MODEL = os.getenv("EXP_OLLAMA_MODEL")


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
    world_generator = WorldGeneratorAgent(
        profile=OllamaAgentProfile(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
            temperature=0.4,
            context_window=65536,
            prompts=[
                PromptMessage(
                    role=MessageRole.SYSTEM,
                    content="""
You are a world generation tool for a role-play simulation.

You create proposed world content only. You do not commit canonical state.

You may generate:
- locations
- entities
- items
- world entries
- minor characters
- environmental discoveries

Rules:
- Generated content must fit the existing world tone, time period, location, and mystery structure.
- Do not solve major mysteries unless explicitly requested.
- Do not contradict supplied canonical facts.
- If generating clues, prefer partial, ambiguous, or actionable clues.
- Use temporary IDs only.
- Mark generated content as pending/proposed.
- Include a commit_policy for resolver handling.
- Do not narrate.
- Do not decide whether the player or NPC succeeded.
- Do not expose hidden GM-only truth unless the request explicitly allows GM-side generation.
"""
                ),
                PromptMessage(
                    role=MessageRole.USER,
                    content="""
Context:
{{ data["context"] }}

Trigger:
{{ data["trigger"] }}

Constraints:
{{ data["constraints"] }}
"""
                )
            ],
        ),
    )

    asyncio.run(experiment_world_generator(world_generator))


if __name__ == "__main__":
    main()
