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

    async def entity_exists(self, entity_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (entity {id: $id})
            RETURN count(entity) AS entity_count
            """,
            parameters_={"id": entity_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["entity_count"])

    async def create_item(self,
                          item: Item,
                          source_id: str,
                          ) -> Item | None:
        result = await self._driver.execute_query(
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.item_from_node(record["i"])

    async def list_items(self,
                         world_id: str | None = None,
                         simulation_id: str | None = None,
                         ) -> list[Item]:
        if world_id is not None and simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(i:Item)
                RETURN i
                ORDER BY i.name
                """,
                parameters_={
                    "world_id": world_id,
                    "simulation_id": simulation_id,
                },
            )
        elif world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})-[:CONTAINS]->(i:Item)
                RETURN i
                ORDER BY i.name
                """,
                parameters_={"world_id": world_id},
            )
        elif simulation_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(i:Item)
                RETURN i
                ORDER BY i.name
                """,
                parameters_={"simulation_id": simulation_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (i:Item)
                RETURN i
                ORDER BY i.name
                """
            )

        return [
            self.item_from_node(record["i"])
            for record in result.records
        ]

    async def get_item(self, item_id: str) -> Item | None:
        result = await self._driver.execute_query(
            "MATCH (i:Item {id: $id}) RETURN i",
            parameters_={"id": item_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.item_from_node(record["i"])

    async def update_item(self,
                          item_id: str,
                          properties: dict,
                          ) -> Item | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (i:Item {id: $id})
            SET i += $properties
            RETURN i LIMIT 1
            """,
            parameters_={
                "id": item_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.item_from_node(record["i"])

    async def delete_item(self, item_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (i:Item {id: $id})
            OPTIONAL MATCH (stack:ItemStack)-[:OF_TYPE]->(i)
            WITH collect(DISTINCT i) AS items, collect(DISTINCT stack) AS stacks
            WITH items + stacks AS nodes, size(items) AS deleted
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted
            """,
            parameters_={"id": item_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_stack(self,
                           item_id: str,
                           stack: ItemStack,
                           location_id: str | None = None,
                           position: str | None = None,
                           source_id: str | None = None,
                           holder_id: str | None = None,
                           owner_id: str | None = None,
                           ) -> ItemStack | None:
        if source_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (source:World|Simulation {id: $source_id})
                MATCH (item:Item {id: $item_id})
                OPTIONAL MATCH (source)-[:CONTAINS]->(direct_item:Item {id: $item_id})
                OPTIONAL MATCH (source)-[:BASED_ON]->(:World)-[:CONTAINS]->(world_item:Item {id: $item_id})
                OPTIONAL MATCH (location:Location {id: $location_id})
                OPTIONAL MATCH (holder {id: $holder_id})
                OPTIONAL MATCH (owner {id: $owner_id})
                WITH source, item, direct_item, world_item, location, holder, owner
                WHERE (direct_item IS NOT NULL OR world_item IS NOT NULL)
                    AND ($location_id IS NULL OR location IS NOT NULL)
                    AND ($holder_id IS NULL OR holder IS NOT NULL)
                    AND ($owner_id IS NULL OR owner IS NOT NULL)
                    AND ($location_id IS NOT NULL OR $holder_id IS NOT NULL)
                CREATE (stack:ItemStack {
                    id: $id,
                    quantity: $quantity,
                    quality: $quality
                })
                MERGE (source)-[:CONTAINS]->(stack)
                MERGE (stack)-[:OF_TYPE]->(item)
                FOREACH (_ IN CASE
                    WHEN $location_id IS NOT NULL AND location IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (stack)-[present:PRESENT_IN]->(location)
                    SET present.position = $position
                )
                FOREACH (_ IN CASE
                    WHEN $holder_id IS NOT NULL AND holder IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (holder)-[:HOLDS]->(stack)
                )
                FOREACH (_ IN CASE
                    WHEN $owner_id IS NOT NULL AND owner IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (owner)-[:OWNS]->(stack)
                )
                RETURN stack
                """,
                parameters_={
                    "source_id": source_id,
                    "item_id": item_id,
                    "id": stack.id,
                    "quantity": stack.quantity,
                    "quality": stack.quality,
                    "location_id": location_id,
                    "position": position,
                    "holder_id": holder_id,
                    "owner_id": owner_id,
                },
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (source:World|Simulation)-[:CONTAINS]->(item:Item {id: $item_id})
                OPTIONAL MATCH (location:Location {id: $location_id})
                OPTIONAL MATCH (holder {id: $holder_id})
                OPTIONAL MATCH (owner {id: $owner_id})
                WITH source, item, location, holder, owner
                WHERE ($location_id IS NULL OR location IS NOT NULL)
                    AND ($holder_id IS NULL OR holder IS NOT NULL)
                    AND ($owner_id IS NULL OR owner IS NOT NULL)
                    AND ($location_id IS NOT NULL OR $holder_id IS NOT NULL)
                LIMIT 1
                CREATE (stack:ItemStack {
                    id: $id,
                    quantity: $quantity,
                    quality: $quality
                })
                MERGE (source)-[:CONTAINS]->(stack)
                MERGE (stack)-[:OF_TYPE]->(item)
                FOREACH (_ IN CASE
                    WHEN $location_id IS NOT NULL AND location IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (stack)-[present:PRESENT_IN]->(location)
                    SET present.position = $position
                )
                FOREACH (_ IN CASE
                    WHEN $holder_id IS NOT NULL AND holder IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (holder)-[:HOLDS]->(stack)
                )
                FOREACH (_ IN CASE
                    WHEN $owner_id IS NOT NULL AND owner IS NOT NULL
                    THEN [1]
                    ELSE []
                END |
                    MERGE (owner)-[:OWNS]->(stack)
                )
                RETURN stack
                """,
                parameters_={
                    "item_id": item_id,
                    "id": stack.id,
                    "quantity": stack.quantity,
                    "quality": stack.quality,
                    "location_id": location_id,
                    "position": position,
                    "holder_id": holder_id,
                    "owner_id": owner_id,
                },
            )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.stack_from_node(record["stack"])

    async def list_stacks(self,
                          world_id: str | None = None,
                          simulation_id: str | None = None,
                          item_id: str | None = None,
                          owner_id: str | None = None,
                          holder_id: str | None = None,
                          location_id: str | None = None,
                          ) -> list[ItemStack]:
        if world_id is not None and simulation_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(stack:ItemStack)
            MATCH (stack)-[:OF_TYPE]->(item:Item)
            """
        elif world_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})-[:CONTAINS]->(stack:ItemStack)
            MATCH (stack)-[:OF_TYPE]->(item:Item)
            """
        elif simulation_id is not None:
            source_match = """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(stack:ItemStack)
            MATCH (stack)-[:OF_TYPE]->(item:Item)
            """
        else:
            source_match = """
            MATCH (stack:ItemStack)-[:OF_TYPE]->(item:Item)
            """

        result = await self._driver.execute_query(
            source_match + """
            OPTIONAL MATCH (owner)-[:OWNS]->(stack)
            OPTIONAL MATCH (holder)-[:HOLDS]->(stack)
            OPTIONAL MATCH (stack)-[:PRESENT_IN]->(location:Location)
            WHERE ($item_id IS NULL OR item.id = $item_id)
                AND ($owner_id IS NULL OR owner.id = $owner_id)
                AND ($holder_id IS NULL OR holder.id = $holder_id)
                AND ($location_id IS NULL OR location.id = $location_id AND holder IS NULL)
            RETURN DISTINCT stack
            ORDER BY stack.id
            """,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
                "item_id": item_id,
                "owner_id": owner_id,
                "holder_id": holder_id,
                "location_id": location_id,
            },
        )

        return [
            self.stack_from_node(record["stack"])
            for record in result.records
        ]

    async def get_stack(self, stack_id: str) -> ItemStack | None:
        result = await self._driver.execute_query(
            """
            MATCH (stack:ItemStack {id: $id})
            RETURN stack LIMIT 1
            """,
            parameters_={"id": stack_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.stack_from_node(record["stack"])

    async def update_stack(self,
                           stack_id: str,
                           properties: dict,
                           ) -> ItemStack | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (stack:ItemStack {id: $id})
            SET stack += $properties
            RETURN stack LIMIT 1
            """,
            parameters_={
                "id": stack_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.stack_from_node(record["stack"])

    async def delete_stack(self, stack_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (stack:ItemStack {id: $id})
            WITH collect(stack) AS stacks
            FOREACH (stack IN stacks | DETACH DELETE stack)
            RETURN size(stacks) AS deleted
            """,
            parameters_={"id": stack_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def place_stack_in_location(self,
                                      stack_id: str,
                                      location_id: str,
                                      position: str | None = None,
                                      ) -> ItemStack | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:ItemStack {id: $stack_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(s)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(s)
            MATCH (loc:Location {id: $location_id})
            DELETE hold, present
            MERGE (s)-[new_present:PRESENT_IN]->(loc)
            SET new_present.position = $position
            RETURN s
            """,
            parameters_={
                "stack_id": stack_id,
                "location_id": location_id,
                "position": position,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.stack_from_node(record["s"])

    async def assign_stack(self,
                           stack_id: str,
                           holder_id: str | None = None,
                           owner_id: str | None = None,
                           ) -> ItemStack | None:
        stack: ItemStack | None = await self.get_stack(stack_id)
        if stack is None:
            return None

        if holder_id:
            result = await self._driver.execute_query(
                """
                MATCH (s:ItemStack {id: $stack_id})
                OPTIONAL MATCH (o)-[r:HOLDS]->(s)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(s)
                MATCH (h {id: $holder_id})
                DELETE r, present
                MERGE (h) -[:HOLDS]-> (s)
                RETURN s
                """,
                parameters_={
                    "stack_id": stack_id,
                    "holder_id": holder_id,
                }
            )
            record = result.records[0] if result.records else None
            if not record:
                return None
            stack = self.stack_from_node(record["s"])

        if owner_id:
            result = await self._driver.execute_query(
                """
                MATCH (s:ItemStack {id: $stack_id})
                OPTIONAL MATCH (previous_owner)-[r:OWNS]->(s)
                MATCH (owner {id: $owner_id})
                DELETE r
                MERGE (owner) -[:OWNS]-> (s)
                RETURN s
                """,
                parameters_={
                    "stack_id": stack_id,
                    "owner_id": owner_id,
                }
            )
            record = result.records[0] if result.records else None
            if not record:
                return None
            stack = self.stack_from_node(record["s"])

        return stack

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
            OPTIONAL MATCH (holder)-[:HOLDS]->(stack)
            WITH item, stack, location, r, holder
            WHERE holder IS NULL
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
