import operator
from datetime import timedelta
from typing import Annotated
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SceneCoordinationStatus, TurnType
from world_simulation_engine.model import ActionValidationResult, World, Simulation, InputInterpretation, \
    ActionCandidateSet, ActionProposal, CharacterActionPlan, ProposedAction, SceneCoordinationResult, \
    MemorySummaryProposal, StateCommitProposal, Turn
from world_simulation_engine.service import DatabaseService
from .action_validator import ActionValidator
from .character_simulator import CharacterSimulator
from .input_interpreter import InputInterpreter
from .memory_summarizer import MemorySummarizer
from .narrator import Narrator
from .scene_coordinator import SceneCoordinator
from .state_committer import StateCommitter


class CharacterActionProposalRecord(BaseModel):
    character_id: str
    proposal: ActionProposal
    rework_attempt: int = Field(default=0, ge=0)


class CharacterActionValidationRecord(BaseModel):
    character_id: str
    proposal: ActionProposal
    validation: ActionValidationResult


class WorldSimulatorState(BaseModel):
    world: World
    simulation: Simulation

    user_input: str | None

    input_interpretation: InputInterpretation | None = None
    user_action_validation: ActionValidationResult | None = None
    user_action_coordination: SceneCoordinationResult | None = None

    character_actions: Annotated[
        list[CharacterActionProposalRecord],
        operator.add,
    ] = Field(default_factory=list)
    character_action_validations: Annotated[
        list[CharacterActionValidationRecord],
        operator.add,
    ] = Field(default_factory=list)
    character_action_coordination: SceneCoordinationResult | None = None
    narration: str | None = None
    committed_turn: Turn | None = None
    state_commit_proposal: StateCommitProposal | None = None
    memory_summary_proposal: MemorySummaryProposal | None = None


class CharacterActionProposalState(BaseModel):
    world_id: str
    simulation_id: str
    character_id: str
    user_input: str
    character_actions: Annotated[
        list[CharacterActionProposalRecord],
        operator.add,
    ] = Field(default_factory=list)
    character_action_validations: Annotated[
        list[CharacterActionValidationRecord],
        operator.add,
    ] = Field(default_factory=list)
    character_action_coordination: SceneCoordinationResult | None = None
    narration: str | None = None
    committed_turn: Turn | None = None
    state_commit_proposal: StateCommitProposal | None = None
    memory_summary_proposal: MemorySummaryProposal | None = None


