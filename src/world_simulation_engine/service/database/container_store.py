from neo4j import AsyncDriver

from world_simulation_engine.model import Container, Location, Item, ItemStack, Equipment
from .equipment_store import EquipmentStore
from .item_store import ItemStore
from .location_store import LocationStore


class ContainerStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def container_from_node(container_node) -> Container:
        return Container(
            id=container_node["id"],
            name=container_node["name"],
            description=container_node["description"],
            state=container_node["state"],
        )

    async def create_container(self,
                               container: Container,
                               source_id: str,
                               location_id: str | None = None,
                               position: str | None = None,
                               ):
        await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            CREATE (c:Container {
                id: $id,
                name: $name,
                description: $description,
                state: $state
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
            RETURN c
            """,
            parameters_={
                "id": container.id,
                "name": container.name,
                "description": container.description,
                "state": container.state,
                "source_id": source_id,
                "location_id": location_id,
                "position": position,
            }
        )

    async def get_container(self, container_id: str) -> Container | None:
        result = await self._driver.execute_query(
            "MATCH (c:Container {id: $id}) RETURN c LIMIT 1",
            parameters_={"id": container_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["c"])

    async def get_containers_by_location(self,
                                         location_id: str,
                                         ) -> list[tuple[Container, Location, str | None, str | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id}) <-[r:PRESENT_IN]- (container:Container)
            OPTIONAL MATCH (owner)-[:OWNS]->(container)
            RETURN container, location, r.position AS position, owner.id AS owner_id
            ORDER BY container.name
            """,
            parameters_={"location_id": location_id},
        )

        return [
            (
                self.container_from_node(record["container"]),
                LocationStore.location_from_node(record["location"]),
                record["position"],
                record["owner_id"],
            )
            for record in result.records
        ]

    async def place_container_in_location(self,
                                          container_id: str,
                                          location_id: str,
                                          position: str | None = None,
                                          ):
        await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(container)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(container)
            MATCH (location:Location {id: $location_id})
            DELETE hold, present
            MERGE (container)-[new_present:PRESENT_IN]->(location)
            SET new_present.position = $position
            """,
            parameters_={
                "container_id": container_id,
                "location_id": location_id,
                "position": position,
            },
        )

    async def assign_container(self,
                               container_id: str,
                               holder_id: str | None = None,
                               owner_id: str | None = None,
                               ):
        if holder_id:
            await self._driver.execute_query(
                """
                MATCH (container:Container {id: $container_id})
                OPTIONAL MATCH (holder)-[hold:HOLDS]->(container)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(container)
                MATCH (new_holder {id: $holder_id})
                DELETE hold, present
                MERGE (new_holder)-[:HOLDS]->(container)
                """,
                parameters_={
                    "container_id": container_id,
                    "holder_id": holder_id,
                },
            )

        if owner_id:
            await self._driver.execute_query(
                """
                MATCH (container:Container {id: $container_id})
                OPTIONAL MATCH (previous_owner)-[owns:OWNS]->(container)
                MATCH (owner {id: $owner_id})
                DELETE owns
                MERGE (owner)-[:OWNS]->(container)
                """,
                parameters_={
                    "container_id": container_id,
                    "owner_id": owner_id,
                },
            )

    async def put_stack_in_container(self,
                                     stack_id: str,
                                     container_id: str,
                                     ):
        await self._driver.execute_query(
            """
            MATCH (stack:ItemStack {id: $stack_id})
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(stack)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(stack)
            DELETE hold, present
            MERGE (container)-[:HOLDS]->(stack)
            """,
            parameters_={
                "stack_id": stack_id,
                "container_id": container_id,
            },
        )

    async def put_equipment_in_container(self,
                                         equipment_id: str,
                                         container_id: str,
                                         ):
        await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $equipment_id})
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS|EQUIPS]->(equipment)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(equipment)
            DELETE hold, present
            MERGE (container)-[:HOLDS]->(equipment)
            """,
            parameters_={
                "equipment_id": equipment_id,
                "container_id": container_id,
            },
        )

    async def put_container_in_container(self,
                                        held_container_id: str,
                                        holder_container_id: str,
                                        ):
        await self._driver.execute_query(
            """
            MATCH (held:Container {id: $held_container_id})
            MATCH (holder:Container {id: $holder_container_id})
            WHERE held <> holder
            OPTIONAL MATCH (previous_holder)-[hold:HOLDS]->(held)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(held)
            DELETE hold, present
            MERGE (holder)-[:HOLDS]->(held)
            """,
            parameters_={
                "held_container_id": held_container_id,
                "holder_container_id": holder_container_id,
            },
        )

    async def get_held_stacks(self,
                              container_id: str,
                              ) -> list[tuple[Item, ItemStack]]:
        result = await self._driver.execute_query(
            """
            MATCH (:Container {id: $container_id}) -[:HOLDS]-> (stack:ItemStack) -[:OF_TYPE]-> (item:Item)
            RETURN item, stack
            ORDER BY item.name, stack.id
            """,
            parameters_={"container_id": container_id},
        )

        return [
            (ItemStore.item_from_node(record["item"]), ItemStore.stack_from_node(record["stack"]))
            for record in result.records
        ]

    async def get_held_equipment(self,
                                 container_id: str,
                                 ) -> list[Equipment]:
        result = await self._driver.execute_query(
            """
            MATCH (:Container {id: $container_id}) -[:HOLDS]-> (equipment:Equipment)
            RETURN equipment
            ORDER BY equipment.name
            """,
            parameters_={"container_id": container_id},
        )

        return [
            EquipmentStore.equipment_from_node(record["equipment"])
            for record in result.records
        ]

    async def get_held_containers(self,
                                  container_id: str,
                                  ) -> list[Container]:
        result = await self._driver.execute_query(
            """
            MATCH (:Container {id: $container_id}) -[:HOLDS]-> (container:Container)
            RETURN container
            ORDER BY container.name
            """,
            parameters_={"container_id": container_id},
        )

        return [
            self.container_from_node(record["container"])
            for record in result.records
        ]

    async def add_unlocking_item(self,
                                 item_id: str,
                                 container_id: str,
                                 ):
        await self._driver.execute_query(
            """
            MATCH (item:Item {id: $item_id})
            MATCH (container:Container {id: $container_id})
            MERGE (item)-[:UNLOCKS]->(container)
            """,
            parameters_={
                "item_id": item_id,
                "container_id": container_id,
            },
        )

    async def remove_unlocking_item(self,
                                    item_id: str,
                                    container_id: str,
                                    ):
        await self._driver.execute_query(
            """
            MATCH (:Item {id: $item_id}) -[unlocks:UNLOCKS]-> (:Container {id: $container_id})
            DELETE unlocks
            """,
            parameters_={
                "item_id": item_id,
                "container_id": container_id,
            },
        )

    async def get_unlocking_items(self,
                                  container_id: str,
                                  ) -> list[Item]:
        result = await self._driver.execute_query(
            """
            MATCH (item:Item) -[:UNLOCKS]-> (:Container {id: $container_id})
            RETURN item
            ORDER BY item.name
            """,
            parameters_={"container_id": container_id},
        )

        return [
            ItemStore.item_from_node(record["item"])
            for record in result.records
        ]
