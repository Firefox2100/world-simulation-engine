import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { waitForBlocksVoiced } from "./turnVoicePolling.js";

describe("waitForBlocksVoiced", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("resolves once every requested block has a voice_media_id", async () => {
        const responses = [
            { narration_blocks: [{ id: "b1" }, { id: "b2" }] },
            { narration_blocks: [{ id: "b1", voice_media_id: "m1" }, { id: "b2" }] },
            {
                narration_blocks: [
                    { id: "b1", voice_media_id: "m1" },
                    { id: "b2", voice_media_id: "m2" },
                ],
            },
        ];
        let call = 0;
        const fetchTurnPresentation = vi.fn(() =>
            Promise.resolve(responses[Math.min(call++, responses.length - 1)]),
        );

        const { done } = waitForBlocksVoiced({
            turnId: "t1",
            blockIds: ["b1", "b2"],
            fetchTurnPresentation,
            intervalMs: 1000,
            timeoutMs: 10000,
        });

        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(1000);
        await vi.advanceTimersByTimeAsync(1000);

        const result = await done;
        expect(result.map((block) => block.id)).toEqual(["b1", "b2"]);
        expect(fetchTurnPresentation).toHaveBeenCalledTimes(3);
    });

    it("resolves with a partial set once the timeout elapses rather than hanging forever", async () => {
        const fetchTurnPresentation = vi.fn(() =>
            Promise.resolve({
                narration_blocks: [{ id: "b1", voice_media_id: "m1" }, { id: "b2" }],
            }),
        );

        const { done } = waitForBlocksVoiced({
            turnId: "t1",
            blockIds: ["b1", "b2"],
            fetchTurnPresentation,
            intervalMs: 1000,
            timeoutMs: 2500,
        });

        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(1000);
        await vi.advanceTimersByTimeAsync(1000);
        await vi.advanceTimersByTimeAsync(1000);

        const result = await done;
        expect(result.map((block) => block.id)).toEqual(["b1"]);
    });

    it("treats a fetch failure as not-ready-yet and keeps retrying instead of rejecting", async () => {
        const fetchTurnPresentation = vi
            .fn()
            .mockRejectedValueOnce(new Error("network error"))
            .mockResolvedValue({ narration_blocks: [{ id: "b1", voice_media_id: "m1" }] });

        const { done } = waitForBlocksVoiced({
            turnId: "t1",
            blockIds: ["b1"],
            fetchTurnPresentation,
            intervalMs: 1000,
            timeoutMs: 10000,
        });

        await vi.advanceTimersByTimeAsync(0);
        await vi.advanceTimersByTimeAsync(1000);

        const result = await done;
        expect(result.map((block) => block.id)).toEqual(["b1"]);
        expect(fetchTurnPresentation).toHaveBeenCalledTimes(2);
    });

    it("cancel() stops further polling and resolves done immediately", async () => {
        const fetchTurnPresentation = vi.fn(() =>
            Promise.resolve({ narration_blocks: [{ id: "b1" }] }),
        );

        const { cancel, done } = waitForBlocksVoiced({
            turnId: "t1",
            blockIds: ["b1"],
            fetchTurnPresentation,
            intervalMs: 1000,
            timeoutMs: 60000,
        });

        await vi.advanceTimersByTimeAsync(0);
        expect(fetchTurnPresentation).toHaveBeenCalledTimes(1);

        cancel();
        await expect(done).resolves.toEqual([]);

        await vi.advanceTimersByTimeAsync(5000);
        expect(fetchTurnPresentation).toHaveBeenCalledTimes(1);
    });
});
