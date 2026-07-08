from world_simulation_engine.model import PerceivedEntity
from world_simulation_engine.service import DatabaseService, LlmService


class PerspectiveResolver:
    """
    This component finds all the element that a character can see in a scene. It's designed to use different
    data sources for future extension
    """

    def __init__(self,
                 world_id: str,
                 simulation_id: str,
                 character_id: str,
                 database: DatabaseService,
                 ):
        self._world_id = world_id
        self._simulation_id = simulation_id
        self._character_id = character_id

        self._db = database

    async def _resolve_perceived_entity_in_graph(self):
        location = await self._db.location.get_location_by_character(self._character_id)



    async def resolve_perceived_entities(self):
        pass
