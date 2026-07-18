const API_PREFIX = "/api";

export function apiUrl(path) {
    return `${API_PREFIX}${path}`;
}

export async function apiRequest(path, options = {}) {
    const response = await fetch(apiUrl(path), options);

    if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail ?? `Request failed: ${response.status}`);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

async function readErrorDetail(response) {
    try {
        const data = await response.json();
        if (typeof data?.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data?.detail)) {
            return data.detail
                .map((item) => item?.msg ?? item?.message)
                .filter(Boolean)
                .join("; ");
        }
    } catch {
        return null;
    }

    return null;
}
