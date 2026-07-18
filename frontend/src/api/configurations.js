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

export async function fetchLlmConfigs() {
    return apiRequest("/config/llm");
}

export async function createLlmConfig(provider, config) {
    return apiRequest(`/config/llm/${provider}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
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
