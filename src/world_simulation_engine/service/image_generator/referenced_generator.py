from world_simulation_engine.model import CurrentCharacterVisualSpec, ReferencedImageGenerationProfile
from .image_generator import ImageGenerator


class ReferencedImageGenerator(ImageGenerator[ReferencedImageGenerationProfile]):
    async def generate_character_current(self,
                                         spec: CurrentCharacterVisualSpec,
                                         reference_image: bytes,
                                         ):
        prompts = self._compose_prompts(
            positive_template=self.profile.current_character_prompts.positive,
            negative_template=self.profile.current_character_prompts.negative,
            data={
                "spec": spec,
            }
        )

        images = await self.backend.generate_image(
            positive_prompt=prompts.positive,
            negative_prompt=prompts.negative,
            reference_image=reference_image,
        )

        return images[0]
