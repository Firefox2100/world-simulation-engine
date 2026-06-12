import json
from typing import Any, cast
from langchain.messages import ToolMessage
from langchain_core.runnables import RunnableConfig, patch_config
from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.model import Simulation, SimulationState, Location, Character, WorldEntry, Task, \
    Item, Equipment, Faction, FactionRelationship, DirectorAgentProfile, DirectorOutput, PendingGeneratedProposal
from .world_agent import WorldAgent


class DirectorAgent(WorldAgent[DirectorAgentProfile]):
    """
    Schedules the turn and decides which agents to activate.
    Does not build per-character briefings.
    """

    async def plan_turn(self,
                        simulation: Simulation,
                        state: SimulationState,
                        current_location: Location,
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
                        config: RunnableConfig | None = None,
                        ) -> tuple[DirectorOutput, list[PendingGeneratedProposal]]:
        LOGGER.info("Planning turn %s for simulation %s", state.turn_number + 1, simulation.id)

        base_data = {
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
        LOGGER.debug("Base data:\n%s", TypeAdapter(dict[str, Any]).dump_json(base_data, indent=2).decode())

        generation_messages = self._compose_messages(
            prompts=self.profile.generation_prompt,
            data=base_data,
        )
        LOGGER.debug("Generation messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in generation_messages]))

        tool_results: list[dict[str, Any]] = []
        working = list(generation_messages)

        if generation_tools:
            model_with_tools = self.model.bind_tools(generation_tools)
            tools_by_name = {tool.name: tool for tool in generation_tools}

            for i in range(self.profile.max_tool_rounds):
                ai_msg = await model_with_tools.ainvoke(
                    working,
                    config=patch_config(
                        config,
                        run_name="director_tool_calling",
                    ) if config else None,
                )
                working.append(ai_msg)
                LOGGER.debug(
                    "Model returned potential tool calls:\n%s\n%s",
                    ai_msg.content,
                    getattr(ai_msg, "tool_calls", None) or []
                )

                tool_calls = getattr(ai_msg, "tool_calls", None) or []
                if not tool_calls:
                    LOGGER.info("Model stopped calling tools on turn %s", i + 1)
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
                    LOGGER.debug("Tool result added to messages:\n%s", working[-1].content)

        final_data = {
            **base_data,
            "pending_generated_proposals": tool_results,
        }

        final_messages = self._compose_messages(
            prompts=self.profile.planning_prompt,
            data=final_data,
        )

        LOGGER.info("Generating final plan for turn %s of simulation %s", state.turn_number + 1, simulation.id)
        LOGGER.debug("Final messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in final_messages]))

        structured_model = self.model.with_structured_output(DirectorOutput)
        return (
            cast(
                DirectorOutput,
                await structured_model.ainvoke(
                    final_messages,
                    config=patch_config(
                        config,
                        run_name="director_planning",
                    ) if config else None,
                )
            ),
            [PendingGeneratedProposal.model_validate(p) for p in tool_results]
        )
