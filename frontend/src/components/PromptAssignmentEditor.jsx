import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
    fetchPrompts,
    fetchSimulationPromptAssignments,
    fetchWorldPromptAssignments,
    promptAssignmentKey,
    promptLabel,
    promptLanguages,
    promptUsages,
    setSimulationPromptAssignments,
    setWorldPromptAssignments,
} from "@/api/prompts";

function assignmentMapFromList(assignments) {
    return assignments.reduce((result, assignment) => {
        result[promptAssignmentKey(assignment)] = assignment.prompt?.id ?? "";
        return result;
    }, {});
}

function assignmentRows(language) {
    const languages = language ? [language] : promptLanguages;
    return languages.flatMap((entryLanguage) =>
        promptUsages.map((usage) => ({
            ...usage,
            language: entryLanguage,
        })),
    );
}

export function PromptAssignmentEditor({ sourceType, sourceId, language = null }) {
    const { t } = useTranslation();
    const [prompts, setPrompts] = useState([]);
    const [assignmentsByKey, setAssignmentsByKey] = useState({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [notice, setNotice] = useState(null);
    const rows = useMemo(() => assignmentRows(language), [language]);

    useEffect(() => {
        let cancelled = false;

        async function loadPromptAssignments() {
            if (!sourceId) {
                setLoading(false);
                return;
            }

            setLoading(true);
            setError(null);
            setNotice(null);

            try {
                const [promptData, assignmentData] = await Promise.all([
                    fetchPrompts(language ? { language } : {}),
                    sourceType === "world"
                        ? fetchWorldPromptAssignments(sourceId)
                        : fetchSimulationPromptAssignments(sourceId),
                ]);

                if (!cancelled) {
                    setPrompts(promptData);
                    setAssignmentsByKey(assignmentMapFromList(assignmentData));
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

        loadPromptAssignments();

        return () => {
            cancelled = true;
        };
    }, [language, sourceId, sourceType]);

    function updateAssignment(row, mediaId) {
        setAssignmentsByKey((current) => ({
            ...current,
            [promptAssignmentKey(row)]: mediaId,
        }));
    }

    async function saveAssignments() {
        setError(null);
        setNotice(null);

        try {
            setSaving(true);
            const assignments = rows.map((row) => ({
                prompt_name: row.prompt_name,
                language: row.language,
                component: row.component,
                media_id: assignmentsByKey[promptAssignmentKey(row)] || null,
            }));

            const saved = sourceType === "world"
                ? await setWorldPromptAssignments(sourceId, assignments)
                : await setSimulationPromptAssignments(sourceId, assignments);
            setAssignmentsByKey(assignmentMapFromList(saved));
            setNotice(t("prompts.assignment.saved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (!sourceId) {
        return <p className="status-text">{t("prompts.assignment.saveSourceFirst")}</p>;
    }

    if (loading) {
        return <p className="status-text">{t("prompts.assignment.loading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? <p className="form-error">{t("prompts.assignment.error", { error })}</p> : null}
            <div className="world-editor-config-matrix prompt-assignment-matrix">
                <div className="world-editor-config-matrix-header">
                    <span>{t("prompts.fields.component")}</span>
                    <span>{t("prompts.fields.usage")}</span>
                    <span>{t("prompts.fields.language")}</span>
                    <span>{t("prompts.fields.prompt")}</span>
                </div>
                {rows.map((row) => {
                    const rowPrompts = prompts.filter(
                        (prompt) =>
                            prompt.language === row.language
                            && prompt.prompt_name === row.prompt_name
                            && (prompt.component ?? "") === (row.component ?? ""),
                    );
                    return (
                        <div className="world-editor-config-row" key={promptAssignmentKey(row)}>
                            <div className="world-editor-component-name">
                                {t(`worldCreate.newEditor.components.${row.component}`, { defaultValue: row.component })}
                            </div>
                            <div className="world-editor-component-name">
                                {t(`prompts.usages.${row.prompt_name}`, { defaultValue: row.prompt_name })}
                            </div>
                            <div className="world-editor-component-name">
                                {t(`prompts.languages.${row.language}`, { defaultValue: row.language })}
                            </div>
                            <select
                                className="single-line-input"
                                value={assignmentsByKey[promptAssignmentKey(row)] ?? ""}
                                onChange={(event) => updateAssignment(row, event.target.value)}
                            >
                                <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                                {rowPrompts.map((prompt) => (
                                    <option key={prompt.id} value={prompt.id}>
                                        {promptLabel(prompt)}
                                    </option>
                                ))}
                            </select>
                        </div>
                    );
                })}
            </div>

            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveAssignments}>
                    {saving ? t("prompts.assignment.saving") : t("prompts.assignment.save")}
                </button>
            </div>
        </section>
    );
}
