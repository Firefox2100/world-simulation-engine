"""Stage 0 of the SillyTavern import pipeline: deterministic normalization, no LLM/DB involved.

Turns a parsed `SillyTavernCardV3` into a `PreprocessedCard`: macro-normalized free text, only the
single primary opening (alternate_greetings are out of scope for this iteration - a later UI will
let the user pick which opening, and which lorebook entries, to feed the converter at all), enabled
lorebook entries stripped down to the fields later stages actually need, and `extensions` triaged
into "definitely irrelevant SillyTavern/site runtime metadata" (discarded) versus "might be a
variable schema" (forwarded, unparsed, for a later LLM pass to read).
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from world_simulation_engine.model.silly_tavern import SillyTavernCardV3


# {{char}}/<BOT> and {{user}}/<USER> are SillyTavern's own macro syntax for "this character" and
# "the player persona". They're normalized here into this system's own entity-placeholder syntax
# (see misc/placeholder.py) addressed at stable slugs, not real ids - no character has been created
# yet at this stage. A later stage rewrites 'self'/'user' to the real minted character ids once
# reconstruction assigns them, so the final stored text stays a live reference (resolved at read
# time against the current roster) rather than a name baked in at import time.
_CHAR_MACRO_PATTERN = re.compile(r"\{\{\s*char\s*\}\}|<BOT>", re.IGNORECASE)
_USER_MACRO_PATTERN = re.compile(r"\{\{\s*user\s*\}\}|<USER>", re.IGNORECASE)

_CHAR_PLACEHOLDER = "{{ character['self'].name }}"
_USER_PLACEHOLDER = "{{ character['user'].name }}"

# Substrings that identify a `tavern_helper.scripts` entry as (probably) a Zod-style MVU variable
# schema definition, rather than an unrelated automation/runtime script. Deliberately loose - a
# false positive here just means an irrelevant script gets forwarded to a later LLM pass instead of
# discarded, which is cheap; a false negative silently drops a real variable schema, which is not.
_VARIABLE_SCHEMA_MARKERS = (
    "z.object(",
    "z.string(",
    "z.number(",
    "z.coerce.number(",
    "z.enum(",
    "z.record(",
    "z.array(",
    ".prefault(",
    ".describe(",
    "registermvuschema",
)

# extensions keys that are always pure SillyTavern/site-runtime metadata with no content this
# system could use - UI slider values, injection-depth tuning, site upload ids, and the like.
_ALWAYS_DISCARDED_EXTENSION_KEYS = {
    "talkativeness",
    "fav",
    "world",
    "depth_prompt",
    "aicc-site",
    "aicc-site-id",
    "regex_scripts",
}


class VariableScriptCandidate(BaseModel):
    """A script or lorebook entry that might define tracked-variable schema, unparsed.

    "Might" because detection here is a cheap substring heuristic (see `_VARIABLE_SCHEMA_MARKERS`);
    an actual variable-schema-reading LLM pass decides what, if anything, is really in it.
    """

    source: str = Field(description="Where this candidate came from, e.g. 'tavern_helper_script'")
    name: str | None = None
    content: str


class PreprocessedLorebookEntry(BaseModel):
    """One enabled lorebook entry, reduced to what a later classification/extraction pass needs.

    SillyTavern's injection-timing/matching mechanics (position, selective, probability, depth,
    sticky, ...) control how/when the entry gets spliced into a live chat prompt - meaningless for
    a one-time extraction pass over the whole card, so none of it is carried forward.
    """

    source_id: str = Field(description="The original card_v3 entry id/comment, kept for traceability only")
    name: str | None = None
    keys: list[str] = Field(default_factory=list)
    content: str
    constant: bool = False


class PreprocessedCard(BaseModel):
    """Deterministic stage-0 output: macro-normalized text, single opening, triaged extensions."""

    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_message: str = ""
    example_dialogue: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    post_history_instructions: str = ""
    creator_notes: str = ""
    tags: list[str] = Field(default_factory=list)

    lorebook_entries: list[PreprocessedLorebookEntry] = Field(default_factory=list)
    variable_schema_candidates: list[VariableScriptCandidate] = Field(default_factory=list)

    discarded: list[str] = Field(
        default_factory=list,
        description="Human-readable log of what was dropped and why, for the conversion report.",
    )


class CardPreprocessor:
    """Stage 0: deterministic normalization. No LLM, no DB - a pure function over the parsed card."""

    @staticmethod
    def _normalize_macros(text: str) -> str:
        if not text:
            return text
        text = _CHAR_MACRO_PATTERN.sub(_CHAR_PLACEHOLDER, text)
        text = _USER_MACRO_PATTERN.sub(_USER_PLACEHOLDER, text)
        return text

    @classmethod
    def _split_example_dialogue(cls, mes_example: str) -> list[str]:
        if not mes_example.strip():
            return []
        # SillyTavern separates independent example exchanges with a literal "<START>" line.
        segments = [segment.strip() for segment in mes_example.split("<START>")]
        return [cls._normalize_macros(segment) for segment in segments if segment]

    @classmethod
    def _preprocess_lorebook_entries(cls, card: SillyTavernCardV3) -> list[PreprocessedLorebookEntry]:
        book = card.data.character_book
        if not book:
            return []

        entries = []
        for entry in book.entries:
            if not entry.enabled:
                continue
            source_id = (
                str(entry.id) if entry.id is not None
                else entry.comment or entry.name or str(len(entries))
            )
            entries.append(PreprocessedLorebookEntry(
                source_id=source_id,
                name=entry.name or entry.comment,
                keys=list(entry.keys),
                content=cls._normalize_macros(entry.content),
                constant=entry.constant,
            ))
        return entries

    @classmethod
    def _looks_like_variable_schema(cls, content: str) -> bool:
        lowered = content.lower()
        return any(marker in lowered for marker in _VARIABLE_SCHEMA_MARKERS)

    @classmethod
    def _triage_extensions(cls, extensions: dict[str, Any]) -> tuple[list[VariableScriptCandidate], list[str]]:
        candidates: list[VariableScriptCandidate] = []
        discarded: list[str] = []

        always_discarded_present = sorted(_ALWAYS_DISCARDED_EXTENSION_KEYS & extensions.keys())
        if always_discarded_present:
            discarded.append(
                "discarded SillyTavern/site runtime metadata: " + ", ".join(always_discarded_present)
            )

        scripts = extensions.get("tavern_helper", {})
        scripts = scripts.get("scripts", []) if isinstance(scripts, dict) else []
        forwarded_script_names = []
        discarded_script_names = []
        for script in scripts:
            if not isinstance(script, dict) or not script.get("enabled", True):
                continue
            content = script.get("content") or ""
            name = script.get("name")
            if cls._looks_like_variable_schema(content):
                candidates.append(VariableScriptCandidate(
                    source="tavern_helper_script",
                    name=name,
                    content=content,
                ))
                forwarded_script_names.append(name or "(unnamed)")
            else:
                discarded_script_names.append(name or "(unnamed)")
        if forwarded_script_names:
            discarded.append(
                "forwarded tavern_helper scripts as variable-schema candidates: "
                + ", ".join(forwarded_script_names)
            )
        if discarded_script_names:
            discarded.append(
                "discarded tavern_helper scripts (not variable schema): " + ", ".join(discarded_script_names)
            )

        known_keys = _ALWAYS_DISCARDED_EXTENSION_KEYS | {"tavern_helper"}
        unrecognized = sorted(extensions.keys() - known_keys)
        if unrecognized:
            discarded.append("discarded unrecognized extension keys: " + ", ".join(unrecognized))

        return candidates, discarded

    @classmethod
    def preprocess(cls, card: SillyTavernCardV3) -> PreprocessedCard:
        data = card.data
        variable_schema_candidates, discarded = cls._triage_extensions(data.extensions)

        if data.alternate_greetings:
            discarded.append(
                f"ignored {len(data.alternate_greetings)} alternate greeting(s): only the "
                "primary first_mes is used this iteration"
            )
        if data.group_only_greetings:
            discarded.append(
                f"ignored {len(data.group_only_greetings)} group-only greeting(s)"
            )

        return PreprocessedCard(
            name=data.name,
            description=cls._normalize_macros(data.description),
            personality=cls._normalize_macros(data.personality),
            scenario=cls._normalize_macros(data.scenario),
            first_message=cls._normalize_macros(data.first_mes),
            example_dialogue=cls._split_example_dialogue(data.mes_example),
            system_prompt=cls._normalize_macros(data.system_prompt),
            post_history_instructions=cls._normalize_macros(data.post_history_instructions),
            creator_notes=cls._normalize_macros(data.creator_notes),
            tags=list(data.tags),
            lorebook_entries=cls._preprocess_lorebook_entries(card),
            variable_schema_candidates=variable_schema_candidates,
            discarded=discarded,
        )
