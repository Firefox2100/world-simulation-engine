export async function fetchWorlds({ limit = null, offset = 0 } = {}) {
    const params = new URLSearchParams();

    if (limit !== null && limit !== undefined) {
        params.set("limit", String(limit));
    }

    params.set("offset", String(offset));

    const response = await fetch(`/api/worlds?${params.toString()}`);

    if (!response.ok) {
        throw new Error(`Failed to fetch worlds: ${response.status}`);
    }

    return response.json();
}

export async function createWorld(world) {
    const response = await fetch("/api/worlds", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(world),
    });

    if (!response.ok) {
        throw new Error(`Failed to create world: ${response.status}`);
    }

    return response.json();
}

export async function uploadWorldCoverImage(worldId, file) {
    const formData = new FormData();
    formData.set("file", file);

    const response = await fetch(`/api/worlds/${worldId}/images/cover`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Failed to upload world cover image: ${response.status}`);
    }

    return response.json();
}

export function getWorldCoverUrl(worldId) {
    return `/api/worlds/${worldId}/images/cover`;
}
