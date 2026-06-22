import operator
from copy import deepcopy
from uuid import uuid4
from typing import Any, Annotated
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import FactionRelationshipEntity, TurnType
from world_simulation_engine.model import Simulation, SimulationState, LlmConnectionProfile, DirectorOutput, \
    PendingGeneratedProposal, CharacterBriefing, BriefingOutput, CharacterActionOutput, CharacterInventory, \
    ResolverOutput, Faction, FactionRelationship, CommitterFinalOutput, CharacterReactionContext, \
    FailedCharacterRecord, Character, WorldEntry, Location, Item, ResolvedAction, Task, Equipment, \
    NarratorResolvedEvent, NarratorResolutionView, SummaryOutput, TurnRecordCreate, WaitForUserNarrationContext, \
    UserInputResolverContext, UserInputResolutionOutput, UserInputFailureNarrationContext
from world_simulation_engine.service import DatabaseService, EmbeddingService, DirectorAgent, WorldGeneratorAgent, \
    MemoryAgent, CharacterAgent, ResolverAgent, CommitterAgent, NarratorAgent
from ..world_entry_recaller import WorldEntryRecaller


class ConnectionProfileCache(BaseModel):
    director: LlmConnectionProfile | None = None
    memory: LlmConnectionProfile | None = None
    character: LlmConnectionProfile | None = None
    resolver: LlmConnectionProfile | None = None
    committer: LlmConnectionProfile | None = None
    narrator: LlmConnectionProfile | None = None
    world_generator: LlmConnectionProfile | None = None
    embedding: LlmConnectionProfile | None = None


class TurnGeneratorState(BaseModel):
    run_id: str
    simulation_id: int
    user_input: str | None = None

    simulation: Simulation | None = None
    state: SimulationState | None = None
    connection_profiles: ConnectionProfileCache = Field(default_factory=ConnectionProfileCache)

    user_input_resolution: UserInputResolutionOutput | None = None
    director_output: DirectorOutput | None = None
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing_output: BriefingOutput | None = None
    character_action_outputs: Annotated[
        list[CharacterActionOutput],
        operator.add,
    ] = Field(default_factory=list)
    character_reaction_outputs: Annotated[
        list[CharacterActionOutput],
        operator.add,
    ] = Field(default_factory=list)
    resolver_output: ResolverOutput | None = None
    reaction_resolver_output: ResolverOutput | None = None
    committer_output: CommitterFinalOutput | None = None
    narration: str | None = None
    summary_output: SummaryOutput | None = None


class CharacterActionState(BaseModel):
    user_input: str | None
    simulation: Simulation | None
    state: SimulationState | None
    connection_profiles: ConnectionProfileCache
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing: CharacterBriefing


class CharacterReactionState(BaseModel):
    user_input: str | None
    simulation: Simulation | None
    state: SimulationState | None
    connection_profiles: ConnectionProfileCache
    generated_proposals: list[PendingGeneratedProposal] | None = None
    reaction_context: CharacterReactionContext


