export function makeInitialWorldStateState() {
    return {
        state: {
            id: 1,
            scene: "",
            turn_number: "0",
            state: "",
            time_label: "",
            recent_history_summary: "",
            long_term_history_summary: "",
        },
        characters: [],
        locations: [],
        factions: [],
        faction_relationships: [],
        inventories: [],
        tasks: [],
        world_entries: [],
        turn_records: [],
        nextIds: {
            character: 1,
            location: 1,
            entity: 1,
            faction: 1,
            item: 1,
            equipment: 1,
            task: 1,
            worldEntry: 1,
            turnRecord: 1,
        },
    };
}

export function makeCharacter(id) {
    return {
        id,
        name: "",
        gender: "",
        age: "",
        description: "",
        appearance: "",
        public_state: "",
        private_state: "",
        attributes: [],
        stats: [],
        location: "",
        user_controlled: false,
    };
}

export function makeLocation(id) {
    return {
        id,
        primary_location: "",
        detailed_location: "",
        scene: "",
        description: "",
        attributes: [],
        stats: [],
        entities: [],
    };
}

export function makeEntity(id) {
    return {
        id,
        name: "",
        type: "",
        description: "",
        status: "",
        interactions: [],
    };
}

export function makeFaction(id) {
    return {
        id,
        name: "",
        description: "",
        attributes: [],
        stats: [],
    };
}

export function makeFactionRelationship() {
    return {
        from_type: "character",
        from_id: "",
        to_type: "faction",
        to_id: "",
        relationship: "",
        private: false,
    };
}

export function makeInventory(characterId) {
    return {
        character_id: String(characterId),
        items: [],
        equipments: [],
    };
}

export function makeItem(id) {
    return {
        id,
        name: "",
        description: "",
        quality: "",
        quantity: "1",
        unique: false,
    };
}

export function makeEquipment(id) {
    return {
        id,
        name: "",
        description: "",
        quality: "",
        status: "idle",
    };
}

export function makeTask(id) {
    return {
        id,
        character_ids: [],
        private: true,
        priority: "normal",
        status: "in_progress",
        type: "side_quest",
        goal: "",
        progress: "",
        source: "",
        reward: "",
    };
}

export function makeWorldEntry(id) {
    return {
        id,
        scopeMode: "everyone",
        scope: [],
        content: "",
        visibility: "known",
        confidence: "1",
        created_at: "",
        narration_permission: "visible",
        recall_type: "always",
        keywords: [],
        chained_ids: [],
        semantic_instruction: "",
    };
}

export function makeWorldEntryKeyword() {
    return {
        keyword: "",
        similarity: "0.8",
    };
}

export function makeTurnRecord(id) {
    return {
        id,
        simulation_id: 1,
        turn_number: "0",
        type: "ai_response",
        narration: "",
    };
}

function cleanText(value) {
    const trimmed = String(value).trim();
    return trimmed.length > 0 ? trimmed : "";
}

function buildAttributes(rows) {
    return Object.fromEntries(
        rows
            .map((row) => [
                cleanText(row.name),
                row.values.map(cleanText).filter((value) => value.length > 0),
            ])
            .filter(([name, values]) => name.length > 0 && values.length > 0),
    );
}

function buildStats(rows) {
    return Object.fromEntries(
        rows
            .map((row) => [cleanText(row.name), Number.parseFloat(row.value)])
            .filter(([name, value]) => name.length > 0 && !Number.isNaN(value)),
    );
}

function buildEntity(entity) {
    return {
        id: entity.id,
        name: cleanText(entity.name),
        type: cleanText(entity.type),
        description: cleanText(entity.description),
        status: cleanText(entity.status),
        interactions: entity.interactions.map(cleanText).filter((value) => value.length > 0),
    };
}

function buildLocation(location) {
    return {
        id: location.id,
        primary_location: cleanText(location.primary_location),
        detailed_location: cleanText(location.detailed_location),
        scene: cleanText(location.scene),
        description: cleanText(location.description),
        attributes: buildAttributes(location.attributes),
        stats: buildStats(location.stats),
        entities: location.entities.map(buildEntity),
    };
}

function buildCharacter(character) {
    return {
        id: character.id,
        name: cleanText(character.name),
        gender: cleanText(character.gender),
        age: Number.parseInt(character.age, 10) || 0,
        description: cleanText(character.description),
        appearance: cleanText(character.appearance),
        public_state: cleanText(character.public_state),
        private_state: cleanText(character.private_state),
        attributes: buildAttributes(character.attributes),
        stats: buildStats(character.stats),
        location: Number.parseInt(character.location, 10) || 0,
        user_controlled: character.user_controlled,
    };
}

