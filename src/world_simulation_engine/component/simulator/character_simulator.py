from typing import Optional, Any
from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import Salience, Visibility, ComponentType
from world_simulation_engine.model import PromptMessage, ProposedAction, Character, Location
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


class CharacterPerspective(BaseModel):
    actor: Character = Field(
        ...,
        description="The character that the perspective is in"
    )
    world_time: str
    location: Location

    inventory: list[EntityRef] = Field(default_factory=list)
    equipment: list[EntityRef] = Field(default_factory=list)

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
                 world_id: str,
                 simulation_id: str,
                 character_id: str,
                 database: DatabaseService,
                 ):
        self._world_id = world_id
        self._simulation_id = simulation_id
        self._character_id = character_id

        self._db = database

    async def _build_perspective(self) -> CharacterPerspective:
        simulation=await self._db.simulation.get_simulation(self._simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {self._simulation_id} not found")

        character = await self._db.character.get_character(self._character_id)
        if not character:
            raise ValueError(f"Character {self._character_id} not found")

        location = await self._db.loca

        return CharacterPerspective(
            actor=character,
            world_time=simulation.current_time,
        )

    async def propose_actions(self):
        perspective = await self._build_perspective()
        world = await self._db.world.get_world(self._world_id)
        if not world:
            raise ValueError(f"World {self._world_id} not found")

        prompt_data = PROMPTS[world.language]["action_proposal"]
        prompt = [PromptMessage.model_validate(p) for p in prompt_data]

        chat_config = await self._db.config.get_chat_by_source(
            source_id=self._simulation_id,
            component=ComponentType.CHARACTER_SIMULATOR,
        )
        if not chat_config:
            raise ValueError(
                f"Simulation {self._simulation_id} does not have a chat model configured for character simulation"
            )

        connection_config = await self._db.config.get_connection_by_source(
            source_id=chat_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Chat model config {chat_config.id} does not have a connection configured"
            )

        llm = LlmService(
            model_config=chat_config,
            connection_config=connection_config,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ProposedAction,
            messages=prompt,
            data=perspective.model_dump(),
            repair_instruction="",
            run_name="character.propose_actions",
        )

        return result
