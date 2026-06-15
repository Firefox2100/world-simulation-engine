import re
from enum import StrEnum
from uuid import uuid4
from typing import cast, Any
from langchain.tools import tool
from pydantic import BaseModel

from world_simulation_engine.model import WorldGeneratorAgentProfile, Simulation, SimulationState, Location, \
    Character, Entity, Item, Equipment, Faction, FactionRelationship, ProposedLocation, ProposedItem, ProposedEntity, \
    ProposedWorldEntry, ProposedEquipment, ProposedGenerationPackage
from .world_agent import WorldAgent


class WorldGeneratorAgent(WorldAgent[WorldGeneratorAgentProfile]):
    @staticmethod
    def _build_base_data(
        simulation: Simulation,
        state: SimulationState,
        current_location: Location,
        present_characters: list[Character],
        existing_locations: list[Location],
        existing_entities: list[Entity],
        existing_items: list[Item],
        existing_equipments: list[Equipment] | None,
        factions: list[Faction] | None,
        faction_relationships: list[FactionRelationship] | None,
        goal: str,
        trigger: str,
        constraints: list[str],
    ) -> dict[str, Any]:
        return {
            "generation_context": {
                "simulation_name": simulation.name,
                "simulation_description": simulation.description,
                "data_preset": simulation.data_preset.model_dump(),
                "round_number": state.turn_number,
                "time_label": state.time_label,
                "state_summary": state.state,
                "current_location": current_location.model_dump(),
                "present_characters": [c.model_dump() for c in present_characters],
                "existing_locations": [l.model_dump() for l in existing_locations],
                "existing_entities": [e.model_dump() for e in existing_entities],
                "existing_items": [i.model_dump() for i in existing_items],
                "existing_equipments": [e.model_dump() for e in existing_equipments or []],
                "factions": [f.model_dump() for f in factions or []],
                "faction_relationships": [r.model_dump() for r in faction_relationships or []],
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

    @staticmethod
    def _slug(value: str, fallback: str) -> str:
        text = (value or fallback).strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or fallback

    def _stabilise_temp_ids(self, proposal: BaseModel, prefix: str) -> BaseModel:
        """
        Namespaces model-generated temporary IDs so:
        - all generated IDs are stable inside this result;
        - all linked references use the same rewritten IDs;
        - the database can later replace them while preserving relationships.

        The LLM may produce readable IDs like "entity_temp_locked_box".
        This method rewrites them to e.g.
        "entity_2f4c8a1d_entity_temp_locked_box".
        """
        batch_id = uuid4().hex[:8]
        data = proposal.model_dump()
        id_map: dict[str, str] = {}

        def collect_ids(obj: Any) -> None:
            if isinstance(obj, dict):
                temp_id = obj.get("temp_id")
                if isinstance(temp_id, str) and temp_id:
                    kind = prefix
                    if temp_id.startswith("loc_") or temp_id.startswith("location_"):
                        kind = "loc"
                    elif temp_id.startswith("entity_"):
                        kind = "entity"
                    elif temp_id.startswith("item_"):
                        kind = "item"
                    elif temp_id.startswith("equip_") or temp_id.startswith("equipment_"):
                        kind = "equip"
                    elif temp_id.startswith("entry_"):
                        kind = "entry"
                    elif temp_id.startswith("pkg_") or temp_id.startswith("package_"):
                        kind = "pkg"

                    if temp_id not in id_map:
                        id_map[temp_id] = f"{kind}_{batch_id}_{self._slug(temp_id, kind)}"

                for value in obj.values():
                    collect_ids(value)

            elif isinstance(obj, list):
                for value in obj:
                    collect_ids(value)

        def rewrite(obj: Any) -> Any:
            if isinstance(obj, dict):
                rewritten = {}

                for key, value in obj.items():
                    if isinstance(value, str) and value in id_map:
                        rewritten[key] = id_map[value]
                    elif isinstance(value, list):
                        rewritten[key] = [
                            id_map.get(item, rewrite(item)) if isinstance(item, str) else rewrite(item)
                            for item in value
                        ]
                    else:
                        rewritten[key] = rewrite(value)

                if "temp_id" in rewritten:
                    temp_id = rewritten.get("temp_id")
                    if isinstance(temp_id, str):
                        rewritten["temp_id"] = id_map.get(temp_id, temp_id)

                return rewritten

            if isinstance(obj, list):
                return [rewrite(value) for value in obj]

            return obj

        collect_ids(data)

        if "temp_id" in data and not data["temp_id"]:
            data["temp_id"] = f"{prefix}_{batch_id}"

        rewritten_data = rewrite(data)

        return proposal.__class__.model_validate(rewritten_data)

    async def generate_location(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedLocation:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.location_generation_prompt,
            data=data,
        )

        model = self.model.with_structured_output(ProposedLocation)

        result = cast(
            ProposedLocation,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_location"},
            ),
        )

        return cast(ProposedLocation, self._stabilise_temp_ids(result, "loc"))

    async def generate_item(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedItem:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.item_generation_prompt,
            data=data,
        )

        model = self.model.with_structured_output(ProposedItem)

        result = cast(
            ProposedItem,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_item"},
            ),
        )

        return cast(ProposedItem, self._stabilise_temp_ids(result, "item"))

    async def generate_equipment(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedEquipment:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.equipment_generation_prompt,
            data=data,
        )

        model = self.model.with_structured_output(ProposedEquipment)

        result = cast(
            ProposedEquipment,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_equipment"},
            ),
        )

        return cast(ProposedEquipment, self._stabilise_temp_ids(result, "equip"))

    async def generate_entity(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedEntity:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.entity_generation_prompt,
            data=data,
        )

        model = self.model.with_structured_output(self._patch_entity_model(entity_types))

        result = cast(
            ProposedEntity,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_entity"},
            ),
        )

        return cast(ProposedEntity, self._stabilise_temp_ids(result, "entity"))

    async def generate_world_entry(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedWorldEntry:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.world_entry_generation_prompt,
            data=data,
        )

        model = self.model.with_structured_output(ProposedWorldEntry)

        result = cast(
            ProposedWorldEntry,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_world_entry"},
            ),
        )

        return cast(ProposedWorldEntry, self._stabilise_temp_ids(result, "entry"))

    async def generate_generation_package(
        self,
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
        existing_equipments: list[Equipment] | None = None,
        factions: list[Faction] | None = None,
        faction_relationships: list[FactionRelationship] | None = None,
    ) -> ProposedGenerationPackage:
        data = self._build_base_data(
            simulation=simulation,
            state=state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=existing_locations,
            existing_entities=existing_entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            goal=goal,
            trigger=trigger,
            constraints=constraints,
        )

        messages = self._compose_messages(
            prompts=self.profile.generation_package_prompt,
            data=data,
        )

        model = self.model.with_structured_output(ProposedGenerationPackage)

        result = cast(
            ProposedGenerationPackage,
            await model.ainvoke(
                messages,
                config={"run_name": "generate_generation_package"},
            ),
        )

        return cast(ProposedGenerationPackage, self._stabilise_temp_ids(result, "pkg"))

    def get_tools(
            self,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            present_characters: list[Character],
            existing_locations: list[Location],
            existing_entities: list[Entity],
            existing_items: list[Item],
            entity_types: list[str],
            existing_equipments: list[Equipment] | None = None,
            factions: list[Faction] | None = None,
            faction_relationships: list[FactionRelationship] | None = None,
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

            Prefer generate_generation_package instead if the new location also requires linked entities, items,
            equipment, or scoped world entries.

            Do not use for known locations already present in existing_locations.
            Do not use for flavour-only environmental detail.
            Do not decide whether the action that revealed the location succeeds.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The narrative or simulation purpose this generation should serve.
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
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        @tool(parse_docstring=True)
        async def generate_item(goal: str, trigger: str, constraints: list[str]) -> ProposedItem:
            """
            Generate one pending portable item proposal.

            Use this for objects that may enter inventory:
            - clues, keys, notes, letters, fragments, maps, receipts;
            - tools, tokens, evidence, personal effects;
            - contents discovered inside a searched container.

            Prefer generate_generation_package if the item also requires linked scoped knowledge entries.

            Do not use for fixed environmental features; use generate_entity instead.
            Do not use for worn/carried functional gear; use generate_equipment instead.
            Do not duplicate existing items.
            Do not decide whether the search or discovery succeeds.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The narrative or simulation purpose this generation should serve.
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
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        @tool(parse_docstring=True)
        async def generate_equipment(goal: str, trigger: str, constraints: list[str]) -> ProposedEquipment:
            """
            Generate one pending equipment proposal.

            Use this for worn, carried, installed, or repeatedly usable functional gear:
            - weapons, armour, tools, instruments, radios, lanterns, protective clothing;
            - character gear that should have status and condition;
            - non-consumable devices that may be equipped, damaged, repaired, or used repeatedly.

            Prefer generate_item for portable clues, documents, evidence, receipts, maps, fragments, and ordinary objects.
            Prefer generate_entity for fixed scene fixtures.
            Prefer generate_generation_package if the equipment also requires linked scoped world entries.

            Do not duplicate existing equipment.
            Do not decide whether the equipment is obtained, repaired, equipped, or successfully used.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The narrative or simulation purpose this generation should serve.
                trigger: Event or action that motivates creating new equipment.
                constraints: Hard requirements the generated equipment must satisfy.

            Returns:
                ProposedEquipment: A structured equipment proposal.
            """
            return await self.generate_equipment(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
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

            Prefer generate_generation_package if the entity has hidden facts, latent clues, contents, or linked knowledge.

            Do not use for portable inventory items; use generate_item instead.
            Do not use for wearable/carried functional gear; use generate_equipment instead.
            Do not use if the entity already exists in current location or existing_entities.
            Do not decide whether the entity is discovered successfully.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The narrative or simulation purpose this generation should serve.
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
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
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
            - GM-hidden latent fact created by a generator request.

            Prefer generate_generation_package if the world entry must be linked to a new generated entity, item,
            equipment, or location.

            Do not use for ordinary observations already implied by the current scene.
            Do not use for temporary narration.
            Do not use for facts already present in existing world entries.
            Do not decide whether the fact is committed.

            The result is pending and non-canonical until resolver approval.

            Args:
                goal: The narrative or simulation purpose this generation should serve.
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
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
            )

        @tool(parse_docstring=True)
        async def generate_generation_package(goal: str, trigger: str,
                                              constraints: list[str]) -> ProposedGenerationPackage:
            """
            Generate one pending linked proposal package.

            Use this when the new content is interdependent and should be generated together:
            - a new room with entities inside it;
            - an entity with latent clue world entries;
            - a container with possible contents;
            - an item or equipment with associated scoped knowledge;
            - a discovered clue that needs both a physical object and a world entry;
            - any case where separate tool calls would risk inconsistent IDs or mismatched facts.

            This tool may return locations, entities, items, equipment, world entries, and links between them.
            All temp_id values are temporary and non-canonical, but stable within the proposal.

            Do not use this for a single independent object when generate_location, generate_entity, generate_item,
            generate_equipment, or generate_world_entry is sufficient.
            Do not decide whether discovery, search, movement, or use succeeds.

            Args:
                goal: The narrative or simulation purpose this linked generation should serve.
                trigger: Event or action that motivates creating the linked package.
                constraints: Hard requirements the package must satisfy.

            Returns:
                ProposedGenerationPackage: A structured linked proposal package.
            """
            return await self.generate_generation_package(
                simulation=simulation,
                state=state,
                current_location=current_location,
                present_characters=present_characters,
                existing_locations=existing_locations,
                existing_entities=existing_entities,
                existing_items=existing_items,
                existing_equipments=existing_equipments,
                factions=factions,
                faction_relationships=faction_relationships,
                goal=goal,
                trigger=trigger,
                constraints=constraints,
                entity_types=entity_types,
            )

        return [
            generate_location,
            generate_item,
            generate_equipment,
            generate_entity,
            generate_world_entry,
            generate_generation_package,
        ]
