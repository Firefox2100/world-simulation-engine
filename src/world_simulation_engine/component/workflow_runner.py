from world_simulation_engine.service import DatabaseService, EmbeddingService, DirectorAgent, WorldGeneratorAgent
from .world_entry_recaller import WorldEntryRecaller


class WorkflowRunner:
    def __init__(self,
                 database_service: DatabaseService,
                 embedding_service: EmbeddingService,
                 ):
        self._database = database_service
        self._embedding = embedding_service
