import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CollapsibleFormSection } from "@/components/CollapsibleFormSection";
import { agentRoles } from "@/shared/agentPresetModel";

const messageRoles = ["system", "user", "assistant", "tool"];
const systemMessagePolicies = ["preserve", "merge_to_top", "drop"];
const reasoningOptions = ["", "true", "false", "low", "medium", "high"];

export function AgentPresetEditor({
    enabled,
    onEnabledChange,
    value,
    onChange,
    llmConnections,
    providerLabels,
}) {
    const { t } = useTranslation();
    const [openRoles, setOpenRoles] = useState(
        agentRoles.reduce((state, role) => ({ ...state, [role.key]: false }), {}),
    );
    const [openPrompts, setOpenPrompts] = useState({});

    function updateProfile(roleKey, updater) {
        onChange({
            ...value,
            [roleKey]: updater(value[roleKey]),
        });
    }

    function updateBackend(roleKey, field, fieldValue) {
        updateProfile(roleKey, (profile) => ({
            ...profile,
            backend_configuration: {
                ...profile.backend_configuration,
                [field]: fieldValue,
            },
        }));
    }

    function updateProfileField(roleKey, field, fieldValue) {
        updateProfile(roleKey, (profile) => ({
            ...profile,
            [field]: fieldValue,
        }));
    }

    function addPromptMessage(roleKey, promptKey) {
        updateProfile(roleKey, (profile) => ({
            ...profile,
            prompts: {
                ...profile.prompts,
                [promptKey]: [...profile.prompts[promptKey], { role: "system", content: "" }],
            },
        }));
    }

    function updatePromptMessage(roleKey, promptKey, index, field, fieldValue) {
        updateProfile(roleKey, (profile) => ({
            ...profile,
            prompts: {
                ...profile.prompts,
                [promptKey]: profile.prompts[promptKey].map((message, messageIndex) =>
                    messageIndex === index ? { ...message, [field]: fieldValue } : message,
                ),
            },
        }));
    }

    function removePromptMessage(roleKey, promptKey, index) {
        updateProfile(roleKey, (profile) => ({
            ...profile,
            prompts: {
                ...profile.prompts,
                [promptKey]: profile.prompts[promptKey].filter(
                    (_, messageIndex) => messageIndex !== index,
                ),
            },
        }));
    }

    function togglePrompt(roleKey, promptKey) {
        const key = `${roleKey}.${promptKey}`;
        setOpenPrompts((current) => ({ ...current, [key]: !current[key] }));
    }

    function selectedProvider(profile) {
        const connectionId = Number.parseInt(profile.backend_configuration.connection, 10);
        const connection = llmConnections.find((candidate) => candidate.id === connectionId);
        return connection?.provider ?? "openai";
    }

    return (
        <div className="agent-preset-editor">
            <label className="checkbox-field agent-preset-enable">
                <span>{t("worldCreate.agentPreset.include")}</span>
                <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(event) => onEnabledChange(event.target.checked)}
                />
            </label>

            {enabled ? (
                <div className="nested-form-stack">
                    {agentRoles.map((role) => {
                        const profile = value[role.key];
                        const provider = selectedProvider(profile);

                        return (
                            <div className="agent-role-section" key={role.key}>
                                <CollapsibleFormSection
                                    title={t(`worldCreate.agentPreset.roles.${role.key}`)}
                                    tooltipLabel={t("worldCreate.tooltipLabel", {
                                        field: t(`worldCreate.agentPreset.roles.${role.key}`),
                                    })}
                                    tooltip={t("worldCreate.agentPreset.roleTooltip")}
                                    open={openRoles[role.key]}
                                    onToggle={() =>
                                        setOpenRoles((current) => ({
                                            ...current,
                                            [role.key]: !current[role.key],
                                        }))
                                    }
                                >
                                <div className="agent-profile-editor">
                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-connection`}>
                                            {t("worldCreate.agentPreset.fields.connection")}
                                        </label>
                                        <select
                                            id={`${role.key}-connection`}
                                            className="single-line-input"
                                            value={profile.backend_configuration.connection}
                                            onChange={(event) =>
                                                updateBackend(
                                                    role.key,
                                                    "connection",
                                                    event.target.value,
                                                )
                                            }
                                        >
                                            <option value="">
                                                {t("worldCreate.agentPreset.noConnection")}
                                            </option>
                                            {llmConnections.map((connection) => (
                                                <option key={connection.id} value={connection.id}>
                                                    {connection.name ||
                                                        t("connections.unnamedProfile", {
                                                            provider:
                                                                providerLabels[connection.provider] ??
                                                                connection.provider,
                                                        })}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-model`}>
                                            {t("worldCreate.agentPreset.fields.model")}
                                        </label>
                                        <input
                                            id={`${role.key}-model`}
                                            className="single-line-input"
                                            value={profile.backend_configuration.model}
                                            onChange={(event) =>
                                                updateBackend(role.key, "model", event.target.value)
                                            }
                                        />
                                    </div>

                                    <div className="agent-number-grid">
                                        {[
                                            ["temperature", "number", "0.1"],
                                            ["context_window", "number", "1"],
                                            ["seed", "number", "1"],
                                            ["max_tool_rounds", "number", "1"],
                                        ].map(([field, type, step]) => (
                                            <div className="compact-form-field" key={field}>
                                                <label htmlFor={`${role.key}-${field}`}>
                                                    {t(`worldCreate.agentPreset.fields.${field}`)}
                                                </label>
                                                <input
                                                    id={`${role.key}-${field}`}
                                                    className="single-line-input"
                                                    type={type}
                                                    step={step}
                                                    value={
                                                        field === "max_tool_rounds"
                                                            ? profile.max_tool_rounds
                                                            : profile.backend_configuration[field]
                                                    }
                                                    onChange={(event) =>
                                                        field === "max_tool_rounds"
                                                            ? updateProfileField(
                                                                  role.key,
                                                                  field,
                                                                  event.target.value,
                                                              )
                                                            : updateBackend(
                                                                  role.key,
                                                                  field,
                                                                  event.target.value,
                                                              )
                                                    }
                                                />
                                            </div>
                                        ))}
                                    </div>

                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-reasoning`}>
                                            {t("worldCreate.agentPreset.fields.reasoning")}
                                        </label>
                                        <select
                                            id={`${role.key}-reasoning`}
                                            className="single-line-input"
                                            value={profile.backend_configuration.reasoning}
                                            onChange={(event) =>
                                                updateBackend(
                                                    role.key,
                                                    "reasoning",
                                                    event.target.value,
                                                )
                                            }
                                        >
                                            {reasoningOptions.map((option) => (
                                                <option key={option || "default"} value={option}>
                                                    {t(
                                                        `worldCreate.agentPreset.reasoning.${
                                                            option || "default"
                                                        }`,
                                                    )}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-stop-tokens`}>
                                            {t("worldCreate.agentPreset.fields.stop_tokens")}
                                        </label>
                                        <input
                                            id={`${role.key}-stop-tokens`}
                                            className="single-line-input"
                                            value={profile.backend_configuration.stop_tokens}
                                            onChange={(event) =>
                                                updateBackend(
                                                    role.key,
                                                    "stop_tokens",
                                                    event.target.value,
                                                )
                                            }
                                        />
                                    </div>

                                    {provider === "ollama" ? (
                                        <div className="agent-number-grid">
                                            {[
                                                ["mirostat", "number", "1"],
                                                ["mirostat_eta", "number", "0.1"],
                                                ["mirostat_tau", "number", "0.1"],
                                                ["num_predict", "number", "1"],
                                                ["repeat_penalty_window", "number", "1"],
                                                ["repeat_penalty", "number", "0.1"],
                                            ].map(([field, type, step]) => (
                                                <div className="compact-form-field" key={field}>
                                                    <label htmlFor={`${role.key}-${field}`}>
                                                        {t(
                                                            `worldCreate.agentPreset.fields.${field}`,
                                                        )}
                                                    </label>
                                                    <input
                                                        id={`${role.key}-${field}`}
                                                        className="single-line-input"
                                                        type={type}
                                                        step={step}
                                                        value={profile.backend_configuration[field]}
                                                        onChange={(event) =>
                                                            updateBackend(
                                                                role.key,
                                                                field,
                                                                event.target.value,
                                                            )
                                                        }
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                    ) : null}

                                    <div className="checkbox-grid agent-checkbox-grid">
                                        {[
                                            "remove_empty_messages",
                                            "merge_adjacent_user",
                                            "merge_adjacent_assistant",
                                            "merge_assistant_with_tool_calls",
                                        ].map((field) => (
                                            <label className="checkbox-field" key={field}>
                                                <span>
                                                    {t(
                                                        `worldCreate.agentPreset.fields.${field}`,
                                                    )}
                                                </span>
                                                <input
                                                    type="checkbox"
                                                    checked={profile[field]}
                                                    onChange={(event) =>
                                                        updateProfileField(
                                                            role.key,
                                                            field,
                                                            event.target.checked,
                                                        )
                                                    }
                                                />
                                            </label>
                                        ))}
                                    </div>

                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-system-policy`}>
                                            {t(
                                                "worldCreate.agentPreset.fields.system_message_policy",
                                            )}
                                        </label>
                                        <select
                                            id={`${role.key}-system-policy`}
                                            className="single-line-input"
                                            value={profile.system_message_policy}
                                            onChange={(event) =>
                                                updateProfileField(
                                                    role.key,
                                                    "system_message_policy",
                                                    event.target.value,
                                                )
                                            }
                                        >
                                            {systemMessagePolicies.map((policy) => (
                                                <option key={policy} value={policy}>
                                                    {t(
                                                        `worldCreate.agentPreset.systemMessagePolicy.${policy}`,
                                                    )}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="form-field inline-field">
                                        <label htmlFor={`${role.key}-merge-separator`}>
                                            {t(
                                                "worldCreate.agentPreset.fields.message_merge_separator",
                                            )}
                                        </label>
                                        <input
                                            id={`${role.key}-merge-separator`}
                                            className="single-line-input"
                                            value={profile.message_merge_separator}
                                            onChange={(event) =>
                                                updateProfileField(
                                                    role.key,
                                                    "message_merge_separator",
                                                    event.target.value,
                                                )
                                            }
                                        />
                                    </div>

                                    <div className="prompt-field-stack">
                                        {role.prompts.map((promptKey) => {
                                            const openKey = `${role.key}.${promptKey}`;

                                            return (
                                                <div className="agent-prompt-section" key={promptKey}>
                                                    <CollapsibleFormSection
                                                        title={t(
                                                            `worldCreate.agentPreset.prompts.${promptKey}`,
                                                        )}
                                                        tooltipLabel={t("worldCreate.tooltipLabel", {
                                                            field: t(
                                                                `worldCreate.agentPreset.prompts.${promptKey}`,
                                                            ),
                                                        })}
                                                        tooltip={t(
                                                            "worldCreate.agentPreset.promptTooltip",
                                                        )}
                                                        open={Boolean(openPrompts[openKey])}
                                                        onToggle={() =>
                                                            togglePrompt(role.key, promptKey)
                                                        }
                                                    >
                                                    <div className="prompt-message-list">
                                                        {profile.prompts[promptKey].map(
                                                            (message, index) => (
                                                                <div
                                                                    className="prompt-message-editor"
                                                                    key={index}
                                                                >
                                                                    <div className="prompt-message-header">
                                                                        <select
                                                                            className="single-line-input"
                                                                            value={message.role}
                                                                            onChange={(event) =>
                                                                                updatePromptMessage(
                                                                                    role.key,
                                                                                    promptKey,
                                                                                    index,
                                                                                    "role",
                                                                                    event.target
                                                                                        .value,
                                                                                )
                                                                            }
                                                                        >
                                                                            {messageRoles.map(
                                                                                (messageRole) => (
                                                                                    <option
                                                                                        key={
                                                                                            messageRole
                                                                                        }
                                                                                        value={
                                                                                            messageRole
                                                                                        }
                                                                                    >
                                                                                        {t(
                                                                                            `worldCreate.agentPreset.messageRoles.${messageRole}`,
                                                                                        )}
                                                                                    </option>
                                                                                ),
                                                                            )}
                                                                        </select>
                                                                        <button
                                                                            type="button"
                                                                            className="secondary-button"
                                                                            onClick={() =>
                                                                                removePromptMessage(
                                                                                    role.key,
                                                                                    promptKey,
                                                                                    index,
                                                                                )
                                                                            }
                                                                        >
                                                                            {t(
                                                                                "worldCreate.remove",
                                                                            )}
                                                                        </button>
                                                                    </div>
                                                                    <textarea
                                                                        className="multi-line-input prompt-template-input"
                                                                        value={message.content}
                                                                        onChange={(event) =>
                                                                            updatePromptMessage(
                                                                                role.key,
                                                                                promptKey,
                                                                                index,
                                                                                "content",
                                                                                event.target.value,
                                                                            )
                                                                        }
                                                                    />
                                                                </div>
                                                            ),
                                                        )}

                                                        <div className="prompt-add-row">
                                                            <button
                                                                type="button"
                                                                className="secondary-button"
                                                                onClick={() =>
                                                                    addPromptMessage(
                                                                        role.key,
                                                                        promptKey,
                                                                    )
                                                                }
                                                            >
                                                                {t(
                                                                    "worldCreate.agentPreset.addMessage",
                                                                )}
                                                            </button>
                                                        </div>
                                                    </div>
                                                    </CollapsibleFormSection>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                                </CollapsibleFormSection>
                            </div>
                        );
                    })}
                </div>
            ) : null}
        </div>
    );
}
