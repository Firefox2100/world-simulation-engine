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
                               ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (loc:Location {id: $location_id})
            WITH source, loc
            WHERE $location_id IS NULL OR loc IS NOT NULL
            CREATE (c:Container {
                id: $id,
                name: $name,
                description: $description,
                state: $state
            })
            MERGE (source)-[:CONTAINS]->(c)
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["c"])

    async def list_containers(self,
                              world_id: str | None = None,
                              simulation_id: str | None = None,
                              location_id: str | None = None,
                              owner_id: str | None = None,
                              holder_id: str | None = None,
                              ) -> list[Container]:
        if world_id is not None and simulation_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(:Simulation {id: $simulation_id})-[:CONTAINS]->(container:Container)
            """
        elif world_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})-[:CONTAINS]->(container:Container)
            """
        elif simulation_id is not None:
            source_match = """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(container:Container)
            """
        else:
            source_match = """
            MATCH (container:Container)
            """

        result = await self._driver.execute_query(
            source_match + """
            WHERE ($location_id IS NULL OR (
                    EXISTS {
                        MATCH (container)-[:PRESENT_IN]->(:Location {id: $location_id})
                    }
                    AND NOT EXISTS {
                        MATCH ()-[:HOLDS]->(container)
                    }
                ))
                AND ($owner_id IS NULL OR EXISTS {
                    MATCH (owner {id: $owner_id})-[:OWNS]->(container)
                })
                AND ($holder_id IS NULL OR EXISTS {
                    MATCH (holder {id: $holder_id})-[:HOLDS]->(container)
                })
            RETURN DISTINCT container
            ORDER BY container.name
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
            self.container_from_node(record["container"])
            for record in result.records
        ]

    async def get_container(self, container_id: str) -> Container | None:
        result = await self._driver.execute_query(
            "MATCH (c:Container {id: $id}) RETURN c LIMIT 1",
            parameters_={"id": container_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["c"])

    async def update_container(self,
                               container_id: str,
                               properties: dict,
                               ) -> Container | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            SET container += $properties
            RETURN container LIMIT 1
            """,
            parameters_={
                "container_id": container_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["container"])

    async def delete_container(self, container_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH path = (container)-[:HOLDS*0..]->(node)
            WHERE node:Container OR node:ItemStack OR node:Equipment
            WITH collect(DISTINCT node) AS nodes, 1 AS deleted
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted
            """,
            parameters_={"container_id": container_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def get_containers_by_location(self,
                                         location_id: str,
                                         ) -> list[tuple[Container, Location, str | None, str | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (location:Location {id: $location_id}) <-[r:PRESENT_IN]- (container:Container)
            OPTIONAL MATCH (holder)-[:HOLDS]->(container)
            WITH container, location, r, holder
            WHERE holder IS NULL
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
                                          ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(container)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(container)
            MATCH (location:Location {id: $location_id})
            DELETE hold, present
            MERGE (container)-[new_present:PRESENT_IN]->(location)
            SET new_present.position = $position
            RETURN container
            """,
            parameters_={
                "container_id": container_id,
                "location_id": location_id,
                "position": position,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["container"])

    async def assign_container(self,
                               container_id: str,
                               holder_id: str | None = None,
                               owner_id: str | None = None,
                               ) -> Container | None:
        container = await self.get_container(container_id)
        if container is None:
            return None

        if holder_id:
            result = await self._driver.execute_query(
                """
                MATCH (container:Container {id: $container_id})
                OPTIONAL MATCH (holder)-[hold:HOLDS]->(container)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(container)
                MATCH (new_holder {id: $holder_id})
                DELETE hold, present
                MERGE (new_holder)-[:HOLDS]->(container)
                RETURN container
                """,
                parameters_={
                    "container_id": container_id,
                    "holder_id": holder_id,
                },
            )
            record = result.records[0] if result.records else None
            if not record:
                return None
            container = self.container_from_node(record["container"])

        if owner_id:
            result = await self._driver.execute_query(
                """
                MATCH (container:Container {id: $container_id})
                OPTIONAL MATCH (previous_owner)-[owns:OWNS]->(container)
                MATCH (owner {id: $owner_id})
                DELETE owns
                MERGE (owner)-[:OWNS]->(container)
                RETURN container
                """,
                parameters_={
                    "container_id": container_id,
                    "owner_id": owner_id,
                },
            )
            record = result.records[0] if result.records else None
            if not record:
                return None
            container = self.container_from_node(record["container"])

        return container

    async def remove_location(self, container_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (container)-[present:PRESENT_IN]->(:Location)
            DELETE present
            RETURN count(container) AS container_count
            """,
            parameters_={"container_id": container_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def remove_owner(self, container_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (owner)-[owns:OWNS]->(container)
            DELETE owns
            RETURN count(container) AS container_count
            """,
            parameters_={"container_id": container_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def remove_holder(self, container_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[holds:HOLDS]->(container)
            DELETE holds
            RETURN count(container) AS container_count
            """,
            parameters_={"container_id": container_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def put_stack_in_container(self,
                                     stack_id: str,
                                     container_id: str,
                                     ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (stack:ItemStack {id: $stack_id})
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS]->(stack)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(stack)
            DELETE hold, present
            MERGE (container)-[:HOLDS]->(stack)
            RETURN container
            """,
            parameters_={
                "stack_id": stack_id,
                "container_id": container_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["container"])

    async def put_equipment_in_container(self,
                                         equipment_id: str,
                                         container_id: str,
                                         ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (equipment:Equipment {id: $equipment_id})
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (holder)-[hold:HOLDS|EQUIPS]->(equipment)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(equipment)
            DELETE hold, present
            MERGE (container)-[:HOLDS]->(equipment)
            RETURN container
            """,
            parameters_={
                "equipment_id": equipment_id,
                "container_id": container_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["container"])

    async def put_container_in_container(self,
                                        held_container_id: str,
                                        holder_container_id: str,
                                        ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (held:Container {id: $held_container_id})
            MATCH (holder:Container {id: $holder_container_id})
            WHERE held <> holder
            OPTIONAL MATCH (previous_holder)-[hold:HOLDS]->(held)
            OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(held)
            DELETE hold, present
            MERGE (holder)-[:HOLDS]->(held)
            RETURN holder
            """,
            parameters_={
                "held_container_id": held_container_id,
                "holder_container_id": holder_container_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["holder"])

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
                                 ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (item:Item {id: $item_id})
            MATCH (container:Container {id: $container_id})
            MERGE (item)-[:UNLOCKS]->(container)
            RETURN container
            """,
            parameters_={
                "item_id": item_id,
                "container_id": container_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.container_from_node(record["container"])

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

    async def replace_held_stacks(self,
                                  container_id: str,
                                  stack_ids: list[str],
                                  ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (container)-[existing:HOLDS]->(:ItemStack)
            DELETE existing
            WITH container
            CALL {
                WITH container
                UNWIND $stack_ids AS stack_id
                MATCH (stack:ItemStack {id: stack_id})
                OPTIONAL MATCH (holder)-[hold:HOLDS]->(stack)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(stack)
                DELETE hold, present
                MERGE (container)-[:HOLDS]->(stack)
                RETURN count(*) AS linked_count
            }
            RETURN container
            """,
            parameters_={
                "container_id": container_id,
                "stack_ids": stack_ids,
            },
        )

        record = result.records[0] if result.records else None
        return self.container_from_node(record["container"]) if record else None

    async def replace_held_equipment(self,
                                     container_id: str,
                                     equipment_ids: list[str],
                                     ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (container)-[existing:HOLDS]->(:Equipment)
            DELETE existing
            WITH container
            CALL {
                WITH container
                UNWIND $equipment_ids AS equipment_id
                MATCH (equipment:Equipment {id: equipment_id})
                OPTIONAL MATCH (holder)-[hold:HOLDS|EQUIPS]->(equipment)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(equipment)
                DELETE hold, present
                MERGE (container)-[:HOLDS]->(equipment)
                RETURN count(*) AS linked_count
            }
            RETURN container
            """,
            parameters_={
                "container_id": container_id,
                "equipment_ids": equipment_ids,
            },
        )

        record = result.records[0] if result.records else None
        return self.container_from_node(record["container"]) if record else None

    async def remove_held_equipment(self,
                                    container_id: str,
                                    equipment_ids: list[str],
                                    ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            CALL {
                WITH container
                UNWIND $equipment_ids AS equipment_id
                OPTIONAL MATCH (container)-[hold:HOLDS]->(:Equipment {id: equipment_id})
                DELETE hold
                RETURN count(*) AS removed_count
            }
            RETURN count(container) AS container_count
            """,
            parameters_={
                "container_id": container_id,
                "equipment_ids": equipment_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def remove_held_stacks(self,
                                 container_id: str,
                                 stack_ids: list[str],
                                 ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            CALL {
                WITH container
                UNWIND $stack_ids AS stack_id
                OPTIONAL MATCH (container)-[hold:HOLDS]->(:ItemStack {id: stack_id})
                DELETE hold
                RETURN count(*) AS removed_count
            }
            RETURN count(container) AS container_count
            """,
            parameters_={
                "container_id": container_id,
                "stack_ids": stack_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def replace_held_containers(self,
                                      container_id: str,
                                      held_container_ids: list[str],
                                      ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (container)-[existing:HOLDS]->(:Container)
            DELETE existing
            WITH container
            CALL {
                WITH container
                UNWIND $held_container_ids AS held_container_id
                MATCH (held:Container {id: held_container_id})
                WHERE held <> container
                OPTIONAL MATCH (holder)-[hold:HOLDS]->(held)
                OPTIONAL MATCH (:Location)<-[present:PRESENT_IN]-(held)
                DELETE hold, present
                MERGE (container)-[:HOLDS]->(held)
                RETURN count(*) AS linked_count
            }
            RETURN container
            """,
            parameters_={
                "container_id": container_id,
                "held_container_ids": held_container_ids,
            },
        )

        record = result.records[0] if result.records else None
        return self.container_from_node(record["container"]) if record else None

    async def remove_held_containers(self,
                                     container_id: str,
                                     held_container_ids: list[str],
                                     ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            CALL {
                WITH container
                UNWIND $held_container_ids AS held_container_id
                OPTIONAL MATCH (container)-[hold:HOLDS]->(:Container {id: held_container_id})
                DELETE hold
                RETURN count(*) AS removed_count
            }
            RETURN count(container) AS container_count
            """,
            parameters_={
                "container_id": container_id,
                "held_container_ids": held_container_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

    async def replace_unlocking_items(self,
                                      container_id: str,
                                      item_ids: list[str],
                                      ) -> Container | None:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            OPTIONAL MATCH (:Item)-[existing:UNLOCKS]->(container)
            DELETE existing
            WITH container
            CALL {
                WITH container
                UNWIND $item_ids AS item_id
                MATCH (item:Item {id: item_id})
                MERGE (item)-[:UNLOCKS]->(container)
                RETURN count(*) AS linked_count
            }
            RETURN container
            """,
            parameters_={
                "container_id": container_id,
                "item_ids": item_ids,
            },
        )

        record = result.records[0] if result.records else None
        return self.container_from_node(record["container"]) if record else None

    async def remove_unlocking_items(self,
                                     container_id: str,
                                     item_ids: list[str],
                                     ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (container:Container {id: $container_id})
            CALL {
                WITH container
                UNWIND $item_ids AS item_id
                OPTIONAL MATCH (:Item {id: item_id})-[unlocks:UNLOCKS]->(container)
                DELETE unlocks
                RETURN count(*) AS removed_count
            }
            RETURN count(container) AS container_count
            """,
            parameters_={
                "container_id": container_id,
                "item_ids": item_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["container_count"])

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

    async def copy_containers(self,
                              source_id: str,
                              target_id: str,
                              location_pairs: list[dict] | None = None,
                              entity_pairs: list[dict] | None = None,
                              equipment_pairs: list[dict] | None = None,
                              ) -> tuple[list[Container], list[dict]]:
        location_pairs = location_pairs or []
        entity_pairs = entity_pairs or []
        equipment_pairs = equipment_pairs or []
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(source_container:Container)
            MATCH (target:World|Simulation {id: $target_id})
            CREATE (container:Container {
                id: randomUUID(),
                name: source_container.name,
                description: source_container.description,
                state: source_container.state
            })
            MERGE (target)-[:CONTAINS]->(container)
            RETURN source_container.id AS source_id, container.id AS copy_id, container
            ORDER BY container.name
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )
        container_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if container_pairs and location_pairs:
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS container_pair
                MATCH (source_container:Container {id: container_pair.source_id})-[source_present:PRESENT_IN]->(source_location:Location)
                WITH container_pair, source_present, [
                    location_pair IN $location_pairs
                    WHERE location_pair.source_id = source_location.id
                ][0] AS location_pair
                WHERE location_pair IS NOT NULL
                MATCH (copy_container:Container {id: container_pair.copy_id})
                MATCH (copy_location:Location {id: location_pair.copy_id})
                MERGE (copy_container)-[present:PRESENT_IN]->(copy_location)
                SET present.position = source_present.position
                """,
                parameters_={
                    "container_pairs": container_pairs,
                    "location_pairs": location_pairs,
                },
            )
        if container_pairs and entity_pairs:
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS container_pair
                MATCH (source_owner)-[:OWNS]->(:Container {id: container_pair.source_id})
                WITH container_pair, [
                    entity_pair IN $entity_pairs
                    WHERE entity_pair.source_id = source_owner.id
                ][0] AS owner_pair
                WHERE owner_pair IS NOT NULL
                MATCH (copy_owner {id: owner_pair.copy_id})
                MATCH (copy_container:Container {id: container_pair.copy_id})
                MERGE (copy_owner)-[:OWNS]->(copy_container)
                """,
                parameters_={
                    "container_pairs": container_pairs,
                    "entity_pairs": entity_pairs,
                },
            )
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS container_pair
                MATCH (source_holder)-[:HOLDS]->(:Container {id: container_pair.source_id})
                WITH container_pair, [
                    entity_pair IN $entity_pairs
                    WHERE entity_pair.source_id = source_holder.id
                ][0] AS holder_pair
                WHERE holder_pair IS NOT NULL
                MATCH (copy_holder {id: holder_pair.copy_id})
                MATCH (copy_container:Container {id: container_pair.copy_id})
                MERGE (copy_holder)-[:HOLDS]->(copy_container)
                """,
                parameters_={
                    "container_pairs": container_pairs,
                    "entity_pairs": entity_pairs,
                },
            )
        if container_pairs:
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS holder_pair
                UNWIND $container_pairs AS held_pair
                MATCH (:Container {id: holder_pair.source_id})-[:HOLDS]->(:Container {id: held_pair.source_id})
                MATCH (copy_holder:Container {id: holder_pair.copy_id})
                MATCH (copy_held:Container {id: held_pair.copy_id})
                MERGE (copy_holder)-[:HOLDS]->(copy_held)
                """,
                parameters_={"container_pairs": container_pairs},
            )
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS container_pair
                MATCH (item:Item)-[:UNLOCKS]->(:Container {id: container_pair.source_id})
                MATCH (copy_container:Container {id: container_pair.copy_id})
                MERGE (item)-[:UNLOCKS]->(copy_container)
                """,
                parameters_={"container_pairs": container_pairs},
            )
        if container_pairs and equipment_pairs:
            await self._driver.execute_query(
                """
                UNWIND $container_pairs AS container_pair
                MATCH (:Container {id: container_pair.source_id})-[:HOLDS]->(source_equipment:Equipment)
                WITH container_pair, [
                    equipment_pair IN $equipment_pairs
                    WHERE equipment_pair.source_id = source_equipment.id
                ][0] AS equipment_pair
                WHERE equipment_pair IS NOT NULL
                MATCH (copy_container:Container {id: container_pair.copy_id})
                MATCH (copy_equipment:Equipment {id: equipment_pair.copy_id})
                MERGE (copy_container)-[:HOLDS]->(copy_equipment)
                """,
                parameters_={
                    "container_pairs": container_pairs,
                    "equipment_pairs": equipment_pairs,
                },
            )

        return (
            [
                self.container_from_node(record["container"])
                for record in result.records
            ],
            container_pairs,
        )
