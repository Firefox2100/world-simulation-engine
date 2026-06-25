import pytest

from world_simulation_engine.misc.enums import CanonicalImageReferenceFormat
from world_simulation_engine.model import CanonicalCharacterVisualSpec
from world_simulation_engine.service import ImageGenerationAgent, CharacterImageGenerator


@pytest.fixture
def image_generation_agent(mock_image_generation_agent_profile,
                           mock_llm_connection,
                           ) -> ImageGenerationAgent:
    return ImageGenerationAgent(
        profile=mock_image_generation_agent_profile,
        connection=mock_llm_connection,
    )


@pytest.fixture
def character_generator(mock_character_generation_profile,
                        mock_image_generation_connection,
                        ) -> CharacterImageGenerator:
    return CharacterImageGenerator(
        profile=mock_character_generation_profile,
        connection=mock_image_generation_connection,
    )


async def test_generate_canonical_character_spec(image_generation_agent,
                                                 mock_characters,
                                                 ):
    spec = await image_generation_agent.generate_canonical_spec(
        character=mock_characters[0],
        # TODO: Implement these configurations
        world_style=None,
        reference_format=None,
    )

    assert isinstance(spec, CanonicalCharacterVisualSpec)
    assert spec.character_id == mock_characters[0].id


async def test_generate_canonical_character_image(character_generator):
    spec = CanonicalCharacterVisualSpec(
        character_id=1,
        name='Eleanor Graves',
        demographic_keywords=[
            'female', '42 years old', 'middle-aged human'
        ],
        body_keywords=[
            'composed silhouette', 'upright build', 'mature physique'
        ],
        face_keywords=[
            'sharp features', 'defined jawline', 'mature face structure'
        ],
        hair_keywords=[
            'neatly styled', 'professional cut', 'conservative style'
        ],
        eye_keywords=[
            'tired eyes', 'focused gaze', 'observant expression'
        ],
        posture_keywords=[
            'immaculate posture', 'formal restraint', 'upright stance', 'public-facing bearing'
        ],
        expression_keywords=[
            'composed resting face', 'neutral but alert', 'controlled demeanor'
        ],
        canonical_clothing_keywords=[
            'professional business attire', 'conservative suit or formal dress', 'muted colors', 'neat appearance'
        ],
        accessory_keywords=[
            'minimal professional accessories'
        ],
        personality_visual_cues=[
            'controlled demeanor', 'calculated stillness', 'authoritative presence'
        ],
        social_role_visual_cues=[
            'mayoral authority', 'civic formality', 'polished public image'
        ],
        background_keywords=[
            'neutral studio background', 'soft gradient', 'official portrait style', 'uncluttered'
        ],
        style_keywords=[
            'realistic', 'cinematic lighting', 'character sheet', 'front_back_reference',
            'high detail', 'reference photography'
        ],
        reference_format=CanonicalImageReferenceFormat.FRONT_BACK_REFERENCE,
        must_include=[
            'sharp facial features', 'tired eyes', 'formal posture', 'middle-aged female appearance'
        ],
        must_avoid=[
            'casual clothing', 'overt emotion', 'fantasy elements', 'scene-specific props'
        ],
        uncertainty_notes=[
            'Hair color and specific style not specified in source data; exact clothing details undefined beyond formality.'
        ]
    )

    image = await character_generator.generate_character_canonical(spec)

    assert isinstance(image, bytes)
