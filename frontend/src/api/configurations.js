import { apiRequest } from "@/api/client";

export const simulatorComponents = [
    "action_validator",
    "character_simulator",
    "input_interpreter",
    "memory_summarizer",
    "narrator",
    "perspective_resolver",
    "scene_coordinator",
    "state_committer",
];

export const imageComponents = [
    "character_image_generator",
    "character_portrait_image_generator",
    "location_image_generator",
    "item_image_generator",
    "scene_image_generator",
];

// Every image generator needs a chat model too (to build the image prompt), plus the trigger
// that decides whether a turn should be auto-illustrated - it only ever needs a chat model.
export const imageChatComponents = [...imageComponents, "turn_image_trigger"];

// The SillyTavern import pipeline's extraction stages - configured globally (not per-world/
// simulation), see GET /worlds/import/sillytavern/status.
export const stImportComponents = [
    "st_lorebook_classifier",
    "st_character_extractor",
    "st_location_extractor",
    "st_world_lore_extractor",
    "st_narrative_extractor",
    "st_intent_extractor",
    "st_variable_schema_extractor",
    "st_item_extractor",
    "st_equipment_extractor",
];

export async function fetchConnections() {
    return apiRequest("/config/connections");
}

export async function createConnection(connection) {
    return apiRequest("/config/connections", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(connection),
    });
}

