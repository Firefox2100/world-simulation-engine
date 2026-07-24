from datetime import datetime, timedelta
from math import exp, log, sqrt
from typing import Optional
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import (
    ActionType,
    ComponentType,
    IntentType,
    MemoryStance,
    MemorySupportType,
    Salience,
    SupportedLanguage,
)
from world_simulation_engine.model import (
    Intent,
    EntityRelationship,
    EmotionVector,
    ActionProposal,
    Character,
    CharacterActionPlan,
    Location,
    InventoryStack,
    InventoryEquipment,
    ReactionHistoryEntry,
    SceneCoordinationResult,
    Simulation,
    World,
    MemoryAtom,
    SubjectiveEntityClaim,
    PerceivedBackgroundCharacter,
    PerceivedCharacter,
    PerceivedContainer,
    PerceivedEquipment,
    PerceivedItem,
    ProposedAction,
    PerceivedLandmark,
)
from world_simulation_engine.service import DatabaseService, EmbedService
from world_simulation_engine.service.database.memory_store import MemoryRecallRecord
from ..prompt_loader import PromptLoader
from .memory_retriever import MemoryRetrievalDiagnostics, MemoryRetriever, RecalledMemory
from .simulator_component import SimulatorComponent
from .perspective_resolver import PerspectiveResolver


class RecalledIntent(BaseModel):
    intent: Intent
    recall_sources: list[str] = Field(default_factory=list)
    similarity: Optional[float] = None


class CharacterPerspective(BaseModel):
    actor: Character = Field(
        ...,
        description="The character that the perspective is in"
    )
    world_time: datetime = Field(
        ...,
        description="The current time in the simulation"
    )
    location: Location = Field(
        ...,
        description="The current location the character is in"
    )

    inventory: list[InventoryStack] = Field(
        default_factory=list,
        description="The items this character holds"
    )
    equipment: list[InventoryEquipment] = Field(
        default_factory=list,
        description="The equipment this character is wearing or holding"
    )
    user_input: str = Field(
        "",
        description="The latest user input that triggered this action proposal"
    )

    intents: list[RecalledIntent] = Field(default_factory=list)

    perceived_characters: list[PerceivedCharacter] = Field(default_factory=list)
    perceived_background_characters: list[PerceivedBackgroundCharacter] = Field(default_factory=list)
    perceived_items: list[PerceivedItem] = Field(default_factory=list)
    perceived_equipment: list[PerceivedEquipment] = Field(default_factory=list)
    perceived_containers: list[PerceivedContainer] = Field(default_factory=list)
    perceived_landmarks: list[PerceivedLandmark] = Field(default_factory=list)

    relevant_memories: list[RecalledMemory] = Field(default_factory=list)
    memory_retrieval: MemoryRetrievalDiagnostics | None = None
    relationships: list[EntityRelationship] = Field(
        default_factory=list,
        description="Objective facts and subjective relationships available to this actor.",
    )
    subjective_claims: list[SubjectiveEntityClaim] = Field(default_factory=list)
    emotion: EmotionVector | None = None

    recent_events: list[str] = Field(
        default_factory=list,
        description="Immediately preceding events from this actor's perspective."
    )
    hard_constraints: list[str] = Field(
        default_factory=list,
        description="Rules the proposal must not violate."
    )
    soft_constraints: list[str] = Field(
        default_factory=list,
        description="Preferences, norms, personality tendencies, uncertainty, tone."
    )


class CharacterReactionContext(BaseModel):
    perspective: CharacterPerspective = Field(
        ...,
        description="The reacting actor's ordinary action-proposal perspective."
    )
    coordination_result: SceneCoordinationResult = Field(
        ...,
        description="The latest coordination result that requires this reaction."
    )
    action_plans: list[CharacterActionPlan] = Field(
        default_factory=list,
        description="The action plans immediately before the coordination problem, including other actors."
    )
    reaction_history: list[ReactionHistoryEntry] = Field(
        default_factory=list,
        description="Previously attempted reactions in this scene."
    )


