from neo4j import AsyncDriver

from world_simulation_engine.model import Location, Landmark


class LocationStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def location_from_node(location_node) -> Location:
        return Location(
            id=location_node["id"],
            name=location_node["name"],
            description=location_node["description"],
        )

    @staticmethod
    def landmark_from_node(landmark_node) -> Landmark:
        return Landmark(
            id=landmark_node["id"],
            name=landmark_node["name"],
            description=landmark_node["description"],
        )

    async def create_location(self,
                              location: Location,
                              source_id: str,
                              contained_in: str | None = None,
                              ) -> Location | None:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (parent:Location {id: $contained_in})
            WITH source, parent
            WHERE $contained_in IS NULL OR parent IS NOT NULL
            CREATE (l:Location {
                id: $id,
                name: $name,
                description: $description
            })
            MERGE (source)-[:CONTAINS]->(l)
            FOREACH (_ IN CASE
                WHEN $contained_in IS NOT NULL AND parent IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (l)<-[:CONTAINS]-(parent)
            )
            RETURN l
            """,
            parameters_={
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "source_id": source_id,
                "contained_in": contained_in,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.location_from_node(record["l"])

    async def create_sub_location(self,
                                  location: Location,
                                  parent_id: str,
                                  ) -> Location | None:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation)-[:CONTAINS]->(parent:Location {id: $parent_id})
            CREATE (location:Location {
                id: $id,
                name: $name,
                description: $description
            })
            MERGE (source)-[:CONTAINS]->(location)
            MERGE (parent)-[:CONTAINS]->(location)
            RETURN location
            LIMIT 1
            """,
            parameters_={
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "parent_id": parent_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.location_from_node(record["location"])

    async def list_locations(self,
                             world_id: str | None = None,
                             simulation_id: str | None = None,
                             region_id: str | None = None,
                             ) -> list[Location]:
        if region_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Location {id: $region_id})-[:CONTAINS]->(location:Location)
                RETURN location
                ORDER BY location.name
                """,
                parameters_={"region_id": region_id},
            )
        elif world_id is not None and simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(location:Location)
                RETURN location
                ORDER BY location.name
                """,
                parameters_={
                    "world_id": world_id,
                    "simulation_id": simulation_id,
                },
            )
        elif world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})-[:CONTAINS]->(location:Location)
                RETURN location
                ORDER BY location.name
                """,
                parameters_={"world_id": world_id},
            )
        elif simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(location:Location)
                RETURN location
                ORDER BY location.name
                """,
                parameters_={"simulation_id": simulation_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (location:Location)
                RETURN location
                ORDER BY location.name
                """
            )

        return [
            self.location_from_node(record["location"])
            for record in result.records
        ]

    async def get_location(self, location_id: str) -> Location | None:
        result = await self._driver.execute_query(
            "MATCH (l:Location {id: $id}) RETURN l LIMIT 1",
            parameters_={"id": location_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.location_from_node(record["l"])

    async def update_location(self,
                              location_id: str,
                              properties: dict,
                              ) -> Location | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id})
            SET location += $properties
            RETURN location LIMIT 1
            """,
            parameters_={
                "location_id": location_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.location_from_node(record["location"])

    async def delete_location(self, location_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id})
            OPTIONAL MATCH path = (location)-[:CONTAINS*0..]->(node)
            WHERE node:Location OR node:Landmark
            WITH collect(DISTINCT node) AS nodes, 1 AS deleted
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted
            """,
            parameters_={"location_id": location_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

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

        return self.location_from_node(record["loc"])

    async def create_landmark(self,
                              landmark: Landmark,
                              location_id: str,
                              ) -> Landmark | None:
        result = await self._driver.execute_query(
            """
            MATCH (loc:Location {id: $location_id})
            CREATE (l:Landmark {
                id: $id,
                name: $name,
                description: $description
            })
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.landmark_from_node(record["l"])

    async def list_landmarks(self,
                             world_id: str | None = None,
                             simulation_id: str | None = None,
                             location_id: str | None = None,
                             ) -> list[Landmark]:
        if location_id is not None:
            source_match = """
            MATCH (:Location {id: $location_id})-[:CONTAINS]->(landmark:Landmark)
            """
        elif world_id is not None and simulation_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(:Location)-[:CONTAINS]->(landmark:Landmark)
            """
        elif world_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})-[:CONTAINS]->(:Location)-[:CONTAINS]->(landmark:Landmark)
            """
        elif simulation_id is not None:
            source_match = """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(:Location)-[:CONTAINS]->(landmark:Landmark)
            """
        else:
            source_match = """
            MATCH (landmark:Landmark)
            """

        result = await self._driver.execute_query(
            source_match + """
            RETURN DISTINCT landmark
            ORDER BY landmark.name
            """,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
                "location_id": location_id,
            },
        )

        return [
            self.landmark_from_node(record["landmark"])
            for record in result.records
        ]

    async def get_landmarks_by_location(self,
                                        location_id: str,
                                        ) -> list[Landmark]:
        result = await self._driver.execute_query(
            """
            MATCH (:Location {id: $location_id}) -[:CONTAINS]-> (landmark:Landmark)
            RETURN landmark
            ORDER BY landmark.name
            """,
            parameters_={"location_id": location_id},
        )

        return [
            self.landmark_from_node(record["landmark"])
            for record in result.records
        ]

    async def get_landmark(self, landmark_id: str) -> Landmark | None:
        result = await self._driver.execute_query(
            """
            MATCH (landmark:Landmark {id: $landmark_id})
            RETURN landmark LIMIT 1
            """,
            parameters_={"landmark_id": landmark_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.landmark_from_node(record["landmark"])

    async def update_landmark(self,
                              landmark_id: str,
                              properties: dict,
                              ) -> Landmark | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }
        if not properties:
            return await self.get_landmark(landmark_id)

        result = await self._driver.execute_query(
            """
            MATCH (landmark:Landmark {id: $landmark_id})
            SET landmark += $properties
            RETURN landmark LIMIT 1
            """,
            parameters_={
                "landmark_id": landmark_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.landmark_from_node(record["landmark"])

    async def move_landmark_to_location(self,
                                        landmark_id: str,
                                        location_id: str,
                                        ) -> Landmark | None:
        result = await self._driver.execute_query(
            """
            MATCH (landmark:Landmark {id: $landmark_id})
            MATCH (location:Location {id: $location_id})
            OPTIONAL MATCH (:Location)-[existing:CONTAINS]->(landmark)
            DELETE existing
            MERGE (location)-[:CONTAINS]->(landmark)
            RETURN landmark LIMIT 1
            """,
            parameters_={
                "landmark_id": landmark_id,
                "location_id": location_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.landmark_from_node(record["landmark"])

    async def delete_landmark(self, landmark_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (landmark:Landmark {id: $landmark_id})
            WITH collect(landmark) AS landmarks
            FOREACH (landmark IN landmarks | DETACH DELETE landmark)
            RETURN size(landmarks) AS deleted
            """,
            parameters_={"landmark_id": landmark_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def copy_locations(self,
                             source_id: str,
                             target_id: str,
                             ) -> tuple[list[Location], list[dict], list[dict]]:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            MATCH (target:World|Simulation {id: $target_id})
            MATCH (source)-[:CONTAINS]->(source_location:Location)
            WITH target, collect(source_location) AS source_locations
            UNWIND source_locations AS source_location
            CREATE (location:Location {
                id: randomUUID(),
                name: source_location.name,
                description: source_location.description
            })
            MERGE (target)-[:CONTAINS]->(location)
            WITH collect({
                source_id: source_location.id,
                copy_id: location.id,
                copy: location
            }) AS location_pairs
            CALL {
                WITH location_pairs
                UNWIND location_pairs AS child_pair
                UNWIND location_pairs AS parent_pair
                MATCH (:Location {id: parent_pair.source_id})-[:CONTAINS]->(:Location {id: child_pair.source_id})
                MATCH (parent_copy:Location {id: parent_pair.copy_id})
                MATCH (child_copy:Location {id: child_pair.copy_id})
                MERGE (parent_copy)-[:CONTAINS]->(child_copy)
                RETURN count(*) AS link_count
            }
            WITH location_pairs
            UNWIND location_pairs AS pair
            RETURN pair.source_id AS source_id, pair.copy_id AS copy_id, pair.copy AS location
            ORDER BY location.name
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )

        locations = [
            self.location_from_node(record["location"])
            for record in result.records
        ]
        location_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if not location_pairs:
            return locations, location_pairs, []

        landmark_result = await self._driver.execute_query(
            """
            UNWIND $location_pairs AS location_pair
            MATCH (source_location:Location {id: location_pair.source_id})-[:CONTAINS]->(source_landmark:Landmark)
            MATCH (copy_location:Location {id: location_pair.copy_id})
            CREATE (landmark:Landmark {
                id: randomUUID(),
                name: source_landmark.name,
                description: source_landmark.description
            })
            MERGE (copy_location)-[:CONTAINS]->(landmark)
            RETURN source_landmark.id AS source_id, landmark.id AS copy_id
            """,
            parameters_={"location_pairs": location_pairs},
        )
        landmark_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in landmark_result.records
        ]

        return locations, location_pairs, landmark_pairs
