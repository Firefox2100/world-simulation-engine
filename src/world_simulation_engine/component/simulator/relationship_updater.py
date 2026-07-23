"""Memory-grounded, single-perspective relationship inference and application."""

from datetime import datetime

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import (
    CompatibilityRelationshipDetails,
    EntityRelationship,
    EmotionVector,
    GenericRelationshipDetails,
    GoalRelationshipDetails,
    InteractionRelationshipDetails,
    InterpersonalRelationshipDetails,
    MemoryAtom,
    ProposedEntityRelationshipChange,
    RelationshipChangeAudit,
    RelationshipEntityRef,
    RelationshipScope,
    RelationshipUpdateProposal,
    RelationshipVisibility,
    SpatialRelationshipDetails,
    SubjectiveEntityClaim,
)

from .simulator_component import SimulatorComponent


class RelationshipUpdateContext(BaseModel):
    """Small prompt context for one character and one committed turn."""
    simulation_id: str
    actor_id: str
    actor_name: str
    simulation_time: datetime
    turn_id: str
    new_memories: list[MemoryAtom] = Field(default_factory=list)
    candidate_entities: list[RelationshipEntityRef] = Field(default_factory=list)
    existing_relationships: list[EntityRelationship] = Field(default_factory=list)
    emotion: EmotionVector | None = None
    subjective_claims: list[SubjectiveEntityClaim] = Field(default_factory=list)


class RelationshipUpdateApplyResult(BaseModel):
    """Identifiers and rejection count produced by deterministic application."""
    applied_relationship_ids: list[str] = Field(default_factory=list)
    audit_ids: list[str] = Field(default_factory=list)
    skipped_changes: int = 0


