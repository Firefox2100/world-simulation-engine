import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.image_generator import SceneImageGenerator, TurnImageTrigger
from world_simulation_engine.component.image_generator.turn_image_trigger import deterministic_turn_significance
from world_simulation_engine.misc.enums import ActionType, ImageGenerationMode, SceneCoordinationStatus, TurnType
from world_simulation_engine.model import AcceptedSceneAction, ImageGenerationConfig, ProposedAction, \
    SceneCoordinationResult, Turn


def make_action(action_type: ActionType, label: str = "act") -> ProposedAction:
    return ProposedAction(type=action_type, label=label, intended_duration_seconds=5)


def make_accepted(actor_id: str, action: ProposedAction) -> AcceptedSceneAction:
    return AcceptedSceneAction(
        actor_id=actor_id,
        proposal_index=0,
        action_index=0,
        action=action,
        start_offset_seconds=0,
        end_offset_seconds=5,
        summary="did something",
    )


def make_turn(sequence: int = 5) -> Turn:
    return Turn(
        sequence=sequence,
        type=TurnType.SYSTEM_RESPONSE,
        content="content",
        start_time=datetime.now(timezone.utc),
    )


def make_coordination(*accepted: AcceptedSceneAction) -> SceneCoordinationResult:
    return SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE, accepted_actions=list(accepted))


class TestDeterministicTurnSignificance:
    def test_no_actions_is_insignificant(self):
        assert deterministic_turn_significance([]) is False

    def test_significant_action_type_is_significant(self):
        actions = [make_action(ActionType.SPEAK), make_action(ActionType.MOVE)]
        assert deterministic_turn_significance(actions) is True

    def test_all_insignificant_action_types_is_insignificant(self):
        actions = [make_action(ActionType.SPEAK), make_action(ActionType.WAIT), make_action(ActionType.OBSERVE)]
        assert deterministic_turn_significance(actions) is False

    def test_ambiguous_action_type_is_inconclusive(self):
        actions = [make_action(ActionType.OTHER)]
        assert deterministic_turn_significance(actions) is None

    def test_mixed_insignificant_and_ambiguous_is_inconclusive(self):
        actions = [make_action(ActionType.SPEAK), make_action(ActionType.STOP_ACTIVITY)]
        assert deterministic_turn_significance(actions) is None


class TestShouldGenerate:
    async def test_manual_mode_never_triggers(self):
        database = Mock()
        trigger = TurnImageTrigger(database=database, storage=Mock())
        config = ImageGenerationConfig(mode=ImageGenerationMode.MANUAL)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            actions=[make_action(ActionType.ATTACK)], config=config,
        )

        assert result is False

    async def test_always_mode_always_triggers(self):
        database = Mock()
        trigger = TurnImageTrigger(database=database, storage=Mock())
        config = ImageGenerationConfig(mode=ImageGenerationMode.ALWAYS)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            actions=[], config=config,
        )

        assert result is True

    async def test_auto_mode_deterministic_significant_triggers_without_llm(self):
        database = Mock()
        trigger = TurnImageTrigger(database=database, storage=Mock())
        trigger._llm_significance = AsyncMock()
        config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=10)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(sequence=5), narration="",
            actions=[make_action(ActionType.ATTACK)], config=config,
        )

        assert result is True
        trigger._llm_significance.assert_not_called()

    async def test_auto_mode_deterministic_insignificant_below_fallback_does_not_trigger(self):
        database = Mock()
        database.media.get_last_turn_sequence_with_generated_image = AsyncMock(return_value=4)
        trigger = TurnImageTrigger(database=database, storage=Mock())
        config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=10)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(sequence=5), narration="",
            actions=[make_action(ActionType.WAIT)], config=config,
        )

        assert result is False

    async def test_auto_mode_forces_generation_after_fallback_turns(self):
        database = Mock()
        database.media.get_last_turn_sequence_with_generated_image = AsyncMock(return_value=1)
        trigger = TurnImageTrigger(database=database, storage=Mock())
        config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=3)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(sequence=5), narration="",
            actions=[make_action(ActionType.WAIT)], config=config,
        )

        # turns_since = 5 - 1 = 4 >= fallback_turns=3
        assert result is True

    async def test_auto_mode_inconclusive_defers_to_llm(self):
        database = Mock()
        database.media.get_last_turn_sequence_with_generated_image = AsyncMock(return_value=4)
        trigger = TurnImageTrigger(database=database, storage=Mock())
        trigger._llm_significance = AsyncMock(return_value=True)
        config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=10)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(sequence=5), narration="narration text",
            actions=[make_action(ActionType.OTHER)], config=config,
        )

        assert result is True
        trigger._llm_significance.assert_awaited_once()

    async def test_auto_mode_llm_says_no_and_below_fallback_does_not_trigger(self):
        database = Mock()
        database.media.get_last_turn_sequence_with_generated_image = AsyncMock(return_value=4)
        trigger = TurnImageTrigger(database=database, storage=Mock())
        trigger._llm_significance = AsyncMock(return_value=False)
        config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=10)

        result = await trigger.should_generate(
            simulation_id="simulation_1", turn=make_turn(sequence=5), narration="",
            actions=[make_action(ActionType.OTHER)], config=config,
        )

        assert result is False

    async def test_turns_since_last_generation_never_generated_uses_current_sequence(self):
        database = Mock()
        database.media.get_last_turn_sequence_with_generated_image = AsyncMock(return_value=None)
        trigger = TurnImageTrigger(database=database, storage=Mock())

        turns_since = await trigger._turns_since_last_generation(simulation_id="simulation_1", current_sequence=7)

        assert turns_since == 7


