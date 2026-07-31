import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAuthors } from "@/api/authors";
import { importWorld } from "@/api/worlds";

export function WorldImportModal({ onClose, onImported }) {
    const { t } = useTranslation();
    const [authors, setAuthors] = useState([]);
    const [authorId, setAuthorId] = useState("");
    const [file, setFile] = useState(null);
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

    useEffect(() => {
        fetchAuthors()
            .then((data) => {
                setAuthors(data);
                setAuthorId((current) => current || data[0]?.id || "");
            })
            .catch((err) => setError(err.message));
    }, []);

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        if (!file) {
            setError(t("worldImport.validation.fileRequired"));
            return;
        }

        if (!authorId) {
            setError(t("worldImport.validation.authorRequired"));
            return;
        }

        try {
            setSaving(true);
            await importWorld(file, authorId);
            setSaving(false);
            onImported();
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
                aria-labelledby="import-world-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="connection-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="import-world-title">{t("worldImport.title")}</h2>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("worldImport.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </div>

                    <div className="connection-create-form-content">
                        <p className="simulation-details-empty-line">{t("worldImport.description")}</p>

                        <div className="form-field inline-field">
                            <label htmlFor="world-import-author">{t("worldImport.fields.author")}</label>
                            <select
                                id="world-import-author"
                                className="single-line-input"
                                value={authorId}
                                onChange={(event) => setAuthorId(event.target.value)}
                            >
                                <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                                {authors.map((author) => (
                                    <option key={author.id} value={author.id}>
                                        {author.name}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="world-import-file">{t("worldImport.fields.file")}</label>
                            <input
                                id="world-import-file"
                                type="file"
                                accept=".zip,application/zip"
                                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                            />
                        </div>

                        {error ? <p className="form-error">{error}</p> : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("worldImport.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving}>
                            {saving ? t("worldImport.importing") : t("worldImport.submit")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
