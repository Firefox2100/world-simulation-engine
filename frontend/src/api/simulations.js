export async function fetchSimulations({ limit = null, offset = 0 } = {}) {
    const params = new URLSearchParams();

    if (limit !== null && limit !== undefined) {
        params.set("limit", String(limit));
    }

    params.set("offset", String(offset));

    const response = await fetch(`/api/simulations?${params.toString()}`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulations: ${response.status}`);
    }

    return response.json();
}

export function getSimulationCoverUrl(simulationId) {
    return `/api/simulations/${simulationId}/images/cover`;
}
