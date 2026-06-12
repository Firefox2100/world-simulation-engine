import json
from uuid import uuid4
from copy import deepcopy
from typing import Any, cast
from langchain.tools import tool
from langchain.messages import ToolMessage
from .world_agent import WorldAgent

from world_simulation_engine.model import CommitterAgentProfile, Simulation, SimulationState, Character, \
    Location, CharacterInventory, Task, WorldEntry, LlmConnectionProfile, SandboxMutationRecord, SandboxObjectRef, \
    CommitterValidationOutput, CommitterFinalOutput


class CommitterAgent(WorldAgent[CommitterAgentProfile]):
    def __init__(self,
                 profile: CommitterAgentProfile,
                 connection: LlmConnectionProfile,
                 simulation: Simulation,
                 state: SimulationState,
                 characters: list[Character],
                 locations: list[Location],
                 inventory: dict[int, CharacterInventory],
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
            if getattr(obj, "id", None) == object_id:
                return index, obj
        raise KeyError(f"{collection_name} object id={object_id} not found")

    def _patch_model_object(self, obj: Any, patch: dict[str, Any]) -> Any:
        if hasattr(obj, "model_copy"):
            return obj.model_copy(update=patch)

        for key, value in patch.items():
            setattr(obj, key, value)

        return obj

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

            This does not write to the database.
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
            """
            loc_index, loc = self._find_list_object("locations", location_id)

            for entity_index, entity in enumerate(loc.entities):
                if entity.id == entity_id:
                    updated_entity = self._patch_model_object(entity, patch)
                    new_entities = list(loc.entities)
                    new_entities[entity_index] = updated_entity
                    self._sandbox["locations"][loc_index] = loc.model_copy(update={"entities": new_entities})
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
            """
            self._sandbox["locations"].append(data)
            return self._record(
                operation="create",
                target=SandboxObjectRef(object_type="location", object_id=data.get("id", data.get("temp_id", "new"))),
                payload=data,
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
            """
            self._sandbox["world_entries"].append(data)
            return self._record(
                operation="create",
                target=SandboxObjectRef(object_type="world_entry", object_id=data.get("id", data.get("temp_id", "new"))),
                payload=data,
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
            """
            self._sandbox["tasks"].append(data)
            return self._record(
                operation="create",
                target=SandboxObjectRef(object_type="task", object_id=data.get("id", data.get("temp_id", "new"))),
                payload=data,
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

            This does not write to the database.
            """
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

            This records removal intent. Your database layer should validate it.
            """
            return self._record(
                operation="remove",
                target=SandboxObjectRef(object_type=object_type, object_id=object_id),
                payload={},
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
            }

            messages = self._compose_messages(
                prompts=self.profile.mutation_prompt,
                data=data,
            )

            ai_msg = await tool_model.ainvoke(messages)
            tool_calls = getattr(ai_msg, "tool_calls", None) or []

            if tool_calls:
                for call in tool_calls:
                    name = call["name"]
                    args = call.get("args", {})
                    tool_call_id = call.get("id")

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

                    _ = ToolMessage(
                        content=json.dumps(result_payload, ensure_ascii=False, default=str),
                        tool_call_id=tool_call_id,
                        name=name,
                    )

            validation_data = {
                **data,
                "current_sandbox_state": self.snapshot(),
                "mutation_log": self.mutation_log(),
            }

            validation_messages = self._compose_messages(
                prompts=self.profile.validation_prompt,
                data=validation_data,
            )

            validation_model = self.model.with_structured_output(CommitterValidationOutput)
            previous_validation = await validation_model.ainvoke(validation_messages)

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