class SpeechRepairContext(BaseModel):
    perspective: CharacterPerspective
    proposal: ActionProposal
    action: ProposedAction
    reasoning_summary: str
    memory_updates_suggested: list[str] = Field(default_factory=list)


class CharacterSimulator(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.CHARACTER_SIMULATOR

    def __init__(self,
                 database: DatabaseService,
                 langfuse_handler: CallbackHandler | None,
                 prompt_loader: PromptLoader | None = None,
                 ):
        super().__init__(
            database=database,
            prompt_loader=prompt_loader,
        )

        self._perspective_resolver = PerspectiveResolver(
            database=database,
            langfuse_handler=langfuse_handler
        )
        self._memory_retriever = MemoryRetriever(database)
        self._last_memory_retrieval_diagnostics: MemoryRetrievalDiagnostics | None = None

    async def _prepare_embed_service(self,
                                     simulation_id: str,
                                     ) -> EmbedService:
        embed_config = await self._db.config.get_embed_by_source(
            source_id=simulation_id,
            component=self.COMPONENT_TYPE,
        )
        if not embed_config:
            raise ValueError(
                f"Simulation {simulation_id} does not have an embed model configured for character simulation"
            )

        connection_config = await self._db.config.get_connection_by_embed_source(
            source_id=embed_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Embed model config {embed_config.id} does not have a connection configured"
            )

        return EmbedService(
            model_config=embed_config,
            connection_config=connection_config,
        )

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0

        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot_product / (left_norm * right_norm)

    @staticmethod
    def _decayed_confidence(record: MemoryRecallRecord,
                            current_time: datetime,
                            half_life_days: float = 30.0,
                            ) -> float:
        elapsed = current_time - record.event_ending_time
        elapsed_days = max(elapsed.total_seconds() / 86400, 0)
        decay_multiplier = exp(-log(2) * elapsed_days / half_life_days)

        return max(min(record.confidence * decay_multiplier, 1), 0)

    @staticmethod
    def _recalled_memory_from_record(record: MemoryRecallRecord,
                                     current_time: datetime,
                                     recall_sources: list[str],
                                     similarity: float | None = None,
                                     ) -> RecalledMemory:
        return RecalledMemory(
            memory=record.memory,
            event=record.event,
            event_id=record.event.id,
            event_name=record.event.name,
            event_summary=record.event.summary,
            event_ending_time=record.event_ending_time,
            support_type=record.support_type,
            confidence=record.confidence,
            decayed_confidence=CharacterSimulator._decayed_confidence(record, current_time),
            salience=record.salience,
            behavioural_relevance=record.behavioural_relevance,
            stance=record.stance,
            recall_sources=recall_sources,
            similarity=similarity,
        )

    async def _recall_memory(self,
                             simulation: Simulation,
                             character: Character,
                             user_input: str,
                             entity_ids: list[str] | None = None,
                             ) -> list[RecalledMemory]:
        query_embedding = None
        embed_service = None
        if user_input.strip():
            embed_service = await self._prepare_embed_service(simulation.id)
            query_embedding = (await embed_service.embed_texts([user_input]))[0]
        result = await self._memory_retriever.retrieve(
            simulation_id=simulation.id,
            character_id=character.id,
            current_time=simulation.current_time,
            entity_ids=entity_ids or [],
            query_embedding=query_embedding,
            embed_service=embed_service,
        )
        self._last_memory_retrieval_diagnostics = result.diagnostics
        return result.memories

    async def _recall_intents(self,
                              simulation: Simulation,
                              character: Character,
                              user_input: str,
                              ) -> list[RecalledIntent]:
        deadline_delta = timedelta(hours=24)
        priority_threshold = 0.7
        urgency_threshold = 0.7

        recalled_by_id = {
            intent.id: RecalledIntent(
                intent=intent,
                recall_sources=["active_filter"],
            )
            for intent in await self._db.intent.get_active_intent_candidates(
                character_id=character.id,
                current_time=simulation.current_time,
                deadline_delta=deadline_delta,
                priority_threshold=priority_threshold,
                urgency_threshold=urgency_threshold,
            )
        }

        if user_input.strip():
            embed_service = await self._prepare_embed_service(simulation.id)
            query_embedding = (await embed_service.embed_texts([user_input]))[0]
            scored_intents = [
                (
                    intent,
                    self._cosine_similarity(query_embedding, intent.embedding or []),
                )
                for intent in await self._db.intent.get_character_intents(character.id)
            ]
            scored_intents.sort(key=lambda item: item[1], reverse=True)

            for intent, similarity in scored_intents[:10]:
                if similarity <= 0:
                    continue

                if intent.id in recalled_by_id:
                    recalled = recalled_by_id[intent.id]
                    recalled.similarity = similarity
                    if "embedding_match" not in recalled.recall_sources:
                        recalled.recall_sources.append("embedding_match")
                else:
                    recalled_by_id[intent.id] = RecalledIntent(
                        intent=intent,
                        recall_sources=["embedding_match"],
                        similarity=similarity,
                    )

        return list(recalled_by_id.values())

    async def _build_perspective(self,
                                 world: World,
                                 simulation: Simulation,
                                 character: Character,
                                 user_input: str,
                                 thread_id: str | None = None,
                                 ) -> CharacterPerspective:
        location = await self._db.location.get_location_by_character(character.id)
        if not location:
            raise ValueError(f"Character {character.id} is not in a location")

        inventory = await self._db.item.get_inventory(character.id)
        equipment = await self._db.equipment.get_equipment_inventory(character.id)

        perspective = await self._perspective_resolver.resolve_perceived_entities(
            world_id=world.id,
            simulation_id=simulation.id,
            character_id=character.id,
            thread_id=thread_id,
        )
        emotion = await self._effective_emotion(
            simulation=simulation,
            character_id=character.id,
        )
        intents = self._apply_emotion_intent_bias(
            await self._recall_intents(
                simulation=simulation,
                character=character,
                user_input=user_input,
            ),
            emotion,
        )
        relationship_entity_ids = {
            character.id,
            location.id,
            *(entry.item_id for entry in inventory),
            *(entry.stack_id for entry in inventory),
            *(entry.id for entry in equipment),
            *(entry.character.id for entry in perspective.perceived_characters),
            *(entry.item.id for entry in perspective.perceived_items),
            *(entry.stack.id for entry in perspective.perceived_items),
            *(entry.equipment.id for entry in perspective.perceived_equipment),
            *(entry.container.id for entry in perspective.perceived_containers),
            *(entry.landmark.id for entry in perspective.perceived_landmarks),
        }
        relevant_memories = await self._recall_memory(
            simulation=simulation,
            character=character,
            user_input=user_input,
            entity_ids=sorted(relationship_entity_ids),
        )
        relationships = await self._db.entity_relationship.list_relationships(
            scope_id=simulation.id,
            perspective_character_id=character.id,
            entity_ids=list(relationship_entity_ids),
        )
        subjective_claims = await self._subjective_claims(
            simulation_id=simulation.id, observer_character_id=character.id,
            subject_ids=list(relationship_entity_ids),
        )

        return CharacterPerspective(
            actor=character,
            world_time=simulation.current_time,
            location=location,
            inventory=inventory,
            equipment=equipment,
            user_input=user_input,
            intents=intents,
            perceived_characters=perspective.perceived_characters,
            perceived_background_characters=perspective.perceived_background_characters,
            perceived_items=perspective.perceived_items,
            perceived_equipment=perspective.perceived_equipment,
            perceived_containers=perspective.perceived_containers,
            perceived_landmarks=perspective.perceived_landmarks,
            relevant_memories=relevant_memories,
            memory_retrieval=self._last_memory_retrieval_diagnostics,
            relationships=relationships,
            subjective_claims=subjective_claims,
            emotion=emotion,
        )

    @staticmethod
    def _apply_emotion_intent_bias(
            intents: list[RecalledIntent],
            emotion: EmotionVector | None,
    ) -> list[RecalledIntent]:
        """Apply a small contextual priority bias without mutating canonical intents."""
        if not emotion:
            return intents
        activation = abs(emotion.arousal)
        distress = max(-emotion.valence, 0)
        for recalled in intents:
            if recalled.intent.type not in {IntentType.NEED, IntentType.REACTION}:
                continue
            bias = min(activation * 0.1 + distress * 0.05, 0.15)
            recalled.intent = recalled.intent.model_copy(update={
                "priority": min(recalled.intent.priority + bias, 1),
                "urgency": min(recalled.intent.urgency + bias, 1),
            })
            if bias > 0 and "emotion_bias" not in recalled.recall_sources:
                recalled.recall_sources.append("emotion_bias")
        return intents

    async def propose_actions(self,
                              world_id: str,
                              simulation_id: str,
                              character_id: str,
                              user_input: str,
                              thread_id: str | None = None,
                              ) -> ActionProposal:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        character = await self._db.character.get_character(character_id)
        if not character:
            raise ValueError(f"Character {character_id} not found in database")

        perspective = await self._build_perspective(
            world=world,
            simulation=simulation,
            character=character,
            user_input=user_input,
            thread_id=thread_id,
        )

        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="action_proposal",
        )
        prompt = self._with_relationship_context(prompt)
        if perspective.subjective_claims:
            prompt = self._with_subjective_claim_context(prompt)
        if perspective.emotion is not None:
            prompt = self._with_emotion_context(prompt)

        llm = await self._prepare_llm_service(
            simulation_id=simulation_id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ActionProposal,
            messages=prompt,
            data=perspective.model_dump(),
            repair_instruction=(
                "Return a valid ActionProposal. If any action type is speak, "
                "that action utterance must be the exact line the actor says and must not be null. "
                "utterance may be null only for non-speech actions where the character acts without speaking."
            ),
            run_name="character.propose_actions",
        )

        return await self._ensure_speak_actions_have_utterance(
            proposal=result,
            perspective=perspective,
            simulation_id=simulation_id,
            language=world.language,
            llm=llm,
            run_name="character.repair_proposed_speech",
        )

    async def _repair_missing_speech(
            self,
            *,
            proposal: ActionProposal,
            perspective: CharacterPerspective,
            simulation_id: str | None = None,
            language: SupportedLanguage,
            action: ProposedAction,
            llm,
            run_name: str,
    ) -> str:
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id or "",
            language=language,
            prompt_name="speech_repair",
        )
        try:
            raw_utterance = await llm.invoke_text(
                messages=prompt,
                data=SpeechRepairContext(
                    perspective=perspective,
                    proposal=proposal,
                    action=action,
                    reasoning_summary=proposal.reasoning_summary,
                    memory_updates_suggested=proposal.memory_updates_suggested,
                ).model_dump(),
                run_name=run_name,
            )
            utterance = self._sanitize_repaired_utterance(raw_utterance)
            if utterance:
                return utterance
        except Exception:
            pass

        return self._fallback_speech_utterance(
            proposal=proposal,
            action=action,
            actor_name=perspective.actor.name,
        )

    @staticmethod
    def _sanitize_repaired_utterance(value: str) -> str:
        utterance = value.strip()
        for prefix in ("utterance:", "speech:", "line:", "dialogue:", "dialog:"):
            if utterance.lower().startswith(prefix):
                utterance = utterance[len(prefix):].strip()

        if utterance.startswith("{") or utterance.startswith("["):
            return ""

        if (
                len(utterance) >= 2
                and utterance[0] == utterance[-1]
                and utterance[0] in {'"', "'"}
        ):
            utterance = utterance[1:-1].strip()

        lines = [
            line.strip()
            for line in utterance.splitlines()
            if line.strip()
        ]
        if len(lines) == 1:
            utterance = lines[0]

        return utterance

    @staticmethod
    def _fallback_speech_utterance(
            *,
            proposal: ActionProposal,
            action: ProposedAction,
            actor_name: str | None = None,
    ) -> str:
        candidates = [
            *proposal.memory_updates_suggested,
            *action.expected_effects,
            proposal.reasoning_summary,
            action.label.replace("_", " "),
        ]
        for candidate in candidates:
            cleaned = " ".join(str(candidate).strip().split())
            if not cleaned:
                continue
            if actor_name:
                cleaned = cleaned.removeprefix(f"{actor_name} ")
            for prefix in ("confirms ", "answers ", "states ", "says ", "publicly clarifies "):
                cleaned = cleaned.removeprefix(prefix).removeprefix(prefix.capitalize())
            if not cleaned.endswith((".", "!", "?")):
                cleaned = f"{cleaned}."
            return cleaned

        return "I have something to say."

    async def _ensure_speak_actions_have_utterance(
            self,
            *,
            proposal: ActionProposal,
            perspective: CharacterPerspective,
            simulation_id: str | None = None,
            language: SupportedLanguage,
            llm,
            run_name: str,
    ) -> ActionProposal:
        async def repair_sequence(sequence: list[ProposedAction], sequence_name: str) -> tuple[list[ProposedAction], bool]:
            repaired = []
            changed = False
            for action_index, action in enumerate(sequence):
                if action.type == ActionType.SPEAK and not (action.utterance or "").strip():
                    changed = True
                    repaired.append(
                        action.model_copy(
                            update={
                                "utterance": await self._repair_missing_speech(
                                    proposal=proposal,
                                    perspective=perspective,
                                    simulation_id=simulation_id,
                                    language=language,
                                    action=action,
                                    llm=llm,
                                    run_name=f"{run_name}_{sequence_name}_{action_index}",
                                )
                            }
                        )
                    )
                else:
                    repaired.append(action)

            return repaired, changed

        actions, actions_changed = await repair_sequence(proposal.actions, "primary")

        backup_proposals = []
        backups_changed = False
        for proposal_index, backup in enumerate(proposal.backup_proposals):
            repaired_backup, backup_changed = await repair_sequence(backup, f"backup_{proposal_index}")
            backup_proposals.append(repaired_backup)
            backups_changed = backups_changed or backup_changed

        if not actions_changed and not backups_changed:
            return proposal

        return proposal.model_copy(
            update={
                "actions": actions,
                "backup_proposals": backup_proposals,
            }
        )

    async def propose_reaction(self,
                               world_id: str,
                               simulation_id: str,
                               character_id: str,
                               coordination_result: SceneCoordinationResult,
                               action_plans: list[CharacterActionPlan],
                               reaction_history: list[ReactionHistoryEntry] | None = None,
                               user_input: str = "",
                               thread_id: str | None = None,
                               ) -> ActionProposal:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        character = await self._db.character.get_character(character_id)
        if not character:
            raise ValueError(f"Character {character_id} not found in database")

        perspective = await self._build_perspective(
            world=world,
            simulation=simulation,
            character=character,
            user_input=user_input,
            thread_id=thread_id,
        )
        context = CharacterReactionContext(
            perspective=perspective,
            coordination_result=coordination_result,
            action_plans=action_plans,
            reaction_history=reaction_history or [],
        )

        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="action_reaction",
        )
        prompt = self._with_relationship_context(
            prompt,
            nested_under_perspective=True,
        )
        if perspective.subjective_claims:
            prompt = self._with_subjective_claim_context(prompt, nested_under_perspective=True)
        if perspective.emotion is not None:
            prompt = self._with_emotion_context(
                prompt,
                expression="perspective.emotion",
            )

        llm = await self._prepare_llm_service(
            simulation_id=simulation_id,
        )

        result = await llm.invoke_structured_with_repair(
            output_model=ActionProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return a valid ActionProposal for the reacting character only. "
                "Do not narrate, coordinate, or decide final outcomes. If any action type is speak, "
                "that action utterance must be the exact line the actor says and must not be null. "
                "utterance may be null only for non-speech actions where the character acts without speaking."
            ),
            run_name="character.propose_reaction",
        )

        return await self._ensure_speak_actions_have_utterance(
            proposal=result,
            perspective=perspective,
            simulation_id=simulation_id,
            language=world.language,
            llm=llm,
            run_name="character.repair_reaction_speech",
        )
