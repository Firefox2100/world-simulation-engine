import { useTranslation } from "react-i18next";

export function EmbeddingProfileEditor({
    enabled,
    onEnabledChange,
    value,
    onChange,
    llmConnections,
    providerLabels,
}) {
    const { t } = useTranslation();

    function updateField(field, fieldValue) {
        onChange({
            ...value,
            [field]: fieldValue,
        });
    }

    return (
        <div className="embedding-profile-editor">
            <label className="checkbox-field agent-preset-enable">
                <span>{t("worldCreate.embeddingProfile.include")}</span>
                <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(event) => onEnabledChange(event.target.checked)}
                />
            </label>

            {enabled ? (
                <div className="nested-form-stack">
                    <div className="agent-role-section">
                        <div className="agent-profile-editor">
                            <div className="form-field inline-field">
                                <label htmlFor="embedding-connection">
                                    {t("worldCreate.embeddingProfile.fields.connection")}
                                </label>
                                <select
                                    id="embedding-connection"
                                    className="single-line-input"
                                    value={value.connection}
                                    onChange={(event) =>
                                        updateField("connection", event.target.value)
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
                                <label htmlFor="embedding-model">
                                    {t("worldCreate.embeddingProfile.fields.model")}
                                </label>
                                <input
                                    id="embedding-model"
                                    className="single-line-input"
                                    value={value.model}
                                    onChange={(event) => updateField("model", event.target.value)}
                                />
                            </div>

                            <div className="agent-number-grid">
                                {["dimensions", "context_window"].map((field) => (
                                    <div className="compact-form-field" key={field}>
                                        <label htmlFor={`embedding-${field}`}>
                                            {t(`worldCreate.embeddingProfile.fields.${field}`)}
                                        </label>
                                        <input
                                            id={`embedding-${field}`}
                                            className="single-line-input"
                                            type="number"
                                            step="1"
                                            value={value[field]}
                                            onChange={(event) =>
                                                updateField(field, event.target.value)
                                            }
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
