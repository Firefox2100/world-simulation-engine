import os
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter


async def test_interpret_returns_empty_interpretation_without_llm_for_whitespace():
    interpreter = InputInterpreter(database=Mock())
    interpreter._prepare_llm_service = AsyncMock()

    result = await interpreter.interpret(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input=" \n\t ",
    )

    assert result.items == []
    assert result.parser_notes == ["Raw input contained no non-whitespace text."]
    interpreter._prepare_llm_service.assert_not_called()


async def test_interpret_returns_ooc_only_interpretation_without_llm():
    interpreter = InputInterpreter(database=Mock())
    interpreter._prepare_llm_service = AsyncMock()

    result = await interpreter.interpret(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="[/OOC: keep the next response concise]",
    )

    assert len(result.items) == 1
    assert result.items[0].type == "ooc"
    assert result.items[0].command_text == "keep the next response concise"
    assert result.items[0].source_text == "[/OOC: keep the next response concise]"
    assert result.unparsed_text == []
    interpreter._prepare_llm_service.assert_not_called()
