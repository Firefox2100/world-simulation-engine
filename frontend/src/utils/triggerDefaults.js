// Default-value constructors for Trigger's discriminated-union fields (condition/effects/
// operations/entity refs) - kept in a plain module, not alongside the editor components that
// consume them, since a component file may only export components (react-refresh/
// only-export-components) for Vite's fast refresh to work.

export function defaultCondition(type) {
    switch (type) {
        case "time":
            return { type: "time", operator: "gte", value: "" };
        case "variable":
            return { type: "variable", owner_id: "", variable_name: "", operator: "eq", value: "" };
        case "semantic":
            return { type: "semantic", mode: "fact", statement: "", relevant_character_ids: [] };
        case "all_of":
            return { type: "all_of", conditions: [defaultCondition("location")] };
        case "any_of":
            return { type: "any_of", conditions: [defaultCondition("location")] };
        case "not":
            return { type: "not", condition: defaultCondition("location") };
        case "location":
        default:
            return { type: "location", character_id: "", location_id: "", landmark_id: null };
    }
}

export function defaultEntityRef(type = "character") {
    return { type, id: "", name: "" };
}

export function defaultOperation(type) {
    switch (type) {
        case "relationship_change":
            return {
                type: "relationship_change",
                relationship_type: "near",
                subject: defaultEntityRef(),
                object: defaultEntityRef(),
                old_object: null,
                properties: {},
                ended: false,
                source_action_refs: [],
                reason: "",
            };
        case "create":
            return {
                type: "create",
                entity_type: "character",
                proposed_id: null,
                properties: {},
                initial_relationships: [],
                source_action_refs: [],
                reason: "",
            };
        case "promote":
            return {
                type: "promote",
                source_entity: defaultEntityRef(),
                target_entity_type: "equipment",
                target_properties: {},
                preserve_source_as_state: true,
                source_state_changes: [],
                relationship_changes: [],
                source_action_refs: [],
                reason: "",
            };
        case "no_physical_change":
            return { type: "no_physical_change", source_action_refs: [], reason: "" };
        case "state_change":
        default:
            return {
                type: "state_change",
                entity: defaultEntityRef(),
                field_changes: [{ field_path: "", old_value: null, new_value: "", reason: "" }],
                source_action_refs: [],
                reason: "",
            };
    }
}

export function defaultEffect(type) {
    switch (type) {
        case "forced_action":
            return { type: "forced_action", character_id: "", directive: "" };
        case "state_mutation":
            return { type: "state_mutation", operations: [defaultOperation("state_change")], note: "" };
        case "perceived_cue":
            return { type: "perceived_cue", character_ids: [], description: "", expires_after_turns: 20 };
        case "narrative_beat":
        default:
            return { type: "narrative_beat", directive: "", relevant_character_ids: [] };
    }
}
