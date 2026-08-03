"""Bounded, memory-grounded updates to one entity's arbitrary tracked variables."""

from datetime import datetime

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import (
    EntityVariableSet,
    MemoryAtom,
    PhysicalEntityType,
    ProposedVariableChange,
    VariableChangeAudit,
    VariableDefinition,
    VariableUpdateProposal,
    VariableValueType,
)

from .simulator_component import SimulatorComponent


class VariableUpdateContext(BaseModel):
    """Compact local-model context for one entity and one turn."""

    owner_id: str
    owner_type: PhysicalEntityType
    owner_name: str
    simulation_time: datetime
    variables: list[VariableDefinition] = Field(default_factory=list)
    memories: list[MemoryAtom] = Field(default_factory=list)


class VariableUpdateApplyResult(BaseModel):
    """Result identifiers without exposing tracked values to foreground output."""

    variable_set_id: str | None = None
    audit_id: str | None = None
    applied_variable_names: list[str] = Field(default_factory=list)
    skipped_changes: int = 0


class VariableUpdater(SimulatorComponent):
    """Ask for a small set of variable changes, then bound and apply them in code.

    Reuses the memory-summarizer chat model, like EmotionUpdater/RelationshipUpdater/
    SubjectiveModelUpdater - all four run together as isolated derived updates after memory
    commit, so they share one configured model per simulation instead of requiring four.
    """

    COMPONENT_TYPE = ComponentType.MEMORY_SUMMARIZER
    _MAX_MEMORIES = 4

    async def update_from_memories(
            self,
            *,
            simulation_id: str,
            owner_id: str,
            turn_id: str,
            memory_ids: list[str],
    ) -> VariableUpdateApplyResult:
        """Apply at most a handful of bounded, evidence-grounded variable changes.

        Most entities have no EntityVariableSet at all - variables are used sparingly, only for
        cards/worlds that actually define tracked attributes - so the common case is a fast no-op.
        """
        if not memory_ids:
            return VariableUpdateApplyResult()
        existing = await self._db.variable.get_variable_set(owner_id)
        if not existing or not existing.variables:
            return VariableUpdateApplyResult()
        simulation = await self._db.simulation.get_simulation(simulation_id)
        world = await self._db.world.get_world_by_simulation(simulation_id)
        if not simulation or not world:
            return VariableUpdateApplyResult(variable_set_id=existing.id)

        memories = [
            memory
            for memory_id in list(dict.fromkeys(memory_ids))[:self._MAX_MEMORIES]
            if (memory := await self._db.memory.get_memory(memory_id)) is not None
        ]
        if not memories:
            return VariableUpdateApplyResult(variable_set_id=existing.id)

        owner_refs = await self._db.entity_relationship.resolve_entity_refs(
            scope_id=simulation_id,
            entity_ids=[owner_id],
        )
        owner_name = owner_refs[0].name or owner_id if owner_refs else owner_id

        context = VariableUpdateContext(
            owner_id=owner_id,
            owner_type=existing.owner_type,
            owner_name=owner_name,
            simulation_time=simulation.current_time,
            variables=existing.variables,
            memories=memories,
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="variable_updater",
        )
        llm = await self._prepare_llm_service(simulation_id)
        proposal = await llm.invoke_structured_with_repair(
            output_model=VariableUpdateProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return VariableUpdateProposal JSON only. For no changes use exactly "
                '{"changes": [], "updater_notes": []}. Each change needs name (must match a '
                "tracked variable listed above), new_value (matching that variable's type, range, "
                "and allowed values), evidence_memory_ids (only from the supplied memories), and reason."
            ),
            run_name="variable_updater.update_from_memories",
        )
        return await self._apply_proposal(
            proposal=proposal,
            existing=existing,
            memories=memories,
            simulation_time=simulation.current_time,
            turn_id=turn_id,
        )

    @staticmethod
    def _bounded_value(value, definition: VariableDefinition):
        """Return `value` clamped/validated against `definition`, or None if it can't apply."""
        if not VariableDefinition.matches_value_type(value, definition.value_type):
            return None
        if definition.value_type == VariableValueType.STRING:
            if definition.allowed_values and value not in definition.allowed_values:
                return None
            return value
        if definition.minimum is not None and value < definition.minimum:
            value = definition.minimum
        if definition.maximum is not None and value > definition.maximum:
            value = definition.maximum
        return int(value) if definition.value_type == VariableValueType.INTEGER else value

    async def _apply_proposal(
            self,
            *,
            proposal: VariableUpdateProposal,
            existing: EntityVariableSet,
            memories: list[MemoryAtom],
            simulation_time: datetime,
            turn_id: str,
    ) -> VariableUpdateApplyResult:
        if not proposal.changes:
            return VariableUpdateApplyResult(variable_set_id=existing.id)

        allowed_evidence_ids = {memory.id for memory in memories}
        index_by_name = {definition.name: index for index, definition in enumerate(existing.variables)}
        updated_variables = list(existing.variables)
        applied_names: list[str] = []
        cited_evidence: set[str] = set()
        skipped = 0

        for change in proposal.changes[:self._MAX_MEMORIES]:
            applied = self._apply_change(
                change=change,
                definition=(
                    updated_variables[index_by_name[change.name]]
                    if change.name in index_by_name else None
                ),
                allowed_evidence_ids=allowed_evidence_ids,
            )
            if applied is None:
                skipped += 1
                continue
            updated_definition, evidence = applied
            updated_variables[index_by_name[change.name]] = updated_definition
            applied_names.append(change.name)
            cited_evidence.update(evidence)

        if not applied_names:
            return VariableUpdateApplyResult(variable_set_id=existing.id, skipped_changes=skipped)

        candidate = existing.model_copy(update={
            "variables": updated_variables,
            "last_updated_at": simulation_time,
            "version": existing.version + 1,
        })
        stored = await self._db.variable.update_variable_set(candidate)
        if not stored:
            return VariableUpdateApplyResult(
                variable_set_id=existing.id,
                skipped_changes=skipped + len(applied_names),
            )

        audit = VariableChangeAudit(
            variable_set_id=stored.id,
            source_id=stored.source_id,
            owner_id=stored.owner_id,
            turn_id=turn_id,
            evidence_memory_ids=sorted(cited_evidence),
            changed_at=simulation_time,
            change_type="update",
            previous_version=existing.version,
            new_version=stored.version,
            previous_state=existing.model_dump(mode="json"),
            new_state=stored.model_dump(mode="json"),
        )
        stored_audit = await self._db.variable.create_change_audit(audit)
        return VariableUpdateApplyResult(
            variable_set_id=stored.id,
            audit_id=stored_audit.id if stored_audit else None,
            applied_variable_names=applied_names,
            skipped_changes=skipped,
        )

    @classmethod
    def _apply_change(
            cls,
            *,
            change: ProposedVariableChange,
            definition: VariableDefinition | None,
            allowed_evidence_ids: set[str],
    ) -> tuple[VariableDefinition, list[str]] | None:
        if not definition:
            return None
        evidence = list(dict.fromkeys(change.evidence_memory_ids))
        if not evidence or not set(evidence).issubset(allowed_evidence_ids):
            return None
        bounded = cls._bounded_value(change.new_value, definition)
        if bounded is None:
            return None
        return definition.model_copy(update={"value": bounded}), evidence
