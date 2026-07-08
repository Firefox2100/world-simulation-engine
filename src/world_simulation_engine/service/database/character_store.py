from neo4j import AsyncDriver

from world_simulation_engine.model import CurrentActivity, Character


def _character_from_node(character_node) -> Character:
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


class CharacterStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

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

        return _character_from_node(record["c"])

    async def move_to_location(self,
                               character_id: str,
                               location_id: str,
                               ):
        await self._driver.execute_query(
            """
            MATCH (c:Character {id: $character_id})
            OPTIONAL MATCH (:Location) <-[r:PRESENT_IN]- (c)
            MATCH (l:Location {id: $location_id})
            DELETE r
            MERGE (c) -[:PRESENT_IN]-> (l)
            """,
            parameters_={
                "character_id": character_id,
                "location_id": location_id,
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
