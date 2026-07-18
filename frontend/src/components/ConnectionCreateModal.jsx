import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
    createImageConnectionProfile,
    createLlmConnectionProfile,
    updateImageConnectionProfile,
    updateLlmConnectionProfile,
} from "@/api/connections";

const providerOptions = {
    llm: ["openai", "ollama"],
    image: ["comfy_ui"],
};

function cleanOptionalText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

export function ConnectionCreateModal({ type, profile = null, providerLabels, onClose, onCreated }) {
    const { t } = useTranslation();
    const providers = providerOptions[type];
    const editing = Boolean(profile);
    const [provider, setProvider] = useState(profile?.provider ?? providers[0]);
    const [name, setName] = useState(profile?.name ?? "");
    const [baseUrl, setBaseUrl] = useState(profile?.base_url ?? "");
    const [apiKey, setApiKey] = useState(profile?.api_key ?? "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    function buildPayload() {
        const cleanedName = cleanOptionalText(name);
        const cleanedBaseUrl = cleanOptionalText(baseUrl);
        const cleanedApiKey = cleanOptionalText(apiKey);

        if (editing) {
            return {
                name: cleanedName,
                base_url: cleanedBaseUrl,
                api_key: cleanedApiKey,
            };
        }

        const payload = { provider };

        if (cleanedName) {
            payload.name = cleanedName;
        }

        if (cleanedBaseUrl) {
            payload.base_url = cleanedBaseUrl;
        }

        if (cleanedApiKey) {
            payload.api_key = cleanedApiKey;
        }

        return payload;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        try {
            setSaving(true);
            if (editing && type === "llm") {
                await updateLlmConnectionProfile(profile.id, buildPayload());
            } else if (editing) {
                await updateImageConnectionProfile(profile.id, buildPayload());
            } else if (type === "llm") {
                await createLlmConnectionProfile(buildPayload());
            } else {
                await createImageConnectionProfile(buildPayload());
            }
            setSaving(false);
            onCreated();
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal-panel compact-modal-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="create-connection-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="connection-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="create-connection-title">
                            {editing ? t(`connectionCreate.${type}.editTitle`) : t(`connectionCreate.${type}.title`)}
                        </h2>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("connectionCreate.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </div>

                    <div className="connection-create-form-content">
                        <div className="form-field inline-field">
                            <label htmlFor="connection-provider">
                                {t("connectionCreate.fields.provider.label")}
                            </label>
                            <select
                                id="connection-provider"
                                className="single-line-input"
                                value={provider}
                                disabled={editing}
                                onChange={(event) => setProvider(event.target.value)}
                            >
                                {providers.map((providerOption) => (
                                    <option key={providerOption} value={providerOption}>
                                        {providerLabels[providerOption] ?? providerOption}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="connection-name">
                                {t("connectionCreate.fields.name.label")}
                            </label>
                            <input
                                id="connection-name"
                                className="single-line-input"
                                value={name}
                                onChange={(event) => setName(event.target.value)}
                            />
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="connection-base-url">
                                {t("connectionCreate.fields.baseUrl.label")}
                            </label>
                            <input
                                id="connection-base-url"
                                className="single-line-input"
                                value={baseUrl}
                                onChange={(event) => setBaseUrl(event.target.value)}
                                placeholder={t("connectionCreate.fields.baseUrl.placeholder")}
                            />
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="connection-api-key">
                                {t("connectionCreate.fields.apiKey.label")}
                            </label>
                            <input
                                id="connection-api-key"
                                className="single-line-input"
                                type="password"
                                value={apiKey}
                                onChange={(event) => setApiKey(event.target.value)}
                                autoComplete="off"
                            />
                        </div>

                        {error ? (
                            <p className="form-error">
                                {t(editing ? "connectionCreate.editError" : "connectionCreate.error", { error })}
                            </p>
                        ) : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("connectionCreate.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving}>
                            {saving
                                ? t(editing ? "connectionCreate.updating" : "connectionCreate.saving")
                                : t(editing ? "connectionCreate.update" : "connectionCreate.submit")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
