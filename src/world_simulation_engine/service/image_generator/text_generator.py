from world_simulation_engine.model import CanonicalCharacterVisualSpec, CurrentCharacterVisualSpec, \
    TextImageGeneratorProfile
from .image_generator import ImageGenerator


class TextImageGenerator(ImageGenerator[TextImageGeneratorProfile]):
    async def generate_character_canonical(self, spec: CanonicalCharacterVisualSpec) -> bytes:
        prompts = self._compose_prompts(
            positive_template=self.profile.canonical_character_prompts.positive,
            negative_template=self.profile.canonical_character_prompts.negative,
            data={
                "spec": spec,
            },
        )

        images = await self.backend.generate_image(positive_prompt=prompts.positive, negative_prompt=prompts.negative)

        return images[0]

    async def generate_character_current(self,
                                         spec: CurrentCharacterVisualSpec,
                                         ):
        prompts = self._compose_prompts(
            positive_template=self.profile.canonical_character_prompts.positive,
            negative_template=self.profile.canonical_character_prompts.negative,
            data={
                "spec": spec,
            }
        )

        images = await self.backend.generate_image(
            positive_prompt=prompts.positive,
            negative_prompt=prompts.negative,
        )

        return images[0]
