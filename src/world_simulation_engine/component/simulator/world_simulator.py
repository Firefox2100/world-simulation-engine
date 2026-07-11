from langgraph.constants import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph
from pydantic import BaseModel

from world_simulation_engine.model import ActionValidationResult, World, Simulation, InputInterpretation
from world_simulation_engine.service import DatabaseService
from .action_validator import ActionValidator
from .input_interpreter import InputInterpreter


class WorldSimulatorState(BaseModel):
    world: World
    simulation: Simulation

    user_input: str | None

    input_interpretation: InputInterpretation | None = None
    user_action_validation: ActionValidationResult | None = None


class WorldSimulator:
    def __init__(self,
                 database: DatabaseService,
                 ):
        self._db = database

        self._action_validator = ActionValidator(database=database)
        self._input_interpreter = InputInterpreter(database=database)

        self._simulator_graph = self._build_simulator_graph()

    async def interpret_user_input(self, state: WorldSimulatorState):
        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        if not state.user_input:
            raise RuntimeError("No user input supplied")

        interpretation = await self._input_interpreter.interpret(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            character_id=user_character.id,
            user_input=state.user_input,
        )

        return {
            "input_interpretation": interpretation,
        }

    async def validate_user_action(self, state: WorldSimulatorState):
        if not state.input_interpretation:
            raise RuntimeError("No input interpretation supplied")

        if any(item.type == "ooc" for item in state.input_interpretation.items):
            # TODO: Handle OOC commands before validating user actions.
            raise NotImplementedError("OOC command handling is not implemented yet")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        actions = [
            item.action
            for item in state.input_interpretation.items
            if item.type == "action"
        ]
        validation = await self._action_validator.validate_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            character_id=user_character.id,
            actions=actions,
        )

        return {
            "user_action_validation": validation,
        }

    async def route_after_input(self, state: WorldSimulatorState):
        if state.user_input:
            return "interpret_user_input"

        # TODO: Implement system-continue generation when no user input is supplied.
        raise NotImplementedError("System-continue route is not implemented yet")

    async def route_after_input_interpretation(self, state: WorldSimulatorState):
        if not state.input_interpretation:
            raise RuntimeError("No input interpretation supplied")

        if any(item.type == "ooc" for item in state.input_interpretation.items):
            # TODO: Route OOC commands to their own handler.
            raise NotImplementedError("OOC command route is not implemented yet")

        return "validate_user_action"

    def _build_simulator_graph(self) -> CompiledStateGraph:
        graph = StateGraph(WorldSimulatorState)

        graph.add_node("interpret_user_input", self.interpret_user_input)
        graph.add_node("validate_user_action", self.validate_user_action)

        graph.add_conditional_edges(
            START,
            self.route_after_input,
        )
        graph.add_conditional_edges(
            "interpret_user_input",
            self.route_after_input_interpretation,
        )

        return graph.compile()
