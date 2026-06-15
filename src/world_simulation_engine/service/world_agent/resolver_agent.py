from typing import cast

from world_simulation_engine.model import Location, Character, WorldEntry, Simulation, SimulationState, \
    CharacterInventory, Faction, FactionRelationship, ResolverAgentProfile, CharacterActionOutput, \
    PendingGeneratedProposal, ResolverOutput
from .world_agent import WorldAgent


class ResolverAgent(WorldAgent[ResolverAgentProfile]):
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

    async def resolve_user_input(self):
        data = {
            "simulation": Simulation,
            "state": SimulationState,
            "current_location": Location,
            "player_character": Character,
            "present_characters": list[Character],
            "visible_entities": list[Entity],
            "player_inventory": dict,
            "player_tasks": list[Task],
            "player_world_entries": list[WorldEntry],
            "user_input": str,
            "last_narration": str | None,
            "recent_history_summary": str | None,
            "previous_resolver_notes": str | None,
            "strictness": Literal["permissive", "normal", "strict"],
        }
