from typing import Optional
from pydantic import BaseModel, Field


class ModelAttribute(BaseModel):
    """
    An attribute is a (list of) tag to describe a certain aspect of a model object.
    """
    name: str = Field(
        ...,
        description="The name of the attribute. Must match the model attribute dictionary key.",
    )
    values: Optional[list[str]] = Field(
        None,
        description="The allowed values for this attribute. If left empty or not specified, it's considered an open "
                    "field, and LLM will invent the values.",
    )

    creation_instruction: str = Field(
        ...,
        description="The instruction to tell LLM how to assign this field when creating an entity.",
    )
    update_instruction: str = Field(
        ...,
        description="The instruction to tell LLM how to update this attribute.",
    )
    universal: bool = Field(
        False,
        description="Whether this attribute must be assigned to all entities of the type when creating."
    )


class ModelStat(BaseModel):
    """
    A stat that is numerical and used in internal comparison, and is subject to change frequently.
    """
    name: str = Field(
        ...,
        description="The name of the stat. Must match the model stat dictionary key.",
    )

    creation_instruction: str = Field(
        ...,
        description="The instruction to tell LLM how to assign this field when creating an entity.",
    )
    update_instruction: str = Field(
        ...,
        description="The instruction to tell LLM how to update this attribute.",
    )
    universal: bool = Field(
        False,
        description="Whether this stat must be assigned to all entities of the type when creating.",
    )


class DataPreset(BaseModel):
    """
    A preset is a set of extra data fields used in simulations in addition to the standard model fields.
    These fields are usually specific to each world setup.
    """
    character_attributes: list[ModelAttribute] = Field(
        ...,
        description="The list of character attributes for this preset.",
    )
    character_stats: list[ModelStat] = Field(
        ...,
        description="The list of character stats for this preset.",
    )

    entity_types: dict[str, str] = Field(
        ...,
        description="The entity types allowed in a location, and its explanation.",
    )
