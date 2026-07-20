import { startTransition, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
    createPrompt,
    deletePrompt,
    fetchBuiltinPromptMessages,
    fetchPromptMessages,
    fetchPrompts,
    promptLabel,
    promptLanguages,
    promptUsages,
    updatePrompt,
} from "@/api/prompts";

const components = [...new Set(promptUsages.map((usage) => usage.component))];

function makeFormState(prompt = null) {
    return {
        title: prompt?.title ?? "",
        filename: prompt?.filename ?? "",
        language: prompt?.language ?? "en",
        prompt_name: prompt?.prompt_name ?? promptUsages[0].prompt_name,
        component: prompt?.component ?? promptUsages[0].component,
        messages: "[]",
    };
}

function parseMessages(messages) {
    const parsed = JSON.parse(messages);
    if (!Array.isArray(parsed)) {
        throw new Error("Prompt JSON must be an array.");
    }

    return parsed;
}

function buildPromptPayload(form) {
    return {
        title: form.title.trim() || null,
        filename: form.filename.trim() || null,
        language: form.language,
        prompt_name: form.prompt_name,
        component: form.component || null,
        messages: parseMessages(form.messages),
    };
}

function PromptRow({ prompt, onEdit, onDelete }) {
    const { t } = useTranslation();

    return (
        <article className="configuration-row">
            <div className="connection-tile-main">
                <div className="connection-icon-frame" aria-hidden="true">
                    <span className="connection-provider-fallback">P</span>
                </div>
                <div className="configuration-row-copy">
                    <div className="connection-name" title={promptLabel(prompt)}>
                        {promptLabel(prompt)}
                    </div>
                    <div className="configuration-row-details">
                        {[
                            t(`prompts.usages.${prompt.prompt_name}`, { defaultValue: prompt.prompt_name }),
                            t(`prompts.languages.${prompt.language}`, { defaultValue: prompt.language }),
                            prompt.component
                                ? t(`worldCreate.newEditor.components.${prompt.component}`, { defaultValue: prompt.component })
                                : null,
                        ].filter(Boolean).join(" · ")}
                    </div>
                </div>
            </div>

            <div className="connection-actions">
                <button type="button" className="connection-action-button" onClick={() => onEdit(prompt)}>
                    {t("prompts.actions.edit")}
                </button>
                <button type="button" className="connection-action-button danger" onClick={() => onDelete(prompt)}>
                    {t("prompts.actions.delete")}
                </button>
            </div>
        </article>
    );
}

