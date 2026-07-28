import { startTransition, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
    createConnection,
    createEmbeddingConfig,
    createImageConfig,
    createLlmConfig,
    createSttConfig,
    createTtsConfig,
    deleteConnection,
    deleteEmbeddingConfig,
    deleteImageConfig,
    deleteLlmConfig,
    deleteSttConfig,
    deleteTtsConfig,
    fetchConnections,
    fetchEmbeddingConfigs,
    fetchImageConfigs,
    fetchLlmConfigs,
    fetchSttConfigs,
    fetchTtsConfigs,
    setEmbeddingConfigConnection,
    setImageConfigConnection,
    setLlmConfigConnection,
    setSttConfigConnection,
    setTtsConfigConnection,
    updateConnection,
    updateEmbeddingConfig,
    updateImageConfig,
    updateLlmConfig,
    updateSttConfig,
    updateTtsConfig,
} from "@/api/configurations";
import { ConnectionProviderIcon } from "@/components/ConnectionProviderIcon";

const tabs = ["connections", "embeddings", "llms", "tts", "images", "stt"];
const connectionProviders = ["openai", "ollama", "alltalk", "whispercpp", "comfyui"];
const modelProviders = ["openai", "ollama"];
const ttsEngines = ["xtts", "piper", "vits", "parler", "f5tts"];
const ttsLanguageEngines = ["xtts", "vits", "f5tts"];
const ttsTemperatureEngines = ["xtts", "parler"];
const ttsRepetitionPenaltyEngines = ["xtts"];
const imageProviders = ["comfyui"];
const sttProviders = ["whispercpp"];
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
            provider: item ? inferEmbeddingProvider(item) : "",
            connection_id: item?.connection?.id ?? "",
            name: item?.name ?? "",
            model: item?.model ?? "",
            dimension: item?.dimension == null ? "" : String(item.dimension),
            context_window: item?.context_window == null ? "" : String(item.context_window),
        };
    }

    if (kind === "tts") {
        return {
            engine: item?.engine ?? "xtts",
            connection_id: item?.connection?.id ?? "",
            model: item?.model ?? "",
            narrator_voice: item?.narrator_voice ?? "",
            narrator_enabled: item?.narrator_enabled ?? false,
            text_filtering: item?.text_filtering ?? "",
            text_not_inside: item?.text_not_inside ?? "",
            rvc_narrator_voice: item?.rvc_narrator_voice ?? "",
            rvc_narrator_pitch: item?.rvc_narrator_pitch == null ? "" : String(item.rvc_narrator_pitch),
            output_file_timestamp: item?.output_file_timestamp ?? false,
            autoplay: item?.autoplay ?? false,
            autoplay_volume: item?.autoplay_volume == null ? "" : String(item.autoplay_volume),
            language: item?.language ?? "",
            speed: item?.speed == null ? "" : String(item.speed),
            temperature: item?.temperature == null ? "" : String(item.temperature),
            repetition_penalty: item?.repetition_penalty == null ? "" : String(item.repetition_penalty),
        };
    }

    if (kind === "images") {
        return {
            provider: imageProviders[0],
            connection_id: item?.connection?.id ?? "",
            model: item?.model ?? "",
            vae: item?.vae ?? "",
            clip: item?.clip ?? "",
            image_width: item?.image_width == null ? "" : String(item.image_width),
            image_height: item?.image_height == null ? "" : String(item.image_height),
            seed: item?.seed == null ? "" : String(item.seed),
            steps: item?.steps == null ? "" : String(item.steps),
            cfg: item?.cfg == null ? "" : String(item.cfg),
        };
    }

    if (kind === "stt") {
        return {
            provider: sttProviders[0],
            connection_id: item?.connection?.id ?? "",
            model: item?.model ?? "",
            language: item?.language ?? "",
            translate: item?.translate ?? false,
            temperature: item?.temperature == null ? "" : String(item.temperature),
            temperature_inc: item?.temperature_inc == null ? "" : String(item.temperature_inc),
            initial_prompt: item?.initial_prompt ?? "",
            carry_initial_prompt: item?.carry_initial_prompt ?? false,
        };
    }

    return {
        provider: item ? inferLlmProvider(item) : "",
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
            name: cleanText(form.name),
            model: form.model.trim(),
            dimension: numberOrNull(form.dimension, Number.parseInt),
        };

        if (form.provider === "ollama" || editing) {
            payload.context_window = numberOrNull(form.context_window, Number.parseInt);
        }

        return payload;
    }

    if (kind === "tts") {
        const payload = {
            model: cleanText(form.model),
            narrator_voice: cleanText(form.narrator_voice),
            narrator_enabled: form.narrator_enabled,
            text_filtering: form.text_filtering || null,
            text_not_inside: form.text_not_inside || null,
            rvc_narrator_voice: cleanText(form.rvc_narrator_voice),
            rvc_narrator_pitch: numberOrNull(form.rvc_narrator_pitch, Number.parseInt),
            output_file_timestamp: form.output_file_timestamp,
            autoplay: form.autoplay,
            autoplay_volume: numberOrNull(form.autoplay_volume),
            speed: numberOrNull(form.speed),
        };

        if (ttsLanguageEngines.includes(form.engine)) {
            payload.language = cleanText(form.language);
        }
        if (ttsTemperatureEngines.includes(form.engine)) {
            payload.temperature = numberOrNull(form.temperature);
        }
        if (ttsRepetitionPenaltyEngines.includes(form.engine)) {
            payload.repetition_penalty = numberOrNull(form.repetition_penalty);
        }

        return payload;
    }

    if (kind === "images") {
        return {
            model: cleanText(form.model),
            vae: cleanText(form.vae),
            clip: cleanText(form.clip),
            image_width: numberOrNull(form.image_width, Number.parseInt),
            image_height: numberOrNull(form.image_height, Number.parseInt),
            seed: numberOrNull(form.seed, Number.parseInt),
            steps: numberOrNull(form.steps, Number.parseInt),
            cfg: numberOrNull(form.cfg, Number.parseInt),
        };
    }

    if (kind === "stt") {
        return {
            model: cleanText(form.model),
            language: cleanText(form.language),
            translate: form.translate,
            temperature: numberOrNull(form.temperature),
            temperature_inc: numberOrNull(form.temperature_inc),
            initial_prompt: cleanText(form.initial_prompt),
            carry_initial_prompt: form.carry_initial_prompt,
        };
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

    if (kind === "tts" || kind === "images" || kind === "stt") {
        return hasValue(form.connection_id);
    }

    return hasValue(form.provider) && hasValue(form.model);
}

