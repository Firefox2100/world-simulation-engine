const API_PREFIX = "/api";

export function apiUrl(path) {
    return `${API_PREFIX}${path}`;
}

export async function apiRequest(path, options = {}) {
    const response = await fetch(apiUrl(path), options);
    let body = "";
    if (response.status !== 204) {
        try {
            body = await response.text();
        } catch (error) {
            throw new Error(
                `Connection ended while reading the server response (HTTP ${response.status}) for ${path}`,
                { cause: error },
            );
        }
    }

    if (!response.ok) {
        const detail = readErrorDetail(body);
        throw new Error(detail ?? `Request failed: ${response.status}`);
    }

    if (response.status === 204) {
        return null;
    }

    if (!body.trim()) {
        throw new Error(`Server returned an empty response (HTTP ${response.status}) for ${path}`);
    }

    try {
        return JSON.parse(body);
    } catch (error) {
        const declaredLength = response.headers.get("content-length");
        const contentType = response.headers.get("content-type") ?? "unknown content type";
        const receivedBytes = new TextEncoder().encode(body).length;
        const lengthDetail = declaredLength ? `; expected ${declaredLength} bytes` : "";
        throw new Error(
            `Server response was incomplete or invalid JSON (HTTP ${response.status}, ${contentType}; `
            + `received ${receivedBytes} bytes${lengthDetail}): ${error.message}`,
            { cause: error },
        );
    }
}

function readErrorDetail(body) {
    try {
        const data = JSON.parse(body);
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