class TestMaybeGenerate:
    async def test_skips_when_no_config(self):
        database = Mock()
        database.config.get_image_generation_config = AsyncMock(return_value=None)
        trigger = TurnImageTrigger(database=database, storage=Mock())

        await trigger.maybe_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            coordination_result=make_coordination(),
        )

        database.config.get_image_generation_config.assert_awaited_once_with("simulation_1")

    async def test_skips_when_manual(self):
        database = Mock()
        database.config.get_image_generation_config = AsyncMock(
            return_value=ImageGenerationConfig(mode=ImageGenerationMode.MANUAL)
        )
        trigger = TurnImageTrigger(database=database, storage=Mock())
        trigger.should_generate = AsyncMock()

        await trigger.maybe_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            coordination_result=make_coordination(),
        )

        trigger.should_generate.assert_not_called()

    async def test_skips_when_no_location_resolvable(self):
        database = Mock()
        database.config.get_image_generation_config = AsyncMock(
            return_value=ImageGenerationConfig(mode=ImageGenerationMode.ALWAYS)
        )
        database.location.get_location_by_character = AsyncMock(return_value=None)
        trigger = TurnImageTrigger(database=database, storage=Mock())

        accepted = make_accepted("character_1", make_action(ActionType.ATTACK))
        await trigger.maybe_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            coordination_result=make_coordination(accepted),
        )

        database.location.get_location_by_character.assert_awaited_once_with("character_1")

    async def test_generates_scene_when_triggered(self, monkeypatch):
        database = Mock()
        database.config.get_image_generation_config = AsyncMock(
            return_value=ImageGenerationConfig(mode=ImageGenerationMode.ALWAYS)
        )
        database.location.get_location_by_character = AsyncMock(return_value=Mock(id="location_1"))
        trigger = TurnImageTrigger(database=database, storage=Mock())

        generate_scene = AsyncMock()
        monkeypatch.setattr(SceneImageGenerator, "generate_scene", generate_scene)

        accepted = make_accepted("character_1", make_action(ActionType.ATTACK))
        turn = make_turn()
        await trigger.maybe_generate(
            simulation_id="simulation_1", turn=turn, narration="",
            coordination_result=make_coordination(accepted),
        )

        generate_scene.assert_awaited_once_with(
            simulation_id="simulation_1", location_id="location_1", turn_id=turn.id,
        )

    async def test_swallows_errors(self):
        database = Mock()
        database.config.get_image_generation_config = AsyncMock(side_effect=RuntimeError("boom"))
        trigger = TurnImageTrigger(database=database, storage=Mock())

        # Must not raise: a failed auto-trigger evaluation must never disrupt the turn pipeline.
        await trigger.maybe_generate(
            simulation_id="simulation_1", turn=make_turn(), narration="",
            coordination_result=make_coordination(),
        )