export async function updateConnection(connectionId, connection) {
    return apiRequest(`/config/connections/${connectionId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(connection),
    });
}

export async function deleteConnection(connectionId) {
    await apiRequest(`/config/connections/${connectionId}`, {
        method: "DELETE",
    });
}

export async function fetchAllTalkStatus(connectionId) {
    return apiRequest(`/config/connections/${connectionId}/alltalk-status`);
}

export async function fetchLlmConfigs() {
    return apiRequest("/config/llm");
}

export async function createLlmConfig(provider, config) {
    return apiRequest("/config/llm", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            provider,
            ...config,
        }),
    });
}

export async function updateLlmConfig(configId, config) {
    return apiRequest(`/config/llm/${configId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function setLlmConfigConnection(configId, connectionId) {
    return apiRequest(`/config/llm/${configId}/connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            connection_id: connectionId,
        }),
    });
}

export async function deleteLlmConfigConnection(configId) {
    await apiRequest(`/config/llm/${configId}/connection`, {
        method: "DELETE",
    });
}

export async function deleteLlmConfig(configId) {
    await apiRequest(`/config/llm/${configId}`, {
        method: "DELETE",
    });
}

export async function fetchEmbeddingConfigs() {
    return apiRequest("/config/embeddings");
}

export async function createEmbeddingConfig(provider, config) {
    return apiRequest(`/config/embeddings/${provider}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function updateEmbeddingConfig(configId, config) {
    return apiRequest(`/config/embeddings/${configId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function setEmbeddingConfigConnection(configId, connectionId) {
    return apiRequest(`/config/embeddings/${configId}/connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            connection_id: connectionId,
        }),
    });
}

export async function deleteEmbeddingConfigConnection(configId) {
    await apiRequest(`/config/embeddings/${configId}/connection`, {
        method: "DELETE",
    });
}

export async function deleteEmbeddingConfig(configId) {
    await apiRequest(`/config/embeddings/${configId}`, {
        method: "DELETE",
    });
}

export async function fetchWorldLlmConfig(worldId, component = "narrator") {
    const params = new URLSearchParams({ component });
    return apiRequest(`/worlds/${worldId}/llm-connection?${params.toString()}`);
}

export async function setWorldLlmConfig(worldId, configId, component) {
    return apiRequest(`/worlds/${worldId}/llm-connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            component,
            config_id: configId,
        }),
    });
}

export async function deleteWorldLlmConfig(worldId, component) {
    const params = new URLSearchParams({ component });
    await apiRequest(`/worlds/${worldId}/llm-connection?${params.toString()}`, {
        method: "DELETE",
    });
}

export async function fetchGlobalLlmConfigs(components) {
    const params = new URLSearchParams();
    components.forEach((component) => params.append("components", component));
    return apiRequest(`/config/llm/global-connections?${params.toString()}`);
}

export async function setGlobalLlmConfigs(assignments) {
    return apiRequest("/config/llm/global-connections", {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchWorldLlmConfigs(worldId) {
    return apiRequest(`/worlds/${worldId}/llm-connections`);
}

export async function setWorldLlmConfigs(worldId, assignments) {
    return apiRequest(`/worlds/${worldId}/llm-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchWorldEmbeddingConfig(worldId, component = "character_simulator") {
    const params = new URLSearchParams({ component });
    return apiRequest(`/worlds/${worldId}/embedding-connection?${params.toString()}`);
}

export async function setWorldEmbeddingConfig(worldId, configId, component) {
    return apiRequest(`/worlds/${worldId}/embedding-connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            component,
            config_id: configId,
        }),
    });
}

export async function deleteWorldEmbeddingConfig(worldId, component) {
    const params = new URLSearchParams({ component });
    await apiRequest(`/worlds/${worldId}/embedding-connection?${params.toString()}`, {
        method: "DELETE",
    });
}

export async function fetchWorldEmbeddingConfigs(worldId) {
    return apiRequest(`/worlds/${worldId}/embedding-connections`);
}

export async function setWorldEmbeddingConfigs(worldId, assignments) {
    return apiRequest(`/worlds/${worldId}/embedding-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchSimulationLlmConfigs(simulationId) {
    return apiRequest(`/simulations/${simulationId}/llm-connections`);
}

export async function setSimulationLlmConfigs(simulationId, assignments) {
    return apiRequest(`/simulations/${simulationId}/llm-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchSimulationEmbeddingConfigs(simulationId) {
    return apiRequest(`/simulations/${simulationId}/embedding-connections`);
}

export async function setSimulationEmbeddingConfigs(simulationId, assignments) {
    return apiRequest(`/simulations/${simulationId}/embedding-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchSimulationImageGenerationConfig(simulationId) {
    return apiRequest(`/simulations/${simulationId}/image-generation-config`);
}

export async function setSimulationImageGenerationConfig(simulationId, config) {
    return apiRequest(`/simulations/${simulationId}/image-generation-config`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function fetchSimulationTtsGenerationConfig(simulationId) {
    return apiRequest(`/simulations/${simulationId}/tts-generation-config`);
}

export async function setSimulationTtsGenerationConfig(simulationId, config) {
    return apiRequest(`/simulations/${simulationId}/tts-generation-config`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function updateTtsConfig(configId, config) {
    return apiRequest(`/config/tts/${configId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function fetchTtsConfigs() {
    return apiRequest("/config/tts");
}

export async function createTtsConfig(engine, config) {
    return apiRequest(`/config/tts/alltalk/${engine}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function deleteTtsConfig(configId) {
    await apiRequest(`/config/tts/${configId}`, {
        method: "DELETE",
    });
}

export async function setTtsConfigConnection(configId, connectionId) {
    return apiRequest(`/config/tts/${configId}/connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            connection_id: connectionId,
        }),
    });
}

export async function deleteTtsConfigConnection(configId) {
    await apiRequest(`/config/tts/${configId}/connection`, {
        method: "DELETE",
    });
}

export async function setSimulationTtsConfig(simulationId, configId) {
    return apiRequest(`/simulations/${simulationId}/tts-connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            component: "narrator_tts",
            config_id: configId,
        }),
    });
}

export async function fetchWorldTtsConfig(worldId) {
    const params = new URLSearchParams({ component: "narrator_tts" });
    return apiRequest(`/worlds/${worldId}/tts-connection?${params.toString()}`);
}

export async function setWorldTtsConfig(worldId, configId) {
    return apiRequest(`/worlds/${worldId}/tts-connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            component: "narrator_tts",
            config_id: configId,
        }),
    });
}

export async function fetchImageConfigs() {
    return apiRequest("/config/images");
}

export async function createImageConfig(provider, config) {
    return apiRequest(`/config/images/${provider}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function updateImageConfig(configId, config) {
    return apiRequest(`/config/images/${configId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function deleteImageConfig(configId) {
    await apiRequest(`/config/images/${configId}`, {
        method: "DELETE",
    });
}

export async function setImageConfigConnection(configId, connectionId) {
    return apiRequest(`/config/images/${configId}/connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            connection_id: connectionId,
        }),
    });
}

export async function deleteImageConfigConnection(configId) {
    await apiRequest(`/config/images/${configId}/connection`, {
        method: "DELETE",
    });
}

export async function fetchSimulationImageConfigs(simulationId) {
    return apiRequest(`/simulations/${simulationId}/image-connections`);
}

export async function setSimulationImageConfigs(simulationId, assignments) {
    return apiRequest(`/simulations/${simulationId}/image-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchWorldImageConfigs(worldId) {
    return apiRequest(`/worlds/${worldId}/image-connections`);
}

export async function setWorldImageConfigs(worldId, assignments) {
    return apiRequest(`/worlds/${worldId}/image-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchSttConfigs() {
    return apiRequest("/config/stt");
}

export async function createSttConfig(provider, config) {
    return apiRequest(`/config/stt/${provider}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function updateSttConfig(configId, config) {
    return apiRequest(`/config/stt/${configId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
    });
}

export async function deleteSttConfig(configId) {
    await apiRequest(`/config/stt/${configId}`, {
        method: "DELETE",
    });
}

export async function setSttConfigConnection(configId, connectionId) {
    return apiRequest(`/config/stt/${configId}/connection`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            connection_id: connectionId,
        }),
    });
}

export async function deleteSttConfigConnection(configId) {
    await apiRequest(`/config/stt/${configId}/connection`, {
        method: "DELETE",
    });
}
