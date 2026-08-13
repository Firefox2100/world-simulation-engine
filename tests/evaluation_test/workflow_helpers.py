import json
from datetime import UTC, datetime
from pathlib import Path

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import (
    ActionCandidateSet,
    CharacterActionPlan,
    ProposedAction,
    SceneCoordinationResult,
)

from world_fixtures import discover_world_dirs

# "Intended input" test scenarios, read at import time (not via a fixture) so
# @pytest.mark.parametrize - which needs its case list at collection time, before any fixture runs
# - can consume them directly, the same way the SillyTavern eval tests parametrize over
# CARDS_DIR.glob(...) rather than a fixture. Every discovered world bundle (see world_fixtures.py's
# discover_world_dirs) contributes its own eval/scenarios.json cases, flattened into one list of
# (world_dir, case) pairs per category - a world with none for a given category (the common case
# for a freshly generated, not-yet-hand-authored bundle) simply contributes zero parametrized
# cases for it, not an error. Case ids only need to be unique *within* one world's scenarios.json,
# not globally - keep that in mind if you ever need to distinguish same-named cases from different
# worlds in tests/evaluation_test/output/*.json.
WORLD_DIRS = discover_world_dirs()


def _load_scenarios(world_dir: Path) -> dict:
    path = world_dir / "eval" / "scenarios.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _cases_for(key: str) -> list[tuple[Path, dict]]:
    return [
        (world_dir, case)
        for world_dir in WORLD_DIRS
        for case in _load_scenarios(world_dir).get(key, [])
    ]


def case_ids(pairs: list[tuple[Path, dict]]) -> list[str]:
    return [f"{world_dir.name}:{case['case_id']}" for world_dir, case in pairs]


SYNTHETIC_COORDINATION_CASES = _cases_for("synthetic_coordination_cases")
INPUT_PIPELINE_CASES = _cases_for("input_pipeline_cases")
ACTION_VALIDATOR_EVALUATION_CASES = _cases_for("action_validator_evaluation_cases")
USER_COORDINATION_CASES = _cases_for("user_coordination_cases")
CHARACTER_SIMULATOR_CASES = _cases_for("character_simulator_cases")
EMOTION_UPDATER_CASES = _cases_for("emotion_updater_cases")
SUBJECTIVE_MODEL_UPDATER_CASES = _cases_for("subjective_model_updater_cases")
RELATIONSHIP_UPDATER_CASES = _cases_for("relationship_updater_cases")
OBJECTIVE_RELATIONSHIP_VALIDATION_CASES = _cases_for("objective_relationship_validation_cases")
WORLD_SIMULATOR_CASES = _cases_for("world_simulator_cases")


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


def _case_id_of(entry: dict | tuple[Path, dict]) -> str:
    """`case_order` historically held plain case dicts; it now also accepts the (world_dir, case)
    pairs `_cases_for` produces, so callers can pass e.g. SYNTHETIC_COORDINATION_CASES directly
    without unpacking it first."""
    case = entry[1] if isinstance(entry, tuple) else entry
    return case["case_id"]


def write_case_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    case_order: list[dict] | list[tuple[Path, dict]],
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
                cases_by_id[case_id]
                for case_id in (_case_id_of(entry) for entry in case_order)
                if case_id in cases_by_id
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
