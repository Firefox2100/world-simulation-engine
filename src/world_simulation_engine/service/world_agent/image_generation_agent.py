from typing import cast

from world_simulation_engine.misc.enums import CanonicalImageReferenceFormat, CurrentImageReferenceFormat
from world_simulation_engine.model import ImageGenerationAgentProfile, CanonicalCharacterVisualSpec, \
    CurrentCharacterVisualSpec, Character, Equipment, Location, ResolvedAction, SimulationState
from .world_agent import WorldAgent


class ImageGenerationAgent(WorldAgent[ImageGenerationAgentProfile]):
    async def generate_canonical_spec(self,
                                      character: Character,
                                      world_style: str | None = None,
                                      reference_format: CanonicalImageReferenceFormat | None = None
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
                run_name="character_canonical_spec",
                max_attempts=2,
            ),
        )

    async def generate_current_spec(self,
                                    character: Character,
                                    location: Location,
                                    state: SimulationState,
                                    canonical_spec: CanonicalCharacterVisualSpec | None = None,
                                    equipments: list[Equipment] | None = None,
                                    actions: list[ResolvedAction] | None = None,
                                    reference_format: CurrentImageReferenceFormat | None = None
                                    ) -> CurrentCharacterVisualSpec:
        data = {
            "character": character,
            "canonical_spec": canonical_spec,
            "equipments": equipments,
            "location": location,
            "actions": actions,
            "state": state,
            "reference_format": reference_format
        }

        messages = self._compose_messages(
            prompts=self.profile.character_canonical_prompt,
            data=data,
        )

        return cast(
            CurrentCharacterVisualSpec,
            await self._invoke_structured_with_repair(
                output_model=CurrentCharacterVisualSpec,
                messages=messages,
                repair_instruction=(
                    "You must return a valid CurrentCharacterVisualSpec."
                ),
                run_name="character_current_spec",
                max_attempts=2,
            ),
        )
