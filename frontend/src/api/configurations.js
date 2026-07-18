import { apiRequest } from "@/api/client";

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
