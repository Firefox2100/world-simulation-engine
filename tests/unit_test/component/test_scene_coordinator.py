import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ActionType, SceneCoordinationStatus, SupportedLanguage
from world_simulation_engine.model import ActionCandidateSet, Character, CharacterActionPlan, CurrentActivity, Landmark, \
    Location, ProposedAction, SceneCoordinationResult, Simulation, World


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )


def make_simulation() -> Simulation:
    return Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def make_character(character_id: str = "character_1") -> Character:
    return Character(
        id=character_id,
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="A character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )


def make_action() -> ProposedAction:
    return ProposedAction(
        type=ActionType.LOOK,
        label="look_around",
        target_ids=[],
        intended_duration_seconds=2,
        interruptible=True,
    )


def make_database(
        *,
        world: World | None = None,
        simulation: Simulation | None = None,
        character: Character | None = None,
        location: Location | None = None,
) -> Mock:
    world = world or make_world()
    simulation = simulation or make_simulation()
    character = character or make_character()
    location = location or Location(
        id="location_1",
        name="Room",
        description="A small room",
    )
    database = Mock()
    database.entity_relationship.list_relationships = AsyncMock(return_value=[])
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=location)
    database.item.get_inventory = AsyncMock(return_value=[])
    database.equipment.get_equipment_inventory = AsyncMock(return_value=[])
    database.get_characters_in_location = AsyncMock(return_value=[])
    database.character.get_background_characters_by_location = AsyncMock(return_value=[])
    database.item.get_stacks_by_location = AsyncMock(return_value=[])
    database.equipment.get_equipment_by_location = AsyncMock(return_value=[])
    database.container.get_containers_by_location = AsyncMock(return_value=[])
    database.location.get_landmarks_by_location = AsyncMock(return_value=[])
    return database


async def test_coordinate_scene_returns_complete_without_llm_for_no_plans():
    coordinator = SceneCoordinator(database=Mock())
    coordinator._prepare_llm_service = AsyncMock()

    result = await coordinator.coordinate_scene(
        world_id="world_1",
        simulation_id="simulation_1",
        action_plans=[],
    )

    assert result.status == SceneCoordinationStatus.COMPLETE
    assert result.accepted_actions == []
    assert result.pending_actions == []
    coordinator._prepare_llm_service.assert_not_called()


async def test_coordinate_scene_returns_pending_without_llm_when_plans_have_no_actions():
    coordinator = SceneCoordinator(database=Mock())
    coordinator._prepare_llm_service = AsyncMock()

    result = await coordinator.coordinate_scene(
        world_id="world_1",
        simulation_id="simulation_1",
        action_plans=[
            CharacterActionPlan(actor_id="character_1"),
            CharacterActionPlan(actor_id="character_2"),
        ],
    )

    assert result.status == SceneCoordinationStatus.COMPLETE
    assert result.accepted_actions == []
    assert result.pending_actions == []
    assert result.coordinator_notes == ["No proposed actions were supplied for coordination."]
    coordinator._prepare_llm_service.assert_not_called()


def test_pending_actions_for_empty_coordination_preserves_actor_and_action_indexes():
    first_action = make_action()
    second_action = ProposedAction(
        type=ActionType.WAIT,
        label="wait",
        target_ids=[],
        intended_duration_seconds=5,
        interruptible=True,
    )

    pending = SceneCoordinator._pending_actions_for_empty_coordination(
        [
            CharacterActionPlan(actor_id="character_1", actions=[first_action, second_action]),
            CharacterActionPlan(actor_id="character_2", actions=[second_action]),
        ]
    )

    assert [(action.actor_id, action.action_index, action.action.label) for action in pending] == [
        ("character_1", 0, "look_around"),
        ("character_1", 1, "wait"),
        ("character_2", 0, "wait"),
    ]
    assert {action.reason for action in pending} == {"No coordination was performed."}


async def test_build_context_fetches_actor_and_scene_state():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    location = Location(
        id="location_1",
        name="Room",
        description="A small room",
    )
    action_plan = CharacterActionPlan(
        actor_id=character.id,
        actions=[make_action()],
    )

    database = Mock()
    database.entity_relationship.list_relationships = AsyncMock(return_value=[])
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=location)
    database.item.get_inventory = AsyncMock(return_value=[])
    database.equipment.get_equipment_inventory = AsyncMock(return_value=[])
    database.get_characters_in_location = AsyncMock(return_value=[])
    database.character.get_background_characters_by_location = AsyncMock(return_value=[])
    database.item.get_stacks_by_location = AsyncMock(return_value=[])
    database.equipment.get_equipment_by_location = AsyncMock(return_value=[])
    database.container.get_containers_by_location = AsyncMock(return_value=[])
    database.location.get_landmarks_by_location = AsyncMock(return_value=[])
    coordinator = SceneCoordinator(database=database)

    context = await coordinator._build_context(
        world_id=world.id,
        simulation_id=simulation.id,
        action_plans=[action_plan],
    )

    assert context.world == world
    assert context.simulation == simulation
    assert context.user_character_id == character.id
    assert context.action_plans == [action_plan]
    assert context.actors[0].actor == character
    assert context.actors[0].location == location
    assert context.actors[0].relationships == []
    database.entity_relationship.list_relationships.assert_awaited_once()
    relationship_call = database.entity_relationship.list_relationships.await_args.kwargs
    assert relationship_call["perspective_character_id"] == character.id