class TurnGenerator:
    def __init__(self,
                 database_service: DatabaseService,
                 ):
        self._db = database_service

    @staticmethod
    def _inventory_values(
            inventory: CharacterInventory | dict,
            field_name: str,
    ) -> list[Any]:
        if isinstance(inventory, dict):
            return inventory.get(field_name, []) or []

        values = getattr(inventory, "__dict__", {}).get(field_name)
        if values is not None:
            return values

        return getattr(inventory, field_name, []) or []

    @staticmethod
    def _dedupe_relationships(relationships: list[FactionRelationship]) -> list[FactionRelationship]:
        seen = set()
        result = []
        for relationship in relationships:
            key = (
                relationship.from_type,
                relationship.from_id,
                relationship.to_type,
                relationship.to_id,
                relationship.relationship,
                relationship.private,
            )
            if key in seen:
                continue

            seen.add(key)
            result.append(relationship)

        return result

    @staticmethod
    def _faction_ids_from_relationships(relationships: list[FactionRelationship]) -> list[int]:
        faction_ids = set()
        for relationship in relationships:
            if relationship.from_type == FactionRelationshipEntity.FACTION:
                faction_ids.add(relationship.from_id)
            if relationship.to_type == FactionRelationshipEntity.FACTION:
                faction_ids.add(relationship.to_id)

        return list(faction_ids)

    async def _load_faction_context(
        self,
        simulation_id: int,
        character_ids: list[int] | None = None,
        item_ids: list[int] | None = None,
        include_private: bool = False,
    ) -> tuple[list[Faction], list[FactionRelationship]]:
        entity_refs = [
            (FactionRelationshipEntity.CHARACTER, character_id)
            for character_id in (character_ids or [])
        ] + [
            (FactionRelationshipEntity.ITEM, item_id)
            for item_id in (item_ids or [])
        ]
        if not entity_refs:
            return [], []

        privacy_filter = None if include_private else False
        relationships = await self._db.faction_relationship.list(
            entity_refs=entity_refs or None,
            simulation_id=simulation_id,
            private=privacy_filter,
        )

        faction_ids = self._faction_ids_from_relationships(relationships)
        if faction_ids:
            faction_relationships = await self._db.faction_relationship.list(
                entity_refs=[
                    (FactionRelationshipEntity.FACTION, faction_id)
                    for faction_id in faction_ids
                ],
                simulation_id=simulation_id,
                private=privacy_filter,
            )
            relationships = self._dedupe_relationships(relationships + faction_relationships)
            faction_ids = self._faction_ids_from_relationships(relationships)

        if not faction_ids:
            return [], relationships

        factions = await self._db.faction.list(
            simulation_id=simulation_id,
            faction_ids=faction_ids,
        )

        return factions, relationships

    async def _load_character_faction_context(
        self,
        simulation_id: int,
        acting_character_id: int,
        visible_character_ids: list[int],
        item_ids: list[int],
    ) -> tuple[list[Faction], list[FactionRelationship]]:
        public_factions, public_relationships = await self._load_faction_context(
            simulation_id=simulation_id,
            character_ids=[acting_character_id] + visible_character_ids,
            item_ids=item_ids,
            include_private=False,
        )
        private_relationships = await self._db.faction_relationship.list(
            entity_refs=[
                (FactionRelationshipEntity.CHARACTER, acting_character_id),
                *[
                    (FactionRelationshipEntity.ITEM, item_id)
                    for item_id in item_ids
                ],
            ],
            simulation_id=simulation_id,
            private=True,
        )
        relationships = self._dedupe_relationships(public_relationships + private_relationships)
        faction_ids = self._faction_ids_from_relationships(relationships)

        if not faction_ids:
            return [], relationships

        private_factions = await self._db.faction.list(
            simulation_id=simulation_id,
            faction_ids=faction_ids,
        )
        factions_by_id = {faction.id: faction for faction in public_factions + private_factions}

        return list(factions_by_id.values()), relationships

    def _normalise_character_action_output(
            self,
            result: CharacterActionOutput,
            character: Character,
            visible_characters: list[Character],
            current_location: Location,
            inventory: list[Item],
    ) -> CharacterActionOutput:
        valid_character_ids = {
            c.id
            for c in visible_characters
        }

        valid_entity_ids = {
            entity.id
            for entity in current_location.entities
        }

        valid_item_ids = {
            item.id
            for item in inventory
        }

        changed = False
        notes: list[str] = []

        if result.character_id != character.id:
            notes.append(
                f"Corrected character_id from {result.character_id} to {character.id}."
            )
            result.character_id = character.id
            changed = True

        if result.character_name != character.name:
            notes.append(
                f"Corrected character_name from {result.character_name!r} to {character.name!r}."
            )
            result.character_name = character.name
            changed = True

        original_target_character_ids = list(result.target_character_ids or [])
        result.target_character_ids = [
            character_id
            for character_id in original_target_character_ids
            if character_id in valid_character_ids
        ]

        if result.target_character_ids != original_target_character_ids:
            notes.append(
                "Removed invalid target_character_ids not visible to the acting character."
            )
            changed = True

        original_target_entity_ids = list(result.target_entity_ids or [])
        result.target_entity_ids = [
            entity_id
            for entity_id in original_target_entity_ids
            if entity_id in valid_entity_ids
        ]

        if result.target_entity_ids != original_target_entity_ids:
            notes.append(
                "Removed invalid target_entity_ids not present in the current location."
            )
            changed = True

        original_target_item_ids = list(result.target_item_ids or [])
        result.target_item_ids = [
            item_id
            for item_id in original_target_item_ids
            if item_id in valid_item_ids
        ]

        if result.target_item_ids != original_target_item_ids:
            notes.append(
                "Removed invalid target_item_ids not present in the acting character's inventory."
            )
            changed = True

        if result.target_location_id is not None:
            # In the current prompt we only give the current location ID.
            # Until known exits/adjacent locations are explicitly supplied, disallow
            # arbitrary location targeting except the current location.
            if result.target_location_id != current_location.id:
                notes.append(
                    f"Cleared unsupported target_location_id {result.target_location_id}; "
                    "known exits/destinations were not supplied."
                )
                result.target_location_id = None
                changed = True

        result.urgency = max(0, min(100, int(result.urgency)))
        result.persistence = max(0, min(100, int(result.persistence)))

        if not result.target_character_ids:
            result.target_character_ids = []

        if not result.target_entity_ids:
            result.target_entity_ids = []

        if not result.target_item_ids:
            result.target_item_ids = []

        if changed:
            existing_notes = result.notes or ""
            appended_notes = " ".join(notes)

            if existing_notes:
                result.notes = f"{existing_notes} [System normalisation: {appended_notes}]"
            else:
                result.notes = f"System normalisation: {appended_notes}"

        return result

    def _normalise_action_for_resolver_input(self, action: CharacterActionOutput) -> CharacterActionOutput:
        if action.target_character_ids is None:
            action.target_character_ids = []

        if action.target_entity_ids is None:
            action.target_entity_ids = []

        if action.target_item_ids is None:
            action.target_item_ids = []

        if action.constraints_for_resolver is None:
            action.constraints_for_resolver = []

        action.urgency = max(0, min(100, int(action.urgency)))
        action.persistence = max(0, min(100, int(action.persistence)))

        return action

    def _build_resolver_recall_query(
            self,
            state: TurnGeneratorState,
            current_location: Location,
            character_actions: list[CharacterActionOutput],
    ) -> str:
        parts: list[str] = [
            state.state.state if state.state else "",
            state.user_input or "",
            current_location.primary_location,
            current_location.detailed_location,
            current_location.scene,
            current_location.description,
        ]

        for entity in current_location.entities:
            parts.extend(
                [
                    entity.name,
                    entity.type,
                    entity.description,
                    entity.status,
                    " ".join(entity.interactions or []),
                ]
            )

        for action in character_actions:
            parts.extend(
                [
                    action.character_name,
                    action.intent,
                    action.action_type,
                    action.method,
                    action.visible_behavior,
                    action.expected_outcome,
                    action.private_reason_for_system or "",
                    " ".join(action.constraints_for_resolver or []),
                ]
            )

        return "\n".join(part for part in parts if part)

    def _build_actor_knowledge_index(
            self,
            acting_character_ids: list[int],
            world_entries: list[WorldEntry],
    ) -> dict[int, list[int]]:
        actor_knowledge_index: dict[int, list[int]] = {
            actor_id: []
            for actor_id in acting_character_ids
        }

        for entry in world_entries:
            scopes = set(entry.scope or [])

            # GM-only entries are intentionally not actor knowledge.
            if -1 in scopes:
                continue

            for actor_id in acting_character_ids:
                if 0 in scopes or actor_id in scopes:
                    actor_knowledge_index[actor_id].append(entry.id)

        return actor_knowledge_index

    def _build_action_validation_reports(
            self,
            actions: list[CharacterActionOutput],
            present_characters: list[Character],
            current_location: Location,
            inventory: dict[int, CharacterInventory],
            actor_knowledge_index: dict[int, list[int]],
    ) -> list[dict]:
        present_character_ids = {character.id for character in present_characters}
        present_character_by_id = {character.id: character for character in present_characters}

        current_entity_ids = {entity.id for entity in current_location.entities}

        reports: list[dict] = []

        for action in actions:
            actor = present_character_by_id.get(action.character_id)

            actor_inventory = inventory.get(action.character_id)
            actor_item_ids = {
                item.id
                for item in self._inventory_values(actor_inventory, "items")
            } if actor_inventory else set()

            actor_equipment_ids = {
                equipment.id
                for equipment in self._inventory_values(actor_inventory, "equipments")
            } if actor_inventory else set()

            invalid_target_character_ids = [
                character_id
                for character_id in action.target_character_ids
                if character_id not in present_character_ids
            ]

            invalid_target_entity_ids = [
                entity_id
                for entity_id in action.target_entity_ids
                if entity_id not in current_entity_ids
            ]

            invalid_target_item_ids = [
                item_id
                for item_id in action.target_item_ids
                if item_id not in actor_item_ids
            ]

            notes: list[str] = []
            possible_ooc_flags: list[str] = []

            if actor is None:
                notes.append("Acting character is not present in the current resolver scene.")

            if invalid_target_character_ids:
                notes.append(
                    f"Invalid target_character_ids not present in scene: {invalid_target_character_ids}"
                )

            if invalid_target_entity_ids:
                notes.append(
                    f"Invalid target_entity_ids not present in current location: {invalid_target_entity_ids}"
                )

            if invalid_target_item_ids:
                notes.append(
                    f"Invalid target_item_ids not in actor inventory: {invalid_target_item_ids}"
                )

            if action.target_location_id is not None and action.target_location_id != current_location.id:
                notes.append(
                    "Action targets a different location, but known exits/destinations were not supplied to resolver."
                )

            if action.uses_private_knowledge and not action.private_reason_for_system:
                possible_ooc_flags.append(
                    "Action claims private knowledge was used but gives no private_reason_for_system."
                )

            if not action.uses_private_knowledge and action.private_reason_for_system:
                possible_ooc_flags.append(
                    "Action includes private_reason_for_system but uses_private_knowledge is false."
                )

            # Heuristic: if target fields are empty but method/visible behaviour mentions known entity names,
            # flag it so Resolver can avoid losing target grounding.
            mentioned_entities_without_target: list[int] = []
            method_blob = f"{action.intent}\n{action.method}\n{action.visible_behavior}\n{action.expected_outcome}".lower()

            for entity in current_location.entities:
                if entity.name.lower() in method_blob and entity.id not in action.target_entity_ids:
                    mentioned_entities_without_target.append(entity.id)

            if mentioned_entities_without_target:
                notes.append(
                    f"Action text mentions entity/entities {mentioned_entities_without_target} but target_entity_ids does not include them."
                )

            # Heuristic: if action mentions a visible character name but target_character_ids omits it.
            mentioned_characters_without_target: list[int] = []

            for character in present_characters:
                if character.id == action.character_id:
                    continue

                if character.name.lower() in method_blob and character.id not in action.target_character_ids:
                    mentioned_characters_without_target.append(character.id)

            if mentioned_characters_without_target:
                notes.append(
                    f"Action text mentions character(s) {mentioned_characters_without_target} but target_character_ids does not include them."
                )

            reports.append(
                {
                    "actor_id": action.character_id,
                    "actor_name": action.character_name,
                    "actor_present": actor is not None,
                    "actor_known_world_entry_ids": actor_knowledge_index.get(action.character_id, []),
                    "invalid_target_character_ids": invalid_target_character_ids,
                    "invalid_target_entity_ids": invalid_target_entity_ids,
                    "invalid_target_item_ids": invalid_target_item_ids,
                    "mentioned_entities_without_target": mentioned_entities_without_target,
                    "mentioned_characters_without_target": mentioned_characters_without_target,
                    "actor_inventory_item_ids": sorted(actor_item_ids),
                    "actor_equipment_ids": sorted(actor_equipment_ids),
                    "notes": notes,
                    "possible_ooc_flags": possible_ooc_flags,
                }
            )

        return reports

    def _normalise_resolver_output(
            self,
            result: ResolverOutput,
            character_actions: list[CharacterActionOutput],
            present_character_ids: set[int],
    ) -> ResolverOutput:
        valid_statuses = {
            "succeeded",
            "partially_succeeded",
            "failed",
            "blocked",
            "delayed",
            "invalid",
            "cancelled",
        }

        action_by_actor_id = {
            action.character_id: action
            for action in character_actions
        }

        resolved_actor_ids = {
            resolved.actor_id
            for resolved in result.resolved_actions
        }

        # Add invalid fallback entries for any action the model forgot to resolve.
        for action in character_actions:
            if action.character_id in resolved_actor_ids:
                continue

            result.resolved_actions.append(
                ResolvedAction(
                    actor_id=action.character_id,
                    actor_name=action.character_name,
                    original_intent=action.intent,
                    final_status="invalid",
                    resolved_order=None,
                    visible_result="No resolved result was produced for this attempted action.",
                    private_result_for_actor=None,
                    failure_reason="Resolver omitted this action; marked invalid by system normalisation.",
                    blocking_actor_id=None,
                    blocking_entity_id=None,
                    state_change_hints=[],
                    world_entry_hints=[],
                    requires_actor_retry=True,
                    retry_instruction="Re-attempt with a simpler, better-grounded action.",
                )
            )

        for resolved in result.resolved_actions:
            if resolved.final_status not in valid_statuses:
                resolved.final_status = "invalid"
                resolved.failure_reason = "Resolver produced an unsupported final_status."

            if resolved.actor_id not in present_character_ids:
                resolved.final_status = "invalid"
                resolved.failure_reason = "Actor is not present in the resolved scene."

            if resolved.state_change_hints is None:
                resolved.state_change_hints = []

            if resolved.world_entry_hints is None:
                resolved.world_entry_hints = []

            if resolved.final_status in {"failed", "blocked", "invalid", "cancelled"}:
                if not resolved.failure_reason:
                    resolved.failure_reason = "Action did not complete."

                if resolved.requires_actor_retry and resolved.retry_instruction is None:
                    resolved.retry_instruction = "Choose a revised action that avoids the blocking condition."

            else:
                # For success/partial/delay, avoid stale failure fields unless delay/partial explicitly needs it.
                if resolved.final_status == "succeeded":
                    resolved.failure_reason = None
                    resolved.requires_actor_retry = False
                    resolved.retry_instruction = None

            if resolved.blocking_actor_id is not None and resolved.blocking_actor_id not in present_character_ids:
                resolved.blocking_actor_id = None

        failed_actor_ids = {
            resolved.actor_id
            for resolved in result.resolved_actions
            if resolved.final_status in {"failed", "blocked", "invalid", "cancelled"}
               and resolved.requires_actor_retry
        }

        # Preserve model-provided failed_characters if present, but ensure consistency.
        failed_by_actor_id: dict[int, FailedCharacterRecord] = {
            failed.character_id: failed
            for failed in result.failed_characters or []
        }

        for actor_id in failed_actor_ids:
            if actor_id in failed_by_actor_id:
                continue

            action = action_by_actor_id.get(actor_id)
            resolved = next(
                (
                    resolved_action
                    for resolved_action in result.resolved_actions
                    if resolved_action.actor_id == actor_id
                ),
                None,
            )

            failed_by_actor_id[actor_id] = FailedCharacterRecord(
                character_id=actor_id,
                character_name=(
                    resolved.actor_name
                    if resolved is not None
                    else action.character_name if action is not None else "Unknown character"
                ),
                failed_action_summary=(
                    resolved.original_intent
                    if resolved is not None
                    else action.intent if action is not None else "Unknown action"
                ),
                reason=(
                    resolved.failure_reason
                    if resolved is not None and resolved.failure_reason
                    else "Action did not complete."
                ),
                retry_allowed=True,
                retry_context=(
                    resolved.retry_instruction
                    if resolved is not None
                    else None
                ),
            )

        result.failed_characters = list(failed_by_actor_id.values())

        if result.conflicts is None:
            result.conflicts = []

        if result.state_update_suggestions is None:
            result.state_update_suggestions = []

        if result.pending_world_entry_suggestions is None:
            result.pending_world_entry_suggestions = []

        if result.narrator_context is None:
            result.narrator_context = []

        if not result.resolved_actions:
            result.accepted = False
            result.rejection_reason = "No actions were resolved."

        if result.accepted and not result.rejection_reason:
            result.rejection_reason = None

        if not result.requires_director_rerun:
            result.director_rerun_reason = None

        return result

    def _build_character_reaction_recall_query(
            self,
            state: CharacterReactionState,
            character: Character,
            current_location: Location,
            tasks: list[Task],
    ) -> str:
        reaction_context = state.reaction_context

        parts: list[str] = [
            character.name,
            character.public_state,
            character.private_state,
            reaction_context.original_action.intent,
            reaction_context.original_action.action_type,
            reaction_context.original_action.method,
            reaction_context.original_action.visible_behavior,
            reaction_context.original_action.expected_outcome,
            reaction_context.original_action.fallback_if_blocked or "",
            reaction_context.failure_record.failed_action_summary,
            reaction_context.failure_record.reason,
            reaction_context.failure_record.retry_context or "",
            reaction_context.changed_scene_context,
            reaction_context.immediate_failure_context,
            state.user_input or "",
            current_location.primary_location,
            current_location.detailed_location,
            current_location.scene,
            current_location.description,
        ]

        parts.extend(reaction_context.fixed_visible_events or [])
        parts.extend(reaction_context.fixed_private_events_for_actor or [])
        parts.extend(reaction_context.constraints or [])

        for entity in current_location.entities:
            parts.extend(
                [
                    entity.name,
                    entity.type,
                    entity.description,
                    entity.status,
                    " ".join(entity.interactions or []),
                ]
            )

        if tasks:
            parts.append(
                "Relevant task goals: "
                + "; ".join(
                    task.goal
                    for task in tasks
                    if getattr(task, "goal", None)
                )
            )

        return "\n".join(
            part
            for part in parts
            if part
        )

    def _normalise_character_reaction_output(
            self,
            result: CharacterActionOutput,
            character: Character,
            visible_characters: list[Character],
            current_location: Location,
            inventory: list[Item],
            equipments: list[Equipment],
            reaction_context: CharacterReactionContext,
    ) -> CharacterActionOutput:
        valid_character_ids = {
            c.id
            for c in visible_characters
        }

        valid_entity_ids = {
            entity.id
            for entity in current_location.entities
        }

        valid_item_ids = {
            item.id
            for item in inventory
        }

        # Equipment may not currently have a target field in CharacterActionOutput.
        # Keep the set available for future schema extension or validation in notes.
        valid_equipment_ids = {
            equipment.id
            for equipment in equipments
        }

        changed = False
        notes: list[str] = []

        if result.character_id != character.id:
            notes.append(
                f"Corrected character_id from {result.character_id} to {character.id}."
            )
            result.character_id = character.id
            changed = True

        if result.character_name != character.name:
            notes.append(
                f"Corrected character_name from {result.character_name!r} to {character.name!r}."
            )
            result.character_name = character.name
            changed = True

        if result.target_character_ids is None:
            result.target_character_ids = []
            changed = True

        if result.target_entity_ids is None:
            result.target_entity_ids = []
            changed = True

        if result.target_item_ids is None:
            result.target_item_ids = []
            changed = True

        if result.constraints_for_resolver is None:
            result.constraints_for_resolver = []
            changed = True

        original_target_character_ids = list(result.target_character_ids)
        result.target_character_ids = [
            character_id
            for character_id in result.target_character_ids
            if character_id in valid_character_ids
        ]

        if result.target_character_ids != original_target_character_ids:
            notes.append(
                "Removed invalid target_character_ids not visible to the reacting character."
            )
            changed = True

        original_target_entity_ids = list(result.target_entity_ids)
        result.target_entity_ids = [
            entity_id
            for entity_id in result.target_entity_ids
            if entity_id in valid_entity_ids
        ]

        if result.target_entity_ids != original_target_entity_ids:
            notes.append(
                "Removed invalid target_entity_ids not present in the current location."
            )
            changed = True

        original_target_item_ids = list(result.target_item_ids)
        result.target_item_ids = [
            item_id
            for item_id in result.target_item_ids
            if item_id in valid_item_ids
        ]

        if result.target_item_ids != original_target_item_ids:
            notes.append(
                "Removed invalid target_item_ids not present in the reacting character's inventory."
            )
            changed = True

        if result.target_location_id is not None:
            # Until known exits/adjacent locations are supplied to this stage,
            # disallow arbitrary movement targets.
            if result.target_location_id != current_location.id:
                notes.append(
                    f"Cleared unsupported target_location_id {result.target_location_id}; known exits/destinations were not supplied."
                )
                result.target_location_id = None
                changed = True

        result.urgency = max(0, min(100, int(result.urgency)))
        result.persistence = max(0, min(100, int(result.persistence)))

        # Hard retry-scope guard: if the generated reaction appears identical to the failed method,
        # do not silently rewrite it, but flag it to Resolver.
        original_method = (reaction_context.original_action.method or "").strip().lower()
        new_method = (result.method or "").strip().lower()

        original_action_type = reaction_context.original_action.action_type
        same_action_type = result.action_type == original_action_type
        same_method = bool(original_method and new_method and original_method == new_method)

        if same_action_type and same_method:
            notes.append(
                "Reaction appears to repeat the same failed action type and method; Resolver should reject unless context makes this meaningfully different."
            )
            result.constraints_for_resolver.append(
                "System warning: this reaction may repeat the same failed action without a sufficiently different method."
            )
            changed = True

        # Add fixed-event constraints explicitly so Resolver sees them even if the model omitted them.
        fixed_constraints = [
            "This reaction occurs after the original failed/blocked/partial action.",
            "Fixed resolved events from the previous resolution pass cannot be undone.",
            "This is the final retry for this character this round.",
        ]

        for constraint in fixed_constraints:
            if constraint not in result.constraints_for_resolver:
                result.constraints_for_resolver.append(constraint)
                changed = True

        if changed:
            existing_notes = result.notes or ""
            appended_notes = " ".join(notes)

            if existing_notes:
                result.notes = f"{existing_notes} [System normalisation: {appended_notes}]"
            else:
                result.notes = f"System normalisation: {appended_notes}"

        return result

    def _build_reaction_resolver_recall_query(
            self,
            state: TurnGeneratorState,
            current_location: Location,
            reaction_actions: list[CharacterActionOutput],
    ) -> str:
        parts: list[str] = [
            state.state.state if state.state else "",
            state.user_input or "",
            current_location.primary_location,
            current_location.detailed_location,
            current_location.scene,
            current_location.description,
            state.resolver_output.scene_result_summary if state.resolver_output else "",
            state.resolver_output.next_round_note if state.resolver_output else "",
        ]

        if state.resolver_output:
            for resolved in state.resolver_output.resolved_actions:
                parts.extend(
                    [
                        resolved.actor_name,
                        resolved.original_intent,
                        resolved.final_status,
                        resolved.visible_result,
                        resolved.private_result_for_actor or "",
                        resolved.failure_reason or "",
                        " ".join(resolved.state_change_hints or []),
                        " ".join(resolved.world_entry_hints or []),
                    ]
                )

            parts.extend(state.resolver_output.narrator_context or [])
            parts.extend(state.resolver_output.state_update_suggestions or [])
            parts.extend(state.resolver_output.pending_world_entry_suggestions or [])

        for entity in current_location.entities:
            parts.extend(
                [
                    entity.name,
                    entity.type,
                    entity.description,
                    entity.status,
                    " ".join(entity.interactions or []),
                ]
            )

        for action in reaction_actions:
            parts.extend(
                [
                    action.character_name,
                    action.intent,
                    action.action_type,
                    action.method,
                    action.visible_behavior,
                    action.expected_outcome,
                    action.private_reason_for_system or "",
                    " ".join(action.constraints_for_resolver or []),
                ]
            )

        return "\n".join(part for part in parts if part)

    def _build_reaction_validation_reports(
            self,
            actions: list[CharacterActionOutput],
            present_characters: list[Character],
            current_location: Location,
            inventory: dict[int, CharacterInventory],
            actor_knowledge_index: dict[int, list[int]],
            previous_resolver_output: ResolverOutput,
    ) -> list[dict]:
        present_character_ids = {character.id for character in present_characters}
        present_character_by_id = {character.id: character for character in present_characters}

        current_entity_ids = {entity.id for entity in current_location.entities}

        previous_action_by_actor_id = {
            action.actor_id: action
            for action in previous_resolver_output.resolved_actions
        }

        reports: list[dict] = []

        for action in actions:
            actor = present_character_by_id.get(action.character_id)

            actor_inventory = inventory.get(action.character_id)
            actor_item_ids = {
                item.id
                for item in self._inventory_values(actor_inventory, "items")
            } if actor_inventory else set()

            actor_equipment_ids = {
                equipment.id
                for equipment in self._inventory_values(actor_inventory, "equipments")
            } if actor_inventory else set()

            invalid_target_character_ids = [
                character_id
                for character_id in action.target_character_ids
                if character_id not in present_character_ids
            ]

            invalid_target_entity_ids = [
                entity_id
                for entity_id in action.target_entity_ids
                if entity_id not in current_entity_ids
            ]

            invalid_target_item_ids = [
                item_id
                for item_id in action.target_item_ids
                if item_id not in actor_item_ids
            ]

            notes: list[str] = []
            possible_ooc_flags: list[str] = []

            if actor is None:
                notes.append("Reacting character is not present in the current resolver scene.")

            if action.character_id not in previous_action_by_actor_id:
                notes.append(
                    "Reacting character did not have a resolved failed/blocked/delayed/partial action in the previous resolver output."
                )

            if invalid_target_character_ids:
                notes.append(
                    f"Invalid target_character_ids not present in scene: {invalid_target_character_ids}"
                )

            if invalid_target_entity_ids:
                notes.append(
                    f"Invalid target_entity_ids not present in current location: {invalid_target_entity_ids}"
                )

            if invalid_target_item_ids:
                notes.append(
                    f"Invalid target_item_ids not in actor inventory: {invalid_target_item_ids}"
                )

            if action.target_location_id is not None and action.target_location_id != current_location.id:
                notes.append(
                    "Reaction targets a different location, but known exits/destinations were not supplied to resolver."
                )

            if action.uses_private_knowledge and not action.private_reason_for_system:
                possible_ooc_flags.append(
                    "Reaction claims private knowledge was used but gives no private_reason_for_system."
                )

            if not action.uses_private_knowledge and action.private_reason_for_system:
                possible_ooc_flags.append(
                    "Reaction includes private_reason_for_system but uses_private_knowledge is false."
                )

            method_blob = (
                f"{action.intent}\n"
                f"{action.method}\n"
                f"{action.visible_behavior}\n"
                f"{action.expected_outcome}"
            ).lower()

            mentioned_entities_without_target: list[int] = []
            for entity in current_location.entities:
                if entity.name.lower() in method_blob and entity.id not in action.target_entity_ids:
                    mentioned_entities_without_target.append(entity.id)

            if mentioned_entities_without_target:
                notes.append(
                    f"Reaction text mentions entity/entities {mentioned_entities_without_target} but target_entity_ids does not include them."
                )

            mentioned_characters_without_target: list[int] = []
            for character in present_characters:
                if character.id == action.character_id:
                    continue

                if character.name.lower() in method_blob and character.id not in action.target_character_ids:
                    mentioned_characters_without_target.append(character.id)

            if mentioned_characters_without_target:
                notes.append(
                    f"Reaction text mentions character(s) {mentioned_characters_without_target} but target_character_ids does not include them."
                )

            previous_resolved_action = previous_action_by_actor_id.get(action.character_id)

            repeats_original_failed_action = False
            if previous_resolved_action:
                previous_intent = (previous_resolved_action.original_intent or "").strip().lower()
                current_intent = (action.intent or "").strip().lower()
                current_method = (action.method or "").strip().lower()

                if previous_intent and current_intent and previous_intent == current_intent:
                    repeats_original_failed_action = True
                    notes.append(
                        "Reaction intent appears identical to the previous resolved intent."
                    )

                # If the previous visible result/failure says the actor was blocked,
                # repeating same target may be suspect unless method changed.
                if (
                        previous_resolved_action.final_status in {"failed", "blocked", "invalid", "cancelled"}
                        and previous_resolved_action.failure_reason
                        and previous_resolved_action.failure_reason.lower() in current_method
                ):
                    notes.append(
                        "Reaction method appears to rely on the same failed/blocking condition; resolver should check whether it meaningfully changes approach."
                    )

            # Fixed-event conflict heuristic.
            fixed_event_blob = "\n".join(
                [
                    resolved.visible_result
                    for resolved in previous_resolver_output.resolved_actions
                    if resolved.final_status in {"succeeded", "partially_succeeded", "delayed"}
                       and resolved.visible_result
                ]
            ).lower()

            possible_fixed_event_conflict = False
            undo_words = ["undo", "prevent", "stop before", "keep from happening", "as if it had not", "reverse"]

            if any(word in method_blob for word in undo_words):
                possible_fixed_event_conflict = True
                notes.append(
                    "Reaction may be attempting to undo or retroactively prevent a fixed resolved event."
                )

            reports.append(
                {
                    "actor_id": action.character_id,
                    "actor_name": action.character_name,
                    "actor_present": actor is not None,
                    "actor_known_world_entry_ids": actor_knowledge_index.get(action.character_id, []),
                    "invalid_target_character_ids": invalid_target_character_ids,
                    "invalid_target_entity_ids": invalid_target_entity_ids,
                    "invalid_target_item_ids": invalid_target_item_ids,
                    "mentioned_entities_without_target": mentioned_entities_without_target,
                    "mentioned_characters_without_target": mentioned_characters_without_target,
                    "repeats_original_failed_action": repeats_original_failed_action,
                    "possible_fixed_event_conflict": possible_fixed_event_conflict,
                    "actor_inventory_item_ids": sorted(actor_item_ids),
                    "actor_equipment_ids": sorted(actor_equipment_ids),
                    "notes": notes,
                    "possible_ooc_flags": possible_ooc_flags,
                }
            )

        return reports

    def _normalise_reaction_resolver_output(
            self,
            result: ResolverOutput,
            reaction_actions: list[CharacterActionOutput],
            present_character_ids: set[int],
    ) -> ResolverOutput:
        valid_statuses = {
            "succeeded",
            "partially_succeeded",
            "failed",
            "blocked",
            "delayed",
            "invalid",
            "cancelled",
        }

        resolved_actor_ids = {
            resolved.actor_id
            for resolved in result.resolved_actions
        }

        for action in reaction_actions:
            if action.character_id in resolved_actor_ids:
                continue

            result.resolved_actions.append(
                ResolvedAction(
                    actor_id=action.character_id,
                    actor_name=action.character_name,
                    original_intent=action.intent,
                    final_status="invalid",
                    resolved_order=None,
                    visible_result="No resolved result was produced for this reaction action.",
                    private_result_for_actor=None,
                    failure_reason="Reaction resolver omitted this action; marked invalid by system normalisation.",
                    blocking_actor_id=None,
                    blocking_entity_id=None,
                    state_change_hints=[],
                    world_entry_hints=[],
                    requires_actor_retry=False,
                    retry_instruction=None,
                )
            )

        for resolved in result.resolved_actions:
            if resolved.final_status not in valid_statuses:
                resolved.final_status = "invalid"
                resolved.failure_reason = "Reaction resolver produced an unsupported final_status."

            if resolved.actor_id not in present_character_ids:
                resolved.final_status = "invalid"
                resolved.failure_reason = "Actor is not present in the resolved scene."

            if resolved.state_change_hints is None:
                resolved.state_change_hints = []

            if resolved.world_entry_hints is None:
                resolved.world_entry_hints = []

            if resolved.final_status in {"failed", "blocked", "invalid", "cancelled"}:
                if not resolved.failure_reason:
                    resolved.failure_reason = "Reaction action did not complete."

            if resolved.final_status == "succeeded":
                resolved.failure_reason = None

            if resolved.blocking_actor_id is not None and resolved.blocking_actor_id not in present_character_ids:
                resolved.blocking_actor_id = None

            # Hard invariant: no retry after reaction resolver.
            resolved.requires_actor_retry = False
            resolved.retry_instruction = None

        # Failed records are allowed as final bookkeeping, but they must not route again.
        normalised_failed_records: list[FailedCharacterRecord] = []

        existing_failed_by_id = {
            failed.character_id: failed
            for failed in result.failed_characters or []
        }

        for resolved in result.resolved_actions:
            if resolved.final_status not in {"failed", "blocked", "invalid", "cancelled"}:
                continue

            existing_failed = existing_failed_by_id.get(resolved.actor_id)

            if existing_failed:
                existing_failed.retry_allowed = False
                if not existing_failed.reason:
                    existing_failed.reason = resolved.failure_reason or "Reaction action did not complete."
                if not existing_failed.failed_action_summary:
                    existing_failed.failed_action_summary = resolved.original_intent
                normalised_failed_records.append(existing_failed)
            else:
                normalised_failed_records.append(
                    FailedCharacterRecord(
                        character_id=resolved.actor_id,
                        character_name=resolved.actor_name,
                        failed_action_summary=resolved.original_intent,
                        reason=resolved.failure_reason or "Reaction action did not complete.",
                        retry_allowed=False,
                        retry_context=None,
                    )
                )

        # Preserve any model-provided failed records for actors not in resolved actions,
        # but mark non-retryable.
        resolved_failed_ids = {record.character_id for record in normalised_failed_records}

        for failed in result.failed_characters or []:
            if failed.character_id in resolved_failed_ids:
                continue

            failed.retry_allowed = False
            normalised_failed_records.append(failed)

        result.failed_characters = normalised_failed_records

        if result.conflicts is None:
            result.conflicts = []

        if result.state_update_suggestions is None:
            result.state_update_suggestions = []

        if result.pending_world_entry_suggestions is None:
            result.pending_world_entry_suggestions = []

        if result.narrator_context is None:
            result.narrator_context = []

        if not result.resolved_actions:
            result.accepted = False
            result.rejection_reason = "No reaction actions were resolved."

        if result.accepted and not result.rejection_reason:
            result.rejection_reason = None

        if not result.requires_director_rerun:
            result.director_rerun_reason = None

        # Second pass should not request another scheduling loop unless the round is incoherent.
        # Do not force requires_director_rerun false, but if true, require a reason.
        if result.requires_director_rerun and not result.director_rerun_reason:
            result.director_rerun_reason = (
                "Reaction resolver requested Director rerun without a reason; check round coherence."
            )

        return result

    def _user_input_resolution_to_resolver_output(
            self,
            output: UserInputResolutionOutput,
    ) -> ResolverOutput:
        return ResolverOutput(
            accepted=output.accepted,
            rejection_reason=output.rejection_reason,
            resolved_actions=[
                ResolvedAction.model_validate(action.model_dump())
                for action in output.resolved_actions
            ],
            conflicts=[
                conflict.model_dump()
                for conflict in output.conflicts
            ],
            failed_characters=[],
            scene_result_summary=output.scene_result_summary,
            next_round_note=output.next_round_note,
            narrator_context=output.narrator_context,
            state_update_suggestions=output.state_update_suggestions,
            pending_world_entry_suggestions=output.pending_world_entry_suggestions,
            requires_director_rerun=output.requires_director_rerun,
            director_rerun_reason=output.director_rerun_reason,
            notes=output.notes,
        )

    def _merge_resolver_outputs_for_downstream(
            self,
            primary: ResolverOutput,
            reaction: ResolverOutput | None = None,
    ) -> ResolverOutput:
        if reaction is None:
            return primary

        resolved_actions = [
            *primary.resolved_actions,
            *reaction.resolved_actions,
        ]

        conflicts = [
            *primary.conflicts,
            *reaction.conflicts,
        ]

        # First-pass failed characters that retried should not necessarily remain as
        # active final failures if their reaction succeeded. Keep only:
        # - non-retryable first-pass failures;
        # - first-pass failures whose actor has no reaction result;
        # - reaction-pass failures.
        reaction_actor_ids = {
            action.actor_id
            for action in reaction.resolved_actions
        }

        reaction_success_actor_ids = {
            action.actor_id
            for action in reaction.resolved_actions
            if action.final_status in {"succeeded", "partially_succeeded", "delayed"}
        }

        failed_characters: list[FailedCharacterRecord] = []

        for failed in primary.failed_characters:
            if failed.character_id in reaction_success_actor_ids:
                continue

            if failed.character_id in reaction_actor_ids and failed.retry_allowed:
                # This first-pass failure has been superseded by a reaction result.
                continue

            failed_characters.append(failed)

        for failed in reaction.failed_characters:
            failed.retry_allowed = False
            failed_characters.append(failed)

        narrator_context = [
            *primary.narrator_context,
            *reaction.narrator_context,
        ]

        state_update_suggestions = [
            *primary.state_update_suggestions,
            *reaction.state_update_suggestions,
        ]

        pending_world_entry_suggestions = [
            *primary.pending_world_entry_suggestions,
            *reaction.pending_world_entry_suggestions,
        ]

        scene_result_parts = [
            primary.scene_result_summary,
            reaction.scene_result_summary,
        ]

        next_round_parts = [
            primary.next_round_note,
            reaction.next_round_note,
        ]

        accepted = primary.accepted and reaction.accepted

        rejection_reason = None
        if not accepted:
            rejection_reasons = [
                reason
                for reason in [
                    primary.rejection_reason,
                    reaction.rejection_reason,
                ]
                if reason
            ]
            rejection_reason = " ".join(rejection_reasons) or "One resolver pass rejected the turn."

        requires_director_rerun = (
                primary.requires_director_rerun
                or reaction.requires_director_rerun
        )

        director_rerun_reason = None
        if requires_director_rerun:
            director_rerun_reason = " ".join(
                reason
                for reason in [
                    primary.director_rerun_reason,
                    reaction.director_rerun_reason,
                ]
                if reason
            ) or "Merged resolver output requires Director rerun."

        notes = "\n".join(
            note
            for note in [
                primary.notes,
                reaction.notes,
            ]
            if note
        )

        return ResolverOutput(
            accepted=accepted,
            rejection_reason=rejection_reason,
            resolved_actions=resolved_actions,
            conflicts=conflicts,
            failed_characters=failed_characters,
            scene_result_summary=" ".join(part for part in scene_result_parts if part),
            next_round_note=" ".join(part for part in next_round_parts if part),
            narrator_context=narrator_context,
            state_update_suggestions=state_update_suggestions,
            pending_world_entry_suggestions=pending_world_entry_suggestions,
            requires_director_rerun=requires_director_rerun,
            director_rerun_reason=director_rerun_reason,
            notes=notes,
        )

    def _build_narrator_resolution_view(
            self,
            resolver_output: ResolverOutput,
    ) -> NarratorResolutionView:
        events: list[NarratorResolvedEvent] = []

        for action in resolver_output.resolved_actions:
            if not action.visible_result:
                continue

            events.append(
                NarratorResolvedEvent(
                    actor_id=action.actor_id,
                    actor_name=action.actor_name,
                    final_status=action.final_status,
                    resolved_order=action.resolved_order,
                    visible_result=action.visible_result,
                    failure_reason=(
                        action.failure_reason
                        if action.final_status in {
                            "failed",
                            "blocked",
                            "invalid",
                            "cancelled",
                        }
                        else None
                    ),
                    blocking_actor_id=action.blocking_actor_id,
                    blocking_entity_id=action.blocking_entity_id,
                )
            )

        events.sort(
            key=lambda event: (
                event.resolved_order is None,
                event.resolved_order or 9999,
            )
        )

        return NarratorResolutionView(
            resolved_visible_events=events,
            safe_narrator_context=list(resolver_output.narrator_context or []),
            scene_result_summary=resolver_output.scene_result_summary,
            next_round_note=resolver_output.next_round_note,
        )

    def _build_narrator_recall_query(
            self,
            state: TurnGeneratorState,
            current_location: Location,
            narrator_resolution_view: NarratorResolutionView,
            user_input: str | None = None,
    ) -> str:
        parts: list[str] = [
            user_input or "",
            state.state.state if state.state else "",
            state.state.recent_history_summary if state.state else "",
            state.state.long_term_history_summary if state.state else "",
            current_location.primary_location,
            current_location.detailed_location,
            current_location.scene,
            current_location.description,
            narrator_resolution_view.scene_result_summary,
        ]

        for event in narrator_resolution_view.resolved_visible_events:
            parts.extend(
                [
                    event.actor_name,
                    event.final_status,
                    event.visible_result,
                    event.failure_reason or "",
                ]
            )

        parts.extend(narrator_resolution_view.safe_narrator_context or [])

        return "\n".join(part for part in parts if part)

    async def _persist_entity_update(
            self,
            *,
            simulation_id: int,
            entity_id: int | str,
            payload: dict[str, Any],
    ) -> None:
        location_id = payload.pop("location_id")

        # If you have a real entity repository, prefer it.
        entity_repo = getattr(self._db, "entity", None)
        if entity_repo is not None and hasattr(entity_repo, "update"):
            await entity_repo.update(
                entity_id,
                payload,
            )
            return

        if location_id is None:
            raise ValueError(
                f"Entity update for entity_id={entity_id} requires location_id "
                "when no self._db.entity.update repository exists."
            )

        location = await self._db.location.get(location_id)
        if not location:
            raise ValueError(
                f"Location id={location_id} not found for entity update of entity_id={entity_id}"
            )
        location_data = location.model_dump(mode="json")

        entities = list(location_data.get("entities") or [])
        updated = False

        for index, entity in enumerate(entities):
            if entity.get("id") == entity_id or entity.get("temp_id") == entity_id:
                entities[index] = {
                    **entity,
                    **payload,
                }
                updated = True
                break

        if not updated:
            raise ValueError(
                f"Entity id={entity_id} not found in location id={location_id}"
            )

        await self._db.location.update(
            location_id,
            {
                "entities": entities,
            },
        )

    async def _persist_inventory_update(
            self,
            *,
            simulation_id: int,
            owner_id: int | str,
            payload: dict[str, Any],
    ) -> None:
        owner_id = int(owner_id)

        if "items" in payload:
            await self._replace_inventory_items(
                simulation_id=simulation_id,
                owner_id=owner_id,
                items=payload["items"],
            )

        if "equipments" in payload:
            await self._replace_inventory_equipments(
                simulation_id=simulation_id,
                owner_id=owner_id,
                equipments=payload["equipments"],
            )

    async def _replace_inventory_items(
            self,
            *,
            simulation_id: int,
            owner_id: int,
            items: list[dict[str, Any]],
    ) -> None:
        # owner_id=0 means world inventory.
        if owner_id == 0:
            existing = await self._db.item.list(
                simulation_id=simulation_id,
            )
        else:
            existing = await self._db.item.list(
                character_id=owner_id,
            )

        existing_by_id = {
            item.id: item
            for item in existing
            if getattr(item, "id", None) is not None
        }

        incoming_ids = {
            item.get("id")
            for item in items
            if item.get("id") is not None
        }

        for existing_id in set(existing_by_id) - incoming_ids:
            await self._db.item.delete(existing_id)

        for item in items:
            item_data = dict(item)
            item_id = item_data.pop("id", None)
            item_data.pop("temp_id", None)

            if owner_id == 0:
                item_data["simulation_id"] = simulation_id
                item_data["character_id"] = None
            else:
                item_data["simulation_id"] = simulation_id
                item_data["character_id"] = owner_id

            if item_id is None:
                await self._db.item.create(item_data)
            else:
                await self._db.item.update(item_id, item_data)

    async def _replace_inventory_equipments(
            self,
            *,
            simulation_id: int,
            owner_id: int,
            equipments: list[dict[str, Any]],
    ) -> None:
        if owner_id == 0:
            existing = await self._db.equipment.list(
                simulation_id=simulation_id,
            )
        else:
            existing = await self._db.equipment.list(
                character_id=owner_id,
            )

        existing_by_id = {
            equipment.id: equipment
            for equipment in existing
            if getattr(equipment, "id", None) is not None
        }

        incoming_ids = {
            equipment.get("id")
            for equipment in equipments
            if equipment.get("id") is not None
        }

        for existing_id in set(existing_by_id) - incoming_ids:
            await self._db.equipment.delete(existing_id)

        for equipment in equipments:
            equipment_data = dict(equipment)
            equipment_id = equipment_data.pop("id", None)
            equipment_data.pop("temp_id", None)

            if owner_id == 0:
                equipment_data["simulation_id"] = simulation_id
                equipment_data["character_id"] = None
            else:
                equipment_data["simulation_id"] = simulation_id
                equipment_data["character_id"] = owner_id

            if equipment_id is None:
                await self._db.equipment.create(equipment_data)
            else:
                await self._db.equipment.update(equipment_id, equipment_data)

    async def _persist_update_mutation(
            self,
            *,
            simulation_id: int,
            object_type: str,
            object_id: int | str,
            payload: dict[str, Any],
            mutation: dict[str, Any],
    ) -> dict[str, Any]:
        if object_type == "state":
            await self._db.state.update(
                int(object_id),
                payload,
            )

        elif object_type == "character":
            await self._db.character.update(
                int(object_id),
                payload,
            )

        elif object_type == "location":
            await self._db.location.update(
                int(object_id),
                payload,
            )

        elif object_type == "task":
            await self._db.task.update(
                int(object_id),
                payload,
            )

        elif object_type == "world_entry":
            await self._db.entry.update(
                int(object_id),
                payload,
            )

        elif object_type == "faction":
            await self._db.faction.update(
                int(object_id),
                payload,
            )

        elif object_type == "faction_relationship":
            await self._db.faction_relationship.update(
                int(object_id),
                payload,
            )

        elif object_type == "inventory":
            await self._persist_inventory_update(
                simulation_id=simulation_id,
                owner_id=object_id,
                payload=payload,
            )

        elif object_type == "item":
            await self._db.item.update(
                int(object_id),
                payload,
            )

        elif object_type == "equipment":
            await self._db.equipment.update(
                int(object_id),
                payload,
            )

        elif object_type == "entity":
            await self._persist_entity_update(
                simulation_id=simulation_id,
                entity_id=object_id,
                payload=payload,
            )

        else:
            raise ValueError(
                f"Unsupported update target object_type={object_type!r}"
            )

        return {
            "mutation_id": mutation.get("mutation_id"),
            "operation": "update",
            "object_type": object_type,
            "object_id": object_id,
        }

    def _normalise_world_entry_payload(
            self,
            data: dict[str, Any],
    ) -> dict[str, Any]:
        data = dict(data)

        keywords = data.get("keywords")

        if keywords and all(isinstance(item, str) for item in keywords):
            data["keywords"] = [
                {
                    "keyword": item,
                    "similarity": 0.72,
                    "embedding": None,
                }
                for item in keywords
            ]

        data.setdefault("embedding", None)

        return data

    async def _persist_entity_create(
            self,
            *,
            simulation_id: int,
            payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = dict(payload)

        location_id = data.pop("location_id", None) or data.pop("proposed_location_id", None)
        if location_id is None:
            raise ValueError(
                "Creating an entity requires location_id or proposed_location_id."
            )

        entity_repo = getattr(self._db, "entity", None)
        if entity_repo is not None and hasattr(entity_repo, "create"):
            data["simulation_id"] = simulation_id
            data["location_id"] = location_id
            return await entity_repo.create(data)

        location = await self._db.location.get(location_id)
        location_data = location.model_dump(mode="json") if location else {}

        entities = list(location_data.get("entities") or [])

        # If entities are embedded, DB may not assign an entity ID here.
        # Use temp_id until a later normalisation/migration gives it a real ID.
        if data.get("id") is None and not data.get("temp_id"):
            data["temp_id"] = f"entity_{uuid4().hex[:12]}"

        entities.append(data)

        await self._db.location.update(
            location_id,
            {
                "entities": entities,
            },
        )

        return data

    async def _persist_create_mutation(
            self,
            *,
            simulation_id: int,
            object_type: str,
            object_id: int | str | None,
            payload: dict[str, Any],
            mutation: dict[str, Any],
            temp_id_map: dict[str, int],
    ) -> dict[str, Any]:
        data = dict(payload)
        temp_id = data.pop("temp_id", None)
        data.pop("id", None)

        created: Any

        if object_type == "location":
            data["simulation_id"] = simulation_id
            created = await self._db.location.create(data)

        elif object_type == "character":
            data["simulation_id"] = simulation_id
            created = await self._db.character.create(data)

        elif object_type == "world_entry":
            data["simulation_id"] = simulation_id
            data = self._normalise_world_entry_payload(data)
            created = await self._db.entry.create(data)

        elif object_type == "task":
            data["simulation_id"] = simulation_id
            created = await self._db.task.create(data)

        elif object_type == "faction":
            data["simulation_id"] = simulation_id
            created = await self._db.faction.create(data)

        elif object_type == "faction_relationship":
            created = await self._db.faction_relationship.create(data)

        elif object_type == "item":
            data["simulation_id"] = simulation_id
            created = await self._db.item.create(data)

        elif object_type == "equipment":
            data["simulation_id"] = simulation_id
            created = await self._db.equipment.create(data)

        elif object_type == "entity":
            created = await self._persist_entity_create(
                simulation_id=simulation_id,
                payload=data,
            )

        else:
            raise ValueError(
                f"Unsupported create object_type={object_type!r}"
            )

        created_id = getattr(created, "id", None)
        if created_id is None and isinstance(created, dict):
            created_id = created.get("id")

        if temp_id and created_id is not None:
            temp_id_map[str(temp_id)] = int(created_id)

        return {
            "mutation_id": mutation.get("mutation_id"),
            "operation": "create",
            "object_type": object_type,
            "object_id": created_id,
            "temp_id": temp_id,
        }

    async def _persist_remove_mutation(
            self,
            *,
            simulation_id: int,
            object_type: str,
            object_id: int | str,
            payload: dict[str, Any],
            mutation: dict[str, Any],
    ) -> dict[str, Any]:
        if object_type == "character":
            # Usually prefer soft update over delete for characters.
            await self._db.character.delete(int(object_id))

        elif object_type == "location":
            await self._db.location.delete(int(object_id))

        elif object_type == "task":
            await self._db.task.delete(int(object_id))

        elif object_type == "world_entry":
            await self._db.entry.delete(int(object_id))

        elif object_type == "faction":
            await self._db.faction.delete(int(object_id))

        elif object_type == "faction_relationship":
            await self._db.faction_relationship.delete(int(object_id))

        elif object_type == "item":
            await self._db.item.delete(int(object_id))

        elif object_type == "equipment":
            await self._db.equipment.delete(int(object_id))

        elif object_type == "entity":
            await self._persist_entity_remove(
                simulation_id=simulation_id,
                entity_id=object_id,
                payload=payload,
            )

        else:
            raise ValueError(
                f"Unsupported remove object_type={object_type!r}"
            )

        return {
            "mutation_id": mutation.get("mutation_id"),
            "operation": "remove",
            "object_type": object_type,
            "object_id": object_id,
        }

    async def _persist_entity_remove(
            self,
            *,
            simulation_id: int,
            entity_id: int | str,
            payload: dict[str, Any],
    ) -> None:
        entity_repo = getattr(self._db, "entity", None)
        if entity_repo is not None and hasattr(entity_repo, "delete"):
            await entity_repo.delete(entity_id)
            return

        location_id = payload.get("location_id")
        if location_id is None:
            raise ValueError(
                "Removing embedded entity requires location_id in payload."
            )

        location = await self._db.location.get(location_id)
        location_data = location.model_dump(mode="json") if location else {}

        entities = [
            entity
            for entity in location_data.get("entities", [])
            if entity.get("id") != entity_id
               and entity.get("temp_id") != entity_id
        ]

        await self._db.location.update(
            int(location_id),
            {
                "entities": entities,
            },
        )

    async def _persist_proposal_mutation(
            self,
            *,
            operation: str,
            object_id: int | str,
            payload: dict[str, Any],
            mutation: dict[str, Any],
    ) -> dict[str, Any]:
        status_by_operation = {
            "accept_proposal": "accepted",
            "reject_proposal": "rejected",
            "defer_proposal": "deferred",
        }

        status = status_by_operation[operation]

        proposal_repo = getattr(self._db, "generated_proposal", None)

        if proposal_repo is not None:
            if hasattr(proposal_repo, "update_by_temp_id"):
                await proposal_repo.update_by_temp_id(
                    object_id,
                    {
                        "status": status,
                    },
                )
            elif hasattr(proposal_repo, "update"):
                await proposal_repo.update(
                    object_id,
                    {
                        "status": status,
                    },
                )
            else:
                # Repository exists but does not expose a known update method.
                raise ValueError(
                    "generated_proposal repository has no supported update method."
                )

        return {
            "mutation_id": mutation.get("mutation_id"),
            "operation": operation,
            "proposal_id": object_id,
            "status": status,
        }

    async def _persist_single_committer_mutation(
            self,
            *,
            simulation_id: int,
            mutation: dict[str, Any],
            temp_id_map: dict[str, int],
    ) -> dict[str, Any]:
        operation = mutation["operation"]
        target = mutation.get("target") or {}
        payload = deepcopy(mutation.get("payload") or {})

        object_type = target.get("object_type")
        object_id = target.get("object_id")

        if isinstance(object_id, str) and object_id in temp_id_map:
            object_id = temp_id_map[object_id]

        if operation == "update":
            return await self._persist_update_mutation(
                simulation_id=simulation_id,
                object_type=object_type,
                object_id=object_id,
                payload=payload,
                mutation=mutation,
            )

        if operation == "create":
            return await self._persist_create_mutation(
                simulation_id=simulation_id,
                object_type=object_type,
                object_id=object_id,
                payload=payload,
                mutation=mutation,
                temp_id_map=temp_id_map,
            )

        if operation == "remove":
            return await self._persist_remove_mutation(
                simulation_id=simulation_id,
                object_type=object_type,
                object_id=object_id,
                payload=payload,
                mutation=mutation,
            )

        if operation in {
            "accept_proposal",
            "reject_proposal",
            "defer_proposal",
        }:
            return await self._persist_proposal_mutation(
                operation=operation,
                object_id=object_id,
                payload=payload,
                mutation=mutation,
            )

        raise ValueError(
            f"Unsupported committer mutation operation: {operation!r}"
        )

    def _build_wait_for_user_narration_context(
            self,
            *,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            present_characters: list[Character],
            director_output: DirectorOutput,
            user_input: str | None,
            last_narration: str | None,
            recalled_entries: list[WorldEntry],
    ) -> WaitForUserNarrationContext:
        return WaitForUserNarrationContext(
            simulation_name=simulation.name,
            simulation_description=simulation.description,
            time_label=state.time_label,
            scene_state=state.state,
            recent_history_summary=getattr(state, "recent_history_summary", None),
            long_term_history_summary=getattr(state, "long_term_history_summary", None),
            short_term_memory=getattr(state, "short_term_memory", None),
            long_term_memory=getattr(state, "long_term_memory", None),
            location_label=self._location_label(current_location),
            location_description=current_location.description,
            user_input=user_input,
            last_narration=last_narration,
            scene_focus=director_output.scene_focus,
            reason_to_wait=director_output.reason_to_wait,
            present_characters=[
                {
                    "id": character.id,
                    "name": character.name,
                    "public_state": character.public_state,
                    "user_controlled": character.user_controlled,
                }
                for character in present_characters
            ],
            visible_world_entries=[
                {
                    "id": entry.id,
                    "content": entry.content,
                    "visibility": entry.visibility,
                    "narration_permission": entry.narration_permission,
                }
                for entry in recalled_entries
                if -1 not in (entry.scope or [])
            ],
        )

    def _location_label(self, location: Location) -> str:
        parts = [
            getattr(location, "primary_location", None),
            getattr(location, "detailed_location", None),
            getattr(location, "scene", None),
        ]

        return " / ".join(part for part in parts if part) or f"Location {location.id}"

    def _compact_entity_for_user_input_resolver(self, entity: Any) -> dict[str, Any]:
        data = entity.model_dump() if hasattr(entity, "model_dump") else dict(entity)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "type": data.get("type"),
            "description": data.get("description"),
            "status": data.get("status"),
            "interactions": data.get("interactions", []),
        }

    def _compact_location_for_user_input_resolver(self, location: Location) -> dict[str, Any]:
        return {
            "id": location.id,
            "label": self._location_label(location),
            "description": location.description,
            "entities": [
                self._compact_entity_for_user_input_resolver(entity)
                for entity in (location.entities or [])
            ],
        }

    def _compact_character_for_user_input_resolver(
            self,
            character: Character,
            inventory: CharacterInventory | None = None,
    ) -> dict[str, Any]:
        return {
            "id": character.id,
            "name": character.name,
            "user_controlled": character.user_controlled,
            "location": character.location,
            "public_state": character.public_state,
            "private_state": character.private_state,
            "attributes": character.attributes,
            "stats": character.stats,
            "inventory": self._compact_inventory_for_user_input_resolver(inventory),
        }

    def _compact_inventory_for_user_input_resolver(
            self,
            inventory: CharacterInventory | None,
    ) -> dict[str, Any]:
        if inventory is None:
            return {
                "items": [],
                "equipments": [],
            }

        return {
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "quantity": item.quantity,
                    "quality": item.quality,
                }
                for item in (inventory.items or [])
            ],
            "equipments": [
                {
                    "id": equipment.id,
                    "name": equipment.name,
                    "description": equipment.description,
                    "status": equipment.status,
                    "quality": equipment.quality,
                }
                for equipment in (inventory.equipments or [])
            ],
        }

    def _compact_task_for_user_input_resolver(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "character_ids": task.character_ids,
            "private": task.private,
            "priority": task.priority,
            "status": task.status,
            "goal": task.goal,
            "progress": task.progress,
            "source": task.source,
        }

    def _compact_world_entry_for_user_input_resolver(self, entry: WorldEntry) -> dict[str, Any]:
        return {
            "id": entry.id,
            "scope": entry.scope,
            "content": entry.content,
            "visibility": entry.visibility,
            "confidence": entry.confidence,
            "narration_permission": entry.narration_permission,
            "recall_type": entry.recall_type,
        }

    def _build_user_input_failure_narration_context(
            self,
            *,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            player_character: Character | None,
            user_input: str,
            user_input_resolution: UserInputResolutionOutput,
            last_narration: str | None,
            recalled_entries: list[WorldEntry],
    ) -> UserInputFailureNarrationContext:
        return UserInputFailureNarrationContext(
            simulation_name=simulation.name,
            simulation_description=simulation.description,
            time_label=state.time_label,
            state_summary=state.state,
            short_term_memory=getattr(state, "short_term_memory", None),
            long_term_memory=getattr(state, "long_term_memory", None),
            recent_history_summary=getattr(state, "recent_history_summary", None),
            long_term_history_summary=getattr(state, "long_term_history_summary", None),
            location_label=self._location_label(current_location),
            location_description=current_location.description,
            player_character=(
                {
                    "id": player_character.id,
                    "name": player_character.name,
                    "public_state": player_character.public_state,
                    "location": player_character.location,
                    "user_controlled": player_character.user_controlled,
                }
                if player_character is not None
                else None
            ),
            user_input=user_input,
            input_kind=user_input_resolution.input_kind,
            legality=user_input_resolution.legality,
            rejection_reason=user_input_resolution.rejection_reason,
            user_retry_instruction=user_input_resolution.user_retry_instruction,
            conflicts=[
                conflict.model_dump()
                if hasattr(conflict, "model_dump")
                else dict(conflict)
                for conflict in user_input_resolution.conflicts
            ],
            blocked_actions=[
                action.model_dump()
                if hasattr(action, "model_dump")
                else dict(action)
                for action in user_input_resolution.resolved_actions
                if getattr(action, "final_status", None)
                   in {"failed", "blocked", "invalid", "cancelled"}
            ],
            last_narration=last_narration,
            visible_world_entries=[
                {
                    "id": entry.id,
                    "content": entry.content,
                    "visibility": entry.visibility,
                    "narration_permission": entry.narration_permission,
                }
                for entry in recalled_entries
                if -1 not in (entry.scope or [])
            ],
        )

    async def load_simulation(self, state: TurnGeneratorState) -> dict:
        simulation = await self._db.simulation.get(state.simulation_id)
        simulation_state = await self._db.state.get(state.simulation_id)

        if simulation is None or simulation_state is None:
            raise ValueError(f"Simulation {state.simulation_id} not found")

        connection_ids = {
            simulation.agent_preset.director.backend_configuration.connection,
            simulation.agent_preset.memory.backend_configuration.connection,
            simulation.agent_preset.character.backend_configuration.connection,
            simulation.agent_preset.resolver.backend_configuration.connection,
            simulation.agent_preset.committer.backend_configuration.connection,
            simulation.agent_preset.narrator.backend_configuration.connection,
            simulation.agent_preset.world_generator.backend_configuration.connection,
            simulation.embedding_profile.connection,
        }

        connections = {}
        for connection_id in connection_ids:
            if connection_id is None:
                raise ValueError("Not all connections are configured")

            connection = await self._db.connection.llm.get(connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            connections[connection_id] = connection

        return {
            "simulation": simulation,
            "state": simulation_state,
            "connection_profiles": ConnectionProfileCache(
                director=connections[simulation.agent_preset.director.backend_configuration.connection],
                memory=connections[simulation.agent_preset.memory.backend_configuration.connection],
                character=connections[simulation.agent_preset.character.backend_configuration.connection],
                resolver=connections[simulation.agent_preset.resolver.backend_configuration.connection],
                committer=connections[simulation.agent_preset.committer.backend_configuration.connection],
                narrator=connections[simulation.agent_preset.narrator.backend_configuration.connection],
                world_generator=connections[simulation.agent_preset.world_generator.backend_configuration.connection],
                embedding=connections[simulation.embedding_profile.connection],
            ),
        }

    async def director_planning(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.director is None:
            raise RuntimeError("Director connection profile not loaded")

        director_agent = DirectorAgent(
            profile=state.simulation.agent_preset.director,
            connection=state.connection_profiles.director,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.connection_profiles.world_generator is None:
            raise RuntimeError("World generator connection profile not loaded")

        generator = WorldGeneratorAgent(
            profile=state.simulation.agent_preset.world_generator,
            connection=state.connection_profiles.world_generator,
        )

        present_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            location=state.state.scene,
        )
        user_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            controlled_by_user=True,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation_id,
        )

        tasks = await self._db.task.list(
            character_ids=[c.id for c in present_characters],
        )

        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.id for c in present_characters],
        )

        if state.user_input:
            recall_query = state.user_input
        elif last_records:
            recall_query = last_records[0].narration
        else:
            recall_query = None

        recalled_entries = await recaller.recall(
            query=recall_query,
            entries=world_entries,
            language=state.simulation.language,
        )

        # Full context only for generation/tool-gating.
        all_locations = await self._db.location.list(
            simulation_id=state.simulation_id,
        )

        existing_items = await self._db.item.list(
            simulation_id=state.simulation_id,
            include_character_items=True,
        )

        existing_equipments = await self._db.equipment.list(
            simulation_id=state.simulation_id,
            include_character_equipment=True,
        )

        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation_id,
            character_ids=[c.id for c in present_characters],
            item_ids=[i.id for i in existing_items],
            include_private=True,
        )

        generator_tools = generator.get_tools(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=all_locations,
            existing_entities=current_location.entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            entity_types=state.simulation.data_preset.entity_types.keys(),
        )

        output, proposals = await director_agent.plan_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            user_characters=user_characters,
            present_characters=present_characters,
            relevant_tasks=tasks,
            recalled_world_entries=recalled_entries,
            generation_tools=generator_tools,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        if not state.simulation.act_for_user:
            for activation in output.activations:
                character = next(
                    (c for c in present_characters if c.id == activation.character_id),
                    None,
                )

                if character and character.user_controlled:
                    activation.activate = False
                    activation.priority = 0
                    activation.reason = "User-controlled character. System policy prevents autonomous activation."
                    activation.private_motive_used = False

        return {
            "director_output": output,
            "generated_proposals": proposals,
        }

    async def memory_briefing(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.memory is None:
            raise RuntimeError("Memory connection profile not loaded")

        memory_agent = MemoryAgent(
            profile=state.simulation.agent_preset.memory,
            connection=state.connection_profiles.memory,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.director_output is None:
            raise RuntimeError("Director output not generated")

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")

        active_character_ids = [
            activation.character_id
            for activation in state.director_output.activations
            if activation.activate
        ]

        active_characters: list[Character] = []
        if active_character_ids:
            active_characters = await self._db.character.list(
                simulation_id=state.simulation_id,
                character_ids=active_character_ids,
            )

        if not active_characters:
            return {
                "briefing_output": BriefingOutput(
                    briefings=[],
                    notes="No active characters selected by Director.",
                ),
            }

        public_factions, public_faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation_id,
            character_ids=active_character_ids,
            include_private=False,
        )

        public_tasks = await self._db.task.list(
            character_ids=[character.id for character in active_characters],
            private=False,
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation_id,
        )

        candidate_world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [character.id for character in active_characters],
        )

        def is_safe_public_entry(entry: WorldEntry) -> bool:
            """
            Defensive local filter for the public briefing layer.

            This does not replace your database visibility model; it prevents accidental
            leakage if entry.list returns scoped private entries together with public ones.
            Adjust allowed visibility/narration values to match your exact enum names.
            """
            visibility = getattr(entry, "visibility", None)
            narration_permission = getattr(entry, "narration_permission", None)
            private = getattr(entry, "private", False)

            if private:
                return False

            if visibility is not None:
                visibility_value = str(visibility).lower()
                if visibility_value in {
                    "hidden",
                    "secret",
                    "private",
                    "unknown",
                    "director_only",
                }:
                    return False

            if narration_permission is not None:
                narration_value = str(narration_permission).lower()
                if narration_value in {
                    "hidden",
                    "forbidden",
                    "never",
                    "private",
                    "director_only",
                }:
                    return False

            return True

        safe_world_entries = [
            entry
            for entry in candidate_world_entries
            if is_safe_public_entry(entry)
        ]

        if state.user_input:
            recall_query = f"{state.director_output.scene_focus}\n{state.user_input}"
        elif last_records:
            recall_query = f"{state.director_output.scene_focus}\n{last_records[0].narration}"
        else:
            recall_query = state.director_output.scene_focus

        recalled_entries = await recaller.recall(
            query=recall_query,
            entries=safe_world_entries,
            language=state.simulation.language,
        )

        result = await memory_agent.build_briefings(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=active_characters,
            tasks=public_tasks,
            world_entries=recalled_entries,
            director_output=state.director_output,
            factions=public_factions,
            faction_relationships=public_faction_relationships,
            pending_generated_proposals=state.generated_proposals,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        return {
            "briefing_output": result,
        }

    async def memory_summary(self, state: TurnGeneratorState):
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if state.narration is None:
            raise RuntimeError("Narration is not generated")

        if state.connection_profiles.memory is None:
            raise RuntimeError("Memory connection profile not loaded")

        memory_agent = MemoryAgent(
            profile=state.simulation.agent_preset.memory,
            connection=state.connection_profiles.memory,
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation_id,
            last_n=10,
        )

        result = await memory_agent.build_summary(
            last_turns=last_records,
            narration=state.narration,
            state=state.state,
        )

        return {
            "summary_output": result,
        }

    async def character_action(self, state: CharacterActionState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.character is None:
            raise RuntimeError("Character connection profile not loaded")

        character_agent = CharacterAgent(
            profile=state.simulation.agent_preset.character,
            connection=state.connection_profiles.character,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        character = await self._db.character.get(state.briefing.character_id)
        if not character:
            raise ValueError(f"Character {state.briefing.character_id} not found")

        if character.user_controlled and not state.simulation.act_for_user:
            raise RuntimeError(
                f"Character {character.id} is user-controlled and autonomous acting is disabled"
            )

        current_location = await self._db.location.get(character.location)
        if not current_location:
            raise ValueError(f"Current location {character.location} does not exist")

        present_characters = await self._db.character.list(
            simulation_id=state.simulation.id,
            location=character.location,
        )

        visible_characters = [
            c
            for c in present_characters
            if c.id != character.id
        ]

        visible_character_ids = [
            c.id
            for c in visible_characters
        ]

        # Character agents should receive their own tasks, including private tasks.
        # Do not pass private tasks belonging only to other characters.
        candidate_tasks = await self._db.task.list(
            character_ids=[character.id],
        )

        tasks = [
            task
            for task in candidate_tasks
            if character.id in task.character_ids
        ]

        # Character agents may receive:
        # - public/global entries, scope [0];
        # - entries scoped to themselves;
        # - never GM-only scope [-1];
        # - never private entries scoped only to other characters.
        candidate_world_entries = await self._db.entry.list(
            simulation_id=state.simulation.id,
            search_scope=[0, character.id],
        )

        def entry_visible_to_character(entry: WorldEntry, character_id: int) -> bool:
            scopes = set(entry.scope or [])

            if -1 in scopes:
                return False

            if 0 in scopes:
                return True

            if character_id in scopes:
                return True

            return False

        safe_candidate_world_entries = [
            entry
            for entry in candidate_world_entries
            if entry_visible_to_character(entry, character.id)
        ]

        recall_parts = [
            state.briefing.scene_context,
            state.briefing.recent_context,
            state.briefing.known_relevant_facts,
            state.briefing.immediate_situation,
            state.briefing.instruction,
            state.user_input or "",
        ]

        if state.briefing.available_interactions:
            recall_parts.append(
                "Available interactions: "
                + "; ".join(state.briefing.available_interactions)
            )

        if tasks:
            recall_parts.append(
                "Relevant task goals: "
                + "; ".join(
                    task.goal
                    for task in tasks
                    if getattr(task, "goal", None)
                )
            )

        recall_query = "\n".join(
            part
            for part in recall_parts
            if part
        )

        recalled_world_entries = await recaller.recall(
            query=recall_query or None,
            entries=safe_candidate_world_entries,
            language=state.simulation.language,
        )

        # Preserve any public world entries already selected by Memory, but only
        # if they are still visible to this character. This avoids losing useful
        # public context while still preventing accidental leakage.
        briefing_world_entries: list[WorldEntry] = []
        if state.briefing.relevant_world_entry_ids:
            briefing_world_entries = await self._db.entry.list(
                entry_ids=state.briefing.relevant_world_entry_ids,
            )

        merged_world_entries_by_id: dict[int, WorldEntry] = {}

        for entry in briefing_world_entries + recalled_world_entries:
            if entry_visible_to_character(entry, character.id):
                merged_world_entries_by_id[entry.id] = entry

        world_entries = list(merged_world_entries_by_id.values())

        # Inventory/equipment are scoped to the acting character only.
        inventory = await self._db.item.list(
            character_id=character.id,
        )

        equipments = await self._db.equipment.list(
            character_id=character.id,
        )

        factions, faction_relationships = await self._load_character_faction_context(
            simulation_id=state.simulation.id,
            acting_character_id=character.id,
            visible_character_ids=visible_character_ids,
            item_ids=[item.id for item in inventory],
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        result = await character_agent.generate_action(
            character=character,
            briefing=state.briefing,
            current_location=current_location,
            visible_characters=visible_characters,
            tasks=tasks,
            world_entries=world_entries,
            inventory=inventory,
            equipments=equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            proposals=state.generated_proposals or [],
            data_preset=state.simulation.data_preset,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        result = self._normalise_character_action_output(
            result=result,
            character=character,
            visible_characters=visible_characters,
            current_location=current_location,
            inventory=inventory,
        )

        return {
            "character_action_outputs": [result],
        }

    async def character_reaction(self, state: CharacterReactionState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.character is None:
            raise RuntimeError("Character connection profile not loaded")

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        if not state.reaction_context.failure_record.retry_allowed:
            return {
                "character_reaction_outputs": []
            }

        character_agent = CharacterAgent(
            profile=state.simulation.agent_preset.character,
            connection=state.connection_profiles.character,
        )

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        character = await self._db.character.get(state.reaction_context.character_id)
        if not character:
            raise ValueError(f"Character {state.reaction_context.character_id} not found")

        if character.user_controlled and not state.simulation.act_for_user:
            raise RuntimeError(
                f"Character {character.id} is user-controlled and autonomous reaction is disabled"
            )

        current_location = await self._db.location.get(character.location)
        if not current_location:
            raise ValueError(f"Current location {character.location} does not exist")

        present_characters = await self._db.character.list(
            simulation_id=state.simulation.id,
            location=character.location,
        )

        visible_characters = [
            c
            for c in present_characters
            if c.id != character.id
        ]

        visible_character_ids = [
            c.id
            for c in visible_characters
        ]

        # Reaction agent receives the acting character's own tasks, including private.
        # Public briefing task IDs may be incomplete because Memory is public-safe.
        candidate_tasks = await self._db.task.list(
            character_ids=[character.id],
        )

        tasks = [
            task
            for task in candidate_tasks
            if character.id in task.character_ids
        ]

        # Character reaction must not see GM-only entries or other-character-only entries.
        candidate_world_entries = await self._db.entry.list(
            simulation_id=state.simulation.id,
            search_scope=[0, character.id],
        )

        def entry_visible_to_character(entry: WorldEntry, character_id: int) -> bool:
            scopes = set(entry.scope or [])

            if -1 in scopes:
                return False

            if 0 in scopes:
                return True

            if character_id in scopes:
                return True

            return False

        safe_candidate_world_entries = [
            entry
            for entry in candidate_world_entries
            if entry_visible_to_character(entry, character.id)
        ]

        recall_query = self._build_character_reaction_recall_query(
            state=state,
            character=character,
            current_location=current_location,
            tasks=tasks,
        )

        recalled_world_entries = await recaller.recall(
            query=recall_query,
            entries=safe_candidate_world_entries,
            language=state.simulation.language,
        )

        # Preserve any explicitly referenced briefing/reaction entries, but only if visible to this character.
        context_world_entries: list[WorldEntry] = []
        if state.reaction_context.relevant_world_entry_ids:
            context_world_entries = await self._db.entry.list(
                entry_ids=state.reaction_context.relevant_world_entry_ids,
            )

        world_entries_by_id: dict[int, WorldEntry] = {}

        for entry in context_world_entries + recalled_world_entries:
            if entry_visible_to_character(entry, character.id):
                world_entries_by_id[entry.id] = entry

        world_entries = list(world_entries_by_id.values())

        inventory = await self._db.item.list(
            character_id=character.id,
        )

        equipments = await self._db.equipment.list(
            character_id=character.id,
        )

        factions, faction_relationships = await self._load_character_faction_context(
            simulation_id=state.simulation.id,
            acting_character_id=character.id,
            visible_character_ids=visible_character_ids,
            item_ids=[item.id for item in inventory],
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        result = await character_agent.generate_reaction(
            character=character,
            reaction_context=state.reaction_context,
            current_location=current_location,
            visible_characters=visible_characters,
            tasks=tasks,
            world_entries=world_entries,
            inventory=inventory,
            equipments=equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            proposals=state.generated_proposals or [],
            data_preset=state.simulation.data_preset,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        result = self._normalise_character_reaction_output(
            result=result,
            character=character,
            visible_characters=visible_characters,
            current_location=current_location,
            inventory=inventory,
            equipments=equipments,
            reaction_context=state.reaction_context,
        )

        return {
            "character_reaction_outputs": [result]
        }

    async def resolve_character_actions(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.briefing_output:
            raise RuntimeError("Briefing output is not generated")

        if not state.character_action_outputs:
            raise RuntimeError("Character action outputs is not generated")

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Resolver connection profile not loaded")

        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")

        # Resolver needs all present characters, not only acting characters.
        present_characters = await self._db.character.list(
            simulation_id=state.simulation.id,
            location=state.state.scene,
        )

        present_character_ids = [character.id for character in present_characters]
        acting_character_ids = [action.character_id for action in state.character_action_outputs]

        acting_character_id_set = set(acting_character_ids)
        present_character_id_set = set(present_character_ids)

        # Normalise character actions enough to avoid schema/None issues,
        # but do not silently remove suspicious content. Resolver should see validation reports.
        character_actions = [
            self._normalise_action_for_resolver_input(
                action=action,
            )
            for action in state.character_action_outputs
        ]

        # Inventory/equipment for all present characters, because:
        # - actions may target non-acting characters;
        # - resolver needs access/possession context;
        # - user-controlled characters may be targets.
        inventory: dict[int, CharacterInventory] = {}
        all_item_ids: list[int] = []

        for character in present_characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)

            all_item_ids.extend(item.id for item in items)

            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )

        # Resolver is system-side / rule-engine-side, so it may see private and GM-only context.
        # Use recall to keep the prompt bounded, but include [-1] so hidden truth can be recalled.
        candidate_world_entries = await self._db.entry.list(
            simulation_id=state.simulation.id,
            search_scope=[-1, 0] + present_character_ids,
        )

        resolver_recall_query = self._build_resolver_recall_query(
            state=state,
            current_location=current_location,
            character_actions=character_actions,
        )

        recalled_world_entries = await recaller.recall(
            query=resolver_recall_query,
            entries=candidate_world_entries,
            language=state.simulation.language,
        )

        # Add briefing entries back in if they are available; these are usually public-safe,
        # but Resolver can receive them anyway.
        briefing_world_entry_ids: set[int] = set()
        for briefing in state.briefing_output.briefings:
            briefing_world_entry_ids |= set(briefing.relevant_world_entry_ids or [])

        briefing_world_entries: list[WorldEntry] = []
        if briefing_world_entry_ids:
            briefing_world_entries = await self._db.entry.list(
                entry_ids=list(briefing_world_entry_ids),
            )

        world_entries_by_id: dict[int, WorldEntry] = {}

        for entry in recalled_world_entries + briefing_world_entries:
            world_entries_by_id[entry.id] = entry

        resolver_world_entries = list(world_entries_by_id.values())

        # For OOC/context-leak detection: what each actor could legitimately know.
        actor_knowledge_index = self._build_actor_knowledge_index(
            acting_character_ids=acting_character_ids,
            world_entries=resolver_world_entries,
        )

        action_validation_reports = self._build_action_validation_reports(
            actions=character_actions,
            present_characters=present_characters,
            current_location=current_location,
            inventory=inventory,
            actor_knowledge_index=actor_knowledge_index,
        )

        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation.id,
            character_ids=present_character_ids,
            item_ids=all_item_ids,
            include_private=True,
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        result = await resolver_agent.resolve_character_actions(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=present_characters,
            character_actions=character_actions,
            proposals=state.generated_proposals or [],
            inventory=inventory,
            world_entries=resolver_world_entries,
            actor_knowledge_index=actor_knowledge_index,
            action_validation_reports=action_validation_reports,
            factions=factions,
            faction_relationships=faction_relationships,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        result = self._normalise_resolver_output(
            result=result,
            character_actions=character_actions,
            present_character_ids=present_character_id_set,
        )

        return {
            "resolver_output": result,
        }

    async def resolve_character_reactions(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.character_reaction_outputs:
            raise RuntimeError("Character reaction outputs are not generated")

        if not state.resolver_output:
            raise RuntimeError("Resolver output is not generated")

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Resolver connection profile not loaded")

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")

        # Reaction resolver needs all present characters because reactions may target
        # previous actors, blockers, user-controlled characters, or bystanders.
        present_characters = await self._db.character.list(
            simulation_id=state.simulation.id,
            location=state.state.scene,
        )

        present_character_ids = [character.id for character in present_characters]
        present_character_id_set = set(present_character_ids)

        reaction_actions = [
            self._normalise_action_for_resolver_input(action)
            for action in state.character_reaction_outputs
        ]

        reaction_actor_ids = [action.character_id for action in reaction_actions]

        inventory: dict[int, CharacterInventory] = {}
        all_item_ids: list[int] = []

        for character in present_characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)

            all_item_ids.extend(item.id for item in items)

            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )

        # Second-pass resolver is system-side, so it may see hidden GM-only entries.
        candidate_world_entries = await self._db.entry.list(
            simulation_id=state.simulation.id,
            search_scope=[-1, 0] + present_character_ids,
        )

        resolver_recall_query = self._build_reaction_resolver_recall_query(
            state=state,
            current_location=current_location,
            reaction_actions=reaction_actions,
        )

        recalled_world_entries = await recaller.recall(
            query=resolver_recall_query,
            entries=candidate_world_entries,
            language=state.simulation.language,
        )

        # Add entries referenced by the previous normal resolver's originating briefings if available.
        # These are not enough by themselves, but useful to preserve context.
        briefing_world_entry_ids: set[int] = set()
        if state.briefing_output:
            for briefing in state.briefing_output.briefings:
                briefing_world_entry_ids |= set(briefing.relevant_world_entry_ids or [])

        briefing_world_entries: list[WorldEntry] = []
        if briefing_world_entry_ids:
            briefing_world_entries = await self._db.entry.list(
                entry_ids=list(briefing_world_entry_ids),
            )

        world_entries_by_id: dict[int, WorldEntry] = {}

        for entry in recalled_world_entries + briefing_world_entries:
            world_entries_by_id[entry.id] = entry

        resolver_world_entries = list(world_entries_by_id.values())

        actor_knowledge_index = self._build_actor_knowledge_index(
            acting_character_ids=reaction_actor_ids,
            world_entries=resolver_world_entries,
        )

        action_validation_reports = self._build_reaction_validation_reports(
            actions=reaction_actions,
            present_characters=present_characters,
            current_location=current_location,
            inventory=inventory,
            actor_knowledge_index=actor_knowledge_index,
            previous_resolver_output=state.resolver_output,
        )

        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation.id,
            character_ids=present_character_ids,
            item_ids=all_item_ids,
            include_private=True,
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        result = await resolver_agent.resolve_character_reactions(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=present_characters,
            character_reactions=reaction_actions,
            previous_resolver_output=state.resolver_output,
            proposals=state.generated_proposals or [],
            inventory=inventory,
            world_entries=resolver_world_entries,
            actor_knowledge_index=actor_knowledge_index,
            action_validation_reports=action_validation_reports,
            factions=factions,
            faction_relationships=faction_relationships,
            last_narration=last_records[0].narration if last_records else None,
            previous_resolver_notes=last_records[0].resolver_output.next_round_note if last_records else None,
        )

        result = self._normalise_reaction_resolver_output(
            result=result,
            reaction_actions=reaction_actions,
            present_character_ids=present_character_id_set,
        )

        return {
            "reaction_resolver_output": result,
        }

    async def resolve_user_input(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.user_input or not state.user_input.strip():
            return {
                "user_input_resolution": UserInputResolutionOutput(
                    accepted=True,
                    input_kind="no_action",
                    legality="legal",
                    scene_result_summary="No explicit user action was provided.",
                    next_round_note="Director should decide whether the scene needs player input or can continue.",
                )
            }

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Resolver connection profile not loaded")

        simulation_id = state.simulation_id

        current_location = await self._db.location.get(state.state.scene)
        if current_location is None:
            raise RuntimeError(f"Current location {state.state.scene} not found")

        all_characters = await self._db.character.list(
            simulation_id=simulation_id,
        )

        present_characters = await self._db.character.list(
            simulation_id=simulation_id,
            location=state.state.scene,
        )

        player_character = next(
            (character for character in all_characters if character.user_controlled),
            None,
        )

        locations = await self._db.location.list(
            simulation_id=simulation_id,
        )

        tasks = await self._db.task.list(
            simulation_id=simulation_id,
        )

        inventory_by_character_id: dict[int, CharacterInventory] = {}

        for character in all_characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)
            inventory_by_character_id[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )

        # World inventory, owner 0, useful for checking if an item exists somewhere in the world.
        world_items = await self._db.item.list(simulation_id=simulation_id)
        world_equipments = await self._db.equipment.list(simulation_id=simulation_id)
        world_inventory = CharacterInventory(
            items=world_items,
            equipments=world_equipments,
        )

        # Visible entries: public + player-specific only.
        visible_scope = [0]
        if player_character is not None:
            visible_scope.append(player_character.id)

        visible_world_entries = await self._db.entry.list(
            simulation_id=simulation_id,
            search_scope=visible_scope,
            narration_only=True,
        )

        # Resolver entries: can include hidden [-1] plus all present characters and player.
        resolver_scope = [-1, 0]
        resolver_scope.extend(character.id for character in present_characters)
        if player_character is not None and player_character.id not in resolver_scope:
            resolver_scope.append(player_character.id)

        resolver_world_entries = await self._db.entry.list(
            simulation_id=simulation_id,
            search_scope=resolver_scope,
        )

        context = UserInputResolverContext(
            simulation_name=state.simulation.name,
            simulation_description=state.simulation.description,
            language=state.simulation.language,
            user_input=state.user_input,
            time_label=state.state.time_label,
            state_summary=state.state.state,
            recent_history_summary=state.state.recent_history_summary,
            long_term_history_summary=state.state.long_term_history_summary,
            short_term_memory=getattr(state.state, "short_term_memory", None),
            long_term_memory=getattr(state.state, "long_term_memory", None),
            current_location=self._compact_location_for_user_input_resolver(current_location),
            player_character=(
                self._compact_character_for_user_input_resolver(
                    player_character,
                    inventory_by_character_id.get(player_character.id),
                )
                if player_character is not None
                else None
            ),
            present_characters=[
                self._compact_character_for_user_input_resolver(
                    character,
                    inventory_by_character_id.get(character.id),
                )
                for character in present_characters
            ],
            all_characters=[
                self._compact_character_for_user_input_resolver(
                    character,
                    inventory_by_character_id.get(character.id),
                )
                for character in all_characters
            ],
            locations=[
                self._compact_location_for_user_input_resolver(location)
                for location in locations
            ],
            inventory={
                "world": self._compact_inventory_for_user_input_resolver(world_inventory),
                "characters": {
                    str(character_id): self._compact_inventory_for_user_input_resolver(inventory)
                    for character_id, inventory in inventory_by_character_id.items()
                },
            },
            tasks=[
                self._compact_task_for_user_input_resolver(task)
                for task in tasks
            ],
            visible_world_entries=[
                self._compact_world_entry_for_user_input_resolver(entry)
                for entry in visible_world_entries
                if -1 not in (entry.scope or [])
            ],
            resolver_world_entries=[
                self._compact_world_entry_for_user_input_resolver(entry)
                for entry in resolver_world_entries
            ],
        )

        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )

        result = await resolver_agent.resolve_user_input(
            context=context,
        )

        return {
            "user_input_resolution": result,
        }

    async def commit_changes(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.committer is None:
            raise RuntimeError("Committer connection profile not loaded")

        if state.resolver_output is None:
            raise RuntimeError("Resolver output is not generated")

        simulation_id = state.simulation.id

        effective_resolver_output = self._merge_resolver_outputs_for_downstream(
            primary=state.resolver_output,
            reaction=state.reaction_resolver_output,
        )

        effective_character_actions = [
            *(state.character_action_outputs or []),
            *(state.character_reaction_outputs or []),
        ]

        characters = await self._db.character.list(
            simulation_id=simulation_id,
        )

        locations = await self._db.location.list(
            simulation_id=simulation_id,
        )

        tasks = await self._db.task.list(
            simulation_id=simulation_id,
        )

        world_entries = await self._db.entry.list(
            simulation_id=simulation_id,
        )

        factions = await self._db.faction.list(
            simulation_id=simulation_id,
        )

        faction_relationships = await self._db.faction_relationship.list(
            simulation_id=simulation_id,
        )

        inventory: dict[int, CharacterInventory] = {}

        world_items = await self._db.item.list(
            simulation_id=simulation_id,
        )

        world_equipments = await self._db.equipment.list(
            simulation_id=simulation_id,
        )

        inventory[0] = CharacterInventory(
            items=world_items,
            equipments=world_equipments,
        )

        for character in characters:
            items = await self._db.item.list(
                character_id=character.id,
            )

            equipments = await self._db.equipment.list(
                character_id=character.id,
            )

            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )

        committer_agent = CommitterAgent(
            profile=state.simulation.agent_preset.committer,
            connection=state.connection_profiles.committer,
            simulation=state.simulation,
            state=state.state,
            characters=characters,
            locations=locations,
            inventory=inventory,
            factions=factions,
            faction_relationships=faction_relationships,
            tasks=tasks,
            world_entries=world_entries,
        )

        result = await committer_agent.commit_changes(
            user_input=state.user_input,
            character_actions=effective_character_actions,
            resolver_output=effective_resolver_output,
            pending_generated_proposals=state.generated_proposals or [],
        )

        return {
            "committer_output": result,
        }

    async def narrate_resolved_turn(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.resolver_output:
            raise RuntimeError("Resolver output is not generated")

        if state.connection_profiles.narrator is None:
            raise RuntimeError("Narrator connection profile not loaded")

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        narrator_agent = NarratorAgent(
            profile=state.simulation.agent_preset.narrator,
            connection=state.connection_profiles.narrator,
        )

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")

        effective_resolver_output = self._merge_resolver_outputs_for_downstream(
            primary=state.resolver_output,
            reaction=state.reaction_resolver_output,
        )

        narrator_resolution_view = self._build_narrator_resolution_view(
            resolver_output=effective_resolver_output,
        )

        involved_character_ids = {
            event.actor_id
            for event in narrator_resolution_view.resolved_visible_events
        }

        for action in state.character_action_outputs or []:
            involved_character_ids.add(action.character_id)

        for action in state.character_reaction_outputs or []:
            involved_character_ids.add(action.character_id)

        # Usually the player should be present in the scene even if they did not act
        # as an autonomous character.
        present_characters = await self._db.character.list(
            simulation_id=state.simulation.id,
            location=state.state.scene,
        )

        present_character_ids = {
            character.id
            for character in present_characters
        }

        involved_character_ids |= present_character_ids

        characters = [
            character
            for character in present_characters
            if character.id in involved_character_ids
        ]

        # Adjust this to your own way of identifying the player character.
        player_character = next(
            (
                character
                for character in present_characters
                if character.user_controlled
            ),
            None,
        )

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        # Narrator-safe entries only.
        # Your narration_only=True filter is good: it excludes INVISIBLE.
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation.id,
            search_scope=[0] + list(present_character_ids),
            narration_only=True,
        )

        recall_query = self._build_narrator_recall_query(
            state=state,
            current_location=current_location,
            narrator_resolution_view=narrator_resolution_view,
            user_input=state.user_input,
        )

        recalled_entries = await recaller.recall(
            query=recall_query,
            entries=world_entries,
            language=state.simulation.language,
        )

        result = await narrator_agent.narrate_resolved_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=characters,
            player_character=player_character,
            narrator_resolution_view=narrator_resolution_view,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            recent_history_summary=state.state.recent_history_summary,
            long_term_history_summary=state.state.long_term_history_summary,
            world_entries_for_narrator=recalled_entries,
            pending_generated_proposals=state.generated_proposals,
        )

        return {
            "narration": result,
        }

    async def narrate_wait_for_user(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.director_output:
            raise RuntimeError("Director output not generated")

        if state.connection_profiles.narrator is None:
            raise RuntimeError("Narrator connection profile not loaded")

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        narrator_agent = NarratorAgent(
            profile=state.simulation.agent_preset.narrator,
            connection=state.connection_profiles.narrator,
        )

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")

        present_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            location=state.state.scene,
        )

        player_character = (await self._db.character.list(
            simulation_id=state.simulation.id,
            controlled_by_user=True,
        ))[0]

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        # Player-facing narration should not see all NPC-private entries.
        narrator_scope = [0]
        if player_character is not None:
            narrator_scope.append(player_character.id)

        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=narrator_scope,
            narration_only=True,
        )

        recall_query = (
                state.user_input
                or state.director_output.scene_focus
                or state.director_output.reason_to_wait
                or current_location.description
                or ""
        )

        recalled_entries = await recaller.recall(
            query=recall_query,
            entries=world_entries,
            language=state.simulation.language,
        )

        context = self._build_wait_for_user_narration_context(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            director_output=state.director_output,
            user_input=state.user_input,
            last_narration=last_records[0].narration if last_records else None,
            recalled_entries=recalled_entries,
        )

        result = await narrator_agent.narrate_wait_for_user(
            context=context,
        )

        return {
            "narration": result,
        }

    async def narrate_user_failure(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if not state.user_input:
            raise RuntimeError("User input is missing")

        if state.user_input_resolution is None:
            raise RuntimeError("User input resolution is missing")

        if state.connection_profiles.narrator is None:
            raise RuntimeError("Narrator connection profile not loaded")

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")

        narrator_agent = NarratorAgent(
            profile=state.simulation.agent_preset.narrator,
            connection=state.connection_profiles.narrator,
        )

        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )

        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if current_location is None:
            raise ValueError(f"Current location {state.state.scene} does not exist")

        player_character = (await self._db.character.list(
            simulation_id=state.simulation_id,
            controlled_by_user=True
        ))[0]

        last_records = await self._db.record.get_last_records(
            simulation_id=state.simulation.id,
        )

        # Failure narration must be player-facing.
        # Do not include every NPC private scope.
        search_scope = [0]
        if player_character is not None:
            search_scope.append(player_character.id)

        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=search_scope,
            narration_only=True,
        )

        recall_query = " ".join(
            part
            for part in [
                state.user_input,
                state.user_input_resolution.rejection_reason,
                state.user_input_resolution.user_retry_instruction,
                current_location.description,
            ]
            if part
        )

        recalled_entries = await recaller.recall(
            query=recall_query,
            entries=world_entries,
            language=state.simulation.language,
        )

        context = self._build_user_input_failure_narration_context(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            player_character=player_character,
            user_input=state.user_input,
            user_input_resolution=state.user_input_resolution,
            last_narration=last_records[0].narration if last_records else None,
            recalled_entries=recalled_entries,
        )

        result = await narrator_agent.narrate_user_input_failure(
            context=context,
        )

        return {
            "narration": result,
        }

    @staticmethod
    def route_after_input_resolution(state: TurnGeneratorState):
        output = state.user_input_resolution

        if output is None:
            raise RuntimeError("User input resolution missing")

        if not output.accepted:
            return "narrate"

        return "director"

    @staticmethod
    def route_after_director(state: TurnGeneratorState):
        if not state.director_output:
            raise RuntimeError("Director output not generated")

        if not state.director_output.wait_for_user:
            return "memory"

        return "narration"

    @staticmethod
    def route_after_briefing(state: TurnGeneratorState):
        if not state.briefing_output:
            raise RuntimeError("Briefing output not generated")

        return [
            Send(
                "character_action",
                CharacterActionState(
                    simulation=state.simulation,
                    state=state.state,
                    connection_profiles=state.connection_profiles,
                    user_input=state.user_input,
                    generated_proposals=state.generated_proposals,
                    briefing=briefing
                ),
            ) for briefing in state.briefing_output.briefings
        ]

    @staticmethod
    def route_after_resolving(state: TurnGeneratorState):
        if not state.resolver_output:
            raise RuntimeError("Resolver output not generated")

        if not state.resolver_output.failed_characters:
            return ["commit_changes", "narrate_resolved_turn"]

        if not state.character_action_outputs:
            raise RuntimeError("Character action outputs not generated")

        if not state.briefing_output:
            raise RuntimeError("Briefing output not generated")

        retryable_failed_characters = [
            failed_character
            for failed_character in state.resolver_output.failed_characters
            if failed_character.retry_allowed
        ]

        if not retryable_failed_characters:
            return ["commit_changes", "narrate_resolved_turn"]

        def get_failed_character_id(failed_character) -> int:
            if isinstance(failed_character, int):
                return failed_character

            character_id = getattr(failed_character, "character_id", None)
            if character_id is None:
                raise RuntimeError(f"Failed character record has no character_id: {failed_character}")

            return character_id

        def get_failed_character_name(failed_character, original_action: CharacterActionOutput) -> str:
            return (
                    getattr(failed_character, "character_name", None)
                    or original_action.character_name
            )

        def get_failed_action_summary(
                failed_character,
                original_action: CharacterActionOutput,
                resolved_action,
        ) -> str:
            summary = getattr(failed_character, "failed_action_summary", None)
            if summary:
                return summary

            if resolved_action:
                return resolved_action.original_intent

            return original_action.intent

        def get_failed_reason(failed_character, resolved_action) -> str:
            reason = getattr(failed_character, "reason", None)
            if reason:
                return reason

            if resolved_action and resolved_action.failure_reason:
                return resolved_action.failure_reason

            return "The action did not complete successfully."

        def get_retry_context(failed_character, resolved_action) -> str | None:
            retry_context = getattr(failed_character, "retry_context", None)
            if retry_context:
                return retry_context

            if resolved_action and resolved_action.retry_instruction:
                return resolved_action.retry_instruction

            return None

        def get_failed_status(failed_character, resolved_action) -> str | None:
            status = getattr(failed_character, "status", None)
            if status:
                return status

            if resolved_action:
                return resolved_action.final_status

            return None

        def build_reaction_context(failed_character):
            failed_character_id = get_failed_character_id(failed_character)

            original_action = next(
                (
                    action
                    for action in state.character_action_outputs
                    if action.character_id == failed_character_id
                ),
                None,
            )
            if original_action is None:
                raise RuntimeError(
                    f"Original action for failed character {failed_character_id} not found"
                )

            original_briefing = next(
                (
                    briefing
                    for briefing in state.briefing_output.briefings
                    if briefing.character_id == failed_character_id
                ),
                None,
            )
            if original_briefing is None:
                raise RuntimeError(
                    f"Original briefing for failed character {failed_character_id} not found"
                )

            resolved_action = next(
                (
                    action
                    for action in state.resolver_output.resolved_actions
                    if action.actor_id == failed_character_id
                ),
                None,
            )

            fixed_visible_events = [
                action.visible_result
                for action in state.resolver_output.resolved_actions
                if action.actor_id != failed_character_id
                   and action.final_status in {
                       "succeeded",
                       "partially_succeeded",
                       "delayed",
                   }
                   and action.visible_result
            ]

            # Include the failed actor's own visible failed/blocked attempt if it happened visibly.
            if resolved_action and resolved_action.visible_result:
                fixed_visible_events.append(
                    f"Your previous attempt: {resolved_action.visible_result}"
                )

            fixed_private_events_for_actor = [
                action.private_result_for_actor
                for action in state.resolver_output.resolved_actions
                if action.actor_id == failed_character_id
                   and action.private_result_for_actor
            ]

            failed_action_summary = get_failed_action_summary(
                failed_character=failed_character,
                original_action=original_action,
                resolved_action=resolved_action,
            )

            failure_reason = get_failed_reason(
                failed_character=failed_character,
                resolved_action=resolved_action,
            )

            retry_context = get_retry_context(
                failed_character=failed_character,
                resolved_action=resolved_action,
            )

            status = get_failed_status(
                failed_character=failed_character,
                resolved_action=resolved_action,
            )

            # This assumes CharacterReactionContext has these fields.
            # If it does not yet have `status`, either add it or remove that line.
            return CharacterReactionContext(
                character_id=failed_character_id,
                character_name=get_failed_character_name(
                    failed_character=failed_character,
                    original_action=original_action,
                ),
                original_action=original_action,
                failure_record=FailedCharacterRecord(
                    character_id=failed_character_id,
                    character_name=get_failed_character_name(
                        failed_character=failed_character,
                        original_action=original_action,
                    ),
                    failed_action_summary=failed_action_summary,
                    status=status,
                    reason=failure_reason,
                    retry_context=retry_context,
                ),
                fixed_visible_events=fixed_visible_events,
                fixed_private_events_for_actor=[
                    event for event in fixed_private_events_for_actor if event is not None
                ],
                relevant_task_ids=original_briefing.relevant_task_ids,
                relevant_world_entry_ids=original_briefing.relevant_world_entry_ids,
                changed_scene_context=state.resolver_output.scene_result_summary,
                immediate_failure_context=failure_reason,
                retry_number=1,
                max_retries_this_round=1,
                allowed_reaction_scope="respond_to_failure",
                constraints=[
                    "Do not undo fixed resolved events.",
                    "Do not prevent another character's already fixed successful, partially successful, or delayed action.",
                    "Do not repeat the same failed action without a different method, target, or immediate purpose.",
                    "React only to what this character can perceive or privately know.",
                    "This is the final retry for this round.",
                ],
            )

        return [
            Send(
                "character_reaction",
                CharacterReactionState(
                    simulation=state.simulation,
                    state=state.state,
                    connection_profiles=state.connection_profiles,
                    user_input=state.user_input,
                    generated_proposals=state.generated_proposals,
                    reaction_context=build_reaction_context(failed_character),
                ),
            )
            for failed_character in retryable_failed_characters
        ]

    @staticmethod
    def route_after_narration(state: TurnGeneratorState):
        return ["memory_summary"]

    def build_graph(self):
        graph = StateGraph(TurnGeneratorState)

        graph.add_node("load_simulation", self.load_simulation)
        graph.add_node("director_planning", self.director_planning)
        graph.add_node("memory_briefing", self.memory_briefing)
        graph.add_node("memory_summary", self.memory_summary)
        graph.add_node("character_action", self.character_action)
        graph.add_node("character_reaction", self.character_reaction)
        graph.add_node("resolve_character_actions", self.resolve_character_actions)
        graph.add_node("resolve_character_reactions", self.resolve_character_reactions)
        graph.add_node("resolve_user_input", self.resolve_user_input)
        graph.add_node("commit_changes", self.commit_changes)
        graph.add_node("narrate_resolved_turn", self.narrate_resolved_turn)
        graph.add_node("narrate_wait_for_user", self.narrate_wait_for_user)
        graph.add_node("narrate_user_failure", self.narrate_user_failure)

        graph.add_edge(START, "load_simulation")
        graph.add_edge("load_simulation", "resolve_user_input")
        graph.add_conditional_edges(
            "resolve_user_input",
            self.route_after_input_resolution,
            {
                "director": "director_planning",
                "narrate": "narrate_user_failure",
            }
        )
        graph.add_edge("narrate_user_failure", "memory_summary")
        graph.add_conditional_edges(
            "director_planning",
            self.route_after_director,
            {
                "memory": "memory_briefing",
                "narration": "narrate_wait_for_user",
            }
        )
        graph.add_conditional_edges(
            "memory_briefing",
            self.route_after_briefing,
        )
        graph.add_edge("character_action", "resolve_character_actions")
        graph.add_conditional_edges(
            "resolve_character_actions",
            self.route_after_resolving,
        )
        graph.add_edge("character_reaction", "resolve_character_reactions")
        graph.add_edge("resolve_character_reactions", "commit_changes")
        graph.add_edge("resolve_character_reactions", "narrate_resolved_turn")
        graph.add_edge("commit_changes", END)
        graph.add_conditional_edges(
            "narrate_resolved_turn",
            self.route_after_narration,
        )
        graph.add_conditional_edges(
            "narrate_wait_for_user",
            self.route_after_narration,
        )
        graph.add_edge("memory_summary", END)

        return graph.compile()

    async def persist_state_to_database(self, payload: dict):
        previous_turn_number = payload["state"]["turn_number"]
        if not payload.get("narration"):
            # Narration not generated, this run is not completed
            raise ValueError(f"Graph run {payload['run_id']} failed, nothing to persist.")

        new_turns = [
            TurnRecordCreate(
                simulation_id=payload["simulation_id"],
                turn_number=previous_turn_number + 1,
                type=TurnType.USER_INPUT,
                director_output=None,
                proposals=None,
                briefing_output=None,
                character_actions=[],
                character_reactions=[],
                resolver_output=None,
                reaction_resolving=None,
                committer_output=None,
                narration=payload.get("user_input", ""),
                summary_output=None,
            ),
        ]

        if not payload.get("director_output"):
            # TODO: Director is not run or not succeeded
            raise NotImplementedError
        elif not payload.get("committer_output"):
            # Committer not run, waiting for user input
            if not payload.get("summary_output"):
                # Summary not generated, running of workflow didn't complete
                raise ValueError(f"Summary output is not generated in run {payload['run_id']}")
            new_turns.append(
                TurnRecordCreate(
                    simulation_id=payload["simulation_id"],
                    turn_number=previous_turn_number + 2,
                    type=TurnType.AI_WAIT,
                    director_output=DirectorOutput.model_validate(payload["director_output"]),
                    proposals=[
                        PendingGeneratedProposal.model_validate(p)
                        for p in payload.get("generated_proposals", [])
                    ],
                    briefing_output=None,
                    character_actions=[],
                    character_reactions=[],
                    resolver_output=None,
                    reaction_resolving=None,
                    committer_output=None,
                    narration=payload["narration"],
                    summary_output=SummaryOutput.model_validate(payload["summary_output"]),
                )
            )
        else:
            # Normal run through, persist the commits
            committer_output = payload["committer_output"]

            if not committer_output.get("ready_to_commit"):
                # Cannot continue with state inconsistency
                raise RuntimeError(
                    f"Committer output is not ready to commit. warnings={committer_output.get('warnings')}"
                )

            mutations = committer_output.get("database_patch_preview") or committer_output.get("mutation_log") or []

            if mutations:
                applied: list[dict[str, Any]] = []
                temp_id_map: dict[str, int] = {}

                # Prefer a real transaction if your DB layer supports it.
                transaction = getattr(self._db, "transaction", None)

                if transaction is not None:
                    async with transaction():
                        for mutation in mutations:
                            result = await self._persist_single_committer_mutation(
                                simulation_id=committer_output["simulation_id"],
                                mutation=mutation,
                                temp_id_map=temp_id_map,
                            )
                            applied.append(result)
                else:
                    # Non-transactional fallback. Good for early testing, but use a transaction long-term.
                    for mutation in mutations:
                        result = await self._persist_single_committer_mutation(
                            simulation_id=committer_output["simulation_id"],
                            mutation=mutation,
                            temp_id_map=temp_id_map,
                        )
                        applied.append(result)

            # Persist the summaries
            summary_output = payload["summary_output"]
            await self._db.state.update(
                state_id=payload["simulation_id"],
                patched_data={
                    "turn_number": previous_turn_number + 2,
                    "state": summary_output["scene_summary"],
                    "recent_history_summary": summary_output["short_term_memory"],
                    "long_term_history_summary": summary_output["long_term_memory"],
                },
            )

            # Add the complete record
            new_turns.append(
                TurnRecordCreate(
                    simulation_id=payload["simulation_id"],
                    turn_number=previous_turn_number + 2,
                    type=TurnType.AI_RESPONSE if payload.get("user_input") else TurnType.AI_CONTINUE,
                    director_output=DirectorOutput.model_validate(payload["director_output"]),
                    proposals=[
                        PendingGeneratedProposal.model_validate(p)
                        for p in payload.get("generated_proposals", [])
                    ],
                    briefing_output=BriefingOutput.model_validate(payload["briefing_output"]),
                    character_actions=[
                        CharacterActionOutput.model_validate(a)
                        for a in payload.get("character_action_outputs", [])
                    ],
                    character_reactions=[
                        CharacterActionOutput.model_validate(r)
                        for r in payload.get("character_reaction_outputs", [])
                    ],
                    resolver_output=ResolverOutput.model_validate(payload["resolver_output"]),
                    reaction_resolving=ResolverOutput.model_validate(payload["reaction_resolver_output"])
                        if payload.get("reaction_resolver_output") else None,
                    committer_output=CommitterFinalOutput.model_validate(payload["committer_output"]),
                    narration=payload["narration"],
                    summary_output=SummaryOutput.model_validate(payload["summary_output"]),
                )
            )

        # Write the turn records
        for t in new_turns:
            await self._db.record.create(t)
