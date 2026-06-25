from typing import cast

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, ResolverOutput, \
    NarratorResolutionView, WaitForUserNarrationContext, WorldEntry, PendingGeneratedProposal, \
    NarratorAgentProfile, UserInputFailureNarrationContext
from .world_agent import WorldAgent


class NarratorAgent(WorldAgent[NarratorAgentProfile]):
    async def narrate_resolved_turn(
            self,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            characters: list[Character],
            narrator_resolution_view: NarratorResolutionView,
            user_input: str | None = None,
            player_character: Character | None = None,
            last_narration: str | None = None,
            recent_history_summary: str | None = None,
            long_term_history_summary: str | None = None,
            world_entries_for_narrator: list[WorldEntry] | None = None,
            pending_generated_proposals: list[PendingGeneratedProposal] | None = None,
    ) -> str:
        data = {
            "simulation": simulation,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "player_character": player_character,
            "narrator_resolution_view": narrator_resolution_view,
            "user_input": user_input,
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
            config={"run_name": "narrate_resolved_turn"},
        )

        return cast(str, result.content).strip()

    async def narrate_user_input_failure(self,
                                         context: UserInputFailureNarrationContext,
                                         ) -> str:
        data = {
            "context": context.model_dump(),
        }

        messages = self._compose_messages(
            prompts=self.profile.narrate_user_input_failure_prompt,
            data=data,
        )

        result = await self.model.ainvoke(
            messages,
            config={"run_name": "narrate_user_input_failure"},
        )

        return cast(str, result.content).strip()

    async def narrate_wait_for_user(
        self,
        *,
        context: WaitForUserNarrationContext,
    ) -> str:
        data = {
            "context": context.model_dump(),
        }

        messages = self._compose_messages(
            prompts=self.profile.narrate_wait_for_user_prompt,
            data=data,
        )

        result = await self.model.ainvoke(
            messages,
            config={"run_name": "narrate_wait_for_user"},
        )

        return cast(str, result.content).strip()
