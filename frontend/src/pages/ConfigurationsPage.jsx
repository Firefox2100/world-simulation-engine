import { startTransition, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
    createConnection,
    createEmbeddingConfig,
    createLlmConfig,
    deleteConnection,
    deleteEmbeddingConfig,
    deleteLlmConfig,
    fetchConnections,
    fetchEmbeddingConfigs,
    fetchLlmConfigs,
    setEmbeddingConfigConnection,
    setLlmConfigConnection,
    updateConnection,
    updateEmbeddingConfig,
    updateLlmConfig,
} from "@/api/configurations";
import { ConnectionProviderIcon } from "@/components/ConnectionProviderIcon";

const tabs = ["connections", "embeddings", "llms"];
const providers = ["openai", "ollama"];
const ollamaLlmFields = [
    "mirostat",
    "mirostat_eta",
    "mirostat_tau",
    "num_predict",
    "repeat_penalty_window",
    "repeat_penalty",
];

function cleanText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function numberOrNull(value, parser = Number.parseFloat) {
    const cleaned = cleanText(value);
    if (!cleaned) {
        return null;
    }

    const parsed = parser(cleaned, 10);
    return Number.isNaN(parsed) ? null : parsed;
}

function inferLlmProvider(config) {
    if (config.provider || config.type) {
        return config.provider ?? config.type;
    }

    return ollamaLlmFields.some((field) => config[field] !== undefined && config[field] !== null)
        ? "ollama"
        : "openai";
}

function inferEmbeddingProvider(config) {
    if (config.provider || config.type) {
        return config.provider ?? config.type;
    }

    return "openai";
}

function makeFormState(kind, item = null) {
    if (kind === "connections") {
        return {
            type: item?.type ?? "openai",
            name: item?.name ?? "",
            base_url: item?.base_url ?? "",
            api_key: item?.api_key ?? "",
        };
    }

    if (kind === "embeddings") {
        return {
            provider: item ? inferEmbeddingProvider(item) : "openai",
            connection_id: item?.connection?.id ?? "",
            model: item?.model ?? "",
            dimension: item?.dimension == null ? "" : String(item.dimension),
            context_window: item?.context_window == null ? "" : String(item.context_window),
        };
    }

    return {
        provider: item ? inferLlmProvider(item) : "openai",
        connection_id: item?.connection?.id ?? "",
        name: item?.name ?? "",
        model: item?.model ?? "",
        temperature: item?.temperature == null ? "1" : String(item.temperature),
        context_window: item?.context_window == null ? "8192" : String(item.context_window),
        seed: item?.seed == null ? "" : String(item.seed),
        reasoning: item?.reasoning == null ? "" : String(item.reasoning),
        stop_tokens: Array.isArray(item?.stop_tokens) ? item.stop_tokens.join(", ") : "",
        mirostat: item?.mirostat == null ? "" : String(item.mirostat),
        mirostat_eta: item?.mirostat_eta == null ? "" : String(item.mirostat_eta),
        mirostat_tau: item?.mirostat_tau == null ? "" : String(item.mirostat_tau),
        num_predict: item?.num_predict == null ? "" : String(item.num_predict),
        repeat_penalty_window:
            item?.repeat_penalty_window == null ? "" : String(item.repeat_penalty_window),
        repeat_penalty: item?.repeat_penalty == null ? "" : String(item.repeat_penalty),
    };
}

function buildPayload(kind, form, editing) {
    if (kind === "connections") {
        return {
            type: form.type,
            name: form.name.trim(),
            base_url: cleanText(form.base_url),
            api_key: cleanText(form.api_key),
        };
    }

    if (kind === "embeddings") {
        const payload = {
            model: form.model.trim(),
            dimension: numberOrNull(form.dimension, Number.parseInt),
        };

        if (form.provider === "ollama" || editing) {
            payload.context_window = numberOrNull(form.context_window, Number.parseInt);
        }

        return payload;
    }

    const payload = {
        name: form.name.trim(),
        model: form.model.trim(),
        temperature: numberOrNull(form.temperature),
        context_window: numberOrNull(form.context_window, Number.parseInt),
        seed: numberOrNull(form.seed, Number.parseInt),
        reasoning: cleanText(form.reasoning),
        stop_tokens:
            cleanText(form.stop_tokens)?.split(",").map((token) => token.trim()).filter(Boolean) ?? null,
    };

    if (form.provider === "ollama" || editing) {
        payload.mirostat = numberOrNull(form.mirostat, Number.parseInt);
        payload.mirostat_eta = numberOrNull(form.mirostat_eta);
        payload.mirostat_tau = numberOrNull(form.mirostat_tau);
        payload.num_predict = numberOrNull(form.num_predict, Number.parseInt);
        payload.repeat_penalty_window = numberOrNull(form.repeat_penalty_window, Number.parseInt);
        payload.repeat_penalty = numberOrNull(form.repeat_penalty);
    }

    return payload;
}

