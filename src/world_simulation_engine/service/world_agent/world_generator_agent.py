from enum import StrEnum
from langchain.tools import tool

from world_simulation_engine.model import AgentProfiles
from .models import ProposedLocation, ProposedItem, ProposedEntity, ProposedWorldEntry
from .world_agent import WorldAgent


class WorldGeneratorAgent(WorldAgent):
    def __init__(self,
                 profile: AgentProfiles,
                 entity_types: list[str],
                 ):
        super().__init__(profile)
        self._entity_types = entity_types

    def _patch_entity_model(self) -> type[ProposedEntity]:
        EntityTypeEnum = StrEnum(
            "EntityTypeEnum",
            {t.upper().replace("-", "_").replace(" ", "_"): t for t in self._entity_types},
        )

        class ProposedEntityPatched(ProposedEntity):
            type: EntityTypeEnum

        return ProposedEntityPatched

    async def generate_location(self,
                                context: str,
                                trigger: str,
                                constraints: list[str],
                                ) -> ProposedLocation:
        messages = self._compose_messages(
            data={
                "context": context,
                "trigger": trigger,
                "constraints": constraints,
            }
        )
        messages[-1].content += "\n\nGenerate one proposed location."

        location_model = self.model.with_structured_output(ProposedLocation)

        result = await location_model.ainvoke(messages)

        return result

    async def generate_item(self,
                            context: str,
                            trigger: str,
                            constraints: list[str],
                            ) -> ProposedItem:
        messages = self._compose_messages(
            data={
                "context": context,
                "trigger": trigger,
                "constraints": constraints,
            }
        )
        messages[-1].content += "\n\nGenerate one proposed item."

        item_model = self.model.with_structured_output(ProposedItem)

        result = await item_model.ainvoke(messages)

        return result

    async def generate_entity(self,
                              context: str,
                              trigger: str,
                              constraints: list[str],
                              entity_types: list[str],
                              ) -> ProposedEntity:
        messages = self._compose_messages(
            data={
                "context": context,
                "trigger": trigger,
                "constraints": constraints,
            }
        )
        messages[-1].content += "\n\nGenerate one proposed entity."

        entity_model = self.model.with_structured_output(self._patch_entity_model())

        result = await entity_model.ainvoke(messages)

        return result

    async def generate_world_entry(self,
                                   context: str,
                                   trigger: str,
                                   constraints: list[str],
                                   ) -> ProposedWorldEntry:
        messages = self._compose_messages(
            data={
                "context": context,
                "trigger": trigger,
                "constraints": constraints,
            }
        )
        messages[-1].content += "\n\nGenerate one proposed world entry."

        world_entry_model = self.model.with_structured_output(ProposedWorldEntry)

        result = await world_entry_model.ainvoke(messages)

        return result

    def get_tools(self):
        @tool(parse_docstring=True)
        async def generate_location(context: str, trigger: str, constraints: list[str]) -> ProposedLocation:
            """
            Generate one proposed new location when the current round exposes an unknown place.

            Use this only when a user or resolved action would reveal a place that does not
            yet exist in canonical state, such as entering an unexplored room, opening a
            hidden passage, descending into an unknown tunnel, or discovering a new scene.

            The generated location is a pending proposal only. It must not be treated as
            canonical until the resolver accepts it.

            Do not use this for narration, flavour text, or known locations.

            Args:
                context: Serialized world state relevant to generation (for example known locations,
                    entities, items, and relationships).
                trigger: Event or action that motivates creating a new location.
                constraints: Hard requirements the generated location must satisfy.

            Returns:
                ProposedLocation: A structured location proposal.
            """
            return await self.generate_location(context, trigger, constraints)

        @tool(parse_docstring=True)
        async def generate_item(context: str, trigger: str, constraints: list[str]) -> ProposedItem:
            """
            Generate one proposed inventory-style item, clue, document, key, tool, fragment,
            token, or portable object.

            Use this when a search, discovery, container opening, handover, or evidence
            reveal may produce a portable item. The result is pending until the resolver
            commits it.

            Do not use this for fixed environmental features; use generate_entity instead.

            Args:
                context: Serialized world state relevant to generation.
                trigger: Event or action that motivates creating a new item.
                constraints: Hard requirements the generated item must satisfy.

            Returns:
                ProposedItem: A structured item proposal.
            """
            return await self.generate_item(context, trigger, constraints)

        @tool(parse_docstring=True)
        async def generate_entity(
            context: str,
            trigger: str,
            constraints: list[str],
        ) -> ProposedEntity:
            """
            Generate one proposed interactable entity inside an existing location.

            Use this when an action reveals or requires a physical object, fixture,
            container, sign, clue-bearing surface, mechanism, document cache, trace, or
            other interactable scene element that is not already in canonical state.

            The generated entity is pending only. The resolver decides whether it exists,
            is discovered, remains hidden, or is discarded.

            Do not use this to generate inventory items directly unless the entity remains
            part of the scene.

            Args:
                context: Serialized world state relevant to generation.
                trigger: Event or action that motivates creating a new entity.
                constraints: Hard requirements the generated entity must satisfy.

            Returns:
                ProposedEntity: A structured entity proposal with a constrained `type` value.
            """
            return await self.generate_entity(context, trigger, constraints)

        @tool(parse_docstring=True)
        async def generate_world_entry(context: str, trigger: str, constraints: list[str]) -> ProposedWorldEntry:
            """
            Generate one proposed world-entry fact, rumour, memory, belief, suspicion, or
            scoped knowledge entry.

            Use this when the round introduces knowledge rather than a physical object:
            rumours, overheard facts, changed beliefs, newly inferred motives, discoveries,
            or hidden truths that should be stored in the world-entry recall system.

            The entry is pending. The resolver decides whether to commit it and with what
            scope, visibility, confidence, recall type, and narration permission.

            Content must be a complete factual sentence, not a title.

            Args:
                context: Serialized world state relevant to generation.
                trigger: Event or action that motivates creating a new world entry.
                constraints: Hard requirements the generated world entry must satisfy.

            Returns:
                ProposedWorldEntry: A structured world-entry proposal.
            """
            return await self.generate_world_entry(context, trigger, constraints)

        return [
            generate_location,
            generate_item,
            generate_entity,
            generate_world_entry,
        ]
