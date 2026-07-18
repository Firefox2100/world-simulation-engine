export const dataPresetListFields = [
    { key: "character_attributes", type: "attribute" },
    { key: "character_stats", type: "stat" },
    { key: "faction_attributes", type: "attribute" },
    { key: "faction_stats", type: "stat" },
];

export function makeModelAttribute() {
    return {
        name: "",
        values: [],
        creation_instruction: "",
        update_instruction: "",
        universal: false,
    };
}

export function makeModelStat() {
    return {
        name: "",
        creation_instruction: "",
        update_instruction: "",
        universal: false,
    };
}

export function makeDataPresetState() {
    return {
        character_attributes: [],
        character_stats: [],
        faction_attributes: [],
        faction_stats: [],
        entity_types: [],
    };
}

export function dataPresetFormFromWorld(dataPreset = null) {
    if (!dataPreset) {
        return makeDataPresetState();
    }

    return {
        character_attributes: (dataPreset.character_attributes ?? []).map((attribute) => ({
            name: attribute.name ?? "",
            values: attribute.values ?? [],
            creation_instruction: attribute.creation_instruction ?? "",
            update_instruction: attribute.update_instruction ?? "",
            universal: attribute.universal ?? false,
        })),
        character_stats: (dataPreset.character_stats ?? []).map((stat) => ({
            name: stat.name ?? "",
            creation_instruction: stat.creation_instruction ?? "",
            update_instruction: stat.update_instruction ?? "",
            universal: stat.universal ?? false,
        })),
        faction_attributes: (dataPreset.faction_attributes ?? []).map((attribute) => ({
            name: attribute.name ?? "",
            values: attribute.values ?? [],
            creation_instruction: attribute.creation_instruction ?? "",
            update_instruction: attribute.update_instruction ?? "",
            universal: attribute.universal ?? false,
        })),
        faction_stats: (dataPreset.faction_stats ?? []).map((stat) => ({
            name: stat.name ?? "",
            creation_instruction: stat.creation_instruction ?? "",
            update_instruction: stat.update_instruction ?? "",
            universal: stat.universal ?? false,
        })),
        entity_types: Object.entries(dataPreset.entity_types ?? {}).map(([name, description]) => ({
            name,
            description,
        })),
    };
}

function cleanText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function buildAttributePayload(attribute) {
    const name = cleanText(attribute.name);

    if (!name) {
        return null;
    }

    const values = attribute.values.map(cleanText).filter(Boolean);

    return {
        name,
        values: values.length > 0 ? values : undefined,
        creation_instruction: attribute.creation_instruction.trim(),
        update_instruction: attribute.update_instruction.trim(),
        universal: attribute.universal,
    };
}

function buildStatPayload(stat) {
    const name = cleanText(stat.name);

    if (!name) {
        return null;
    }

    return {
        name,
        creation_instruction: stat.creation_instruction.trim(),
        update_instruction: stat.update_instruction.trim(),
        universal: stat.universal,
    };
}

export function buildDataPresetPayload(dataPreset) {
    return {
        character_attributes: dataPreset.character_attributes
            .map(buildAttributePayload)
            .filter(Boolean),
        character_stats: dataPreset.character_stats.map(buildStatPayload).filter(Boolean),
        faction_attributes: dataPreset.faction_attributes.map(buildAttributePayload).filter(Boolean),
        faction_stats: dataPreset.faction_stats.map(buildStatPayload).filter(Boolean),
        entity_types: Object.fromEntries(
            dataPreset.entity_types
                .map((entityType) => [cleanText(entityType.name), cleanText(entityType.description)])
                .filter(([name, description]) => name && description),
        ),
    };
}
