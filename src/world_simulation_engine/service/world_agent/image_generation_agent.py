from typing import cast

from world_simulation_engine.model import ImageGenerationAgentProfile, CanonicalCharacterVisualSpec, Character
from .world_agent import WorldAgent


class ImageGenerationAgent(WorldAgent[ImageGenerationAgentProfile]):
    async def generate_canonical_spec(self,
                                      character: Character,
                                      world_style: str | None = None,
                                      reference_format: str | None = None
                                      ) -> CanonicalCharacterVisualSpec:
        data = {
            "id": character.id,
            "name": character.name,
            "gender": character.gender,
            "age": character.age,
            "description": character.description,
            "appearance": character.appearance,
            "public_state": character.public_state,
            "private_state": character.private_state,
            "world_style": world_style,
            "reference_format": reference_format
        }

        messages = self._compose_messages(
            prompts=self.profile.character_canonical_prompt,
            data=data,
        )

        return cast(
            CanonicalCharacterVisualSpec,
            await self._invoke_structured_with_repair(
                output_model=CanonicalCharacterVisualSpec,
                messages=messages,
                repair_instruction=(
                    "You must return a valid CanonicalCharacterVisualSpec."
                ),
                run_name="canonical_spec",
                max_attempts=2,
            ),
        )
