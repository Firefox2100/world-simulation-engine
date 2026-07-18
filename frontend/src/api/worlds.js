import { apiRequest, apiUrl } from "@/api/client";

const DEFAULT_AUTHOR_NAME = "Codex Local Author";
const DEFAULT_LANGUAGE = "en";
const DEFAULT_STARTING_TIME = "2000-01-01T00:00:00.000Z";

let defaultAuthorPromise = null;

export async function fetchWorlds({ limit = null, offset = 0 } = {}) {
    const params = new URLSearchParams();

    if (limit !== null && limit !== undefined) {
        params.set("limit", String(limit));
    }

    params.set("skip", String(offset));

    const worlds = await apiRequest(`/worlds?${params.toString()}`);
    return worlds.map(normalizeWorld);
}

export async function createWorld(world) {
    const response = await apiRequest("/worlds", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(await buildWorldCreatePayload(world)),
    });

    return normalizeWorld(response);
}

export async function fetchWorld(worldId) {
    return normalizeWorld(await apiRequest(`/worlds/${worldId}`));
}

export async function updateWorld(worldId, world) {
    const response = await apiRequest(`/worlds/${worldId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(buildWorldUpdatePayload(world)),
    });

    return normalizeWorld(response);
}

export async function deleteWorld(worldId) {
    await apiRequest(`/worlds/${worldId}`, {
        method: "DELETE",
    });
}

export async function createSimulationFromWorld(worldId) {
    return apiRequest(`/worlds/${worldId}/simulations`, {
        method: "POST",
    });
}

export async function uploadWorldCoverImage(worldId, file) {
    const formData = new FormData();
    formData.set("file", file);
    formData.set("type", "image/png");
    formData.set("title", file.name);
    formData.set("filename", file.name.replace(/\.[^.]+$/, ""));

    const media = await apiRequest("/media", {
        method: "POST",
        body: formData,
    });

    return apiRequest(`/worlds/${worldId}/cover-image`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ media_id: media.id }),
    });
}

export function getWorldCoverUrl(worldId) {
    return apiUrl(`/worlds/${worldId}/cover-image`);
}

function normalizeWorld(world) {
    return {
        ...world,
        description: world.description ?? "",
        language: world.language ?? DEFAULT_LANGUAGE,
        starting_time: world.starting_time ?? DEFAULT_STARTING_TIME,
    };
}

async function buildWorldCreatePayload(world) {
    return {
        ...buildWorldUpdatePayload(world),
        author_id: world.author_id ?? (await getDefaultAuthorId()),
        starting_time: normalizeDateTime(world.starting_time),
        language: normalizeLanguage(world.language),
    };
}

function buildWorldUpdatePayload(world) {
    return {
        name: world.name,
        description: world.description ?? null,
        starting_time: normalizeDateTime(world.starting_time),
        version: world.version ?? 1,
        url: world.url ?? null,
        language: normalizeLanguage(world.language),
    };
}

function normalizeLanguage(language) {
    if (typeof language !== "string") {
        return DEFAULT_LANGUAGE;
    }

    return language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function normalizeDateTime(value) {
    if (typeof value === "string" && value.trim().length > 0) {
        const parsed = new Date(value);
        if (!Number.isNaN(parsed.getTime())) {
            return parsed.toISOString();
        }
    }

    return DEFAULT_STARTING_TIME;
}

async function getDefaultAuthorId() {
    if (!defaultAuthorPromise) {
        defaultAuthorPromise = findOrCreateDefaultAuthor();
    }

    return defaultAuthorPromise;
}

async function findOrCreateDefaultAuthor() {
    const authors = await apiRequest("/authors");
    const existing = authors.find((author) => author.name === DEFAULT_AUTHOR_NAME) ?? authors[0];

    if (existing?.id) {
        return existing.id;
    }

    const created = await apiRequest("/authors", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: DEFAULT_AUTHOR_NAME }),
    });

    return created.id;
}
