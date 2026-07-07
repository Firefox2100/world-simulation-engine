from typing import Optional, Any
from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import Salience, Visibility
from world_simulation_engine.model import PromptMessage
from world_simulation_engine.service import DatabaseService, LlmService


class EntityRef(BaseModel):
    id: str
    kind: str = Field(description="character, item, landmark, location, event, etc.")
    name: str


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


class MemoryAtom(BaseModel):
    id: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    salience: Salience = "medium"
    related_entities: list[str] = Field(default_factory=list)
    behavioural_relevance: Optional[str] = None


class Goal(BaseModel):
    id: str
    description: str
    priority: float = Field(ge=0, le=1)
    deadline: Optional[str] = Field(default=None, description="World time or natural description.")
    constraints: list[str] = Field(default_factory=list)
    success_conditions: list[str] = Field(default_factory=list)


class CurrentActivity(BaseModel):
    name: str
    started_at: Optional[str] = None
    expected_end: Optional[str] = None
    interruptible: bool = True
    constraints: list[str] = Field(default_factory=list)


class CharacterPerspective(BaseModel):
    world_id: str
    actor: EntityRef
    world_time: str
    location: EntityRef

    actor_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Mood, fatigue, injuries, intoxication, stress, hunger, etc."
    )
    inventory: list[EntityRef] = Field(default_factory=list)
    equipment: list[EntityRef] = Field(default_factory=list)

    current_activity: Optional[CurrentActivity] = None
    goals: list[Goal] = Field(default_factory=list)

    visible_or_known_entities: list[PerceivedEntity] = Field(default_factory=list)
    relevant_memories: list[MemoryAtom] = Field(default_factory=list)

    recent_events: list[str] = Field(
        default_factory=list,
        description="Immediately preceding events from this actor's perspective."
    )
    hard_constraints: list[str] = Field(
        default_factory=list,
        description="Rules the proposal must not violate."
    )
    soft_constraints: list[str] = Field(
        default_factory=list,
        description="Preferences, norms, personality tendencies, uncertainty, tone."
    )


class CharacterSimulator:
    def __init__(self,
                 character_id: str,
                 database: DatabaseService,
                 ):
        self._character_id = character_id
        self._db = database

    async def _build_perspective(self) -> CharacterPerspective:
        pass

    async def propose_actions(self):
        perspective = await self._build_perspective()
        world = await self._db.world.get_world(perspective.world_id)
        if not world:
            raise ValueError(f"World {perspective.world_id} not found")

        prompt_data = PROMPTS[world.language]["action_proposal"]
        prompt = [PromptMessage.model_validate(p) for p in prompt_data]
