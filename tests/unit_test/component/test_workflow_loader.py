import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.component.workflow_loader import WorkflowLoader
from world_simulation_engine.misc.consts import WORKFLOWS
from world_simulation_engine.model import WorkflowMediaFile


async def test_load_workflow_uses_simulation_or_world_override_media():
    override = {
        "version": "1.0",
        "positive_prompt": "/10/inputs/text",
    }
    media = WorkflowMediaFile(
        id="workflow_1",
        title="Override",
        hash="a" * 64,
        filename="character",
        workflow_name="character",
    )
    database = SimpleNamespace(
        media=SimpleNamespace(get_workflow_media=AsyncMock(return_value=media)),
    )
    storage = SimpleNamespace(
        get_bytes=AsyncMock(return_value=json.dumps(override).encode("utf-8")),
    )

    result = await WorkflowLoader(database=database, storage=storage).load_workflow(
        simulation_id="simulation_1",
        workflow_name="character",
    )

    assert result == override
    database.media.get_workflow_media.assert_awaited_once_with(
        simulation_id="simulation_1",
        workflow_name="character",
    )
    storage.get_bytes.assert_awaited_once_with(media.hash)


async def test_load_workflow_falls_back_to_builtin_when_no_override_exists():
    database = SimpleNamespace(
        media=SimpleNamespace(get_workflow_media=AsyncMock(return_value=None)),
    )
    storage = SimpleNamespace(get_bytes=AsyncMock())

    result = await WorkflowLoader(database=database, storage=storage).load_workflow(
        simulation_id="simulation_1",
        workflow_name="character",
    )

    assert result == WORKFLOWS["character"]
    storage.get_bytes.assert_not_awaited()
