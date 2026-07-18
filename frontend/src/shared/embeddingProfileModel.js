export function makeEmbeddingProfileState() {
    return {
        connection: "",
        model: "",
        dimensions: "",
        context_window: "",
    };
}

export function embeddingProfileFormFromWorld(profile = null) {
    if (!profile) {
        return makeEmbeddingProfileState();
    }

    return {
        connection: profile.connection == null ? "" : String(profile.connection),
        model: profile.model ?? "",
        dimensions: profile.dimensions == null ? "" : String(profile.dimensions),
        context_window: profile.context_window == null ? "" : String(profile.context_window),
    };
}

function optionalInt(value) {
    const trimmed = String(value).trim();
    return trimmed.length > 0 ? Number.parseInt(trimmed, 10) : undefined;
}

export function buildEmbeddingProfilePayload(profile) {
    const payload = {
        model: profile.model.trim(),
    };

    if (profile.connection !== "") {
        payload.connection = Number.parseInt(profile.connection, 10);
    }

    const dimensions = optionalInt(profile.dimensions);
    const contextWindow = optionalInt(profile.context_window);

    if (dimensions !== undefined) {
        payload.dimensions = dimensions;
    }

    if (contextWindow !== undefined) {
        payload.context_window = contextWindow;
    }

    return payload;
}
