"""
Experiment file to assist in designing the director agent.
"""

import asyncio
import json

from world_simulation_engine.model import WorldEntry, Task
from world_simulation_engine.service import DirectorAgent, WorldGeneratorAgent, EmbeddingService
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks, example_locations, example_inventory
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
    existing_items = []
    for _, inventory in example_inventory.items():
        existing_items.extend(inventory["items"])
    generator_tools = generator.get_tools(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=example_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        entity_types=example_simulation.data_preset.entity_types.keys(),
    )

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

    print("Testing direct generation with history")
    result = await director.plan_turn(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        present_characters=present_characters,
        relevant_tasks=filtered_tasks,
        recalled_world_entries=recalled_entries,
        generation_tools=generator_tools,
        last_narration="The Iron Stag Inn hummed with festival noise, glasses clinking beneath the low beams "
                       "while rain tapped against the windows. Clara moved behind the bar with practiced "
                       "cheer, but her eyes returned to Arthur more often than chance required. Eleanor "
                       "Graves had just left the doorway after offering a polished welcome, and several "
                       "locals pretended not to listen.",
        recent_history_summary="Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara "
                               "noticed his controlled manner and suspected he was not merely a curious "
                               "traveller. Eleanor briefly greeted Arthur, presenting the town as orderly "
                               "and festive while probing his purpose. Arthur has not yet revealed the "
                               "anonymous letter.",
        long_term_history_summary="Director Harlan disappeared three weeks ago. Officially he left without "
                                  "notice, but many residents doubt this. The observatory, the old mine, "
                                  "altered property records, the unknown visitor, and Harlan's missing "
                                  "notebook are all unresolved investigation threads.",
        previous_resolver_notes="No active conflict remained from the previous round. Eleanor successfully "
                                "withdrew from the immediate conversation without revealing concern. Clara "
                                "is available at the bar and is socially positioned to answer or redirect "
                                "Arthur's questions.",
    )
    print(json.dumps(result.model_dump(), indent=2))

    print("Testing generating items/entities")
    user_input = ("Arthur asks Clara for permission to inspect the Visitor's Room Ledger, then looks closely "
                  "at the Room 7 entry and the pages around it.")
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
        last_narration="Clara set a glass down in front of a farmer without looking away from Arthur for "
                       "more than a heartbeat. The ledger remained behind the bar, half-hidden beneath a "
                       "folded cloth, its worn leather cover darkened by years of spilled ale and damp hands.",
        recent_history_summary="Arthur has established a cautious rapport with Clara. Clara is curious about "
                               "his investigation and may cooperate if she believes the truth will surface. "
                               "The Room 7 ledger entry is suspected to contain a false name linked to the "
                               "unknown visitor.",
        long_term_history_summary="An unknown visitor stayed in Room 7 shortly before Harlan disappeared. "
                                  "Clara remembers enough about the visitor to be uneasy, but the visitor's "
                                  "true identity is unknown.",
        previous_resolver_notes="Arthur is close enough to request access to the ledger. Clara has not yet "
                                "decided whether to help openly, help indirectly, or protect her own information.",
    )
    print(json.dumps(result.model_dump(), indent=2))

    print("Testing wait for user")
    user_input = "Arthur says nothing for the moment and watches the room."
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
        last_narration="The bar continued around Arthur as though nothing had changed, but several conversations "
                       "had grown slightly quieter. Clara polished the same glass twice. Near the hearth, a pair "
                       "of miners argued under their breath about the observatory road.",
        recent_history_summary="Arthur has just arrived and has not committed to a line of questioning. Clara is "
                               "attentive but not yet directly engaged. Eleanor is no longer immediately "
                               "pressing him.",
        long_term_history_summary="The investigation is still at its opening stage. Arthur has possible leads: "
                                  "Clara, Room 7, the observatory, the old mine, and the mayor's office.",
        previous_resolver_notes="No NPC has a forced immediate action. Clara may observe Arthur, but there is no "
                                "urgent need to interrupt unless her curiosity overrides caution.",
    )
    print(json.dumps(result.model_dump(), indent=2))

    print("Testing generating location")
    user_input = "Arthur leaves the bar and asks Clara to show him Room 7."
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
        last_narration="The mention of Room 7 left a small silence between them, brief enough that only Arthur "
                       "might have noticed it. Clara's hand rested near the ledger, her expression still "
                       "friendly, though the friendliness had become deliberate.",
        recent_history_summary="Arthur questioned Clara about the unknown visitor. Clara did not deny that Room "
                               "7 mattered. The ledger suggests the visitor used a false name and paid in cash.",
        long_term_history_summary="Room 7 was occupied by an unknown visitor shortly before Harlan disappeared. "
                                  "The visitor may have met Harlan secretly before the disappearance.",
        previous_resolver_notes="If Clara agrees, the scene may move from the bar to Room 7. Existing canonical "
                                "location ID 4 already describes Room 7, so generation should not be necessary "
                                "unless the Director wants a newly discovered entity inside the room.",
    )
    print(json.dumps(result.model_dump(), indent=2))

    print("Testing continues generation")
    user_input = ""
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
        last_narration="Arthur stood at the bar with the ledger question hanging between him and Clara. Outside, "
                       "the festival drums continued despite the rain, their rhythm faint beneath the inn's roof.",
        recent_history_summary="Arthur has started probing the Room 7 lead. Clara is conflicted between "
                               "curiosity, caution, and her control over inn gossip. Eleanor may become concerned "
                               "if Arthur gains momentum too quickly.",
        long_term_history_summary="The town is trying to preserve the appearance of normal festival order despite "
                                  "Harlan's disappearance. Several factions have reason to monitor Arthur's "
                                  "investigation.",
        previous_resolver_notes="The scene risks stalling unless Clara responds, another NPC intervenes, or an "
                                "external disturbance changes the pressure in the room.",
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