function titleFor(kind, item) {
    if (kind === "connections") {
        return item.name;
    }

    if (kind === "llms" || kind === "embeddings") {
        return item.name || item.model;
    }

    if (kind === "tts") {
        return item.model || item.narrator_voice || item.engine;
    }

    if (kind === "images") {
        return item.model || "ComfyUI";
    }

    if (kind === "stt") {
        return item.model || "whisper.cpp";
    }

    return item.model;
}

function providerFor(kind, item) {
    if (kind === "connections") {
        return item.type;
    }

    if (kind === "tts") {
        return item.engine;
    }

    if (kind === "images" || kind === "stt") {
        return item.provider;
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

    if (kind === "tts") {
        return [
            t(`configurations.providers.${item.engine}`, { defaultValue: item.engine }),
            item.connection
                ? t("configurations.details.connection", { name: item.connection.name })
                : t("configurations.details.noConnection"),
            item.narrator_voice
                ? t("configurations.details.narratorVoice", { value: item.narrator_voice })
                : null,
            item.speed != null ? t("configurations.details.speed", { value: item.speed }) : null,
        ]
            .filter(Boolean)
            .join(" · ");
    }

    if (kind === "images") {
        return [
            t("configurations.providers.comfyui"),
            item.connection
                ? t("configurations.details.connection", { name: item.connection.name })
                : t("configurations.details.noConnection"),
            item.image_width && item.image_height
                ? t("configurations.details.imageSize", { width: item.image_width, height: item.image_height })
                : null,
            item.steps != null ? t("configurations.details.steps", { value: item.steps }) : null,
        ]
            .filter(Boolean)
            .join(" · ");
    }

    if (kind === "stt") {
        return [
            t("configurations.providers.whispercpp"),
            item.connection
                ? t("configurations.details.connection", { name: item.connection.name })
                : t("configurations.details.noConnection"),
            item.language ? t("configurations.details.language", { value: item.language }) : null,
            item.temperature != null ? t("configurations.details.temperature", { value: item.temperature }) : null,
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
        setForm((current) => {
            const next = {
                ...current,
                [field]: value,
                ...(field === "engine" ? { connection_id: "" } : {}),
            };

            // The provider/type is no longer picked directly - it's implied by whichever
            // connection is selected, since a connection already carries that information.
            if (field === "connection_id" && kind !== "connections" && kind !== "tts") {
                const selectedConnection = connections.find((connection) => connection.id === value);
                next.provider = selectedConnection?.type ?? "";
            }

            return next;
        });
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
            } else if (kind === "tts") {
                savedConfig = editing
                    ? await updateTtsConfig(item.id, payload)
                    : await createTtsConfig(form.engine, payload);
                await setTtsConfigConnection(savedConfig.id, form.connection_id);
            } else if (kind === "images") {
                savedConfig = editing
                    ? await updateImageConfig(item.id, payload)
                    : await createImageConfig(form.provider, payload);
                await setImageConfigConnection(savedConfig.id, form.connection_id);
            } else if (kind === "stt") {
                savedConfig = editing
                    ? await updateSttConfig(item.id, payload)
                    : await createSttConfig(form.provider, payload);
                await setSttConfigConnection(savedConfig.id, form.connection_id);
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
    const showProviderSelect = kind === "connections" || kind === "tts";
    const providerField = kind === "connections" ? "type" : "engine";
    const providerOptions = kind === "connections" ? connectionProviders : ttsEngines;
    const providerLabel = kind === "tts" ? t("configurations.fields.engine") : t("configurations.fields.provider");

    return (
        <>
            {showProviderSelect ? (
                <div className="form-field inline-field modal-form-field">
                    <FieldLabel htmlFor="configuration-provider" label={providerLabel} required />
                    <select
                        id="configuration-provider"
                        className="single-line-input"
                        value={form[providerField]}
                        disabled={editing}
                        onChange={(event) => onChange(providerField, event.target.value)}
                    >
                        {providerOptions.map((option) => (
                            <option key={option} value={option}>
                                {t(`configurations.providers.${option}`)}
                            </option>
                        ))}
                    </select>
                </div>
            ) : null}

            {kind !== "tts" && kind !== "images" && kind !== "stt" ? (
                <TextField
                    id="configuration-name"
                    label={t("configurations.fields.name")}
                    value={form.name}
                    onChange={(value) => onChange("name", value)}
                    required={kind !== "embeddings"}
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
                <ModelFields kind={kind} editing={editing} form={form} connections={connections} onChange={onChange} t={t} />
            )}
        </>
    );
}

function ModelFields({ kind, editing, form, connections, onChange, t }) {
    const showOllamaFields = form.provider === "ollama";
    const matchingConnections = kind === "tts"
        ? connections.filter((connection) => connection.type === "alltalk")
        : kind === "images"
            ? connections.filter((connection) => imageProviders.includes(connection.type))
            : kind === "stt"
                ? connections.filter((connection) => sttProviders.includes(connection.type))
                // Editing an existing embedding/LLM config can't change its provider (the
                // Neo4j node label is fixed at creation), so only offer connections that
                // still match it. Creating a new one lets any supported provider's
                // connections through - picking one derives the provider automatically.
                : editing
                    ? connections.filter((connection) => connection.type === form.provider)
                    : connections.filter((connection) => modelProviders.includes(connection.type));

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
                required={kind !== "tts" && kind !== "images" && kind !== "stt"}
            />

            {kind === "tts" ? (
                <TtsModelFields form={form} onChange={onChange} t={t} />
            ) : kind === "images" ? (
                <ImageModelFields form={form} onChange={onChange} t={t} />
            ) : kind === "stt" ? (
                <SttModelFields form={form} onChange={onChange} t={t} />
            ) : kind === "embeddings" ? (
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

function TtsModelFields({ form, onChange, t }) {
    return (
        <>
            <TextField
                id="configuration-narrator-voice"
                label={t("configurations.fields.narratorVoice")}
                value={form.narrator_voice}
                onChange={(value) => onChange("narrator_voice", value)}
            />
            <CheckboxField
                id="configuration-narrator-enabled"
                label={t("configurations.fields.narratorEnabled")}
                checked={form.narrator_enabled}
                onChange={(value) => onChange("narrator_enabled", value)}
            />
            <SelectField
                id="configuration-text-filtering"
                label={t("configurations.fields.textFiltering")}
                value={form.text_filtering}
                emptyLabel={t("configurations.fields.notSet")}
                options={["none", "standard", "html"].map((option) => ({
                    value: option,
                    label: t(`configurations.fields.textFilteringOptions.${option}`),
                }))}
                onChange={(value) => onChange("text_filtering", value)}
            />
            <SelectField
                id="configuration-text-not-inside"
                label={t("configurations.fields.textNotInside")}
                value={form.text_not_inside}
                emptyLabel={t("configurations.fields.notSet")}
                options={["character", "narrator", "silent"].map((option) => ({
                    value: option,
                    label: t(`configurations.fields.textNotInsideOptions.${option}`),
                }))}
                onChange={(value) => onChange("text_not_inside", value)}
            />
            <TextField
                id="configuration-rvc-narrator-voice"
                label={t("configurations.fields.rvcNarratorVoice")}
                value={form.rvc_narrator_voice}
                onChange={(value) => onChange("rvc_narrator_voice", value)}
            />
            <TextField
                id="configuration-rvc-narrator-pitch"
                label={t("configurations.fields.rvcNarratorPitch")}
                value={form.rvc_narrator_pitch}
                onChange={(value) => onChange("rvc_narrator_pitch", value)}
                type="number"
            />
            {ttsLanguageEngines.includes(form.engine) ? (
                <TextField
                    id="configuration-language"
                    label={t("configurations.fields.language")}
                    value={form.language}
                    onChange={(value) => onChange("language", value)}
                />
            ) : null}
            <TextField
                id="configuration-speed"
                label={t("configurations.fields.speed")}
                value={form.speed}
                onChange={(value) => onChange("speed", value)}
                type="number"
                step="0.05"
            />
            {ttsTemperatureEngines.includes(form.engine) ? (
                <TextField
                    id="configuration-temperature"
                    label={t("configurations.fields.temperature")}
                    value={form.temperature}
                    onChange={(value) => onChange("temperature", value)}
                    type="number"
                    step="0.1"
                />
            ) : null}
            {ttsRepetitionPenaltyEngines.includes(form.engine) ? (
                <TextField
                    id="configuration-repetition-penalty"
                    label={t("configurations.fields.repetitionPenalty")}
                    value={form.repetition_penalty}
                    onChange={(value) => onChange("repetition_penalty", value)}
                    type="number"
                    step="0.5"
                />
            ) : null}
            <CheckboxField
                id="configuration-output-file-timestamp"
                label={t("configurations.fields.outputFileTimestamp")}
                checked={form.output_file_timestamp}
                onChange={(value) => onChange("output_file_timestamp", value)}
            />
            <CheckboxField
                id="configuration-server-autoplay"
                label={t("configurations.fields.serverAutoplay")}
                checked={form.autoplay}
                onChange={(value) => onChange("autoplay", value)}
            />
            <TextField
                id="configuration-autoplay-volume"
                label={t("configurations.fields.autoplayVolume")}
                value={form.autoplay_volume}
                onChange={(value) => onChange("autoplay_volume", value)}
                type="number"
                step="0.1"
            />
        </>
    );
}

function ImageModelFields({ form, onChange, t }) {
    return (
        <>
            <TextField
                id="configuration-vae"
                label={t("configurations.fields.vae")}
                value={form.vae}
                onChange={(value) => onChange("vae", value)}
            />
            <TextField
                id="configuration-clip"
                label={t("configurations.fields.clip")}
                value={form.clip}
                onChange={(value) => onChange("clip", value)}
            />
            <TextField
                id="configuration-image-width"
                label={t("configurations.fields.imageWidth")}
                value={form.image_width}
                onChange={(value) => onChange("image_width", value)}
                type="number"
            />
            <TextField
                id="configuration-image-height"
                label={t("configurations.fields.imageHeight")}
                value={form.image_height}
                onChange={(value) => onChange("image_height", value)}
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
                id="configuration-steps"
                label={t("configurations.fields.steps")}
                value={form.steps}
                onChange={(value) => onChange("steps", value)}
                type="number"
            />
            <TextField
                id="configuration-cfg"
                label={t("configurations.fields.cfg")}
                value={form.cfg}
                onChange={(value) => onChange("cfg", value)}
                type="number"
            />
        </>
    );
}

function SttModelFields({ form, onChange, t }) {
    return (
        <>
            <TextField
                id="configuration-language"
                label={t("configurations.fields.language")}
                value={form.language}
                onChange={(value) => onChange("language", value)}
            />
            <CheckboxField
                id="configuration-translate"
                label={t("configurations.fields.translate")}
                checked={form.translate}
                onChange={(value) => onChange("translate", value)}
            />
            <TextField
                id="configuration-temperature"
                label={t("configurations.fields.temperature")}
                value={form.temperature}
                onChange={(value) => onChange("temperature", value)}
                type="number"
                step="0.1"
            />
            <TextField
                id="configuration-temperature-inc"
                label={t("configurations.fields.temperatureInc")}
                value={form.temperature_inc}
                onChange={(value) => onChange("temperature_inc", value)}
                type="number"
                step="0.1"
            />
            <TextField
                id="configuration-initial-prompt"
                label={t("configurations.fields.initialPrompt")}
                value={form.initial_prompt}
                onChange={(value) => onChange("initial_prompt", value)}
            />
            <CheckboxField
                id="configuration-carry-initial-prompt"
                label={t("configurations.fields.carryInitialPrompt")}
                checked={form.carry_initial_prompt}
                onChange={(value) => onChange("carry_initial_prompt", value)}
            />
        </>
    );
}

function CheckboxField({ id, label, checked, onChange }) {
    return (
        <div className="form-field inline-field modal-form-field">
            <FieldLabel htmlFor={id} label={label} />
            <input
                id={id}
                type="checkbox"
                checked={checked}
                onChange={(event) => onChange(event.target.checked)}
            />
        </div>
    );
}

function SelectField({ id, label, value, options, onChange, emptyLabel }) {
    return (
        <div className="form-field inline-field modal-form-field">
            <FieldLabel htmlFor={id} label={label} />
            <select
                id={id}
                className="single-line-input"
                value={value}
                onChange={(event) => onChange(event.target.value)}
            >
                <option value="">{emptyLabel}</option>
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        </div>
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
    const [ttsConfigs, setTtsConfigs] = useState([]);
    const [imageConfigs, setImageConfigs] = useState([]);
    const [sttConfigs, setSttConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [modalState, setModalState] = useState(null);

    const data = useMemo(
        () => ({
            connections,
            embeddings,
            llms,
            tts: ttsConfigs,
            images: imageConfigs,
            stt: sttConfigs,
        }),
        [connections, embeddings, llms, ttsConfigs, imageConfigs, sttConfigs],
    );

    async function loadConfigurations() {
        try {
            setLoading(true);
            setError(null);

            const [connectionData, embeddingData, llmData, ttsData, imageData, sttData] = await Promise.all([
                fetchConnections(),
                fetchEmbeddingConfigs(),
                fetchLlmConfigs(),
                fetchTtsConfigs(),
                fetchImageConfigs(),
                fetchSttConfigs(),
            ]);

            setConnections(connectionData);
            setEmbeddings(embeddingData);
            setLlms(llmData);
            setTtsConfigs(ttsData);
            setImageConfigs(imageData);
            setSttConfigs(sttData);
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

    // STT is global - simulations don't pick their own backend, so at most one config should
    // exist. Once one is set up, editing it is done via the row's own edit action instead.
    const sttCreateDisabled = activeTab === "stt" && sttConfigs.length > 0;

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
            } else if (kind === "tts") {
                await deleteTtsConfig(item.id);
            } else if (kind === "images") {
                await deleteImageConfig(item.id);
            } else if (kind === "stt") {
                await deleteSttConfig(item.id);
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
                {sttCreateDisabled ? null : (
                    <button
                        type="button"
                        className="primary-button"
                        onClick={() => setModalState({ kind: activeTab, item: null })}
                    >
                        {t(`configurations.actions.create.${activeTab}`)}
                    </button>
                )}
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
