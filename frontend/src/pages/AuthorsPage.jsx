import { startTransition, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { createAuthor, deleteAuthor, fetchAuthors, updateAuthor } from "@/api/authors";

function cleanOptionalText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function buildAuthorPayload(form) {
    return {
        name: form.name.trim(),
        url: cleanOptionalText(form.url),
    };
}

function isAuthorFormValid(form) {
    return form.name.trim().length > 0;
}

function AuthorRow({ author, onEdit, onDelete }) {
    const { t } = useTranslation();

    return (
        <article className="configuration-row">
            <div className="connection-tile-main">
                <div className="connection-icon-frame" aria-hidden="true">
                    <span className="connection-provider-fallback">A</span>
                </div>
                <div className="configuration-row-copy">
                    <div className="connection-name" title={author.name}>
                        {author.name}
                    </div>
                    <div className="configuration-row-details">
                        {author.url || t("authors.noUrl")}
                    </div>
                </div>
            </div>

            <div className="connection-actions">
                <button type="button" className="connection-action-button" onClick={() => onEdit(author)}>
                    {t("authors.actions.edit")}
                </button>
                <button
                    type="button"
                    className="connection-action-button danger"
                    onClick={() => onDelete(author)}
                >
                    {t("authors.actions.delete")}
                </button>
            </div>
        </article>
    );
}

function AuthorModal({ author = null, onClose, onSaved }) {
    const { t } = useTranslation();
    const editing = Boolean(author);
    const [form, setForm] = useState({
        name: author?.name ?? "",
        url: author?.url ?? "",
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const formValid = isAuthorFormValid(form);

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
        setForm((current) => ({ ...current, [field]: value }));
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        try {
            setSaving(true);
            const payload = buildAuthorPayload(form);
            editing ? await updateAuthor(author.id, payload) : await createAuthor(payload);
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
                aria-labelledby="author-modal-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="connection-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="author-modal-title">
                            {editing ? t("authors.modal.editTitle") : t("authors.modal.createTitle")}
                        </h2>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("authors.modal.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </div>

                    <div className="connection-create-form-content">
                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel htmlFor="author-name" label={t("authors.fields.name")} required />
                            <input
                                id="author-name"
                                className="single-line-input"
                                value={form.name}
                                onChange={(event) => updateField("name", event.target.value)}
                                required
                            />
                        </div>

                        <div className="form-field inline-field modal-form-field">
                            <FieldLabel htmlFor="author-url" label={t("authors.fields.url")} />
                            <input
                                id="author-url"
                                className="single-line-input"
                                value={form.url}
                                onChange={(event) => updateField("url", event.target.value)}
                            />
                        </div>

                        {error ? <p className="form-error">{t("authors.modal.error", { error })}</p> : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("authors.modal.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving || !formValid}>
                            {saving
                                ? t("authors.modal.saving")
                                : editing
                                  ? t("authors.modal.update")
                                  : t("authors.modal.submit")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function FieldLabel({ htmlFor, label, required = false }) {
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

export function AuthorsPage() {
    const { t } = useTranslation();
    const [authors, setAuthors] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [modalAuthor, setModalAuthor] = useState(null);
    const [createModalOpen, setCreateModalOpen] = useState(false);

    async function loadAuthors() {
        try {
            setLoading(true);
            setError(null);
            setAuthors(await fetchAuthors());
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        startTransition(() => {
            loadAuthors();
        });
    }, []);

    async function handleSaved() {
        setCreateModalOpen(false);
        setModalAuthor(null);
        await loadAuthors();
    }

    async function handleDelete(author) {
        if (!window.confirm(t("authors.confirmDelete", { name: author.name }))) {
            return;
        }

        try {
            setActionError(null);
            await deleteAuthor(author.id);
            await loadAuthors();
        } catch (err) {
            setActionError(err.message);
        }
    }

    return (
        <section>
            <div className="page-heading page-heading-with-action">
                <div>
                    <h1>{t("authors.title")}</h1>
                    <p>{t("authors.subtitle")}</p>
                </div>
                <button type="button" className="primary-button" onClick={() => setCreateModalOpen(true)}>
                    {t("authors.actions.create")}
                </button>
            </div>

            {actionError ? (
                <p className="status-text error-text">{t("authors.actionError", { error: actionError })}</p>
            ) : null}

            {loading ? (
                <p className="status-text">{t("authors.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("authors.error", { error })}</p>
            ) : authors.length === 0 ? (
                <p className="connection-empty-text">{t("authors.empty")}</p>
            ) : (
                <div className="configuration-list">
                    {authors.map((author) => (
                        <AuthorRow
                            key={author.id ?? author.name}
                            author={author}
                            onEdit={setModalAuthor}
                            onDelete={handleDelete}
                        />
                    ))}
                </div>
            )}

            {createModalOpen ? (
                <AuthorModal onClose={() => setCreateModalOpen(false)} onSaved={handleSaved} />
            ) : null}

            {modalAuthor ? (
                <AuthorModal
                    author={modalAuthor}
                    onClose={() => setModalAuthor(null)}
                    onSaved={handleSaved}
                />
            ) : null}
        </section>
    );
}
