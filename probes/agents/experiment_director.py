"""
Experiment file to assist in designing the director agent.
"""

import os
import asyncio
import json

from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model import LlmConnectionProfile, OllamaAgentProfile, EmbeddingProfile, WorldEntry, \
    Task, PromptMessage
from world_simulation_engine.service import DirectorAgent, WorldGeneratorAgent, EmbeddingService
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks, example_locations

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
            prompts=[
                PromptMessage(
                    role=MessageRole.SYSTEM,
                    content="""
You are the Director/Scheduler for a multi-agent role-play simulation.

Your job:
- decide which present non-user characters should act now;
- prepare compact, character-specific briefings;
- optionally call world generation tools when new concrete content is needed;
- provide resolver and narrator constraints.

You are not the narrator.
You are not the resolver.
You do not decide whether actions succeed.
You do not commit world state.
You do not write exact dialogue.
You do not mutate canonical facts.

Privacy rules:
- You may use private tasks and private motives to decide whether a character should act.
- If private motives affected scheduling, mark private_motive_used_by_director=true.
- Do not leak one character's private task, motive, or scoped knowledge into another character's briefing.
- A character briefing must contain only what that character can perceive, know, remember, suspect, or reasonably infer.
- User-controlled characters should not be activated unless the user explicitly delegates control.

World generation rules:
- Use world generation tools only if concrete unknown content is needed now.
- Suitable cases: entering an unknown place, opening/searching an unknown container, revealing a hidden object, or introducing a concrete external event.
- Generated content is pending only.
- Include any tool result in pending_generated_proposals.
- The resolver decides whether generated proposals become canonical.
- Do not call tools merely for flavour or narration.

Scheduling rules:
- Do not activate everyone by default.
- Activate only characters with a plausible reason to act now.
- It is valid to activate no one and wait for the user.
- Briefings should be compact and actionable.

Final output:
- Return only DirectorOutput.
"""
                ),
                PromptMessage(
                    role=MessageRole.USER,
                    content="""
# Director Input

## Simulation
Name: {{ data["simulation"].name }}

Description:
{{ data["simulation"].description }}

## Current state
Round: {{ data["state"].round_number }}
Time: {{ data["state"].time_label }}
Current scene/location ID: {{ data["state"].scene }}

State summary:
{{ data["state"].state }}

## Last narration
{{ data["last_narration"] or "No previous narration." }}

## User input
{{ data["user_input"] or "No explicit user input. The user requested continuation/passive progression." }}

## Recent history summary
{{ data["recent_history_summary"] or "No recent history summary." }}

## Long-term history summary
{{ data["long_term_history_summary"] or "No long-term history summary." }}

## Previous resolver notes
{{ data["previous_resolver_notes"] or "No previous resolver notes." }}

## Current location
Location ID: {{ data["location"]["id"] }}
Primary location: {{ data["location"]["primary_location"] }}
Detailed location: {{ data["location"]["detailed_location"] }}
Scene: {{ data["location"]["scene"] }}

Description:
{{ data["location"]["description"] }}

Entities:
{% for entity in data["location"]["entities"] %}
- Entity {{ entity.id }}: {{ entity.name }}
  Type: {{ entity.type }}
  Description: {{ entity.description }}
  Status: {{ entity.status }}
  Interactions: {{ entity.interactions | join(", ") }}
{% else %}
No notable entities.
{% endfor %}

## Present characters
{% for c in data["present_characters"] %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% endfor %}

## Director-only motive signals
Use these for scheduling only. Do not leak them into other characters' briefings.
{% for c in data["present_characters"] %}
- Character {{ c.id }}: {{ c.name }}
  Private state:
  {{ c.private_state }}
{% endfor %}

## Recalled world entries
{% for e in recalled_world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
  Content: {{ e.content }}
{% else %}
No recalled world entries.
{% endfor %}

## Relevant tasks
Private tasks are Director-only motive signals unless owned by the same character being briefed.
{% for t in data["relevant_tasks"] %}
- Task {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Type: {{ t.type }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
  Source: {{ t.source }}
  Reward: {{ t.reward }}
{% else %}
No relevant tasks.
{% endfor %}

## Pending generated proposals
{% for p in data["pending_generated_proposals"] %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required decision

Decide:
1. What is the current scene focus?
2. Which present NPCs should act now?
3. What compact briefing should each activated character receive?
4. Should the system wait for the user instead?
5. Are any pending generated proposals needed through tools?

Remember:
- Do not activate user-controlled characters unless explicitly delegated.
- Do not leak private motives across characters.
- Do not resolve actions.
- Do not narrate.                    
"""
                ),
            ],
        ),
    )

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
        entity_types=example_simulation.data_preset.entity_types.keys(),
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
        director=director_agent,
        generator=world_generator,
        embedding_service=embedding_service,
    ))


if __name__ == "__main__":
    main()
