"""Stage 2 (variable-schema branch, conditional) of the SillyTavern import pipeline: turn a card's
tracked-variable schema (SillyTavern MVU/Zod scripts, or a human-readable restatement of one) into
candidate `VariableDefinition`s (§4 - `EntityVariableSet`'s per-owner variable list).

Only meaningful for cards like card 03, which embeds a real Zod schema (`extensions.tavern_helper.
scripts`, forwarded by `CardPreprocessor` as `PreprocessedCard.variable_schema_candidates`) and/or a
`variable_meta`-bucket lorebook entry restating the same schema in prose. One call per source - a
script candidate or a `variable_meta` item - using the same prompt/schema for both, since both
describe the same kind of thing (a named, typed, defaulted, described tracked variable) just in
different notations. Explicitly best-effort: this is read comprehension over a scripting-language
snippet, not a real JS/Zod parser, so output should be treated as low-confidence by the conversion
report (stage 3), never auto-committed as authoritative. Cross-source deduplication (the same
variable named in both the script and its human-readable restatement) is deferred to stage 3
(`WorldAssembler`), which has visibility across every source at once; this stage just tags each
candidate with its own `source_item_ids` for that later reconciliation.

A schema/rules source describes tracked *fields* in the abstract (e.g. "affection, mood, outfit -
one set per character") and by itself rarely names a real character per variable, so its
`owner_hint` frequently can't be resolved by `WorldAssembler` and the variable gets dropped (real
bug found on an MVU-style card: every variable's `owner_hint` came back as a copy of the schema's
own "owning character" column-header label instead of a real name, because that's all the schema
text itself said - schema entries don't carry per-instance identity). The actual *initial values*, correctly scoped to
real character names, conventionally live in the card's **opening message** instead (an
`<UpdateVariable><initvar>...</initvar></UpdateVariable>`-wrapped, YAML-like block keyed by
character name), since lorebook/world-book entries aren't dynamically edited during play. `extract`
therefore also fans out a second kind of call - `_extract_first_message_source`, gated by a cheap
marker check so cards without any such block never spend an LLM call on it - over
`PreprocessedCard.first_message`, using a dedicated prompt that's told explicitly to key
`owner_hint` off the block's real top-level names. Ordered after the schema sources in `extract`, so
if a schema source's `owner_hint` *does* happen to resolve to the same (owner, name) pair, its
richer `description`/bounds win over the plainer first-message-derived candidate.
"""

import functools

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage
from world_simulation_engine.model.variable import VariableValueType

from .card_preprocessor import PreprocessedCard
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .initial_value_block import has_initial_value_block
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent

_MAX_VARIABLES_PER_SOURCE = 60
_MAX_ALLOWED_VALUES = 10


class VariableFieldCandidate(BaseModel):
    """One inferred variable - field shape mirrors `VariableDefinition`, minus `value` (no live
    value exists yet at import time - `default_value` doubles as the initial value at stage 3)."""

    model_config = ConfigDict(extra="forbid")

    owner_hint: str = Field(
        description="Best-effort free text for who/what this variable belongs to - 'self' for the "
                    "card's own protagonist, 'world' for global/environment state, or another "
                    "character's name copied from context if clearly scoped to them.",
    )
    name: str
    value_type: VariableValueType
    default_value: str | int | float | bool
    description: str = Field(
        description="What this variable means and how it should change over time - becomes the "
                    "update rule shown to the LLM that later proposes changes to it.",
    )
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: list[str] = Field(default_factory=list, max_length=_MAX_ALLOWED_VALUES)


class VariableSchemaCandidates(BaseModel):
    """Structured output for one source (script or human-readable restatement)."""

    model_config = ConfigDict(extra="forbid")

    variables: list[VariableFieldCandidate] = Field(
        default_factory=list, max_length=_MAX_VARIABLES_PER_SOURCE,
    )


class ExtractedVariable(BaseModel):
    owner_hint: str
    name: str
    value_type: VariableValueType
    default_value: str | int | float | bool
    description: str
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)


class VariableSchemaExtraction(BaseModel):
    variables: list[ExtractedVariable] = Field(default_factory=list)


class VariableSchemaExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_source(
            self, *, label: str, content: str, language: SupportedLanguage,
    ) -> VariableSchemaCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_variable_schema_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=VariableSchemaCandidates,
            messages=prompt,
            data={"label": label, "content": content},
            repair_instruction=(
                "Return a single VariableSchemaCandidates JSON object only, with at most "
                f"{_MAX_VARIABLES_PER_SOURCE} entries. Only include a variable you can clearly "
                "identify a name and type for - an empty list is correct if nothing in the "
                "content is a real tracked variable."
            ),
            run_name="variable_schema_extractor.extract_source",
        )

    async def _extract_first_message_source(
            self, *, content: str, language: SupportedLanguage,
    ) -> VariableSchemaCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_variable_initial_value_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=VariableSchemaCandidates,
            messages=prompt,
            data={"content": content},
            repair_instruction=(
                "Return a single VariableSchemaCandidates JSON object only, with at most "
                f"{_MAX_VARIABLES_PER_SOURCE} entries. Only include a variable if the opening "
                "message actually has a grouped-by-character block of concrete initial values; an "
                "empty list is correct otherwise. owner_hint must be the real top-level key text "
                "from that block, never a field label."
            ),
            run_name="variable_schema_extractor.extract_first_message",
        )

    @staticmethod
    def _collect_sources(
            card: PreprocessedCard, classification: LorebookClassification,
    ) -> list[tuple[str, str, str]]:
        content_by_id = content_by_item_id(card)
        sources = [
            (f"script:{index}", candidate.name or candidate.source, candidate.content)
            for index, candidate in enumerate(card.variable_schema_candidates)
        ]
        sources += [
            (classified.item_id, classified.item_id, content_by_id[classified.item_id])
            for classified in classification.by_bucket(LorebookItemBucket.VARIABLE_META)
            if classified.item_id in content_by_id
        ]
        return sources

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            *,
            language: SupportedLanguage,
    ) -> VariableSchemaExtraction:
        sources = self._collect_sources(card, classification)
        has_initial_values = has_initial_value_block(card.first_message)
        if not sources and not has_initial_values:
            return VariableSchemaExtraction()

        calls = [
            functools.partial(
                self._extract_source, label=label, content=content, language=language,
            )
            for _, label, content in sources
        ]
        source_ids = [item_id for item_id, _, _ in sources]
        if has_initial_values:
            calls.append(
                functools.partial(
                    self._extract_first_message_source,
                    content=card.first_message,
                    language=language,
                ),
            )
            source_ids.append("first_message")

        results = await run_fan_out(
            self._fan_out_graph,
            calls,
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="variable_schema_extractor.extract",
        )
        variables = [
            ExtractedVariable(source_item_ids=[item_id], **candidate.model_dump())
            for item_id, batch in zip(source_ids, results)
            for candidate in batch.variables
        ]
        return VariableSchemaExtraction(variables=variables)
