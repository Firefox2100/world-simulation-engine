import {
    createConnection,
    fetchConnections,
    updateConnection,
} from "@/api/configurations";

export async function fetchLlmConnectionProfiles() {
    const connections = await fetchConnections();
    return connections.map(normalizeLegacyConnectionProfile);
}

export async function fetchImageConnectionProfiles() {
    return [];
}

export async function createLlmConnectionProfile(profile) {
    return normalizeLegacyConnectionProfile(await createConnection(toConnectionConfig(profile)));
}

export async function createImageConnectionProfile(profile) {
    return normalizeLegacyConnectionProfile(await createConnection(toConnectionConfig(profile)));
}

export async function updateLlmConnectionProfile(profileId, profile) {
    return normalizeLegacyConnectionProfile(await updateConnection(profileId, toConnectionConfig(profile)));
}

export async function updateImageConnectionProfile(profileId, profile) {
    return normalizeLegacyConnectionProfile(await updateConnection(profileId, toConnectionConfig(profile)));
}

function normalizeLegacyConnectionProfile(connection) {
    return {
        ...connection,
        provider: connection.provider ?? connection.type,
    };
}

function toConnectionConfig(profile) {
    const type = profile.type ?? profile.provider;
    return {
        ...profile,
        type: type === "comfy_ui" ? "openai" : type,
    };
}
