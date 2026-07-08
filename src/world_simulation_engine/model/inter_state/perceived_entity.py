from typing import Optional
from pydantic import BaseModel, Field


class PerceivedEntity(BaseModel):
    entity: EntityRef
    relation_to_actor: Optional[str] = None
    visibility: list[Visibility] = Field(default_factory=list)
    distance_hint: Optional[str] = Field(
        default=None,
        description="near, across_room, same_location, behind_counter, unknown, etc."
    )
    affordances: list[str] = Field(
        default_factory=list,
        description="Actions this actor currently believes are possible with this entity."
    )
    salience: Salience = "medium"
    notes: Optional[str] = None
