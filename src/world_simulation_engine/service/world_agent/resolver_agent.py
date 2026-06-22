from typing import cast

from world_simulation_engine.model import Location, Character, WorldEntry, Simulation, SimulationState, \
    CharacterInventory, Faction, FactionRelationship, ResolverAgentProfile, CharacterActionOutput, \
    PendingGeneratedProposal, ResolverOutput, UserInputResolutionOutput, UserInputResolverContext
from .world_agent import WorldAgent


class ResolverAgent(WorldAgent[ResolverAgentProfile]):
    def _normalise_user_input_resolution(self,
                                         output: UserInputResolutionOutput,
                                         ) -> UserInputResolutionOutput:
        if output.accepted:
            output.rejection_reason = None
            output.user_retry_instruction = None

        if not output.accepted:
            output.resolved_actions = []
            output.requires_director_rerun = False
            output.director_rerun_reason = None

        for action in output.resolved_actions:
            if action.final_status in {"failed", "blocked", "invalid", "cancelled"}:
                if not action.failure_reason:
                    action.failure_reason = "The user-authored action could not be completed as stated."

        return output

    async def resolve_character_actions(
            self,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            characters: list[Character],
            character_actions: list[CharacterActionOutput],
            proposals: list[PendingGeneratedProposal],
            inventory: dict[int, CharacterInventory],
            world_entries: list[WorldEntry],
            actor_knowledge_index: dict[int, list[int]],
            action_validation_reports: list[dict],
            factions: list[Faction] | None = None,
            faction_relationships: list[FactionRelationship] | None = None,
            last_narration: str | None = None,
            previous_resolver_notes: str | None = None,
    ) -> ResolverOutput:
        data = {
            "simulation": simulation,
            "data_preset": simulation.data_preset,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "character_actions": character_actions,
            "pending_generated_proposals": proposals,
            "inventory": inventory,
            "world_entries": world_entries,
            "actor_knowledge_index": actor_knowledge_index,
            "action_validation_reports": action_validation_reports,
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
            "round_constraints": {
                "priority_order": [
                    {
                        "character_id": action.character_id,
                        "character_name": action.character_name,
                        "urgency": action.urgency,
                        "persistence": action.persistence,
                    }
                    for action in sorted(character_actions, key=lambda a: a.urgency, reverse=True)
                ],
            },
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }

        messages = self._compose_messages(
            prompts=self.profile.resolve_character_prompt,
            data=data,
        )

        structured_model = self.model.with_structured_output(ResolverOutput)

        return cast(
            ResolverOutput,
            await structured_model.ainvoke(
                messages,
                config={"run_name": "resolve_character_action"},
            ),
        )

    async def resolve_character_reactions(
            self,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            characters: list[Character],
            character_reactions: list[CharacterActionOutput],
            previous_resolver_output: ResolverOutput,
            proposals: list[PendingGeneratedProposal],
            inventory: dict[int, CharacterInventory],
            world_entries: list[WorldEntry],
            actor_knowledge_index: dict[int, list[int]],
            action_validation_reports: list[dict],
            factions: list[Faction] | None = None,
            faction_relationships: list[FactionRelationship] | None = None,
            last_narration: str | None = None,
            previous_resolver_notes: str | None = None,
    ) -> ResolverOutput:
        data = {
            "simulation": simulation,
            "data_preset": simulation.data_preset,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "reaction_actions": character_reactions,
            "previous_resolver_output": previous_resolver_output,
            "pending_generated_proposals": proposals,
            "inventory": inventory,
            "world_entries": world_entries,
            "actor_knowledge_index": actor_knowledge_index,
            "action_validation_reports": action_validation_reports,
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
            "round_constraints": {
                "second_pass": True,
                "retrying_character_ids": [action.character_id for action in character_reactions],
                "no_more_retries_after_this": True,
            },
        }

        messages = self._compose_messages(
            prompts=self.profile.resolve_reaction_prompt,
            data=data,
        )

        structured_model = self.model.with_structured_output(ResolverOutput)

        return cast(
            ResolverOutput,
            await structured_model.ainvoke(
                messages,
                config={"run_name": "resolve_reaction"},
            ),
        )

    async def resolve_user_input(self,
                                 context: UserInputResolverContext,
                                 ) -> UserInputResolutionOutput:
        data = {
            "context": context.model_dump(),
        }

        messages = self._compose_messages(
            prompts=self.profile.resolve_user_prompt,
            data=data,
        )

        output = cast(
            UserInputResolutionOutput,
            await self._invoke_structured_with_repair(
                output_model=UserInputResolutionOutput,
                messages=messages,
                repair_instruction=(
                    "Return a valid UserInputResolutionOutput. "
                    "If the user input is legal or merely ordinary dialogue, set accepted=true. "
                    "If it is impossible, conflicting, or too ambiguous to resolve, set accepted=false "
                    "with rejection_reason and user_retry_instruction."
                ),
                run_name="user_input_resolver",
                max_attempts=2,
            ),
        )

        return self._normalise_user_input_resolution(output)
