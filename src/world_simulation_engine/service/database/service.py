from neo4j import AsyncDriver


class DatabaseService:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver
