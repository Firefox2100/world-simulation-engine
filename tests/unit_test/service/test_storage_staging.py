import pytest

from world_simulation_engine.service.storage_service import StorageService


async def test_staged_bytes_are_not_visible_until_promoted(tmp_path):
    storage = StorageService(tmp_path)
    await storage.initialise()
    staged = await storage.stage_bytes(b"temporary image")

    with pytest.raises(ValueError, match="not found"):
        await storage.get_bytes(staged.digest)

    stored = await storage.promote_staged(staged.token, expected_digest=staged.digest)

    assert stored.digest == staged.digest
    assert await storage.get_bytes(staged.digest) == b"temporary image"


async def test_promote_rejects_arbitrary_temporary_paths(tmp_path):
    storage = StorageService(tmp_path)
    await storage.initialise()

    with pytest.raises(ValueError, match="Invalid temporary object token"):
        await storage.promote_staged("../../anything", expected_digest="a" * 64)
