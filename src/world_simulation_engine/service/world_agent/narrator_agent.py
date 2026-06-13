from typing import cast
from langchain_core.runnables import RunnableConfig, patch_config

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, ResolverOutput, \
    CharacterActionOutput, DirectorOutput, WorldEntry, PendingGeneratedProposal, NarratorAgentProfile
from .world_agent import WorldAgent


class NarratorAgent(WorldAgent[NarratorAgentProfile]):
    async def narrate_resolved_turn(self,
                                    simulation: Simulation,
                                    state: SimulationState,
                                    current_location: Location,
                                    characters: list[Character],
                                    resolver_output: ResolverOutput,
                                    user_input: str | None = None,
                                    character_actions: list[CharacterActionOutput] | None = None,
                                    director_output: DirectorOutput | None = None,
                                    last_narration: str | None = None,
                                    recent_history_summary: str | None = None,
                                    long_term_history_summary: str | None = None,
                                    world_entries_for_narrator: list[WorldEntry] | None = None,
                                    pending_generated_proposals: list[PendingGeneratedProposal] | None = None,
                                    config: RunnableConfig | None = None,
                                    ) -> str:
        data = {
            "simulation": simulation,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "resolver_output": resolver_output,
            "user_input": user_input,
            "character_actions": character_actions or [],
            "director_output": director_output,
            "last_narration": last_narration,
            "recent_history_summary": recent_history_summary,
            "long_term_history_summary": long_term_history_summary,
            "world_entries_for_narrator": world_entries_for_narrator or [],
            "pending_generated_proposals": pending_generated_proposals or [],
        }

        messages = self._compose_messages(
            prompts=self.profile.narrate_resolved_turn_prompt,
            data=data,
        )

        result = await self.model.ainvoke(
            messages,
            config=patch_config(
                config,
                run_name="narrate_resolved_turn"
            ) if config else None,
        )

        return cast(str, result.content).strip()

    async def narrate_user_input_failure(self,
                                         simulation: Simulation,
                                         state: SimulationState,
                                         current_location: Location,
                                         player_character: Character,
                                         user_input: str,
                                         user_input_resolver_output: ResolverOutput,
                                         last_narration: str | None = None,
                                         recent_history_summary: str | None = None,
                                         long_term_history_summary: str | None = None,
                                         world_entries_for_narrator: list[WorldEntry] | None = None,
                                         config: RunnableConfig | None = None,
                                         ) -> str:
        data = {
            "simulation": simulation,
            "state": state,
            "current_location": current_location,
            "player_character": player_character,
            "user_input": user_input,
            "resolver_output": user_input_resolver_output,
            "last_narration": last_narration,
            "recent_history_summary": recent_history_summary,
            "long_term_history_summary": long_term_history_summary,
            "world_entries_for_narrator": world_entries_for_narrator or [],
        }

        messages = self._compose_messages(
            prompts=self.profile.narrate_user_input_failure_prompt,
            data=data,
        )

        result = await self.model.ainvoke(
            messages,
            config=patch_config(
                config,
                run_name="narrate_user_input_failure"
            ) if config else None,
        )

        return cast(str, result.content).strip()

    async def narrate_wait_for_user(self,
                                    simulation: Simulation,
                                    state: SimulationState,
                                    current_location: Location,
                                    characters: list[Character],
                                    director_output: DirectorOutput,
                                    user_input: str | None = None,
                                    last_narration: str | None = None,
                                    recent_history_summary: str | None = None,
                                    long_term_history_summary: str | None = None,
                                    world_entries_for_narrator: list[WorldEntry] | None = None,
                                    config: RunnableConfig | None = None,
                                    ) -> str:
        data = {
            "simulation": simulation,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "director_output": director_output,
            "user_input": user_input,
            "last_narration": last_narration,
            "recent_history_summary": recent_history_summary,
            "long_term_history_summary": long_term_history_summary,
            "world_entries_for_narrator": world_entries_for_narrator or [],
        }

        messages = self._compose_messages(
            prompts=self.profile.narrate_wait_for_user_prompt,
            data=data,
        )

        result = await self.model.ainvoke(
            messages,
            config=patch_config(
                config,
                run_name="narrate_wait_for_user"
            ) if config else None,
        )

        return cast(str, result.content).strip()
