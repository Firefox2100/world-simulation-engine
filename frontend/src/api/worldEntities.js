import { apiRequest } from "@/api/client";

function query(path, params) {
    const search = new URLSearchParams(params);
    return apiRequest(`${path}?${search.toString()}`);
}

function jsonRequest(path, method, body) {
    return apiRequest(path, {
        method,
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });
}

export async function fetchWorldAuthor(worldId) {
    return apiRequest(`/worlds/${worldId}/author`);
}

export async function updateWorldAuthor(worldId, authorId) {
    return jsonRequest(`/worlds/${worldId}/author`, "PATCH", { id: authorId });
}

export async function fetchWorldLocations(worldId) {
    return query("/locations", { world_id: worldId });
}

export async function createWorldLocation(worldId, location) {
    const parentId = location.parent_location_id;
    const payload = {
        name: location.name,
        description: location.description,
    };

    return parentId
        ? jsonRequest(`/locations/${parentId}/locations`, "POST", payload)
        : jsonRequest(`/worlds/${worldId}/locations`, "POST", payload);
}

export async function updateLocation(locationId, location) {
    return jsonRequest(`/locations/${locationId}`, "PATCH", {
        name: location.name,
        description: location.description,
    });
}

export async function deleteLocation(locationId) {
    await apiRequest(`/locations/${locationId}`, { method: "DELETE" });
}

export async function fetchWorldCharacters(worldId) {
    return query("/characters", { world_id: worldId });
}

export async function createWorldCharacter(worldId, character) {
    const created = await jsonRequest(`/worlds/${worldId}/characters`, "POST", characterPayload(character));
    await saveCharacterLocation(created.id, character);
    return created;
}

export async function updateCharacter(characterId, character) {
    const updated = await jsonRequest(`/characters/${characterId}`, "PATCH", characterPayload(character));
    await saveCharacterLocation(characterId, character);
    return updated;
}

export async function deleteCharacter(characterId) {
    await apiRequest(`/characters/${characterId}`, { method: "DELETE" });
}

export async function fetchWorldBackgroundCharacters(worldId) {
    return query("/background-characters", { world_id: worldId });
}

export async function createWorldBackgroundCharacter(worldId, character) {
    return jsonRequest(`/worlds/${worldId}/background-characters`, "POST", nullablePayload(character));
}

export async function updateBackgroundCharacter(characterId, character) {
    return jsonRequest(`/background-characters/${characterId}`, "PATCH", nullablePayload(character));
}

export async function deleteBackgroundCharacter(characterId) {
    await apiRequest(`/background-characters/${characterId}`, { method: "DELETE" });
}

export async function fetchWorldItems(worldId) {
    return query("/items", { world_id: worldId });
}

export async function createWorldItem(worldId, item) {
    return jsonRequest(`/worlds/${worldId}/items`, "POST", itemPayload(item));
}

export async function updateItem(itemId, item) {
    return jsonRequest(`/items/${itemId}`, "PATCH", itemPayload(item));
}

export async function deleteItem(itemId) {
    await apiRequest(`/items/${itemId}`, { method: "DELETE" });
}

export async function fetchWorldEquipment(worldId) {
    return query("/equipment", { world_id: worldId });
}

export async function createWorldEquipment(worldId, equipment) {
    return jsonRequest(`/worlds/${worldId}/equipment`, "POST", nullablePayload(equipment));
}

export async function updateEquipment(equipmentId, equipment) {
    return jsonRequest(`/equipment/${equipmentId}`, "PATCH", nullablePayload(equipment));
}

export async function deleteEquipment(equipmentId) {
    await apiRequest(`/equipment/${equipmentId}`, { method: "DELETE" });
}

export async function fetchWorldContainers(worldId) {
    return query("/containers", { world_id: worldId });
}

export async function createWorldContainer(worldId, container) {
    return jsonRequest(`/worlds/${worldId}/containers`, "POST", containerPayload(container));
}

export async function updateContainer(containerId, container) {
    return jsonRequest(`/containers/${containerId}`, "PATCH", containerPayload(container));
}

export async function deleteContainer(containerId) {
    await apiRequest(`/containers/${containerId}`, { method: "DELETE" });
}

export async function createWorldItemStack(worldId, itemId, stack) {
    return jsonRequest(`/worlds/${worldId}/items/${itemId}/stacks`, "POST", nullablePayload(stack));
}

async function saveCharacterLocation(characterId, character) {
    if (character.location_id) {
        await jsonRequest(`/characters/${characterId}/location`, "PUT", {
            location_id: character.location_id,
            position: cleanText(character.position),
        });
    } else {
        await apiRequest(`/characters/${characterId}/location`, { method: "DELETE" });
    }
}

function characterPayload(character) {
    return {
        user_controlled: Boolean(character.user_controlled),
        name: character.name,
        age: toNumber(character.age, 0),
        gender: character.gender,
        appearance: character.appearance,
        description: character.description,
        public_state: character.public_state,
        private_state: character.private_state,
        current_activity: {
            name: character.activity_name || "Idle",
            interruptible: Boolean(character.activity_interruptible),
            constraints: splitList(character.activity_constraints),
        },
    };
}

function itemPayload(item) {
    return {
        name: item.name,
        description: item.description,
        unique: Boolean(item.unique),
    };
}

function containerPayload(container) {
    return nullablePayload({
        ...container,
        state: container.state || "unlocked",
        held_stack_ids: splitList(container.held_stack_ids),
        held_equipment_ids: splitList(container.held_equipment_ids),
        held_container_ids: splitList(container.held_container_ids),
        unlocking_item_ids: splitList(container.unlocking_item_ids),
    });
}

function nullablePayload(values) {
    return Object.fromEntries(
        Object.entries(values).map(([key, value]) => [
            key,
            typeof value === "string" ? cleanText(value) : value,
        ]),
    );
}

function cleanText(value) {
    if (typeof value !== "string") {
        return value ?? null;
    }

    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function splitList(value) {
    if (Array.isArray(value)) {
        return value;
    }

    return cleanText(value)?.split(",").map((entry) => entry.trim()).filter(Boolean) ?? [];
}

function toNumber(value, fallback) {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
}
