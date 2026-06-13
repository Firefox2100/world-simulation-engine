from typing import Any, cast
from pydantic import TypeAdapter
from langchain_core.runnables import RunnableConfig, patch_config

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task, \
    Faction, FactionRelationship, MemoryAgentProfile, BriefingOutput, PendingGeneratedProposal
from .world_agent import WorldAgent


class MemoryAgent(WorldAgent[MemoryAgentProfile]):
    """
    Builds safe per-character briefings after Director activation.
    Input should already be filtered to public/character-safe data.
    """

    async def build_briefings(self,
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
                              config: RunnableConfig | None = None,
                              ) -> BriefingOutput:
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

        messages = self._compose_messages(
            prompts=self.profile.briefing_prompt,
            data=data,
        )

        structured_model = self.model.with_structured_output(BriefingOutput)
        return cast(
            BriefingOutput,
            await structured_model.ainvoke(
                messages,
                config=patch_config(
                    config,
                    run_name="memory_briefing",
                ) if config else None,
            ))
