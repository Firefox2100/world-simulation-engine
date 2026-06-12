from uuid import uuid4
from copy import deepcopy
from typing import Any, cast
from langchain.tools import tool
from .world_agent import WorldAgent

from world_simulation_engine.model import CommitterAgentProfile, Simulation, SimulationState, Character, \
    Location, CharacterInventory, Task, WorldEntry, LlmConnectionProfile, SandboxMutationRecord, SandboxObjectRef, \
    CommitterValidationOutput, CommitterFinalOutput, Faction, FactionRelationship


class CommitterAgent(WorldAgent[CommitterAgentProfile]):
    def __init__(self,
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

    def _record(
        self,
        *,
        operation: str,
        target: SandboxObjectRef | None,
        payload: dict[str, Any],
        reason: str,
        source_event: str | None = None,
    ) -> dict[str, Any]:
        record = SandboxMutationRecord(
            mutation_id=str(uuid4()),
            operation=operation,
            target=target,
            payload=payload,
            reason=reason,
            source_event=source_event,
        )
        self._mutation_log.append(record)
        return record.model_dump()

    def _find_list_object(self, collection_name: str, object_id: int):
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

    def _append_collection_object(
        self,
        collection_name: str,
        object_type: str,
        data: dict[str, Any],
        reason: str,
        source_event: str | None = None,
    ) -> dict[str, Any]:
        self._sandbox[collection_name].append(data)
        return self._record(
            operation="create",
            target=SandboxObjectRef(object_type=object_type, object_id=data.get("id", data.get("temp_id", "new"))),
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
    ) -> dict[str, Any]:
        owner_id = data.get("owner_id", data.get("character_id", data.get("proposed_owner_id", 0))) or 0
        if owner_id not in self._sandbox["inventory"]:
            self._sandbox["inventory"][owner_id] = CharacterInventory()

        inventory = self._sandbox["inventory"][owner_id]
        field_name = "equipments" if object_type == "equipment" else "items"
        current_values = inventory[field_name] if isinstance(inventory, dict) else getattr(inventory, field_name)
        self._sandbox["inventory"][owner_id] = self._patch_model_object(
            inventory,
            {
                field_name: [*current_values, data],
            },
        )
        return self._record(
            operation="create",
            target=SandboxObjectRef(object_type=object_type, object_id=data.get("id", data.get("temp_id", "new"))),
            payload={"owner_id": owner_id, **data},
            reason=reason,
            source_event=source_event,
        )

    def _create_entity_object(
        self,
        data: dict[str, Any],
        reason: str,
        source_event: str | None = None,
    ) -> dict[str, Any]:
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
            target=SandboxObjectRef(object_type="entity", object_id=data.get("id", data.get("temp_id", "new"))),
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
            current_values = inventory[field_name] if isinstance(inventory, dict) else getattr(inventory, field_name)
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

    def get_tools(self):
        @tool
        def update_simulation_state(
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update the current SimulationState in the sandbox.

            Use this every turn to update the overall scene/state summary,
            round-level state, scene id, time label, or other SimulationState fields.

            Args:
                patch: Partial SimulationState fields to update, such as state, scene, time_label, or summaries.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            self._sandbox["state"] = self._patch_model_object(
                self._sandbox["state"],
                patch,
            )
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="state", object_id=self._sandbox["state"].id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def update_character(
            character_id: int,
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update an existing character in the sandbox.

            Use for public_state, private_state, location, attributes, stats,
            or other character fields that changed because of resolved events.

            Do not delete dead or absent characters. Use state changes instead.

            Args:
                character_id: Existing character ID to update.
                patch: Partial Character fields to update.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            index, obj = self._find_list_object("characters", character_id)
            self._sandbox["characters"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="character", object_id=character_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def update_location(
            location_id: int,
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update an existing location in the sandbox.

            Use for changed location description, scene status, attributes, stats,
            or entity list changes when the whole location needs patching.

            Prefer update_entity for a single entity status change.

            Args:
                location_id: Existing location ID to update.
                patch: Partial Location fields to update.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            index, obj = self._find_list_object("locations", location_id)
            self._sandbox["locations"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="location", object_id=location_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def update_entity(
            location_id: int,
            entity_id: int,
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update an entity inside a location.

            Use for changed entity status, description, interactions, or other
            entity properties after a resolved action.

            Prefer status changes over deletion for auditability.

            Args:
                location_id: Existing location ID containing the entity.
                entity_id: Existing entity ID to update.
                patch: Partial Entity fields to update.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            loc_index, loc = self._find_list_object("locations", location_id)
            entities = loc["entities"] if isinstance(loc, dict) else loc.entities

            for entity_index, entity in enumerate(entities):
                if self._object_id(entity) == entity_id:
                    updated_entity = self._patch_model_object(entity, patch)
                    new_entities = list(entities)
                    new_entities[entity_index] = updated_entity
                    self._sandbox["locations"][loc_index] = self._patch_model_object(loc, {"entities": new_entities})
                    return self._record(
                        operation="update",
                        target=SandboxObjectRef(object_type="entity", object_id=entity_id),
                        payload={"location_id": location_id, **patch},
                        reason=reason,
                        source_event=source_event,
                    )

            raise KeyError(f"Entity id={entity_id} not found in location id={location_id}")

        @tool
        def create_location(
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Create a new location in the sandbox.

            Use when an accepted generated proposal or resolved event introduces
            a new canonical location.

            Use temporary negative/string IDs only if the database ID is not known.

            Args:
                data: Complete Location-like payload to add to the sandbox.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the create mutation.
            """
            return self._append_collection_object(
                collection_name="locations",
                object_type="location",
                data=data,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def create_world_entry(
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Create a new world-entry fact in the sandbox.

            Use for persistent knowledge, rumours, memories, beliefs, scoped facts,
            newly revealed information, or GM-side truth that must enter recall.

            Content must be a complete factual sentence.

            Args:
                data: Complete WorldEntry-like payload to add to the sandbox.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the create mutation.
            """
            return self._append_collection_object(
                collection_name="world_entries",
                object_type="world_entry",
                data=data,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def create_task(
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Create a new task in the sandbox.

            Use when resolved events create a new goal, obligation, lead,
            investigation thread, promise, danger, or persistent objective.

            Args:
                data: Complete Task-like payload to add to the sandbox.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the create mutation.
            """
            return self._append_collection_object(
                collection_name="tasks",
                object_type="task",
                data=data,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def update_task(
            task_id: int,
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update an existing task.

            Use for progress, status, priority, goal refinement, source update,
            or task completion after resolved events.

            Args:
                task_id: Existing task ID to update.
                patch: Partial Task fields to update.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            index, obj = self._find_list_object("tasks", task_id)
            self._sandbox["tasks"][index] = self._patch_model_object(obj, patch)
            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="task", object_id=task_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def update_inventory(
            owner_id: int,
            patch: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Update a character inventory in the sandbox.

            Use for adding/removing/updating items and equipment.

            The patch may replace the items/equipments list or update inventory metadata.

            Args:
                owner_id: Character ID whose inventory should be patched.
                patch: Partial CharacterInventory fields, usually items and/or equipments.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the update mutation.
            """
            if owner_id not in self._sandbox["inventory"]:
                raise KeyError(f"Inventory owner id={owner_id} not found")

            inv = self._sandbox["inventory"][owner_id]
            self._sandbox["inventory"][owner_id] = self._patch_model_object(inv, patch)

            return self._record(
                operation="update",
                target=SandboxObjectRef(object_type="inventory", object_id=owner_id),
                payload=patch,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def create_object(
            object_type: str,
            data: dict[str, Any],
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Generic create operation for sandbox objects not covered by specialised tools.

            Use sparingly. Prefer specialised tools when possible.
            Supported object_type examples:
            character, item, equipment, entity, faction, faction_relationship.
            For item/equipment, include owner_id, character_id, or proposed_owner_id in data when known.
            For entity, include location_id or proposed_location_id in data.

            Args:
                object_type: Type of object to create. Prefer a specialised tool for state, location, task, and world_entry.
                data: Complete object payload to add to the sandbox or preview in the mutation log.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the create mutation.
            """
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
                target=SandboxObjectRef(object_type=object_type, object_id=data.get("id", data.get("temp_id", "new"))),
                payload=data,
                reason=reason,
                source_event=source_event,
            )

        @tool
        def remove_object(
            object_type: str,
            object_id: int | str,
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Mark an object for removal from the sandbox.

            Use sparingly. Prefer status updates for narrative changes.
            Do not remove characters merely because they die, leave, vanish, or become inactive.

            This removes the object from the sandbox when it can be found and records removal intent.
            The database layer should still validate removals before persistence.

            Args:
                object_type: Type of object to remove.
                object_id: Existing object ID or temporary proposal ID.
                reason: Short justification tied to a resolver result or accepted proposal.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the remove mutation.
            """
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

        @tool
        def accept_generated_proposal(
            temp_id: str,
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Mark a pending generated proposal as accepted.

            Use when a resolved event confirms that the proposed content should
            become canonical. You must also create/update the corresponding
            canonical object with another tool call.

            Args:
                temp_id: Temporary proposal ID to accept.
                reason: Short justification tied to a resolver result.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the proposal acceptance.
            """
            return self._record(
                operation="accept_proposal",
                target=SandboxObjectRef(object_type="pending_generated_proposal", object_id=temp_id),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        @tool
        def reject_generated_proposal(
            temp_id: str,
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Mark a pending generated proposal as rejected.

            Use when a proposed generated object is not supported by resolved events.

            Args:
                temp_id: Temporary proposal ID to reject.
                reason: Short justification tied to a resolver result.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the proposal rejection.
            """
            return self._record(
                operation="reject_proposal",
                target=SandboxObjectRef(object_type="pending_generated_proposal", object_id=temp_id),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        @tool
        def defer_generated_proposal(
            temp_id: str,
            reason: str,
            source_event: str | None = None,
        ) -> dict[str, Any]:
            """
            Mark a pending generated proposal as deferred.

            Use when it may become canonical later, but this turn does not confirm it.

            Args:
                temp_id: Temporary proposal ID to defer.
                reason: Short justification tied to a resolver result.
                source_event: Optional ID or text naming the source resolved action/proposal.

            Returns:
                SandboxMutationRecord as a dict describing the proposal deferral.
            """
            return self._record(
                operation="defer_proposal",
                target=SandboxObjectRef(object_type="pending_generated_proposal", object_id=temp_id),
                payload={},
                reason=reason,
                source_event=source_event,
            )

        return [
            update_simulation_state,
            update_character,
            update_location,
            update_entity,
            create_location,
            create_world_entry,
            create_task,
            update_task,
            update_inventory,
            create_object,
            remove_object,
            accept_generated_proposal,
            reject_generated_proposal,
            defer_generated_proposal,
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
    ) -> CommitterFinalOutput:
        max_rounds = max_mutation_rounds or getattr(self.profile, "max_mutation_rounds", 4)

        tools = self.get_tools()
        tool_model = self.model.bind_tools(tools)
        tools_by_name = {tool.name: tool for tool in tools}

        previous_validation: CommitterValidationOutput | None = None
        previous_tool_results: list[dict[str, Any]] = []

        for round_index in range(max_rounds):
            data = {
                "mutation_round": round_index + 1,
                "max_mutation_rounds": max_rounds,
                "user_input": user_input,
                "director_output": self._dump_obj(director_output),
                "briefing_output": self._dump_obj(briefing_output),
                "character_actions": self._dump_obj(character_actions),
                "resolver_output": self._dump_obj(resolver_output),
                "pending_generated_proposals": self._dump_obj(pending_generated_proposals or []),
                "data_preset": self._dump_obj(self._sandbox["data_preset"]),
                "current_sandbox_state": self.snapshot(),
                "mutation_log": self.mutation_log(),
                "previous_validation": (
                    previous_validation.model_dump()
                    if previous_validation is not None
                    else None
                ),
                "previous_tool_results": previous_tool_results,
            }

            messages = self._compose_messages(
                prompts=self.profile.mutation_prompt,
                data=data,
            )

            ai_msg = await tool_model.ainvoke(messages)
            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            round_tool_results: list[dict[str, Any]] = []

            if tool_calls:
                for call in tool_calls:
                    name = call["name"]
                    args = call.get("args", {})

                    if name not in tools_by_name:
                        result_payload = {
                            "error": f"Unknown tool: {name}",
                            "available_tools": list(tools_by_name),
                        }
                    else:
                        try:
                            result_payload = await tools_by_name[name].ainvoke(args)
                        except Exception as exc:
                            result_payload = {
                                "error": type(exc).__name__,
                                "message": str(exc),
                                "tool": name,
                                "args": args,
                            }

                    round_tool_results.append({
                        "tool": name,
                        "args": args,
                        "result": self._dump_obj(result_payload),
                    })

            validation_data = {
                **data,
                "current_sandbox_state": self.snapshot(),
                "mutation_log": self.mutation_log(),
                "tool_results": round_tool_results,
            }

            validation_messages = self._compose_messages(
                prompts=self.profile.validation_prompt,
                data=validation_data,
            )

            validation_model = self.model.with_structured_output(CommitterValidationOutput)
            previous_validation = await validation_model.ainvoke(validation_messages)
            previous_tool_results = round_tool_results

            if previous_validation.complete and not previous_validation.needs_more_changes:
                break

        final_data = {
            "user_input": user_input,
            "director_output": self._dump_obj(director_output),
            "briefing_output": self._dump_obj(briefing_output),
            "character_actions": self._dump_obj(character_actions),
            "resolver_output": self._dump_obj(resolver_output),
            "pending_generated_proposals": self._dump_obj(pending_generated_proposals or []),
            "data_preset": self._dump_obj(self._sandbox["data_preset"]),
            "original_state": self._dump_obj(self._original),
            "final_sandbox_state": self.snapshot(),
            "mutation_log": self.mutation_log(),
            "tool_results": previous_tool_results,
            "last_validation": (
                previous_validation.model_dump()
                if previous_validation is not None
                else None
            ),
        }

        final_messages = self._compose_messages(
            prompts=self.profile.final_prompt,
            data=final_data,
        )

        final_model = self.model.with_structured_output(CommitterFinalOutput)
        return cast(CommitterFinalOutput, await final_model.ainvoke(final_messages))
