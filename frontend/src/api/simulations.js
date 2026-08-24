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

    const turns = await apiRequest(`/turn-presentations?${params.toString()}`);
    return turns.map(normalizeTurn);
}

export async function fetchSimulationRecords(options) {
    return fetchSimulationTurns(options);
}

export async function fetchTurnPresentation(turnId) {
    const presentedTurn = await apiRequest(`/turns/${turnId}/presentation`);
    return normalizeTurn(presentedTurn);
}

function query(path, params) {
    const search = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== "") {
            search.set(key, String(value));
        }
    });

    return apiRequest(`${path}?${search.toString()}`);
}

export async function fetchSimulationCharacters(simulationId) {
    return query("/characters", { simulation_id: simulationId });
}

export async function fetchSimulationLocations(simulationId) {
    return query("/locations", { simulation_id: simulationId });
}

export async function fetchSimulationBackgroundCharacters(simulationId) {
    return query("/background-characters", { simulation_id: simulationId });
}

export async function fetchSimulationLandmarks(simulationId) {
    return query("/landmarks", { simulation_id: simulationId });
}

export async function fetchSimulationItems(simulationId) {
    return query("/items", { simulation_id: simulationId });
}

export async function fetchSimulationStacks(simulationId) {
    return query("/stacks", { simulation_id: simulationId });
}

export async function fetchSimulationEquipment(simulationId) {
    return query("/equipment", { simulation_id: simulationId });
}

export async function fetchSimulationContainers(simulationId) {
    return query("/containers", { simulation_id: simulationId });
}

export async function fetchSimulationEvents(simulationId) {
    return query("/events", { simulation_id: simulationId });
}

export async function fetchSimulationMemories(simulationId) {
    return query("/memories", { simulation_id: simulationId });
}

export async function fetchSimulationIntents(simulationId) {
    return query("/intents", { simulation_id: simulationId });
}

export async function fetchSimulationAuditEvents({
    simulationId,
    runId = null,
    turnId = null,
    category = null,
    actorId = null,
    limit = 200,
    offset = 0,
}) {
    return query(`/simulations/${simulationId}/audit-events`, {
        run_id: runId,
        turn_id: turnId,
        category,
        actor_id: actorId,
        limit,
        skip: offset,
    });
}

export async function fetchCharacterInventory(characterId) {
    return apiRequest(`/characters/${characterId}/inventory`);
}

export async function fetchCharacterLocation(characterId) {
    return apiRequest(`/characters/${characterId}/location`);
}

export async function fetchCharacterEmotion({ simulationId, characterId }) {
    return query(`/characters/${characterId}/emotion`, { simulation_id: simulationId });
}

export async function fetchCharacterTtsConfig(characterId) {
    return apiRequest(`/characters/${characterId}/tts-config`);
}

export async function setCharacterTtsConfig(characterId, config) {
    return apiRequest(`/characters/${characterId}/tts-config`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function fetchSimulationTtsBackendConfig(simulationId) {
    return query(`/simulations/${simulationId}/tts-connection`, { component: "narrator_tts" });
}

export async function generateBlockVoice(blockId) {
    return apiRequest(`/turn-presentations/blocks/${blockId}/voice`, {
        method: "POST",
    });
}

export async function generateCharacterCoverImage({ sourceId, characterId }) {
    return apiRequest(`/characters/${characterId}/generate-image/state`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ source_id: sourceId }),
    });
}

export async function generateLocationCoverImage({ sourceId, locationId }) {
    return apiRequest(`/locations/${locationId}/generate-image/state`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ source_id: sourceId }),
    });
}

export async function generateItemCoverImage({ sourceId, itemId }) {
    return apiRequest(`/items/${itemId}/generate-image/state`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ source_id: sourceId }),
    });
}

export async function generateCharacterPortraitImage({ simulationId, characterId, turnId = null, blockId = null }) {
    return apiRequest(`/simulations/${simulationId}/characters/${characterId}/generate-image/portrait`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ turn_id: turnId, block_id: blockId }),
    });
}

export async function generateSceneImage({ simulationId, locationId, turnId = null, blockId = null }) {
    return apiRequest(`/simulations/${simulationId}/locations/${locationId}/generate-image/scene`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ turn_id: turnId, block_id: blockId }),
    });
}

export async function fetchTurnGeneratedImages(turnId) {
    return apiRequest(`/turns/${turnId}/generated-images`);
}

