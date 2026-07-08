from neo4j import AsyncDriver

from world_simulation_engine.model import Item, ItemStack, InventoryStack


def _item_from_node(item_node) -> Item:
    return Item(
        id=item_node["id"],
        name=item_node["name"],
        description=item_node["description"],
        unique=item_node["unique"],
    )


def _inventory_stack_from_record(record) -> InventoryStack:
    return InventoryStack(
        item_id=record["i"]["id"],
        name=record["i"]["name"],
        description=record["i"]["description"],
        unique=record["i"]["unique"],
        stack_id=record["s"]["id"],
        quantity=record["s"]["quantity"],
        quality=record["s"].get("quality"),
        owner_id=record["o"]["id"] if record["o"] else None,
    )


class ItemStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_item(self, item: Item):
        await self._driver.execute_query(
            """
            CREATE (i:Item {
                id: $id,
                name: $name,
                description: $description,
                unique: $unique
            }) RETURN i
            """,
            parameters_={
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "unique": item.unique,
            }
        )

    async def get_item(self, item_id: str) -> Item | None:
        result = await self._driver.execute_query(
            "MATCH (i:Item {id: $id}) RETURN i",
            parameters_={"id": item_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _item_from_node(record["i"])

    async def create_stack(self,
                           item_id: str,
                           stack: ItemStack,
                           ):
        await self._driver.execute_query(
            """
            MATCH (i:Item {id: $item_id})
            CREATE (s:ItemStack {
                id: $id,
                quantity: $quantity,
                quality: $quality
            })
            MERGE (s) -[:OF_TYPE]-> (i)
            """,
            parameters_={
                "item_id": item_id,
                "id": stack.id,
                "quantity": stack.quantity,
                "quality": stack.quality,
            }
        )

    async def assign_stack(self,
                           stack_id: str,
                           holder_id: str | None = None,
                           owner_id: str | None = None,
                           ):
        if holder_id:
            await self._driver.execute_query(
                """
                MATCH (s:ItemStack {id: $stack_id})
                OPTIONAL MATCH (o)-[r:HOLDS]->(s)
                MATCH (h {id: $holder_id})
                DELETE r
                MERGE (h) -[:HOLDS]-> (s)
                """,
                parameters_={
                    "stack_id": stack_id,
                    "holder_id": holder_id,
                }
            )

        if owner_id:
            await self._driver.execute_query(
                """
                MATCH (s:ItemStack {id: $stack_id})
                OPTIONAL MATCH (previous_owner)-[r:OWNS]->(s)
                MATCH (owner {id: $owner_id})
                DELETE r
                MERGE (owner) -[:OWNS]-> (s)
                """,
                parameters_={
                    "stack_id": stack_id,
                    "owner_id": owner_id,
                }
            )

    async def get_inventory(self, holder_id: str) -> list[InventoryStack]:
        result = await self._driver.execute_query(
            """
            MATCH (h {id: $holder_id}) -[:HOLDS]-> (s:ItemStack) -[:OF_TYPE]->(i:Item)
            OPTIONAL MATCH (o)-[r:OWNS]->(s)
            RETURN s, i, o
            """,
            parameters_={
                "holder_id": holder_id,
            }
        )

        return [_inventory_stack_from_record(record) for record in result.records]
