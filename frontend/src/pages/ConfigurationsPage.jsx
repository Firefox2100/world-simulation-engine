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
    fetchAllTalkStatus,
    fetchConnections,
    fetchEmbeddingConfigs,
    fetchGlobalLlmConfigs,
    fetchImageConfigs,
    fetchLlmConfigs,
    fetchSttConfigs,
    fetchTtsConfigs,
    setEmbeddingConfigConnection,
    setGlobalLlmConfigs,
    setImageConfigConnection,
    setLlmConfigConnection,
    setSttConfigConnection,
    setTtsConfigConnection,
    stImportComponents,
    updateConnection,
    updateEmbeddingConfig,
    updateImageConfig,
    updateLlmConfig,
    updateSttConfig,
    updateTtsConfig,
} from "@/api/configurations";
import { ConnectionProviderIcon } from "@/components/ConnectionProviderIcon";

const tabs = ["connections", "embeddings", "llms", "tts", "images", "stt", "stImport"];
const llmProviders = [
    "openai",
    "ollama",
    "anthropic",
    "openrouter",
    "google_genai",
    "mistralai",
    "cohere",
    "perplexity",
    "groq",
    "deepseek",
    "xai",
    "cloudflare",
];
const connectionProviders = [...llmProviders, "alltalk", "whispercpp", "comfyui"];
const embeddingProviders = [
    "openai",
    "ollama",
    "google_genai",
    "mistralai",
    "cohere",
    "perplexity",
    "cloudflare",
];
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
const commonLlmFields = [
    { name: "temperature", type: "number", step: "0.1" },
    { name: "context_window", type: "int" },
    { name: "seed", type: "int" },
    { name: "reasoning", type: "flexible" },
    { name: "stop_tokens", type: "csv" },
];
const llmProviderFields = {
    ollama: [
        { name: "mirostat", type: "int" },
        { name: "mirostat_eta", type: "number" },
        { name: "mirostat_tau", type: "number" },
        { name: "num_predict", type: "int" },
        { name: "repeat_penalty_window", type: "int" },
        { name: "repeat_penalty", type: "number" },
        { name: "validate_model_on_init", type: "boolean" },
        { name: "num_gpu", type: "int" },
        { name: "num_thread", type: "int" },
        { name: "logprobs", type: "boolean" },
        { name: "top_logprobs", type: "int" },
        { name: "tfs_z", type: "number" },
        { name: "top_k", type: "int" },
        { name: "top_p", type: "number" },
        { name: "format", type: "jsonOrText" },
        { name: "keep_alive", type: "text" },
        { name: "client_kwargs", type: "json" },
        { name: "async_client_kwargs", type: "json" },
        { name: "sync_client_kwargs", type: "json" },
    ],
    openai: [
        { name: "model_kwargs", type: "json" },
        { name: "organization", type: "text" },
        { name: "openai_proxy", type: "text" },
        { name: "request_timeout", type: "jsonOrNumber" },
        { name: "stream_usage", type: "boolean" },
        { name: "max_retries", type: "int" },
        { name: "presence_penalty", type: "number" },
        { name: "frequency_penalty", type: "number" },
        { name: "logprobs", type: "boolean" },
        { name: "top_logprobs", type: "int" },
        { name: "logit_bias", type: "json" },
        { name: "streaming", type: "boolean" },
        { name: "n", type: "int" },
        { name: "top_p", type: "number" },
        { name: "max_completion_tokens", type: "int" },
        { name: "reasoning_effort", type: "text" },
        { name: "verbosity", type: "text" },
        { name: "tiktoken_model_name", type: "text" },
        { name: "default_headers", type: "json" },
        { name: "default_query", type: "json" },
        { name: "http_socket_options", type: "json" },
        { name: "stream_chunk_timeout", type: "number" },
        { name: "extra_body", type: "json" },
        { name: "include_response_headers", type: "boolean" },
        { name: "disabled_params", type: "json" },
        { name: "context_management", type: "json" },
        { name: "include", type: "csv" },
        { name: "service_tier", type: "text" },
        { name: "store", type: "boolean" },
        { name: "truncation", type: "text" },
        { name: "use_previous_response_id", type: "boolean" },
        { name: "use_responses_api", type: "boolean" },
    ],
    anthropic: [
        { name: "model_kwargs", type: "json" },
        { name: "max_tokens", type: "int" },
        { name: "timeout", type: "number" },
        { name: "max_retries", type: "int" },
        { name: "top_p", type: "number" },
        { name: "top_k", type: "int" },
        { name: "thinking", type: "json" },
        { name: "output_config", type: "json" },
        { name: "stream_usage", type: "boolean" },
        { name: "streaming", type: "boolean" },
        { name: "default_headers", type: "json" },
        { name: "betas", type: "csv" },
        { name: "service_tier", type: "text" },
        { name: "mcp_servers", type: "json" },
        { name: "container", type: "jsonOrText" },
        { name: "inference_geo", type: "text" },
    ],
    google_genai: [
        { name: "model_kwargs", type: "json" },
        { name: "max_output_tokens", type: "int" },
        { name: "top_p", type: "number" },
        { name: "top_k", type: "int" },
        { name: "n", type: "int" },
        { name: "max_retries", type: "int" },
        { name: "timeout", type: "number" },
        { name: "safety_settings", type: "json" },
        { name: "response_mime_type", type: "text" },
        { name: "response_schema", type: "json" },
        { name: "cached_content", type: "text" },
        { name: "thinking_budget", type: "int" },
        { name: "include_thoughts", type: "boolean" },
        { name: "transport", type: "text" },
        { name: "client_options", type: "json" },
    ],
    mistralai: [
        { name: "model_kwargs", type: "json" },
        { name: "max_tokens", type: "int" },
        { name: "top_p", type: "number" },
        { name: "random_seed", type: "int" },
        { name: "safe_mode", type: "boolean" },
        { name: "streaming", type: "boolean" },
        { name: "endpoint", type: "text" },
        { name: "timeout", type: "int" },
        { name: "max_retries", type: "int" },
        { name: "max_concurrent_requests", type: "int" },
    ],
    cohere: [
        { name: "model_kwargs", type: "json" },
        { name: "preamble", type: "text" },
        { name: "streaming", type: "boolean" },
        { name: "user_agent", type: "text" },
        { name: "timeout_seconds", type: "number" },
    ],
    groq: [
        { name: "max_tokens", type: "int" },
        { name: "reasoning_format", type: "select", options: ["parsed", "raw", "hidden"] },
        { name: "response_format", type: "json" },
        { name: "parallel_tool_calls", type: "boolean" },
    ],
    xai: [
        { name: "search_parameters", type: "json" },
    ],
    cloudflare: [
        { name: "model_kwargs", type: "json" },
        { name: "account_id", type: "text" },
        { name: "endpoint_format", type: "select", options: ["workers_ai", "openai_compatible"] },
        { name: "ai_gateway", type: "text" },
        { name: "max_tokens", type: "int" },
        { name: "top_p", type: "number" },
        { name: "top_k", type: "int" },
        { name: "streaming", type: "boolean" },
    ],
};
for (const provider of ["openrouter", "perplexity", "deepseek"]) {
    llmProviderFields[provider] = llmProviderFields.openai;
}
const llmExtraFields = Array.from(
    new Set(Object.values(llmProviderFields).flat().map((field) => field.name)),
);
const embeddingProviderFields = {
    ollama: [
        { name: "context_window", type: "int" },
        { name: "validate_model_on_init", type: "boolean" },
        { name: "client_kwargs", type: "json" },
        { name: "async_client_kwargs", type: "json" },
        { name: "sync_client_kwargs", type: "json" },
        { name: "mirostat", type: "int" },
        { name: "mirostat_eta", type: "number" },
        { name: "mirostat_tau", type: "number" },
        { name: "num_gpu", type: "int" },
        { name: "keep_alive", type: "int" },
        { name: "num_thread", type: "int" },
        { name: "repeat_last_n", type: "int" },
        { name: "repeat_penalty", type: "number" },
        { name: "temperature", type: "number" },
        { name: "stop", type: "csv" },
        { name: "tfs_z", type: "number" },
        { name: "top_k", type: "int" },
        { name: "top_p", type: "number" },
    ],
    openai: [
        { name: "deployment", type: "text" },
        { name: "api_version", type: "text" },
        { name: "openai_api_type", type: "text" },
        { name: "openai_proxy", type: "text" },
        { name: "embedding_ctx_length", type: "int" },
        { name: "organization", type: "text" },
        { name: "allowed_special", type: "flexible" },
        { name: "disallowed_special", type: "csv" },
        { name: "chunk_size", type: "int" },
        { name: "max_retries", type: "int" },
        { name: "request_timeout", type: "jsonOrNumber" },
        { name: "headers", type: "json" },
        { name: "tiktoken_enabled", type: "boolean" },
        { name: "tiktoken_model_name", type: "text" },
        { name: "show_progress_bar", type: "boolean" },
        { name: "model_kwargs", type: "json" },
        { name: "skip_empty", type: "boolean" },
        { name: "default_headers", type: "json" },
        { name: "default_query", type: "json" },
        { name: "retry_min_seconds", type: "int" },
        { name: "retry_max_seconds", type: "int" },
        { name: "check_embedding_ctx_length", type: "boolean" },
    ],
    google_genai: [
        {
            name: "task_type",
            type: "select",
            options: [
                "TASK_TYPE_UNSPECIFIED",
                "RETRIEVAL_QUERY",
                "RETRIEVAL_DOCUMENT",
                "SEMANTIC_SIMILARITY",
                "CLASSIFICATION",
                "CLUSTERING",
                "QUESTION_ANSWERING",
                "FACT_VERIFICATION",
                "CODE_RETRIEVAL_QUERY",
            ],
        },
        { name: "vertexai", type: "boolean" },
        { name: "project", type: "text" },
        { name: "location", type: "text" },
        { name: "additional_headers", type: "json" },
        { name: "client_args", type: "json" },
        { name: "api_version", type: "text" },
        { name: "request_options", type: "json" },
    ],
    mistralai: [
        { name: "endpoint", type: "text" },
        { name: "max_retries", type: "int" },
        { name: "timeout", type: "int" },
        { name: "wait_time", type: "int" },
        { name: "max_concurrent_requests", type: "int" },
    ],
    cohere: [
        { name: "truncate", type: "select", options: ["NONE", "START", "END"] },
        { name: "embedding_types", type: "csv" },
        { name: "max_retries", type: "int" },
        { name: "request_timeout", type: "number" },
        { name: "user_agent", type: "text" },
    ],
    perplexity: [
        { name: "request_timeout", type: "jsonOrNumber" },
        { name: "max_retries", type: "int" },
    ],
    cloudflare: [
        { name: "account_id", type: "text" },
        { name: "batch_size", type: "int" },
        { name: "strip_new_lines", type: "boolean" },
        { name: "api_base_url", type: "text" },
        { name: "headers", type: "json" },
    ],
};
const embeddingExtraFields = Array.from(
    new Set(Object.values(embeddingProviderFields).flat().map((field) => field.name)),
);

