import { apiRequest } from "@/api/client";

export async function parseSillyTavernCard(file) {
    const formData = new FormData();
    formData.set("file", file);

    return apiRequest("/worlds/import/sillytavern/parse", {
        method: "POST",
        body: formData,
    });
}

export async function getSillyTavernImportStatus() {
    return apiRequest("/worlds/import/sillytavern/status");
}

export async function extractSillyTavernCard(card, language) {
    return apiRequest("/worlds/import/sillytavern/extract", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ card, language }),
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
