import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { commitSillyTavernWorld, extractSillyTavernCard, getSillyTavernImportStatus, parseSillyTavernCard } from "@/api/sillytavernImport";
import { getDefaultAuthorId, uploadWorldCoverImage } from "@/api/worlds";
import { SillyTavernDropzone } from "@/components/SillyTavernDropzone";
import { SillyTavernExtractedWorldEditor } from "@/components/SillyTavernExtractedWorldEditor";
import { SillyTavernGreetingEditor } from "@/components/SillyTavernGreetingEditor";
import { SillyTavernLorebookEntryEditor } from "@/components/SillyTavernLorebookEntryEditor";

const FIRST_MES_KEY = "first_mes";

function buildGreetings(parsedCard) {
    const greetings = [{ key: FIRST_MES_KEY, label: "primary", text: parsedCard.first_mes ?? "" }];

    (parsedCard.alternate_greetings ?? []).forEach((text, index) => {
        greetings.push({ key: `alt-${index}`, label: "alternate", index, text });
    });

    return greetings;
}

export function SillyTavernImportPage() {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [fileName, setFileName] = useState(null);
    const [originalFile, setOriginalFile] = useState(null);
    const [coverImage, setCoverImage] = useState(null);

    const [fields, setFields] = useState(null);
    const [greetings, setGreetings] = useState([]);
    const [selectedGreetingKey, setSelectedGreetingKey] = useState(FIRST_MES_KEY);
    const [lorebookEntries, setLorebookEntries] = useState([]);

    const [status, setStatus] = useState(null);
    const [language, setLanguage] = useState(i18n.language?.startsWith("zh") ? "zh" : "en");
    const [extracting, setExtracting] = useState(false);
    const [extractError, setExtractError] = useState(null);
    const [assembled, setAssembled] = useState(null);

    const [committing, setCommitting] = useState(false);
    const [commitError, setCommitError] = useState(null);
    const [committedWorld, setCommittedWorld] = useState(null);

    const hasCard = fields !== null;
    const enabledEntryCount = useMemo(
        () => lorebookEntries.filter((entry) => entry.enabled).length,
        [lorebookEntries],
    );

    useEffect(() => {
        let cancelled = false;

        getSillyTavernImportStatus()
            .then((result) => {
                if (!cancelled) {
                    setStatus(result);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setStatus({ configured: false, missing_components: [] });
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    async function handleFileSelected(file) {
        setError(null);
        setLoading(true);
        setFileName(file.name);
        setOriginalFile(file);
        setAssembled(null);
        setExtractError(null);
        setCommittedWorld(null);
        setCommitError(null);

        try {
            const parsedCard = await parseSillyTavernCard(file);

            setFields({
                name: parsedCard.name ?? "",
                description: parsedCard.description ?? "",
                personality: parsedCard.personality ?? "",
                scenario: parsedCard.scenario ?? "",
                creator_notes: parsedCard.creator_notes ?? "",
                system_prompt: parsedCard.system_prompt ?? "",
                post_history_instructions: parsedCard.post_history_instructions ?? "",
                mes_example: parsedCard.mes_example ?? "",
                tags: (parsedCard.tags ?? []).join(", "),
            });
            setGreetings(buildGreetings(parsedCard));
            setSelectedGreetingKey(FIRST_MES_KEY);
            setLorebookEntries(parsedCard.lorebook_entries ?? []);
            setCoverImage(parsedCard.cover_image_data_uri ?? null);
        } catch (err) {
            setError(err.message);
            setFields(null);
        } finally {
            setLoading(false);
        }
    }

    function updateField(name, value) {
        setFields((current) => ({ ...current, [name]: value }));
    }

    function updateGreetingText(key, text) {
        setGreetings((current) => current.map((greeting) => (greeting.key === key ? { ...greeting, text } : greeting)));
    }

    function updateLorebookEntry(index, nextEntry) {
        setLorebookEntries((current) => current.map((entry, entryIndex) => (entryIndex === index ? nextEntry : entry)));
    }

    function handleReset() {
        setFields(null);
        setGreetings([]);
        setLorebookEntries([]);
        setCoverImage(null);
        setFileName(null);
        setOriginalFile(null);
        setError(null);
        setAssembled(null);
        setExtractError(null);
        setCommittedWorld(null);
        setCommitError(null);
    }

    async function handleExtract() {
        setExtractError(null);
        setExtracting(true);

        try {
            const selectedGreeting = greetings.find((greeting) => greeting.key === selectedGreetingKey);
            const card = {
                name: fields.name,
                description: fields.description,
                personality: fields.personality,
                scenario: fields.scenario,
                first_message: selectedGreeting?.text ?? "",
                mes_example: fields.mes_example,
                creator_notes: fields.creator_notes,
                system_prompt: fields.system_prompt,
                post_history_instructions: fields.post_history_instructions,
                tags: fields.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
                lorebook_entries: lorebookEntries
                    .filter((entry) => entry.enabled)
                    .map((entry) => ({ name: entry.name, keys: entry.keys, content: entry.content })),
            };

            setAssembled(await extractSillyTavernCard(card, language));
        } catch (err) {
            setExtractError(err.message);
        } finally {
            setExtracting(false);
        }
    }

    async function handleCommit() {
        setCommitError(null);
        setCommitting(true);

        try {
            const authorId = await getDefaultAuthorId();
            const world = await commitSillyTavernWorld(assembled.world, assembled.sections, authorId);

            if (originalFile) {
                await uploadWorldCoverImage(world.id, originalFile).catch(() => {});
            }

            setCommittedWorld(world);
        } catch (err) {
            setCommitError(err.message);
        } finally {
            setCommitting(false);
        }
    }

    return (
        <div className="st-import-page">
            <header className="st-import-header">
                <button type="button" className="secondary-button" onClick={() => navigate("/worlds")}>
                    {t("sillyTavernImport.back")}
                </button>
                <h1>{t("sillyTavernImport.title")}</h1>
                <div className="st-import-header-spacer" />
            </header>

            <div className="st-import-layout">
                <section className="st-import-left">
                    {!hasCard ? (
                        <div className="st-import-placeholder">
                            <SillyTavernDropzone onFileSelected={handleFileSelected} disabled={loading} />
                            {loading ? <p className="status-text">{t("sillyTavernImport.parsing")}</p> : null}
                            {error ? <p className="form-error">{t("sillyTavernImport.parseError", { error })}</p> : null}
                        </div>
                    ) : null}

                    {hasCard ? (
                        <div className="st-import-card-editor">
                            <div className="st-import-card-summary">
                                {coverImage ? (
                                    <img className="st-import-cover" src={coverImage} alt={fields.name} />
                                ) : null}
                                <div>
                                    <p className="st-import-file-name">{fileName}</p>
                                    <button type="button" className="secondary-button" onClick={handleReset}>
                                        {t("sillyTavernImport.chooseAnother")}
                                    </button>
                                </div>
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.name")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={fields.name}
                                    onChange={(event) => updateField("name", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.description")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.description}
                                    onChange={(event) => updateField("description", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.personality")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.personality}
                                    onChange={(event) => updateField("personality", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.scenario")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.scenario}
                                    onChange={(event) => updateField("scenario", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.mesExample")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.mes_example}
                                    onChange={(event) => updateField("mes_example", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.creatorNotes")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.creator_notes}
                                    onChange={(event) => updateField("creator_notes", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.systemPrompt")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.system_prompt}
                                    onChange={(event) => updateField("system_prompt", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.postHistoryInstructions")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={fields.post_history_instructions}
                                    onChange={(event) => updateField("post_history_instructions", event.target.value)}
                                />
                            </div>

                            <div className="form-field">
                                <label>{t("sillyTavernImport.fields.tags")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={fields.tags}
                                    onChange={(event) => updateField("tags", event.target.value)}
                                />
                            </div>

                            <section className="st-import-section">
                                <h2>{t("sillyTavernImport.greetings.title")}</h2>
                                <p className="st-import-section-hint">{t("sillyTavernImport.greetings.hint")}</p>
                                <div className="st-import-greeting-list">
                                    {greetings.map((greeting) => (
                                        <SillyTavernGreetingEditor
                                            key={greeting.key}
                                            greeting={{
                                                ...greeting,
                                                label:
                                                    greeting.label === "primary"
                                                        ? t("sillyTavernImport.greetings.primary")
                                                        : t("sillyTavernImport.greetings.alternate", {
                                                              index: greeting.index + 1,
                                                          }),
                                            }}
                                            selected={selectedGreetingKey === greeting.key}
                                            onSelect={() => setSelectedGreetingKey(greeting.key)}
                                            onChange={(text) => updateGreetingText(greeting.key, text)}
                                        />
                                    ))}
                                </div>
                            </section>

                            <section className="st-import-section">
                                <h2>{t("sillyTavernImport.lorebook.title")}</h2>
                                <p className="st-import-section-hint">
                                    {t("sillyTavernImport.lorebook.hint", {
                                        enabled: enabledEntryCount,
                                        total: lorebookEntries.length,
                                    })}
                                </p>
                                {lorebookEntries.length === 0 ? (
                                    <p className="status-text">{t("sillyTavernImport.lorebook.empty")}</p>
                                ) : (
                                    <div className="st-import-entry-list">
                                        {lorebookEntries.map((entry, index) => (
                                            <SillyTavernLorebookEntryEditor
                                                key={index}
                                                entry={entry}
                                                index={index}
                                                onChange={updateLorebookEntry}
                                            />
                                        ))}
                                    </div>
                                )}
                            </section>
                        </div>
                    ) : null}
                </section>

                <section className="st-import-right">
                    {committedWorld ? (
                        <div className="st-import-placeholder">
                            <div className="st-import-review-gate">
                                <p className="status-text">{t("sillyTavernImport.review.committed")}</p>
                                <button
                                    type="button"
                                    className="primary-button"
                                    onClick={() => navigate("/worlds")}
                                >
                                    {t("sillyTavernImport.review.goToWorld")}
                                </button>
                            </div>
                        </div>
                    ) : assembled ? (
                        <div className="st-import-review">
                            <SillyTavernExtractedWorldEditor assembled={assembled} onChange={setAssembled} />
                            {commitError ? (
                                <p className="form-error">{t("sillyTavernImport.review.commitError", { error: commitError })}</p>
                            ) : null}
                            <button
                                type="button"
                                className="primary-button st-import-commit-button"
                                onClick={handleCommit}
                                disabled={committing}
                            >
                                {committing
                                    ? t("sillyTavernImport.review.committing")
                                    : t("sillyTavernImport.review.commit")}
                            </button>
                        </div>
                    ) : status === null ? (
                        <div className="st-import-placeholder">
                            <p className="status-text">{t("sillyTavernImport.parsing")}</p>
                        </div>
                    ) : !status.configured ? (
                        <div className="st-import-placeholder">
                            <p className="status-text">{t("sillyTavernImport.review.notConfigured")}</p>
                        </div>
                    ) : !hasCard ? (
                        <div className="st-import-placeholder">
                            <p className="status-text">{t("sillyTavernImport.review.needsCard")}</p>
                        </div>
                    ) : extracting ? (
                        <div className="st-import-placeholder">
                            <p className="status-text">{t("sillyTavernImport.review.extracting")}</p>
                        </div>
                    ) : (
                        <div className="st-import-placeholder">
                            <div className="st-import-review-gate">
                                {extractError ? (
                                    <p className="form-error">{t("sillyTavernImport.review.extractError", { error: extractError })}</p>
                                ) : null}
                                <div className="form-field">
                                    <label>{t("sillyTavernImport.review.languageLabel")}</label>
                                    <select
                                        className="single-line-input"
                                        value={language}
                                        onChange={(event) => setLanguage(event.target.value)}
                                    >
                                        <option value="en">English</option>
                                        <option value="zh">中文</option>
                                    </select>
                                </div>
                                <button type="button" className="primary-button" onClick={handleExtract}>
                                    {extractError
                                        ? t("sillyTavernImport.review.retry")
                                        : t("sillyTavernImport.review.start")}
                                </button>
                            </div>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