export async function fetchBlockGeneratedImages(blockId) {
    return apiRequest(`/turn-presentations/blocks/${blockId}/generated-images`);
}

export async function fetchEventsByTurn(turnId) {
    return query("/events", { turn_id: turnId });
}

export async function fetchMemoriesByCharacter(characterId) {
    return query("/memories", { character_id: characterId });
}

export async function fetchIntentsByCharacter(characterId) {
    return query("/intents", { character_id: characterId });
}

export async function deleteSimulation(simulationId) {
    await apiRequest(`/simulations/${simulationId}`, {
        method: "DELETE",
    });
}

export async function sendSimulationInput({
    simulationId,
    userInput,
    regenerateTurnSequence = null,
    clientRequestId = crypto.randomUUID(),
}) {
    const hasUserInput = userInput !== null && userInput !== undefined && String(userInput).trim().length > 0;
    const requestType = regenerateTurnSequence !== null
        ? "regeneration"
        : (hasUserInput ? "user_input_generation" : "continue_generation");
    const run = await apiRequest(`/simulations/${simulationId}/input`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            request_type: requestType,
            user_input: requestType === "user_input_generation" ? userInput : null,
            regenerate_turn_sequence: regenerateTurnSequence,
            client_request_id: clientRequestId,
        }),
    });

    return {
        ...run,
        run_id: run.run_id ?? run.thread_id,
    };
}

export async function listTurnVersions({ simulationId, turnSequence }) {
    const params = new URLSearchParams();
    params.set("turn_sequence", String(turnSequence));

    return apiRequest(`/simulations/${simulationId}/turn-versions?${params.toString()}`);
}

export async function revertTurnVersion({ simulationId, versionId }) {
    return apiRequest(`/simulations/${simulationId}/turn-versions/${versionId}/revert`, {
        method: "POST",
    });
}

export function getSimulationRunUrl({ simulationId, threadId }) {
    return apiUrl(`/simulations/${simulationId}/runs/${threadId}`);
}

export function getSimulationCoverUrl(simulationId) {
    return apiUrl(`/simulations/${simulationId}/cover-image`);
}

export function getSimulationCharacterImageUrl({ characterId }) {
    return apiUrl(`/characters/${characterId}/cover-image`);
}

export function getSimulationLocationImageUrl({ locationId }) {
    return apiUrl(`/locations/${locationId}/cover-image`);
}

export function getSimulationBackgroundCharacterImageUrl(characterId) {
    return apiUrl(`/background-characters/${characterId}/cover-image`);
}

export function getSimulationLandmarkImageUrl(landmarkId) {
    return apiUrl(`/landmarks/${landmarkId}/cover-image`);
}

export function getSimulationItemImageUrl(itemId) {
    return apiUrl(`/items/${itemId}/cover-image`);
}

export function getSimulationStackImageUrl(stackId) {
    return apiUrl(`/stacks/${stackId}/cover-image`);
}

export function getSimulationEquipmentImageUrl(equipmentId) {
    return apiUrl(`/equipment/${equipmentId}/cover-image`);
}

export function getSimulationContainerImageUrl(containerId) {
    return apiUrl(`/containers/${containerId}/cover-image`);
}

function normalizeSimulation(simulation) {
    return {
        ...simulation,
        description: simulation.description ?? "",
        emotion_enabled: simulation.emotion_enabled ?? true,
        suggested_actions: simulation.suggested_actions ?? [],
    };
}

export function normalizeTurn(presentedTurn) {
    const turn = presentedTurn.turn;
    const presentationBlocks = presentedTurn.presentation_blocks ?? [];
    return {
        ...turn,
        turn_number: turn.sequence,
        narration: presentationBlocks.length > 0
            ? narrationTextFromBlocks(presentationBlocks)
            : turn.content,
        narration_blocks: presentationBlocks,
        rendering_id: presentedTurn.rendering_id ?? "default",
        locale: presentedTurn.locale ?? null,
    };
}

function narrationTextFromBlocks(blocks) {
    return blocks
        .map((block) => {
            if (block.type === "speech") {
                const speaker = block.speaker_name || block.speaker_id || "";
                return speaker ? `${speaker}: "${block.text}"` : block.text;
            }

            return block.text;
        })
        .filter(Boolean)
        .join("\n\n");
}