async def test_build_context_deduplicates_landmarks_and_excludes_planned_characters_from_perceived_list():
    world = make_world()
    simulation = make_simulation()
    actor_1 = make_character("character_1")
    actor_2 = make_character("character_2")
    by_id = {
        actor_1.id: actor_1,
        actor_2.id: actor_2,
    }
    location_1 = Location(id="location_1", name="Room 1", description="The first room")
    location_2 = Location(id="location_2", name="Room 2", description="The second room")
    by_location = {
        actor_1.id: location_1,
        actor_2.id: location_2,
    }
    observer = make_character("observer_1")
    shared_landmark = Landmark(id="landmark_1", name="Clock", description="A brass clock")

    database = Mock()
    database.entity_relationship.list_relationships = AsyncMock(return_value=[])
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=actor_1)
    database.character.get_character = AsyncMock(side_effect=lambda actor_id: by_id[actor_id])
    database.location.get_location_by_character = AsyncMock(side_effect=lambda actor_id: by_location[actor_id])
    database.item.get_inventory = AsyncMock(return_value=[])
    database.equipment.get_equipment_inventory = AsyncMock(return_value=[])
    database.get_characters_in_location = AsyncMock(
        side_effect=[
            [(actor_1, location_1, "standing", None), (observer, location_1, None, None)],
            [(actor_2, location_2, "standing", None), (observer, location_2, None, None)],
        ]
    )
    database.character.get_background_characters_by_location = AsyncMock(return_value=[])
    database.item.get_stacks_by_location = AsyncMock(return_value=[])
    database.equipment.get_equipment_by_location = AsyncMock(return_value=[])
    database.container.get_containers_by_location = AsyncMock(return_value=[])
    database.location.get_landmarks_by_location = AsyncMock(return_value=[shared_landmark])
    coordinator = SceneCoordinator(database=database)

    context = await coordinator._build_context(
        world_id=world.id,
        simulation_id=simulation.id,
        action_plans=[
            CharacterActionPlan(actor_id=actor_1.id, actions=[make_action()]),
            CharacterActionPlan(actor_id=actor_2.id, actions=[make_action()]),
        ],
    )

    assert [actor.actor.id for actor in context.actors] == ["character_1", "character_2"]
    assert {entry.character.id for entry in context.perceived_characters} == {"observer_1"}
    assert [entry.id for entry in context.perceived_landmarks] == ["landmark_1"]


async def test_coordinate_scene_preserves_planned_speech_when_llm_drops_utterance():
    character = make_character("character_clara")
    speech_action = ProposedAction(
        type=ActionType.SPEAK,
        label="respond_to_room7_inquiry",
        target_ids=["character_arthur"],
        utterance="Yes, Room Seven was certainly occupied before he disappeared.",
        intended_duration_seconds=12,
        interruptible=True,
    )
    llm_result = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            {
                "actor_id": character.id,
                "proposal_index": 0,
                "action_index": 0,
                "action": {
                    "type": ActionType.SPEAK,
                    "label": "respond_to_room7_inquiry",
                    "target_ids": [],
                    "utterance": None,
                    "intended_duration_seconds": 12,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [],
                },
                "start_offset_seconds": 0,
                "end_offset_seconds": 12,
                "summary": "Clara speaks to Arthur about Room Seven.",
            }
        ],
    )
    database = make_database(character=character)
    coordinator = SceneCoordinator(database=database)
    coordinator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=llm_result)
    coordinator._prepare_llm_service.return_value = llm

    result = await coordinator.coordinate_scene(
        world_id="world_1",
        simulation_id="simulation_1",
        action_plans=[
            CharacterActionPlan(
                actor_id=character.id,
                actions=[speech_action],
            )
        ],
    )

    assert result.accepted_actions[0].action == speech_action
    assert result.accepted_actions[0].summary == "Clara speaks to Arthur about Room Seven."


