"""Run many independent async calls concurrently through LangGraph's `Send` mechanism.

Mirrors the private fan-out sub-graph `WorldSimulator` already uses internally
(`_FanOutWork`/`_build_fan_out_graph`), kept as a separate, self-contained copy here rather than
imported from `component.simulator.world_simulator` - that module's helpers are private
implementation detail of the turn-generation graph, not a shared utility, and duplicating ~30
lines is a smaller risk than coupling this package to it.
"""

import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar

from langgraph.constants import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, ConfigDict, Field

ResultT = TypeVar("ResultT")


class _FanOutWork(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    index: int
    call: Callable[[], Awaitable[Any]]


class _FanOutState(BaseModel):
    """`results` uses an additive reducer so each Send-dispatched worker's single-item result
    list merges into the shared list instead of one overwriting another; caller-visible order is
    restored afterward from `index`, since completion order does not track dispatch order."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[_FanOutWork] = Field(default_factory=list)
    results: Annotated[list[tuple[int, Any]], operator.add] = Field(default_factory=list)


async def _fan_out_worker(work: _FanOutWork) -> dict:
    result = await work.call()
    return {"results": [(work.index, result)]}


def _fan_out_dispatch(state: _FanOutState):
    if not state.items:
        return END
    return [Send("fan_out_worker", item) for item in state.items]


def build_fan_out_graph() -> CompiledStateGraph:
    graph = StateGraph(_FanOutState)
    graph.add_node("fan_out_worker", _fan_out_worker, input_schema=_FanOutWork)
    graph.add_conditional_edges(START, _fan_out_dispatch)
    graph.add_edge("fan_out_worker", END)
    return graph.compile()


async def run_fan_out(
        graph: CompiledStateGraph,
        calls: list[Callable[[], Awaitable[ResultT]]],
        *,
        max_concurrency: int,
        run_name: str = "fan_out",
) -> list[ResultT]:
    """Run every call concurrently (capped at `max_concurrency`), preserving `calls`' order."""
    if not calls:
        return []

    final_state = await graph.ainvoke(
        _FanOutState(items=[_FanOutWork(index=index, call=call) for index, call in enumerate(calls)]),
        config={"max_concurrency": max_concurrency, "run_name": run_name},
    )
    results = final_state["results"] if isinstance(final_state, dict) else final_state.results
    return [result for _, result in sorted(results, key=lambda pair: pair[0])]