function cleanText(value) {
    const trimmed = String(value ?? "").trim();
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

function formatFormValue(value) {
    if (value === null || value === undefined) {
        return "";
    }

    if (typeof value === "object") {
        return JSON.stringify(value, null, 2);
    }

    return String(value);
}

function parseJsonOrNull(value) {
    const cleaned = cleanText(value);
    if (!cleaned) {
        return null;
    }

    return JSON.parse(cleaned);
}

function parseJsonOrText(value) {
    const cleaned = cleanText(value);
    if (!cleaned) {
        return null;
    }

    try {
        return JSON.parse(cleaned);
    } catch {
        return cleaned;
    }
}

function parseFlexibleValue(value) {
    const cleaned = cleanText(value);
    if (!cleaned) {
        return null;
    }

    if (cleaned === "true") {
        return true;
    }
    if (cleaned === "false") {
        return false;
    }

    try {
        return JSON.parse(cleaned);
    } catch {
        return cleaned;
    }
}

function parseCsvOrNull(value) {
    return cleanText(value)?.split(",").map((token) => token.trim()).filter(Boolean) ?? null;
}

function omitNullishEntries(payload) {
    return Object.fromEntries(
        Object.entries(payload).filter(([, value]) => value !== null && value !== undefined),
    );
}

function parseLlmFieldValue(field, form) {
    const value = form[field.name];
    if (field.type === "int") {
        return numberOrNull(value, Number.parseInt);
    }
    if (field.type === "number") {
        return numberOrNull(value);
    }
    if (field.type === "boolean") {
        return value === "" ? null : Boolean(value);
    }
    if (field.type === "json") {
        return parseJsonOrNull(value);
    }
    if (field.type === "jsonOrText") {
        return parseJsonOrText(value);
    }
    if (field.type === "jsonOrNumber") {
        const parsedJson = parseJsonOrText(value);
        if (typeof parsedJson === "string") {
            return numberOrNull(parsedJson);
        }
        return parsedJson;
    }
    if (field.type === "flexible") {
        return parseFlexibleValue(value);
    }
    if (field.type === "csv") {
        return parseCsvOrNull(value);
    }

    return cleanText(value);
}

function humanizeFieldName(field) {
    return field
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fieldLabel(t, field) {
    return t(`configurations.fields.${field}`, { defaultValue: humanizeFieldName(field) });
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
        const embeddingState = {
            provider: item ? inferEmbeddingProvider(item) : "",
            connection_id: item?.connection?.id ?? "",
            name: item?.name ?? "",
            model: item?.model ?? "",
            dimension: item?.dimension == null ? "" : String(item.dimension),
        };

        for (const field of embeddingExtraFields) {
            embeddingState[field] = typeof item?.[field] === "boolean"
                ? item[field]
                : formatFormValue(item?.[field]);
        }

        return embeddingState;
    }

    if (kind === "tts") {
        return {
            name: item?.name ?? "",
            // engine/model and the *_capable flags are read from the live AllTalk server, not
            // picked by the user - seeded here from the existing config so the read-only display
            // isn't blank while the live status is (re)loading, but the fetch is authoritative.
            engine: item?.engine ?? "",
            connection_id: item?.connection?.id ?? "",
            model: item?.model ?? "",
            languages_capable: false,
            temperature_capable: false,
            repetition_penalty_capable: false,
            generation_speed_capable: false,
            narrator_enabled: item?.narrator_enabled ?? false,
            text_filtering: item?.text_filtering ?? "",
            text_not_inside: item?.text_not_inside ?? "",
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

    const llmState = {
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

    for (const field of llmExtraFields) {
        if (!(field in llmState)) {
            llmState[field] = typeof item?.[field] === "boolean"
                ? item[field]
                : formatFormValue(item?.[field]);
        }
    }

    return llmState;
}

function buildPayload(kind, form) {
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

        for (const field of embeddingProviderFields[form.provider] ?? []) {
            payload[field.name] = parseLlmFieldValue(field, form);
        }

        return omitNullishEntries(payload);
    }

    if (kind === "tts") {
        // engine and model are never chosen here - they mirror whatever AllTalk currently has
        // loaded (fetched live from the connection), since this app never alters AllTalk's own
        // engine/model configuration. No voice lives here either - narrator voice is configured
        // per-simulation (TtsGenerationConfig) and each character configures its own voice.
        const payload = {
            name: cleanText(form.name),
            model: cleanText(form.model),
            narrator_enabled: form.narrator_enabled,
            text_filtering: form.text_filtering || null,
            text_not_inside: form.text_not_inside || null,
            output_file_timestamp: form.output_file_timestamp,
            autoplay: form.autoplay,
            autoplay_volume: numberOrNull(form.autoplay_volume),
        };

        if (form.generation_speed_capable) {
            payload.speed = numberOrNull(form.speed);
        }
        if (form.languages_capable) {
            payload.language = cleanText(form.language);
        }
        if (form.temperature_capable) {
            payload.temperature = numberOrNull(form.temperature);
        }
        if (form.repetition_penalty_capable) {
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
        temperature: parseLlmFieldValue(commonLlmFields[0], form),
        context_window: parseLlmFieldValue(commonLlmFields[1], form),
        seed: parseLlmFieldValue(commonLlmFields[2], form),
        reasoning: parseLlmFieldValue(commonLlmFields[3], form),
        stop_tokens: parseLlmFieldValue(commonLlmFields[4], form),
    };

    for (const field of llmProviderFields[form.provider] ?? []) {
        payload[field.name] = parseLlmFieldValue(field, form);
    }

    return omitNullishEntries(payload);
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

    if (kind === "tts") {
        // form.engine is only ever set once the live AllTalk status has been fetched for the
        // selected connection, so this also blocks submitting before that resolves.
        return hasValue(form.connection_id) && hasValue(form.engine);
    }

    if (kind === "images" || kind === "stt") {
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
        return item.name || item.model || item.engine;
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
            item.model,
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
    const [allTalkStatus, setAllTalkStatus] = useState(null);
    const [allTalkStatusLoading, setAllTalkStatusLoading] = useState(false);
    const [allTalkStatusError, setAllTalkStatusError] = useState(null);
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

    // AllTalk's own engine/model config is authoritative and never altered by this app, so the
    // TTS editor mirrors it live from whichever connection is selected instead of letting the
    // user pick an engine/model or type in voices freehand.
    useEffect(() => {
        if (kind !== "tts" || !form.connection_id) {
            return undefined;
        }

        let cancelled = false;

        async function loadStatus() {
            try {
                setAllTalkStatusLoading(true);
                setAllTalkStatusError(null);
                const status = await fetchAllTalkStatus(form.connection_id);
                if (cancelled) {
                    return;
                }

                setAllTalkStatus(status);
                setForm((current) => ({
                    ...current,
                    engine: status.engine,
                    model: status.model ?? "",
                    languages_capable: status.languages_capable,
                    temperature_capable: status.temperature_capable,
                    repetition_penalty_capable: status.repetition_penalty_capable,
                    generation_speed_capable: status.generation_speed_capable,
                }));
            } catch (err) {
                if (!cancelled) {
                    setAllTalkStatus(null);
                    setAllTalkStatusError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setAllTalkStatusLoading(false);
                }
            }
        }

        loadStatus();

        return () => {
            cancelled = true;
        };
    }, [kind, form.connection_id]);

    function updateField(field, value) {
        setForm((current) => {
            const next = { ...current, [field]: value };

            // The provider/type is no longer picked directly - it's implied by whichever
            // connection is selected, since a connection already carries that information.
            if (field === "connection_id" && kind !== "connections" && kind !== "tts") {
                const selectedConnection = connections.find((connection) => connection.id === value);
                next.provider = selectedConnection?.type ?? "";
            }

            // Switching connections invalidates whatever engine/model/voices were resolved for
            // the previous one - clear them so stale data isn't submitted while the new
            // connection's live status is still loading.
            if (field === "connection_id" && kind === "tts") {
                next.engine = "";
                next.model = "";
            }

            return next;
        });
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        try {
            setSaving(true);
            const payload = buildPayload(kind, form);

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
                            allTalkStatus={allTalkStatus}
                            allTalkStatusLoading={allTalkStatusLoading}
                            allTalkStatusError={allTalkStatusError}
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

function ConfigurationFields({
    kind,
    editing,
    form,
    connections,
    onChange,
    allTalkStatus,
    allTalkStatusLoading,
    allTalkStatusError,
}) {
    const { t } = useTranslation();
    const showProviderSelect = kind === "connections";

    return (
        <>
            {showProviderSelect ? (
                <div className="form-field inline-field modal-form-field">
                    <FieldLabel htmlFor="configuration-provider" label={t("configurations.fields.provider")} required />
                    <select
                        id="configuration-provider"
                        className="single-line-input"
                        value={form.type}
                        disabled={editing}
                        onChange={(event) => onChange("type", event.target.value)}
                    >
                        {connectionProviders.map((option) => (
                            <option key={option} value={option}>
                                {t(`configurations.providers.${option}`)}
                            </option>
                        ))}
                    </select>
                </div>
            ) : null}

            {kind !== "images" && kind !== "stt" ? (
                <TextField
                    id="configuration-name"
                    label={t("configurations.fields.name")}
                    value={form.name}
                    onChange={(value) => onChange("name", value)}
                    required={kind !== "embeddings" && kind !== "tts"}
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
                <ModelFields
                    kind={kind}
                    editing={editing}
                    form={form}
                    connections={connections}
                    onChange={onChange}
                    t={t}
                    allTalkStatus={allTalkStatus}
                    allTalkStatusLoading={allTalkStatusLoading}
                    allTalkStatusError={allTalkStatusError}
                />
            )}
        </>
    );
}

function ModelFields({
    kind,
    editing,
    form,
    connections,
    onChange,
    t,
    allTalkStatus,
    allTalkStatusLoading,
    allTalkStatusError,
}) {
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
                    : connections.filter((connection) => (
                        kind === "embeddings"
                            ? embeddingProviders.includes(connection.type)
                            : llmProviders.includes(connection.type)
                    ));

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

            {kind !== "tts" ? (
                <TextField
                    id="configuration-model"
                    label={t("configurations.fields.model")}
                    value={form.model}
                    onChange={(value) => onChange("model", value)}
                    required={kind !== "images" && kind !== "stt"}
                />
            ) : null}

            {kind === "tts" ? (
                <TtsModelFields
                    form={form}
                    onChange={onChange}
                    t={t}
                    status={allTalkStatus}
                    statusLoading={allTalkStatusLoading}
                    statusError={allTalkStatusError}
                    connectionSelected={Boolean(form.connection_id)}
                />
            ) : kind === "images" ? (
                <ImageModelFields form={form} onChange={onChange} t={t} />
            ) : kind === "stt" ? (
                <SttModelFields form={form} onChange={onChange} t={t} />
            ) : kind === "embeddings" ? (
                <EmbeddingModelFields form={form} onChange={onChange} t={t} />
            ) : (
                <LlmModelFields form={form} onChange={onChange} t={t} />
            )}
        </>
    );
}

function EmbeddingModelFields({ form, onChange, t }) {
    return (
        <>
            <TextField
                id="configuration-dimension"
                label={t("configurations.fields.dimension")}
                value={form.dimension}
                onChange={(value) => onChange("dimension", value)}
                type="number"
            />
            {(embeddingProviderFields[form.provider] ?? []).map((field) => (
                <LlmConfigField
                    key={field.name}
                    field={field}
                    form={form}
                    onChange={onChange}
                    t={t}
                />
            ))}
        </>
    );
}

function LlmModelFields({ form, onChange, t }) {
    return (
        <>
            {commonLlmFields.map((field) => (
                <LlmConfigField
                    key={field.name}
                    field={field}
                    form={form}
                    onChange={onChange}
                    t={t}
                />
            ))}
            {(llmProviderFields[form.provider] ?? []).map((field) => (
                <LlmConfigField
                    key={field.name}
                    field={field}
                    form={form}
                    onChange={onChange}
                    t={t}
                />
            ))}
        </>
    );
}

function LlmConfigField({ field, form, onChange, t }) {
    const label = field.name === "stop_tokens"
        ? t("configurations.fields.stopTokens")
        : fieldLabel(t, field.name);
    const id = `configuration-${field.name}`;

    if (field.type === "boolean") {
        return (
            <CheckboxField
                id={id}
                label={label}
                checked={Boolean(form[field.name])}
                onChange={(value) => onChange(field.name, value)}
            />
        );
    }

    if (field.type === "select") {
        return (
            <SelectField
                id={id}
                label={label}
                value={form[field.name]}
                emptyLabel={t("configurations.fields.notSet")}
                options={field.options.map((option) => ({
                    value: option,
                    label: t(`configurations.fieldOptions.${field.name}.${option}`, { defaultValue: option }),
                }))}
                onChange={(value) => onChange(field.name, value)}
            />
        );
    }

    if (field.type === "json" || field.type === "jsonOrText") {
        return (
            <TextAreaField
                id={id}
                label={label}
                value={form[field.name]}
                onChange={(value) => onChange(field.name, value)}
            />
        );
    }

    return (
        <TextField
            id={id}
            label={label}
            value={form[field.name]}
            onChange={(value) => onChange(field.name, value)}
            type={field.type === "number" || field.type === "int" ? "number" : "text"}
            step={field.step ?? (field.type === "number" ? "0.1" : undefined)}
        />
    );
}

function TtsModelFields({ form, onChange, t, status, statusLoading, statusError, connectionSelected }) {
    if (!connectionSelected) {
        return <p className="connection-empty-text">{t("configurations.fields.ttsSelectConnectionFirst")}</p>;
    }

    if (statusLoading && !status) {
        return <p className="status-text">{t("configurations.fields.ttsStatusLoading")}</p>;
    }

    if (statusError) {
        return (
            <p className="status-text error-text">
                {t("configurations.fields.ttsStatusError", { error: statusError })}
            </p>
        );
    }

    if (!status) {
        return null;
    }

    return (
        <>
            <div className="form-field inline-field modal-form-field">
                <FieldLabel htmlFor="configuration-tts-engine" label={t("configurations.fields.engine")} />
                <input
                    id="configuration-tts-engine"
                    className="single-line-input"
                    value={t(`configurations.providers.${status.engine}`, { defaultValue: status.engine })}
                    disabled
                />
            </div>
            <div className="form-field inline-field modal-form-field">
                <FieldLabel htmlFor="configuration-tts-model" label={t("configurations.fields.model")} />
                <input
                    id="configuration-tts-model"
                    className="single-line-input"
                    value={status.model ?? ""}
                    disabled
                />
            </div>
            <p className="connection-empty-text">{t("configurations.fields.ttsEngineModelHint")}</p>

            <CheckboxField
                id="configuration-narrator-enabled"
                label={t("configurations.fields.narratorEnabled")}
                checked={form.narrator_enabled}
                onChange={(value) => onChange("narrator_enabled", value)}
            />
            <p className="connection-empty-text">{t("configurations.fields.ttsNarratorVoiceHint")}</p>
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
            {status.languages_capable ? (
                <TextField
                    id="configuration-language"
                    label={t("configurations.fields.language")}
                    value={form.language}
                    onChange={(value) => onChange("language", value)}
                />
            ) : null}
            {status.generation_speed_capable ? (
                <TextField
                    id="configuration-speed"
                    label={t("configurations.fields.speed")}
                    value={form.speed}
                    onChange={(value) => onChange("speed", value)}
                    type="number"
                    step="0.05"
                />
            ) : null}
            {status.temperature_capable ? (
                <TextField
                    id="configuration-temperature"
                    label={t("configurations.fields.temperature")}
                    value={form.temperature}
                    onChange={(value) => onChange("temperature", value)}
                    type="number"
                    step="0.1"
                />
            ) : null}
            {status.repetition_penalty_capable ? (
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

function SelectField({ id, label, value, options, onChange, emptyLabel, disabled = false, required = false }) {
    return (
        <div className="form-field inline-field modal-form-field">
            <FieldLabel htmlFor={id} label={label} required={required} />
            <select
                id={id}
                className="single-line-input"
                value={value}
                disabled={disabled}
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

function TextField({ id, label, value, onChange, type = "text", required = false, step, disabled = false }) {
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
                disabled={disabled}
                onChange={(event) => onChange(event.target.value)}
            />
        </div>
    );
}

function TextAreaField({ id, label, value, onChange, required = false, disabled = false }) {
    return (
        <div className="form-field inline-field modal-form-field">
            <FieldLabel htmlFor={id} label={label} required={required} />
            <textarea
                id={id}
                className="multi-line-input short-textarea"
                value={value}
                required={required}
                disabled={disabled}
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

function SillyTavernExtractorConfig({ llmConfigs }) {
    const { t } = useTranslation();
    const [assignments, setAssignments] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState(null);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        let cancelled = false;

        fetchGlobalLlmConfigs(stImportComponents)
            .then((rows) => {
                if (cancelled) {
                    return;
                }

                const map = {};
                rows.forEach((row) => {
                    map[row.component] = row.config.id;
                });
                setAssignments(map);
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(err.message);
                }
            })
            .finally(() => {
                if (!cancelled) {
                    setLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    function updateAssignment(component, configId) {
        setSaved(false);
        setAssignments((current) => ({ ...current, [component]: configId }));
    }

    async function handleSave() {
        setSaving(true);
        setSaveError(null);
        setSaved(false);

        try {
            await setGlobalLlmConfigs(
                stImportComponents.map((component) => ({
                    component,
                    config_id: assignments[component] || null,
                })),
            );
            setSaved(true);
        } catch (err) {
            setSaveError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("configurations.stImport.loading")}</p>;
    }

    if (error) {
        return <p className="status-text error-text">{t("configurations.stImport.error", { error })}</p>;
    }

    return (
        <div className="st-import-config">
            <p className="st-import-config-hint">{t("configurations.stImport.hint")}</p>
            <div className="world-editor-config-matrix st-import-config-matrix">
                <div className="world-editor-config-matrix-header">
                    <span>{t("worldCreate.newEditor.fields.component")}</span>
                    <span>{t("worldCreate.newEditor.fields.llmConfig")}</span>
                </div>
                {stImportComponents.map((component) => (
                    <div className="world-editor-config-row" key={component}>
                        <div className="world-editor-component-name">
                            {t(`configurations.stImport.components.${component}`)}
                        </div>
                        <select
                            className="single-line-input"
                            value={assignments[component] ?? ""}
                            onChange={(event) => updateAssignment(component, event.target.value)}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {llmConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {config.name || config.model || config.id}
                                </option>
                            ))}
                        </select>
                    </div>
                ))}
            </div>
            {saveError ? (
                <p className="status-text error-text">{t("configurations.stImport.saveError", { error: saveError })}</p>
            ) : null}
            <div className="st-import-config-actions">
                <button type="button" className="primary-button" onClick={handleSave} disabled={saving}>
                    {saving ? t("configurations.stImport.saving") : t("configurations.stImport.save")}
                </button>
                {saved ? <span className="st-import-config-saved">{t("configurations.stImport.saved")}</span> : null}
            </div>
        </div>
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
    // The ST-import tab is an assignment matrix (existing chat configs -> components), not a
    // creatable record kind - it has no create/modal flow at all.
    const hideCreateButton = sttCreateDisabled || activeTab === "stImport";

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
                {hideCreateButton ? null : (
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
            ) : activeTab === "stImport" ? (
                <SillyTavernExtractorConfig llmConfigs={llms} />
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
