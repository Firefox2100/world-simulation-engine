"""Small-model-friendly synthesis of private entity claims from committed memories."""

import re
from datetime import datetime

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import (
    MemoryAtom, ProposedSubjectiveClaimChange, RelationshipEntityRef,
    SubjectiveClaimChangeAudit, SubjectiveClaimStance, SubjectiveClaimUpdateProposal,
    SubjectiveEntityClaim,
)
from .simulator_component import SimulatorComponent


class SubjectiveModelUpdateContext(BaseModel):
    simulation_id: str
    actor_id: str
    actor_name: str
    simulation_time: datetime
    turn_id: str
    new_memories: list[MemoryAtom] = Field(default_factory=list)
    candidate_entities: list[RelationshipEntityRef] = Field(default_factory=list)
    existing_claims: list[SubjectiveEntityClaim] = Field(default_factory=list)


class SubjectiveModelApplyResult(BaseModel):
    applied_claim_ids: list[str] = Field(default_factory=list)
    audit_ids: list[str] = Field(default_factory=list)
    skipped_changes: int = 0


class SubjectiveModelUpdater(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.MEMORY_SUMMARIZER
    _MAX_CANDIDATES = 16
    _MAX_EXISTING = 16
    _CONFIDENCE_STEP = 0.1

    async def update_from_memories(self, *, simulation_id: str, character_id: str, turn_id: str,
                                   memory_ids: list[str], candidate_entity_ids: list[str]) -> SubjectiveModelApplyResult:
        if not memory_ids:
            return SubjectiveModelApplyResult()
        simulation = await self._db.simulation.get_simulation(simulation_id)
        actor = await self._db.character.get_character(character_id)
        if not simulation or not actor:
            return SubjectiveModelApplyResult(skipped_changes=1)
        memories = [memory for memory_id in list(dict.fromkeys(memory_ids))[:4]
                    if (memory := await self._db.memory.get_memory(memory_id)) is not None]
        refs = await self._db.entity_relationship.resolve_entity_refs(
            scope_id=simulation_id,
            entity_ids=list(dict.fromkeys(candidate_entity_ids))[:self._MAX_CANDIDATES],
        )
        refs = [ref for ref in refs if ref.id != character_id]
        if not memories or not refs:
            return SubjectiveModelApplyResult()
        existing = await self._db.subjective_entity_claim.list_claims(
            simulation_id=simulation_id, observer_character_id=character_id,
            subject_ids=[ref.id for ref in refs], limit=self._MAX_EXISTING,
        )
        context = SubjectiveModelUpdateContext(
            simulation_id=simulation_id, actor_id=character_id, actor_name=actor.name,
            simulation_time=simulation.current_time, turn_id=turn_id, new_memories=memories,
            candidate_entities=refs, existing_claims=existing,
        )
        world = await self._db.world.get_world_by_simulation(simulation_id)
        if not world:
            return SubjectiveModelApplyResult(skipped_changes=1)
        prompt = await self._prepare_prompt(simulation_id=simulation_id, language=world.language,
                                            prompt_name="subjective_model_updater")
        proposal = await (await self._prepare_llm_service(simulation_id)).invoke_structured_with_repair(
            output_model=SubjectiveClaimUpdateProposal, messages=prompt,
            data={"actor": {"id": actor.id, "name": actor.name}, **context.model_dump()},
            repair_instruction=("Return at most two changes using only supplied subject, claim, and memory IDs. "
                                "Use supports for a new claim. Return changes: [] for weak evidence."),
            run_name="subjective_model_updater.update_from_memories",
        )
        return await self._apply_proposal(proposal, context)

    async def _apply_proposal(self, proposal: SubjectiveClaimUpdateProposal,
                              context: SubjectiveModelUpdateContext) -> SubjectiveModelApplyResult:
        subjects = {ref.id: ref for ref in context.candidate_entities}
        existing = {claim.id: claim for claim in context.existing_claims}
        allowed_memories = {memory.id for memory in context.new_memories}
        applied, audits, skipped = [], [], 0
        for change in proposal.changes[:2]:
            result = await self._apply_change(change, context, subjects, existing, allowed_memories)
            if not result:
                skipped += 1
                continue
            claim, audit = result
            applied.append(claim.id); audits.append(audit.id); existing[claim.id] = claim
        return SubjectiveModelApplyResult(applied_claim_ids=applied, audit_ids=audits, skipped_changes=skipped)

    async def _apply_change(self, change: ProposedSubjectiveClaimChange,
                            context: SubjectiveModelUpdateContext,
                            subjects: dict[str, RelationshipEntityRef],
                            existing: dict[str, SubjectiveEntityClaim], allowed_memories: set[str]):
        evidence = list(dict.fromkeys(change.evidence_memory_ids))
        if change.subject_id not in subjects or not evidence or not set(evidence).issubset(allowed_memories):
            return None
        normalized = self.normalize_statement(change.statement)
        current = existing.get(change.claim_id) if change.claim_id else None
        if not current:
            current = next((claim for claim in existing.values()
                            if claim.subject.id == change.subject_id and claim.category == change.category
                            and claim.normalized_statement == normalized), None)
        if current and (current.observer_character_id != context.actor_id
                        or current.subject.id != change.subject_id or current.category != change.category):
            return None
        if current:
            supports = list(current.supporting_memory_ids)
            contradicts = list(current.contradicting_memory_ids)
            target = supports if change.evidence_effect == "supports" else contradicts
            target.extend(item for item in evidence if item not in target)
            delta = self._CONFIDENCE_STEP if change.evidence_effect == "supports" else -self._CONFIDENCE_STEP
            candidate = current.model_copy(update={
                "stance": change.stance, "confidence": max(0, min(1, current.confidence + delta)),
                "supporting_memory_ids": supports, "contradicting_memory_ids": contradicts,
                "last_updated_at": context.simulation_time, "version": current.version + 1,
            })
            stored = await self._db.subjective_entity_claim.update_claim(candidate)
            change_type = "update"
        else:
            if change.evidence_effect != "supports":
                return None
            candidate = SubjectiveEntityClaim(
                simulation_id=context.simulation_id, observer_character_id=context.actor_id,
                subject=subjects[change.subject_id], category=change.category, statement=change.statement.strip(),
                normalized_statement=normalized, stance=change.stance,
                confidence=self.initial_confidence(change.stance), supporting_memory_ids=evidence,
                first_observed_at=context.simulation_time, last_updated_at=context.simulation_time,
            )
            stored = await self._db.subjective_entity_claim.create_claim(candidate)
            change_type = "create"
        if not stored:
            return None
        audit = SubjectiveClaimChangeAudit(
            claim_id=stored.id, simulation_id=context.simulation_id, observer_character_id=context.actor_id,
            turn_id=context.turn_id, evidence_memory_ids=evidence, changed_at=context.simulation_time,
            change_type=change_type, previous_version=current.version if current else None,
            new_version=stored.version, previous_state=current.model_dump(mode="json") if current else None,
            new_state=stored.model_dump(mode="json"),
        )
        stored_audit = await self._db.subjective_entity_claim.create_change_audit(audit)
        return (stored, stored_audit) if stored_audit else None

    @staticmethod
    def normalize_statement(value: str) -> str:
        return re.sub(r"[^\w]+", " ", value.casefold()).strip()

    @staticmethod
    def initial_confidence(stance: SubjectiveClaimStance) -> float:
        return {SubjectiveClaimStance.BELIEVES: .65, SubjectiveClaimStance.DENIES: .65,
                SubjectiveClaimStance.SUSPECTS: .45, SubjectiveClaimStance.DOUBTS: .4,
                SubjectiveClaimStance.UNCERTAIN: .35}[stance]
