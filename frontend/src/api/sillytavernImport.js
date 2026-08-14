import { apiRequest, apiUrl } from "@/api/client";

export async function parseSillyTavernCard(file) {
    const formData = new FormData();
    formData.set("file", file);

    return apiRequest("/worlds/import/sillytavern/parse", {
        method: "POST",
        body: formData,
    });
}

export async function parseSillyTavernCardUrl(url) {
    return apiRequest("/worlds/import/sillytavern/parse-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    });
}

export async function getSillyTavernImportStatus() {
    return apiRequest("/worlds/import/sillytavern/status");
}

export async function extractSillyTavernCard(card, language, selectedImageUrls = [], onProgress = null) {
    const response = await fetch(apiUrl("/worlds/import/sillytavern/extract"), {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
        },
        body: JSON.stringify({ card, language, selected_image_urls: selectedImageUrls }),
    });
    if (!response.ok) {
        throw new Error(`Extraction request failed: HTTP ${response.status}`);
    }
    if (!response.body) {
        throw new Error("Extraction stream returned no response body");
    }

    const result = {
        world: null,
        sections: {},
        report: null,
        image_candidates: [],
        image_scan: null,
    };
    const progress = { connected: false, keepalives: 0, sections: {} };
    let completed = false;

    await consumeSse(response.body, (event, data) => {
        if (event === "started") {
            progress.connected = true;
        } else if (event === "keepalive") {
            progress.keepalives += 1;
        } else if (event === "world") {
            result.world = data;
        } else if (event === "section_start") {
            result.sections[data.name] = [];
            progress.sections[data.name] = { received: 0, total: data.total };
        } else if (event === "section_item") {
            (result.sections[data.name] ??= []).push(data.row);
            const section = progress.sections[data.name] ?? { received: 0, total: null };
            progress.sections[data.name] = { ...section, received: section.received + 1 };
        } else if (event === "report") {
            result.report = data;
        } else if (event === "image_candidate") {
            result.image_candidates.push(data);
        } else if (event === "image_scan") {
            result.image_scan = data;
        } else if (event === "error") {
            throw new Error(data.detail ?? `Extraction failed (reference ${data.request_id})`);
        } else if (event === "complete") {
            completed = true;
        }
        onProgress?.({
            connected: progress.connected,
            keepalives: progress.keepalives,
            sections: { ...progress.sections },
        });
    });

    if (!completed || !result.world || !result.report) {
        throw new Error("Extraction stream ended before the complete result was received");
    }
    return result;
}

async function consumeSse(stream, onEvent) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
            let boundary;
            while ((boundary = buffer.indexOf("\n\n")) !== -1) {
                const block = buffer.slice(0, boundary);
                buffer = buffer.slice(boundary + 2);
                const parsed = parseSseBlock(block);
                if (parsed) {
                    onEvent(parsed.event, parsed.data);
                }
            }
            if (done) {
                break;
            }
        }
    } catch (error) {
        await reader.cancel(error);
        throw error;
    } finally {
        reader.releaseLock();
    }
}

function parseSseBlock(block) {
    if (!block) {
        return null;
    }
    if (block.startsWith(":")) {
        return { event: "keepalive", data: null };
    }
    let event = "message";
    const dataLines = [];
    for (const line of block.split("\n")) {
        if (line.startsWith("event:")) {
            event = line.slice(6).trimStart();
        } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
        }
    }
    if (dataLines.length === 0) {
        return null;
    }
    try {
        return { event, data: JSON.parse(dataLines.join("\n")) };
    } catch (error) {
        throw new Error(`Invalid JSON in extraction SSE event ${event}`, { cause: error });
    }
}

export async function fetchSillyTavernImages(urls) {
    return apiRequest("/worlds/import/sillytavern/images/fetch", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ urls }),
    });
}

export async function commitSillyTavernWorld(world, sections, authorId) {
    return apiRequest("/worlds/import/sillytavern/commit", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ world, sections, author_id: authorId }),
    });
}
