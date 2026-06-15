from uuid import uuid4
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast
from langchain_core.runnables import RunnableConfig, patch_config
from .world_agent import WorldAgent

from world_simulation_engine.model import CommitterAgentProfile, Simulation, SimulationState, Character, \
    Location, CharacterInventory, Task, WorldEntry, LlmConnectionProfile, SandboxMutationRecord, SandboxObjectRef, \
    CommitterValidationOutput, CommitterFinalOutput, Faction, FactionRelationship, CommitterMutationPlanOutput, \
    CommitterPlannedMutation


@dataclass
class _InventoryTemplateView:
    items: list[Any]
    equipments: list[Any]


class CommitterAgent(WorldAgent[CommitterAgentProfile]):
    def __init__(
        self,
        profile: CommitterAgentProfile,
        connection: LlmConnectionProfile,
        simulation: Simulation,
        state: SimulationState,
        characters: list[Character],
        locations: list[Location],
        inventory: dict[int, CharacterInventory],
        factions: list[Faction],
        faction_relationships: list[FactionRelationship],
        tasks: list[Task],
        world_entries: list[WorldEntry],
    ):
        super().__init__(
            profile=profile,
            connection=connection,
        )

        self._original = {
            "simulation": simulation,
            "data_preset": simulation.data_preset,
            "state": state,
            "characters": characters,
            "locations": locations,
            "inventory": inventory,
            "factions": factions,
            "faction_relationships": faction_relationships,
            "tasks": tasks,
            "world_entries": world_entries,
        }

        self._sandbox = deepcopy(self._original)
        self._mutation_log: list[SandboxMutationRecord] = []

    @staticmethod
    def _dump_obj(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return {k: CommitterAgent._dump_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [CommitterAgent._dump_obj(v) for v in obj]
        return obj

    def snapshot(self) -> dict[str, Any]:
        return self._dump_obj(self._sandbox)

    def mutation_log(self) -> list[dict[str, Any]]:
        return [m.model_dump() for m in self._mutation_log]

    @staticmethod
    def _object_id(obj: Any) -> int | str | None:
        if isinstance(obj, dict):
            return obj.get("id", obj.get("temp_id"))
        return getattr(obj, "id", None)

    def _new_temp_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    @staticmethod
    def _inventory_values(inventory: Any, field_name: str) -> list[Any]:
        if isinstance(inventory, dict):
            return inventory.get(field_name, []) or []

        values = getattr(inventory, "__dict__", {}).get(field_name)
        if values is not None:
            return values

        return getattr(inventory, field_name, []) or []

    def _record(
        self,
        *,
        operation: str,
        target: SandboxObjectRef | None,
        payload: dict[str, Any],
        reason: str,
        source_event: str | None = None,
    ) -> SandboxMutationRecord:
        record = SandboxMutationRecord(
            mutation_id=str(uuid4()),
            operation=operation,
            target=target,
            payload=payload,
            reason=reason,
            source_event=source_event,
        )
        self._mutation_log.append(record)
        return record

    def _find_list_object(self, collection_name: str, object_id: int | str):
        collection = self._sandbox[collection_name]
        for index, obj in enumerate(collection):
            if self._object_id(obj) == object_id:
                return index, obj
        raise KeyError(f"{collection_name} object id={object_id} not found")

    def _patch_model_object(self, obj: Any, patch: dict[str, Any]) -> Any:
        if hasattr(obj, "model_copy"):
            return obj.model_copy(update=patch)

        if isinstance(obj, dict):
            return {**obj, **patch}

        for key, value in patch.items():
            setattr(obj, key, value)

        return obj

    def _ensure_temp_id(self, data: dict[str, Any], prefix: str) -> dict[str, Any]:
        data = dict(data)

        if data.get("id") is None and not data.get("temp_id"):
            data.pop("id", None)
            data["temp_id"] = self._new_temp_id(prefix)

        if data.get("temp_id") is None:
            data["temp_id"] = self._new_temp_id(prefix)

        return data

    def _append_collection_object(
            self,
            collection_name: str,
            object_type: str,
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
    ) -> SandboxMutationRecord:
        data = self._ensure_temp_id(data, object_type)

        self._sandbox[collection_name].append(data)

        return self._record(
            operation="create",
            target=SandboxObjectRef(
                object_type=object_type,
                object_id=data.get("id", data.get("temp_id", "new")),
            ),
            payload=data,
            reason=reason,
            source_event=source_event,
        )

    def _create_inventory_object(
            self,
            object_type: str,
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
    ) -> SandboxMutationRecord:
        data = self._ensure_temp_id(data, object_type)

        owner_id = (
                data.get("owner_id")
                or data.get("character_id")
                or data.get("proposed_owner_id")
                or 0
        )

        if owner_id not in self._sandbox["inventory"]:
            self._sandbox["inventory"][owner_id] = CharacterInventory(
                items=[],
                equipments=[],
            )

        inventory = self._sandbox["inventory"][owner_id]
        field_name = "equipments" if object_type == "equipment" else "items"

        current_values = (
            inventory[field_name]
            if isinstance(inventory, dict)
            else getattr(inventory, field_name)
        )

        self._sandbox["inventory"][owner_id] = self._patch_model_object(
            inventory,
            {
                field_name: [*current_values, data],
            },
        )

        return self._record(
            operation="create",
            target=SandboxObjectRef(
                object_type=object_type,
                object_id=data.get("id", data.get("temp_id", "new")),
            ),
            payload={"owner_id": owner_id, **data},
            reason=reason,
            source_event=source_event,
        )

    def _create_entity_object(
            self,
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
    ) -> SandboxMutationRecord:
        data = self._ensure_temp_id(data, "entity")

        location_id = data.get("location_id", data.get("proposed_location_id"))
        if location_id is None:
            raise ValueError("Creating an entity requires location_id or proposed_location_id")

        loc_index, location = self._find_list_object("locations", location_id)
        entities = location["entities"] if isinstance(location, dict) else location.entities

        self._sandbox["locations"][loc_index] = self._patch_model_object(
            location,
            {
                "entities": [*entities, data],
            },
        )

        return self._record(
            operation="create",
            target=SandboxObjectRef(
                object_type="entity",
                object_id=data.get("id", data.get("temp_id", "new")),
            ),
            payload=data,
            reason=reason,
            source_event=source_event,
        )

    def _remove_from_collection(self, collection_name: str, object_id: int | str) -> bool:
        collection = self._sandbox[collection_name]
        for index, obj in enumerate(collection):
            if self._object_id(obj) == object_id:
                del collection[index]
                return True
        return False

    def _remove_entity_object(self, object_id: int | str) -> bool:
        for loc_index, location in enumerate(self._sandbox["locations"]):
            entities = location["entities"] if isinstance(location, dict) else location.entities

            for entity_index, entity in enumerate(entities):
                if self._object_id(entity) == object_id:
                    new_entities = list(entities)
                    del new_entities[entity_index]

                    self._sandbox["locations"][loc_index] = self._patch_model_object(
                        location,
                        {
                            "entities": new_entities,
                        },
                    )

                    return True

        return False

    def _remove_inventory_object(self, object_type: str, object_id: int | str) -> bool:
        field_name = "equipments" if object_type == "equipment" else "items"

        for owner_id, inventory in self._sandbox["inventory"].items():
            current_values = self._inventory_values(inventory, field_name)

            for index, obj in enumerate(current_values):
                if self._object_id(obj) == object_id:
                    new_values = list(current_values)
                    del new_values[index]

                    self._sandbox["inventory"][owner_id] = self._patch_model_object(
                        inventory,
                        {
                            field_name: new_values,
                        },
                    )

                    return True

        return False

    def _execute_mutation(self, mutation: CommitterPlannedMutation) -> SandboxMutationRecord:
        op = mutation.operation
        args = mutation.args or {}
        reason = mutation.reason
        source_event = mutation.source_event

        if op == "noop":
            return self._record(
                operation="update",
                target=SandboxObjectRef(
                    object_type="state",
                    object_id=self._object_id(self._sandbox["state"]) or "state",
                ),
                payload={"noop": True},
                reason=reason or "No persistent changes required.",
                source_event=source_event,
            )

        if op == "update_simulation_state":
            patch = args["patch"]
            self._sandbox["state"] = self._patch_model_object(
                self._sandbox["state"],
                patch,
            )
            return self._record(
                operation="update",
                target=SandboxObjectRef(
                    object_type="state",
                    object_id=self._object_id(self._sandbox["state"]) or "state",
                ),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        if op == "update_character":
            character_id = args["character_id"]
            patch = args["patch"]
            index, obj = self._find_list_object("characters", character_id)
            self._sandbox["characters"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="character", object_id=character_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        if op == "update_location":
            location_id = args["location_id"]
            patch = args["patch"]
            index, obj = self._find_list_object("locations", location_id)
            self._sandbox["locations"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="location", object_id=location_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        if op == "update_entity":
            location_id = args["location_id"]
            entity_id = args["entity_id"]
            patch = args["patch"]

            loc_index, loc = self._find_list_object("locations", location_id)
            entities = loc["entities"] if isinstance(loc, dict) else loc.entities

            for entity_index, entity in enumerate(entities):
                if self._object_id(entity) == entity_id:
                    updated_entity = self._patch_model_object(entity, patch)
                    new_entities = list(entities)
                    new_entities[entity_index] = updated_entity

                    self._sandbox["locations"][loc_index] = self._patch_model_object(
                        loc,
                        {
                            "entities": new_entities,
                        },
                    )

                    return self._record(
                        operation="update",
                        target=SandboxObjectRef(object_type="entity", object_id=entity_id),
                        payload={"location_id": location_id, **patch},
                        reason=reason,
                        source_event=source_event,
                    )

            raise KeyError(f"Entity id={entity_id} not found in location id={location_id}")

        if op == "create_location":
            return self._append_collection_object(
                collection_name="locations",
                object_type="location",
                data=args["data"],
                reason=reason,
                source_event=source_event,
            )

        if op == "create_world_entry":
            return self._append_collection_object(
                collection_name="world_entries",
                object_type="world_entry",
                data=args["data"],
                reason=reason,
                source_event=source_event,
            )

        if op == "create_task":
            return self._append_collection_object(
                collection_name="tasks",
                object_type="task",
                data=args["data"],
                reason=reason,
                source_event=source_event,
            )

        if op == "update_task":
            task_id = args["task_id"]
            patch = args["patch"]
            index, obj = self._find_list_object("tasks", task_id)
            self._sandbox["tasks"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="task", object_id=task_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        if op == "update_inventory":
            owner_id = args["owner_id"]
            patch = args["patch"]

            if owner_id not in self._sandbox["inventory"]:
                self._sandbox["inventory"][owner_id] = CharacterInventory(
                    items=[],
                    equipments=[],
                )

            inv = self._sandbox["inventory"][owner_id]
            self._sandbox["inventory"][owner_id] = self._patch_model_object(inv, patch)

            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="inventory", object_id=owner_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        if op == "create_object":
            object_type = args["object_type"]
            data = args["data"]

            collection_by_type = {
                "character": "characters",
                "faction": "factions",
                "faction_relationship": "faction_relationships",
            }

            collection_name = collection_by_type.get(object_type)

            if collection_name is not None:
                return self._append_collection_object(
                    collection_name=collection_name,
                    object_type=object_type,
                    data=data,
                    reason=reason,
                    source_event=source_event,
                )

            if object_type in {"item", "equipment"}:
                return self._create_inventory_object(
                    object_type=object_type,
                    data=data,
                    reason=reason,
                    source_event=source_event,
                )

            if object_type == "entity":
                return self._create_entity_object(
                    data=data,
                    reason=reason,
                    source_event=source_event,
                )

            return self._record(
                operation="create",
                target=SandboxObjectRef(
                    object_type=object_type,
                    object_id=data.get("id", data.get("temp_id", "new")),
                ),
                payload=data,
                reason=reason,
                source_event=source_event,
            )

        if op == "remove_object":
            object_type = args["object_type"]
            object_id = args["object_id"]

            collection_by_type = {
                "character": "characters",
                "location": "locations",
                "task": "tasks",
                "world_entry": "world_entries",
                "faction": "factions",
                "faction_relationship": "faction_relationships",
            }

            collection_name = collection_by_type.get(object_type)
            removed = False

            if collection_name is not None:
                removed = self._remove_from_collection(collection_name, object_id)
            elif object_type in {"item", "equipment"}:
                removed = self._remove_inventory_object(object_type, object_id)
            elif object_type == "entity":
                removed = self._remove_entity_object(object_id)

            return self._record(
                operation="remove",
                target=SandboxObjectRef(object_type=object_type, object_id=object_id),
                payload={"removed_from_sandbox": removed},
                reason=reason,
                source_event=source_event,
            )

        if op == "accept_generated_proposal":
            temp_id = args["temp_id"]
            return self._record(
                operation="accept_proposal",
                target=SandboxObjectRef(
                    object_type="pending_generated_proposal",
                    object_id=temp_id,
                ),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        if op == "reject_generated_proposal":
            temp_id = args["temp_id"]
            return self._record(
                operation="reject_proposal",
                target=SandboxObjectRef(
                    object_type="pending_generated_proposal",
                    object_id=temp_id,
                ),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        if op == "defer_generated_proposal":
            temp_id = args["temp_id"]
            return self._record(
                operation="defer_proposal",
                target=SandboxObjectRef(
                    object_type="pending_generated_proposal",
                    object_id=temp_id,
                ),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        raise ValueError(f"Unsupported committer mutation operation: {op}")

    def _resolved_action_text(self, resolver_output: Any) -> list[str]:
        resolver = self._dump_obj(resolver_output)
        actions = resolver.get("resolved_actions", []) if isinstance(resolver, dict) else []

        result: list[str] = []

        for index, action in enumerate(actions, start=1):
            actor = action.get("actor_name", "Unknown actor")
            status = action.get("final_status", "unknown")
            visible = action.get("visible_result", "")
            failure = action.get("failure_reason")
            state_hints = action.get("state_change_hints", []) or []
            world_hints = action.get("world_entry_hints", []) or []

            parts = [
                f"ResolvedAction {index}: {actor}: {status}.",
                visible,
            ]

            if failure:
                parts.append(f"Failure/block reason: {failure}")

            if state_hints:
                parts.append("State hints: " + "; ".join(state_hints))

            if world_hints:
                parts.append("World-entry hints: " + "; ".join(world_hints))

            result.append(" ".join(part for part in parts if part))

        return result

    def _resolver_state_change_hints(self, resolver_output: Any) -> list[str]:
        resolver = self._dump_obj(resolver_output)
        hints: list[str] = []

        if not isinstance(resolver, dict):
            return hints

        for action in resolver.get("resolved_actions", []) or []:
            hints.extend(action.get("state_change_hints", []) or [])

        hints.extend(resolver.get("state_update_suggestions", []) or [])

        return [hint for hint in hints if hint]

    def _resolver_world_entry_hints(self, resolver_output: Any) -> list[str]:
        resolver = self._dump_obj(resolver_output)
        hints: list[str] = []

        if not isinstance(resolver, dict):
            return hints

        for action in resolver.get("resolved_actions", []) or []:
            hints.extend(action.get("world_entry_hints", []) or [])

        hints.extend(resolver.get("pending_world_entry_suggestions", []) or [])

        return [hint for hint in hints if hint]

    def _state_summary_patch(self, resolver_output: Any) -> dict[str, Any]:
        resolver = self._dump_obj(resolver_output)
        state = self._sandbox["state"]

        if hasattr(state, "state"):
            current_state_summary = state.state or ""
            current_recent = getattr(state, "recent_history_summary", None) or ""
        elif isinstance(state, dict):
            current_state_summary = state.get("state") or ""
            current_recent = state.get("recent_history_summary") or ""
        else:
            current_state_summary = ""
            current_recent = ""

        scene_summary = ""
        next_note = ""

        if isinstance(resolver, dict):
            scene_summary = resolver.get("scene_result_summary") or ""
            next_note = resolver.get("next_round_note") or ""

        patch: dict[str, Any] = {}

        if scene_summary and scene_summary not in current_state_summary:
            patch["state"] = (
                f"{current_state_summary.strip()}\n\nLatest resolved turn: {scene_summary}"
                if current_state_summary.strip()
                else scene_summary
            )

        if next_note and next_note not in current_recent:
            patch["recent_history_summary"] = (
                f"{current_recent.strip()}\n{next_note}"
                if current_recent.strip()
                else next_note
            )

        return patch

    def _fallback_plan(
        self,
        *,
        resolver_output: Any,
        pending_generated_proposals: list[Any] | None,
        reason: str,
    ) -> CommitterMutationPlanOutput:
        mutations: list[CommitterPlannedMutation] = []

        state_patch = self._state_summary_patch(resolver_output)

        if state_patch:
            mutations.append(
                CommitterPlannedMutation(
                    operation="update_simulation_state",
                    args={"patch": state_patch},
                    reason="Fallback: record the resolved turn in SimulationState.",
                    source_event="resolver.scene_result_summary",
                )
            )

        for proposal in pending_generated_proposals or []:
            proposal_data = self._dump_obj(proposal)
            if not isinstance(proposal_data, dict):
                continue

            temp_id = proposal_data.get("temp_id") or proposal_data.get("id")
            if not temp_id:
                continue

            mutations.append(
                CommitterPlannedMutation(
                    operation="defer_generated_proposal",
                    args={"temp_id": str(temp_id)},
                    reason="Fallback: proposal was not explicitly accepted or rejected this turn.",
                    source_event="fallback_commit_plan",
                )
            )

        if not mutations:
            mutations.append(
                CommitterPlannedMutation(
                    operation="noop",
                    args={},
                    reason="Fallback: no safe deterministic mutation could be inferred.",
                    source_event="fallback_commit_plan",
                )
            )

        return CommitterMutationPlanOutput(
            plan_summary=f"Fallback mutation plan: {reason}",
            mutations=mutations,
            no_changes_needed=False,
            confidence=0.25,
            warnings=[reason],
        )

    def _normalise_plan(
        self,
        plan: CommitterMutationPlanOutput,
    ) -> CommitterMutationPlanOutput:
        if plan.no_changes_needed:
            plan.mutations = []
            return plan

        normalised_mutations: list[CommitterPlannedMutation] = []

        for mutation in plan.mutations:
            if mutation.operation == "noop" and len(plan.mutations) > 1:
                continue

            if not mutation.reason:
                mutation.reason = "No reason supplied by planner."

            normalised_mutations.append(mutation)

        plan.mutations = normalised_mutations
        return plan

    def _normalise_validation(
        self,
        validation: CommitterValidationOutput,
    ) -> CommitterValidationOutput:
        if validation.complete:
            validation.needs_more_changes = False
            validation.next_instruction = None

        if validation.needs_more_changes:
            validation.complete = False

        return validation

    def _build_final_output(
        self,
        *,
        resolver_output: Any,
        validation: CommitterValidationOutput,
        extra_warnings: list[str],
    ) -> CommitterFinalOutput:
        resolver = self._dump_obj(resolver_output)
        mutation_log = [
            SandboxMutationRecord.model_validate(record)
            for record in self.mutation_log()
        ]

        round_summary = ""
        if isinstance(resolver, dict):
            round_summary = resolver.get("scene_result_summary") or ""

        if not round_summary:
            round_summary = "Resolved turn processed by Committer."

        warnings = [
            *validation.missing_changes,
            *validation.questionable_changes,
            *validation.consistency_notes,
            *extra_warnings,
        ]

        return CommitterFinalOutput(
            ready_to_commit=bool(mutation_log) and validation.complete,
            round_summary=round_summary,
            mutation_log=mutation_log,
            warnings=warnings,
            final_state=self._compact_sandbox_state(),
            database_patch_preview=mutation_log,
        )

    def _compact_simulation(self) -> dict[str, Any]:
        simulation = self._original["simulation"]

        return {
            "id": simulation.id,
            "name": simulation.name,
            "description": simulation.description,
            "language": getattr(simulation, "language", None),
        }

    def _compact_state(self, state: Any | None = None) -> dict[str, Any]:
        state = state or self._sandbox["state"]

        data = self._dump_obj(state)

        allowed_keys = {
            "id",
            "simulation_id",
            "turn_number",
            "time_label",
            "scene",
            "state",
            "recent_history_summary",
            "long_term_history_summary",
        }

        return {
            key: value
            for key, value in data.items()
            if key in allowed_keys
        }

    def _compact_entity(self, entity: Any) -> dict[str, Any]:
        data = self._dump_obj(entity)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "type": data.get("type"),
            "description": data.get("description"),
            "status": data.get("status"),
            "interactions": data.get("interactions", []),
        }

    def _compact_location(self, location: Any) -> dict[str, Any]:
        data = self._dump_obj(location)

        return {
            "id": data.get("id", data.get("temp_id")),
            "primary_location": data.get("primary_location"),
            "detailed_location": data.get("detailed_location"),
            "scene": data.get("scene"),
            "description": data.get("description"),
            "attributes": data.get("attributes", {}),
            "stats": data.get("stats", {}),
            "entities": [
                self._compact_entity(entity)
                for entity in data.get("entities", [])
            ],
        }

    def _compact_character(self, character: Any) -> dict[str, Any]:
        data = self._dump_obj(character)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "user_controlled": data.get("user_controlled"),
            "location": data.get("location"),
            "public_state": data.get("public_state"),
            "private_state": data.get("private_state"),
            "attributes": data.get("attributes", {}),
            "stats": data.get("stats", {}),
        }

    def _compact_item(self, item: Any) -> dict[str, Any]:
        data = self._dump_obj(item)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "description": data.get("description"),
            "quantity": data.get("quantity"),
            "quality": data.get("quality"),
        }

    def _compact_equipment(self, equipment: Any) -> dict[str, Any]:
        data = self._dump_obj(equipment)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "description": data.get("description"),
            "status": data.get("status"),
            "quality": data.get("quality"),
        }

    def _compact_inventory(self, inventory: Any) -> dict[str, Any]:
        data = self._dump_obj(inventory)

        return {
            "items": [
                self._compact_item(item)
                for item in data.get("items", [])
            ],
            "equipments": [
                self._compact_equipment(equipment)
                for equipment in data.get("equipments", [])
            ],
        }

    def _compact_inventory_template_view(self, inventory: Any) -> _InventoryTemplateView:
        compact = self._compact_inventory(inventory)

        return _InventoryTemplateView(
            items=compact["items"],
            equipments=compact["equipments"],
        )

    def _compact_task(self, task: Any) -> dict[str, Any]:
        data = self._dump_obj(task)

        return {
            "id": data.get("id", data.get("temp_id")),
            "character_ids": data.get("character_ids", []),
            "private": data.get("private"),
            "priority": data.get("priority"),
            "status": data.get("status"),
            "type": data.get("type"),
            "goal": data.get("goal"),
            "progress": data.get("progress"),
            "source": data.get("source"),
        }

    def _compact_world_entry(self, entry: Any) -> dict[str, Any]:
        data = self._dump_obj(entry)

        return {
            "id": data.get("id", data.get("temp_id")),
            "scope": data.get("scope", []),
            "content": data.get("content"),
            "visibility": data.get("visibility"),
            "confidence": data.get("confidence"),
            "narration_permission": data.get("narration_permission"),
            "recall_type": data.get("recall_type"),
            "keywords": data.get("keywords"),
            "chained_ids": data.get("chained_ids"),
            "semantic_instruction": data.get("semantic_instruction"),
        }

    def _compact_faction(self, faction: Any) -> dict[str, Any]:
        data = self._dump_obj(faction)

        return {
            "id": data.get("id", data.get("temp_id")),
            "name": data.get("name"),
            "description": data.get("description"),
            "attributes": data.get("attributes", {}),
            "stats": data.get("stats", {}),
        }

    def _compact_faction_relationship(self, relationship: Any) -> dict[str, Any]:
        data = self._dump_obj(relationship)

        return {
            "id": data.get("id", data.get("temp_id")),
            "from_type": data.get("from_type"),
            "from_id": data.get("from_id"),
            "to_type": data.get("to_type"),
            "to_id": data.get("to_id"),
            "relationship": data.get("relationship"),
            "private": data.get("private"),
        }

    def _compact_sandbox_state(self, template_view: bool = False) -> dict[str, Any]:
        return {
            "simulation": self._compact_simulation(),
            "state": self._compact_state(),
            "characters": [
                self._compact_character(character)
                for character in self._sandbox["characters"]
            ],
            "locations": [
                self._compact_location(location)
                for location in self._sandbox["locations"]
            ],
            "inventory": {
                owner_id: (
                    self._compact_inventory_template_view(inventory)
                    if template_view
                    else self._compact_inventory(inventory)
                )
                for owner_id, inventory in self._sandbox["inventory"].items()
            },
            "factions": [
                self._compact_faction(faction)
                for faction in self._sandbox["factions"]
            ],
            "faction_relationships": [
                self._compact_faction_relationship(relationship)
                for relationship in self._sandbox["faction_relationships"]
            ],
            "tasks": [
                self._compact_task(task)
                for task in self._sandbox["tasks"]
            ],
            "world_entries": [
                self._compact_world_entry(entry)
                for entry in self._sandbox["world_entries"]
            ],
        }

    def _compact_original_state(self) -> dict[str, Any]:
        original_sandbox = self._sandbox
        try:
            self._sandbox = self._original
            return self._compact_sandbox_state()
        finally:
            self._sandbox = original_sandbox

    def _render_safe_snapshot(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        inventory = snapshot.get("inventory")

        if isinstance(inventory, dict):
            snapshot["inventory"] = {
                owner_id: _InventoryTemplateView(
                    items=(
                        inv.get("items", [])
                        if isinstance(inv, dict)
                        else self._inventory_values(inv, "items")
                    ),
                    equipments=(
                        inv.get("equipments", [])
                        if isinstance(inv, dict)
                        else self._inventory_values(inv, "equipments")
                    ),
                )
                for owner_id, inv in inventory.items()
            }

        return snapshot

    def _data_preset_text(self) -> str:
        preset = self._sandbox["data_preset"]
        data = self._dump_obj(preset)

        lines: list[str] = []

        lines.append("Entity types:")
        entity_types = data.get("entity_types") or {}
        if entity_types:
            for type_name, description in entity_types.items():
                lines.append(f"- {type_name}: {description}")
        else:
            lines.append("- None.")

        lines.append("")
        lines.append("Character attributes:")
        character_attributes = data.get("character_attributes") or []
        if character_attributes:
            for attr in character_attributes:
                lines.append(f"- {attr.get('name')}")
                lines.append(f"  Universal: {attr.get('universal')}")
                lines.append(f"  Allowed values: {attr.get('values') or 'open'}")
                lines.append(f"  Creation instruction: {attr.get('creation_instruction') or ''}")
                lines.append(f"  Update instruction: {attr.get('update_instruction') or ''}")
        else:
            lines.append("- None.")

        lines.append("")
        lines.append("Character stats:")
        character_stats = data.get("character_stats") or []
        if character_stats:
            for stat in character_stats:
                lines.append(f"- {stat.get('name')}")
                lines.append(f"  Universal: {stat.get('universal')}")
                lines.append(f"  Creation instruction: {stat.get('creation_instruction') or ''}")
                lines.append(f"  Update instruction: {stat.get('update_instruction') or ''}")
        else:
            lines.append("- None.")

        lines.append("")
        lines.append("Faction attributes:")
        faction_attributes = data.get("faction_attributes") or []
        if faction_attributes:
            for attr in faction_attributes:
                lines.append(f"- {attr.get('name')}")
                lines.append(f"  Universal: {attr.get('universal')}")
                lines.append(f"  Allowed values: {attr.get('values') or 'open'}")
                lines.append(f"  Creation instruction: {attr.get('creation_instruction') or ''}")
                lines.append(f"  Update instruction: {attr.get('update_instruction') or ''}")
        else:
            lines.append("- None.")

        lines.append("")
        lines.append("Faction stats:")
        faction_stats = data.get("faction_stats") or []
        if faction_stats:
            for stat in faction_stats:
                lines.append(f"- {stat.get('name')}")
                lines.append(f"  Universal: {stat.get('universal')}")
                lines.append(f"  Creation instruction: {stat.get('creation_instruction') or ''}")
                lines.append(f"  Update instruction: {stat.get('update_instruction') or ''}")
        else:
            lines.append("- None.")

        return "\n".join(lines)

    def _compact_resolved_action(self, action: Any, index: int) -> dict[str, Any]:
        data = self._dump_obj(action)

        return {
            "index": index,
            "actor_id": data.get("actor_id"),
            "actor_name": data.get("actor_name"),
            "original_intent": data.get("original_intent"),
            "final_status": data.get("final_status"),
            "resolved_order": data.get("resolved_order"),
            "visible_result": data.get("visible_result"),
            "failure_reason": data.get("failure_reason"),
            "blocking_actor_id": data.get("blocking_actor_id"),
            "blocking_entity_id": data.get("blocking_entity_id"),
            "state_change_hints": data.get("state_change_hints", []),
            "world_entry_hints": data.get("world_entry_hints", []),
        }

    def _compact_resolver_output(self, resolver_output: Any) -> dict[str, Any]:
        data = self._dump_obj(resolver_output)

        actions = data.get("resolved_actions", []) if isinstance(data, dict) else []

        return {
            "accepted": data.get("accepted"),
            "rejection_reason": data.get("rejection_reason"),
            "resolved_actions": [
                self._compact_resolved_action(action, index)
                for index, action in enumerate(actions, start=1)
            ],
            "conflicts": data.get("conflicts", []),
            "failed_characters": data.get("failed_characters", []),
            "scene_result_summary": data.get("scene_result_summary"),
            "next_round_note": data.get("next_round_note"),
            "state_update_suggestions": data.get("state_update_suggestions", []),
            "pending_world_entry_suggestions": data.get("pending_world_entry_suggestions", []),
            "requires_director_rerun": data.get("requires_director_rerun"),
            "director_rerun_reason": data.get("director_rerun_reason"),
        }

    def _compact_character_action(self, action: Any) -> dict[str, Any]:
        data = self._dump_obj(action)

        return {
            "character_id": data.get("character_id"),
            "character_name": data.get("character_name"),
            "intent": data.get("intent"),
            "action_type": data.get("action_type"),
            "target_character_ids": data.get("target_character_ids", []),
            "target_entity_ids": data.get("target_entity_ids", []),
            "target_location_id": data.get("target_location_id"),
            "target_item_ids": data.get("target_item_ids", []),
            "method": data.get("method"),
            "visible_behavior": data.get("visible_behavior"),
            "spoken_intent": data.get("spoken_intent"),
            "expected_outcome": data.get("expected_outcome"),
            "constraints_for_resolver": data.get("constraints_for_resolver", []),
        }

    def _compact_character_actions(self, actions: list[Any]) -> list[dict[str, Any]]:
        return [
            self._compact_character_action(action)
            for action in actions
        ]

    def _compact_pending_proposal(self, proposal: Any) -> dict[str, Any]:
        data = self._dump_obj(proposal)

        if not isinstance(data, dict):
            return {"raw": str(data)}

        return {
            "id": data.get("id"),
            "temp_id": data.get("temp_id"),
            "proposal_type": data.get("proposal_type"),
            "status": data.get("status"),
            "result": data.get("result"),
            "reason": data.get("reason"),
        }

    def _compact_pending_proposals(self, proposals: list[Any] | None) -> list[dict[str, Any]]:
        return [
            self._compact_pending_proposal(proposal)
            for proposal in proposals or []
        ]

    async def commit_changes(
        self,
        user_input: str | None,
        director_output: Any | None,
        briefing_output: Any | None,
        character_actions: list[Any],
        resolver_output: Any,
        pending_generated_proposals: list[Any] | None = None,
        max_mutation_rounds: int | None = None,
        config: RunnableConfig | None = None,
    ) -> CommitterFinalOutput:
        max_rounds = max_mutation_rounds or getattr(
            self.profile,
            "max_mutation_rounds",
            4,
        )

        previous_validation: CommitterValidationOutput | None = None
        previous_execution_results: list[dict[str, Any]] = []
        all_warnings: list[str] = []

        for round_index in range(max_rounds):
            final_round = round_index + 1 >= max_rounds

            compact_resolver_output = self._compact_resolver_output(resolver_output)
            compact_character_actions = self._compact_character_actions(character_actions)
            compact_pending_proposals = self._compact_pending_proposals(pending_generated_proposals)

            data = {
                "mutation_round": round_index + 1,
                "max_mutation_rounds": max_rounds,
                "user_input": user_input,
                "character_actions": compact_character_actions,
                "resolver_output": compact_resolver_output,
                "resolved_action_text": self._resolved_action_text(compact_resolver_output),
                "resolver_state_change_hints": self._resolver_state_change_hints(compact_resolver_output),
                "resolver_world_entry_hints": self._resolver_world_entry_hints(compact_resolver_output),
                "pending_generated_proposals": compact_pending_proposals,
                "data_preset_text": self._data_preset_text(),
                "original_state": self._compact_original_state(),
                "current_sandbox_state": self._compact_sandbox_state(template_view=True),
                "mutation_log": self.mutation_log(),
                "previous_validation": (
                    previous_validation.model_dump()
                    if previous_validation is not None
                    else None
                ),
                "previous_execution_results": previous_execution_results,
                "available_operations": [
                    "update_simulation_state",
                    "update_character",
                    "update_location",
                    "update_entity",
                    "create_location",
                    "create_world_entry",
                    "create_task",
                    "update_task",
                    "update_inventory",
                    "create_object",
                    "remove_object",
                    "accept_generated_proposal",
                    "reject_generated_proposal",
                    "defer_generated_proposal",
                    "noop",
                ],
            }

            plan_messages = self._compose_messages(
                prompts=self.profile.mutation_prompt,
                data=data,
            )

            plan_model = self.model.with_structured_output(CommitterMutationPlanOutput)

            try:
                plan = cast(
                    CommitterMutationPlanOutput,
                    await self._invoke_structured_with_repair(
                        output_model=CommitterMutationPlanOutput,
                        messages=plan_messages,
                        repair_instruction=(
                            "You must return a valid CommitterMutationPlanOutput. "
                            "If changes are needed, mutations must contain at least one concrete mutation. "
                            "If no changes are needed, set no_changes_needed=true and mutations=[]. "
                            "Never return mutations=[] with no_changes_needed=false."
                        ),
                        run_name="committer_mutation_plan",
                        max_attempts=2,
                    ),
                )
                plan = self._normalise_plan(plan)
            except Exception as exc:
                plan = self._fallback_plan(
                    resolver_output=resolver_output,
                    pending_generated_proposals=pending_generated_proposals,
                    reason=f"Structured mutation planning failed: {type(exc).__name__}: {exc}",
                )

            if plan.warnings:
                all_warnings.extend(plan.warnings)

            if plan.no_changes_needed and not plan.mutations and not self._mutation_log:
                plan = self._fallback_plan(
                    resolver_output=resolver_output,
                    pending_generated_proposals=pending_generated_proposals,
                    reason="Planner claimed no changes were needed before any mutation was recorded.",
                )
                all_warnings.extend(plan.warnings)

            if not plan.mutations and not plan.no_changes_needed:
                plan = self._fallback_plan(
                    resolver_output=resolver_output,
                    pending_generated_proposals=pending_generated_proposals,
                    reason="Planner returned no mutations and did not mark no_changes_needed.",
                )
                all_warnings.extend(plan.warnings)

            execution_results: list[dict[str, Any]] = []

            for mutation in plan.mutations:
                if mutation.operation == "noop" and self._mutation_log:
                    continue

                try:
                    record = self._execute_mutation(mutation)
                    execution_results.append(
                        {
                            "success": True,
                            "operation": mutation.operation,
                            "args": mutation.args,
                            "record": record.model_dump(),
                        }
                    )
                except Exception as exc:
                    execution_results.append(
                        {
                            "success": False,
                            "operation": mutation.operation,
                            "args": mutation.args,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        }
                    )

            previous_execution_results = execution_results

            validation_data = {
                **data,
                "current_sandbox_state": self._render_safe_snapshot(),
                "mutation_log": self.mutation_log(),
                "latest_plan": plan.model_dump(),
                "latest_execution_results": execution_results,
            }

            validation_messages = self._compose_messages(
                prompts=self.profile.validation_prompt,
                data=validation_data,
            )

            validation_model = self.model.with_structured_output(CommitterValidationOutput)

            try:
                previous_validation = cast(
                    CommitterValidationOutput,
                    await self._invoke_structured_with_repair(
                        output_model=CommitterValidationOutput,
                        messages=validation_messages,
                        repair_instruction=(
                            "You must return a valid CommitterValidationOutput. "
                            "If the sandbox is complete, set complete=true and needs_more_changes=false. "
                            "If changes are still missing, set complete=false and needs_more_changes=true "
                            "with concrete missing_changes and next_instruction."
                        ),
                        run_name="committer_validation",
                        max_attempts=2,
                    ),
                )
                previous_validation = self._normalise_validation(previous_validation)
            except Exception as exc:
                previous_validation = CommitterValidationOutput(
                    complete=False,
                    needs_more_changes=not final_round,
                    missing_changes=[
                        "Validation structured output failed."
                    ],
                    questionable_changes=[
                        f"{type(exc).__name__}: {exc}"
                    ],
                    consistency_notes=[],
                    next_instruction=(
                        "Retry mutation planning conservatively."
                        if not final_round
                        else None
                    ),
                )

            if previous_validation.complete and not previous_validation.needs_more_changes:
                break

        if previous_validation is None:
            previous_validation = CommitterValidationOutput(
                complete=False,
                needs_more_changes=False,
                missing_changes=["Committer loop produced no validation output."],
                questionable_changes=[],
                consistency_notes=[],
                next_instruction=None,
            )

        return self._build_final_output(
            resolver_output=resolver_output,
            validation=previous_validation,
            extra_warnings=all_warnings,
        )