function buildFaction(faction) {
    return {
        id: faction.id,
        name: cleanText(faction.name),
        description: cleanText(faction.description),
        attributes: buildAttributes(faction.attributes),
        stats: buildStats(faction.stats),
    };
}

function buildFactionRelationship(relationship) {
    return {
        from_type: relationship.from_type,
        from_id: Number.parseInt(relationship.from_id, 10) || 0,
        to_type: relationship.to_type,
        to_id: Number.parseInt(relationship.to_id, 10) || 0,
        relationship: cleanText(relationship.relationship),
        private: relationship.private,
    };
}

function optionalText(value) {
    const text = cleanText(value);
    return text.length > 0 ? text : undefined;
}

function buildItem(item) {
    return {
        id: item.id,
        name: cleanText(item.name),
        description: cleanText(item.description),
        quality: optionalText(item.quality),
        quantity: Number.parseInt(item.quantity, 10) || 0,
        unique: item.unique,
    };
}

function buildEquipment(equipment) {
    return {
        id: equipment.id,
        name: cleanText(equipment.name),
        description: cleanText(equipment.description),
        quality: optionalText(equipment.quality),
        status: equipment.status,
    };
}

function buildTask(task) {
    const progress = String(task.progress).trim();

    return {
        id: task.id,
        character_ids: task.character_ids.map((id) => Number.parseInt(id, 10)),
        private: task.private,
        priority: task.priority,
        status: task.status,
        type: task.type,
        goal: cleanText(task.goal),
        progress: progress.length > 0 ? Number.parseInt(progress, 10) : undefined,
        source: cleanText(task.source),
        reward: cleanText(task.reward),
    };
}

function buildWorldEntry(entry) {
    let scope = entry.scope.map((id) => Number.parseInt(id, 10));

    if (entry.scopeMode === "everyone") {
        scope = [0];
    } else if (entry.scopeMode === "no_one") {
        scope = [-1];
    }

    const createdAt = String(entry.created_at).trim();

    return {
        id: entry.id,
        scope,
        content: cleanText(entry.content),
        visibility: entry.visibility,
        confidence: Number.parseFloat(entry.confidence),
        created_at: createdAt.length > 0 ? Number.parseInt(createdAt, 10) : undefined,
        narration_permission: entry.narration_permission,
        recall_type: entry.recall_type,
        keywords:
            entry.keywords.length > 0
                ? entry.keywords
                      .map((keyword) => ({
                          keyword: cleanText(keyword.keyword),
                          similarity: Number.parseFloat(keyword.similarity),
                      }))
                      .filter((keyword) => keyword.keyword.length > 0)
                : undefined,
        chained_ids:
            entry.chained_ids.length > 0
                ? entry.chained_ids.map((id) => Number.parseInt(id, 10))
                : undefined,
        semantic_instruction: optionalText(entry.semantic_instruction),
    };
}

function buildTurnRecord(record) {
    return {
        id: record.id,
        simulation_id: record.simulation_id,
        turn_number: Number.parseInt(record.turn_number, 10) || 0,
        type: record.type,
        narration: cleanText(record.narration),
    };
}

export function buildSimulationStatePayload(initialState) {
    return {
        id: initialState.state.id,
        scene: Number.parseInt(initialState.state.scene, 10) || 0,
        turn_number: Number.parseInt(initialState.state.turn_number, 10) || 0,
        state: cleanText(initialState.state.state),
        time_label: cleanText(initialState.state.time_label),
        recent_history_summary:
            cleanText(initialState.state.recent_history_summary) || undefined,
        long_term_history_summary:
            cleanText(initialState.state.long_term_history_summary) || undefined,
    };
}

export function buildCharactersPayload(initialState) {
    return initialState.characters.map(buildCharacter);
}

export function buildLocationsPayload(initialState) {
    return initialState.locations.map(buildLocation);
}

export function buildFactionsPayload(initialState) {
    return initialState.factions.map(buildFaction);
}

export function buildFactionRelationshipsPayload(initialState) {
    return initialState.faction_relationships.map(buildFactionRelationship);
}

export function buildInventoryPayload(initialState) {
    return Object.fromEntries(
        initialState.inventories
            .filter((inventory) => inventory.character_id !== "")
            .map((inventory) => [
                Number.parseInt(inventory.character_id, 10),
                {
                    items: inventory.items.map(buildItem),
                    equipments: inventory.equipments.map(buildEquipment),
                },
            ]),
    );
}

export function buildTasksPayload(initialState) {
    return initialState.tasks.map(buildTask);
}

export function buildWorldEntriesPayload(initialState) {
    return initialState.world_entries.map(buildWorldEntry);
}

export function buildTurnRecordsPayload(initialState) {
    return initialState.turn_records.map(buildTurnRecord);
}
