from typing import Any, cast
from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import LOGGER
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
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
        last_narration: str | None = None,
        previous_resolver_notes: str | None = None,
    ) -> ResolverOutput:
        LOGGER.info("Resolving character actions for turn %s", state.turn_number + 1)

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
        LOGGER.debug("Base data:\n%s", TypeAdapter(dict[str, Any]).dump_json(data, indent=2).decode())

        messages = self._compose_messages(
            prompts=self.profile.resolve_character_prompt,
            data=data,
        )
        LOGGER.debug("Messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        structured_model = self.model.with_structured_output(ResolverOutput)
        return cast(ResolverOutput, await structured_model.ainvoke(messages))

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
