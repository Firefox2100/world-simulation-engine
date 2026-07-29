from world_simulation_engine.misc.enums import ComponentType, ImageGenerationType
from world_simulation_engine.model import Character, MediaFile

from .character_image_generator import CharacterImageGenerator
from .image_generator_component import ImageGeneratorComponent, ImageParticipant
from .location_image_generator import LocationImageGenerator


class CharacterPortraitImageGenerator(ImageGeneratorComponent):
    """Generates an environmental portrait: one character shown within their current location,
    with their current look and pose, optionally grounded by a specific turn's narration.

    Both the character and the location are canonical-identity-bearing participants: if either
    does not have an established identity yet, it is generated first via CharacterImageGenerator
    or LocationImageGenerator before the portrait itself is built.
    """

    COMPONENT_TYPE = ComponentType.CHARACTER_PORTRAIT_IMAGE_GENERATOR
    WORKFLOW_NAME = "character"

    async def _get_entity(self, entity_id: str) -> Character | None:
        return await self._db.character.get_character(entity_id)

    async def generate_portrait(self,
                                *,
                                simulation_id: str,
                                character_id: str,
                                turn_id: str | None = None,
                                block_id: str | None = None,
                                ) -> MediaFile:
        character = await self._get_entity(character_id)
        if not character:
            raise ValueError(f"Entity {character_id} not found")

        location = await self._db.location.get_location_by_character(character_id)
        if not location:
            raise ValueError(f"Character {character_id} is not in a location")

        narration = await self._narration_for_turn(turn_id) if turn_id else ""

        character_generator = CharacterImageGenerator(
            database=self._db, storage=self._storage,
            workflow_loader=self._workflow_loader, prompt_loader=self._prompt_loader,
        )
        location_generator = LocationImageGenerator(
            database=self._db, storage=self._storage,
            workflow_loader=self._workflow_loader, prompt_loader=self._prompt_loader,
        )
        participants = [
            ImageParticipant(
                entity_id=character.id,
                kind="character",
                name=character.name,
                description=character.description,
                details=f"{character.age}-year-old {character.gender}. Appearance: {character.appearance}.",
                pose_hint=character.public_state,
                state_generator=character_generator,
            ),
            ImageParticipant(
                entity_id=location.id,
                kind="location",
                name=location.name,
                description=location.description,
                details=location.description,
                pose_hint="",
                state_generator=location_generator,
            ),
        ]

        return await self._generate_composite(
            source_id=simulation_id,
            purpose=(
                "An environmental portrait of one character shown within their current location, "
                "the environment as backdrop, the character remaining the clear focal point with "
                "their current look and pose."
            ),
            participants=participants,
            generation_type=ImageGenerationType.CHARACTER_PORTRAIT,
            narration=narration,
            title=character.name,
            filename=character_id,
            turn_id=turn_id,
            block_id=block_id,
        )
