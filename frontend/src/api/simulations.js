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

export async function fetchSimulationTurns({ simulationId, limit = 50, offset = 0 }) {
    const params = new URLSearchParams();

    params.set("simulation_id", simulationId);
    params.set("limit", String(limit));
    params.set("skip", String(offset));

    const turns = await apiRequest(`/turns?${params.toString()}`);
    return turns.map(normalizeTurn);
}

export async function fetchSimulationRecords(options) {
    return fetchSimulationTurns(options);
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
    const hasUserInput = userInput !== null && userInput !== undefined && String(userInput).trim().length > 0;
    const run = await apiRequest(`/simulations/${simulationId}/input`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            request_type: hasUserInput ? "user_input_generation" : "continue_generation",
            user_input: hasUserInput ? userInput : null,
        }),
    });

    return {
        ...run,
        run_id: run.run_id ?? run.thread_id,
    };
}

export function getSimulationRunUrl({ simulationId, threadId }) {
    return apiUrl(`/simulations/${simulationId}/runs/${threadId}`);
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

function normalizeTurn(turn) {
    const narrationBlocks = parseNarrationBlocks(turn.content);
    return {
        ...turn,
        turn_number: turn.sequence,
        narration: narrationBlocks ? narrationTextFromBlocks(narrationBlocks) : turn.content,
        narration_blocks: narrationBlocks,
    };
}

function parseNarrationBlocks(content) {
    if (typeof content !== "string") {
        return null;
    }

    try {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed?.blocks)) {
            return parsed.blocks;
        }
    } catch {
        // Legacy turns store plain text.
    }

    return null;
}

function narrationTextFromBlocks(blocks) {
    return blocks
        .map((block) => {
            if (block.type === "speech") {
                const speaker = block.character_name || block.character_id || "";
                return speaker ? `${speaker}: "${block.text}"` : block.text;
            }

            return block.text;
        })
        .filter(Boolean)
        .join("\n\n");
}
