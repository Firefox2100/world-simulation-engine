from enum import StrEnum
from typing import cast
from langchain.tools import tool

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.model import WorldGeneratorAgentProfile, Simulation, SimulationState, Location, \
    Character, Entity, Item
from .models import ProposedLocation, ProposedItem, ProposedEntity, ProposedWorldEntry
from .world_agent import WorldAgent


class WorldGeneratorAgent(WorldAgent[WorldGeneratorAgentProfile]):
    @staticmethod
    def _build_base_data(simulation: Simulation,
                         state: SimulationState,
                         current_location: Location,
                         present_characters: list[Character],
                         existing_locations: list[Location],
                         existing_entities: list[Entity],
                         existing_items: list[Item],
                         goal: str,
                         trigger: str,
                         constraints: list[str],
                         ):
        return {
            "generation_context": {
                "simulation_name": simulation.name,
                "simulation_description": simulation.description,
                "round_number": state.round_number,
                "time_label": state.time_label,
                "state_summary": state.state,
                "current_location": current_location.model_dump(),
                "present_characters": [c.model_dump() for c in present_characters],
                "existing_locations": [l.model_dump() for l in existing_locations],
                "existing_entities": [e.model_dump() for e in existing_entities],
                "existing_items": [i.model_dump() for i in existing_items],
            },
            "goal": goal,
            "trigger": trigger,
            "constraints": constraints,
        }

    @staticmethod
    def _patch_entity_model(entity_types: list[str]) -> type[ProposedEntity]:
        EntityTypeEnum = StrEnum(
            "EntityTypeEnum",
            {t.upper().replace("-", "_").replace(" ", "_"): t for t in entity_types},
        )

        class ProposedEntityPatched(ProposedEntity):
            type: EntityTypeEnum

        return ProposedEntityPatched

    async def generate_location(self,
                                simulation: Simulation,
                                state: SimulationState,
                                current_location: Location,
                                present_characters: list[Character],
                                existing_locations: list[Location],
                                existing_entities: list[Entity],
                                existing_items: list[Item],
                                goal: str,
                                trigger: str,
                                constraints: list[str],
                                ) -> ProposedLocation:
        LOGGER.info("Generating location...")
        LOGGER.debug("Goal: %s\nTrigger: %s\nConstraints: %s", goal, trigger, constraints)

        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.location_generation_prompt,
            data=data
        )
        LOGGER.debug("Generation messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        location_model = self.model.with_structured_output(ProposedLocation)

        result = cast(ProposedLocation, await location_model.ainvoke(messages))
        LOGGER.info("Location generation completed for %s", result.scene)
        LOGGER.debug("Location:\n%s", result.model_dump_json(indent=2))

        return result

    async def generate_item(self,
                            simulation: Simulation,
                            state: SimulationState,
                            current_location: Location,
                            present_characters: list[Character],
                            existing_locations: list[Location],
                            existing_entities: list[Entity],
                            existing_items: list[Item],
                            goal: str,
                            trigger: str,
                            constraints: list[str],
                            ) -> ProposedItem:
        LOGGER.info("Generating item...")
        LOGGER.debug("Goal: %s\nTrigger: %s\nConstraints: %s", goal, trigger, constraints)

        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.item_generation_prompt,
            data=data
        )
        LOGGER.debug("Generation messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        item_model = self.model.with_structured_output(ProposedItem)

        result = cast(ProposedItem, await item_model.ainvoke(messages))
        LOGGER.info("Item generation completed for %s", result.name)
        LOGGER.debug("Item:\n%s", result.model_dump_json(indent=2))

        return result

    async def generate_entity(self,
                              simulation: Simulation,
                              state: SimulationState,
                              current_location: Location,
                              present_characters: list[Character],
                              existing_locations: list[Location],
                              existing_entities: list[Entity],
                              existing_items: list[Item],
                              goal: str,
                              trigger: str,
                              constraints: list[str],
                              entity_types: list[str],
                              ) -> ProposedEntity:
        LOGGER.info("Generating entity...")
        LOGGER.debug("Goal: %s\nTrigger: %s\nConstraints: %s", goal, trigger, constraints)

        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.entity_generation_prompt,
            data=data
        )
        LOGGER.debug("Generation messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        entity_model = self.model.with_structured_output(self._patch_entity_model(entity_types))

        result = cast(ProposedEntity, await entity_model.ainvoke(messages))
        LOGGER.info("Entity generation completed for %s", result.name)
        LOGGER.debug("Entity:\n%s", result.model_dump_json(indent=2))

        return result

    async def generate_world_entry(self,
                                   simulation: Simulation,
                                   state: SimulationState,
                                   current_location: Location,
                                   present_characters: list[Character],
                                   existing_locations: list[Location],
                                   existing_entities: list[Entity],
                                   existing_items: list[Item],
                                   goal: str,
                                   trigger: str,
                                   constraints: list[str],
                                   ) -> ProposedWorldEntry:
        LOGGER.info("Generating world entry...")
        LOGGER.debug("Goal: %s\nTrigger: %s\nConstraints: %s", goal, trigger, constraints)

        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.world_entry_generation_prompt,
            data=data
        )
        LOGGER.debug("Generation messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        world_entry_model = self.model.with_structured_output(ProposedWorldEntry)

        result = cast(ProposedWorldEntry, await world_entry_model.ainvoke(messages))
        LOGGER.info("World entry generation completed for %s", result.content)
        LOGGER.debug("World entry:\n%s", result.model_dump_json(indent=2))

        return result

    def get_tools(self,
                  simulation: Simulation,
                  state: SimulationState,
                  current_location: Location,
                  present_characters: list[Character],
                  existing_locations: list[Location],
                  existing_entities: list[Entity],
                  existing_items: list[Item],
                  entity_types: list[str],
                  ):
        @tool(parse_docstring=True)
        async def generate_location(goal: str, trigger: str, constraints: list[str]) -> ProposedLocation:
            """
            Generate one pending location proposal.

            Use this when the current round exposes an unknown place:
            - entering an unexplored room;
            - revealing a hidden passage;
            - descending into an unknown tunnel;
            - opening a route to a new scene;
            - discovering a site that does not already exist in canonical locations.

            Do not use for known locations already present in existing_locations.
            Do not use for flavour-only environmental detail.
            Do not decide whether the action that revealed the location succeeds.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The overarching goal or narrative purpose that this generation should serve.
                trigger: Event or action that motivates creating a new location.
                constraints: Hard requirements the generated location must satisfy.

            Returns:
                ProposedLocation: A structured location proposal.
            """
            return await self.generate_location(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        @tool(parse_docstring=True)
        async def generate_item(goal: str, trigger: str, constraints: list[str]) -> ProposedItem:
            """
            Generate one pending portable item proposal.

            Use this for objects that may enter an inventory:
            - clues, keys, notes, letters, fragments, maps, receipts;
            - tools, tokens, evidence, personal effects;
            - contents discovered inside a searched container.

            Do not use for fixed environmental features; use generate_entity instead.
            Do not duplicate existing items.
            Do not decide whether the search or discovery succeeds.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The overarching goal or narrative purpose that this generation should serve.
                trigger: Event or action that motivates creating a new item.
                constraints: Hard requirements the generated item must satisfy.

            Returns:
                ProposedItem: A structured item proposal.
            """
            return await self.generate_item(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        @tool(parse_docstring=True)
        async def generate_entity(goal: str, trigger: str, constraints: list[str]) -> ProposedEntity:
            """
            Generate one pending interactable entity proposal inside an existing location.

            Use this for non-portable or scene-anchored objects:
            - hidden caches;
            - doors, plaques, shelves, mechanisms;
            - signs, stains, traces, machinery;
            - containers before their contents are separately generated;
            - clue-bearing surfaces or fixtures.

            Do not use for portable inventory items; use generate_item instead.
            Do not use if the entity already exists in current location or existing_entities.
            Do not decide whether the entity is discovered successfully.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The overarching goal or narrative purpose that this generation should serve.
                trigger: Event or action that motivates creating a new entity.
                constraints: Hard requirements the generated entity must satisfy.

            Returns:
                ProposedEntity: A structured entity proposal with a constrained `type` value.
            """
            return await self.generate_entity(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
                entity_types=entity_types,
            )

        @tool(parse_docstring=True)
        async def generate_world_entry(goal: str, trigger: str, constraints: list[str]) -> ProposedWorldEntry:
            """
            Generate one pending world-entry proposal.

            Use this only for persistent knowledge that should enter the recall system:
            - a newly learned fact;
            - a rumour;
            - a belief, suspicion, memory, or inference;
            - scoped knowledge for one or more characters;
            - GM-hidden fact created by a generator request.

            Do not use for ordinary observations already implied by the current scene.
            Do not use for temporary narration.
            Do not use for facts already present in existing_world_entries.
            Do not decide whether the fact is committed.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The overarching goal or narrative purpose that this generation should serve.
                trigger: Event or action that motivates creating a new world entry.
                constraints: Hard requirements the generated world entry must satisfy.

            Returns:
                ProposedWorldEntry: A structured world-entry proposal.
            """
            return await self.generate_world_entry(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        return [
            generate_location,
            generate_item,
            generate_entity,
            generate_world_entry,
        ]
