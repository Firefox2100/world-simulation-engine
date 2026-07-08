from neo4j import AsyncDriver

from world_simulation_engine.model import Item, ItemStack, InventoryStack, Location
from .location_store import LocationStore


class ItemStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def item_from_node(item_node) -> Item:
        return Item(
            id=item_node["id"],
            name=item_node["name"],
            description=item_node["description"],
            unique=item_node["unique"],
        )

    @staticmethod
    def inventory_stack_from_record(record) -> InventoryStack:
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

    @staticmethod
    def stack_from_node(stack_node) -> ItemStack:
        return ItemStack(
            id=stack_node["id"],
            quantity=stack_node["quantity"],
            quality=stack_node.get("quality"),
        )

    async def create_item(self,
                          item: Item,
                          source_id: str,
                          ):
        await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            CREATE (i:Item {
                id: $id,
                name: $name,
                description: $description,
                unique: $unique
            })
            MERGE (source)-[:CONTAINS]->(i)
            RETURN i
            """,
            parameters_={
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "unique": item.unique,
                "source_id": source_id,
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

        return self.item_from_node(record["i"])

    async def create_stack(self,
                           item_id: str,
                           stack: ItemStack,
                           location_id: str | None = None,
                           position: str | None = None,
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
            WITH s
            OPTIONAL MATCH (loc:Location {id: $location_id})
            FOREACH (_ IN CASE
                WHEN $location_id IS NOT NULL AND loc IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (s)-[present:PRESENT_IN]->(loc)
                SET present.position = $position
            )
            """,
            parameters_={
                "item_id": item_id,
                "id": stack.id,
                "quantity": stack.quantity,
                "quality": stack.quality,
                "location_id": location_id,
                "position": position,
            }
        )

    async def place_stack_in_location(self,
                                      stack_id: str,
                                      location_id: str,
                                      position: str | None = None,
                                      ):
        await self._driver.execute_query(
            """
            MATCH (s:ItemStack {id: $stack_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(s)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(s)
            MATCH (loc:Location {id: $location_id})
            DELETE hold, present
            MERGE (s)-[new_present:PRESENT_IN]->(loc)
            SET new_present.position = $position
            """,
            parameters_={
                "stack_id": stack_id,
                "location_id": location_id,
                "position": position,
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
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(s)
                MATCH (h {id: $holder_id})
                DELETE r, present
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

        return [self.inventory_stack_from_record(record) for record in result.records]

    async def get_stacks_by_location(self,
                                     location_id: str,
                                     ) -> list[tuple[Item, ItemStack, Location, str | None, str | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id}) <-[r:PRESENT_IN]- (stack:ItemStack) -[:OF_TYPE]-> (item:Item)
            OPTIONAL MATCH (owner)-[:OWNS]->(stack)
            RETURN item, stack, location, r.position AS position, owner.id AS owner_id
            ORDER BY item.name, stack.id
            """,
            parameters_={
                "location_id": location_id,
            }
        )

        return [
            (
                self.item_from_node(record["item"]),
                self.stack_from_node(record["stack"]),
                LocationStore.location_from_node(record["location"]),
                record["position"],
                record["owner_id"],
            )
            for record in result.records
        ]
