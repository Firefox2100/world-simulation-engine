import json
from datetime import UTC, datetime
from pathlib import Path

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ActionType, ComponentType
from world_simulation_engine.model import (
    ActionCandidateSet,
    CharacterActionPlan,
    ProposedAction,
    SceneCoordinationResult,
)


SYNTHETIC_COORDINATION_CASES = [
    {
        "case_id": "arthur_asks_clara_room_7",
        "source": "user",
        "user_input": (
            "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
            "before Director Harlan vanished."
        ),
        "coordination": {
            "status": "complete",
            "accepted_actions": [
                {
                    "actor_id": "character_arthur_moore",
                    "proposal_index": 0,
                    "action_index": 0,
                    "start_offset_seconds": 0,
                    "end_offset_seconds": 4,
                    "summary": "Arthur Moore asks Clara Whitlock whether Room 7 was occupied before Harlan vanished.",
                    "action": {
                        "type": ActionType.SPEAK,
                        "label": "ask_clara_about_room_7",
                        "target_ids": ["character_clara_whitlock"],
                        "utterance": None,
                        "intended_duration_seconds": 4,
                        "interruptible": True,
                        "interruption_triggers": ["clara_answers", "bar_interrupts"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
            "problem": None,
            "pending_actions": [],
        },
    },
    {
        "case_id": "arthur_reads_notice_board",
        "source": "user",
        "user_input": (
            "I step away from the bar for a moment and study the Notice Board, looking for older papers "
            "hidden underneath the festival announcements."
        ),
        "coordination": {
            "status": "complete",
            "accepted_actions": [
                {
                    "actor_id": "character_arthur_moore",
                    "proposal_index": 0,
                    "action_index": 0,
                    "start_offset_seconds": 0,
                    "end_offset_seconds": 3,
                    "summary": "Arthur Moore steps away from the bar toward the Notice Board.",
                    "action": {
                        "type": ActionType.MOVE,
                        "label": "step_toward_notice_board",
                        "target_ids": ["landmark_notice_board"],
                        "utterance": None,
                        "intended_duration_seconds": 3,
                        "interruptible": True,
                        "interruption_triggers": ["clara_calls_after_arthur"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                },
                {
                    "actor_id": "character_arthur_moore",
                    "proposal_index": 0,
                    "action_index": 1,
                    "start_offset_seconds": 3,
                    "end_offset_seconds": 15,
                    "summary": "Arthur Moore studies the Notice Board for older papers under the festival notices.",
                    "action": {
                        "type": ActionType.OBSERVE,
                        "label": "study_notice_board_for_older_papers",
                        "target_ids": ["landmark_notice_board"],
                        "utterance": None,
                        "intended_duration_seconds": 12,
                        "interruptible": True,
                        "interruption_triggers": ["someone_blocks_notice_board"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                },
            ],
            "problem": None,
            "pending_actions": [],
        },
    },
    {
        "case_id": "clara_answers_room_7",
        "source": "character",
        "user_input": (
            "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
            "before Director Harlan vanished."
        ),
        "coordination": {
            "status": "complete",
            "accepted_actions": [
                {
                    "actor_id": "character_clara_whitlock",
                    "proposal_index": 0,
                    "action_index": 0,
                    "start_offset_seconds": 0,
                    "end_offset_seconds": 6,
                    "summary": "Clara Whitlock answers Arthur's question about Room 7 while staying behind the bar.",
                    "action": {
                        "type": ActionType.SPEAK,
                        "label": "answer_room_7_question",
                        "target_ids": ["character_arthur_moore"],
                        "utterance": "Room 7 was occupied, Mr. Moore, but not by a name I trusted.",
                        "intended_duration_seconds": 6,
                        "interruptible": True,
                        "interruption_triggers": ["customer_interrupts"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
            "problem": None,
            "pending_actions": [],
        },
    },
    {
        "case_id": "clara_hands_receipt",
        "source": "character",
        "user_input": "Clara hands Arthur the Room 7 cash receipt.",
        "coordination": {
            "status": "complete",
            "accepted_actions": [
                {
                    "actor_id": "character_clara_whitlock",
                    "proposal_index": 0,
                    "action_index": 0,
                    "start_offset_seconds": 0,
                    "end_offset_seconds": 4,
                    "summary": "Clara Whitlock hands the Room 7 cash receipt to Arthur Moore.",
                    "action": {
                        "type": ActionType.GIVE,
                        "label": "hand_room_7_receipt_to_arthur",
                        "target_ids": ["item_room_7_cash_receipt", "character_arthur_moore"],
                        "utterance": None,
                        "intended_duration_seconds": 4,
                        "interruptible": True,
                        "interruption_triggers": ["arthur_refuses", "customer_interrupts"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
            "problem": None,
            "pending_actions": [],
        },
    },
    {
        "case_id": "eleanor_intervenes_then_pending_clara",
        "source": "character",
        "user_input": (
            "Arthur lowers his voice and says, \"I am not here to embarrass the town, Miss Whitlock, "
            "but I do need the truth.\""
        ),
        "coordination": {
            "status": "problem",
            "accepted_actions": [
                {
                    "actor_id": "character_eleanor_graves",
                    "proposal_index": 0,
                    "action_index": 0,
                    "start_offset_seconds": 0,
                    "end_offset_seconds": 4,
                    "summary": "Eleanor Graves cuts in before Clara can answer Arthur.",
                    "action": {
                        "type": ActionType.SPEAK,
                        "label": "intervene_about_town_discretion",
                        "target_ids": ["character_arthur_moore"],
                        "utterance": "Discretion is also a kind of truth, Mr. Moore.",
                        "intended_duration_seconds": 4,
                        "interruptible": True,
                        "interruption_triggers": ["arthur_addresses_clara_directly"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
            "problem": {
                "type": "interruption",
                "time_offset_seconds": 4,
                "involved_actor_ids": ["character_clara_whitlock", "character_eleanor_graves"],
                "involved_actions": [
                    {
                        "actor_id": "character_clara_whitlock",
                        "proposal_index": 0,
                        "action_index": 0,
                    },
                    {
                        "actor_id": "character_eleanor_graves",
                        "proposal_index": 0,
                        "action_index": 0,
                    },
                ],
                "description": "Eleanor's public interruption delays Clara's private answer to Arthur.",
                "needs_user_decision": False,
                "actors_to_react": ["character_clara_whitlock"],
                "resolver_required": False,
            },
            "pending_actions": [
                {
                    "actor_id": "character_clara_whitlock",
                    "proposal_index": 0,
                    "action_index": 0,
                    "reason": "Clara must decide whether to answer after Eleanor interrupts.",
                    "action": {
                        "type": ActionType.SPEAK,
                        "label": "answer_arthur_truth_request",
                        "target_ids": ["character_arthur_moore"],
                        "utterance": None,
                        "intended_duration_seconds": 8,
                        "interruptible": True,
                        "interruption_triggers": ["eleanor_continues_interruption"],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
        },
    },
]


INPUT_PIPELINE_CASES = [
    {
        "case_id": "ask_clara_room_7",
        "user_input": (
            "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
            "before Director Harlan vanished."
        ),
    },
    {
        "case_id": "inspect_ledger",
        "user_input": (
            "I ask Clara to let me see the Visitor's Room Ledger, then compare the Room 7 entry "
            "against the dates around Harlan's disappearance."
        ),
    },
    {
        "case_id": "mixed_speech_and_ooc",
        "user_input": (
            "Arthur lowers his voice and says, \"I am not here to embarrass the town, Miss Whitlock, "
            "but I do need the truth.\" [/OOC: Keep the interpretation focused on the attempted action.]"
        ),
    },
    {
        "case_id": "read_notice_board",
        "user_input": (
            "I step away from the bar for a moment and study the Notice Board, looking for older papers "
            "hidden underneath the festival announcements."
        ),
    },
    {
        "case_id": "reveal_letter_conditionally",
        "user_input": (
            "If Clara seems willing to speak privately, Arthur shows her only the signature line of the "
            "anonymous letter and asks whether she recognizes the handwriting."
        ),
    },
]


async def link_chat_components(
    *,
    database,
    simulation_id: str,
    config_id: str,
    components: list[ComponentType],
):
    for component in components:
        await database.config.link_chat(
            source_id=simulation_id,
            config_id=config_id,
            component=component,
        )


def write_case_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    case_order: list[dict],
    case_result: dict,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        output = {
            "world_id": world_id,
            "simulation_id": simulation_id,
            "cases": [],
        }

    cases_by_id = {
        case["case_id"]: case
        for case in output.get("cases", [])
    }
    cases_by_id[case_result["case_id"]] = case_result

    output.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "world_id": world_id,
            "simulation_id": simulation_id,
            "cases": [
                cases_by_id[case["case_id"]]
                for case in case_order
                if case["case_id"] in cases_by_id
            ],
        }
    )
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def synthetic_coordination(case: dict) -> SceneCoordinationResult:
    return SceneCoordinationResult.model_validate(case["coordination"])


def actions_from_interpretation(interpretation) -> list[ProposedAction]:
    return [
        item.action
        for item in interpretation.items
        if item.type == "action"
    ]


def allowed_actions_from_validation(validation) -> list[ProposedAction]:
    return [
        item.action
        for item in validation.validations
        if item.allowed
    ]


def proposal_candidates(proposal) -> list[ProposedAction]:
    return [
        action
        for sequence in [proposal.actions, *proposal.backup_proposals]
        for action in sequence
    ]


def action_plan(actor_id: str, actions: list[ProposedAction]) -> CharacterActionPlan:
    return CharacterActionPlan(
        actor_id=actor_id,
        actions=actions,
        candidate_sets=[
            ActionCandidateSet(
                proposal_index=0,
                actions=actions,
            )
        ] if actions else [],
    )


def character_action_plans_from_validation_records(records: list[dict]) -> list[CharacterActionPlan]:
    plans_by_actor: dict[str, CharacterActionPlan] = {}
    for record in records:
        validations = record.get("proposal_validations") or [record["validation"]]
        proposal_sequences = [record["proposal"].actions, *record["proposal"].backup_proposals]
        valid_sequences = [
            (proposal_index, proposal_sequences[proposal_index])
            for proposal_index, validation in enumerate(validations)
            if proposal_index < len(proposal_sequences)
            and validation.validations
            and all(item.allowed for item in validation.validations)
        ]
        if not valid_sequences:
            continue

        plan = plans_by_actor.setdefault(
            record["character_id"],
            CharacterActionPlan(
                actor_id=record["character_id"],
                actions=valid_sequences[0][1],
            ),
        )
        plan.action_proposals.append(record["proposal"])
        for proposal_index, sequence in valid_sequences:
            plan.candidate_sets.append(
                ActionCandidateSet(
                    proposal_index=proposal_index,
                    actions=sequence,
                )
            )

    return list(plans_by_actor.values())


async def nearby_non_user_character_ids(database, simulation_id: str) -> list[str]:
    user_character = await database.character.get_user_character_by_simulation(simulation_id)
    if not user_character:
        raise ValueError(f"Simulation {simulation_id} has no user character")

    location = await database.location.get_location_by_character(user_character.id)
    if not location:
        return []

    nearby_characters = await database.get_characters_in_location(location.id)
    return [
        character.id
        for character, _, _, _ in nearby_characters
        if not character.user_controlled
    ]


async def build_character_coordination_from_input(
    *,
    database,
    world_id: str,
    simulation_id: str,
    user_character_id: str,
    user_input: str,
) -> dict:
    interpreter = InputInterpreter(database=database)
    validator = ActionValidator(database=database)
    coordinator = SceneCoordinator(database=database)
    character_simulator = CharacterSimulator(database=database, langfuse_handler=None)

    interpretation = await interpreter.interpret(
        world_id=world_id,
        simulation_id=simulation_id,
        character_id=user_character_id,
        user_input=user_input,
    )
    user_actions = actions_from_interpretation(interpretation)
    user_validation = await validator.validate_actions(
        world_id=world_id,
        simulation_id=simulation_id,
        character_id=user_character_id,
        actions=user_actions,
    )
    allowed_user_actions = allowed_actions_from_validation(user_validation)
    user_coordination = await coordinator.coordinate_scene(
        world_id=world_id,
        simulation_id=simulation_id,
        action_plans=[action_plan(user_character_id, allowed_user_actions)],
    )

    fanout_character_ids = await nearby_non_user_character_ids(database, simulation_id)
    character_validation_records = []
    for fanout_character_id in fanout_character_ids:
        proposal = await character_simulator.propose_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            character_id=fanout_character_id,
            user_input=user_input,
        )
        validation = await validator.validate_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            character_id=fanout_character_id,
            actions=proposal_candidates(proposal),
        )
        character_validation_records.append(
            {
                "character_id": fanout_character_id,
                "proposal": proposal,
                "validation": validation,
            }
        )

    character_action_plans = character_action_plans_from_validation_records(character_validation_records)
    character_coordination = await coordinator.coordinate_scene(
        world_id=world_id,
        simulation_id=simulation_id,
        action_plans=character_action_plans,
    )

    return {
        "interpretation": interpretation,
        "user_actions": user_actions,
        "user_validation": user_validation,
        "allowed_user_actions": allowed_user_actions,
        "user_coordination": user_coordination,
        "fanout_character_ids": fanout_character_ids,
        "character_validation_records": character_validation_records,
        "character_action_plans": character_action_plans,
        "character_coordination": character_coordination,
    }
