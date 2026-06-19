export async function fetchLlmConnectionProfiles() {
    const response = await fetch("/api/connections/llm");

    if (!response.ok) {
        throw new Error(`Failed to fetch LLM connections: ${response.status}`);
    }

    return response.json();
}

export async function fetchImageConnectionProfiles() {
    const response = await fetch("/api/connections/image");

    if (!response.ok) {
        throw new Error(`Failed to fetch image connections: ${response.status}`);
    }

    return response.json();
}

export async function createLlmConnectionProfile(profile) {
    const response = await fetch("/api/connections/llm", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(profile),
    });

    if (!response.ok) {
        throw new Error(`Failed to create LLM connection: ${response.status}`);
    }

    return response.json();
}

export async function createImageConnectionProfile(profile) {
    const response = await fetch("/api/connections/image", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(profile),
    });

    if (!response.ok) {
        throw new Error(`Failed to create image connection: ${response.status}`);
    }

    return response.json();
}
