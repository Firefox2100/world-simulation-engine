import json
from typing import Any, cast
from langchain.messages import ToolMessage

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task, \
    Item, Equipment, Faction, FactionRelationship, DirectorAgentProfile, DirectorOutput, PendingGeneratedProposal
from .world_agent import WorldAgent


class DirectorAgent(WorldAgent[DirectorAgentProfile]):
    """
    Schedules the turn and decides which agents to activate.
    Does not build per-character briefings.
    """
    def _normalise_director_output(
            self,
            output: DirectorOutput,
    ) -> DirectorOutput:
        any_active = any(
            activation.activate
            for activation in output.activations
        )

        # Hard invariant:
        # If anyone is active, the graph must not wait for user.
        if any_active:
            output.wait_for_user = False
            output.reason_to_wait = None

        # Hard invariant:
        # If waiting for user, nobody acts.
        if output.wait_for_user:
            for activation in output.activations:
                activation.activate = False
                activation.priority = 0

            if not output.reason_to_wait:
                output.reason_to_wait = (
                    "The scene has reached a player decision point."
                )

        # Hard invariant:
        # Inactive characters cannot have priority.
        for activation in output.activations:
            if not activation.activate:
                activation.priority = 0

        return output

    async def plan_turn(self,
                        simulation: Simulation,
                        state: SimulationState,
                        current_location: Location,
                        user_characters: list[Character],
                        present_characters: list[Character],
                        relevant_tasks: list[Task],
                        recalled_world_entries: list[WorldEntry],
                        generation_tools: list,
                        existing_items: list[Item] | None = None,
                        existing_equipments: list[Equipment] | None = None,
                        factions: list[Faction] | None = None,
                        faction_relationships: list[FactionRelationship] | None = None,
                        user_input: str | None = None,
                        last_narration: str | None = None,
                        previous_resolver_notes: str | None = None,
                        ) -> tuple[DirectorOutput, list[PendingGeneratedProposal]]:
        generation_data = {
            "simulation": simulation,
            "data_preset": simulation.data_preset,
            "state": state,
            "last_narration": last_narration,
            "user_input": user_input,
            "previous_resolver_notes": previous_resolver_notes,
            "location": current_location,
            "present_characters": present_characters,
            "relevant_tasks": relevant_tasks,
            "recalled_world_entries": recalled_world_entries,
            "existing_items": existing_items or [],
            "existing_equipments": existing_equipments or [],
            "factions": factions or [],
            "faction_relationships": faction_relationships or [],
        }
        generation_messages = self._compose_messages(
            prompts=self.profile.generation_prompt,
            data=generation_data,
        )
        tool_results: list[dict[str, Any]] = []
        working = list(generation_messages)

        if generation_tools:
            model_with_tools = self.model.bind_tools(generation_tools)
            tools_by_name = {tool.name: tool for tool in generation_tools}

            for _ in range(self.profile.max_tool_rounds):
                ai_msg = await model_with_tools.ainvoke(
                    working,
                    config={"run_name": "director_tool_calling"},
                )
                working.append(ai_msg)

                tool_calls = getattr(ai_msg, "tool_calls", None) or []
                if not tool_calls:
                    break

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
                            raw_result = await tools_by_name[name].ainvoke(args)

                            if hasattr(raw_result, "model_dump"):
                                result_payload = raw_result.model_dump()
                            elif isinstance(raw_result, dict):
                                result_payload = raw_result
                            else:
                                result_payload = {"result": raw_result}

                            tool_results.append(
                                {
                                    "tool_name": name,
                                    "trigger": args.get("trigger", ""),
                                    "result": result_payload,
                                    "intended_use": args.get(
                                        "trigger",
                                        "Generated pending content for this round.",
                                    ),
                                }
                            )

                        except Exception as exc:
                            result_payload = {
                                "error": type(exc).__name__,
                                "message": str(exc),
                                "tool": name,
                                "args": args,
                            }

                    working.append(
                        ToolMessage(
                            content=json.dumps(
                                result_payload,
                                ensure_ascii=False,
                                default=str,
                            ),
                            tool_call_id=tool_call_id,
                            name=name,
                        )
                    )

        scheduling_data = {
            "simulation": simulation,
            "state": state,
            "last_narration": last_narration,
            "user_input": user_input,
            "previous_resolver_notes": previous_resolver_notes,
            "location": current_location,
            "user_characters": user_characters,
            "present_characters": present_characters,
            "relevant_tasks": relevant_tasks,
            "recalled_world_entries": recalled_world_entries,
            "pending_generated_proposals": tool_results,
        }

        final_messages = self._compose_messages(
            prompts=self.profile.planning_prompt,
            data=scheduling_data,
        )

        result = cast(
            DirectorOutput,
            await self._invoke_structured_with_repair(
                output_model=DirectorOutput,
                messages=final_messages,
                repair_instruction=(
                    "You must return a valid DirectorOutput. "
                ),
                run_name="director_planning",
                max_attempts=2,
            ),
        )

        return (
            self._normalise_director_output(result),
            [PendingGeneratedProposal.model_validate(p) for p in tool_results],
        )
