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

function maxId(items) {
    return items.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0);
}

function attributeRows(attributes = {}) {
    return Object.entries(attributes).map(([name, values]) => ({
        name,
        values: values ?? [],
    }));
}

function statRows(stats = {}) {
    return Object.entries(stats).map(([name, value]) => ({
        name,
        value: String(value),
    }));
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

export function initialWorldStateFormFromWorld(world = {}) {
    const locations = (world.locations ?? []).map((location) => ({
        id: location.id,
        primary_location: location.primary_location ?? "",
        detailed_location: location.detailed_location ?? "",
        scene: location.scene ?? "",
        description: location.description ?? "",
        attributes: attributeRows(location.attributes),
        stats: statRows(location.stats),
        entities: (location.entities ?? []).map((entity) => ({
            id: entity.id,
            name: entity.name ?? "",
            type: entity.type ?? "",
            description: entity.description ?? "",
            status: entity.status ?? "",
            interactions: entity.interactions ?? [],
        })),
    }));

    const characters = (world.characters ?? []).map((character) => ({
        id: character.id,
        name: character.name ?? "",
        gender: character.gender ?? "",
        age: character.age == null ? "" : String(character.age),
        description: character.description ?? "",
        appearance: character.appearance ?? "",
        public_state: character.public_state ?? "",
        private_state: character.private_state ?? "",
        attributes: attributeRows(character.attributes),
        stats: statRows(character.stats),
        location: character.location == null ? "" : String(character.location),
        user_controlled: character.user_controlled ?? false,
    }));

    const factions = (world.factions ?? []).map((faction) => ({
        id: faction.id,
        name: faction.name ?? "",
        description: faction.description ?? "",
        attributes: attributeRows(faction.attributes),
        stats: statRows(faction.stats),
    }));

    const inventories = Object.entries(world.inventory ?? {}).map(([characterId, inventory]) => ({
        character_id: String(characterId),
        items: (inventory.items ?? []).map((item) => ({
            id: item.id,
            name: item.name ?? "",
            description: item.description ?? "",
            quality: item.quality ?? "",
            quantity: item.quantity == null ? "1" : String(item.quantity),
            unique: item.unique ?? false,
        })),
        equipments: (inventory.equipments ?? []).map((equipment) => ({
            id: equipment.id,
            name: equipment.name ?? "",
            description: equipment.description ?? "",
            quality: equipment.quality ?? "",
            status: equipment.status ?? "idle",
        })),
    }));

    const allItems = inventories.flatMap((inventory) => inventory.items);
    const allEquipments = inventories.flatMap((inventory) => inventory.equipments);
    const entities = locations.flatMap((location) => location.entities);

    return {
        state: world.state
            ? {
                  id: world.state.id ?? 1,
                  scene: world.state.scene == null ? "" : String(world.state.scene),
                  turn_number:
                      world.state.turn_number == null ? "0" : String(world.state.turn_number),
                  state: world.state.state ?? "",
                  time_label: world.state.time_label ?? "",
                  recent_history_summary: world.state.recent_history_summary ?? "",
                  long_term_history_summary: world.state.long_term_history_summary ?? "",
              }
            : makeInitialWorldStateState().state,
        characters,
        locations,
        factions,
        faction_relationships: (world.faction_relationships ?? []).map((relationship) => ({
            from_type: relationship.from_type ?? "character",
            from_id: relationship.from_id == null ? "" : String(relationship.from_id),
            to_type: relationship.to_type ?? "faction",
            to_id: relationship.to_id == null ? "" : String(relationship.to_id),
            relationship: relationship.relationship ?? "",
            private: relationship.private ?? false,
        })),
        inventories,
        tasks: (world.tasks ?? []).map((task) => ({
            id: task.id,
            character_ids: (task.character_ids ?? []).map(String),
            private: task.private ?? true,
            priority: task.priority ?? "normal",
            status: task.status ?? "in_progress",
            type: task.type ?? "side_quest",
            goal: task.goal ?? "",
            progress: task.progress == null ? "" : String(task.progress),
            source: task.source ?? "",
            reward: task.reward ?? "",
        })),
        world_entries: (world.world_entries ?? []).map((entry) => {
            let scopeMode = "characters";
            if ((entry.scope ?? []).includes(0)) {
                scopeMode = "everyone";
            } else if ((entry.scope ?? []).includes(-1)) {
                scopeMode = "no_one";
            }

            return {
                id: entry.id,
                scopeMode,
                scope: (entry.scope ?? []).filter((id) => id > 0).map(String),
                content: entry.content ?? "",
                visibility: entry.visibility ?? "known",
                confidence: entry.confidence == null ? "1" : String(entry.confidence),
                created_at: entry.created_at == null ? "" : String(entry.created_at),
                narration_permission: entry.narration_permission ?? "visible",
                recall_type: entry.recall_type ?? "always",
                keywords: (entry.keywords ?? []).map((keyword) => ({
                    keyword: keyword.keyword ?? "",
                    similarity:
                        keyword.similarity == null ? "0.8" : String(keyword.similarity),
                })),
                chained_ids: (entry.chained_ids ?? []).map(String),
                semantic_instruction: entry.semantic_instruction ?? "",
            };
        }),
        turn_records: (world.turn_records ?? []).map((record) => ({
            id: record.id,
            simulation_id: record.simulation_id ?? 1,
            turn_number: record.turn_number == null ? "0" : String(record.turn_number),
            type: record.type ?? "ai_response",
            narration: record.narration ?? "",
        })),
        nextIds: {
            character: maxId(characters) + 1,
            location: maxId(locations) + 1,
            entity: maxId(entities) + 1,
            faction: maxId(factions) + 1,
            item: maxId(allItems) + 1,
            equipment: maxId(allEquipments) + 1,
            task: maxId(world.tasks ?? []) + 1,
            worldEntry: maxId(world.world_entries ?? []) + 1,
            turnRecord: maxId(world.turn_records ?? []) + 1,
        },
    };
}