function PromptModal({ prompt = null, onClose, onSaved }) {
    const { t } = useTranslation();
    const editing = Boolean(prompt);
    const [form, setForm] = useState(() => makeFormState(prompt));
    const [loading, setLoading] = useState(editing);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const formValid = form.prompt_name && form.language && form.messages.trim();

    const matchingUsages = useMemo(
        () => promptUsages.filter((usage) => usage.component === form.component),
        [form.component],
    );

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    useEffect(() => {
        let cancelled = false;

        async function loadMessages() {
            if (!prompt) {
                return;
            }

            try {
                setLoading(true);
                const messages = await fetchPromptMessages(prompt.id);
                if (!cancelled) {
                    setForm((current) => ({
                        ...current,
                        messages: JSON.stringify(messages, null, 2),
                    }));
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadMessages();

        return () => {
            cancelled = true;
        };
    }, [prompt]);

    function updateField(field, value) {
        setForm((current) => {
            const next = { ...current, [field]: value };
            if (field === "component") {
                const firstUsage = promptUsages.find((usage) => usage.component === value);
                next.prompt_name = firstUsage?.prompt_name ?? current.prompt_name;
            }
            return next;
        });
    }

    async function loadBuiltin() {
        setError(null);
        try {
            const messages = await fetchBuiltinPromptMessages(form.language, form.prompt_name);
            setForm((current) => ({
                ...current,
                messages: JSON.stringify(messages, null, 2),
            }));
        } catch (err) {
            setError(err.message);
        }
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        try {
            setSaving(true);
            const payload = buildPromptPayload(form);
            editing ? await updatePrompt(prompt.id, payload) : await createPrompt(payload);
            onSaved();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal-panel compact-modal-panel prompt-modal-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="prompt-modal-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="connection-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="prompt-modal-title">
                            {editing ? t("prompts.modal.editTitle") : t("prompts.modal.createTitle")}
                        </h2>
                        <button type="button" className="icon-button" aria-label={t("prompts.modal.close")} onClick={onClose}>
                            ×
                        </button>
                    </div>

                    <div className="connection-create-form-content">
                        {loading ? <p className="status-text">{t("prompts.modal.loading")}</p> : null}
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.title")} required={false} />
                            <input className="single-line-input" value={form.title} onChange={(event) => updateField("title", event.target.value)} />
                        </div>
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.language")} required />
                            <select className="single-line-input" value={form.language} onChange={(event) => updateField("language", event.target.value)}>
                                {promptLanguages.map((language) => (
                                    <option key={language} value={language}>
                                        {t(`prompts.languages.${language}`, { defaultValue: language })}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.component")} required={false} />
                            <select className="single-line-input" value={form.component} onChange={(event) => updateField("component", event.target.value)}>
                                {components.map((component) => (
                                    <option key={component} value={component}>
                                        {t(`worldCreate.newEditor.components.${component}`, { defaultValue: component })}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.usage")} required />
                            <select className="single-line-input" value={form.prompt_name} onChange={(event) => updateField("prompt_name", event.target.value)}>
                                {matchingUsages.map((usage) => (
                                    <option key={usage.prompt_name} value={usage.prompt_name}>
                                        {t(`prompts.usages.${usage.prompt_name}`, { defaultValue: usage.prompt_name })}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.filename")} required={false} />
                            <input className="single-line-input" value={form.filename} onChange={(event) => updateField("filename", event.target.value)} />
                        </div>
                        <div className="modal-actions inline-actions">
                            <button type="button" className="secondary-button" onClick={loadBuiltin}>
                                {t("prompts.modal.loadBuiltin")}
                            </button>
                        </div>
                        <label className="form-field inline-field modal-form-field">
                            <FieldLabel label={t("prompts.fields.messages")} required />
                            <textarea
                                className="multi-line-input prompt-json-editor"
                                value={form.messages}
                                required
                                spellCheck={false}
                                onChange={(event) => updateField("messages", event.target.value)}
                            />
                        </label>
                        {error ? <p className="form-error">{t("prompts.modal.error", { error })}</p> : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("prompts.modal.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving || loading || !formValid}>
                            {saving
                                ? t("prompts.modal.saving")
                                : editing
                                  ? t("prompts.modal.update")
                                  : t("prompts.modal.submit")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function FieldLabel({ label, required = false }) {
    const { t } = useTranslation();

    return (
        <span className="world-editor-field-label">
            <span>{label}</span>
            <span className={`world-editor-required-badge${required ? " required" : ""}`}>
                {required ? t("worldCreate.newEditor.required") : t("worldCreate.newEditor.optional")}
            </span>
        </span>
    );
}

export function PromptsPage() {
    const { t } = useTranslation();
    const [prompts, setPrompts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [modalPrompt, setModalPrompt] = useState(null);
    const [createModalOpen, setCreateModalOpen] = useState(false);

    async function loadPrompts() {
        try {
            setLoading(true);
            setError(null);
            setPrompts(await fetchPrompts());
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        startTransition(() => {
            loadPrompts();
        });
    }, []);

    async function handleSaved() {
        setCreateModalOpen(false);
        setModalPrompt(null);
        await loadPrompts();
    }

    async function handleDelete(prompt) {
        if (!window.confirm(t("prompts.confirmDelete", { name: promptLabel(prompt) }))) {
            return;
        }

        try {
            setActionError(null);
            await deletePrompt(prompt.id);
            await loadPrompts();
        } catch (err) {
            setActionError(err.message);
        }
    }

    return (
        <section>
            <div className="page-heading page-heading-with-action">
                <div>
                    <h1>{t("prompts.title")}</h1>
                    <p>{t("prompts.subtitle")}</p>
                </div>
                <button type="button" className="primary-button" onClick={() => setCreateModalOpen(true)}>
                    {t("prompts.actions.create")}
                </button>
            </div>

            {actionError ? <p className="status-text error-text">{t("prompts.actionError", { error: actionError })}</p> : null}

            {loading ? (
                <p className="status-text">{t("prompts.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("prompts.error", { error })}</p>
            ) : prompts.length === 0 ? (
                <p className="connection-empty-text">{t("prompts.empty")}</p>
            ) : (
                <div className="configuration-list">
                    {prompts.map((prompt) => (
                        <PromptRow key={prompt.id} prompt={prompt} onEdit={setModalPrompt} onDelete={handleDelete} />
                    ))}
                </div>
            )}

            {createModalOpen ? <PromptModal onClose={() => setCreateModalOpen(false)} onSaved={handleSaved} /> : null}
            {modalPrompt ? <PromptModal prompt={modalPrompt} onClose={() => setModalPrompt(null)} onSaved={handleSaved} /> : null}
        </section>
    );
}
