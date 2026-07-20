from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType, SceneCoordinationStatus
from world_simulation_engine.model import BackgroundCharacter, Character, CharacterActionPlan, Container, Equipment, \
    InventoryEquipment, InventoryStack, Item, ItemStack, Landmark, Location, PendingSceneAction, ProposedAction, \
    ReactionHistoryEntry, SceneCoordinationResult, Simulation, World

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


class ActorCoordinationContext(BaseModel):
    actor: Character
    location: Location
    inventory: list[InventoryStack] = Field(default_factory=list)
    equipment: list[InventoryEquipment] = Field(default_factory=list)


class SceneCoordinatorContext(BaseModel):
    world: World
    simulation: Simulation
    user_character_id: str | None = None

    action_plans: list[CharacterActionPlan] = Field(default_factory=list)
    reaction_history: list[ReactionHistoryEntry] = Field(default_factory=list)
    accepted_history: list[str] = Field(default_factory=list)

    actors: list[ActorCoordinationContext] = Field(default_factory=list)
    perceived_characters: list[LocatedCharacter] = Field(default_factory=list)
    perceived_background_characters: list[LocatedBackgroundCharacter] = Field(default_factory=list)
    perceived_items: list[LocatedItemStack] = Field(default_factory=list)
    perceived_equipment: list[LocatedEquipment] = Field(default_factory=list)
    perceived_containers: list[LocatedContainer] = Field(default_factory=list)
    perceived_landmarks: list[Landmark] = Field(default_factory=list)


