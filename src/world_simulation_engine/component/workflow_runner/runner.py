import asyncio
import json
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langfuse.langchain import CallbackHandler


@dataclass
class WorkflowRunHandle:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class WorkflowRunner:
    def __init__(self,
                 graph: CompiledStateGraph,
                 langfuse_handler: CallbackHandler,
                 callback: Callable[[dict], Awaitable] | None = None,
                 ):
        self._graph = graph
        self._langfuse_handler = langfuse_handler
        self._callback = callback

        self._runs: dict[str, WorkflowRunHandle] = {}

    @staticmethod
    def _format_sse(event: str, data: Any):
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def _run_graph(self,
                         run_id: str,
                         input_data: dict[str, Any],
                         handle: WorkflowRunHandle,
                         run_name: str | None = None,
                         metadata: dict | None = None,
                         tags: list[str] | None = None,
                         ):
        payload = {}

        try:
            config: RunnableConfig = {
                "callbacks": [self._langfuse_handler],
                "configurable": {
                    "thread_id": run_id,
                },
            }
            if run_name:
                config["run_name"] = run_name
            if metadata:
                config["metadata"] = metadata
            if tags:
                config["tags"] = tags

            async for mode, chunk in self._graph.astream(
                input_data,
                config=config,
                stream_mode=["values", "updates", "messages"],
            ):
                if mode == "updates":
                    await handle.queue.put({
                        "event": "stage_update",
                        "data": chunk,
                    })
                elif mode == "values":
                    payload = chunk
                elif mode == "messages":
                    message_delta = "".join([b["text"] for b in chunk[0].content_blocks])
                    if message_delta:
                        await handle.queue.put({
                            "event": "token",
                            "data": {
                                "message": message_delta,
                                "metadata": chunk[1],
                            },
                        })

            await handle.queue.put({
                "event": "done",
                "data": {"run_id": run_id},
            })
        except asyncio.CancelledError:
            await handle.queue.put({
                "event": "cancelled",
                "data": {"run_id": run_id},
            })
        except Exception as e:
            await handle.queue.put({
                "event": "error",
                "data": {"message": repr(e)},
            })
        finally:
            if self._callback:
                await self._callback(payload)

            handle.done.set()

    def has_run(self, run_id: str) -> bool:
        if run_id in self._runs:
            return True

        return False

    async def start(self,
                    input_data: dict[str, Any],
                    run_name: str | None = None,
                    metadata: dict | None = None,
                    tags: list[str] | None = None,
                    ) -> str:
        run_id = str(uuid4())
        handle = WorkflowRunHandle()
        self._runs[run_id] = handle

        input_data["run_id"] = run_id

        handle.task = asyncio.create_task(
            self._run_graph(
                run_id=run_id,
                input_data=input_data,
                handle=handle,
                run_name=run_name,
                metadata=metadata,
                tags=tags,
            )
        )

        return run_id

    async def events(self, run_id: str) -> AsyncIterator[str]:
        handle = self._runs.get(run_id)
        if handle is None:
            yield self._format_sse(
                event="error",
                data={"message": f"Run {run_id} not found"},
            )
            return

        try:
            while True:
                # Exit once producer finished and all buffered events were consumed.
                if handle.done.is_set() and handle.queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(handle.queue.get(), timeout=55)
                except asyncio.TimeoutError:
                    yield self._format_sse(
                        event="ping",
                        data={"message": "ping"},
                    )
                    continue

                yield self._format_sse(
                    event=event["event"],
                    data=event["data"],
                )

                if event["event"] in {"done", "error", "cancelled"}:
                    break
        finally:
            if handle.done.is_set() and handle.queue.empty():
                self._runs.pop(run_id, None)
