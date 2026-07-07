from neo4j import AsyncDriver

from world_simulation_engine.model import Equipment


def _equipment_from_node(equipment_node) -> Equipment:
    return Equipment(
        id=equipment_node["id"],
        name=equipment_node["name"],
        description=equipment_node["description"],
        quality=equipment_node.get("quality"),
    )


def _inventory_equipment_from_record(record) -> "InventoryEquipment":
    return InventoryEquipment(
        **_equipment_from_node(record["e"]).model_dump(),
        equipped=record["relationship_type"] == "EQUIPS",
    )


class InventoryEquipment(Equipment):
    equipped: bool


class EquipmentStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_equipment(self, equipment: Equipment):
        await self._driver.execute_query(
            """
            CREATE (e:Equipment {
                id: $id,
                name: $name,
                description: $description,
                quality: $quality
            })
            """,
            parameters_={
                "id": equipment.id,
                "name": equipment.name,
                "description": equipment.description,
                "quality": equipment.quality,
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

        return _equipment_from_node(record["e"])

    async def get_equipment_inventory(self, holder_id: str) -> list[InventoryEquipment]:
        result = await self._driver.execute_query(
            """
            MATCH (holder {id: $holder_id}) -[r:HOLDS|EQUIPS]-> (e:Equipment)
            RETURN e, type(r) AS relationship_type
            """,
            parameters_={"holder_id": holder_id}
        )

        return [_inventory_equipment_from_record(record) for record in result.records]

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
                                ):
        if not equipped:
            # New holder is holding it
            await self._driver.execute_query(
                """
                MATCH (e:Equipment {id: $id})
                OPTIONAL MATCH (h) -[r:HOLDS|EQUIPS]-> (e)
                MATCH (holder {id: $holder_id})
                DELETE r
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
                MATCH (holder:Character {id: $holder_id})
                DELETE r
                MERGE (holder)-[:EQUIPS]->(e)
                """,
                parameters_={
                    "id": equipment_id,
                    "holder_id": holder_id
                }
            )
