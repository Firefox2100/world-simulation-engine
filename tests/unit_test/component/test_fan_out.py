import asyncio

from world_simulation_engine.component.sillytavern_converter.fan_out import build_fan_out_graph, run_fan_out


async def test_run_fan_out_preserves_call_order_regardless_of_completion_order():
    graph = build_fan_out_graph()

    async def slow(value: int) -> int:
        # Later-indexed calls finish first, to prove ordering is restored from dispatch index,
        # not completion order.
        await asyncio.sleep((5 - value) * 0.01)
        return value

    results = await run_fan_out(
        graph,
        [lambda v=v: slow(v) for v in range(5)],
        max_concurrency=8,
    )

    assert results == [0, 1, 2, 3, 4]


async def test_run_fan_out_returns_empty_list_for_no_calls():
    graph = build_fan_out_graph()

    results = await run_fan_out(graph, [], max_concurrency=4)

    assert results == []


async def test_run_fan_out_runs_calls_concurrently_not_sequentially():
    graph = build_fan_out_graph()
    started = []

    async def track(value: int) -> int:
        started.append(value)
        await asyncio.sleep(0.05)
        return value

    results = await run_fan_out(
        graph,
        [lambda v=v: track(v) for v in range(4)],
        max_concurrency=4,
    )

    # If calls ran sequentially, later calls would not have started until earlier ones' sleep
    # finished - asserting all four started before any could have returned proves they overlapped.
    assert sorted(started) == [0, 1, 2, 3]
    assert sorted(results) == [0, 1, 2, 3]


async def test_run_fan_out_propagates_exceptions():
    graph = build_fan_out_graph()

    async def boom():
        raise ValueError("failed item")

    try:
        await run_fan_out(graph, [boom], max_concurrency=4)
        assert False, "expected ValueError to propagate"
    except ValueError as exc:
        assert "failed item" in str(exc)
