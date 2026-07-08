import operator
from typing import Annotated
from langchain_core.runnables import RunnableConfig
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph
from langgraph.types import Send
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import PerceivedEntity, PerceivedCharacter, PerceivedBackgroundCharacter, \
    PerceivedItem, PerceivedEquipment, PerceivedLandmark, PerceivedContainer, Character, BackgroundCharacter, Location, \
    World, Simulation, Landmark, Item, ItemStack, Equipment, Container
from world_simulation_engine.service import DatabaseService
from .simulator_component import SimulatorComponent


class ResolveGraphState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    location: Location

    perceived_characters: Annotated[
        list[PerceivedCharacter],
        operator.add,
    ] = Field(default_factory=list)
    perceived_background_characters: Annotated[
        list[PerceivedBackgroundCharacter],
        operator.add,
    ] = Field(default_factory=list)
    perceived_items: Annotated[
        list[PerceivedItem],
        operator.add,
    ] = Field(default_factory=list)
    perceived_equipment: Annotated[
        list[PerceivedEquipment],
        operator.add,
    ] = Field(default_factory=list)
    perceived_containers: Annotated[
        list[PerceivedContainer],
        operator.add,
    ] = Field(default_factory=list)
    perceived_landmarks: Annotated[
        list[PerceivedLandmark],
        operator.add,
    ] = Field(default_factory=list)


class ResolvePerceivedCharacterState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    target: Character
    target_location: Location
    target_position: str | None = None
    target_landmark: Landmark | None = None


class BackgroundCharacterStatus(BaseModel):
    character: BackgroundCharacter
    location: Location
    position: str | None = None
    landmark: Landmark | None = None


class ResolvePerceivedBackgroundCharacterState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    characters: list[BackgroundCharacterStatus]


class BackgroundCharacterPerception(PerceivedEntity):
    character_id: str
    relation_to_actor: str | None = None


class BackgroundCharacterPerceptionResult(BaseModel):
    characters: list[BackgroundCharacterPerception]


class ItemStatus(BaseModel):
    item: Item
    stack: ItemStack
    location: Location
    position: str | None = None
    owner_id: str | None = None


class ResolvePerceivedItemState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    items: list[ItemStatus]


class ItemPerception(PerceivedEntity):
    stack_id: str


class ItemPerceptionResult(BaseModel):
    items: list[ItemPerception]


class EquipmentStatus(BaseModel):
    equipment: Equipment
    location: Location
    position: str | None = None
    owner_id: str | None = None


class ResolvePerceivedEquipmentState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    equipment: list[EquipmentStatus]


class EquipmentPerception(PerceivedEntity):
    equipment_id: str


class EquipmentPerceptionResult(BaseModel):
    equipment: list[EquipmentPerception]


class ContainerStatus(BaseModel):
    container: Container
    location: Location
    position: str | None = None
    owner_id: str | None = None


class ResolvePerceivedContainerState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    containers: list[ContainerStatus]


class ContainerPerception(PerceivedEntity):
    container_id: str


class ContainerPerceptionResult(BaseModel):
    containers: list[ContainerPerception]


class LandmarkStatus(BaseModel):
    landmark: Landmark
    location: Location


class ResolvePerceivedLandmarkState(BaseModel):
    world: World
    simulation: Simulation
    observer: Character
    observer_location: Location

    landmarks: list[LandmarkStatus]


class LandmarkPerception(PerceivedEntity):
    landmark_id: str


class LandmarkPerceptionResult(BaseModel):
    landmarks: list[LandmarkPerception]