function hasValue(value) {
    return value !== null && value !== undefined && String(value).trim().length > 0;
}

function isConfigFormValid(kind, form) {
    if (kind === "connections") {
        return hasValue(form.type) && hasValue(form.name);
    }

    if (kind === "embeddings") {
        return hasValue(form.provider) && hasValue(form.connection_id) && hasValue(form.model);
    }

    if (kind === "llms") {
        return hasValue(form.provider) && hasValue(form.connection_id) && hasValue(form.name) && hasValue(form.model);
    }

    return hasValue(form.provider) && hasValue(form.model);
}

function titleFor(kind, item) {
    if (kind === "connections") {
        return item.name;
    }

    if (kind === "llms") {
        return item.name || item.model;
    }

    return item.model;
}

function providerFor(kind, item) {
    if (kind === "connections") {
        return item.type;
    }

    return kind === "embeddings" ? inferEmbeddingProvider(item) : inferLlmProvider(item);
}

function ConfigurationRow({ kind, item, onEdit, onDelete }) {
    const { t } = useTranslation();
    const provider = providerFor(kind, item);
    const title = titleFor(kind, item);
    const details = detailText(kind, item, t);

    return (
        <article className="configuration-row">
            <div className="connection-tile-main">
                <div className="connection-icon-frame" aria-hidden="true">
                    <ConnectionProviderIcon provider={provider} />
                </div>
                <div className="configuration-row-copy">
                    <div className="connection-name" title={title}>
                        {title}
                    </div>
                    <div className="configuration-row-details">{details}</div>
                </div>
            </div>

            <div className="connection-actions">
                <button type="button" className="connection-action-button" onClick={() => onEdit(item)}>
                    {t("configurations.actions.edit")}
                </button>
                <button
                    type="button"
                    className="connection-action-button danger"
                    onClick={() => onDelete(item)}
                >
                    {t("configurations.actions.delete")}
                </button>
            </div>
        </article>
    );
}

function detailText(kind, item, t) {
    if (kind === "connections") {
        return [t(`configurations.providers.${item.type}`, { defaultValue: item.type }), item.base_url]
            .filter(Boolean)
            .join(" · ");
    }

    if (kind === "embeddings") {
        return [
            t(`configurations.providers.${providerFor(kind, item)}`, { defaultValue: providerFor(kind, item) }),
            item.connection
                ? t("configurations.details.connection", { name: item.connection.name })
                : t("configurations.details.noConnection"),
            item.dimension ? t("configurations.details.dimension", { value: item.dimension }) : null,
            item.context_window
                ? t("configurations.details.contextWindow", { value: item.context_window })
                : null,
        ]
            .filter(Boolean)
            .join(" · ");
    }

    return [
        t(`configurations.providers.${providerFor(kind, item)}`, { defaultValue: providerFor(kind, item) }),
        item.connection
            ? t("configurations.details.connection", { name: item.connection.name })
            : t("configurations.details.noConnection"),
        item.model,
        item.context_window ? t("configurations.details.contextWindow", { value: item.context_window }) : null,
        item.temperature != null ? t("configurations.details.temperature", { value: item.temperature }) : null,
    ]
        .filter(Boolean)
        .join(" · ");
}

