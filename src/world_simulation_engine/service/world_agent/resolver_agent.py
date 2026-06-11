from typing import Any, cast
from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.model import Location, Character, WorldEntry, Simulation, SimulationState, Equipment, \
    ResolverAgentProfile, CharacterActionOutput, PendingGeneratedProposal, Entity
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
        visible_entities: list[Entity],
        inventory: dict[int, dict[str, list]],
        world_entries: list[WorldEntry],
        last_narration: str | None = None,
        previous_resolver_notes: str | None = None,
    ):
        data = {
            "simulation": simulation,
            "state": state,
            "current_location": current_location,
            "characters": characters,
            "character_actions": character_actions,
            "pending_generated_proposals": proposals,
            "visible_entities": visible_entities,
            "inventory": inventory,
            "world_entries": world_entries,
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }
