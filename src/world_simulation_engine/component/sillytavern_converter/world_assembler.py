"""Stage 3 of the SillyTavern import pipeline: deterministic, no LLM calls.

Takes every stage-2 output (`CharacterExtraction`, `LocationExtraction`, `WorldLoreExtraction`,
`NarrativeExtraction`, `IntentExtraction`, `VariableSchemaExtraction`) and resolves them into one
`WorldImportService`-shaped bundle (§7): a `world` row plus a `sections` dict of the exact same
`dict[str, list[dict]]` shape `WorldImportService._import_world_contents` already consumes. Every
stage-2 entity already carries a provisional id (§6.2), so this stage needs no new id-minting
scheme of its own - it only needs to decide what to do with references that never resolved to one
(drop, per every stage-2 extractor's own established "never fabricate" rule) and handle the handful
of cross-references stage 2 couldn't resolve on its own (variable `owner_hint`, the `{{char}}`/
`{{user}}` macro placeholders that survive verbatim in `first_message` - see `_rewrite_placeholders`
below for why only `first_message` actually needs this in practice).

Not covered by any stage-2 extractor, so always empty here: landmarks, items, item stacks,
equipment, containers, configs, prompts, workflows, media. `WorldImportService` already tolerates
empty sections (`for row in rows` over `[]` is a no-op), so this needs no special-casing.

`assemble()` also takes the pipeline's `language` directly (not derived from anything stage-2
produced) - `World.language` is required and nothing upstream carries it, since every stage-2
extractor already received `language` as its own call-site parameter rather than storing it.
"""

import re
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SupportedLanguage, TurnType
from world_simulation_engine.model.variable import VariableDefinition

from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .intent_extractor import IntentExtraction
from .location_extractor import LocationExtraction
from .name_resolution import resolve_name
from .narrative_extractor import NarrativeExtraction
from .variable_schema_extractor import VariableSchemaExtraction
from .world_lore_extractor import WorldLoreExtraction

_USER_STUB_NAME = "User"
_USER_STUB_DESCRIPTION = (
    "The user's persona for this imported card - not modeled as a full character. Created "
    "automatically so in-card {{user}} references resolve to a name instead of rendering empty; "
    "replace or reassign once a real user persona exists for this world."
)

# World.starting_time drives the simulation clock, so it must be a real datetime - never left
# null. Preference order: (1) an explicit "world"-scoped tracked variable that is clearly a
# date/time (real evidence: card 03's own MVU schema defines "当前日期"/"当前时间", exactly this
# kind of simulation clock, dropped everywhere else per §5's "world"-scope limitation but reused
# here for the one thing it's actually needed for); (2) otherwise default to the import time,
# flagged low-confidence in the report for the user to review - inferring a date from free-form
# prose is deliberately not attempted here (would need a dedicated LLM pass; not built this
# iteration given the explicit-variable signal already covers the strongest case).
_DATE_TERMS = (re.compile("日期"), re.compile(r"\bdate\b", re.IGNORECASE))
_TIME_TERMS = (re.compile("时间"), re.compile(r"\btime\b", re.IGNORECASE))
_CN_DATE_PATTERN = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
_ISO_DATE_PATTERN = re.compile(r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})")
_TIME_PATTERN = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})")


def _mentions_any(text: str, patterns) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _parse_date_value(value) -> tuple[int, int, int] | None:
    text = str(value)
    for pattern in (_CN_DATE_PATTERN, _ISO_DATE_PATTERN):
        match = pattern.search(text)
        if match:
            return int(match["year"]), int(match["month"]), int(match["day"])
    return None


def _parse_time_value(value) -> tuple[int, int] | None:
    match = _TIME_PATTERN.search(str(value))
    if match:
        return int(match["hour"]), int(match["minute"])
    return None


class ConversionReportEntry(BaseModel):
    message: str
    low_confidence: bool = False


class ConversionReport(BaseModel):
    entries: list[ConversionReportEntry] = Field(default_factory=list)

    def note(self, message: str, *, low_confidence: bool = False) -> None:
        self.entries.append(ConversionReportEntry(message=message, low_confidence=low_confidence))


class AssembledWorld(BaseModel):
    world: dict
    sections: dict[str, list]
    report: ConversionReport


