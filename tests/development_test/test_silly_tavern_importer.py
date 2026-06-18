import os
import pytest

from world_simulation_engine.component import SillyTavernImporter


@pytest.fixture
def mock_card_data() -> bytes:
    card_path = os.getenv("TEST_ST_CARD_PATH")
    if not card_path:
        raise ValueError("TEST_ST_CARD_PATH not set")

    with open(card_path, "rb") as f:
        return f.read()


async def test_import_silly_tavern_card(db,
                                        mock_card_data,
                                        ):
    importer = SillyTavernImporter(db=db)

    await importer.import_card(mock_card_data)
