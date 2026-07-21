"""Neo4j persistence for first-class entity relationship nodes."""

import json
from datetime import datetime
from uuid import uuid4

from neo4j import AsyncDriver

from world_simulation_engine.model import (
    EntityRelationship,
    RelationshipChangeAudit,
    RelationshipEntityRef,
)


class EntityRelationshipStore:
    """Persist, query, version, and copy entity relationships."""
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def relationship_from_record(record) -> EntityRelationship:
        """Hydrate a relationship and its endpoints from a query record."""
        node = record["relationship"]
        created_at = node["created_at"]
        last_changed_at = node["last_changed_at"]
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if hasattr(last_changed_at, "to_native"):
            last_changed_at = last_changed_at.to_native()
        return EntityRelationship(
            id=node["id"],
            scope_type=node["scope_type"],
            scope_id=node["scope_id"],
            source=RelationshipEntityRef(
                type=node["source_type"],
                id=record["source"].get("id"),
                name=record["source"].get("name"),
            ),
            target=RelationshipEntityRef(
                type=node["target_type"],
                id=record["target"].get("id"),
                name=record["target"].get("name"),
            ),
            label=node["label"],
            public_description=node.get("public_description"),
            private_description=node.get("private_description"),
            visibility=node["visibility"],
            perspective_character_id=node.get("perspective_character_id"),
            confidence=node["confidence"],
            details=json.loads(node["details_json"]),
            evidence_memory_ids=list(record.get("evidence_memory_ids") or []),
            created_at=created_at,
            last_changed_at=last_changed_at,
            version=node["version"],
            active=node["active"],
        )

    @staticmethod
    def _parameters(relationship: EntityRelationship) -> dict:
        return {
            "id": relationship.id,
            "scope_type": relationship.scope_type,
            "scope_id": relationship.scope_id,
            "source_id": relationship.source.id,
            "source_type": relationship.source.type,
            "target_id": relationship.target.id,
            "target_type": relationship.target.type,
            "label": relationship.label,
            "public_description": relationship.public_description,
            "private_description": relationship.private_description,
            "visibility": relationship.visibility,
            "perspective_character_id": relationship.perspective_character_id,
            "confidence": relationship.confidence,
            "details_json": relationship.details.model_dump_json(),
            "evidence_memory_ids": list(dict.fromkeys(relationship.evidence_memory_ids)),
            "created_at": relationship.created_at,
            "last_changed_at": relationship.last_changed_at,
            "version": relationship.version,
            "active": relationship.active,
        }

    async def create_relationship(
            self,
            relationship: EntityRelationship,
    ) -> EntityRelationship | None:
        """Create a relationship only when scope, endpoints, and evidence exist."""
        result = await self._driver.execute_query(
            """
            MATCH (scope:World|Simulation {id: $scope_id})
            WHERE ($scope_type = 'world' AND scope:World)
                OR ($scope_type = 'simulation' AND scope:Simulation)
            MATCH (source {id: $source_id}), (target {id: $target_id})
            WHERE $source_type IN labels(source) OR toLower(replace($source_type, '_', '')) IN
                    [label IN labels(source) | toLower(label)]
            WITH scope, source, target
            WHERE ($target_type IN labels(target) OR toLower(replace($target_type, '_', '')) IN
                    [label IN labels(target) | toLower(label)])
                AND (EXISTS { MATCH (scope)-[:CONTAINS*0..]->(source) }
                    OR EXISTS {
                        MATCH (scope:Simulation)-[:BASED_ON]->(:World)
                            -[:CONTAINS]->(source:Item)
                    })
                AND (EXISTS { MATCH (scope)-[:CONTAINS*0..]->(target) }
                    OR EXISTS {
                        MATCH (scope:Simulation)-[:BASED_ON]->(:World)
                            -[:CONTAINS]->(target:Item)
                    })
            OPTIONAL MATCH (perspective:Character {id: $perspective_character_id})
            WITH scope, source, target, perspective
            WHERE $perspective_character_id IS NULL
                OR (perspective IS NOT NULL AND EXISTS {
                    MATCH (scope)-[:CONTAINS*0..]->(perspective)
                })
            OPTIONAL MATCH (evidence:MemoryAtom)
            WHERE evidence.id IN $evidence_memory_ids
                AND EXISTS {
                    MATCH (scope)-[:CONTAINS|PART_OF|SUPPORTS*1..]->(evidence)
                }
            WITH scope, source, target, collect(DISTINCT evidence) AS evidence_memories
            WHERE size(evidence_memories) = size($evidence_memory_ids)
                AND NOT EXISTS { MATCH (:EntityRelationship {id: $id}) }
            CREATE (relationship:EntityRelationship {
                id: $id,
                scope_type: $scope_type,
                scope_id: $scope_id,
                source_type: $source_type,
                target_type: $target_type,
                label: $label,
                public_description: $public_description,
                private_description: $private_description,
                visibility: $visibility,
                perspective_character_id: $perspective_character_id,
                confidence: $confidence,
                details_json: $details_json,
                created_at: $created_at,
                last_changed_at: $last_changed_at,
                version: $version,
                active: $active
            })
            MERGE (scope)-[:CONTAINS]->(relationship)
            MERGE (source)-[:RELATIONSHIP_SOURCE]->(relationship)
            MERGE (relationship)-[:RELATIONSHIP_TARGET]->(target)
            FOREACH (memory IN evidence_memories |
                MERGE (memory)-[:EVIDENCE_FOR]->(relationship)
            )
            RETURN relationship, source, target,
                [memory IN evidence_memories | memory.id] AS evidence_memory_ids
            """,
            parameters_=self._parameters(relationship),
        )
        record = result.records[0] if result.records else None
        return self.relationship_from_record(record) if record else None

    async def get_relationship(self, relationship_id: str) -> EntityRelationship | None:
        """Return one relationship by stable ID."""
        result = await self._driver.execute_query(
            """
            MATCH (source)-[:RELATIONSHIP_SOURCE]->(relationship:EntityRelationship {id: $id})
                -[:RELATIONSHIP_TARGET]->(target)
            OPTIONAL MATCH (memory:MemoryAtom)-[:EVIDENCE_FOR]->(relationship)
            RETURN relationship, source, target, collect(DISTINCT memory.id) AS evidence_memory_ids
            LIMIT 1
            """,
            parameters_={"id": relationship_id},
        )
        record = result.records[0] if result.records else None
        return self.relationship_from_record(record) if record else None

    async def list_relationships(
            self,
            *,
            scope_id: str,
            perspective_character_id: str | None = None,
            entity_ids: list[str] | None = None,
            active_only: bool = True,
            limit: int = 50,
    ) -> list[EntityRelationship]:
        """Recall bounded relationships while filtering private perspectives in Cypher."""
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $scope_id})-[:CONTAINS]->(relationship:EntityRelationship)
            MATCH (source)-[:RELATIONSHIP_SOURCE]->(relationship)-[:RELATIONSHIP_TARGET]->(target)
            WHERE (NOT $active_only OR relationship.active)
                AND ($perspective_character_id IS NULL
                    OR relationship.perspective_character_id IS NULL
                    OR relationship.perspective_character_id = $perspective_character_id)
                AND ($entity_ids IS NULL OR source.id IN $entity_ids OR target.id IN $entity_ids)
            OPTIONAL MATCH (memory:MemoryAtom)-[:EVIDENCE_FOR]->(relationship)
            RETURN relationship, source, target, collect(DISTINCT memory.id) AS evidence_memory_ids
            ORDER BY relationship.last_changed_at DESC, relationship.id
            LIMIT $limit
            """,
            parameters_={
                "scope_id": scope_id,
                "perspective_character_id": perspective_character_id,
                "entity_ids": (
                    list(dict.fromkeys(entity_ids))
                    if entity_ids is not None else None
                ),
                "active_only": active_only,
                "limit": limit,
            },
        )
        return [self.relationship_from_record(record) for record in result.records]

    async def resolve_entity_refs(
            self,
            *,
            scope_id: str,
            entity_ids: list[str],
    ) -> list[RelationshipEntityRef]:
        """Resolve only entities belonging to the requested world or simulation."""
        if not entity_ids:
            return []
        result = await self._driver.execute_query(
            """
            MATCH (scope:World|Simulation {id: $scope_id})
            MATCH (entity)
            WHERE entity.id IN $entity_ids
                AND (
                    EXISTS { MATCH (scope)-[:CONTAINS*0..]->(entity) }
                    OR EXISTS {
                        MATCH (scope:Simulation)-[:BASED_ON]->(:World)
                            -[:CONTAINS]->(entity:Item)
                    }
                )
                AND any(label IN labels(entity) WHERE label IN $allowed_labels)
            RETURN entity, labels(entity) AS entity_labels
            ORDER BY entity.id
            """,
            parameters_={
                "scope_id": scope_id,
                "entity_ids": list(dict.fromkeys(entity_ids)),
                "allowed_labels": list(self._ENTITY_TYPES_BY_LABEL),
            },
        )
        return [
            RelationshipEntityRef(
                type=next(
                    self._ENTITY_TYPES_BY_LABEL[label]
                    for label in record["entity_labels"]
                    if label in self._ENTITY_TYPES_BY_LABEL
                ),
                id=record["entity"]["id"],
                name=record["entity"].get("name"),
            )
            for record in result.records
        ]

    async def update_relationship(
            self,
            relationship: EntityRelationship,
    ) -> EntityRelationship | None:
        """Apply a monotonic version update without dropping prior memory evidence."""
        existing = await self.get_relationship(relationship.id)
        if not existing:
            return None
        if not self._is_valid_update(existing, relationship):
            return None
        parameters = self._parameters(relationship)
        parameters["expected_version"] = existing.version
        result = await self._driver.execute_query(
            """
            MATCH (scope:World|Simulation {id: $scope_id})-[:CONTAINS]->
                (relationship:EntityRelationship {id: $id})
            MATCH (source)-[:RELATIONSHIP_SOURCE]->(relationship)
                -[:RELATIONSHIP_TARGET]->(target)
            WHERE source.id = $source_id AND target.id = $target_id
            SET relationship._update_lock = coalesce(relationship._update_lock, 0) + 1
            WITH scope, relationship, source, target
            WHERE relationship.version = $expected_version
            OPTIONAL MATCH (evidence:MemoryAtom)
            WHERE evidence.id IN $evidence_memory_ids
                AND EXISTS {
                    MATCH (scope)-[:CONTAINS|PART_OF|SUPPORTS*1..]->(evidence)
                }
            WITH relationship, source, target, collect(DISTINCT evidence) AS evidence_memories
            WHERE size(evidence_memories) = size($evidence_memory_ids)
            OPTIONAL MATCH (:MemoryAtom)-[old_evidence:EVIDENCE_FOR]->(relationship)
            DELETE old_evidence
            WITH relationship, source, target, evidence_memories
            SET relationship.label = $label,
                relationship.public_description = $public_description,
                relationship.private_description = $private_description,
                relationship.visibility = $visibility,
                relationship.perspective_character_id = $perspective_character_id,
                relationship.confidence = $confidence,
                relationship.details_json = $details_json,
                relationship.last_changed_at = $last_changed_at,
                relationship.version = $version,
                relationship.active = $active
            FOREACH (memory IN evidence_memories |
                MERGE (memory)-[:EVIDENCE_FOR]->(relationship)
            )
            RETURN relationship, source, target,
                [memory IN evidence_memories | memory.id] AS evidence_memory_ids
            """,
            parameters_=parameters,
        )
        record = result.records[0] if result.records else None
        return self.relationship_from_record(record) if record else None

    @staticmethod
    def _is_valid_update(
            existing: EntityRelationship,
            candidate: EntityRelationship,
    ) -> bool:
        immutable_values = (
            existing.scope_type == candidate.scope_type,
            existing.scope_id == candidate.scope_id,
            existing.source.id == candidate.source.id,
            existing.source.type == candidate.source.type,
            existing.target.id == candidate.target.id,
            existing.target.type == candidate.target.type,
            existing.created_at == candidate.created_at,
        )
        return (
            all(immutable_values)
            and candidate.version == existing.version + 1
            and candidate.last_changed_at >= existing.last_changed_at
            and set(existing.evidence_memory_ids).issubset(candidate.evidence_memory_ids)
        )

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship explicitly, primarily for authoring workflows."""
        result = await self._driver.execute_query(
            """
            MATCH (relationship:EntityRelationship {id: $id})
            WITH relationship, 1 AS deleted
            DETACH DELETE relationship
            RETURN deleted
            """,
            parameters_={"id": relationship_id},
        )
        return bool(result.records)

    async def create_change_audit(
            self,
            audit: RelationshipChangeAudit,
    ) -> RelationshipChangeAudit | None:
        """Persist immutable turn and memory provenance for an applied version."""
        result = await self._driver.execute_query(
            """
            MATCH (scope:Simulation {id: $scope_id})-[:CONTAINS]->
                (relationship:EntityRelationship {id: $relationship_id})
            MATCH (scope)-[:CONTAINS]->(turn:Turn {id: $turn_id})
            MATCH (scope)-[:CONTAINS]->(perspective:Character {id: $perspective_character_id})
            MATCH (memory:MemoryAtom)
            WHERE memory.id IN $evidence_memory_ids
                AND EXISTS { MATCH (perspective)-[:REMEMBERS]->(memory) }
                AND EXISTS {
                    MATCH (scope)-[:CONTAINS|PART_OF|SUPPORTS*1..]->(memory)
                }
            WITH scope, relationship, turn, perspective,
                collect(DISTINCT memory) AS evidence_memories
            WHERE size(evidence_memories) = size($evidence_memory_ids)
                AND NOT EXISTS { MATCH (:RelationshipChangeAudit {id: $id}) }
            CREATE (audit:RelationshipChangeAudit {
                id: $id,
                relationship_id: $relationship_id,
                scope_id: $scope_id,
                perspective_character_id: $perspective_character_id,
                turn_id: $turn_id,
                evidence_memory_ids: $evidence_memory_ids,
                changed_at: $changed_at,
                change_type: $change_type,
                previous_version: $previous_version,
                new_version: $new_version,
                previous_state_json: $previous_state_json,
                new_state_json: $new_state_json
            })
            MERGE (scope)-[:CONTAINS]->(audit)
            MERGE (turn)-[:TRIGGERED]->(audit)
            MERGE (audit)-[:CHANGED]->(relationship)
            FOREACH (memory IN evidence_memories |
                MERGE (memory)-[:EVIDENCE_FOR]->(audit)
            )
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

    async def list_change_audits(self, relationship_id: str) -> list[RelationshipChangeAudit]:
        """Return immutable change history in version order."""
        result = await self._driver.execute_query(
            """
            MATCH (audit:RelationshipChangeAudit {relationship_id: $relationship_id})
            RETURN audit
            ORDER BY audit.new_version, audit.id
            """,
            parameters_={"relationship_id": relationship_id},
        )
        audits = []
        for record in result.records:
            node = record["audit"]
            changed_at = node["changed_at"]
            if hasattr(changed_at, "to_native"):
                changed_at = changed_at.to_native()
            audits.append(RelationshipChangeAudit(
                id=node["id"],
                relationship_id=node["relationship_id"],
                scope_id=node["scope_id"],
                perspective_character_id=node["perspective_character_id"],
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

    async def copy_relationships(
            self,
            *,
            source_id: str,
            target_simulation_id: str,
            entity_pairs: list[dict],
            copied_at: datetime,
    ) -> list[EntityRelationship]:
        """Copy template records after remapping copied entity IDs."""
        source_relationships = await self.list_relationships(
            scope_id=source_id,
            active_only=False,
            limit=1000,
        )
        id_map = {
            pair["source_id"]: pair["copy_id"]
            for pair in entity_pairs
        }
        copied = []
        for relationship in source_relationships:
            source_copy_id = id_map.get(relationship.source.id, relationship.source.id)
            target_copy_id = id_map.get(relationship.target.id, relationship.target.id)
            perspective_copy_id = id_map.get(
                relationship.perspective_character_id,
                relationship.perspective_character_id,
            )
            candidate = relationship.model_copy(
                update={
                    "id": str(uuid4()),
                    "scope_type": "simulation",
                    "scope_id": target_simulation_id,
                    "source": relationship.source.model_copy(update={"id": source_copy_id}),
                    "target": relationship.target.model_copy(update={"id": target_copy_id}),
                    "perspective_character_id": perspective_copy_id,
                    "evidence_memory_ids": [],
                    "created_at": copied_at,
                    "last_changed_at": copied_at,
                    "version": 1,
                },
            )
            created = await self.create_relationship(candidate)
            if created:
                copied.append(created)
        return copied

    _ENTITY_TYPES_BY_LABEL = {
        "Character": "character",
        "BackgroundCharacter": "background_character",
        "Item": "item",
        "ItemStack": "item_stack",
        "Equipment": "equipment",
        "Container": "container",
        "Location": "location",
        "Landmark": "landmark",
        "Body": "body",
    }