class WorldSimulator:
    _MAX_VALIDATION_REWORK_ATTEMPTS = 3

    def __init__(self,
                 database: DatabaseService,
                 langfuse_handler: CallbackHandler | None = None,
                 ):
        self._db = database
        self._langfuse_handler = langfuse_handler

        self._action_validator = ActionValidator(database=database)
        self._character_simulator = CharacterSimulator(
            database=database,
            langfuse_handler=self._langfuse_handler
        )
        self._input_interpreter = InputInterpreter(database=database)
        self._memory_summarizer = MemorySummarizer(database=database)
        self._narrator = Narrator(database=database)
        self._scene_coordinator = SceneCoordinator(database=database)
        self._state_committer = StateCommitter(database=database)

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

    async def coordinate_user_actions(self, state: WorldSimulatorState):
        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        actions = self._allowed_actions_from_validation(state.user_action_validation)
        coordination = await self._scene_coordinator.coordinate_scene(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            action_plans=[
                CharacterActionPlan(
                    actor_id=user_character.id,
                    actions=actions,
                    candidate_sets=[
                        ActionCandidateSet(
                            action_index=action_index,
                            actions=[action],
                        )
                        for action_index, action in enumerate(actions)
                    ],
                )
            ],
        )

        return {
            "user_action_coordination": coordination,
        }

    async def propose_character_actions(self, state: CharacterActionProposalState):
        proposal = await self._character_simulator.propose_actions(
            world_id=state.world_id,
            simulation_id=state.simulation_id,
            character_id=state.character_id,
            user_input=state.user_input,
        )

        return {
            "character_actions": [
                CharacterActionProposalRecord(
                    character_id=state.character_id,
                    proposal=proposal,
                )
            ],
        }

    async def validate_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        validation_records = []
        for entry in state.character_actions:
            validation_records.append(
                await self._validate_character_action_with_rework(
                    world_id=world_id,
                    simulation_id=simulation_id,
                    user_input=state.user_input or "",
                    entry=entry,
                )
            )

        return {
            "character_action_validations": validation_records,
        }

    async def propose_scheduled_character_actions(self, state: WorldSimulatorState):
        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        location = await self._db.location.get_location_by_character(
            character_id=user_character.id
        )
        if not location:
            return {
                "character_actions": [],
            }

        # TODO: Replace this local-location activation with the time-based simulation scheduler.
        nearby_characters = await self._db.get_characters_in_location(
            root_location_id=location.id,
        )
        proposals = []
        for character, _, _, _ in nearby_characters:
            if character.id == user_character.id or character.user_controlled:
                continue

            proposal = await self._character_simulator.propose_actions(
                world_id=state.world.id,
                simulation_id=state.simulation.id,
                character_id=character.id,
                user_input=state.user_input or "",
            )
            proposals.append(
                CharacterActionProposalRecord(
                    character_id=character.id,
                    proposal=proposal,
                )
            )

        return {
            "character_actions": proposals,
        }

    async def coordinate_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_validations:
            raise RuntimeError("No character action validations supplied")

        coordination = await self._scene_coordinator.coordinate_scene(
            world_id=world_id,
            simulation_id=simulation_id,
            action_plans=self._character_action_plans_from_validations(state.character_action_validations),
        )

        return {
            "character_action_coordination": coordination,
        }

    async def narrate_turn(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        narration = await self._narrator.narrate_turn(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=state.character_action_coordination,
            user_input=state.user_input,
        )

        return {
            "narration": narration,
        }

    async def commit_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        if not state.narration:
            raise RuntimeError("No narration supplied")

        proposal = await self._state_committer.commit_character_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=state.character_action_coordination,
            user_input=state.user_input,
        )
        simulation = state.simulation if isinstance(state, WorldSimulatorState) else await self._require_simulation(simulation_id)
        turn, simulation = await self._create_turn_and_apply_commit(
            simulation=simulation,
            simulation_id=simulation_id,
            turn_type=TurnType.SYSTEM_RESPONSE if state.user_input else TurnType.SYSTEM_CONTINUE,
            content=state.narration,
            proposal=proposal,
            coordination_result=state.character_action_coordination,
        )
        return {
            "committed_turn": turn,
            "state_commit_proposal": proposal,
            "simulation": simulation,
        }

    async def commit_user_actions(self, state: WorldSimulatorState):
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        if not state.user_input:
            raise RuntimeError("No user input supplied")

        proposal = await self._state_committer.commit_user_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            coordination_result=state.user_action_coordination,
            user_input=state.user_input,
        )
        turn, simulation = await self._create_turn_and_apply_commit(
            simulation=state.simulation,
            simulation_id=state.simulation.id,
            turn_type=TurnType.USER_INPUT,
            content=state.user_input,
            proposal=proposal,
            coordination_result=state.user_action_coordination,
        )
        return {
            "committed_turn": turn,
            "state_commit_proposal": proposal,
            "simulation": simulation,
        }

    async def summarize_user_memory(self, state: WorldSimulatorState):
        if not state.committed_turn:
            raise RuntimeError("No committed turn supplied")
        if not state.state_commit_proposal:
            raise RuntimeError("No state commit proposal supplied")
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        proposal = await self._memory_summarizer.summarize_user_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            turn=state.committed_turn,
            coordination_result=state.user_action_coordination,
            state_commit=state.state_commit_proposal,
            user_input=state.user_input,
        )
        await self._db.memory_summary.apply_memory_summary_proposal(
            proposal=proposal,
            turn_id=state.committed_turn.id,
        )
        return {
            "memory_summary_proposal": proposal,
        }

    async def summarize_character_memory(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.committed_turn:
            raise RuntimeError("No committed turn supplied")
        if not state.state_commit_proposal:
            raise RuntimeError("No state commit proposal supplied")
        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        proposal = await self._memory_summarizer.summarize_character_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            turn=state.committed_turn,
            coordination_result=state.character_action_coordination,
            state_commit=state.state_commit_proposal,
            user_input=state.user_input,
            narration=state.narration,
        )
        await self._db.memory_summary.apply_memory_summary_proposal(
            proposal=proposal,
            turn_id=state.committed_turn.id,
        )
        return {
            "memory_summary_proposal": proposal,
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

    async def route_after_user_action_validation(self, state: WorldSimulatorState):
        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        if all(item.allowed for item in state.user_action_validation.validations):
            return "coordinate_user_actions"

        # TODO: Return validation failures to the user and wait for a revised input.
        raise NotImplementedError("Rejected user action route is not implemented yet")

    async def route_after_user_coordination(self, state: WorldSimulatorState):
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        return self._route_after_coordination(
            state.user_action_coordination,
            complete_route="commit_user_actions",
        )

    async def route_after_scheduled_character_actions(self, state: WorldSimulatorState):
        if state.character_actions:
            return "validate_character_actions"

        return END

    async def route_after_character_coordination(self, state: WorldSimulatorState | CharacterActionProposalState):
        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        return self._route_after_coordination(
            state.character_action_coordination,
            complete_route="narrate_turn",
        )

    @staticmethod
    def _proposal_candidates(proposal: ActionProposal) -> list[ProposedAction]:
        return [
            proposal.chosen_action,
            *proposal.alternatives_considered,
        ]

    async def _validate_character_action_with_rework(
            self,
            *,
            world_id: str,
            simulation_id: str,
            user_input: str,
            entry: CharacterActionProposalRecord,
    ) -> CharacterActionValidationRecord:
        current_entry = entry
        while True:
            validation_record = CharacterActionValidationRecord(
                character_id=current_entry.character_id,
                proposal=current_entry.proposal,
                validation=await self._action_validator.validate_actions(
                    world_id=world_id,
                    simulation_id=simulation_id,
                    character_id=current_entry.character_id,
                    actions=self._proposal_candidates(current_entry.proposal),
                ),
            )
            if self._allowed_actions_from_validation(validation_record.validation):
                return validation_record

            if current_entry.rework_attempt >= self._MAX_VALIDATION_REWORK_ATTEMPTS:
                raise RuntimeError(
                    f"Character {current_entry.character_id} did not propose a valid action after "
                    f"{self._MAX_VALIDATION_REWORK_ATTEMPTS} rework attempts"
                )

            proposal = await self._character_simulator.propose_actions(
                world_id=world_id,
                simulation_id=simulation_id,
                character_id=current_entry.character_id,
                user_input=self._character_rework_input(
                    user_input=user_input,
                    proposal=current_entry.proposal,
                    validation=validation_record.validation,
                    rework_attempt=current_entry.rework_attempt + 1,
                ),
            )
            current_entry = CharacterActionProposalRecord(
                character_id=current_entry.character_id,
                proposal=proposal,
                rework_attempt=current_entry.rework_attempt + 1,
            )

    @staticmethod
    def _character_rework_input(
            *,
            user_input: str,
            proposal: ActionProposal,
            validation: ActionValidationResult,
            rework_attempt: int,
    ) -> str:
        invalid_actions = [
            "\n".join(
                [
                    f"- action_index: {item.action_index}",
                    f"  label: {item.action.label}",
                    f"  reason: {item.reason}",
                    f"  blocking_conditions: {item.blocking_conditions}",
                    f"  warnings: {item.warnings}",
                ]
            )
            for item in validation.validations
            if not item.allowed
        ]
        feedback = "\n".join(invalid_actions) if invalid_actions else "- The previous proposal was not valid."
        return (
            f"{user_input}\n\n"
            f"## Previous action proposal failed validation, rework attempt {rework_attempt}\n\n"
            f"Treat this validator feedback as authoritative context and propose a different ActionProposal.\n"
            f"Do not repeat the invalid action unless the method, target, or immediate purpose meaningfully changes.\n\n"
            f"Failed proposal:\n"
            f"{proposal.model_dump_json(indent=2)}\n\n"
            f"Validation feedback:\n"
            f"{feedback}"
        )

    @staticmethod
    def _allowed_actions_from_validation(validation: ActionValidationResult) -> list[ProposedAction]:
        return [
            item.action
            for item in validation.validations
            if item.allowed
        ]

    def _character_action_plans_from_validations(
            self,
            validation_records: list[CharacterActionValidationRecord],
    ) -> list[CharacterActionPlan]:
        plans_by_actor: dict[str, CharacterActionPlan] = {}
        for record in validation_records:
            plan = plans_by_actor.setdefault(
                record.character_id,
                CharacterActionPlan(actor_id=record.character_id),
            )
            allowed_candidates = self._allowed_actions_from_validation(record.validation)
            if not allowed_candidates:
                continue

            action_index = len(plan.actions)
            plan.actions.append(allowed_candidates[0])
            plan.action_proposals.append(record.proposal)
            plan.candidate_sets.append(
                ActionCandidateSet(
                    action_index=action_index,
                    actions=allowed_candidates,
                )
            )

        return list(plans_by_actor.values())

    @staticmethod
    def _route_after_coordination(
            coordination: SceneCoordinationResult,
            *,
            complete_route: str,
    ) -> str:
        if coordination.status == SceneCoordinationStatus.COMPLETE:
            return complete_route

        if coordination.status == SceneCoordinationStatus.PROBLEM:
            if coordination.problem and coordination.problem.needs_user_decision:
                # TODO: Pause the scene and ask the user to resolve or react to the coordination problem.
                raise NotImplementedError("User-involved coordination problem route is not implemented yet")

            # TODO: Route non-user coordination problems into character reaction generation.
            raise NotImplementedError("Non-user coordination reaction route is not implemented yet")

        if coordination.status == SceneCoordinationStatus.STOPPED:
            # TODO: Commit or narrate a deliberately stopped scene once stop handling is designed.
            raise NotImplementedError("Stopped scene route is not implemented yet")

        raise ValueError(f"Unsupported coordination status: {coordination.status}")

    async def _create_turn_and_apply_commit(
            self,
            *,
            simulation: Simulation,
            simulation_id: str,
            turn_type: TurnType,
            content: str,
            proposal: StateCommitProposal,
            coordination_result: SceneCoordinationResult,
    ) -> tuple[Turn, Simulation]:
        turn = await self._db.turn.create_next_turn(
            source_id=simulation_id,
            turn=Turn(
                sequence=0,
                type=turn_type,
                content=content,
                start_time=simulation.current_time,
            ),
        )
        await self._db.state_commit.apply_state_commit_proposal(
            proposal=proposal,
            source_id=simulation_id,
            turn_id=turn.id,
        )
        advanced_time = simulation.current_time + timedelta(
            seconds=self._coordination_elapsed_seconds(coordination_result)
        )
        updated_simulation = await self._db.simulation.update_current_time(
            simulation_id=simulation_id,
            current_time=advanced_time,
        )
        return turn, updated_simulation

    async def _require_simulation(self, simulation_id: str) -> Simulation:
        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        return simulation

    @staticmethod
    def _coordination_elapsed_seconds(coordination: SceneCoordinationResult) -> int:
        if not coordination.accepted_actions:
            return 0

        return max(action.end_offset_seconds for action in coordination.accepted_actions)

    def _build_simulator_graph(self) -> CompiledStateGraph:
        graph = StateGraph(WorldSimulatorState)

        graph.add_node("interpret_user_input", self.interpret_user_input)
        graph.add_node("validate_user_action", self.validate_user_action)
        graph.add_node("coordinate_user_actions", self.coordinate_user_actions)
        graph.add_node("propose_scheduled_character_actions", self.propose_scheduled_character_actions)
        graph.add_node("propose_character_actions", self.propose_character_actions)
        graph.add_node("validate_character_actions", self.validate_character_actions)
        graph.add_node("coordinate_character_actions", self.coordinate_character_actions)
        graph.add_node("narrate_turn", self.narrate_turn)
        graph.add_node("commit_user_actions", self.commit_user_actions)
        graph.add_node("commit_character_actions", self.commit_character_actions)
        graph.add_node("summarize_user_memory", self.summarize_user_memory)
        graph.add_node("summarize_character_memory", self.summarize_character_memory)

        graph.add_conditional_edges(
            START,
            self.route_after_input,
        )
        graph.add_conditional_edges(
            "interpret_user_input",
            self.route_after_input_interpretation,
        )
        graph.add_conditional_edges(
            "validate_user_action",
            self.route_after_user_action_validation,
        )
        graph.add_conditional_edges(
            "coordinate_user_actions",
            self.route_after_user_coordination,
        )
        graph.add_edge("commit_user_actions", "summarize_user_memory")
        graph.add_edge("summarize_user_memory", "propose_scheduled_character_actions")
        graph.add_conditional_edges(
            "propose_scheduled_character_actions",
            self.route_after_scheduled_character_actions,
        )
        graph.add_edge("propose_character_actions", "validate_character_actions")
        graph.add_edge("validate_character_actions", "coordinate_character_actions")
        graph.add_conditional_edges(
            "coordinate_character_actions",
            self.route_after_character_coordination,
        )
        graph.add_edge("narrate_turn", "commit_character_actions")
        graph.add_edge("commit_character_actions", "summarize_character_memory")
        graph.add_edge("summarize_character_memory", END)

        return graph.compile()
