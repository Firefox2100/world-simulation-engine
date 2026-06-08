import json
from langchain.messages import ToolMessage, HumanMessage

from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task
from .world_agent import WorldAgent
from .models import DirectorOutput

class DirectorAgent(WorldAgent):
    """
    An agent responsible for planning the turn and deciding which other agents to activate.
    """

    async def plan_turn(
            self,
            simulation: Simulation,
            state: SimulationState,
            current_location: Location,
            present_characters: list[Character],
            relevant_tasks: list[Task],
            recalled_world_entries: list[WorldEntry],
            generation_tools: list,
            user_input: str | None = None,
            last_narration: str | None = None,
            recent_history_summary: str | None = None,
            long_term_history_summary: str | None = None,
            previous_resolver_notes: str | None = None,
    ) -> DirectorOutput:
        base_data = {
            "simulation": simulation,
            "state": state,
            "last_narration": last_narration,
            "user_input": user_input,
            "recent_history_summary": recent_history_summary,
            "long_term_history_summary": long_term_history_summary,
            "previous_resolver_notes": previous_resolver_notes,
            "location": current_location,
            "present_characters": present_characters,
            "relevant_tasks": relevant_tasks,
            "recalled_world_entries": recalled_world_entries,
            "pending_generated_proposals": [],
        }

        initial_messages = self._compose_messages(data=base_data)

        tool_results: list[dict] = []

        model_with_tools = self.model.bind_tools(generation_tools)
        tools_by_name = {tool.name: tool for tool in generation_tools}

        working = list(initial_messages)

        for _ in range(self.profile.max_tool_rounds):
            ai_msg = await model_with_tools.ainvoke(working)
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
                                "intended_use": args.get("trigger", "Generated pending content for this round."),
                                "resolver_policy": "resolver_decides",
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
                        content=json.dumps(result_payload, ensure_ascii=False, default=str),
                        tool_call_id=tool_call_id,
                        name=name,
                    )
                )

        # Rebuild clean final prompt.
        final_data = {
            **base_data,
            "pending_generated_proposals": tool_results,
        }

        final_messages = self._compose_messages(data=final_data)

        final_messages.append(
            HumanMessage(
                content="""
Produce the final DirectorOutput.

Rules:
- Do not treat pending generated proposals as canonical.
- Return only valid structured output.
"""
            )
        )

        structured_model = self.model.with_structured_output(DirectorOutput)

        return await structured_model.ainvoke(final_messages)
