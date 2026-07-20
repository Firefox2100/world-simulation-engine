import { apiRequest } from "@/api/client";

export const promptLanguages = ["en", "zh"];

export const promptUsages = [
    { prompt_name: "action_proposal", component: "character_simulator" },
    { prompt_name: "action_reaction", component: "character_simulator" },
    { prompt_name: "speech_repair", component: "character_simulator" },
    { prompt_name: "action_validator", component: "action_validator" },
    { prompt_name: "input_interpreter", component: "input_interpreter" },
    { prompt_name: "memory_summarizer", component: "memory_summarizer" },
    { prompt_name: "narrator", component: "narrator" },
    { prompt_name: "scene_coordinator", component: "scene_coordinator" },
    { prompt_name: "state_committer", component: "state_committer" },
    { prompt_name: "resolve_perceived_character", component: "perspective_resolver" },
    { prompt_name: "resolve_perceived_background_characters", component: "perspective_resolver" },
    { prompt_name: "resolve_perceived_items", component: "perspective_resolver" },
    { prompt_name: "resolve_perceived_equipment", component: "perspective_resolver" },
    { prompt_name: "resolve_perceived_containers", component: "perspective_resolver" },
    { prompt_name: "resolve_perceived_landmarks", component: "perspective_resolver" },
];

export function promptAssignmentKey({ language, prompt_name, component }) {
    return `${language}:${prompt_name}:${component ?? ""}`;
}

export function promptLabel(prompt) {
    return prompt?.title || prompt?.filename || prompt?.prompt_name || prompt?.id;
}

export async function fetchPrompts(filters = {}) {
    const params = new URLSearchParams();
    if (filters.language) {
        params.set("language", filters.language);
    }
    if (filters.component) {
        params.set("component", filters.component);
    }
    if (filters.prompt_name) {
        params.set("prompt_name", filters.prompt_name);
    }

    const query = params.toString();
    return apiRequest(`/prompts${query ? `?${query}` : ""}`);
}

export async function fetchPromptMessages(promptId) {
    return apiRequest(`/prompts/${promptId}/messages`);
}

export async function fetchBuiltinPromptMessages(language, promptName) {
    return apiRequest(`/prompts/builtin/${language}/${promptName}`);
}

export async function createPrompt(prompt) {
    return apiRequest("/prompts", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(prompt),
    });
}

export async function updatePrompt(promptId, prompt) {
    return apiRequest(`/prompts/${promptId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(prompt),
    });
}

export async function deletePrompt(promptId) {
    await apiRequest(`/prompts/${promptId}`, {
        method: "DELETE",
    });
}

export async function fetchWorldPromptAssignments(worldId) {
    return apiRequest(`/worlds/${worldId}/prompt-connections`);
}

export async function setWorldPromptAssignments(worldId, assignments) {
    return apiRequest(`/worlds/${worldId}/prompt-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}

export async function fetchSimulationPromptAssignments(simulationId) {
    return apiRequest(`/simulations/${simulationId}/prompt-connections`);
}

export async function setSimulationPromptAssignments(simulationId, assignments) {
    return apiRequest(`/simulations/${simulationId}/prompt-connections`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ assignments }),
    });
}
