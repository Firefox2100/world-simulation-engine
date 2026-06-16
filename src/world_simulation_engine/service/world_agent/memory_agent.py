from typing import cast

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task, \
    Faction, FactionRelationship, MemoryAgentProfile, BriefingOutput, PendingGeneratedProposal, DirectorOutput, \
    SummaryOutput, TurnRecord
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
            director_output: DirectorOutput,
            factions: list[Faction] | None = None,
            faction_relationships: list[FactionRelationship] | None = None,
            pending_generated_proposals: list[PendingGeneratedProposal] | None = None,
            user_input: str | None = None,
            last_narration: str | None = None,
            previous_resolver_notes: str | None = None,
    ) -> BriefingOutput:
        data = {
            "simulation": simulation,
            "state": state,
            "location": current_location,
            "characters": characters,
            "tasks": tasks,
            "world_entries": world_entries,
            "director_output": director_output,
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

        return cast(
            BriefingOutput,
            await self._invoke_structured_with_repair(
                output_model=BriefingOutput,
                messages=messages,
                repair_instruction=(
                    "You must return a valid BriefingOutput."
                ),
                run_name="memory_briefing",
                max_attempts=2,
            ),
        )

    async def build_summary(self,
                            last_turns: list[TurnRecord],
                            state: SimulationState,
                            narration: str,
                            ) -> SummaryOutput:
        data = {
            "narration": narration,
            "last_turns_narrations": [f"Turn: {t.turn_number} {t.narration}" for t in last_turns],
            "previous_short_term_memory": state.recent_history_summary,
            "previous_long_term_memory": state.long_term_history_summary,
        }

        messages = self._compose_messages(
            prompts=self.profile.summary_prompt,
            data=data,
        )

        return cast(
            SummaryOutput,
            await self._invoke_structured_with_repair(
                output_model=SummaryOutput,
                messages=messages,
                repair_instruction=(
                    "You must return a valid SummaryOutput."
                ),
                run_name="memory_summary",
                max_attempts=2,
            )
        )
