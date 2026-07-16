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
            user_controlled=character_node["user_controlled"],
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
                               ) -> Character | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:World|Simulation {id: $source_id})
            CREATE (c:Character {
                id: $id,
                user_controlled: $user_controlled,
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
                "user_controlled": character.user_controlled,
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.character_from_node(record["c"])

    async def list_characters(self,
                              world_id: str | None = None,
                              simulation_id: str | None = None,
                              ) -> list[Character]:
        if world_id is not None and simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(c:Character)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={
                    "world_id": world_id,
                    "simulation_id": simulation_id,
                },
            )
        elif world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})-[:CONTAINS]->(c:Character)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={"world_id": world_id},
            )
        elif simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(c:Character)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={"simulation_id": simulation_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (c:Character)
                RETURN c
                ORDER BY c.name
                """
            )

        return [
            self.character_from_node(record["c"])
            for record in result.records
        ]

    async def get_character(self, character_id: str) -> Character | None:
        result = await self._driver.execute_query(
            "MATCH (c:Character {id: $character_id}) RETURN c LIMIT 1",
            parameters_={"character_id": character_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.character_from_node(record["c"])

    async def update_character(self,
                               character_id: str,
                               properties: dict,
                               ) -> Character | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }
        current_activity = properties.get("current_activity")
        if current_activity is not None:
            if not isinstance(current_activity, CurrentActivity):
                current_activity = CurrentActivity.model_validate(current_activity)
            properties["current_activity"] = current_activity.model_dump_json()

        result = await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id})
            SET c += $properties
            RETURN c LIMIT 1
            """,
            parameters_={
                "character_id": character_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.character_from_node(record["c"])

    async def delete_character(self, character_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id})
            WITH collect(c) AS characters
            FOREACH (character IN characters | DETACH DELETE character)
            RETURN size(characters) AS deleted
            """,
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def copy_characters(self,
                              source_id: str,
                              target_id: str,
                              location_pairs: list[dict] | None = None,
                              landmark_pairs: list[dict] | None = None,
                              return_pairs: bool = False,
                              ) -> list[Character] | tuple[list[Character], list[dict]]:
        location_pairs = location_pairs or []
        landmark_pairs = landmark_pairs or []
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(source_character:Character)
            MATCH (target:World|Simulation {id: $target_id})
            CREATE (character:Character {
                id: randomUUID(),
                user_controlled: source_character.user_controlled,
                name: source_character.name,
                age: source_character.age,
                gender: source_character.gender,
                appearance: source_character.appearance,
                description: source_character.description,
                public_state: source_character.public_state,
                private_state: source_character.private_state,
                current_activity: source_character.current_activity
            })
            MERGE (target)-[:CONTAINS]->(character)
            RETURN source_character.id AS source_id, character.id AS copy_id, character
            ORDER BY character.name
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )
        character_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if character_pairs and location_pairs:
            await self._driver.execute_query(
                """
                UNWIND $character_pairs AS character_pair
                MATCH (source_character:Character {id: character_pair.source_id})-[source_present:PRESENT_IN]->(source_location:Location)
                WITH character_pair, source_present, [
                    location_pair IN $location_pairs
                    WHERE location_pair.source_id = source_location.id
                ][0] AS location_pair
                WHERE location_pair IS NOT NULL
                MATCH (copy_character:Character {id: character_pair.copy_id})
                MATCH (copy_location:Location {id: location_pair.copy_id})
                MERGE (copy_character)-[present:PRESENT_IN]->(copy_location)
                SET present.position = source_present.position
                """,
                parameters_={
                    "character_pairs": character_pairs,
                    "location_pairs": location_pairs,
                },
            )
        if character_pairs and landmark_pairs:
            await self._driver.execute_query(
                """
                UNWIND $character_pairs AS character_pair
                MATCH (source_character:Character {id: character_pair.source_id})-[:ANCHORED_TO]->(source_landmark:Landmark)
                WITH character_pair, [
                    landmark_pair IN $landmark_pairs
                    WHERE landmark_pair.source_id = source_landmark.id
                ][0] AS landmark_pair
                WHERE landmark_pair IS NOT NULL
                MATCH (copy_character:Character {id: character_pair.copy_id})
                MATCH (copy_landmark:Landmark {id: landmark_pair.copy_id})
                MERGE (copy_character)-[:ANCHORED_TO]->(copy_landmark)
                """,
                parameters_={
                    "character_pairs": character_pairs,
                    "landmark_pairs": landmark_pairs,
                },
            )

        characters = [
            self.character_from_node(record["character"])
            for record in result.records
        ]
        if return_pairs:
            return characters, character_pairs

        return characters

    async def get_user_character_by_simulation(self, simulation_id: str) -> Character | None:
        result = await self._driver.execute_query(
            """
            MATCH (c:Character {user_controlled: true}) <-[:CONTAINS]-(s:Simulation {id: $simulation_id})
            RETURN c LIMIT 1
            """,
            parameters_={"simulation_id": simulation_id}
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
                                          ) -> BackgroundCharacter | None:
        result = await self._driver.execute_query(
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def list_background_characters(self,
                                         world_id: str | None = None,
                                         simulation_id: str | None = None,
                                         location_id: str | None = None,
                                         ) -> list[BackgroundCharacter]:
        if location_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Location {id: $location_id})<-[:PRESENT_IN]-(c:BackgroundCharacter)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={"location_id": location_id},
            )
        elif world_id is not None and simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(c:BackgroundCharacter)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={
                    "world_id": world_id,
                    "simulation_id": simulation_id,
                },
            )
        elif world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})-[:CONTAINS]->(c:BackgroundCharacter)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={"world_id": world_id},
            )
        elif simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(c:BackgroundCharacter)
                RETURN c
                ORDER BY c.name
                """,
                parameters_={"simulation_id": simulation_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (c:BackgroundCharacter)
                RETURN c
                ORDER BY c.name
                """
            )

        return [
            self.background_character_from_node(record["c"])
            for record in result.records
        ]

    async def get_background_character(self, character_id: str) -> BackgroundCharacter | None:
        result = await self._driver.execute_query(
            "MATCH (c:BackgroundCharacter {id: $character_id}) RETURN c LIMIT 1",
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def update_background_character(self,
                                          character_id: str,
                                          properties: dict,
                                          ) -> BackgroundCharacter | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (c:BackgroundCharacter {id: $character_id})
            SET c += $properties
            RETURN c LIMIT 1
            """,
            parameters_={
                "character_id": character_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def delete_background_character(self, character_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (c:BackgroundCharacter {id: $character_id})
            WITH collect(c) AS characters
            FOREACH (character IN characters | DETACH DELETE character)
            RETURN size(characters) AS deleted
            """,
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def move_background_character_to_location(self,
                                                    character_id: str,
                                                    location_id: str,
                                                    position: str | None = None,
                                                    ) -> BackgroundCharacter | None:
        result = await self._driver.execute_query(
            """
            MATCH (c:BackgroundCharacter {id: $character_id})
            OPTIONAL MATCH (:Location)<-[r:PRESENT_IN]-(c)
            MATCH (location:Location {id: $location_id})
            DELETE r
            MERGE (c)-[present:PRESENT_IN]->(location)
            SET present.position = $position
            RETURN c
            """,
            parameters_={
                "character_id": character_id,
                "location_id": location_id,
                "position": position,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def anchor_background_character_to_landmark(self,
                                                      character_id: str,
                                                      landmark_id: str,
                                                      ) -> BackgroundCharacter | None:
        result = await self._driver.execute_query(
            """
            MATCH (c:BackgroundCharacter {id: $character_id})
            OPTIONAL MATCH (:Landmark)<-[r:ANCHORED_TO]-(c)
            MATCH (landmark:Landmark {id: $landmark_id})
            DELETE r
            MERGE (c)-[:ANCHORED_TO]->(landmark)
            RETURN c
            """,
            parameters_={
                "character_id": character_id,
                "landmark_id": landmark_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.background_character_from_node(record["c"])

    async def copy_background_characters(self,
                                         source_id: str,
                                         target_id: str,
                                         location_pairs: list[dict] | None = None,
                                         landmark_pairs: list[dict] | None = None,
                                         ) -> tuple[list[BackgroundCharacter], list[dict]]:
        location_pairs = location_pairs or []
        landmark_pairs = landmark_pairs or []
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(source_character:BackgroundCharacter)
            MATCH (target:World|Simulation {id: $target_id})
            CREATE (character:BackgroundCharacter {
                id: randomUUID(),
                name: source_character.name,
                description: source_character.description
            })
            MERGE (target)-[:CONTAINS]->(character)
            RETURN source_character.id AS source_id, character.id AS copy_id, character
            ORDER BY character.name
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )
        character_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if character_pairs and location_pairs:
            await self._driver.execute_query(
                """
                UNWIND $character_pairs AS character_pair
                MATCH (source_character:BackgroundCharacter {id: character_pair.source_id})-[source_present:PRESENT_IN]->(source_location:Location)
                WITH character_pair, source_present, [
                    location_pair IN $location_pairs
                    WHERE location_pair.source_id = source_location.id
                ][0] AS location_pair
                WHERE location_pair IS NOT NULL
                MATCH (copy_character:BackgroundCharacter {id: character_pair.copy_id})
                MATCH (copy_location:Location {id: location_pair.copy_id})
                MERGE (copy_character)-[present:PRESENT_IN]->(copy_location)
                SET present.position = source_present.position
                """,
                parameters_={
                    "character_pairs": character_pairs,
                    "location_pairs": location_pairs,
                },
            )
        if character_pairs and landmark_pairs:
            await self._driver.execute_query(
                """
                UNWIND $character_pairs AS character_pair
                MATCH (source_character:BackgroundCharacter {id: character_pair.source_id})-[:ANCHORED_TO]->(source_landmark:Landmark)
                WITH character_pair, [
                    landmark_pair IN $landmark_pairs
                    WHERE landmark_pair.source_id = source_landmark.id
                ][0] AS landmark_pair
                WHERE landmark_pair IS NOT NULL
                MATCH (copy_character:BackgroundCharacter {id: character_pair.copy_id})
                MATCH (copy_landmark:Landmark {id: landmark_pair.copy_id})
                MERGE (copy_character)-[:ANCHORED_TO]->(copy_landmark)
                """,
                parameters_={
                    "character_pairs": character_pairs,
                    "landmark_pairs": landmark_pairs,
                },
            )

        return (
            [
                self.background_character_from_node(record["character"])
                for record in result.records
            ],
            character_pairs,
        )

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
