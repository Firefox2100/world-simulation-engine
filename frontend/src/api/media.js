import { apiRequest, apiUrl } from "@/api/client";

export const mediaTypes = ["image/png"];

const coverPaths = {
    world: (id) => `/worlds/${id}/cover-image`,
    simulations: (id) => `/simulations/${id}/cover-image`,
    locations: (id) => `/locations/${id}/cover-image`,
    characters: (id) => `/characters/${id}/cover-image`,
    background: (id) => `/background-characters/${id}/cover-image`,
    items: (id) => `/items/${id}/cover-image`,
    stacks: (id) => `/stacks/${id}/cover-image`,
    equipment: (id) => `/equipment/${id}/cover-image`,
    containers: (id) => `/containers/${id}/cover-image`,
};

export async function fetchMedia({ type = "image/png", worldId = null, simulationId = null, limit = null, offset = 0 } = {}) {
    const params = new URLSearchParams();

    if (type) {
        params.set("type", type);
    }

    if (worldId) {
        params.set("world_id", worldId);
    }

    if (simulationId) {
        params.set("simulation_id", simulationId);
    }

    if (limit !== null && limit !== undefined) {
        params.set("limit", String(limit));
    }

    params.set("skip", String(offset));

    return apiRequest(`/media?${params.toString()}`);
}

export async function uploadMedia(file, { type = "image/png", title = null, filename = null } = {}) {
    const formData = new FormData();
    formData.set("file", file);
    formData.set("type", type);

    if (title) {
        formData.set("title", title);
    }

    if (filename) {
        formData.set("filename", filename);
    }

    return apiRequest("/media", {
        method: "POST",
        body: formData,
    });
}

export async function deleteMedia(mediaId) {
    await apiRequest(`/media/${mediaId}`, {
        method: "DELETE",
    });
}

export async function setCoverImage(kind, sourceId, mediaId) {
    return apiRequest(coverPath(kind, sourceId), {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ media_id: mediaId }),
    });
}

export async function deleteCoverImage(kind, sourceId) {
    await apiRequest(coverPath(kind, sourceId), {
        method: "DELETE",
    });
}

export function getMediaUrl(mediaId) {
    return apiUrl(`/media/${mediaId}`);
}

export function getCoverImageUrl(kind, sourceId) {
    return apiUrl(coverPath(kind, sourceId));
}

function coverPath(kind, sourceId) {
    const buildPath = coverPaths[kind];
    if (!buildPath) {
        throw new Error(`Unsupported cover image source: ${kind}`);
    }

    return buildPath(sourceId);
}
