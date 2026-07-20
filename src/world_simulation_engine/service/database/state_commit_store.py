import json
from datetime import datetime
from uuid import uuid4

from neo4j import AsyncDriver

from world_simulation_engine.model import CurrentActivity, StateCommitProposal, StateCommitEntityRef, StateCommitFieldChange


class StateCommitStore:
    _ENTITY_LABELS = {
        "character": "Character",
        "background_character": "BackgroundCharacter",
        "item": "Item",
        "item_stack": "ItemStack",
        "equipment": "Equipment",
        "container": "Container",
        "location": "Location",
        "landmark": "Landmark",
        "body": "Body",
        "unknown": "PhysicalEntity",
    }
    _RELATIONSHIP_TYPES = {
        "located_at": "PRESENT_IN",
        "inside": "HOLDS",
        "held_by": "HOLDS",
        "owned_by": "OWNS",
        "equipped_by": "EQUIPS",
        "wearing": "EQUIPS",
        "attached_to": "ATTACHED_TO",
        "near": "NEAR",
        "part_of": "PART_OF",
        "derived_from": "DERIVED_FROM",
        "interacting_with": "INTERACTING_WITH",
        "emotion_toward": "EMOTION_TOWARD",
        "state_toward": "STATE_TOWARD",
        "other": "RELATED_TO",
    }

    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @classmethod
    def _label_for_type(cls, entity_type: str) -> str:
        return cls._ENTITY_LABELS.get(entity_type, cls._ENTITY_LABELS["unknown"])

    @classmethod
    def _relationship_for_type(cls, relationship_type: str) -> str:
        return cls._RELATIONSHIP_TYPES.get(relationship_type, cls._RELATIONSHIP_TYPES["other"])

    @staticmethod
    def _safe_property_value(value):
        if isinstance(value, datetime):
            return value

        if isinstance(value, dict | list):
            return json.dumps(value)

        return value

    @classmethod
    def _safe_properties(cls, properties: dict) -> dict:
        return {
            key: cls._safe_property_value(value)
            for key, value in properties.items()
            if value is not None
        }

    @staticmethod
    def _split_current_activity_changes(
            field_changes: list[StateCommitFieldChange],
    ) -> tuple[list[StateCommitFieldChange], list[StateCommitFieldChange]]:
        current_activity_changes = []
        other_changes = []

        for change in field_changes:
            if change.field_path.startswith("current_activity."):
                current_activity_changes.append(change)
            else:
                other_changes.append(change)

        return other_changes, current_activity_changes

    @staticmethod
    def _node_id(ref: StateCommitEntityRef | None) -> str | None:
        return ref.id if ref else None

    @staticmethod
    def _relationship_endpoints(
            relationship_type: str,
            subject: StateCommitEntityRef,
            object: StateCommitEntityRef | None,
    ) -> tuple[StateCommitEntityRef, StateCommitEntityRef | None]:
        if relationship_type in {"held_by", "owned_by", "equipped_by"}:
            return object, subject

        if relationship_type == "inside":
            return object, subject

        return subject, object

    async def apply_state_commit_proposal(self,
                                          *,
                                          proposal: StateCommitProposal,
                                          source_id: str,
                                          turn_id: str,
                                          ):
        for operation in proposal.operations:
            if operation.type == "create":
                await self.create_entity(
                    entity_type=operation.entity_type,
                    properties=operation.properties,
                    source_id=source_id,
                    turn_id=turn_id,
                    proposed_id=operation.proposed_id,
                )
                for relationship in operation.initial_relationships:
                    await self.change_relationship(
                        relationship_type=relationship.relationship_type,
                        subject=relationship.subject,
                        object=relationship.object,
                        old_object=relationship.old_object,
                        properties=relationship.properties,
                        ended=relationship.ended,
                        turn_id=turn_id,
                    )
            elif operation.type == "state_change":
                await self.change_entity_state(
                    entity=operation.entity,
                    field_changes=operation.field_changes,
                    turn_id=turn_id,
                )
            elif operation.type == "promote":
                target_ref = await self.create_entity(
                    entity_type=operation.target_entity_type,
                    properties=operation.target_properties,
                    source_id=source_id,
                    turn_id=turn_id,
                )
                await self.change_entity_state(
                    entity=operation.source_entity,
                    field_changes=operation.source_state_changes,
                    turn_id=turn_id,
                )
                await self.change_relationship(
                    relationship_type="derived_from",
                    subject=target_ref,
                    object=operation.source_entity,
                    old_object=None,
                    properties={},
                    ended=False,
                    turn_id=turn_id,
                )
                for relationship in operation.relationship_changes:
                    await self.change_relationship(
                        relationship_type=relationship.relationship_type,
                        subject=relationship.subject,
                        object=relationship.object,
                        old_object=relationship.old_object,
                        properties=relationship.properties,
                        ended=relationship.ended,
                        turn_id=turn_id,
                    )
            elif operation.type == "relationship_change":
                await self.change_relationship(
                    relationship_type=operation.relationship_type,
                    subject=operation.subject,
                    object=operation.object,
                    old_object=operation.old_object,
                    properties=operation.properties,
                    ended=operation.ended,
                    turn_id=turn_id,
                )

    async def create_entity(self,
                            *,
                            entity_type: str,
                            properties: dict,
                            source_id: str,
                            turn_id: str,
                            proposed_id: str | None = None,
                            ) -> StateCommitEntityRef:
        label = self._label_for_type(entity_type)
        entity_id = proposed_id or properties.get("id") or str(uuid4())
        node_properties = self._safe_properties({
            **properties,
            "id": entity_id,
        })

        await self._driver.execute_query(
            f"""
            MATCH (source:World|Simulation {{id: $source_id}})
            MATCH (turn:Turn {{id: $turn_id}})
            CREATE (entity:{label})
            SET entity += $properties
            MERGE (source)-[:CONTAINS]->(entity)
            MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(entity)
            RETURN entity
            """,
            parameters_={
                "source_id": source_id,
                "turn_id": turn_id,
                "properties": node_properties,
            },
        )

        if entity_type == "item_stack" and properties.get("item_id"):
            await self._driver.execute_query(
                """
                MATCH (stack:ItemStack {id: $stack_id})
                MATCH (item:Item {id: $item_id})
                MERGE (stack)-[:OF_TYPE]->(item)
                """,
                parameters_={
                    "stack_id": entity_id,
                    "item_id": properties["item_id"],
                },
            )

        return StateCommitEntityRef(
            type=entity_type,
            id=entity_id,
            name=properties.get("name"),
        )

    async def change_entity_state(self,
                                  *,
                                  entity: StateCommitEntityRef,
                                  field_changes: list[StateCommitFieldChange],
                                  turn_id: str,
                                  ):
        if not entity.id or not field_changes:
            return

        label = self._label_for_type(entity.type)
        field_changes, current_activity_changes = self._split_current_activity_changes(field_changes)

        if entity.type == "character" and current_activity_changes:
            await self.change_character_current_activity(
                entity_id=entity.id,
                field_changes=current_activity_changes,
                turn_id=turn_id,
            )

        properties = self._safe_properties({
            change.field_path: change.new_value
            for change in field_changes
        })
        if not properties:
            return

        await self._driver.execute_query(
            f"""
            MATCH (entity:{label} {{id: $entity_id}})
            MATCH (turn:Turn {{id: $turn_id}})
            SET entity += $properties
            MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(entity)
            """,
            parameters_={
                "entity_id": entity.id,
                "turn_id": turn_id,
                "properties": properties,
            },
        )

    async def change_character_current_activity(self,
                                                *,
                                                entity_id: str,
                                                field_changes: list[StateCommitFieldChange],
                                                turn_id: str,
                                                ):
        result = await self._driver.execute_query(
            """
            MATCH (entity:Character {id: $entity_id})
            RETURN entity.current_activity AS current_activity
            LIMIT 1
            """,
            parameters_={"entity_id": entity_id},
        )
        record = result.records[0] if result.records else None
        if not record:
            return

        current_activity = CurrentActivity.model_validate_json(record["current_activity"]).model_dump()
        for change in field_changes:
            field_name = change.field_path.removeprefix("current_activity.")
            if field_name in current_activity and change.new_value is not None:
                current_activity[field_name] = change.new_value

        serialized_activity = CurrentActivity.model_validate(current_activity).model_dump_json()
        await self._driver.execute_query(
            """
            MATCH (entity:Character {id: $entity_id})
            MATCH (turn:Turn {id: $turn_id})
            SET entity.current_activity = $current_activity
            MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(entity)
            """,
            parameters_={
                "entity_id": entity_id,
                "turn_id": turn_id,
                "current_activity": serialized_activity,
            },
        )

    async def change_relationship(self,
                                  *,
                                  relationship_type: str,
                                  subject: StateCommitEntityRef,
                                  object: StateCommitEntityRef | None,
                                  old_object: StateCommitEntityRef | None,
                                  properties: dict,
                                  ended: bool,
                                  turn_id: str,
                                  ):
        if not subject.id:
            return

        original_subject = subject
        subject, object = self._relationship_endpoints(
            relationship_type=relationship_type,
            subject=subject,
            object=object,
        )
        if not subject or not subject.id:
            return

        if old_object:
            old_subject, old_target = self._relationship_endpoints(
                relationship_type=relationship_type,
                subject=original_subject,
                object=old_object,
            )
        else:
            old_subject, old_target = None, None

        rel_type = self._relationship_for_type(relationship_type)
        subject_label = self._label_for_type(subject.type)
        object_label = self._label_for_type(object.type) if object else None
        old_subject_label = self._label_for_type(old_subject.type) if old_subject else None
        old_target_label = self._label_for_type(old_target.type) if old_target else None
        safe_properties = self._safe_properties(properties)

        if old_subject and old_subject.id and old_target and old_target.id:
            await self._driver.execute_query(
                f"""
                MATCH (subject:{old_subject_label} {{id: $subject_id}})-[relationship:{rel_type}]->(old_object:{old_target_label} {{id: $old_object_id}})
                MATCH (turn:Turn {{id: $turn_id}})
                SET relationship.active = false,
                    relationship.ended_at_turn_id = $turn_id
                MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(subject)
                """,
                parameters_={
                    "subject_id": old_subject.id,
                    "old_object_id": old_target.id,
                    "turn_id": turn_id,
                },
            )

        if ended:
            if object and object.id:
                await self._driver.execute_query(
                    f"""
                    MATCH (subject:{subject_label} {{id: $subject_id}})-[relationship:{rel_type}]->(object:{object_label} {{id: $object_id}})
                    MATCH (turn:Turn {{id: $turn_id}})
                    SET relationship.active = false,
                        relationship.ended_at_turn_id = $turn_id
                    MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(subject)
                    """,
                    parameters_={
                        "subject_id": subject.id,
                        "object_id": object.id,
                        "turn_id": turn_id,
                    },
                )
            return

        if not object or not object.id:
            return

        await self._driver.execute_query(
            f"""
            MATCH (subject:{subject_label} {{id: $subject_id}})
            MATCH (object:{object_label} {{id: $object_id}})
            MATCH (turn:Turn {{id: $turn_id}})
            MERGE (subject)-[relationship:{rel_type}]->(object)
            SET relationship += $properties,
                relationship.active = true,
                relationship.updated_at_turn_id = $turn_id
            MERGE (turn)-[:PROPOSED_STATE_CHANGE]->(subject)
            """,
            parameters_={
                "subject_id": subject.id,
                "object_id": object.id,
                "turn_id": turn_id,
                "properties": safe_properties,
            },
        )
