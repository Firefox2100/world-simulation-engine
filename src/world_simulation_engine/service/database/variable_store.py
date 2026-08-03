"""Neo4j persistence for one entity's arbitrary tracked variables (health, mana, ...)."""

import json

from neo4j import AsyncDriver

from world_simulation_engine.model import EntityVariableSet, VariableChangeAudit, VariableDefinition


class VariableStore:
    """One `EntityVariableSet` node per owner entity, holding every tracked variable."""

    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def _variable_set_from_node(node) -> EntityVariableSet:
        last_updated_at = node["last_updated_at"]
        if hasattr(last_updated_at, "to_native"):
            last_updated_at = last_updated_at.to_native()
        return EntityVariableSet(
            id=node["id"],
            source_id=node["source_id"],
            owner_type=node["owner_type"],
            owner_id=node["owner_id"],
            variables=[
                VariableDefinition.model_validate(entry)
                for entry in json.loads(node["variables_json"])
            ],
            last_updated_at=last_updated_at,
            version=node["version"],
        )

    async def get_variable_set(self, owner_id: str) -> EntityVariableSet | None:
        """Return the sole variable set for one owner entity, if any."""
        result = await self._driver.execute_query(
            """
            MATCH (owner {id: $owner_id})-[:HAS_VARIABLES]->(set:EntityVariableSet)
            RETURN set LIMIT 1
            """,
            parameters_={"owner_id": owner_id},
        )
        return self._variable_set_from_node(result.records[0]["set"]) if result.records else None

    async def list_variable_sets_by_source(self, source_id: str) -> list[EntityVariableSet]:
        """Return every variable set directly owned by one World or Simulation, for export.

        Most entities have none - variables are used sparingly - so this is typically empty.
        """
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})-[:CONTAINS]->(set:EntityVariableSet)
            RETURN set ORDER BY set.owner_id
            """,
            parameters_={"source_id": source_id},
        )
        return [self._variable_set_from_node(record["set"]) for record in result.records]

    async def owner_belongs_to_source(self, *, source_id: str, owner_id: str) -> bool:
        """Check the owner entity is reachable from the given World or Simulation before writing."""
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            MATCH (source)-[:CONTAINS*0..]->(owner {id: $owner_id})
            RETURN 1 AS found LIMIT 1
            """,
            parameters_={"source_id": source_id, "owner_id": owner_id},
        )
        return bool(result.records)

    async def create_variable_set(self, variable_set: EntityVariableSet) -> EntityVariableSet | None:
        """Create the sole variable set for one owner entity."""
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            MATCH (source)-[:CONTAINS*0..]->(owner {id: $owner_id})
            WHERE NOT EXISTS { MATCH (owner)-[:HAS_VARIABLES]->(:EntityVariableSet) }
            CREATE (set:EntityVariableSet {
                id: $id,
                source_id: $source_id,
                owner_type: $owner_type,
                owner_id: $owner_id,
                variables_json: $variables_json,
                last_updated_at: $last_updated_at,
                version: $version
            })
            MERGE (source)-[:CONTAINS]->(set)
            MERGE (owner)-[:HAS_VARIABLES]->(set)
            RETURN set
            """,
            parameters_=self._variable_set_parameters(variable_set),
        )
        return self._variable_set_from_node(result.records[0]["set"]) if result.records else None

    async def update_variable_set(self, variable_set: EntityVariableSet) -> EntityVariableSet | None:
        """Update one version with a write lock guarding overlapping simulation work."""
        result = await self._driver.execute_query(
            """
            MATCH (stored:EntityVariableSet {id: $id, owner_id: $owner_id})
            SET stored._update_lock = coalesce(stored._update_lock, 0) + 1
            WITH stored
            WHERE stored.version = $expected_version
            SET stored.variables_json = $variables_json,
                stored.last_updated_at = $last_updated_at,
                stored.version = $version
            RETURN stored AS set
            """,
            parameters_={
                **self._variable_set_parameters(variable_set),
                "expected_version": variable_set.version - 1,
            },
        )
        return self._variable_set_from_node(result.records[0]["set"]) if result.records else None

    async def create_change_audit(self, audit: VariableChangeAudit) -> VariableChangeAudit | None:
        """Link an immutable change record to its turn and evidence memories."""
        result = await self._driver.execute_query(
            """
            MATCH (set:EntityVariableSet {id: $variable_set_id})
            MATCH (source:World|Simulation {id: $source_id})-[:CONTAINS]->(turn:Turn {id: $turn_id})
            OPTIONAL MATCH (memory:MemoryAtom) WHERE memory.id IN $evidence_memory_ids
            WITH set, source, turn, collect(DISTINCT memory) AS memories
            WHERE NOT EXISTS { MATCH (:VariableChangeAudit {id: $id}) }
            CREATE (audit:VariableChangeAudit {
                id: $id,
                variable_set_id: $variable_set_id,
                source_id: $source_id,
                owner_id: $owner_id,
                turn_id: $turn_id,
                evidence_memory_ids: $evidence_memory_ids,
                changed_at: $changed_at,
                change_type: $change_type,
                previous_version: $previous_version,
                new_version: $new_version,
                previous_state_json: $previous_state_json,
                new_state_json: $new_state_json
            })
            MERGE (turn)-[:TRIGGERED]->(audit)
            MERGE (audit)-[:CHANGED]->(set)
            FOREACH (memory IN memories | MERGE (memory)-[:EVIDENCE_FOR]->(audit))
            RETURN audit
            """,
            parameters_={
                **audit.model_dump(exclude={"previous_state", "new_state"}),
                "previous_state_json": (
                    json.dumps(audit.previous_state, sort_keys=True)
                    if audit.previous_state is not None else None
                ),
                "new_state_json": json.dumps(audit.new_state, sort_keys=True),
            },
        )
        return audit if result.records else None

    async def list_change_audits(self, variable_set_id: str) -> list[VariableChangeAudit]:
        """Return provenance ordered by resulting variable-set version."""
        result = await self._driver.execute_query(
            """
            MATCH (audit:VariableChangeAudit {variable_set_id: $variable_set_id})
            RETURN audit ORDER BY audit.new_version, audit.id
            """,
            parameters_={"variable_set_id": variable_set_id},
        )
        audits = []
        for record in result.records:
            node = record["audit"]
            changed_at = node["changed_at"]
            if hasattr(changed_at, "to_native"):
                changed_at = changed_at.to_native()
            audits.append(VariableChangeAudit(
                id=node["id"],
                variable_set_id=node["variable_set_id"],
                source_id=node["source_id"],
                owner_id=node["owner_id"],
                turn_id=node["turn_id"],
                evidence_memory_ids=list(node["evidence_memory_ids"]),
                changed_at=changed_at,
                change_type=node["change_type"],
                previous_version=node.get("previous_version"),
                new_version=node["new_version"],
                previous_state=(
                    json.loads(node["previous_state_json"])
                    if node.get("previous_state_json") else None
                ),
                new_state=json.loads(node["new_state_json"]),
            ))
        return audits

    @staticmethod
    def _variable_set_parameters(variable_set: EntityVariableSet) -> dict:
        return {
            "id": variable_set.id,
            "source_id": variable_set.source_id,
            "owner_type": variable_set.owner_type,
            "owner_id": variable_set.owner_id,
            "variables_json": json.dumps([entry.model_dump() for entry in variable_set.variables]),
            "last_updated_at": variable_set.last_updated_at,
            "version": variable_set.version,
        }
