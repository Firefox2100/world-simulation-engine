from pydantic import BaseModel

from world_simulation_engine.model import ImageGenerationAgentProfile, LlmConnectionProfile, \
    ImageGenerationConnectionProfile, TextImageGeneratorProfile, ReferencedImageGenerationProfile, \
    SimulationState
from world_simulation_engine.model.image_record import ImageRecordCreate
from world_simulation_engine.service import DatabaseService, StorageService, ImageGenerationAgent, \
    TextImageGenerator, ReferencedImageGenerator


class ConnectionProfileCache(BaseModel):
    image_generation: LlmConnectionProfile | None = None

    text: ImageGenerationConnectionProfile | None = None
    referenced: ReferencedImageGenerationProfile | None = None


class ImagePresenterState(BaseModel):
    run_id: str
    simulation_id: int

    state: SimulationState | None = None


class CharacterImageState(BaseModel):
    simulation_id: int
    character_id: int
    llm_profile: ImageGenerationAgentProfile
    text_image_profile: TextImageGeneratorProfile
    referenced_image_profile: ReferencedImageGenerationProfile
    llm_connection: LlmConnectionProfile
    image_connection: ImageGenerationConnectionProfile

    state: SimulationState


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
        character_generator = TextImageGenerator(
            profile=state.text_image_profile,
            connection=state.image_connection,
        )

        spec = await image_generation_agent.generate_canonical_spec(
            character=character,
            # TODO: Implement these configurations
            world_style=None,
            reference_format=None,
        )

        image = await character_generator.generate_character_canonical(spec)
        await self._storage.simulation(state.simulation_id).image.save(
            file_name=f"character-{state.character_id}.png",
            data=image,
        )
        await self._db.image.create(
            ImageRecordCreate(
                simulation_id=state.simulation_id,
                target="character",
                category="canonical",
                target_id=state.character_id,
                spec=spec,
            )
        )

    async def generate_character_current_image(self, state: CharacterImageState):
        try:
            canonical_image = await self._storage.simulation(state.simulation_id).image.get(
                file_name=f"character-{state.character_id}.png",
            )
        except FileNotFoundError:
            canonical_image = None

        character = await self._db.character.get(state.character_id)
        if not character:
            raise ValueError(f"Character {state.character_id} not found")
        location = await self._db.location.get(character.location)
        if not location:
            raise ValueError(f"Location {character.location} not found")
        canonical_records = await self._db.image.list(
            simulation_id=state.simulation_id,
            target="character",
            category="canonical",
            target_id=state.character_id
        )
        equipments = await self._db.equipment.list(
            simulation_id=state.simulation_id,
            character_id=state.character_id,
        )
        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation_id,
        )
        if last_records and last_records[0].resolver_output:
            character_actions = [
                a for a in last_records[0].resolver_output.resolved_actions if a.actor_id == state.character_id
            ]
        else:
            character_actions = None

        image_generation_agent = ImageGenerationAgent(
            profile=state.llm_profile,
            connection=state.llm_connection,
        )

        spec = await image_generation_agent.generate_current_spec(
            character=character,
            location=location,
            state=state.state,
            canonical_spec=canonical_records[0].spec if canonical_records else None,
            equipments=equipments,
            actions=character_actions,
            # TODO: Implement these configurations
            reference_format=None,
        )

        if canonical_image:
            # Use the referenced flow
            character_generator = ReferencedImageGenerator(
                profile=state.referenced_image_profile,
                connection=state.image_connection,
            )

            image = await character_generator.generate_character_current(
                spec=spec,
                reference_image=canonical_image,
            )
        else:
            # Use the text-to-image flow
            character_generator = TextImageGenerator(
                profile=state.text_image_profile,
                connection=state.image_connection,
            )

            image = await character_generator.generate_character_current(spec)

        await self._storage.simulation(state.simulation_id).image.save(
            file_name=f"character-{state.character_id}-current.png",
            data=image,
        )
        await self._db.image.create(
            ImageRecordCreate(
                simulation_id=state.simulation_id,
                target="character",
                category="current",
                target_id=state.character_id,
                spec=spec,
            )
        )
