from neo4j import AsyncDriver

from world_simulation_engine.model import CurrentActivity, Character, BackgroundCharacter, Location, Landmark
from .location_store import LocationStore


class CharacterStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def character_from_node(character_node) -> Character:
        return Character(
            id=character_node["id"],
            name=character_node["name"],
            age=character_node["age"],
            gender=character_node["gender"],
            appearance=character_node["appearance"],
            description=character_node["description"],
            public_state=character_node["public_state"],
            private_state=character_node["private_state"],
            current_activity=CurrentActivity.model_validate_json(character_node["current_activity"]),
        )

    @staticmethod
    def background_character_from_node(background_character_node) -> BackgroundCharacter:
        return BackgroundCharacter(
            id=background_character_node["id"],
            name=background_character_node["name"],
            description=background_character_node["description"],
        )

    async def create_character(self,
                               character: Character,
                               source_id: str,
                               ):
        await self._driver.execute_query(
            """
            MATCH (s:World|Simulation {id: $source_id})
            CREATE (c:Character {
                id: $id,
                name: $name,
                age: $age,
                gender: $gender,
                appearance: $appearance,
                description: $description,
                public_state: $public_state,
                private_state: $private_state,
                current_activity: $current_activity
            })
            MERGE (s) -[:CONTAINS]-> (c)
            RETURN c
            """,
            parameters_={
                "id": character.id,
                "name": character.name,
                "age": character.age,
                "gender": character.gender,
                "appearance": character.appearance,
                "description": character.description,
                "public_state": character.public_state,
                "private_state": character.private_state,
                "current_activity": character.current_activity.model_dump_json(),
                "source_id": source_id,
            }
        )

    async def get_character(self, character_id: str) -> Character | None:
        result = await self._driver.execute_query(
            "MATCH (c:Character {id: $character_id}) RETURN c LIMIT 1",
            parameters_={"character_id": character_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.character_from_node(record["c"])

    async def move_to_location(self,
                               character_id: str,
                               location_id: str,
                               position: str | None = None,
                               ):
        await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id})
            OPTIONAL MATCH (:Location) <-[r:PRESENT_IN]- (c)
            MATCH (l:Location {id: $location_id})
            DELETE r
            MERGE (c) -[present:PRESENT_IN]-> (l)
            SET present.position = $position
            """,
            parameters_={
                "character_id": character_id,
                "location_id": location_id,
                "position": position,
            }
        )

    async def anchor_to_landmark(self,
                                character_id: str,
                                landmark_id: str,
                                ):
        await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id})
            OPTIONAL MATCH (:Landmark) <-[r:ANCHORED_TO]- (c)
            MATCH (l:Landmark {id: $landmark_id})
            DELETE r
            MERGE (c) -[:ANCHORED_TO]-> (l)
            """,
            parameters_={
                "character_id": character_id,
                "landmark_id": landmark_id,
            }
        )

    async def create_background_character(self,
                                          character: BackgroundCharacter,
                                          source_id: str,
                                          location_id: str | None = None,
                                          position: str | None = None,
                                          landmark_id: str | None = None,
                                          ):
        await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            CREATE (c:BackgroundCharacter {
                id: $id,
                name: $name,
                description: $description
            })
            MERGE (source)-[:CONTAINS]->(c)
            WITH c
            OPTIONAL MATCH (loc:Location {id: $location_id})
            FOREACH (_ IN CASE
                WHEN $location_id IS NOT NULL AND loc IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (c)-[present:PRESENT_IN]->(loc)
                SET present.position = $position
            )
            WITH c
            OPTIONAL MATCH (landmark:Landmark {id: $landmark_id})
            FOREACH (_ IN CASE
                WHEN $landmark_id IS NOT NULL AND landmark IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (c)-[:ANCHORED_TO]->(landmark)
            )
            RETURN c
            """,
            parameters_={
                "id": character.id,
                "name": character.name,
                "description": character.description,
                "source_id": source_id,
                "location_id": location_id,
                "position": position,
                "landmark_id": landmark_id,
            },
        )

    async def get_background_character(self, character_id: str) -> BackgroundCharacter | None:
        result = await self._driver.execute_query(
            "MATCH (c:BackgroundCharacter {id: $character_id}) RETURN c LIMIT 1",
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def get_background_characters_by_location(self,
                                                    location_id: str,
                                                    ) -> list[
                                                        tuple[
                                                            BackgroundCharacter,
                                                            Location,
                                                            str | None,
                                                            Landmark | None,
                                                        ]
                                                    ]:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id}) <-[r:PRESENT_IN]- (character:BackgroundCharacter)
            OPTIONAL MATCH (character) -[:ANCHORED_TO]-> (landmark:Landmark) <-[:CONTAINS]- (location)
            RETURN character, location, r.position as position, landmark
            ORDER BY character.name
            """,
            parameters_={"location_id": location_id},
        )

        entries = []
        for record in result.records:
            landmark = None
            if record.get("landmark"):
                landmark = LocationStore.landmark_from_node(record["landmark"])

            entries.append((
                self.background_character_from_node(record["character"]),
                LocationStore.location_from_node(record["location"]),
                record["position"],
                landmark,
            ))

        return entries
