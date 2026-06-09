import asyncio
import json

from world_simulation_engine.model import WorldEntry, Task
from world_simulation_engine.service import BriefingAgent
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks, example_locations
from agent_configuration import briefing_agent


async def experiment_briefing_agent(agent: BriefingAgent):
    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)

    result = await briefing_agent.build_briefings(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        characters=safe_characters_for_active_ids,
        character_ids=director_output.active_character_ids,
        tasks=safe_tasks_for_active_ids,
        world_entries=safe_world_entries_for_active_ids,
        pending_generated_proposals=[
            p.model_dump() for p in director_output.pending_generated_proposals
        ],
        user_input=user_input,
        last_narration=last_narration,
        recent_history_summary=recent_history_summary,
        long_term_history_summary=long_term_history_summary,
        previous_resolver_notes=previous_resolver_notes,
    )


def main():
    asyncio.run(experiment_briefing_agent(
        agent=briefing_agent,
    ))


if __name__ == "__main__":
    main()
