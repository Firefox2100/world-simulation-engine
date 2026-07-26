from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Location

from .image_generator_component import ImageGeneratorComponent, ImagePromptBuildContext, ImageSubjectContext


class LocationImageGenerator(ImageGeneratorComponent):
    COMPONENT_TYPE = ComponentType.LOCATION_IMAGE_GENERATOR
    WORKFLOW_NAME = "location"
    NEGATIVE_PROMPT = "people, characters, text, watermark, blurry, low quality"

    async def _get_entity(self, entity_id: str) -> Location | None:
        return await self._db.location.get_location(entity_id)

    async def _build_context(self, entity: Location) -> ImagePromptBuildContext:
        return ImagePromptBuildContext(
            purpose=(
                "A wide establishing shot of one location, empty of any characters, showing its "
                "layout, furnishings, and mood."
            ),
            subjects=[
                ImageSubjectContext(
                    entity_id=entity.id,
                    kind="location",
                    name=entity.name,
                    description=entity.description,
                    details=entity.description,
                )
            ],
        )