def test_hydrate_result_actions_preserves_selected_backup_candidate():
    primary_action = ProposedAction(
        type=ActionType.SPEAK,
        label="respond_to_room7_inquiry",
        target_ids=["character_arthur"],
        utterance="Yes, Room Seven was occupied.",
        intended_duration_seconds=12,
        interruptible=True,
    )
    backup_action = ProposedAction(
        type=ActionType.LOOK,
        label="verify_room7_record",
        target_ids=["landmark_ledger"],
        intended_duration_seconds=5,
        interruptible=True,
    )
    result = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            {
                "actor_id": "character_clara",
                "proposal_index": 1,
                "action_index": 0,
                "action": {
                    "type": ActionType.LOOK,
                    "label": "verify_room7_record",
                    "target_ids": [],
                    "utterance": None,
                    "intended_duration_seconds": 5,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [],
                },
                "start_offset_seconds": 0,
                "end_offset_seconds": 5,
                "summary": "Clara checks the ledger instead of answering immediately.",
            }
        ],
    )

    hydrated = SceneCoordinator._hydrate_result_actions(
        result,
        [
            CharacterActionPlan(
                actor_id="character_clara",
                actions=[primary_action],
                candidate_sets=[
                        ActionCandidateSet(
                            proposal_index=0,
                            actions=[primary_action],
                        ),
                        ActionCandidateSet(
                            proposal_index=1,
                            actions=[backup_action],
                        )
                    ],
                )
        ],
    )

    assert hydrated.accepted_actions[0].action == backup_action


def test_hydrate_result_actions_restores_actions_from_selected_multi_action_sequence():
    first_action = ProposedAction(
        type=ActionType.LOOK,
        label="check_ledger",
        target_ids=["landmark_ledger"],
        intended_duration_seconds=5,
        interruptible=True,
    )
    second_action = ProposedAction(
        type=ActionType.SPEAK,
        label="answer_room7_question",
        target_ids=["character_arthur"],
        utterance="The ledger says Room Seven was occupied.",
        intended_duration_seconds=8,
        interruptible=True,
    )
    result = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            {
                "actor_id": "character_clara",
                "proposal_index": 0,
                "action_index": 0,
                "action": {
                    "type": ActionType.LOOK,
                    "label": "check_ledger",
                    "target_ids": [],
                    "utterance": None,
                    "intended_duration_seconds": 5,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [],
                },
                "start_offset_seconds": 0,
                "end_offset_seconds": 5,
                "summary": "Clara checks the ledger.",
            },
            {
                "actor_id": "character_clara",
                "proposal_index": 0,
                "action_index": 1,
                "action": {
                    "type": ActionType.SPEAK,
                    "label": "answer_room7_question",
                    "target_ids": [],
                    "utterance": None,
                    "intended_duration_seconds": 8,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [],
                },
                "start_offset_seconds": 5,
                "end_offset_seconds": 13,
                "summary": "Clara answers after checking.",
            },
        ],
    )

    hydrated = SceneCoordinator._hydrate_result_actions(
        result,
        [
            CharacterActionPlan(
                actor_id="character_clara",
                actions=[first_action, second_action],
                candidate_sets=[
                    ActionCandidateSet(
                        proposal_index=0,
                        actions=[first_action, second_action],
                    )
                ],
            )
        ],
    )

    assert [accepted.action for accepted in hydrated.accepted_actions] == [first_action, second_action]


def test_hydrate_result_actions_drops_unmatched_coordinator_authored_action():
    authored_action = ProposedAction(
        type=ActionType.LOOK,
        label="check_ledger",
        target_ids=["landmark_ledger"],
        intended_duration_seconds=5,
        interruptible=True,
    )
    invented_action = ProposedAction(
        type=ActionType.SPEAK,
        label="invented_answer",
        target_ids=["character_arthur"],
        utterance="Something the character did not propose.",
        intended_duration_seconds=5,
        interruptible=True,
    )
    result = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            {
                "actor_id": "character_clara",
                "proposal_index": 0,
                "action_index": 9,
                "action": invented_action,
                "start_offset_seconds": 0,
                "end_offset_seconds": 5,
                "summary": "Invented action.",
            }
        ],
    )

    hydrated = SceneCoordinator._hydrate_result_actions(
        result,
        [
            CharacterActionPlan(
                actor_id="character_clara",
                actions=[authored_action],
                candidate_sets=[
                    ActionCandidateSet(
                        proposal_index=0,
                        actions=[authored_action],
                    )
                ],
            )
        ],
    )

    assert hydrated.accepted_actions == []
    assert "Dropped coordinator-authored accepted action" in hydrated.coordinator_notes[0]
