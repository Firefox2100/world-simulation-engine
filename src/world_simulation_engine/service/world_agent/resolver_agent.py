from typing import Any, cast
from pydantic import TypeAdapter
from langchain_core.runnables import RunnableConfig, patch_config

from world_simulation_engine.model import Location, Character, WorldEntry, Simulation, SimulationState, \
    CharacterInventory, Faction, FactionRelationship, ResolverAgentProfile, CharacterActionOutput, \
    PendingGeneratedProposal, ResolverOutput
from .world_agent import WorldAgent


class ResolverAgent(WorldAgent[ResolverAgentProfile]):
    async def resolve_character_actions(self,
                                        simulation: Simulation,
                                        state: SimulationState,
                                        current_location: Location,
                                        characters: list[Character],
                                        character_actions: list[CharacterActionOutput],
                                        proposals: list[PendingGeneratedProposal],
                                        inventory: dict[int, CharacterInventory],
                                        world_entries: list[WorldEntry],
                                        factions: list[Faction] | None = None,
                                        faction_relationships: list[FactionRelationship] | None = None,
                                        last_narration: str | None = None,
                                        previous_resolver_notes: str | None = None,
                                        config: RunnableConfig | None = None,
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
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
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
                config=patch_config(
                    config,
                    run_name="resolve_character_action",
                ) if config else None,
            )
        )

    async def resolve_character_reactions(self,
                                          simulation: Simulation,
                                          state: SimulationState,
                                          current_location: Location,
                                          characters: list[Character],
                                          character_reactions: list[CharacterActionOutput],
                                          previous_resolver_output: ResolverOutput,
                                          proposals: list[PendingGeneratedProposal],
                                          inventory: dict[int, CharacterInventory],
                                          world_entries: list[WorldEntry],
                                          factions: list[Faction] | None = None,
                                          faction_relationships: list[FactionRelationship] | None = None,
                                          last_narration: str | None = None,
                                          previous_resolver_notes: str | None = None,
                                          config: RunnableConfig | None = None,
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
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
            "round_constraints": {
                "second_pass": True,
                "retrying_character_ids": [a.character_id for a in character_reactions],
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
                config=patch_config(
                    config,
                    run_name="resolve_reaction",
                ) if config else None,
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
