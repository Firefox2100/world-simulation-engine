from pydantic import BaseModel, ConfigDict, Field


class ImagePromptProposal(BaseModel):
    """Structured text-to-image prompt, split into canonical identity and transient state.

    Canonical identity (look, build, hair, fixed environment features, permanent objects) must
    stay stable across every image of the same entity to prevent visual drift, so it is generated
    once and reused afterward. Transient state (clothing, expression, activity, time of day,
    temporary props) is free to vary per generation.
    """

    model_config = ConfigDict(extra="forbid")

    canonical_tags: list[str] = Field(
        min_length=3,
        max_length=25,
        description=(
            "Short comma-style keywords/phrases for permanent identity: look, build, hair, "
            "fixed environment features, permanent objects."
        ),
    )
    canonical_description: str = Field(
        min_length=1,
        description=(
            "A natural language sentence or two describing permanent identity traits that must "
            "never change across images of this entity."
        ),
    )
    transient_tags: list[str] = Field(
        min_length=3,
        max_length=25,
        description=(
            "Short comma-style keywords/phrases for this specific image's situational state: "
            "clothing, expression, activity, time of day, temporary props."
        ),
    )
    transient_description: str = Field(
        min_length=1,
        description="A natural language sentence or two describing this image's pose, relationship, and interaction.",
    )


class TransientImagePromptProposal(BaseModel):
    """Situational-only prompt content, generated when canonical identity is already established.

    Must never restate or contradict the supplied canonical identity; only describes what is new
    or different about this specific image (clothing, expression, activity, time of day, temporary
    props, spatial arrangement/interaction).
    """

    model_config = ConfigDict(extra="forbid")

    transient_tags: list[str] = Field(
        min_length=3,
        max_length=25,
        description="Short comma-style keywords/phrases for this specific image's situational state only.",
    )
    transient_description: str = Field(
        min_length=1,
        description="A natural language sentence or two describing this image's pose, relationship, and interaction.",
    )
