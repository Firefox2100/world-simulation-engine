import pytest

from world_simulation_engine.misc.enums import CanonicalImageReferenceFormat
from world_simulation_engine.model import CanonicalCharacterVisualSpec
from world_simulation_engine.model.image_record import ImageRecord, ImageRecordCreate


@pytest.fixture
def mock_character_canonical_spec():
    return CanonicalCharacterVisualSpec(
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


@pytest.fixture
def mock_image_record_create(mock_character_canonical_spec,
                             mock_simulation,
                             ):
    return ImageRecordCreate(
        simulation_id=mock_simulation.id,
        target="character",
        category="canonical",
        target_id=1,
        spec=mock_character_canonical_spec,
    )


@pytest.fixture(autouse=True)
async def setup(db, mock_simulation):
    await db.simulation.create(mock_simulation)


async def test_create_image_record(db,
                                   mock_image_record_create
                                   ):
    result = await db.image.create(mock_image_record_create)

    assert isinstance(result, ImageRecord)
    assert result.id == 1
    assert result.simulation_id == 1
    assert result.target == "character"
    assert result.category == "canonical"
    assert result.target_id == 1


async def test_get_image_record(db,
                                mock_image_record_create,
                                ):
    result = await db.image.create(mock_image_record_create)

    fetch_result = await db.image.get(result.id)

    assert isinstance(fetch_result, ImageRecord)
    assert fetch_result.id == result.id
    assert fetch_result.simulation_id == mock_image_record_create.simulation_id
    assert fetch_result.target == mock_image_record_create.target
    assert fetch_result.category == mock_image_record_create.category
    assert fetch_result.target_id == mock_image_record_create.target_id
