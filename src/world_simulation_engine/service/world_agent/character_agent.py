from typing import cast
from langchain_core.runnables import RunnableConfig, patch_config

from world_simulation_engine.model import Location, Character, WorldEntry, Task, Item, Equipment, \
    Faction, FactionRelationship, DataPreset, CharacterAgentProfile, CharacterBriefing, PendingGeneratedProposal, \
    CharacterActionOutput, CharacterReactionContext
from .world_agent import WorldAgent


class CharacterAgent(WorldAgent[CharacterAgentProfile]):
    async def generate_action(self,
                              character: Character,
                              briefing: CharacterBriefing,
                              current_location: Location,
                              visible_characters: list[Character],
                              tasks: list[Task],
                              world_entries: list[WorldEntry],
                              inventory: list[Item],
                              equipments: list[Equipment],
                              factions: list[Faction],
                              faction_relationships: list[FactionRelationship],
                              proposals: list[PendingGeneratedProposal],
                              data_preset: DataPreset | None = None,
                              user_input: str | None = None,
                              last_narration: str | None = None,
                              previous_resolver_notes: str | None = None,
                              config: RunnableConfig | None = None,
                              ) -> CharacterActionOutput:
        data = {
            "character": character,
            "briefing": briefing,
            "current_location": current_location,
            "visible_characters": visible_characters,
            "tasks": tasks,
            "world_entries": world_entries,
            "inventory": inventory,
            "equipments": equipments,
            "factions": factions,
            "faction_relationships": faction_relationships,
            "data_preset": data_preset,
            "pending_generated_proposals": proposals,
            "user_input": user_input,
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }

        messages = self._compose_messages(
            prompts=self.profile.action_prompt,
            data=data,
        )

        structured_model = self.model.with_structured_output(CharacterActionOutput)

        return cast(
            CharacterActionOutput,
            await structured_model.ainvoke(
                messages,
                config=patch_config(
                    config,
                    run_name="character_acting",
                ) if config else None,
            ),
        )

    async def generate_reaction(
            self,
            character: Character,
            reaction_context: CharacterReactionContext,
            current_location: Location,
            visible_characters: list[Character],
            tasks: list[Task],
            world_entries: list[WorldEntry],
            inventory: list[Item],
            equipments: list[Equipment],
            factions: list[Faction],
            faction_relationships: list[FactionRelationship],
            proposals: list[PendingGeneratedProposal],
            data_preset: DataPreset | None = None,
            user_input: str | None = None,
            last_narration: str | None = None,
            previous_resolver_notes: str | None = None,
            config: RunnableConfig | None = None,
    ) -> CharacterActionOutput:
        data = {
            "character": character,
            "reaction_context": reaction_context,
            "current_location": current_location,
            "visible_characters": visible_characters,
            "tasks": tasks,
            "world_entries": world_entries,
            "inventory": inventory,
            "equipments": equipments,
            "factions": factions,
            "faction_relationships": faction_relationships,
            "data_preset": data_preset,
            "pending_generated_proposals": proposals,
            "user_input": user_input,
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }

        messages = self._compose_messages(
            prompts=self.profile.reaction_prompt,
            data=data,
        )

        structured_model = self.model.with_structured_output(CharacterActionOutput)

        return cast(
            CharacterActionOutput,
            await structured_model.ainvoke(
                messages,
                config=patch_config(
                    config,
                    run_name="character_reaction",
                ) if config else None,
            ),
        )
