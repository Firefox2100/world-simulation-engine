from pydantic import BaseModel

from world_simulation_engine.model import ImageGenerationAgentProfile, LlmConnectionProfile, \
    ImageGenerationConnectionProfile, CharacterGeneratorProfile
from world_simulation_engine.service import DatabaseService, StorageService, ImageGenerationAgent, \
    CharacterImageGenerator


class ConnectionProfileCache(BaseModel):
    image_generation: LlmConnectionProfile | None = None

    character: ImageGenerationConnectionProfile | None = None


class ImagePresenterState(BaseModel):
    run_id: str
    simulation_id: int


class CharacterImageState(BaseModel):
    simulation_id: int
    character_id: int
    llm_profile: ImageGenerationAgentProfile
    image_profile: CharacterGeneratorProfile
    llm_connection: LlmConnectionProfile
    image_connection: ImageGenerationConnectionProfile


class ImagePresenter:
    def __init__(self,
                 database_service: DatabaseService,
                 storage_service: StorageService,
                 ):
        self._db = database_service
        self._storage = storage_service

    async def generate_character_canonical_image(self, state: CharacterImageState):
        character = await self._db.character.get(state.character_id)
        if not character:
            raise ValueError(f"Character {state.character_id} not found")

        image_generation_agent = ImageGenerationAgent(
            profile=state.llm_profile,
            connection=state.llm_connection,
        )
        character_generator = CharacterImageGenerator(
            profile=state.image_profile,
            connection=state.image_connection,
        )

        spec = await image_generation_agent.generate_canonical_spec(
            character=character,
            # TODO: Implement these configurations
            world_style=None,
            reference_format=None,
        )

        image = await character_generator.generate_character_canonical(spec)
        if not image:
            raise ValueError(f"Failed to generate image for character {state.character_id}")

        await self._storage.simulation(state.simulation_id).image.save(
            file_name=f"character-{state.character_id}.png",
            data=image,
        )

    async def generate_character_current_image(self, state: CharacterImageState):
        try:
            canonical_image = await self._storage.simulation(state.simulation_id).image.get(
                file_name=f"character-{state.character_id}.png",
            )
        except FileNotFoundError:
            canonical_image = None