class RelationshipUpdater(SimulatorComponent):
    """Apply small, memory-grounded relationship changes for one character perspective."""

    COMPONENT_TYPE = ComponentType.MEMORY_SUMMARIZER
    _MAX_ABSOLUTE_DELTA = 0.15
    _MAX_CONFIDENCE_DELTA = 0.2
    _MAX_CANDIDATE_ENTITIES = 16
    _MAX_EXISTING_RELATIONSHIPS = 12

    async def update_from_memories(
            self,
            *,
            simulation_id: str,
            character_id: str,
            turn_id: str,
            memory_ids: list[str],
            candidate_entity_ids: list[str],
    ) -> RelationshipUpdateApplyResult:
        """Propose and apply at most two changes from newly committed memories."""
        if not memory_ids:
            return RelationshipUpdateApplyResult()
        simulation = await self._db.simulation.get_simulation(simulation_id)
        actor = await self._db.character.get_character(character_id)
        if not simulation or not actor:
            return RelationshipUpdateApplyResult(skipped_changes=1)
        new_memories = [
            memory
            for memory_id in list(dict.fromkeys(memory_ids))[:4]
            if (memory := await self._db.memory.get_memory(memory_id)) is not None
        ]
        if not new_memories:
            return RelationshipUpdateApplyResult()

        candidate_ids = list(dict.fromkeys([
            character_id,
            *candidate_entity_ids,
        ]))[:self._MAX_CANDIDATE_ENTITIES]
        candidate_entities = await self._db.entity_relationship.resolve_entity_refs(
            scope_id=simulation_id,
            entity_ids=candidate_ids,
        )
        existing_relationships = await self._db.entity_relationship.list_relationships(
            scope_id=simulation_id,
            perspective_character_id=character_id,
            entity_ids=candidate_ids,
            limit=self._MAX_EXISTING_RELATIONSHIPS,
        )
        candidates_by_id = {entity.id: entity for entity in candidate_entities}
        for relationship in existing_relationships:
            candidates_by_id.setdefault(relationship.source.id, relationship.source)
            candidates_by_id.setdefault(relationship.target.id, relationship.target)
        if len(candidates_by_id) < 2:
            return RelationshipUpdateApplyResult()

        context = RelationshipUpdateContext(
            simulation_id=simulation_id,
            actor_id=actor.id,
            actor_name=actor.name,
            simulation_time=simulation.current_time,
            turn_id=turn_id,
            new_memories=new_memories,
            candidate_entities=list(candidates_by_id.values()),
            existing_relationships=existing_relationships,
            emotion=await self._effective_emotion(
                simulation=simulation,
                character_id=character_id,
            ),
            subjective_claims=await self._subjective_claims(
                simulation_id=simulation_id, observer_character_id=character_id,
                subject_ids=list(candidates_by_id),
            ),
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=(await self._require_world_for_simulation(simulation_id)).language,
            prompt_name="relationship_updater",
        )
        if context.emotion is not None:
            prompt = self._with_emotion_context(prompt)
        if context.subjective_claims:
            prompt = self._with_subjective_claim_context(prompt)
        llm = await self._prepare_llm_service(simulation_id)
        proposal = await llm.invoke_structured_with_repair(
            output_model=RelationshipUpdateProposal,
            messages=prompt,
            data={
                "actor": {"id": actor.id, "name": actor.name},
                **context.model_dump(),
            },
            repair_instruction=(
                "Return RelationshipUpdateProposal with at most two changes. Use only supplied "
                "entity IDs as source_id/target_id; memory IDs are evidence_memory_ids only. "
                "Every change needs kind, source_id, target_id, label, "
                "private_description, confidence, and evidence_memory_ids. Fill only fields "
                "relevant to kind. Spatial requires distance_metres or travel_time_seconds; "
                "compatibility requires compatible. updater_notes must be a list. "
                'When no valid edge exists return {"changes": [], "updater_notes": []}.'
            ),
            run_name="relationship_updater.update_from_memories",
        )
        return await self._apply_proposal(
            proposal=proposal,
            context=context,
        )

    async def _require_world_for_simulation(self, simulation_id: str):
        world = await self._db.world.get_world_by_simulation(simulation_id)
        if not world:
            raise ValueError(f"Simulation {simulation_id} has no base world")
        return world

    async def _apply_proposal(
            self,
            *,
            proposal: RelationshipUpdateProposal,
            context: RelationshipUpdateContext,
    ) -> RelationshipUpdateApplyResult:
        candidates = {entity.id: entity for entity in context.candidate_entities}
        existing_by_id = {
            relationship.id: relationship
            for relationship in context.existing_relationships
        }
        evidence_ids = {memory.id for memory in context.new_memories}
        applied_ids = []
        audit_ids = []
        skipped = 0
        for change in proposal.changes[:2]:
            try:
                applied = await self._apply_change(
                    change=change,
                    context=context,
                    candidates=candidates,
                    existing_by_id=existing_by_id,
                    allowed_evidence_ids=evidence_ids,
                )
            except (TypeError, ValueError):
                applied = None
            if not applied:
                skipped += 1
                continue
            relationship, audit = applied
            applied_ids.append(relationship.id)
            audit_ids.append(audit.id)
            existing_by_id[relationship.id] = relationship
        return RelationshipUpdateApplyResult(
            applied_relationship_ids=applied_ids,
            audit_ids=audit_ids,
            skipped_changes=skipped,
        )

    async def _apply_change(
            self,
            *,
            change: ProposedEntityRelationshipChange,
            context: RelationshipUpdateContext,
            candidates: dict[str, RelationshipEntityRef],
            existing_by_id: dict[str, EntityRelationship],
            allowed_evidence_ids: set[str],
    ) -> tuple[EntityRelationship, RelationshipChangeAudit] | None:
        if change.source_id not in candidates or change.target_id not in candidates:
            return None
        cited_evidence = list(dict.fromkeys(change.evidence_memory_ids))
        if not cited_evidence or not set(cited_evidence).issubset(allowed_evidence_ids):
            return None

        existing = existing_by_id.get(change.relationship_id) if change.relationship_id else None
        if not existing:
            existing = next((
                relationship
                for relationship in existing_by_id.values()
                if relationship.source.id == change.source_id
                and relationship.target.id == change.target_id
                and relationship.label.casefold() == change.label.casefold()
                and relationship.perspective_character_id == context.actor_id
            ), None)
        if existing and (
                existing.source.id != change.source_id
                or existing.target.id != change.target_id
                or existing.perspective_character_id != context.actor_id
                or existing.details.kind != change.kind
        ):
            return None

        details = self._details_from_change(
            change,
            existing,
            changed_at=context.simulation_time,
        )
        if details is None:
            return None
        if existing:
            confidence = self._bounded_confidence(change.confidence, existing.confidence)
            relationship = existing.model_copy(update={
                "label": change.label,
                "private_description": change.private_description,
                "confidence": confidence,
                "details": details,
                "evidence_memory_ids": list(dict.fromkeys([
                    *existing.evidence_memory_ids,
                    *cited_evidence,
                ])),
                "last_changed_at": context.simulation_time,
                "version": existing.version + 1,
            })
            stored = await self._db.entity_relationship.update_relationship(relationship)
            change_type = "update"
        else:
            relationship = EntityRelationship(
                scope_type=RelationshipScope.SIMULATION,
                scope_id=context.simulation_id,
                source=candidates[change.source_id],
                target=candidates[change.target_id],
                label=change.label,
                private_description=change.private_description,
                visibility=RelationshipVisibility.PRIVATE,
                perspective_character_id=context.actor_id,
                confidence=change.confidence,
                details=details,
                evidence_memory_ids=cited_evidence,
                created_at=context.simulation_time,
                last_changed_at=context.simulation_time,
            )
            stored = await self._db.entity_relationship.create_relationship(relationship)
            change_type = "create"
        if not stored:
            return None
        audit = RelationshipChangeAudit(
            relationship_id=stored.id,
            scope_id=stored.scope_id,
            perspective_character_id=context.actor_id,
            turn_id=context.turn_id,
            evidence_memory_ids=cited_evidence,
            changed_at=context.simulation_time,
            change_type=change_type,
            previous_version=existing.version if existing else None,
            new_version=stored.version,
            previous_state=existing.model_dump(mode="json") if existing else None,
            new_state=stored.model_dump(mode="json"),
        )
        stored_audit = await self._db.entity_relationship.create_change_audit(audit)
        if not stored_audit:
            return None
        return stored, stored_audit

    def _details_from_change(
            self,
            change: ProposedEntityRelationshipChange,
            existing: EntityRelationship | None,
            *,
            changed_at: datetime,
    ):
        current = existing.details if existing else None
        if change.kind == "spatial" and (
                change.distance_metres is None
                and change.travel_time_seconds is None
        ):
            return None
        if change.kind == "compatibility" and change.compatible is None:
            return None
        if change.kind == "interpersonal":
            if not (
                    isinstance(current, InterpersonalRelationshipDetails)
                    or current is None
            ):
                return None
            base = current or InterpersonalRelationshipDetails(category=change.label)
            return base.model_copy(update={
                "familiarity": self._bounded_score(
                    base.familiarity,
                    change.familiarity_delta,
                    0,
                    1,
                ),
                "trust": self._bounded_score(base.trust, change.trust_delta, -1, 1),
                "affinity": self._bounded_score(base.affinity, change.affinity_delta, -1, 1),
                "tension": self._bounded_score(base.tension, change.tension_delta, 0, 1),
            })
        if change.kind == "spatial":
            return SpatialRelationshipDetails(
                distance_metres=change.distance_metres,
                travel_time_seconds=change.travel_time_seconds,
                bidirectional=(
                    current.bidirectional
                    if isinstance(current, SpatialRelationshipDetails)
                    else True
                ),
            )
        if change.kind == "interaction":
            base = current if isinstance(current, InteractionRelationshipDetails) else None
            return InteractionRelationshipDetails(
                frequency=change.frequency or (base.frequency if base else None),
                last_occurrence_at=changed_at,
            )
        if change.kind == "goal":
            base = current if isinstance(current, GoalRelationshipDetails) else None
            return GoalRelationshipDetails(
                status=change.goal_status or (base.status if base else "active"),
                priority=(
                    change.goal_priority
                    if change.goal_priority is not None
                    else (base.priority if base else None)
                ),
            )
        if change.kind == "compatibility":
            base = current if isinstance(current, CompatibilityRelationshipDetails) else None
            return CompatibilityRelationshipDetails(
                compatible=bool(change.compatible),
                conditions=change.conditions or (base.conditions if base else []),
            )
        base_attributes = (
            current.attributes
            if isinstance(current, GenericRelationshipDetails)
            else {}
        )
        return GenericRelationshipDetails(attributes={
            **base_attributes,
            **change.attributes,
        })

    @classmethod
    def _bounded_score(
            cls,
            current: float,
            delta: float | None,
            minimum: float,
            maximum: float,
    ) -> float:
        bounded_delta = max(min(delta or 0, cls._MAX_ABSOLUTE_DELTA), -cls._MAX_ABSOLUTE_DELTA)
        return max(min(current + bounded_delta, maximum), minimum)

    @classmethod
    def _bounded_confidence(cls, proposed: float, current: float) -> float:
        return max(
            min(proposed, current + cls._MAX_CONFIDENCE_DELTA),
            current - cls._MAX_CONFIDENCE_DELTA,
        )
