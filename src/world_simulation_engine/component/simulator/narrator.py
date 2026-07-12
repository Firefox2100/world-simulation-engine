from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Character, Location, SceneCoordinationResult, Simulation, World

from .simulator_component import SimulatorComponent


class NarrationActorContext(BaseModel):
    character: Character
    location: Location | None = None


class NarratorContext(BaseModel):
    world: World
    simulation: Simulation
    user_input: str | None = None
    user_character_id: str | None = None
    coordination_result: SceneCoordinationResult
    actors: list[NarrationActorContext] = Field(default_factory=list)


class Narrator(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.NARRATOR

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             coordination_result: SceneCoordinationResult,
                             user_input: str | None = None,
                             ) -> NarratorContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        user_character = await self._db.character.get_user_character_by_simulation(simulation_id)
        actor_ids = {
            action.actor_id
            for action in coordination_result.accepted_actions
        }
        actor_ids.update(
            action.actor_id
            for action in coordination_result.pending_actions
        )
        if coordination_result.problem:
            actor_ids.update(coordination_result.problem.involved_actor_ids)

        actors = []
        for actor_id in sorted(actor_ids):
            character = await self._db.character.get_character(actor_id)
            if not character:
                continue

            actors.append(
                NarrationActorContext(
                    character=character,
                    location=await self._db.location.get_location_by_character(actor_id),
                )
            )

        return NarratorContext(
            world=world,
            simulation=simulation,
            user_input=user_input,
            user_character_id=user_character.id if user_character else None,
            coordination_result=coordination_result,
            actors=actors,
        )

    async def narrate_turn(self,
                           *,
                           world_id: str,
                           simulation_id: str,
                           coordination_result: SceneCoordinationResult,
                           user_input: str | None = None,
                           ) -> str:
        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=coordination_result,
            user_input=user_input,
        )
        prompt = self._prepare_prompt(
            language=context.world.language,
            prompt_name="narrator",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        return await llm.invoke_text(
            messages=prompt,
            data=context.model_dump(),
            run_name="narrator.narrate_turn",
        )
