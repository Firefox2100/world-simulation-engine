from world_simulation_engine.model import CanonicalCharacterVisualSpec, CharacterGeneratorProfile
from .image_generator import ImageGenerator


class CharacterImageGenerator(ImageGenerator[CharacterGeneratorProfile]):
    async def generate_character_canonical(self, spec: CanonicalCharacterVisualSpec) -> list[bytes]:
        prompts = self._compose_prompts(
            positive_template=self.profile.canonical_prompts.positive,
            negative_template=self.profile.canonical_prompts.negative,
            data={
                "spec": spec,
            },
        )

        images = await self.backend.generate_image(
            positive_prompt=prompts.positive,
            negative_prompt=prompts.negative,
        )

        return images