def _rewrite_placeholders(text: str, *, self_id: str | None, user_id: str | None) -> str:
    """Rewrite stage-0's `character['self']`/`character['user']` macro-normalization slugs to real
    ids, so `misc/placeholder.py` resolves them against the live roster at read time (§5, stage 3).
    In practice, only `first_message` still carries this syntax verbatim by the time it reaches
    this stage - every stage-2 extractor is asked to write its own prose, not copy the source, so
    the literal slugs don't survive into any LLM-authored field (confirmed: none of the real
    evaluation output across all four cards contains the substring `character[` anywhere)."""
    if self_id:
        text = text.replace("character['self']", f"character['{self_id}']")
    if user_id:
        text = text.replace("character['user']", f"character['{user_id}']")
    return text


class WorldAssembler:
    def assemble(
            self,
            card: PreprocessedCard,
            *,
            language: SupportedLanguage,
            characters: CharacterExtraction,
            locations: LocationExtraction,
            world_lore: WorldLoreExtraction,
            narrative: NarrativeExtraction,
            intents: IntentExtraction,
            variables: VariableSchemaExtraction,
    ) -> AssembledWorld:
        report = ConversionReport()

        id_by_character_name = {
            character.target_name: character.id for character in characters.characters
        }
        self_id = resolve_name(card.name, id_by_character_name)
        if not self_id and characters.characters:
            report.note(
                f"Could not identify a single primary character for {{{{char}}}} placeholder "
                f"resolution (card name {card.name!r} matched none of the extracted characters) - "
                "character['self'] references, if any, will render empty until resolved manually.",
                low_confidence=True,
            )

        user_id, user_stub_row = self._resolve_user(characters)

        character_rows = [
            self._character_row(character, self_id=self_id, user_id=user_id)
            for character in characters.characters
        ]
        location_rows = [
            self._location_row(location, self_id=self_id, user_id=user_id)
            for location in locations.locations
        ]

        turn_id = str(uuid4())
        turn_row = self._turn_row(card, turn_id, self_id=self_id, user_id=user_id)

        event_rows = [
            self._event_row(event, turn_id, self_id=self_id, user_id=user_id)
            for event in narrative.events
        ]
        memory_rows = [
            self._memory_row(memory, self_id=self_id, user_id=user_id)
            for memory in narrative.memories
        ]
        intent_rows = [
            self._intent_row(intent, self_id=self_id, user_id=user_id)
            for intent in intents.intents
        ]
        relationship_rows = [
            self._relationship_row(relationship, self_id=self_id, user_id=user_id)
            for relationship in narrative.relationships
        ]

        location_id_by_name = {location.name: location.id for location in locations.locations}
        variable_rows = self._variable_set_rows(
            variables, id_by_character_name, location_id_by_name, user_id=user_id, report=report,
        )

        world_description = None
        if world_lore.description:
            world_description = _rewrite_placeholders(
                world_lore.description, self_id=self_id, user_id=user_id,
            )
        starting_time = self._resolve_starting_time(variables, report=report)
        world_row = {
            "name": card.name,
            "description": world_description,
            "starting_time": starting_time.isoformat(),
            "language": language,
        }

        sections: dict[str, list] = {
            "locations": location_rows,
            "landmarks": [],
            "characters": character_rows,
            "background_characters": [user_stub_row] if user_stub_row else [],
            "items": [],
            "item_stacks": [],
            "equipment": [],
            "containers": [],
            "turns": [turn_row],
            "events": event_rows,
            "memories": memory_rows,
            "intents": intent_rows,
            "entity_relationships": relationship_rows,
            "entity_variable_sets": variable_rows,
            "chat_configs": [],
            "embed_configs": [],
            "image_configs": [],
            "tts_configs": [],
            "prompts": [],
            "workflows": [],
            "media": [],
        }
        return AssembledWorld(world=world_row, sections=sections, report=report)

    @staticmethod
    def _resolve_starting_time(
            variables: VariableSchemaExtraction, *, report: ConversionReport,
    ) -> datetime:
        date_source: tuple[str, tuple[int, int, int]] | None = None
        time_source: tuple[str, tuple[int, int]] | None = None

        for variable in variables.variables:
            if variable.owner_hint.strip().lower() != "world":
                continue
            haystack = f"{variable.name} {variable.description}"

            if date_source is None and _mentions_any(haystack, _DATE_TERMS):
                parsed_date = _parse_date_value(variable.default_value)
                if parsed_date:
                    date_source = (variable.name, parsed_date)

            if time_source is None and _mentions_any(haystack, _TIME_TERMS):
                parsed_time = _parse_time_value(variable.default_value)
                if parsed_time:
                    time_source = (variable.name, parsed_time)

        if date_source:
            name, (year, month, day) = date_source
            hour, minute = time_source[1] if time_source else (0, 0)
            try:
                starting_time = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
            except ValueError:
                starting_time = None
            if starting_time:
                report.note(
                    f"Starting time inferred from the card's own {name!r} tracked variable: "
                    f"{starting_time.isoformat()}."
                )
                return starting_time

        report.note(
            "No explicit starting-time variable found on this card - defaulted to the import "
            "time; review and adjust before starting a simulation from this world.",
            low_confidence=True,
        )
        return datetime.now(timezone.utc)

    @staticmethod
    def _resolve_user(characters: CharacterExtraction) -> tuple[str | None, dict | None]:
        """`{{user}}` maps to whichever character the card itself flagged as user-controlled, if
        any; otherwise a minimal `BackgroundCharacter` stub is synthesized so the reference still
        resolves to *something* rather than rendering empty (real evidence: card 01's own
        `first_message` addresses `{{user}}` directly - "she turns toward {{user}}" - so leaving it
        unresolved would be a visible narrative gap, not just a theoretical one)."""
        for character in characters.characters:
            if character.result.user_controlled:
                return character.id, None

        stub_id = str(uuid4())
        stub_row = {"id": stub_id, "name": _USER_STUB_NAME, "description": _USER_STUB_DESCRIPTION}
        return stub_id, stub_row

    @staticmethod
    def _character_row(character, *, self_id: str | None, user_id: str | None) -> dict:
        result = character.result

        def rewrite(text: str) -> str:
            return _rewrite_placeholders(text, self_id=self_id, user_id=user_id)

        return {
            "id": character.id,
            "user_controlled": result.user_controlled,
            "name": result.name,
            "age": result.age,
            "gender": result.gender,
            "appearance": rewrite(result.appearance),
            "description": rewrite(result.description),
            "public_state": rewrite(result.public_state),
            "private_state": rewrite(result.private_state),
            "current_activity": {
                "name": result.current_activity, "started_at": None, "expected_end": None,
                "interruptible": True, "constraints": [],
            },
            "speech_style": rewrite(result.speech_style),
        }

    @staticmethod
    def _location_row(location, *, self_id: str | None, user_id: str | None) -> dict:
        description = _rewrite_placeholders(location.description, self_id=self_id, user_id=user_id)
        return {
            "id": location.id,
            "name": location.name,
            "description": description,
            "parent_location_id": location.parent_id,
        }

    @staticmethod
    def _turn_row(
            card: PreprocessedCard, turn_id: str, *, self_id: str | None, user_id: str | None,
    ) -> dict:
        content = (
            card.first_message.strip() or "(imported world - no opening message on the source card)"
        )
        return {
            "id": turn_id,
            "sequence": 0,
            "type": TurnType.SYSTEM_RESPONSE,
            "content": _rewrite_placeholders(content, self_id=self_id, user_id=user_id),
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _event_row(event, turn_id: str, *, self_id: str | None, user_id: str | None) -> dict:
        return {
            "id": event.id,
            "name": event.name,
            "summary": _rewrite_placeholders(event.summary, self_id=self_id, user_id=user_id),
            "turn_ids": [turn_id],
            "involved_characters": [
                {"character_id": character_id, "involvement": "participate"}
                for character_id in event.involved_character_ids
            ],
        }

    @staticmethod
    def _memory_row(memory, *, self_id: str | None, user_id: str | None) -> dict:
        return {
            "id": memory.id,
            "summary": _rewrite_placeholders(memory.summary, self_id=self_id, user_id=user_id),
            "keywords": memory.keywords,
            "embedding": None,
            "event_id": memory.event_id,
            "support_type": "direct",
            "character_links": [
                {
                    "character_id": character_id, "confidence": 1.0, "salience": "medium",
                    "stance": "remember", "behavioural_relevance": None,
                }
                for character_id in memory.character_ids
            ],
        }

    @staticmethod
    def _intent_row(intent, *, self_id: str | None, user_id: str | None) -> dict:
        def rewrite(text: str) -> str:
            return _rewrite_placeholders(text, self_id=self_id, user_id=user_id)

        return {
            "id": intent.id,
            "type": intent.type,
            "name": intent.name,
            "description": rewrite(intent.description),
            "keywords": [],
            "embedding": None,
            "priority": intent.priority,
            "urgency": intent.urgency,
            "status": intent.status,
            "desired_state": rewrite(intent.desired_state) if intent.desired_state else None,
            "success_conditions": [],
            "failure_conditions": [],
            "maintenance_conditions": [],
            "deadline": None,
            "horizon": intent.horizon,
            "constraints": [],
            "current_plan": [],
            "next_action_biases": [],
            "blockers": [],
            "open_threads": [],
            "character_id": intent.character_id,
            "created_by_event_id": None,
            "contributed_by_event_ids": [],
        }

    @staticmethod
    def _relationship_row(relationship, *, self_id: str | None, user_id: str | None) -> dict:
        return {
            "label": relationship.label,
            "public_description": _rewrite_placeholders(
                relationship.description, self_id=self_id, user_id=user_id,
            ),
            "private_description": None,
            "visibility": "objective",
            "perspective_character_id": None,
            "confidence": 1.0,
            "details": {"kind": "generic", "attributes": {}},
            "evidence_memory_ids": [],
            "source": {"type": "character", "id": relationship.source_character_id, "name": None},
            "target": {"type": "character", "id": relationship.target_character_id, "name": None},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_changed_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "active": True,
        }

    @staticmethod
    def _resolve_owner(
            hint: str,
            id_by_character_name: dict[str, str],
            location_id_by_name: dict[str, str],
            *,
            user_id: str,
    ) -> tuple[str, str] | None:
        # "self"/"自身" in a tracked-variable schema conventionally means the player's own stats
        # (health, inventory, skills - an MVU-style stat tracker), not the card's own named
        # protagonist: confirmed on a real card, where every "self"-hinted variable (姓名/年龄/
        # 生命值/随身物品/...) was clearly the player character's own state in a survival-RPG card
        # with no single named protagonist to match card.name against at all. `user_id` always
        # resolves (either a real user_controlled character or the synthesized stub - see
        # `_resolve_user`), so this branch never falls through to "unresolved" the way the
        # `{{char}}` self_id placeholder resolution can.
        if hint.strip().lower() == "self":
            return "character", user_id
        character_id = resolve_name(hint, id_by_character_name)
        if character_id:
            return "character", character_id
        location_id = resolve_name(hint, location_id_by_name)
        if location_id:
            return "location", location_id
        return None

    def _variable_set_rows(
            self,
            variables: VariableSchemaExtraction,
            id_by_character_name: dict[str, str],
            location_id_by_name: dict[str, str],
            *,
            user_id: str,
            report: ConversionReport,
    ) -> list[dict]:
        grouped: dict[tuple[str, str], dict[str, dict]] = {}

        for variable in variables.variables:
            type_matches = VariableDefinition.matches_value_type(
                variable.default_value, variable.value_type,
            )
            if not type_matches:
                report.note(
                    f"Dropped variable {variable.name!r}: default_value doesn't match value_type "
                    f"{variable.value_type.value!r}.",
                    low_confidence=True,
                )
                continue

            owner = self._resolve_owner(
                variable.owner_hint, id_by_character_name, location_id_by_name, user_id=user_id,
            )
            if not owner:
                report.note(
                    f"Dropped variable {variable.name!r}: could not resolve owner hint "
                    f"{variable.owner_hint!r} to an extracted character or location.",
                    low_confidence=True,
                )
                continue

            by_name = grouped.setdefault(owner, {})
            if variable.name in by_name:
                continue  # cross-source duplicate (e.g. same variable in both a script and its
                # human-readable restatement) - first occurrence wins, per §5's deferred-dedup note
            by_name[variable.name] = {
                "name": variable.name,
                "value_type": variable.value_type,
                "value": variable.default_value,
                "default_value": variable.default_value,
                "description": variable.description,
                "minimum": variable.minimum,
                "maximum": variable.maximum,
                "allowed_values": variable.allowed_values,
            }

        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "owner_type": owner_type,
                "owner_id": owner_id,
                "variables": list(by_name.values()),
                "last_updated_at": now,
            }
            for (owner_type, owner_id), by_name in grouped.items()
        ]
