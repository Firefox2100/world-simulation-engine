from world_simulation_engine.misc.enums import ComponentType, ImageGenerationType
from world_simulation_engine.model import Location, MediaFile

from .character_image_generator import CharacterImageGenerator
from .image_generator_component import ImageGeneratorComponent, ImageParticipant
from .location_image_generator import LocationImageGenerator


class SceneImageGenerator(ImageGeneratorComponent):
    """Generates a group scene: every character currently present in one location, shown
    together, optionally grounded by a specific turn's narration.

    The location and every present character are canonical-identity-bearing participants: any
    that do not yet have an established identity are generated first via LocationImageGenerator
    or CharacterImageGenerator before the scene itself is built.
    """

    COMPONENT_TYPE = ComponentType.SCENE_IMAGE_GENERATOR
    WORKFLOW_NAME = "scene"
    NEGATIVE_PROMPT = "text, watermark, blurry, low quality, extra limbs, distorted anatomy"

    async def _get_entity(self, entity_id: str) -> Location | None:
        return await self._db.location.get_location(entity_id)

    async def generate_scene(self,
                             *,
                             simulation_id: str,
                             location_id: str,
                             turn_id: str | None = None,
                             ) -> MediaFile:
        location = await self._get_entity(location_id)
        if not location:
            raise ValueError(f"Entity {location_id} not found")

        present = await self._db.get_characters_in_location(location_id)
        characters = [entry[0] for entry in present]
        if not characters:
            raise ValueError(f"No characters are currently present in location {location_id}")

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
                entity_id=location.id,
                kind="location",
                name=location.name,
                description=location.description,
                details=location.description,
                pose_hint="",
                state_generator=location_generator,
            ),
            *(
                ImageParticipant(
                    entity_id=character.id,
                    kind="character",
                    name=character.name,
                    description=character.description,
                    details=f"{character.age}-year-old {character.gender}. Appearance: {character.appearance}.",
                    pose_hint=character.public_state,
                    state_generator=character_generator,
                )
                for character in characters
            ),
        ]

        return await self._generate_composite(
            source_id=simulation_id,
            purpose=(
                f"A wide group scene showing {len(characters)} characters together in one location, "
                "depicting their spatial arrangement and interaction with each other."
            ),
            participants=participants,
            generation_type=ImageGenerationType.SCENE,
            narration=narration,
            title=location.name,
            filename=location_id,
            turn_id=turn_id,
        )
