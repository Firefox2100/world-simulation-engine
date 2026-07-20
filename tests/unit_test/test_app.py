from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine import app as app_module
from world_simulation_engine.component.prompt_loader import PromptLoader


async def test_lifespan_injects_database_backed_prompt_loader(monkeypatch):
    driver = object()
    database = SimpleNamespace(
        generation_job=SimpleNamespace(fail_incomplete_jobs=AsyncMock(return_value=0)),
        close=AsyncMock(),
    )
    storage = SimpleNamespace(initialise=AsyncMock())
    captured = {}
    simulator = SimpleNamespace(shutdown=AsyncMock())

    monkeypatch.setattr(app_module.AsyncGraphDatabase, "driver", Mock(return_value=driver))
    monkeypatch.setattr(app_module, "DatabaseService", Mock(return_value=database))
    monkeypatch.setattr(app_module, "StorageService", Mock(return_value=storage))

    def make_simulator(*, database, prompt_loader):
        captured["database"] = database
        captured["prompt_loader"] = prompt_loader
        return simulator

    monkeypatch.setattr(app_module, "WorldSimulator", make_simulator)
    application = SimpleNamespace(state=SimpleNamespace())

    async with app_module.lifespan(application):
        assert application.state.database is database
        assert application.state.storage is storage

    assert captured["database"] is database
    assert isinstance(captured["prompt_loader"], PromptLoader)
    assert captured["prompt_loader"]._db is database
    assert captured["prompt_loader"]._storage is storage
    database.generation_job.fail_incomplete_jobs.assert_awaited_once()
    simulator.shutdown.assert_awaited_once()
    database.close.assert_awaited_once()