class PerspectiveResolver(SimulatorComponent):
    """
    This component finds all the element that a character can see in a scene. It's designed to use different
    data sources for future extension
    """

    COMPONENT_TYPE = ComponentType.PERSPECTIVE_RESOLVER

    def __init__(self,
                 database: DatabaseService,
                 langfuse_handler: CallbackHandler,
                 ):
        super().__init__(database)
        self._langfuse_handler = langfuse_handler

        self._resolve_graph = self._graph_resolve_graph()

    async def _resolve_perceived_character(self, state: ResolvePerceivedCharacterState):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "target": state.target,
            "target_location": state.target_location,
            "target_position": state.target_position,
            "target_landmark": state.target_landmark,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_character",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=PerceivedEntity,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_character",
        )

        return {
            "perceived_characters": [
                PerceivedCharacter(
                    character=state.target,
                    relation_to_actor="",
                    visibility=result.visibility,
                    distance_hint=result.distance_hint,
                    affordances=result.affordances,
                    salience=result.salience,
                    notes=result.notes,
                )
            ]
        }

    async def _resolve_perceived_background_characters(self,
                                                       state: ResolvePerceivedBackgroundCharacterState,
                                                       ):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "background_characters": state.characters,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_background_characters",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=BackgroundCharacterPerceptionResult,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_background_characters",
        )

        statuses_by_id = {
            status.character.id: status
            for status in state.characters
        }

        return {
            "perceived_background_characters": [
                PerceivedBackgroundCharacter(
                    character=statuses_by_id[character.character_id].character,
                    relation_to_actor=character.relation_to_actor,
                    visibility=character.visibility,
                    distance_hint=character.distance_hint,
                    affordances=character.affordances,
                    salience=character.salience,
                    notes=character.notes,
                )
                for character in result.characters
                if character.character_id in statuses_by_id
            ]
        }

    async def _resolve_perceived_items(self,
                                       state: ResolvePerceivedItemState,
                                       ):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "items": state.items,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_items",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ItemPerceptionResult,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_items",
        )

        statuses_by_id = {
            status.stack.id: status
            for status in state.items
        }

        return {
            "perceived_items": [
                PerceivedItem(
                    item=statuses_by_id[item.stack_id].item,
                    stack=statuses_by_id[item.stack_id].stack,
                    owned_by_actor=statuses_by_id[item.stack_id].owner_id == state.observer.id,
                    visibility=item.visibility,
                    distance_hint=item.distance_hint,
                    affordances=item.affordances,
                    salience=item.salience,
                    notes=item.notes,
                )
                for item in result.items
                if item.stack_id in statuses_by_id
            ]
        }

    async def _resolve_perceived_equipment(self,
                                          state: ResolvePerceivedEquipmentState,
                                          ):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "equipment": state.equipment,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_equipment",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=EquipmentPerceptionResult,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_equipment",
        )

        statuses_by_id = {
            status.equipment.id: status
            for status in state.equipment
        }

        return {
            "perceived_equipment": [
                PerceivedEquipment(
                    equipment=statuses_by_id[equipment.equipment_id].equipment,
                    owned_by_actor=statuses_by_id[equipment.equipment_id].owner_id == state.observer.id,
                    visibility=equipment.visibility,
                    distance_hint=equipment.distance_hint,
                    affordances=equipment.affordances,
                    salience=equipment.salience,
                    notes=equipment.notes,
                )
                for equipment in result.equipment
                if equipment.equipment_id in statuses_by_id
            ]
        }

    async def _resolve_perceived_containers(self,
                                           state: ResolvePerceivedContainerState,
                                           ):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "containers": state.containers,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_containers",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ContainerPerceptionResult,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_containers",
        )

        statuses_by_id = {
            status.container.id: status
            for status in state.containers
        }

        return {
            "perceived_containers": [
                PerceivedContainer(
                    container=statuses_by_id[container.container_id].container,
                    owned_by_actor=statuses_by_id[container.container_id].owner_id == state.observer.id,
                    visibility=container.visibility,
                    distance_hint=container.distance_hint,
                    affordances=container.affordances,
                    salience=container.salience,
                    notes=container.notes,
                )
                for container in result.containers
                if container.container_id in statuses_by_id
            ]
        }

    async def _resolve_perceived_landmarks(self,
                                          state: ResolvePerceivedLandmarkState,
                                          ):
        data = {
            "observer": state.observer,
            "current_location": state.observer_location,
            "landmarks": state.landmarks,
        }

        prompt = self._prepare_prompt(
            language=state.world.language,
            prompt_name="resolve_perceived_landmarks",
        )

        llm = await self._prepare_llm_service(
            simulation_id=state.simulation.id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=LandmarkPerceptionResult,
            messages=prompt,
            data=data,
            repair_instruction="",
            run_name="perspective.resolve_landmarks",
        )

        statuses_by_id = {
            status.landmark.id: status
            for status in state.landmarks
        }

        return {
            "perceived_landmarks": [
                PerceivedLandmark(
                    landmark=statuses_by_id[landmark.landmark_id].landmark,
                    visibility=landmark.visibility,
                    distance_hint=landmark.distance_hint,
                    affordances=landmark.affordances,
                    salience=landmark.salience,
                    notes=landmark.notes,
                )
                for landmark in result.landmarks
                if landmark.landmark_id in statuses_by_id
            ]
        }

    def _graph_resolve_graph(self) -> CompiledStateGraph:
        graph = StateGraph(ResolveGraphState)

        graph.add_node("resolve_perceived_character", self._resolve_perceived_character)
        graph.add_node("resolve_perceived_background_characters", self._resolve_perceived_background_characters)
        graph.add_node("resolve_perceived_items", self._resolve_perceived_items)
        graph.add_node("resolve_perceived_equipment", self._resolve_perceived_equipment)
        graph.add_node("resolve_perceived_containers", self._resolve_perceived_containers)
        graph.add_node("resolve_perceived_landmarks", self._resolve_perceived_landmarks)

        async def route_after_start(state: ResolveGraphState):
            result = []
            characters = await self._db.get_characters_in_location(state.location.id)
            for character, location, position, landmark in characters:
                result.append(Send(
                    "resolve_perceived_character",
                    ResolvePerceivedCharacterState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        target=character,
                        target_location=location,
                        target_position=position,
                        target_landmark=landmark,
                    )
                ))

            background_characters = await self._db.character.get_background_characters_by_location(
                location_id=state.location.id,
            )
            if background_characters:
                result.append(Send(
                    "resolve_perceived_background_characters",
                    ResolvePerceivedBackgroundCharacterState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        characters=[
                            BackgroundCharacterStatus(
                                character=character,
                                location=location,
                                position=position,
                                landmark=landmark,
                            )
                            for character, location, position, landmark in background_characters
                        ],
                    )
                ))

            items = await self._db.item.get_stacks_by_location(location_id=state.location.id)
            if items:
                result.append(Send(
                    "resolve_perceived_items",
                    ResolvePerceivedItemState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        items=[
                            ItemStatus(
                                item=item,
                                stack=stack,
                                location=location,
                                position=position,
                                owner_id=owner_id,
                            )
                            for item, stack, location, position, owner_id in items
                        ],
                    )
                ))

            equipment = await self._db.equipment.get_equipment_by_location(location_id=state.location.id)
            if equipment:
                result.append(Send(
                    "resolve_perceived_equipment",
                    ResolvePerceivedEquipmentState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        equipment=[
                            EquipmentStatus(
                                equipment=entry,
                                location=location,
                                position=position,
                                owner_id=owner_id,
                            )
                            for entry, location, position, owner_id in equipment
                        ],
                    )
                ))

            containers = await self._db.container.get_containers_by_location(location_id=state.location.id)
            if containers:
                result.append(Send(
                    "resolve_perceived_containers",
                    ResolvePerceivedContainerState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        containers=[
                            ContainerStatus(
                                container=container,
                                location=location,
                                position=position,
                                owner_id=owner_id,
                            )
                            for container, location, position, owner_id in containers
                        ],
                    )
                ))

            landmarks = await self._db.location.get_landmarks_by_location(location_id=state.location.id)
            if landmarks:
                result.append(Send(
                    "resolve_perceived_landmarks",
                    ResolvePerceivedLandmarkState(
                        world=state.world,
                        simulation=state.simulation,
                        observer=state.observer,
                        observer_location=state.location,
                        landmarks=[
                            LandmarkStatus(landmark=landmark, location=state.location)
                            for landmark in landmarks
                        ],
                    )
                ))

            return result or END

        graph.add_conditional_edges(
            START,
            route_after_start
        )
        graph.add_edge("resolve_perceived_character", END)
        graph.add_edge("resolve_perceived_background_characters", END)
        graph.add_edge("resolve_perceived_items", END)
        graph.add_edge("resolve_perceived_equipment", END)
        graph.add_edge("resolve_perceived_containers", END)
        graph.add_edge("resolve_perceived_landmarks", END)

        return graph.compile()

    async def _resolve_perceived_entity_in_graph(self,
                                                 world: World,
                                                 simulation: Simulation,
                                                 observer: Character,
                                                 location: Location,
                                                 thread_id: str | None = None,
                                                 ) -> ResolveGraphState:
        result = await self._resolve_graph.ainvoke(
            {
                "world": world,
                "simulation": simulation,
                "observer": observer,
                "location": location
            },
            config=RunnableConfig(
                callbacks=[self._langfuse_handler],
                configurable={
                    "thread_id": thread_id,
                },
                run_name="resolve_perceived_entity_in_graph",
            )
        )

        return ResolveGraphState.model_validate(result)

    async def resolve_perceived_entities(self,
                                         world_id: str,
                                         simulation_id: str,
                                         character_id: str,
                                         thread_id: str | None = None,
                                         ) -> ResolveGraphState:
        # For now, only graph resolution is supported
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        observer = await self._db.character.get_character(character_id)
        if not observer:
            raise ValueError(f"Character {character_id} not found in database")

        location = await self._db.location.get_location_by_character(character_id)
        if not location:
            raise ValueError(f"Character {character_id} is not in a location")

        return await self._resolve_perceived_entity_in_graph(
            world=world,
            simulation=simulation,
            observer=observer,
            location=location,
            thread_id=thread_id,
        )