function ConfigurationModal({ kind, item, connections, onClose, onSaved }) {
    const { t } = useTranslation();
    const editing = Boolean(item);
    const [form, setForm] = useState(() => makeFormState(kind, item));
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const formValid = isConfigFormValid(kind, form);

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    function updateField(field, value) {
        setForm((current) => ({
            ...current,
            [field]: value,
            ...(field === "provider" ? { connection_id: "" } : {}),
        }));
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        try {
            setSaving(true);
            const payload = buildPayload(kind, form, editing);

            let savedConfig = null;

            if (kind === "connections") {
                editing ? await updateConnection(item.id, payload) : await createConnection(payload);
            } else if (kind === "embeddings") {
                savedConfig = editing
                    ? await updateEmbeddingConfig(item.id, payload)
                    : await createEmbeddingConfig(form.provider, payload);
                await setEmbeddingConfigConnection(savedConfig.id, form.connection_id);
            } else {
                savedConfig = editing ? await updateLlmConfig(item.id, payload) : await createLlmConfig(form.provider, payload);
                await setLlmConfigConnection(savedConfig.id, form.connection_id);
            }

            setSaving(false);
            onSaved();
        } catch (err) {
            setSaving(false);
            setError(err.message);
        }
    }

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal-panel compact-modal-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="configuration-modal-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="connection-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="configuration-modal-title">
                            {t(`configurations.modal.${editing ? "edit" : "create"}.${kind}`)}
                        </h2>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("configurations.modal.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </div>

                    <div className="connection-create-form-content">
                        <ConfigurationFields
                            kind={kind}
                            editing={editing}
                            form={form}
                            connections={connections}
                            onChange={updateField}
                        />

                        {error ? <p className="form-error">{t("configurations.modal.error", { error })}</p> : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("configurations.modal.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving || !formValid}>
                            {saving
                                ? t("configurations.modal.saving")
                                : t(`configurations.modal.${editing ? "update" : "submit"}`)}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function ConfigurationFields({ kind, editing, form, connections, onChange }) {
    const { t } = useTranslation();
    const providerField = kind === "connections" ? "type" : "provider";

    return (
        <>
            <div className="form-field inline-field modal-form-field">
                <FieldLabel htmlFor="configuration-provider" label={t("configurations.fields.provider")} required />
                <select
                    id="configuration-provider"
                    className="single-line-input"
                    value={form[providerField]}
                    disabled={editing}
                    onChange={(event) => onChange(providerField, event.target.value)}
                >
                    {providers.map((provider) => (
                        <option key={provider} value={provider}>
                            {t(`configurations.providers.${provider}`)}
                        </option>
                    ))}
                </select>
            </div>

            {kind !== "embeddings" ? (
                <TextField
                    id="configuration-name"
                    label={t("configurations.fields.name")}
                    value={form.name}
                    onChange={(value) => onChange("name", value)}
                    required
                />
            ) : null}

            {kind === "connections" ? (
                <>
                    <TextField
                        id="configuration-base-url"
                        label={t("configurations.fields.baseUrl")}
                        value={form.base_url}
                        onChange={(value) => onChange("base_url", value)}
                    />
                    <TextField
                        id="configuration-api-key"
                        label={t("configurations.fields.apiKey")}
                        value={form.api_key}
                        onChange={(value) => onChange("api_key", value)}
                        type="password"
                    />
                </>
            ) : (
                <ModelFields kind={kind} form={form} connections={connections} onChange={onChange} t={t} />
            )}
        </>
    );
}

function ModelFields({ kind, form, connections, onChange, t }) {
    const showOllamaFields = form.provider === "ollama";
    const matchingConnections = connections.filter((connection) => connection.type === form.provider);

    return (
        <>
            <div className="form-field inline-field modal-form-field">
                <FieldLabel
                    htmlFor="configuration-provider-connection"
                    label={t("configurations.fields.connection")}
                    required
                />
                <select
                    id="configuration-provider-connection"
                    className="single-line-input"
                    value={form.connection_id}
                    required
                    onChange={(event) => onChange("connection_id", event.target.value)}
                >
                    <option value="">{t("configurations.fields.noConnection")}</option>
                    {matchingConnections.map((connection) => (
                        <option key={connection.id} value={connection.id}>
                            {connection.name}
                        </option>
                    ))}
                </select>
            </div>

            <TextField
                id="configuration-model"
                label={t("configurations.fields.model")}
                value={form.model}
                onChange={(value) => onChange("model", value)}
                required
            />

            {kind === "embeddings" ? (
                <>
                    <TextField
                        id="configuration-dimension"
                        label={t("configurations.fields.dimension")}
                        value={form.dimension}
                        onChange={(value) => onChange("dimension", value)}
                        type="number"
                    />
                    {showOllamaFields ? (
                        <TextField
                            id="configuration-context-window"
                            label={t("configurations.fields.contextWindow")}
                            value={form.context_window}
                            onChange={(value) => onChange("context_window", value)}
                            type="number"
                        />
                    ) : null}
                </>
            ) : (
                <>
                    <TextField
                        id="configuration-temperature"
                        label={t("configurations.fields.temperature")}
                        value={form.temperature}
                        onChange={(value) => onChange("temperature", value)}
                        type="number"
                        step="0.1"
                    />
                    <TextField
                        id="configuration-context-window"
                        label={t("configurations.fields.contextWindow")}
                        value={form.context_window}
                        onChange={(value) => onChange("context_window", value)}
                        type="number"
                    />
                    <TextField
                        id="configuration-seed"
                        label={t("configurations.fields.seed")}
                        value={form.seed}
                        onChange={(value) => onChange("seed", value)}
                        type="number"
                    />
                    <TextField
                        id="configuration-reasoning"
                        label={t("configurations.fields.reasoning")}
                        value={form.reasoning}
                        onChange={(value) => onChange("reasoning", value)}
                    />
                    <TextField
                        id="configuration-stop-tokens"
                        label={t("configurations.fields.stopTokens")}
                        value={form.stop_tokens}
                        onChange={(value) => onChange("stop_tokens", value)}
                    />
                    {showOllamaFields
                        ? ollamaLlmFields.map((field) => (
                              <TextField
                                  key={field}
                                  id={`configuration-${field}`}
                                  label={t(`configurations.fields.${field}`)}
                                  value={form[field]}
                                  onChange={(value) => onChange(field, value)}
                                  type={field.includes("eta") || field.includes("tau") || field === "repeat_penalty" ? "number" : "text"}
                              />
                          ))
                        : null}
                </>
            )}
        </>
    );
}

function TextField({ id, label, value, onChange, type = "text", required = false, step }) {
    return (
        <div className="form-field inline-field modal-form-field">
            <FieldLabel htmlFor={id} label={label} required={required} />
            <input
                id={id}
                className="single-line-input"
                value={value}
                type={type}
                required={required}
                step={step}
                onChange={(event) => onChange(event.target.value)}
            />
        </div>
    );
}

function FieldLabel({ htmlFor, label, required }) {
    const { t } = useTranslation();

    return (
        <label htmlFor={htmlFor} className="world-editor-field-label">
            <span>{label}</span>
            <span className={`world-editor-required-badge${required ? " required" : ""}`}>
                {required ? t("worldCreate.newEditor.required") : t("worldCreate.newEditor.optional")}
            </span>
        </label>
    );
}

export function ConfigurationsPage() {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState("connections");
    const [connections, setConnections] = useState([]);
    const [embeddings, setEmbeddings] = useState([]);
    const [llms, setLlms] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [modalState, setModalState] = useState(null);

    const data = useMemo(
        () => ({
            connections,
            embeddings,
            llms,
        }),
        [connections, embeddings, llms],
    );

    async function loadConfigurations() {
        try {
            setLoading(true);
            setError(null);

            const [connectionData, embeddingData, llmData] = await Promise.all([
                fetchConnections(),
                fetchEmbeddingConfigs(),
                fetchLlmConfigs(),
            ]);

            setConnections(connectionData);
            setEmbeddings(embeddingData);
            setLlms(llmData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        startTransition(() => {
            loadConfigurations();
        });
    }, []);

    async function handleDelete(kind, item) {
        const name = titleFor(kind, item);
        if (!window.confirm(t("configurations.confirmDelete", { name }))) {
            return;
        }

        try {
            setActionError(null);
            if (kind === "connections") {
                await deleteConnection(item.id);
            } else if (kind === "embeddings") {
                await deleteEmbeddingConfig(item.id);
            } else {
                await deleteLlmConfig(item.id);
            }

            await loadConfigurations();
        } catch (err) {
            setActionError(err.message);
        }
    }

    async function handleSaved() {
        setModalState(null);
        await loadConfigurations();
    }

    return (
        <section>
            <div className="page-heading page-heading-with-action">
                <div>
                    <h1>{t("configurations.title")}</h1>
                    <p>{t("configurations.subtitle")}</p>
                </div>
                <button
                    type="button"
                    className="primary-button"
                    onClick={() => setModalState({ kind: activeTab, item: null })}
                >
                    {t(`configurations.actions.create.${activeTab}`)}
                </button>
            </div>

            <div className="configuration-tabs" role="tablist" aria-label={t("configurations.tabsLabel")}>
                {tabs.map((tab) => (
                    <button
                        key={tab}
                        type="button"
                        role="tab"
                        aria-selected={activeTab === tab}
                        className={`configuration-tab${activeTab === tab ? " active" : ""}`}
                        onClick={() => setActiveTab(tab)}
                    >
                        {t(`configurations.tabs.${tab}`)}
                    </button>
                ))}
            </div>

            {actionError ? (
                <p className="status-text error-text">{t("configurations.actionError", { error: actionError })}</p>
            ) : null}

            {loading ? (
                <p className="status-text">{t("configurations.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("configurations.error", { error })}</p>
            ) : data[activeTab].length === 0 ? (
                <p className="connection-empty-text">{t(`configurations.empty.${activeTab}`)}</p>
            ) : (
                <div className="configuration-list">
                    {data[activeTab].map((item) => (
                        <ConfigurationRow
                            key={item.id}
                            kind={activeTab}
                            item={item}
                            onEdit={(editItem) => setModalState({ kind: activeTab, item: editItem })}
                            onDelete={(deleteItem) => handleDelete(activeTab, deleteItem)}
                        />
                    ))}
                </div>
            )}

            {modalState ? (
                <ConfigurationModal
                    kind={modalState.kind}
                    item={modalState.item}
                    connections={connections}
                    onClose={() => setModalState(null)}
                    onSaved={handleSaved}
                />
            ) : null}
        </section>
    );
}
