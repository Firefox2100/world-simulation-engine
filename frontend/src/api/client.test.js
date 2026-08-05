import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api/client";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("apiRequest response diagnostics", () => {
    it("reports an empty successful response with route and status", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 200 })));

        await expect(apiRequest("/large-result")).rejects.toThrow(
            "Server returned an empty response (HTTP 200) for /large-result",
        );
    });

    it("reports received and declared sizes for truncated JSON", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"world":', {
            status: 200,
            headers: { "content-type": "application/json", "content-length": "1000" },
        })));

        await expect(apiRequest("/large-result")).rejects.toThrow(
            /incomplete or invalid JSON.*received 9 bytes; expected 1000 bytes/,
        );
    });
});
