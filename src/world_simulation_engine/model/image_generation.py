from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import CanonicalImageReferenceFormat, CurrentImageReferenceFormat


class CanonicalCharacterVisualSpec(BaseModel):
    character_id: int
    name: str

    demographic_keywords: list[str] = Field(default_factory=list)
    body_keywords: list[str] = Field(default_factory=list)
    face_keywords: list[str] = Field(default_factory=list)
    hair_keywords: list[str] = Field(default_factory=list)
    eye_keywords: list[str] = Field(default_factory=list)
    posture_keywords: list[str] = Field(default_factory=list)
    expression_keywords: list[str] = Field(default_factory=list)

    canonical_clothing_keywords: list[str] = Field(default_factory=list)
    accessory_keywords: list[str] = Field(default_factory=list)

    personality_visual_cues: list[str] = Field(default_factory=list)
    social_role_visual_cues: list[str] = Field(default_factory=list)

    background_keywords: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)

    reference_format: CanonicalImageReferenceFormat = CanonicalImageReferenceFormat.FRONT_BACK_REFERENCE

    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)

    uncertainty_notes: list[str] = Field(default_factory=list)


class CurrentCharacterVisualSpec(BaseModel):
    character_id: int
    name: str

    identity_keywords: list[str] = Field(default_factory=list)
    persistent_appearance_keywords: list[str] = Field(default_factory=list)

    current_clothing_keywords: list[str] = Field(default_factory=list)
    visible_equipment_keywords: list[str] = Field(default_factory=list)
    held_object_keywords: list[str] = Field(default_factory=list)

    expression_keywords: list[str] = Field(default_factory=list)
    pose_keywords: list[str] = Field(default_factory=list)
    action_keywords: list[str] = Field(default_factory=list)

    location_background_keywords: list[str] = Field(default_factory=list)
    atmosphere_keywords: list[str] = Field(default_factory=list)
    lighting_keywords: list[str] = Field(default_factory=list)

    camera_keywords: list[str] = Field(default_factory=list)
    composition_keywords: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)

    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)

    private_state_visual_cues: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

    reference_format: CurrentImageReferenceFormat = CurrentImageReferenceFormat.SINGLE_FULL_BODY_SHOWCASE
