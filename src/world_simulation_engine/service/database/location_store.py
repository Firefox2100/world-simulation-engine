from neo4j import AsyncDriver

from world_simulation_engine.model import Location, Landmark


def _location_from_node(location_node) -> Location:
    return Location(
        id=location_node["id"],
        name=location_node["name"],
        description=location_node["description"],
    )


def _landmark_from_node(landmark_node) -> Landmark:
    return Landmark(
        id=landmark_node["id"],
        name=landmark_node["name"],
        description=landmark_node["description"],
    )


class LocationStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_location(self,
                              location: Location,
                              contained_in: str | None = None,
                              ):
        await self._driver.execute_query(
            """
            CREATE (l:Location {
                id: $id,
                name: $name,
                description: $description
            })
            OPTIONAL MATCH (location:Location {id: $contained_in})
            FOREACH (_ IN CASE
                WHEN $contained_in IS NOT NULL AND location IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (l)<-[:CONTAINS]-(location)
            )
            RETURN l
            """,
            parameters_={
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "contained_in": contained_in,
            }
        )

    async def get_location(self, location_id: str) -> Location | None:
        result = await self._driver.execute_query(
            "MATCH (l:Location {id: $id}) RETURN l LIMIT 1",
            parameters_={"id": location_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _location_from_node(record["l"])

    async def get_location_by_character(self, character_id: str) -> Location | None:
        result = await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id}) -[:PRESENT_IN]-> (loc:Location)
            RETURN loc
            """,
            parameters_={"character_id": character_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            # Try checking landmark
            result = await self._driver.execute_query(
                """
                MATCH (c:Character {id: $character_id}) -[:ANCHORED_TO]->(l:Landmark) <-[:CONTAINS]-(loc:Location)
                RETURN loc
                """,
                parameters_={"character_id": character_id}
            )

            record = result.records[0] if result.records else None
            if not record:
                return None

        return _location_from_node(record["loc"])

    async def create_landmark(self,
                              landmark: Landmark,
                              location_id: str,
                              ):
        await self._driver.execute_query(
            """
            CREATE (l:Landmark {
                id: $id,
                name: $name,
                description: $description
            })
            MATCH (loc:Location {id: $location_id})
            MERGE (l)<-[:CONTAINS]-(loc)
            RETURN l
            """,
            parameters_={
                "id": landmark.id,
                "name": landmark.name,
                "description": landmark.description,
                "location_id": location_id,
            }
        )
