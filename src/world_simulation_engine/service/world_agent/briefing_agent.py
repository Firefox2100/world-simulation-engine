from typing import Any
from langchain.messages import HumanMessage

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task
from .world_agent import WorldAgent
from .models import BriefingOutput


class BriefingAgent(WorldAgent):
    """
    Builds safe per-character briefings after Director activation.
    Input should already be filtered to public/character-safe data.
    """

    async def build_briefings(
        self,
        simulation: Simulation,
        state: SimulationState,
        current_location: Location,
        characters: list[Character],
        character_ids: list[int],
        tasks: list[Task],
        world_entries: list[WorldEntry],
        pending_generated_proposals: list[dict[str, Any]] | None = None,
        user_input: str | None = None,
        last_narration: str | None = None,
        recent_history_summary: str | None = None,
        long_term_history_summary: str | None = None,
        previous_resolver_notes: str | None = None,
    ) -> BriefingOutput:
        data = {
            "simulation": simulation,
            "state": state,
            "location": current_location,
            "characters": characters,
            "character_ids": character_ids,
            "tasks": tasks,
            "world_entries": world_entries,
            "pending_generated_proposals": pending_generated_proposals or [],
            "user_input": user_input,
            "last_narration": last_narration,
            "recent_history_summary": recent_history_summary,
            "long_term_history_summary": long_term_history_summary,
            "previous_resolver_notes": previous_resolver_notes,
        }

        messages = self._compose_messages(data=data)

        messages.append(
            HumanMessage(
                content="""
Produce the final BriefingOutput.

Rules:
- Build one briefing per requested active character where possible.
- Use only supplied safe context.
- Do not invent private knowledge.
- Do not write exact dialogue.
- Return only valid structured output.
"""
            )
        )

        structured_model = self.model.with_structured_output(BriefingOutput)
        return await structured_model.ainvoke(messages)
