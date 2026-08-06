"""Extract positive, observer-owned beliefs from memories already assigned to that observer."""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.model import SubjectiveClaimCategory, SubjectiveClaimStance

from .character_extractor import CharacterExtraction
from .equipment_extractor import EquipmentExtraction
from .fan_out import build_fan_out_graph, run_fan_out
from .item_extractor import ItemExtraction
from .location_extractor import LocationExtraction
from .narrative_extractor import NarrativeExtraction
from .pipeline_component import SillyTavernPipelineComponent

_MAX_CLAIMS_PER_OBSERVER = 12


class PrivateKnowledgeClaimCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    category: SubjectiveClaimCategory
    statement: str = Field(min_length=1, max_length=500)
    stance: SubjectiveClaimStance
    confidence: float = Field(ge=0, le=1)
    supporting_memory_ids: list[str] = Field(min_length=1, max_length=4)


class PrivateKnowledgeClaimCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[PrivateKnowledgeClaimCandidate] = Field(
        default_factory=list, max_length=_MAX_CLAIMS_PER_OBSERVER,
    )


class ExtractedPrivateKnowledgeClaim(PrivateKnowledgeClaimCandidate):
    id: str
    observer_character_id: str
    subject_type: str


class PrivateKnowledgeExtraction(BaseModel):
    claims: list[ExtractedPrivateKnowledgeClaim] = Field(default_factory=list)


class PrivateKnowledgeExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_PRIVATE_KNOWLEDGE_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_one(
            self, *, observer: dict, subjects: list[dict], memories: list[dict],
            language: SupportedLanguage,
    ) -> PrivateKnowledgeClaimCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_private_knowledge_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=PrivateKnowledgeClaimCandidates,
            messages=prompt,
            data={"observer": observer, "subjects": subjects, "memories": memories},
            repair_instruction=(
                "Return one PrivateKnowledgeClaimCandidates JSON object only, with at most "
                f"{_MAX_CLAIMS_PER_OBSERVER} claims. Every subject_id and supporting_memory_id must "
                "be copied exactly from the supplied lists. Encode only positive beliefs supported "
                "by those memories; claims: [] is correct when there is no supported belief."
            ),
            run_name="private_knowledge_extractor.extract_one",
        )

    async def extract(
            self, characters: CharacterExtraction, locations: LocationExtraction,
            items: ItemExtraction, equipment: EquipmentExtraction, narrative: NarrativeExtraction,
            *, language: SupportedLanguage,
    ) -> PrivateKnowledgeExtraction:
        subject_type_by_id = {
            **{character.id: "character" for character in characters.characters},
            **{location.id: "location" for location in locations.locations},
            **{item.id: "item" for item in items.items},
            **{item.id: "equipment" for item in equipment.equipment},
        }
        subjects = [
            {"id": character.id, "type": "character", "name": character.target_name}
            for character in characters.characters
        ] + [
            {"id": location.id, "type": "location", "name": location.name}
            for location in locations.locations
        ] + [
            {"id": item.id, "type": "item", "name": item.name}
            for item in items.items
        ] + [
            {"id": item.id, "type": "equipment", "name": item.name}
            for item in equipment.equipment
        ]

        calls = []
        observers = []
        memories_by_observer = []
        for character in characters.characters:
            memories = [
                {"id": memory.id, "summary": memory.summary, "keywords": memory.keywords}
                for memory in narrative.memories
                if character.id in memory.character_ids
            ]
            if not memories:
                continue
            observers.append(character)
            memories_by_observer.append(memories)
            calls.append(functools.partial(
                self._extract_one,
                observer={"id": character.id, "name": character.target_name},
                subjects=[subject for subject in subjects if subject["id"] != character.id],
                memories=memories,
                language=language,
            ))
        if not calls:
            return PrivateKnowledgeExtraction()

        results = await run_fan_out(
            self._fan_out_graph, calls,
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="private_knowledge_extractor.extract",
        )
        extracted = []
        for observer, memories, batch in zip(observers, memories_by_observer, results):
            allowed_memory_ids = {memory["id"] for memory in memories}
            seen = set()
            for claim in batch.claims:
                evidence = list(dict.fromkeys(claim.supporting_memory_ids))
                key = (claim.subject_id, claim.category, claim.statement.strip().casefold())
                if (
                    claim.subject_id not in subject_type_by_id
                    or claim.subject_id == observer.id
                    or not evidence
                    or not set(evidence).issubset(allowed_memory_ids)
                    or key in seen
                ):
                    continue
                seen.add(key)
                extracted.append(ExtractedPrivateKnowledgeClaim(
                    id=str(uuid4()), observer_character_id=observer.id,
                    subject_type=subject_type_by_id[claim.subject_id],
                    **claim.model_dump(exclude={"supporting_memory_ids"}),
                    supporting_memory_ids=evidence,
                ))
        return PrivateKnowledgeExtraction(claims=extracted)
