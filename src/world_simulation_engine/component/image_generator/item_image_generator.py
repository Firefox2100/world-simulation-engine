from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Item

from .image_generator_component import ImageGeneratorComponent, ImagePromptBuildContext, ImageSubjectContext


class ItemImageGenerator(ImageGeneratorComponent):
    COMPONENT_TYPE = ComponentType.ITEM_IMAGE_GENERATOR
    WORKFLOW_NAME = "item"
    NEGATIVE_PROMPT = "people, characters, hands, blurry, low quality, watermark, text"

    async def _get_entity(self, entity_id: str) -> Item | None:
        return await self._db.item.get_item(entity_id)

    async def _build_context(self, entity: Item) -> ImagePromptBuildContext:
        return ImagePromptBuildContext(
            purpose=(
                "A standalone product shot of one item, isolated on a plain background, no people, "
                "no hands, no scene."
            ),
            subjects=[
                ImageSubjectContext(
                    entity_id=entity.id,
                    kind="item",
                    name=entity.name,
                    description=entity.description,
                )
            ],
        )
