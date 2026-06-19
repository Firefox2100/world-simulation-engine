export const agentRoles = [
    {
        key: "director",
        prompts: ["generation_prompt", "planning_prompt"],
    },
    {
        key: "memory",
        prompts: ["briefing_prompt", "summary_prompt"],
    },
    {
        key: "character",
        prompts: ["action_prompt", "reaction_prompt"],
    },
    {
        key: "resolver",
        prompts: ["resolve_character_prompt", "resolve_reaction_prompt", "resolve_user_prompt"],
    },
    {
        key: "committer",
        prompts: ["mutation_prompt", "validation_prompt"],
    },
    {
        key: "narrator",
        prompts: [
            "narrate_resolved_turn_prompt",
            "narrate_user_input_failure_prompt",
            "narrate_wait_for_user_prompt",
        ],
    },
    {
        key: "world_generator",
        prompts: [
            "location_generation_prompt",
            "item_generation_prompt",
            "equipment_generation_prompt",
            "entity_generation_prompt",
            "world_entry_generation_prompt",
            "generation_package_prompt",
        ],
    },
];

function makePromptState(promptKeys) {
    return promptKeys.reduce((state, key) => ({ ...state, [key]: [] }), {});
}

function makeAgentProfile(role) {
    return {
        backend_configuration: {
            connection: "",
            model: "",
            temperature: "1.0",
            context_window: "8192",
            seed: "",
            reasoning: "",
            stop_tokens: "",
            mirostat: "",
            mirostat_eta: "",
            mirostat_tau: "",
            num_predict: "",
            repeat_penalty_window: "",
            repeat_penalty: "",
        },
        remove_empty_messages: true,
        merge_adjacent_user: true,
        merge_adjacent_assistant: false,
        merge_assistant_with_tool_calls: false,
        system_message_policy: "merge_to_top",
        message_merge_separator: "\n\n",
        max_tool_rounds: "3",
        prompts: makePromptState(role.prompts),
    };
}

export function makeAgentPresetState() {
    return agentRoles.reduce((state, role) => ({ ...state, [role.key]: makeAgentProfile(role) }), {});
}

function optionalNumber(value, parser) {
    const trimmed = String(value).trim();
    return trimmed.length > 0 ? parser(trimmed) : undefined;
}

function parseReasoning(value) {
    if (value === "true") {
        return true;
    }

    if (value === "false") {
        return false;
    }

    return value || undefined;
}

function compactObject(object) {
    return Object.fromEntries(Object.entries(object).filter(([, value]) => value !== undefined));
}

function promptPayload(messages) {
    return messages
        .map((message) => ({
            role: message.role,
            content: message.content.trim(),
        }))
        .filter((message) => message.content.length > 0);
}

export function buildAgentPresetPayload(agentPreset) {
    return Object.fromEntries(
        agentRoles.map((role) => {
            const profile = agentPreset[role.key];
            const backend = profile.backend_configuration;
            const payload = {
                backend_configuration: compactObject({
                    connection:
                        backend.connection === "" ? undefined : Number.parseInt(backend.connection, 10),
                    model: backend.model.trim(),
                    temperature: Number.parseFloat(backend.temperature),
                    context_window: Number.parseInt(backend.context_window, 10),
                    seed: optionalNumber(backend.seed, Number.parseInt),
                    reasoning: parseReasoning(backend.reasoning),
                    stop_tokens:
                        backend.stop_tokens.trim().length > 0
                            ? backend.stop_tokens
                                  .split("\n")
                                  .map((token) => token.trim())
                                  .filter(Boolean)
                            : undefined,
                    mirostat: optionalNumber(backend.mirostat, Number.parseInt),
                    mirostat_eta: optionalNumber(backend.mirostat_eta, Number.parseFloat),
                    mirostat_tau: optionalNumber(backend.mirostat_tau, Number.parseFloat),
                    num_predict: optionalNumber(backend.num_predict, Number.parseInt),
                    repeat_penalty_window: optionalNumber(
                        backend.repeat_penalty_window,
                        Number.parseInt,
                    ),
                    repeat_penalty: optionalNumber(backend.repeat_penalty, Number.parseFloat),
                }),
                remove_empty_messages: profile.remove_empty_messages,
                merge_adjacent_user: profile.merge_adjacent_user,
                merge_adjacent_assistant: profile.merge_adjacent_assistant,
                merge_assistant_with_tool_calls: profile.merge_assistant_with_tool_calls,
                system_message_policy: profile.system_message_policy,
                message_merge_separator: profile.message_merge_separator,
                max_tool_rounds: Number.parseInt(profile.max_tool_rounds, 10),
            };

            role.prompts.forEach((promptKey) => {
                payload[promptKey] = promptPayload(profile.prompts[promptKey]);
            });

            return [role.key, payload];
        }),
    );
}
