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

export async function fetchSimulationRecords({ simulationId, limit = 50, startFrom = null }) {
    const params = new URLSearchParams();

    params.set("limit", String(limit));

    if (startFrom !== null && startFrom !== undefined) {
        params.set("start_from", String(startFrom));
    }

    const response = await fetch(`/api/simulations/${simulationId}/records?${params.toString()}`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulation records: ${response.status}`);
    }

    return response.json();
}

export async function deleteSimulation(simulationId) {
    const response = await fetch(`/api/simulations/${simulationId}`, {
        method: "DELETE",
    });

    if (!response.ok) {
        throw new Error(`Failed to delete simulation: ${response.status}`);
    }
}

export async function sendSimulationInput({ simulationId, userInput }) {
    const response = await fetch(`/api/simulations/${simulationId}/input`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            user_input: userInput,
        }),
    });

    if (!response.ok) {
        throw new Error(`Failed to send simulation input: ${response.status}`);
    }

    return response.json();
}

export function getSimulationCoverUrl(simulationId) {
    return `/api/simulations/${simulationId}/images/cover`;
}
