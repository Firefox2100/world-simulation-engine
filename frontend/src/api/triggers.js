import { apiRequest } from "@/api/client";

function query(path, params) {
    const search = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, value]) => value !== null && value !== undefined)),
    );
    const suffix = search.toString();
    return apiRequest(suffix ? `${path}?${suffix}` : path);
}

function jsonRequest(path, method, body) {
    return apiRequest(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
}

export async function fetchTriggers(sourceId) {
    return query("/triggers", { source_id: sourceId });
}

export async function fetchTrigger(triggerId) {
    return apiRequest(`/triggers/${triggerId}`);
}

export async function createTrigger(trigger) {
    return jsonRequest("/triggers", "POST", trigger);
}

export async function updateTrigger(triggerId, trigger) {
    return jsonRequest(`/triggers/${triggerId}`, "PUT", trigger);
}

export async function setTriggerStatus(triggerId, triggerStatus) {
    const search = new URLSearchParams({ trigger_status: triggerStatus });
    return apiRequest(`/triggers/${triggerId}/status?${search.toString()}`, { method: "PATCH" });
}

export async function deleteTrigger(triggerId) {
    await apiRequest(`/triggers/${triggerId}`, { method: "DELETE" });
}
