from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Character

from .image_generator_component import ImageGeneratorComponent, ImagePromptBuildContext, ImageSubjectContext


class CharacterImageGenerator(ImageGeneratorComponent):
    COMPONENT_TYPE = ComponentType.CHARACTER_IMAGE_GENERATOR
    WORKFLOW_NAME = "character"

    async def _get_entity(self, entity_id: str) -> Character | None:
        return await self._db.character.get_character(entity_id)

    async def _build_context(self, entity: Character) -> ImagePromptBuildContext:
        return ImagePromptBuildContext(
            purpose=(
                "A standalone reference/state portrait of one character: plain neutral background, "
                "no scene, no other characters, focused entirely on the character's current appearance "
                "and outfit."
            ),
            subjects=[
                ImageSubjectContext(
                    entity_id=entity.id,
                    kind="character",
                    name=entity.name,
                    description=entity.description,
                    details=f"{entity.age}-year-old {entity.gender}. Appearance: {entity.appearance}.",
                    pose_hint=entity.public_state,
                )
            ],
        )
