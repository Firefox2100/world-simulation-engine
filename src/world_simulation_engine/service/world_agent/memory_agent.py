from typing import Any, cast
from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task, \
    Faction, FactionRelationship, MemoryAgentProfile, BriefingOutput, PendingGeneratedProposal
from .world_agent import WorldAgent


class MemoryAgent(WorldAgent[MemoryAgentProfile]):
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
        tasks: list[Task],
        world_entries: list[WorldEntry],
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
        pending_generated_proposals: list[PendingGeneratedProposal] | None = None,
        user_input: str | None = None,
        last_narration: str | None = None,
        previous_resolver_notes: str | None = None,
    ) -> BriefingOutput:
        LOGGER.info("Generating briefings for turn %s of simulation %s", state.turn_number + 1, simulation.id)

        data = {
            "simulation": simulation,
            "data_preset": simulation.data_preset,
            "state": state,
            "location": current_location,
            "characters": characters,
            "tasks": tasks,
            "world_entries": world_entries,
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
            "pending_generated_proposals": pending_generated_proposals or [],
            "user_input": user_input,
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }
        LOGGER.debug("Base data:\n%s", TypeAdapter(dict[str, Any]).dump_json(data, indent=2).decode())

        messages = self._compose_messages(
            prompts=self.profile.briefing_prompt,
            data=data,
        )
        LOGGER.debug("Messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        structured_model = self.model.with_structured_output(BriefingOutput)
        return cast(BriefingOutput, await structured_model.ainvoke(messages))
