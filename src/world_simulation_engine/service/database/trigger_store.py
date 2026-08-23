"""Neo4j persistence for Trigger and TriggerActivation.

A trigger's condition/effect trees are opaque JSON blobs from the graph's perspective (same
pattern as EntityVariableSet.variables_json in variable_store.py) since they're arbitrarily
nested discriminated unions, not flat per-field graph properties.
"""

import json
import uuid
from typing import Any

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import TriggerEffectType, TriggerStatus
from world_simulation_engine.model import ForcedActionEffect, NarrativeBeatEffect, PerceivedCueEffect, Trigger, \
    TriggerActivation


class TriggerStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def _trigger_from_node(node) -> Trigger:
        gate_effect_json = node.get("gate_effect_json")
        return Trigger(
            id=node["id"],
            source_id=node["source_id"],
            name=node["name"],
            description=node.get("description", ""),
            condition=json.loads(node["condition_json"]),
            effect_kind=node["effect_kind"],
            effects=[json.loads(entry) for entry in node.get("effects_json") or []],
            gate_effect=json.loads(gate_effect_json) if gate_effect_json else None,
            chance=node.get("chance"),
            repeatable=node["repeatable"],
            cooldown_turns=node.get("cooldown_turns"),
            reversible=node["reversible"],
            status=node["status"],
            last_condition_result=node["last_condition_result"],
            last_fired_turn_id=node.get("last_fired_turn_id"),
            last_evaluated_turn_id=node.get("last_evaluated_turn_id"),
        )

    @staticmethod
    def _trigger_parameters(trigger: Trigger) -> dict:
        return {
            "id": trigger.id,
            "source_id": trigger.source_id,
            "name": trigger.name,
            "description": trigger.description,
            "condition_json": json.dumps(trigger.condition.model_dump(mode="json")),
            "effect_kind": trigger.effect_kind,
            "effects_json": [json.dumps(effect.model_dump(mode="json")) for effect in trigger.effects],
            "gate_effect_json": (
                json.dumps(trigger.gate_effect.model_dump(mode="json")) if trigger.gate_effect else None
            ),
            "chance": trigger.chance,
            "repeatable": trigger.repeatable,
            "cooldown_turns": trigger.cooldown_turns,
            "reversible": trigger.reversible,
            "status": trigger.status,
            "last_condition_result": trigger.last_condition_result,
            "last_fired_turn_id": trigger.last_fired_turn_id,
            "last_evaluated_turn_id": trigger.last_evaluated_turn_id,
        }

    async def create_trigger(self, trigger: Trigger) -> Trigger | None:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            CREATE (trigger:Trigger {
                id: $id, source_id: $source_id, name: $name, description: $description,
                condition_json: $condition_json, effect_kind: $effect_kind,
                effects_json: $effects_json, gate_effect_json: $gate_effect_json,
                chance: $chance, repeatable: $repeatable, cooldown_turns: $cooldown_turns,
                reversible: $reversible, status: $status,
                last_condition_result: $last_condition_result,
                last_fired_turn_id: $last_fired_turn_id,
                last_evaluated_turn_id: $last_evaluated_turn_id
            })
            MERGE (source)-[:CONTAINS]->(trigger)
            RETURN trigger
            """,
            parameters_=self._trigger_parameters(trigger),
        )
        return self._trigger_from_node(result.records[0]["trigger"]) if result.records else None

    async def get_trigger(self, trigger_id: str) -> Trigger | None:
        result = await self._driver.execute_query(
            "MATCH (trigger:Trigger {id: $trigger_id}) RETURN trigger LIMIT 1",
            parameters_={"trigger_id": trigger_id},
        )
        return self._trigger_from_node(result.records[0]["trigger"]) if result.records else None

    async def list_triggers(
            self,
            source_id: str | None = None,
            status: TriggerStatus | None = None,
    ) -> list[Trigger]:
        result = await self._driver.execute_query(
            """
            MATCH (trigger:Trigger)
            WHERE ($source_id IS NULL OR EXISTS {
                    MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(trigger)
                })
                AND ($status IS NULL OR trigger.status = $status)
            RETURN trigger ORDER BY trigger.name
            """,
            parameters_={"source_id": source_id, "status": status},
        )
        return [self._trigger_from_node(record["trigger"]) for record in result.records]

    async def list_evaluation_candidates(self, simulation_id: str) -> list[Trigger]:
        """DORMANT/ACTIVE triggers only - DISABLED is excluded, and CONSUMED (one-shot, already
        fired) never needs re-evaluating."""
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(trigger:Trigger)
            WHERE trigger.status IN $statuses
            RETURN trigger ORDER BY trigger.id
            """,
            parameters_={
                "simulation_id": simulation_id,
                "statuses": [TriggerStatus.DORMANT, TriggerStatus.ACTIVE],
            },
        )
        return [self._trigger_from_node(record["trigger"]) for record in result.records]

    async def update_trigger(self, trigger: Trigger) -> Trigger | None:
        """Full-field replace, used by CRUD editing."""
        result = await self._driver.execute_query(
            """
            MATCH (trigger:Trigger {id: $id})
            SET trigger += $properties
            RETURN trigger LIMIT 1
            """,
            parameters_={"id": trigger.id, "properties": self._trigger_parameters(trigger)},
        )
        return self._trigger_from_node(result.records[0]["trigger"]) if result.records else None

    async def update_trigger_runtime_state(
            self,
            *,
            trigger_id: str,
            status: TriggerStatus,
            last_condition_result: bool,
            last_evaluated_turn_id: str | None,
            last_fired_turn_id: str | None = None,
    ) -> Trigger | None:
        """Cheap-path update used by TriggerEngine every evaluation, without touching the
        condition/effect definition fields at all."""
        result = await self._driver.execute_query(
            """
            MATCH (trigger:Trigger {id: $trigger_id})
            SET trigger.status = $status,
                trigger.last_condition_result = $last_condition_result,
                trigger.last_evaluated_turn_id = $last_evaluated_turn_id,
                trigger.last_fired_turn_id = coalesce($last_fired_turn_id, trigger.last_fired_turn_id)
            RETURN trigger LIMIT 1
            """,
            parameters_={
                "trigger_id": trigger_id,
                "status": status,
                "last_condition_result": last_condition_result,
                "last_evaluated_turn_id": last_evaluated_turn_id,
                "last_fired_turn_id": last_fired_turn_id,
            },
        )
        return self._trigger_from_node(result.records[0]["trigger"]) if result.records else None

    async def delete_trigger(self, trigger_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (trigger:Trigger {id: $trigger_id})
            WITH collect(trigger) AS triggers
            FOREACH (trigger IN triggers | DETACH DELETE trigger)
            RETURN size(triggers) AS deleted
            """,
            parameters_={"trigger_id": trigger_id},
        )
        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def copy_triggers(
            self,
            *,
            world_id: str,
            simulation_id: str,
            entity_id_map: dict[str, str],
    ) -> list[Trigger]:
        """Copy every world-authored trigger into a simulation, remapping any entity id embedded
        in its condition/effect trees via `entity_id_map` (source id -> copy id, built by the
        caller from every copy_* pair list produced during simulation creation).

        Done in Python rather than Cypher (unlike other stores' flat-property CREATE...FROM
        copies) because a trigger's condition/effects are deeply nested, arbitrarily-shaped JSON
        with entity ids scattered at unpredictable positions (character_id, owner_id, item/
        equipment/container refs inside state_mutation operations, ...) - a generic recursive
        string-substitution pass is far simpler and less error-prone than per-shape Cypher.
        """
        world_triggers = await self.list_triggers(source_id=world_id)
        copied = []
        for trigger in world_triggers:
            remapped = self._remap_entity_ids(trigger.model_dump(mode="json"), entity_id_map)
            copy = Trigger.model_validate({
                **remapped,
                "id": str(uuid.uuid4()),
                "source_id": simulation_id,
                "status": TriggerStatus.DORMANT,
                "last_condition_result": False,
                "last_fired_turn_id": None,
                "last_evaluated_turn_id": None,
            })
            stored = await self.create_trigger(copy)
            if stored:
                copied.append(stored)
        return copied

    @classmethod
    def _remap_entity_ids(cls, value: Any, entity_id_map: dict[str, str]) -> Any:
        if isinstance(value, str):
            return entity_id_map.get(value, value)
        if isinstance(value, list):
            return [cls._remap_entity_ids(item, entity_id_map) for item in value]
        if isinstance(value, dict):
            return {key: cls._remap_entity_ids(item, entity_id_map) for key, item in value.items()}
        return value

    # -- TriggerActivation -------------------------------------------------------------------

    @staticmethod
    def _activation_from_node(node) -> TriggerActivation:
        return TriggerActivation(
            id=node["id"],
            trigger_id=node["trigger_id"],
            simulation_id=node["simulation_id"],
            fired_at_turn_id=node["fired_at_turn_id"],
            effect=json.loads(node["effect_json"]),
            consumed=node["consumed"],
            consumed_at_turn_id=node.get("consumed_at_turn_id"),
        )

    @staticmethod
    def _relevant_character_ids(effect) -> list[str]:
        if isinstance(effect, ForcedActionEffect):
            return [effect.character_id]
        if isinstance(effect, NarrativeBeatEffect):
            return list(effect.relevant_character_ids)
        if isinstance(effect, PerceivedCueEffect):
            return list(effect.character_ids)
        return []

    async def record_activation(self, activation: TriggerActivation) -> TriggerActivation | None:
        result = await self._driver.execute_query(
            """
            MATCH (trigger:Trigger {id: $trigger_id})
            MATCH (simulation:Simulation {id: $simulation_id})
            CREATE (activation:TriggerActivation {
                id: $id, trigger_id: $trigger_id, simulation_id: $simulation_id,
                fired_at_turn_id: $fired_at_turn_id, effect_json: $effect_json,
                effect_type: $effect_type, relevant_character_ids: $relevant_character_ids,
                consumed: $consumed, consumed_at_turn_id: $consumed_at_turn_id
            })
            MERGE (trigger)-[:FIRED]->(activation)
            MERGE (simulation)-[:CONTAINS]->(activation)
            RETURN activation
            """,
            parameters_={
                "id": activation.id,
                "trigger_id": activation.trigger_id,
                "simulation_id": activation.simulation_id,
                "fired_at_turn_id": activation.fired_at_turn_id,
                "effect_json": json.dumps(activation.effect.model_dump(mode="json")),
                "effect_type": activation.effect.type,
                "relevant_character_ids": self._relevant_character_ids(activation.effect),
                "consumed": activation.consumed,
                "consumed_at_turn_id": activation.consumed_at_turn_id,
            },
        )
        return self._activation_from_node(result.records[0]["activation"]) if result.records else None

    async def list_unconsumed_activations(
            self,
            *,
            simulation_id: str,
            effect_type: TriggerEffectType | None = None,
    ) -> list[TriggerActivation]:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(activation:TriggerActivation)
            WHERE NOT activation.consumed
                AND ($effect_type IS NULL OR activation.effect_type = $effect_type)
            RETURN activation ORDER BY activation.fired_at_turn_id
            """,
            parameters_={"simulation_id": simulation_id, "effect_type": effect_type},
        )
        return [self._activation_from_node(record["activation"]) for record in result.records]

    async def mark_activations_consumed(self, activation_ids: list[str], *, turn_id: str | None = None) -> None:
        """`turn_id` is best-effort provenance only - callers that consume an activation before a
        turn exists yet (e.g. Narrator, which runs before the turn it narrates is committed) omit
        it rather than delaying consumption until a turn_id becomes available."""
        if not activation_ids:
            return
        await self._driver.execute_query(
            """
            UNWIND $activation_ids AS activation_id
            MATCH (activation:TriggerActivation {id: activation_id})
            SET activation.consumed = true, activation.consumed_at_turn_id = $turn_id
            """,
            parameters_={"activation_ids": activation_ids, "turn_id": turn_id},
        )
