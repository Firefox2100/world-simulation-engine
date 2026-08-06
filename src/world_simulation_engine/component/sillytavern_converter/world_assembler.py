"""Stage 3 of the SillyTavern import pipeline: deterministic, no LLM calls.

Takes every stage-2 output (`CharacterExtraction`, `LocationExtraction`, `WorldLoreExtraction`,
`NarrativeExtraction`, `IntentExtraction`, `VariableSchemaExtraction`, `ItemExtraction`,
`EquipmentExtraction`, `OpeningTurnExtraction`, `SpatialStateExtraction`) and resolves them into one
`WorldImportService`-shaped bundle (§7): a `world`
row plus a `sections` dict of the exact same `dict[str, list[dict]]` shape
`WorldImportService._import_world_contents` already consumes. Every stage-2 entity already carries a
provisional id (§6.2), so this stage needs no new id-minting scheme of its own - it only needs to
decide what to do with references that never resolved to one (drop, per every stage-2 extractor's
own established "never fabricate" rule) and handle the handful of cross-references stage 2 couldn't
resolve on its own (variable `owner_hint`, item/equipment `holder_hint`/`location_hint`, the
`{{char}}`/`{{user}}` macro placeholders that survive verbatim in `first_message` - see
`_rewrite_placeholders` below for why only `first_message` actually needs this in practice).

`items`/`item_stacks` are built by `_item_and_stack_rows` (mirrors `_variable_set_rows`'s
hint-resolution shape). An item whose placement remains unknown is retained as an `Item` type, but
has no concrete `ItemStack`, because `WorldImportService._import_item_stacks` rejects an unplaced
stack. `equipment` is built by `_equipment_rows` - `Equipment` has no such "must be
placed somewhere" constraint at persistence time (unlike `ItemStack`), so a candidate whose
`holder_hint` never resolves is still imported, just unassigned and flagged low-confidence, not
dropped. Still not covered by any stage-2 extractor, so always empty here: landmarks, containers,
configs, prompts, workflows, media. `WorldImportService` already tolerates empty sections
(`for row in rows` over `[]` is a no-op), so this needs no special-casing.

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
from .equipment_extractor import EquipmentExtraction
from .intent_extractor import IntentExtraction
from .item_extractor import ItemExtraction
from .location_extractor import LocationExtraction
from .name_resolution import resolve_name
from .narrative_extractor import NarrativeExtraction
from .opening_turn_extractor import OpeningTurnExtraction
from .private_knowledge_extractor import PrivateKnowledgeExtraction
from .spatial_state_extractor import SpatialEntityType, SpatialStateExtraction
from .variable_schema_extractor import VariableSchemaExtraction
from .world_lore_extractor import WorldLoreExtraction

_USER_STUB_NAME = "User"
_USER_STUB_DESCRIPTION = (
    "The user's persona for this imported card - not modeled as a full character. Created "
    "automatically so in-card {{user}} references resolve to a name instead of rendering empty; "
    "replace or reassign once a real user persona exists for this world."
)

# Prefer an explicit world-scoped date/time variable for the simulation clock. Otherwise use the
# import time and flag the fallback for review.
_DATE_TERMS = (re.compile("日期"), re.compile(r"\bdate\b", re.IGNORECASE))
_TIME_TERMS = (re.compile("时间"), re.compile(r"\btime\b", re.IGNORECASE))
_CN_DATE_PATTERN = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
_ISO_DATE_PATTERN = re.compile(r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})")
_TIME_PATTERN = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})")

# The simulation owns exactly one clock (`World.starting_time`, resolved above from a "world"-scoped
# date/time variable when one exists). A per-owner tracked variable that duplicates that concept (an
# in-card "time passed"/"current date" counter) would drift from the real clock the moment the
# simulation starts advancing turns, so these are never imported as `EntityVariableSet` entries -
# regardless of which owner they were hinted at, unlike the world-scope-only restriction
# `_resolve_starting_time` applies when picking the clock's initial value. Reuses `_DATE_TERMS`/
# `_TIME_TERMS` rather than a separate list, since "is this variable about a date/time" is the same
# question in both places.
_TIME_VARIABLE_NAME_TERMS = (
    re.compile("日期"), re.compile("时间"), re.compile("经过时间"), re.compile("时间流逝"),
    re.compile("已过去"),
    # `\bdate\b`/`\btime\b` (as used by `_DATE_TERMS`/`_TIME_TERMS` above) would miss snake_case
    # names like "time_passed"/"current_date" because `\b` does not split on underscores.
    re.compile(
        r"(?:^|[_\W])(?:time|date|elapsed|duration|clock|calendar|timestamp)(?:$|[_\W])",
        re.IGNORECASE,
    ),
)

# Split punctuation-delimited multi-owner hints before resolving each name independently.
_OWNER_HINT_SPLIT_PATTERN = re.compile(r"[/、,，;；&]+|\s+(?:and|和)\s+")


def _split_owner_hint(hint: str) -> list[str]:
    parts = [part.strip() for part in _OWNER_HINT_SPLIT_PATTERN.split(hint) if part.strip()]
    return parts or [hint.strip()]


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
            items: ItemExtraction,
            equipment: EquipmentExtraction,
            opening_turns: OpeningTurnExtraction | None = None,
            spatial_state: SpatialStateExtraction | None = None,
            private_knowledge: PrivateKnowledgeExtraction | None = None,
    ) -> AssembledWorld:
        report = ConversionReport()
        opening_turns = opening_turns or OpeningTurnExtraction()
        spatial_state = spatial_state or SpatialStateExtraction()
        private_knowledge = private_knowledge or PrivateKnowledgeExtraction()

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

        placement_by_entity = {
            (placement.entity_type, placement.entity_name): placement
            for placement in spatial_state.placements
        }
        character_rows = [
            self._character_row(
                character, self_id=self_id, user_id=user_id,
                placement=placement_by_entity.get(
                    (SpatialEntityType.CHARACTER, character.target_name),
                ),
            )
            for character in characters.characters
        ]
        for character, row in zip(characters.characters, character_rows):
            if not row["location_id"]:
                report.note(
                    f"Character {character.target_name!r} has no inferred initial location; "
                    "retained without spatial placement for manual review.",
                    low_confidence=True,
                )
        location_rows = [
            self._location_row(location, self_id=self_id, user_id=user_id)
            for location in locations.locations
        ]

        history_turn_rows, history_turn_id_by_event = self._history_turn_rows(
            narrative, self_id=self_id, user_id=user_id,
        )
        opening_rows = self._turn_rows(
            card, opening_turns, self_id=self_id, user_id=user_id,
        )
        turn_rows = history_turn_rows + opening_rows
        for sequence, row in enumerate(turn_rows):
            row["sequence"] = sequence

        event_rows = [
            self._event_row(
                event, history_turn_id_by_event[event.id], self_id=self_id, user_id=user_id,
            )
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
        knowledge_rows = [
            self._private_knowledge_row(claim)
            for claim in private_knowledge.claims
        ]

        location_id_by_name = {location.name: location.id for location in locations.locations}
        variable_rows = self._variable_set_rows(
            variables, id_by_character_name, location_id_by_name, user_id=user_id, report=report,
        )
        item_rows, item_stack_rows = self._item_and_stack_rows(
            items, id_by_character_name, location_id_by_name, placement_by_entity,
            user_id=user_id, report=report,
        )
        equipment_rows = self._equipment_rows(
            equipment, id_by_character_name, placement_by_entity, user_id=user_id, report=report,
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
            "items": item_rows,
            "item_stacks": item_stack_rows,
            "equipment": equipment_rows,
            "containers": [],
            "turns": turn_rows,
            "events": event_rows,
            "memories": memory_rows,
            "intents": intent_rows,
            "entity_relationships": relationship_rows,
            "subjective_entity_claims": knowledge_rows,
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
        """Resolve `{{user}}` to a user-controlled character or a minimal background stub."""
        for character in characters.characters:
            if character.result.user_controlled:
                return character.id, None

        stub_id = str(uuid4())
        stub_row = {"id": stub_id, "name": _USER_STUB_NAME, "description": _USER_STUB_DESCRIPTION}
        return stub_id, stub_row

    @staticmethod
    def _character_row(
            character, *, self_id: str | None, user_id: str | None, placement=None,
    ) -> dict:
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
            "location_id": placement.location_id if placement else None,
            "position": placement.position if placement else None,
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
    def _turn_rows(
            card: PreprocessedCard, opening: OpeningTurnExtraction, *,
            self_id: str | None, user_id: str | None,
    ) -> list[dict]:
        extracted = opening.turns
        if not extracted:
            content = card.first_message.strip() or (
                "(imported world - no opening message on the source card)"
            )
            extracted = [{"type": TurnType.SYSTEM_RESPONSE, "content": content}]
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": str(uuid4()),
                "sequence": sequence,
                "type": turn.type if hasattr(turn, "type") else turn["type"],
                "content": _rewrite_placeholders(
                    turn.content if hasattr(turn, "content") else turn["content"],
                    self_id=self_id, user_id=user_id,
                ),
                "start_time": now,
            }
            for sequence, turn in enumerate(extracted)
        ]

    @staticmethod
    def _history_turn_rows(
            narrative: NarrativeExtraction, *, self_id: str | None, user_id: str | None,
    ) -> tuple[list[dict], dict[str, str]]:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        turn_id_by_event = {}
        for sequence, event in enumerate(narrative.events):
            turn_id = str(uuid4())
            turn_id_by_event[event.id] = turn_id
            content = event.summary
            if event.outcome:
                content = f"{content}\n\nOutcome: {event.outcome}"
            rows.append({
                "id": turn_id, "sequence": sequence, "type": TurnType.SYSTEM_RESPONSE,
                "content": _rewrite_placeholders(content, self_id=self_id, user_id=user_id),
                "start_time": now,
            })
        return rows, turn_id_by_event

    @staticmethod
    def _event_row(event, turn_id: str, *, self_id: str | None, user_id: str | None) -> dict:
        return {
            "id": event.id,
            "name": event.name,
            "summary": _rewrite_placeholders(event.summary, self_id=self_id, user_id=user_id),
            "outcome": _rewrite_placeholders(
                event.outcome, self_id=self_id, user_id=user_id,
            ) if event.outcome else None,
            "turn_ids": [turn_id],
            "involved_characters": [
                {"character_id": character_id, "involvement": "participate"}
                for character_id in event.involved_character_ids
            ],
        }

    @staticmethod
    def _private_knowledge_row(claim) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        statement = claim.statement.strip()
        return {
            "id": claim.id,
            "observer_character_id": claim.observer_character_id,
            "subject": {"type": claim.subject_type, "id": claim.subject_id, "name": None},
            "category": claim.category,
            "statement": statement,
            "normalized_statement": " ".join(statement.casefold().split()),
            "stance": claim.stance,
            "confidence": claim.confidence,
            "supporting_memory_ids": claim.supporting_memory_ids,
            "contradicting_memory_ids": [],
            "first_observed_at": now,
            "last_updated_at": now,
            "version": 1,
            "active": True,
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
        is_private = relationship.visibility == "private"
        description = _rewrite_placeholders(
            relationship.description, self_id=self_id, user_id=user_id,
        )
        return {
            "label": relationship.label,
            "public_description": None if is_private else description,
            "private_description": description if is_private else None,
            "visibility": relationship.visibility,
            "perspective_character_id": relationship.perspective_character_id,
            "confidence": relationship.confidence,
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
    def _resolve_owners(
            hint: str,
            id_by_character_name: dict[str, str],
            location_id_by_name: dict[str, str],
            *,
            user_id: str,
    ) -> list[tuple[str, str]]:
        # A schema owner of "self" refers to the player's tracked state. `user_id` always resolves
        # to either a user-controlled character or the synthesized stub.
        if hint.strip().lower() == "self":
            return [("character", user_id)]

        owners: list[tuple[str, str]] = []
        for name in _split_owner_hint(hint):
            character_id = resolve_name(name, id_by_character_name)
            if character_id:
                owner = ("character", character_id)
            else:
                location_id = resolve_name(name, location_id_by_name)
                owner = ("location", location_id) if location_id else None
            if owner and owner not in owners:
                owners.append(owner)
        return owners

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
            if _mentions_any(variable.name, _TIME_VARIABLE_NAME_TERMS):
                report.note(
                    f"Dropped variable {variable.name!r}: time/date-tracking variables are never "
                    "imported as tracked state - the simulation manages its own clock via "
                    "World.starting_time.",
                    low_confidence=True,
                )
                continue

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

            owners = self._resolve_owners(
                variable.owner_hint, id_by_character_name, location_id_by_name, user_id=user_id,
            )
            if not owners:
                report.note(
                    f"Dropped variable {variable.name!r}: could not resolve owner hint "
                    f"{variable.owner_hint!r} to an extracted character or location.",
                    low_confidence=True,
                )
                continue

            # A hint naming several owners at once (e.g. "Avery/Blair/Casey" - one schema
            # entry meant to apply per-character across the whole cast) gets the same variable
            # definition attached to each resolved owner independently, rather than only the first.
            for owner in owners:
                by_name = grouped.setdefault(owner, {})
                if variable.name in by_name:
                    continue  # cross-source duplicate (e.g. same variable in both a script and its
                    # human-readable restatement) - first occurrence wins, per §5's deferred-dedup
                    # note
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

    @staticmethod
    def _resolve_item_holder(
            hint: str | None, id_by_character_name: dict[str, str], *, user_id: str | None,
    ) -> str | None:
        if not hint:
            return None
        if hint.strip().lower() == "self":
            return user_id
        return resolve_name(hint, id_by_character_name)

    def _item_and_stack_rows(
            self,
            items: ItemExtraction,
            id_by_character_name: dict[str, str],
            location_id_by_name: dict[str, str],
            placement_by_entity: dict,
            *,
            user_id: str | None,
            report: ConversionReport,
    ) -> tuple[list[dict], list[dict]]:
        item_rows: list[dict] = []
        stack_rows: list[dict] = []
        seen_names: set[str] = set()

        for candidate in items.items:
            if candidate.name in seen_names:
                continue  # cross-source duplicate (same item named in more than one lorebook
                # entry) - first occurrence wins, same convention as _variable_set_rows.

            holder_id = self._resolve_item_holder(
                candidate.holder_hint, id_by_character_name, user_id=user_id,
            )
            location_id = None
            if not holder_id and candidate.location_hint:
                location_id = resolve_name(candidate.location_hint, location_id_by_name)
            placement = placement_by_entity.get((SpatialEntityType.ITEM, candidate.name))
            if not holder_id and not location_id and placement:
                location_id = placement.location_id

            if not holder_id and not location_id:
                # ItemStack requires a holder *or* a location to import at all (§5/§7) - unlike a
                # dropped variable, an unplaced stack would be a fatal WorldImportError downstream,
                # not something WorldImportService tolerates, so this must never be emitted.
                # Preserve knowledge that the item type exists even when no concrete stack can be
                # placed. The simulation discourages unknown placement, but Item itself is valid.
                seen_names.add(candidate.name)
                item_rows.append({
                    "id": candidate.id, "name": candidate.name,
                    "description": candidate.description, "unique": candidate.unique,
                })
                report.note(
                    f"Item {candidate.name!r} has no imported stack: could not resolve holder hint "
                    f"{candidate.holder_hint!r} or location hint {candidate.location_hint!r} to "
                    "an extracted character or location; retained existence as an Item type only.",
                    low_confidence=True,
                )
                continue

            seen_names.add(candidate.name)
            item_id = candidate.id
            item_rows.append({
                "id": item_id,
                "name": candidate.name,
                "description": candidate.description,
                "unique": candidate.unique,
            })
            stack_rows.append({
                "id": str(uuid4()),
                "item_id": item_id,
                "quantity": candidate.quantity,
                "quality": candidate.quality,
                "holder_id": holder_id,
                "location_id": location_id,
                "position": placement.position if placement and not holder_id else None,
            })

        return item_rows, stack_rows

    def _equipment_rows(
            self,
            equipment: EquipmentExtraction,
            id_by_character_name: dict[str, str],
            placement_by_entity: dict,
            *,
            user_id: str | None,
            report: ConversionReport,
    ) -> list[dict]:
        rows: list[dict] = []
        seen_names: set[str] = set()

        for candidate in equipment.equipment:
            if candidate.name in seen_names:
                continue  # cross-source duplicate (e.g. named in both a lorebook entry and the
                # opening message) - first occurrence wins, same convention as items/variables.

            holder_id = self._resolve_item_holder(
                candidate.holder_hint, id_by_character_name, user_id=user_id,
            )
            if candidate.holder_hint and not holder_id:
                # Unlike an item stack, Equipment has no "must be placed somewhere" constraint at
                # persistence time - importing it unassigned is safe, just worth flagging.
                report.note(
                    f"Equipment {candidate.name!r}: could not resolve holder hint "
                    f"{candidate.holder_hint!r} to an extracted character - imported unassigned.",
                    low_confidence=True,
                )
            placement = placement_by_entity.get((SpatialEntityType.EQUIPMENT, candidate.name))
            if not holder_id and not placement:
                report.note(
                    f"Equipment {candidate.name!r} has no inferred holder or initial location; "
                    "retained unplaced for manual review.",
                    low_confidence=True,
                )

            seen_names.add(candidate.name)
            rows.append({
                "id": candidate.id,
                "name": candidate.name,
                "description": candidate.description,
                "quality": candidate.quality,
                "holder_id": holder_id,
                "equipped": True,
                "equipped_position": candidate.slot,
                "location_id": placement.location_id if placement and not holder_id else None,
                "position": placement.position if placement and not holder_id else None,
            })

        return rows
