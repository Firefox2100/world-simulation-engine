import { afterEach, describe, expect, it, vi } from "vitest";

import { extractSillyTavernCard } from "@/api/sillytavernImport";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("SillyTavern extraction SSE", () => {
    it("reassembles events split across network chunks and ignores keep-alives", async () => {
        const payload = [
            'event: started\ndata: {"request_id":"r1"}\n\n: keep-alive\n\n',
            'event: section_start\ndata: {"name":"characters","total":1}\n\nevent: section_item\ndata:',
            ' {"name":"characters","row":{"id":"c1"}}\n\nevent: world\ndata: {"name":"Test"}\n\n',
            'event: report\ndata: {"notes":[]}\n\nevent: image_scan\ndata: {"found":0}\n\n',
            'event: complete\ndata: {"request_id":"r1"}\n\n',
        ];
        const encoder = new TextEncoder();
        const body = new ReadableStream({
            start(controller) {
                payload.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
                controller.close();
            },
        });
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, {
            status: 200,
            headers: { "content-type": "text/event-stream" },
        })));

        const onProgress = vi.fn();
        const result = await extractSillyTavernCard({ name: "Test" }, "en", [], onProgress);

        expect(result.world).toEqual({ name: "Test" });
        expect(result.sections.characters).toEqual([{ id: "c1" }]);
        expect(result.image_scan).toEqual({ found: 0 });
        expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({
            connected: true,
            keepalives: 1,
            sections: { characters: { received: 1, total: 1 } },
        }));
    });

    it("turns an SSE error event into a rejected extraction", async () => {
        const body = 'event: started\ndata: {}\n\nevent: error\ndata: {"detail":"model failed"}\n\n';
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, {
            status: 200,
            headers: { "content-type": "text/event-stream" },
        })));

        await expect(extractSillyTavernCard({ name: "Test" }, "en")).rejects.toThrow("model failed");
    });
});
