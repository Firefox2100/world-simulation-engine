from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import BackgroundCharacter, Character, Container, Equipment, InventoryEquipment, \
    InventoryStack, Item, ItemStack, Landmark, Location, SceneCoordinationResult, Simulation, StateCommitProposal, \
    World

from .simulator_component import SimulatorComponent


class LocatedCharacter(BaseModel):
    character: Character
    location: Location
    position: str | None = None
    landmark: Landmark | None = None


class LocatedBackgroundCharacter(BaseModel):
    character: BackgroundCharacter
    location: Location
    position: str | None = None
    landmark: Landmark | None = None


class LocatedItemStack(BaseModel):
    item: Item
    stack: ItemStack
    location: Location
    position: str | None = None
    owner_id: str | None = None


class LocatedEquipment(BaseModel):
    equipment: Equipment
    location: Location
    position: str | None = None
    owner_id: str | None = None


class LocatedContainer(BaseModel):
    container: Container
    location: Location
    position: str | None = None
    owner_id: str | None = None


class ActorStateCommitContext(BaseModel):
    actor: Character
    location: Location
    inventory: list[InventoryStack] = Field(default_factory=list)
    equipment: list[InventoryEquipment] = Field(default_factory=list)


class StateCommitterContext(BaseModel):
    world: World
    simulation: Simulation
    user_character_id: str | None = None
    user_input: str | None = None
    source: str

    coordination_result: SceneCoordinationResult

    actors: list[ActorStateCommitContext] = Field(default_factory=list)
    nearby_characters: list[LocatedCharacter] = Field(default_factory=list)
    nearby_background_characters: list[LocatedBackgroundCharacter] = Field(default_factory=list)
    nearby_items: list[LocatedItemStack] = Field(default_factory=list)
    nearby_equipment: list[LocatedEquipment] = Field(default_factory=list)
    nearby_containers: list[LocatedContainer] = Field(default_factory=list)
    nearby_landmarks: list[Landmark] = Field(default_factory=list)


class StateCommitter(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.STATE_COMMITTER

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             coordination_result: SceneCoordinationResult,
                             source: str,
                             user_input: str | None = None,
                             ) -> StateCommitterContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        user_character = await self._db.character.get_user_character_by_simulation(simulation_id)
        actor_ids = {
            accepted.actor_id
            for accepted in coordination_result.accepted_actions
        }
        if coordination_result.problem:
            actor_ids.update(coordination_result.problem.involved_actor_ids)

        actor_contexts = []
        actor_location_ids: set[str] = set()
        for actor_id in sorted(actor_ids):
            actor = await self._db.character.get_character(actor_id)
            if not actor:
                continue

            location = await self._db.location.get_location_by_character(actor_id)
            if not location:
                continue

            actor_location_ids.add(location.id)
            actor_contexts.append(
                ActorStateCommitContext(
                    actor=actor,
                    location=location,
                    inventory=await self._db.item.get_inventory(actor_id),
                    equipment=await self._db.equipment.get_equipment_inventory(actor_id),
                )
            )

        located_characters = []
        background_characters = []
        items = []
        equipment = []
        containers = []
        landmarks_by_id: dict[str, Landmark] = {}
        for location_id in actor_location_ids:
            located_characters.extend(await self._db.get_characters_in_location(location_id))
            background_characters.extend(await self._db.character.get_background_characters_by_location(location_id))
            items.extend(await self._db.item.get_stacks_by_location(location_id))
            equipment.extend(await self._db.equipment.get_equipment_by_location(location_id))
            containers.extend(await self._db.container.get_containers_by_location(location_id))
            for landmark in await self._db.location.get_landmarks_by_location(location_id):
                landmarks_by_id[landmark.id] = landmark

        return StateCommitterContext(
            world=world,
            simulation=simulation,
            user_character_id=user_character.id if user_character else None,
            user_input=user_input,
            source=source,
            coordination_result=coordination_result,
            actors=actor_contexts,
            nearby_characters=[
                LocatedCharacter(
                    character=character,
                    location=location,
                    position=position,
                    landmark=landmark,
                )
                for character, location, position, landmark in located_characters
            ],
            nearby_background_characters=[
                LocatedBackgroundCharacter(
                    character=character,
                    location=location,
                    position=position,
                    landmark=landmark,
                )
                for character, location, position, landmark in background_characters
            ],
            nearby_items=[
                LocatedItemStack(
                    item=item,
                    stack=stack,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for item, stack, location, position, owner_id in items
            ],
            nearby_equipment=[
                LocatedEquipment(
                    equipment=entry,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for entry, location, position, owner_id in equipment
            ],
            nearby_containers=[
                LocatedContainer(
                    container=container,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for container, location, position, owner_id in containers
            ],
            nearby_landmarks=list(landmarks_by_id.values()),
        )

    async def _commit_actions(self,
                              *,
                              world_id: str,
                              simulation_id: str,
                              coordination_result: SceneCoordinationResult,
                              source: str,
                              user_input: str | None = None,
                              run_name: str,
                              ) -> StateCommitProposal:
        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=coordination_result,
            source=source,
            user_input=user_input,
        )
        prompt = self._prepare_prompt(
            language=context.world.language,
            prompt_name="state_committer",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        return await llm.invoke_structured_with_repair(
            output_model=StateCommitProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return a valid StateCommitProposal only with top-level fields operations, unchanged_action_refs, "
                "and committer_notes. Every operation must use the current type discriminator shape: create, "
                "state_change, promote, relationship_change, or no_physical_change. Every operation must include "
                "a top-level reason. For state_change operations, every field_changes item must also include "
                "reason; a field-change reason does not replace the operation reason. Do not use wrappers such as "
                "state_commit_proposal, or legacy keys such as op, operation_type, change_type, entity_id, "
                "field_path, value, proposed_changes, or proposed_state_changes. Do not include deletion "
                "operations, events, memories, intent changes, narration, or database-write instructions."
            ),
            run_name=run_name,
        )

    async def commit_user_actions(self,
                                  *,
                                  world_id: str,
                                  simulation_id: str,
                                  coordination_result: SceneCoordinationResult,
                                  user_input: str | None = None,
                                  ) -> StateCommitProposal:
        return await self._commit_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=coordination_result,
            source="user",
            user_input=user_input,
            run_name="state_committer.commit_user_actions",
        )

    async def commit_character_actions(self,
                                       *,
                                       world_id: str,
                                       simulation_id: str,
                                       coordination_result: SceneCoordinationResult,
                                       user_input: str | None = None,
                                       ) -> StateCommitProposal:
        return await self._commit_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=coordination_result,
            source="character",
            user_input=user_input,
            run_name="state_committer.commit_character_actions",
        )
