from neo4j import AsyncDriver

from world_simulation_engine.model import Equipment, InventoryEquipment, Location
from .location_store import LocationStore


class EquipmentStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def equipment_from_node(equipment_node) -> Equipment:
        return Equipment(
            id=equipment_node["id"],
            name=equipment_node["name"],
            description=equipment_node["description"],
            quality=equipment_node.get("quality"),
        )

    @staticmethod
    def inventory_equipment_from_record(record) -> InventoryEquipment:
        return InventoryEquipment(
            **EquipmentStore.equipment_from_node(record["e"]).model_dump(),
            equipped=record["relationship_type"] == "EQUIPS",
            equipped_position=record.get("equipped_position"),
        )

    async def create_equipment(self,
                               equipment: Equipment,
                               source_id: str,
                               location_id: str | None = None,
                               position: str | None = None,
                               ) -> Equipment | None:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (loc:Location {id: $location_id})
            WITH source, loc
            WHERE $location_id IS NULL OR loc IS NOT NULL
            CREATE (e:Equipment {
                id: $id,
                name: $name,
                description: $description,
                quality: $quality
            })
            MERGE (source)-[:CONTAINS]->(e)
            FOREACH (_ IN CASE
                WHEN $location_id IS NOT NULL AND loc IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (e)-[present:PRESENT_IN]->(loc)
                SET present.position = $position
            )
            RETURN e
            """,
            parameters_={
                "id": equipment.id,
                "name": equipment.name,
                "description": equipment.description,
                "quality": equipment.quality,
                "source_id": source_id,
                "location_id": location_id,
                "position": position,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["e"])

    async def list_equipment(self,
                             world_id: str | None = None,
                             simulation_id: str | None = None,
                             location_id: str | None = None,
                             owner_id: str | None = None,
                             holder_id: str | None = None,
                             ) -> list[Equipment]:
        if world_id is not None and simulation_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(equipment:Equipment)
            """
        elif world_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})-[:CONTAINS]->(equipment:Equipment)
            """
        elif simulation_id is not None:
            source_match = """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(equipment:Equipment)
            """
        else:
            source_match = """
            MATCH (equipment:Equipment)
            """

        result = await self._driver.execute_query(
            source_match + """
            OPTIONAL MATCH (equipment)-[:PRESENT_IN]->(location:Location)
            OPTIONAL MATCH (owner)-[:OWNS]->(equipment)
            OPTIONAL MATCH (holder)-[:HOLDS|EQUIPS]->(equipment)
            WHERE ($location_id IS NULL OR location.id = $location_id AND holder IS NULL)
                AND ($owner_id IS NULL OR owner.id = $owner_id)
                AND ($holder_id IS NULL OR holder.id = $holder_id)
            RETURN DISTINCT equipment
            ORDER BY equipment.name
            """,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
                "location_id": location_id,
                "owner_id": owner_id,
                "holder_id": holder_id,
            },
        )

        return [
            self.equipment_from_node(record["equipment"])
            for record in result.records
        ]

    async def get_equipment(self, equipment_id: str) -> Equipment | None:
        result = await self._driver.execute_query(
            "MATCH (e:Equipment {id: $id}) RETURN e LIMIT 1",
            parameters_={"id": equipment_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["e"])

    async def update_equipment(self,
                               equipment_id: str,
                               properties: dict,
                               ) -> Equipment | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $id})
            SET equipment += $properties
            RETURN equipment LIMIT 1
            """,
            parameters_={
                "id": equipment_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["equipment"])

    async def delete_equipment(self, equipment_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $id})
            WITH collect(equipment) AS equipment_items
            FOREACH (equipment IN equipment_items | DETACH DELETE equipment)
            RETURN size(equipment_items) AS deleted
            """,
            parameters_={"id": equipment_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def get_equipment_inventory(self, holder_id: str) -> list[InventoryEquipment]:
        result = await self._driver.execute_query(
            """
            MATCH (holder {id: $holder_id}) -[r:HOLDS|EQUIPS]-> (e:Equipment)
            RETURN e, type(r) AS relationship_type, r.position AS equipped_position
            """,
            parameters_={"holder_id": holder_id}
        )

        return [self.inventory_equipment_from_record(record) for record in result.records]

    async def get_equipment_by_location(self,
                                        location_id: str,
                                        ) -> list[tuple[Equipment, Location, str | None, str | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id}) <-[r:PRESENT_IN]- (equipment:Equipment)
            OPTIONAL MATCH (holder)-[:HOLDS|EQUIPS]->(equipment)
            WITH equipment, location, r, holder
            WHERE holder IS NULL
            OPTIONAL MATCH (owner)-[:OWNS]->(equipment)
            RETURN equipment, location, r.position AS position, owner.id AS owner_id
            ORDER BY equipment.name
            """,
            parameters_={"location_id": location_id}
        )

        return [
            (
                self.equipment_from_node(record["equipment"]),
                LocationStore.location_from_node(record["location"]),
                record["position"],
                record["owner_id"],
            )
            for record in result.records
        ]

    async def place_equipment_in_location(self,
                                          equipment_id: str,
                                          location_id: str,
                                          position: str | None = None,
                                          ) -> Equipment | None:
        result = await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $id})
            OPTIONAL MATCH (holder)-[hold:HOLDS|EQUIPS]->(equipment)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(equipment)
            MATCH (location:Location {id: $location_id})
            DELETE hold, present
            MERGE (equipment)-[new_present:PRESENT_IN]->(location)
            SET new_present.position = $position
            RETURN equipment
            """,
            parameters_={
                "id": equipment_id,
                "location_id": location_id,
                "position": position,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["equipment"])

    async def change_owner(self, equipment_id: str, new_owner_id: str) -> Equipment | None:
        result = await self._driver.execute_query(
            """
            MATCH (e:Equipment {id: $id})
            OPTIONAL MATCH (o) -[r:OWNS]-> (e)
            MATCH (new_owner {id: $new_owner_id})
            DELETE r
            MERGE (new_owner)-[:OWNS]->(e)
            RETURN e
            """,
            parameters_={
                "id": equipment_id,
                "new_owner_id": new_owner_id
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["e"])

    async def change_hold_state(self,
                                equipment_id: str,
                                holder_id: str,
                                equipped: bool = False,
                                equipped_position: str | None = None,
                                ) -> Equipment | None:
        if not equipped:
            # New holder is holding it
            result = await self._driver.execute_query(
                """
                MATCH (e:Equipment {id: $id})
                OPTIONAL MATCH (h) -[r:HOLDS|EQUIPS]-> (e)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(e)
                MATCH (holder {id: $holder_id})
                DELETE r, present
                MERGE (holder)-[:HOLDS]->(e)
                RETURN e
                """,
                parameters_={
                    "id": equipment_id,
                    "holder_id": holder_id
                }
            )
        else:
            # Relationship is equips
            result = await self._driver.execute_query(
                """
                MATCH (e:Equipment {id: $id})
                OPTIONAL MATCH (h) -[r:HOLDS|EQUIPS]-> (e)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(e)
                MATCH (holder:Character {id: $holder_id})
                DELETE r, present
                MERGE (holder)-[equips:EQUIPS]->(e)
                SET equips.position = $position
                RETURN e
                """,
                parameters_={
                    "id": equipment_id,
                    "holder_id": holder_id,
                    "position": equipped_position,
                }
            )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["e"])

    async def copy_equipment(self,
                             source_id: str,
                             target_id: str,
                             location_pairs: list[dict] | None = None,
                             entity_pairs: list[dict] | None = None,
                             ) -> tuple[list[Equipment], list[dict]]:
        location_pairs = location_pairs or []
        entity_pairs = entity_pairs or []
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(source_equipment:Equipment)
            MATCH (target:World|Simulation {id: $target_id})
            CREATE (equipment:Equipment {
                id: randomUUID(),
                name: source_equipment.name,
                description: source_equipment.description,
                quality: source_equipment.quality
            })
            MERGE (target)-[:CONTAINS]->(equipment)
            RETURN source_equipment.id AS source_id, equipment.id AS copy_id, equipment
            ORDER BY equipment.name
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )
        equipment_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if equipment_pairs and location_pairs:
            await self._driver.execute_query(
                """
                UNWIND $equipment_pairs AS equipment_pair
                MATCH (source_equipment:Equipment {id: equipment_pair.source_id})-[source_present:PRESENT_IN]->(source_location:Location)
                WITH equipment_pair, source_present, [
                    location_pair IN $location_pairs
                    WHERE location_pair.source_id = source_location.id
                ][0] AS location_pair
                WHERE location_pair IS NOT NULL
                MATCH (copy_equipment:Equipment {id: equipment_pair.copy_id})
                MATCH (copy_location:Location {id: location_pair.copy_id})
                MERGE (copy_equipment)-[present:PRESENT_IN]->(copy_location)
                SET present.position = source_present.position
                """,
                parameters_={
                    "equipment_pairs": equipment_pairs,
                    "location_pairs": location_pairs,
                },
            )
        if equipment_pairs and entity_pairs:
            await self._driver.execute_query(
                """
                UNWIND $equipment_pairs AS equipment_pair
                MATCH (source_owner)-[:OWNS]->(:Equipment {id: equipment_pair.source_id})
                WITH equipment_pair, [
                    entity_pair IN $entity_pairs
                    WHERE entity_pair.source_id = source_owner.id
                ][0] AS owner_pair
                WHERE owner_pair IS NOT NULL
                MATCH (copy_owner {id: owner_pair.copy_id})
                MATCH (copy_equipment:Equipment {id: equipment_pair.copy_id})
                MERGE (copy_owner)-[:OWNS]->(copy_equipment)
                """,
                parameters_={
                    "equipment_pairs": equipment_pairs,
                    "entity_pairs": entity_pairs,
                },
            )
            await self._driver.execute_query(
                """
                UNWIND $equipment_pairs AS equipment_pair
                MATCH (source_holder)-[source_hold:HOLDS|EQUIPS]->(:Equipment {id: equipment_pair.source_id})
                WITH equipment_pair, source_hold, type(source_hold) AS relationship_type, [
                    entity_pair IN $entity_pairs
                    WHERE entity_pair.source_id = source_holder.id
                ][0] AS holder_pair
                WHERE holder_pair IS NOT NULL
                MATCH (copy_holder {id: holder_pair.copy_id})
                MATCH (copy_equipment:Equipment {id: equipment_pair.copy_id})
                FOREACH (_ IN CASE WHEN relationship_type = "HOLDS" THEN [1] ELSE [] END |
                    MERGE (copy_holder)-[:HOLDS]->(copy_equipment)
                )
                FOREACH (_ IN CASE WHEN relationship_type = "EQUIPS" THEN [1] ELSE [] END |
                    MERGE (copy_holder)-[equips:EQUIPS]->(copy_equipment)
                    SET equips.position = source_hold.position
                )
                """,
                parameters_={
                    "equipment_pairs": equipment_pairs,
                    "entity_pairs": entity_pairs,
                },
            )

        return (
            [
                self.equipment_from_node(record["equipment"])
                for record in result.records
            ],
            equipment_pairs,
        )
