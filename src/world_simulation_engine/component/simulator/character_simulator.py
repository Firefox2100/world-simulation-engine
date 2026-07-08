from datetime import datetime
from typing import Optional
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import Salience, Visibility, ComponentType
from world_simulation_engine.model import PromptMessage, ProposedAction, Character, Location, InventoryStack, \
    InventoryEquipment, Simulation, World
from world_simulation_engine.service import DatabaseService, LlmService
from .simulator_component import SimulatorComponent
from .perspective_resolver import PerspectiveResolver


class EntityRef(BaseModel):
    id: str
    kind: str = Field(description="character, item, landmark, location, event, etc.")
    name: str


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
    world_time: datetime = Field(
        ...,
        description="The current time in the simulation"
    )
    location: Location = Field(
        ...,
        description="The current location the character is in"
    )

    inventory: list[InventoryStack] = Field(
        default_factory=list,
        description="The items this character holds"
    )
    equipment: list[InventoryEquipment] = Field(
        default_factory=list,
        description="The equipment this character is wearing or holding"
    )

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


class CharacterSimulator(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.CHARACTER_SIMULATOR

    def __init__(self,
                 database: DatabaseService,
                 langfuse_handler: CallbackHandler,
                 ):
        super().__init__(database)

        self._perspective_resolver = PerspectiveResolver(
            database=database,
            langfuse_handler=langfuse_handler
        )

    async def _build_perspective(self,
                                 world: World,
                                 simulation: Simulation,
                                 character: Character,
                                 thread_id: str | None = None,
                                 ) -> CharacterPerspective:
        location = await self._db.location.get_location_by_character(character.id)
        if not location:
            raise ValueError(f"Character {character.id} is not in a location")

        inventory = await self._db.item.get_inventory(character.id)
        equipment = await self._db.equipment.get_equipment_inventory(character.id)

        perspective = await self._perspective_resolver.resolve_perceived_entities(
            world_id=world.id,
            simulation_id=simulation.id,
            character_id=character.id,
            thread_id=thread_id,
        )

        return CharacterPerspective(
            actor=character,
            world_time=simulation.current_time,
            location=location,
            inventory=inventory,
            equipment=equipment,
        )

    async def propose_actions(self,
                              world_id: str,
                              simulation_id: str,
                              character_id: str,
                              thread_id: str | None = None,
                              ) -> ProposedAction:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        character = await self._db.character.get_character(character_id)
        if not character:
            raise ValueError(f"Character {character_id} not found in database")

        perspective = await self._build_perspective(
            world=world,
            simulation=simulation,
            character=character,
            thread_id=thread_id,
        )

        prompt = self._prepare_prompt(
            language=world.language,
            prompt_name="action_proposal",
        )

        llm = await self._prepare_llm_service(
            simulation_id=simulation_id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ProposedAction,
            messages=prompt,
            data=perspective.model_dump(),
            repair_instruction="",
            run_name="character.propose_actions",
        )

        return result
