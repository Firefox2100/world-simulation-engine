"""Bounded memory-grounded emotion updates for one character perspective."""

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import (
    Character,
    EmotionChangeAudit,
    EmotionState,
    EmotionUpdateProposal,
    EmotionVector,
    MemoryAtom,
    World,
)

from .simulator_component import SimulatorComponent


class EmotionUpdateContext(BaseModel):
    """Compact local-model context for one character and one turn."""

    actor: Character
    world: World
    state: EmotionState
    effective_emotion: EmotionVector
    turn_id: str
    memories: list[MemoryAtom] = Field(default_factory=list)


class EmotionUpdateApplyResult(BaseModel):
    """Result identifiers without exposing private state to foreground output."""

    emotion_state_id: str | None = None
    audit_id: str | None = None
    applied: bool = False


class EmotionUpdater(SimulatorComponent):
    """Ask for one compact delta, then calculate authoritative values in code."""

    COMPONENT_TYPE = ComponentType.MEMORY_SUMMARIZER
    _MAX_IMMEDIATE_DELTA = 0.35
    _MAX_BASELINE_DELTA = 0.05
    _ALLOWED_EXTENSION_DIMENSIONS = {"fear", "anger", "sadness", "joy"}

    async def update_from_memories(
            self,
            *,
            simulation_id: str,
            character_id: str,
            turn_id: str,
            memory_ids: list[str],
    ) -> EmotionUpdateApplyResult:
        """Apply one event response only when the feature and evidence are valid."""
        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation or not simulation.emotion_enabled or not memory_ids:
            return EmotionUpdateApplyResult()
        actor = await self._db.character.get_character(character_id)
        world = await self._db.world.get_world_by_simulation(simulation_id)
        if not actor or not world:
            return EmotionUpdateApplyResult()
        memories = [
            memory
            for memory_id in list(dict.fromkeys(memory_ids))[:4]
            if (memory := await self._db.memory.get_memory(memory_id)) is not None
        ]
        if not memories:
            return EmotionUpdateApplyResult()
        if not await self._db.emotion.validate_memory_evidence(
                simulation_id=simulation_id,
                character_id=character_id,
                memory_ids=[memory.id for memory in memories],
        ):
            return EmotionUpdateApplyResult()

        existing = await self._db.emotion.get_state(
            simulation_id=simulation_id,
            character_id=character_id,
        )
        state = existing or EmotionState(
            simulation_id=simulation_id,
            character_id=character_id,
            last_updated_at=simulation.current_time,
        )
        decayed = self._db.emotion.decay_state(state, simulation.current_time)
        context = EmotionUpdateContext(
            actor=actor,
            world=world,
            state=decayed,
            effective_emotion=self._db.emotion.combined_vector(decayed),
            turn_id=turn_id,
            memories=memories,
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="emotion_updater",
        )
        llm = await self._prepare_llm_service(simulation_id)
        proposal = await llm.invoke_structured_with_repair(
            output_model=EmotionUpdateProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return EmotionUpdateProposal JSON only. For no response use exactly "
                '{"change": null, "updater_notes": []}. Otherwise immediate_delta and '
                "baseline_delta must be objects, not null. Cite only supplied memory IDs. "
                "Use small valence, arousal, dominance deltas and a list for updater_notes."
            ),
            run_name="emotion_updater.update_from_memories",
        )
        if not proposal.change:
            return EmotionUpdateApplyResult(emotion_state_id=existing.id if existing else None)
        if not self._has_nonzero_delta(
                proposal.change.immediate_delta,
                proposal.change.baseline_delta,
        ):
            return EmotionUpdateApplyResult(emotion_state_id=existing.id if existing else None)
        evidence_ids = list(dict.fromkeys(proposal.change.evidence_memory_ids))
        if not evidence_ids or not set(evidence_ids).issubset({memory.id for memory in memories}):
            return EmotionUpdateApplyResult(emotion_state_id=existing.id if existing else None)

        updated = decayed.model_copy(update={
            "baseline": self._apply_delta(
                decayed.baseline,
                proposal.change.baseline_delta,
                self._MAX_BASELINE_DELTA,
            ),
            "immediate": self._apply_delta(
                decayed.immediate,
                proposal.change.immediate_delta,
                self._MAX_IMMEDIATE_DELTA,
            ),
            "version": decayed.version + 1 if existing else 1,
        })
        stored = (
            await self._db.emotion.update_state(updated)
            if existing else await self._db.emotion.create_state(updated)
        )
        if not stored:
            return EmotionUpdateApplyResult(emotion_state_id=existing.id if existing else None)
        audit = EmotionChangeAudit(
            emotion_state_id=stored.id,
            simulation_id=simulation_id,
            character_id=character_id,
            turn_id=turn_id,
            evidence_memory_ids=evidence_ids,
            changed_at=simulation.current_time,
            change_type="update" if existing else "create",
            previous_version=existing.version if existing else None,
            new_version=stored.version,
            previous_state=existing.model_dump(mode="json") if existing else None,
            new_state=stored.model_dump(mode="json"),
        )
        stored_audit = await self._db.emotion.create_change_audit(audit)
        return EmotionUpdateApplyResult(
            emotion_state_id=stored.id,
            audit_id=stored_audit.id if stored_audit else None,
            applied=stored_audit is not None,
        )

    @staticmethod
    def _has_nonzero_delta(*vectors: EmotionVector) -> bool:
        return any(
            vector.valence
            or vector.arousal
            or vector.dominance
            or any(vector.dimensions.values())
            for vector in vectors
        )

    @classmethod
    def _apply_delta(
            cls,
            current: EmotionVector,
            proposed: EmotionVector,
            maximum_delta: float,
    ) -> EmotionVector:
        def apply(value: float, delta: float) -> float:
            bounded = max(min(delta, maximum_delta), -maximum_delta)
            return max(min(value + bounded, 1), -1)

        dimensions = dict(current.dimensions)
        for key, delta in proposed.dimensions.items():
            if key in cls._ALLOWED_EXTENSION_DIMENSIONS:
                dimensions[key] = apply(dimensions.get(key, 0), delta)
        return EmotionVector(
            valence=apply(current.valence, proposed.valence),
            arousal=apply(current.arousal, proposed.arousal),
            dominance=apply(current.dominance, proposed.dominance),
            dimensions=dimensions,
        )
