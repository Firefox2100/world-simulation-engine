"""Neo4j persistence for observer-private entity claims."""

import json

from neo4j import AsyncDriver

from world_simulation_engine.model import (
    RelationshipEntityRef,
    SubjectiveClaimChangeAudit,
    SubjectiveEntityClaim,
)


class SubjectiveEntityClaimStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def _from_record(record) -> SubjectiveEntityClaim:
        node = record["claim"]
        first = node["first_observed_at"]
        last = node["last_updated_at"]
        if hasattr(first, "to_native"):
            first = first.to_native()
        if hasattr(last, "to_native"):
            last = last.to_native()
        return SubjectiveEntityClaim(
            id=node["id"], simulation_id=node["simulation_id"],
            observer_character_id=node["observer_character_id"],
            subject=RelationshipEntityRef(type=node["subject_type"], id=record["subject"]["id"],
                                          name=record["subject"].get("name")),
            category=node["category"], statement=node["statement"],
            normalized_statement=node["normalized_statement"], stance=node["stance"],
            confidence=node["confidence"],
            supporting_memory_ids=list(record.get("supporting_memory_ids") or []),
            contradicting_memory_ids=list(record.get("contradicting_memory_ids") or []),
            first_observed_at=first, last_updated_at=last, version=node["version"], active=node["active"],
        )

    @staticmethod
    def _params(claim: SubjectiveEntityClaim) -> dict:
        return claim.model_dump(mode="python", exclude={"subject"}) | {
            "subject_id": claim.subject.id, "subject_type": claim.subject.type,
        }

    async def create_claim(self, claim: SubjectiveEntityClaim) -> SubjectiveEntityClaim | None:
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})-[:CONTAINS*0..]->(observer:Character {id: $observer_character_id})
            MATCH (subject {id: $subject_id})
            WHERE ($subject_type IN labels(subject) OR toLower(replace($subject_type, '_', '')) IN [label IN labels(subject) | toLower(label)])
              AND (EXISTS { MATCH (simulation)-[:CONTAINS*0..]->(subject) } OR EXISTS { MATCH (simulation)-[:BASED_ON]->(:World)-[:CONTAINS]->(subject:Item) })
            OPTIONAL MATCH (memory:MemoryAtom) WHERE memory.id IN $evidence_ids AND EXISTS { MATCH (observer)-[:REMEMBERS]->(memory) }
            WITH simulation, observer, subject, collect(DISTINCT memory) AS memories
            WHERE size(memories) = size($evidence_ids) AND NOT EXISTS { MATCH (:SubjectiveEntityClaim {id: $id}) }
            CREATE (claim:SubjectiveEntityClaim {id:$id, simulation_id:$simulation_id, observer_character_id:$observer_character_id,
              subject_type:$subject_type, category:$category, statement:$statement, normalized_statement:$normalized_statement,
              stance:$stance, confidence:$confidence, first_observed_at:$first_observed_at, last_updated_at:$last_updated_at,
              supporting_memory_ids:$supporting_memory_ids, contradicting_memory_ids:$contradicting_memory_ids,
              version:$version, active:$active})
            MERGE (simulation)-[:CONTAINS]->(claim)
            MERGE (observer)-[:HOLDS_MODEL]->(claim)
            MERGE (claim)-[:ABOUT]->(subject)
            FOREACH (m IN memories | MERGE (m)-[:CLAIM_EVIDENCE]->(claim))
            RETURN claim, subject, $supporting_memory_ids AS supporting_memory_ids, $contradicting_memory_ids AS contradicting_memory_ids
            """,
            parameters_=self._params(claim) | {
                "evidence_ids": list(dict.fromkeys([*claim.supporting_memory_ids, *claim.contradicting_memory_ids]))
            },
        )
        return self._from_record(result.records[0]) if result.records else None

    async def get_claim(self, claim_id: str) -> SubjectiveEntityClaim | None:
        result = await self._driver.execute_query(
            """MATCH (claim:SubjectiveEntityClaim {id:$id})-[:ABOUT]->(subject)
            RETURN claim, subject, claim.supporting_memory_ids AS supporting_memory_ids,
              claim.contradicting_memory_ids AS contradicting_memory_ids LIMIT 1""",
            parameters_={"id": claim_id},
        )
        return self._from_record(result.records[0]) if result.records else None

    async def list_claims(self, *, simulation_id: str, observer_character_id: str,
                          subject_ids: list[str] | None = None, active_only: bool = True,
                          limit: int = 30) -> list[SubjectiveEntityClaim]:
        """Always require an observer: there is deliberately no omniscient recall query."""
        result = await self._driver.execute_query(
            """MATCH (:Simulation {id:$simulation_id})-[:CONTAINS]->(claim:SubjectiveEntityClaim)-[:ABOUT]->(subject)
            WHERE claim.observer_character_id=$observer_character_id AND (NOT $active_only OR claim.active)
              AND ($subject_ids IS NULL OR subject.id IN $subject_ids)
            RETURN claim, subject, claim.supporting_memory_ids AS supporting_memory_ids,
              claim.contradicting_memory_ids AS contradicting_memory_ids
            ORDER BY claim.confidence DESC, claim.last_updated_at DESC LIMIT $limit""",
            parameters_={"simulation_id": simulation_id, "observer_character_id": observer_character_id,
                         "subject_ids": list(dict.fromkeys(subject_ids)) if subject_ids is not None else None,
                         "active_only": active_only, "limit": limit},
        )
        return [self._from_record(record) for record in result.records]

    async def update_claim(self, claim: SubjectiveEntityClaim) -> SubjectiveEntityClaim | None:
        existing = await self.get_claim(claim.id)
        if not existing or not self._valid_update(existing, claim):
            return None
        result = await self._driver.execute_query(
            """MATCH (claim:SubjectiveEntityClaim {id:$id})-[:ABOUT]->(subject)
            WHERE claim.version=$expected_version
            SET claim.statement=$statement, claim.normalized_statement=$normalized_statement, claim.stance=$stance,
              claim.confidence=$confidence, claim.supporting_memory_ids=$supporting_memory_ids,
              claim.contradicting_memory_ids=$contradicting_memory_ids, claim.last_updated_at=$last_updated_at,
              claim.version=$version, claim.active=$active
            RETURN claim, subject, claim.supporting_memory_ids AS supporting_memory_ids,
              claim.contradicting_memory_ids AS contradicting_memory_ids""",
            parameters_=self._params(claim) | {"expected_version": existing.version},
        )
        return self._from_record(result.records[0]) if result.records else None

    @staticmethod
    def _valid_update(old: SubjectiveEntityClaim, new: SubjectiveEntityClaim) -> bool:
        return (old.simulation_id == new.simulation_id and old.observer_character_id == new.observer_character_id
                and old.subject == new.subject and old.category == new.category
                and old.first_observed_at == new.first_observed_at and new.version == old.version + 1
                and new.last_updated_at >= old.last_updated_at
                and set(old.supporting_memory_ids).issubset(new.supporting_memory_ids)
                and set(old.contradicting_memory_ids).issubset(new.contradicting_memory_ids))

    async def create_change_audit(self, audit: SubjectiveClaimChangeAudit) -> SubjectiveClaimChangeAudit | None:
        result = await self._driver.execute_query(
            """MATCH (simulation:Simulation {id:$simulation_id})-[:CONTAINS]->(claim:SubjectiveEntityClaim {id:$claim_id})
            MATCH (simulation)-[:CONTAINS]->(turn:Turn {id:$turn_id})
            MATCH (simulation)-[:CONTAINS*0..]->(observer:Character {id:$observer_character_id})
            MATCH (memory:MemoryAtom) WHERE memory.id IN $evidence_memory_ids AND EXISTS { MATCH (observer)-[:REMEMBERS]->(memory) }
            WITH simulation, claim, turn, collect(DISTINCT memory) AS memories
            WHERE size(memories)=size($evidence_memory_ids)
            CREATE (audit:SubjectiveClaimChangeAudit {id:$id, claim_id:$claim_id, simulation_id:$simulation_id,
              observer_character_id:$observer_character_id, turn_id:$turn_id, evidence_memory_ids:$evidence_memory_ids,
              changed_at:$changed_at, change_type:$change_type, previous_version:$previous_version,
              new_version:$new_version, previous_state_json:$previous_state_json, new_state_json:$new_state_json})
            MERGE (simulation)-[:CONTAINS]->(audit) MERGE (turn)-[:TRIGGERED]->(audit) MERGE (audit)-[:CHANGED]->(claim)
            RETURN audit""",
            parameters_=audit.model_dump(exclude={"previous_state", "new_state"}) | {
                "previous_state_json": json.dumps(audit.previous_state, sort_keys=True) if audit.previous_state else None,
                "new_state_json": json.dumps(audit.new_state, sort_keys=True)},
        )
        return audit if result.records else None
