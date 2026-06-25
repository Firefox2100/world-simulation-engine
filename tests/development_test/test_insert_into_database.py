"""
This inserts the entry into the actual database. Only run in controlled environment!
"""

import os
from httpx import AsyncClient

import pytest


@pytest.fixture
def backend_url() -> str:
    return os.getenv("TEST_BACKEND_URL", "http://localhost:9797").strip("/")



async def test_insert_world_into_database(mock_world_create,
                                          backend_url,
                                          ):
    client = AsyncClient(base_url=backend_url)

    result = await client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json", exclude_none=True),
        timeout=60,
    )
    result.raise_for_status()
