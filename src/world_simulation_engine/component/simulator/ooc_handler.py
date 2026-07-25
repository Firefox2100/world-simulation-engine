from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import BackgroundCharacter, Character, Container, Equipment, InventoryEquipment, \
    InventoryStack, Item, ItemStack, Landmark, Location, OOCCommand, OOCEvaluationResult, Simulation, World

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


class OOCCommandContextEntry(BaseModel):
    command_index: int
    command: OOCCommand


class OOCHandlerContext(BaseModel):
    world: World
    simulation: Simulation
    actor: Character
    location: Location

    inventory: list[InventoryStack] = Field(default_factory=list)
    equipment: list[InventoryEquipment] = Field(default_factory=list)

    perceived_characters: list[LocatedCharacter] = Field(default_factory=list)
    perceived_background_characters: list[LocatedBackgroundCharacter] = Field(default_factory=list)
    perceived_items: list[LocatedItemStack] = Field(default_factory=list)
    perceived_equipment: list[LocatedEquipment] = Field(default_factory=list)
    perceived_containers: list[LocatedContainer] = Field(default_factory=list)
    perceived_landmarks: list[Landmark] = Field(default_factory=list)

    commands: list[OOCCommandContextEntry] = Field(default_factory=list)


class OOCHandler(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.OOC_HANDLER

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             character_id: str,
                             commands: list[OOCCommand],
                             ) -> OOCHandlerContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        actor = await self._db.character.get_character(character_id)
        if not actor:
            raise ValueError(f"Character {character_id} not found in database")

        location = await self._db.location.get_location_by_character(character_id)
        if not location:
            raise ValueError(f"Character {character_id} is not in a location")

        inventory = await self._db.item.get_inventory(character_id)
        equipment = await self._db.equipment.get_equipment_inventory(character_id)
        characters = await self._db.get_characters_in_location(location.id)
        background_characters = await self._db.character.get_background_characters_by_location(location.id)
        items = await self._db.item.get_stacks_by_location(location.id)
        location_equipment = await self._db.equipment.get_equipment_by_location(location.id)
        containers = await self._db.container.get_containers_by_location(location.id)
        landmarks = await self._db.location.get_landmarks_by_location(location.id)

        return OOCHandlerContext(
            world=world,
            simulation=simulation,
            actor=actor,
            location=location,
            inventory=inventory,
            equipment=equipment,
            perceived_characters=[
                LocatedCharacter(
                    character=character,
                    location=character_location,
                    position=position,
                    landmark=landmark,
                )
                for character, character_location, position, landmark in characters
                if character.id != character_id
            ],
            perceived_background_characters=[
                LocatedBackgroundCharacter(
                    character=character,
                    location=character_location,
                    position=position,
                    landmark=landmark,
                )
                for character, character_location, position, landmark in background_characters
            ],
            perceived_items=[
                LocatedItemStack(
                    item=item,
                    stack=stack,
                    location=item_location,
                    position=position,
                    owner_id=owner_id,
                )
                for item, stack, item_location, position, owner_id in items
            ],
            perceived_equipment=[
                LocatedEquipment(
                    equipment=entry,
                    location=equipment_location,
                    position=position,
                    owner_id=owner_id,
                )
                for entry, equipment_location, position, owner_id in location_equipment
            ],
            perceived_containers=[
                LocatedContainer(
                    container=container,
                    location=container_location,
                    position=position,
                    owner_id=owner_id,
                )
                for container, container_location, position, owner_id in containers
            ],
            perceived_landmarks=landmarks,
            commands=[
                OOCCommandContextEntry(command_index=index, command=command)
                for index, command in enumerate(commands)
            ],
        )

    async def evaluate_commands(self,
                                *,
                                world_id: str,
                                simulation_id: str,
                                character_id: str,
                                commands: list[OOCCommand],
                                ) -> OOCEvaluationResult:
        if not commands:
            return OOCEvaluationResult(items=[], evaluator_notes=["No OOC commands were supplied."])

        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            character_id=character_id,
            commands=commands,
        )

        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=context.world.language,
            prompt_name="ooc_handler",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        result = await llm.invoke_structured_with_repair(
            output_model=OOCEvaluationResult,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return one valid OOCEvaluationResult JSON object only. Return exactly one evaluation item for "
                "every supplied command, preserving command_index and command_text. Use category "
                "world_state_mutation for direct world state edits and character_action_guide for directing a "
                "specific non-user character's next action. Only set consistent to true when every referenced "
                "entity is present in the supplied context or is a reasonable new creation."
            ),
            run_name="ooc_handler.evaluate_commands",
        )
        return self._restore_input_commands(result=result, commands=commands)

    @staticmethod
    def _restore_input_commands(
            *,
            result: OOCEvaluationResult,
            commands: list[OOCCommand],
    ) -> OOCEvaluationResult:
        items = []
        for item in result.items:
            if item.command_index < len(commands):
                items.append(
                    item.model_copy(
                        update={
                            "command_text": commands[item.command_index].command_text,
                        }
                    )
                )
            else:
                items.append(item)

        return result.model_copy(update={"items": items})
