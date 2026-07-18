import { apiRequest, apiUrl } from "@/api/client";

export async function fetchSimulations({ limit = null, offset = 0 } = {}) {
    const params = new URLSearchParams();

    if (limit !== null && limit !== undefined) {
        params.set("limit", String(limit));
    }

    params.set("skip", String(offset));

    const simulations = await apiRequest(`/simulations?${params.toString()}`);
    return simulations.map(normalizeSimulation);
}

export async function fetchSimulation(simulationId) {
    return normalizeSimulation(await apiRequest(`/simulations/${simulationId}`));
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

export async function fetchSimulationCharacters(simulationId) {
    const response = await fetch(`/api/simulations/${simulationId}/characters`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulation characters: ${response.status}`);
    }

    return response.json();
}

export async function fetchSimulationLocations(simulationId) {
    const response = await fetch(`/api/simulations/${simulationId}/locations`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulation locations: ${response.status}`);
    }

    return response.json();
}

export async function fetchSimulationFactions(simulationId) {
    const response = await fetch(`/api/simulations/${simulationId}/factions`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulation factions: ${response.status}`);
    }

    return response.json();
}

export async function fetchSimulationWorldEntries(simulationId) {
    const response = await fetch(`/api/simulations/${simulationId}/world-entries`);

    if (!response.ok) {
        throw new Error(`Failed to fetch simulation world entries: ${response.status}`);
    }

    return response.json();
}

export async function fetchSimulationCharacterInventory({ simulationId, characterId }) {
    const response = await fetch(`/api/simulations/${simulationId}/characters/${characterId}/inventory`);

    if (!response.ok) {
        throw new Error(`Failed to fetch character inventory: ${response.status}`);
    }

    return response.json();
}

export async function deleteSimulation(simulationId) {
    await apiRequest(`/simulations/${simulationId}`, {
        method: "DELETE",
    });
}

export async function sendSimulationInput({ simulationId, userInput }) {
    const run = await apiRequest(`/simulations/${simulationId}/input`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            request_type: "user_input_generation",
            user_input: userInput,
        }),
    });

    return {
        ...run,
        run_id: run.run_id ?? run.thread_id,
    };
}

export function getSimulationCoverUrl(simulationId) {
    return apiUrl(`/simulations/${simulationId}/cover-image`);
}

export function getSimulationCharacterImageUrl({ simulationId, characterId }) {
    return `/api/simulations/${simulationId}/characters/${characterId}/image`;
}

export function getSimulationLocationImageUrl({ simulationId, locationId }) {
    return `/api/simulations/${simulationId}/locations/${locationId}/image`;
}

export function getSimulationFactionImageUrl({ simulationId, factionId }) {
    return `/api/simulations/${simulationId}/factions/${factionId}/image`;
}

function normalizeSimulation(simulation) {
    return {
        ...simulation,
        description: simulation.description ?? "",
    };
}
