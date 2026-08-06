"""Infer initial placement for extracted entities from current-scene card prose."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .equipment_extractor import EquipmentExtraction
from .item_extractor import ItemExtraction
from .location_extractor import LocationExtraction
from .pipeline_component import SillyTavernPipelineComponent


class SpatialEntityType(StrEnum):
    CHARACTER = "character"
    ITEM = "item"
    EQUIPMENT = "equipment"


class SpatialPlacementCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: SpatialEntityType
    entity_name: str
    location_name: str | None = None
    position: str | None = None


class SpatialPlacementCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placements: list[SpatialPlacementCandidate] = Field(default_factory=list, max_length=100)


class ExtractedSpatialPlacement(BaseModel):
    entity_type: SpatialEntityType
    entity_name: str
    location_id: str
    position: str | None = None


class SpatialStateExtraction(BaseModel):
    placements: list[ExtractedSpatialPlacement] = Field(default_factory=list)


class SpatialStateExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_SPATIAL_STATE_EXTRACTOR

    async def extract(
            self, card: PreprocessedCard, characters: CharacterExtraction,
            locations: LocationExtraction, items: ItemExtraction, equipment: EquipmentExtraction,
            *, language: SupportedLanguage,
    ) -> SpatialStateExtraction:
        entity_names = {
            SpatialEntityType.CHARACTER: [c.target_name for c in characters.characters],
            SpatialEntityType.ITEM: [item.name for item in items.items],
            SpatialEntityType.EQUIPMENT: [item.name for item in equipment.equipment],
        }
        if not locations.locations or not any(entity_names.values()):
            return SpatialStateExtraction()

        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_spatial_state_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=SpatialPlacementCandidates,
            messages=prompt,
            data={
                "scenario": card.scenario,
                "opening_message": card.first_message,
                "characters": [
                    {
                        "name": c.target_name,
                        "public_state": c.result.public_state,
                        "current_activity": c.result.current_activity,
                    }
                    for c in characters.characters
                ],
                "items": entity_names[SpatialEntityType.ITEM],
                "equipment": entity_names[SpatialEntityType.EQUIPMENT],
                "locations": [location.name for location in locations.locations],
            },
            repair_instruction=(
                "Return one SpatialPlacementCandidates JSON object only. Copy entity_type, "
                "entity_name and location_name exactly from the supplied lists. Omit uncertain "
                "placements; never invent an entity or location."
            ),
            run_name="spatial_state_extractor.extract",
        )
        allowed = {(kind, name) for kind, names in entity_names.items() for name in names}
        location_id_by_name = {location.name: location.id for location in locations.locations}
        placements = []
        seen = set()
        for candidate in result.placements:
            key = (candidate.entity_type, candidate.entity_name)
            location_id = location_id_by_name.get(candidate.location_name or "")
            if key not in allowed or not location_id or key in seen:
                continue
            seen.add(key)
            placements.append(ExtractedSpatialPlacement(
                entity_type=candidate.entity_type,
                entity_name=candidate.entity_name,
                location_id=location_id,
                position=candidate.position,
            ))
        return SpatialStateExtraction(placements=placements)