class SceneCoordinator(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.SCENE_COORDINATOR

    @staticmethod
    def _planned_action_candidates_by_ref(
            action_plans: list[CharacterActionPlan],
    ) -> dict[tuple[str, int], list[ProposedAction]]:
        planned_actions = {}
        for plan in action_plans:
            if plan.candidate_sets:
                for candidate_set in plan.candidate_sets:
                    planned_actions[(plan.actor_id, candidate_set.proposal_index)] = candidate_set.actions
            elif plan.actions:
                planned_actions[(plan.actor_id, 0)] = plan.actions

        return planned_actions

    @staticmethod
    def _hydrate_result_action(
            action: ProposedAction,
            sequence: list[ProposedAction] | None,
            action_index: int,
            all_sequences: dict[int, list[ProposedAction]] | None = None,
    ) -> ProposedAction | None:
        if sequence and action_index < len(sequence):
            planned_action = sequence[action_index]
            if planned_action.type == action.type and planned_action.label == action.label:
                return planned_action

        for candidate_sequence in (all_sequences or {}).values():
            if action_index >= len(candidate_sequence):
                continue
            candidate = candidate_sequence[action_index]
            if candidate.type == action.type and candidate.label == action.label:
                return candidate

        if sequence and action_index < len(sequence):
            return sequence[action_index]

        return None

    @staticmethod
    def _pending_actions_for_empty_coordination(action_plans: list[CharacterActionPlan]) -> list[PendingSceneAction]:
        return [
            PendingSceneAction(
                actor_id=plan.actor_id,
                action_index=action_index,
                action=action,
                reason="No coordination was performed.",
            )
            for plan in action_plans
            for action_index, action in enumerate(plan.actions)
        ]

    @classmethod
    def _hydrate_result_actions(cls,
                                result: SceneCoordinationResult,
                                action_plans: list[CharacterActionPlan],
                                ) -> SceneCoordinationResult:
        planned_actions = cls._planned_action_candidates_by_ref(action_plans)
        accepted_actions = []
        pending_actions = []
        notes = list(result.coordinator_notes)
        for accepted in result.accepted_actions:
            actor_sequences = {
                proposal_index: sequence
                for (actor_id, proposal_index), sequence in planned_actions.items()
                if actor_id == accepted.actor_id
            }
            action = cls._hydrate_result_action(
                accepted.action,
                planned_actions.get((accepted.actor_id, accepted.proposal_index)),
                accepted.action_index,
                actor_sequences,
            )
            if action is None:
                notes.append(
                    f"Dropped coordinator-authored accepted action for {accepted.actor_id} "
                    f"proposal {accepted.proposal_index} action {accepted.action_index}."
                )
                continue

            accepted_actions.append(
                accepted.model_copy(update={"action": action})
            )

        for pending in result.pending_actions:
            actor_sequences = {
                proposal_index: sequence
                for (actor_id, proposal_index), sequence in planned_actions.items()
                if actor_id == pending.actor_id
            }
            action = cls._hydrate_result_action(
                pending.action,
                planned_actions.get((pending.actor_id, pending.proposal_index)),
                pending.action_index,
                actor_sequences,
            )
            if action is None:
                notes.append(
                    f"Dropped coordinator-authored pending action for {pending.actor_id} "
                    f"proposal {pending.proposal_index} action {pending.action_index}."
                )
                continue

            pending_actions.append(
                pending.model_copy(update={"action": action})
            )

        if (
                accepted_actions == result.accepted_actions
                and pending_actions == result.pending_actions
                and notes == result.coordinator_notes
        ):
            return result

        return result.model_copy(
            update={
                "accepted_actions": accepted_actions,
                "pending_actions": pending_actions,
                "coordinator_notes": notes,
            }
        )

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             action_plans: list[CharacterActionPlan],
                             reaction_history: list[ReactionHistoryEntry] | None = None,
                             accepted_history: list[str] | None = None,
                             ) -> SceneCoordinatorContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        user_character = await self._db.character.get_user_character_by_simulation(simulation_id)
        actor_contexts = []
        actor_location_ids: set[str] = set()
        for plan in action_plans:
            actor = await self._db.character.get_character(plan.actor_id)
            if not actor:
                raise ValueError(f"Character {plan.actor_id} not found in database")

            location = await self._db.location.get_location_by_character(actor.id)
            if not location:
                raise ValueError(f"Character {actor.id} is not in a location")

            actor_location_ids.add(location.id)
            actor_contexts.append(
                ActorCoordinationContext(
                    actor=actor,
                    location=location,
                    inventory=await self._db.item.get_inventory(actor.id),
                    equipment=await self._db.equipment.get_equipment_inventory(actor.id),
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

        planned_actor_ids = {plan.actor_id for plan in action_plans}

        return SceneCoordinatorContext(
            world=world,
            simulation=simulation,
            user_character_id=user_character.id if user_character else None,
            action_plans=action_plans,
            reaction_history=reaction_history or [],
            accepted_history=accepted_history or [],
            actors=actor_contexts,
            perceived_characters=[
                LocatedCharacter(
                    character=character,
                    location=location,
                    position=position,
                    landmark=landmark,
                )
                for character, location, position, landmark in located_characters
                if character.id not in planned_actor_ids
            ],
            perceived_background_characters=[
                LocatedBackgroundCharacter(
                    character=character,
                    location=location,
                    position=position,
                    landmark=landmark,
                )
                for character, location, position, landmark in background_characters
            ],
            perceived_items=[
                LocatedItemStack(
                    item=item,
                    stack=stack,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for item, stack, location, position, owner_id in items
            ],
            perceived_equipment=[
                LocatedEquipment(
                    equipment=entry,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for entry, location, position, owner_id in equipment
            ],
            perceived_containers=[
                LocatedContainer(
                    container=container,
                    location=location,
                    position=position,
                    owner_id=owner_id,
                )
                for container, location, position, owner_id in containers
            ],
            perceived_landmarks=list(landmarks_by_id.values()),
        )

    async def coordinate_scene(self,
                               *,
                               world_id: str,
                               simulation_id: str,
                               action_plans: list[CharacterActionPlan],
                               reaction_history: list[ReactionHistoryEntry] | None = None,
                               accepted_history: list[str] | None = None,
                               ) -> SceneCoordinationResult:
        if not action_plans:
            return SceneCoordinationResult(
                status=SceneCoordinationStatus.COMPLETE,
                accepted_actions=[],
                pending_actions=[],
                coordinator_notes=["No action plans were supplied for coordination."],
            )

        if not any(plan.actions for plan in action_plans):
            return SceneCoordinationResult(
                status=SceneCoordinationStatus.COMPLETE,
                accepted_actions=[],
                pending_actions=self._pending_actions_for_empty_coordination(action_plans),
                coordinator_notes=["No proposed actions were supplied for coordination."],
            )

        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            action_plans=action_plans,
            reaction_history=reaction_history,
            accepted_history=accepted_history,
        )
        prompt = self._prepare_prompt(
            language=context.world.language,
            prompt_name="scene_coordinator",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        result = await llm.invoke_structured_with_repair(
            output_model=SceneCoordinationResult,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return a valid SceneCoordinationResult. Preserve action references by actor_id, proposal_index, "
                "and action_index. Do not rewrite nested action payloads. "
                "Do not call for character reactions or continue the loop inside this component."
            ),
            run_name="scene_coordinator.coordinate_scene",
        )
        return self._hydrate_result_actions(result, action_plans)
