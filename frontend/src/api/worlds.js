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

export function getWorldCoverUrl(worldId) {
    return `/api/worlds/${worldId}/images/cover`;
}
