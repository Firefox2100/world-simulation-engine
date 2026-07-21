import json
from typing import Any

from world_simulation_engine.misc.consts import WORKFLOWS
from world_simulation_engine.service import DatabaseService, StorageService


class WorkflowLoader:
    def __init__(self,
                 database: DatabaseService,
                 storage: StorageService,
                 ):
        self._db = database
        self._storage = storage

    async def load_workflow(self,
                            *,
                            simulation_id: str,
                            workflow_name: str,
                            ) -> dict[str, Any]:
        media = await self._db.media.get_workflow_media(
            simulation_id=simulation_id,
            workflow_name=workflow_name,
        )
        if media:
            content = await self._storage.get_bytes(media.hash)
            workflow_data = json.loads(content.decode("utf-8"))
        else:
            workflow_data = WORKFLOWS[workflow_name]

        return workflow_data
