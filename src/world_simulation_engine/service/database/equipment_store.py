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
                               ):
        await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            CREATE (e:Equipment {
                id: $id,
                name: $name,
                description: $description,
                quality: $quality
            })
            MERGE (source)-[:CONTAINS]->(e)
            WITH e
            OPTIONAL MATCH (loc:Location {id: $location_id})
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

    async def get_equipment(self, equipment_id: str) -> Equipment | None:
        result = await self._driver.execute_query(
            "MATCH (e:Equipment {id: $id}) RETURN e LIMIT 1",
            parameters_={"id": equipment_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.equipment_from_node(record["e"])

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
                                          ):
        await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $id})
            OPTIONAL MATCH (holder)-[hold:HOLDS|EQUIPS]->(equipment)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(equipment)
            MATCH (location:Location {id: $location_id})
            DELETE hold, present
            MERGE (equipment)-[new_present:PRESENT_IN]->(location)
            SET new_present.position = $position
            """,
            parameters_={
                "id": equipment_id,
                "location_id": location_id,
                "position": position,
            }
        )

    async def change_owner(self, equipment_id: str, new_owner_id: str):
        await self._driver.execute_query(
            """
            MATCH (e:Equipment {id: $id})
            OPTIONAL MATCH (o) -[r:OWNS]-> (e)
            MATCH (new_owner {id: $new_owner_id})
            DELETE r
            MERGE (new_owner)-[:OWNS]->(e)
            """,
            parameters_={
                "id": equipment_id,
                "new_owner_id": new_owner_id
            }
        )

    async def change_hold_state(self,
                                equipment_id: str,
                                holder_id: str,
                                equipped: bool = False,
                                equipped_position: str | None = None,
                                ):
        if not equipped:
            # New holder is holding it
            await self._driver.execute_query(
                """
                MATCH (e:Equipment {id: $id})
                OPTIONAL MATCH (h) -[r:HOLDS|EQUIPS]-> (e)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(e)
                MATCH (holder {id: $holder_id})
                DELETE r, present
                MERGE (holder)-[:HOLDS]->(e)
                """,
                parameters_={
                    "id": equipment_id,
                    "holder_id": holder_id
                }
            )
        else:
            # Relationship is equips
            await self._driver.execute_query(
                """
                MATCH (e:Equipment {id: $id})
                OPTIONAL MATCH (h) -[r:HOLDS|EQUIPS]-> (e)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(e)
                MATCH (holder:Character {id: $holder_id})
                DELETE r, present
                MERGE (holder)-[equips:EQUIPS]->(e)
                SET equips.position = $position
                """,
                parameters_={
                    "id": equipment_id,
                    "holder_id": holder_id,
                    "position": equipped_position,
                }
            )
