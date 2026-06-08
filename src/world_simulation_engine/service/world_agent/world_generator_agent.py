from enum import StrEnum

from .world_agent import WorldAgent, ProposedLocation, ProposedItem, ProposedEntity, ProposedWorldEntry


class WorldGeneratorAgent(WorldAgent):
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

        entity_model = self.model.with_structured_output(self._patch_entity_model(entity_types))

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
