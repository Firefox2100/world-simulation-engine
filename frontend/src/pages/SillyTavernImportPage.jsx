import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
    commitSillyTavernWorld, extractSillyTavernCard,
    getSillyTavernImportStatus, parseSillyTavernCard, parseSillyTavernCardUrl,
} from "@/api/sillytavernImport";
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

function coverFileFromDataUri(dataUri) {
    if (!dataUri) return null;
    const [header, encoded] = dataUri.split(",", 2);
    const mimeType = header.match(/^data:([^;]+);base64$/)?.[1];
    if (!mimeType || !encoded) return null;
    const binary = atob(encoded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new File([bytes], "card-cover.png", { type: mimeType });
}

export function SillyTavernImportPage() {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [fileName, setFileName] = useState(null);
    const [originalFile, setOriginalFile] = useState(null);
    const [coverImage, setCoverImage] = useState(null);
    const [urlModalOpen, setUrlModalOpen] = useState(false);
    const [cardUrl, setCardUrl] = useState("");

    const [fields, setFields] = useState(null);
    const [greetings, setGreetings] = useState([]);
    const [selectedGreetingKey, setSelectedGreetingKey] = useState(FIRST_MES_KEY);
    const [lorebookEntries, setLorebookEntries] = useState([]);
    const [cardAssets, setCardAssets] = useState([]);
    const [cardExtensions, setCardExtensions] = useState({});

    const [status, setStatus] = useState(null);
    const [language, setLanguage] = useState(i18n.language?.startsWith("zh") ? "zh" : "en");
    const [extracting, setExtracting] = useState(false);
    const [streamProgress, setStreamProgress] = useState(null);
    const [extractError, setExtractError] = useState(null);
    const [assembled, setAssembled] = useState(null);
    const [imageCandidates, setImageCandidates] = useState([]);
    const [imageScan, setImageScan] = useState(null);
    const [selectedImageUrls, setSelectedImageUrls] = useState([]);

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

    function applyParsedCard(parsedCard) {
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
        setCardAssets(parsedCard.assets ?? []);
        setCardExtensions(parsedCard.extensions ?? {});
        setImageCandidates(parsedCard.image_candidates ?? []);
        setImageScan(parsedCard.image_scan ?? null);
        setSelectedImageUrls([]);
    }

    function prepareForParse(sourceName, file = null) {
        setError(null);
        setLoading(true);
        setFileName(sourceName);
        setOriginalFile(file);
        setAssembled(null);
        setExtractError(null);
        setStreamProgress(null);
        setCommittedWorld(null);
        setCommitError(null);
    }

    async function handleFileSelected(file) {
        prepareForParse(file.name, file);

        try {
            const parsedCard = await parseSillyTavernCard(file);
            applyParsedCard(parsedCard);
        } catch (err) {
            setError(err.message);
            setFields(null);
        } finally {
            setLoading(false);
        }
    }

    async function handleUrlSubmit(event) {
        event.preventDefault();
        const url = cardUrl.trim();
        if (!url) return;
        setUrlModalOpen(false);
        prepareForParse(url);
        try {
            const parsedCard = await parseSillyTavernCardUrl(url);
            applyParsedCard(parsedCard);
            setOriginalFile(coverFileFromDataUri(parsedCard.cover_image_data_uri));
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
        setCardAssets([]);
        setCardExtensions({});
        setFileName(null);
        setOriginalFile(null);
        setError(null);
        setAssembled(null);
        setExtractError(null);
        setStreamProgress(null);
        setCommittedWorld(null);
        setCommitError(null);
    }

    async function handleExtract() {
        setExtractError(null);
        setExtracting(true);
        setStreamProgress({ connected: false, keepalives: 0, sections: {} });
        setImageCandidates([]);
        setImageScan(null);
        setSelectedImageUrls([]);

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
                assets: cardAssets,
                extensions: cardExtensions,
            };

            const result = await extractSillyTavernCard(
                card, language, selectedImageUrls, setStreamProgress,
            );
            setAssembled(result);
            setImageCandidates(result.image_candidates ?? []);
            setImageScan(result.image_scan ?? null);
            setSelectedImageUrls([]);
        } catch (err) {
            setExtractError(err.message);
        } finally {
            setExtracting(false);
        }
    }

    function toggleImageCandidate(url, checked) {
        setSelectedImageUrls((current) => (
            checked ? [...current, url] : current.filter((selected) => selected !== url)
        ));
    }

    async function handleCommit() {
        setCommitError(null);
        setCommitting(true);

        try {
            const authorId = await getDefaultAuthorId();
            const mediaRows = assembled.sections.media ?? [];
            const world = {
                ...assembled.world,
                media_ids: mediaRows.map((row) => row.id),
            };
            const sections = {
                ...assembled.sections,
                media: mediaRows.map((row) => {
                    const cleaned = { ...row };
                    delete cleaned.preview_data_uri;
                    return cleaned;
                }),
            };
            const committed = await commitSillyTavernWorld(world, sections, authorId);

            if (originalFile && coverImage) {
                await uploadWorldCoverImage(committed.id, originalFile).catch(() => {});
            }

            setCommittedWorld(committed);
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
                            {loading ? (
                                <p className="status-text">{t("sillyTavernImport.parsing")}</p>
                            ) : (
                                <div className="st-import-dropzone-wrapper">
                                    <SillyTavernDropzone
                                        onFileSelected={handleFileSelected}
                                        onUrlRequested={() => setUrlModalOpen(true)}
                                        disabled={false}
                                    />
                                    {error ? (
                                        <p className="form-error">{t("sillyTavernImport.parseError", { error })}</p>
                                    ) : null}
                                </div>
                            )}
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

                            {imageScan ? (
                                <section className="st-import-section">
                                    <h2>{t("sillyTavernImport.imageCandidates.title")}</h2>
                                    <p className="st-import-section-hint">
                                        {t("sillyTavernImport.imageCandidates.summary", {
                                            found: imageScan.found,
                                            autoDownloaded: imageScan.auto_downloaded,
                                            awaitingReview: imageScan.awaiting_review,
                                            droppedUnsafe: imageScan.dropped_unsafe,
                                            droppedNonImage: imageScan.dropped_non_image,
                                        })}
                                    </p>
                                    {imageCandidates.length > 0 ? (
                                        <>
                                            <p className="st-import-section-hint">
                                                {t("sillyTavernImport.imageCandidates.hint")}
                                            </p>
                                            <label className="st-import-chip st-import-image-candidate">
                                                <input
                                                    type="checkbox"
                                                    checked={imageCandidates.length > 0 && selectedImageUrls.length === imageCandidates.length}
                                                    onChange={(event) => setSelectedImageUrls(
                                                        event.target.checked ? imageCandidates.map((candidate) => candidate.url) : [],
                                                    )}
                                                />
                                                <span>{t("sillyTavernImport.imageCandidates.selectAll", { defaultValue: "Select all" })}</span>
                                            </label>
                                            <div className="st-import-chip-list st-import-image-candidate-list">
                                                {imageCandidates.map((candidate) => (
                                                    <label key={candidate.url} className="st-import-chip st-import-image-candidate">
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedImageUrls.includes(candidate.url)}
                                                            onChange={(event) => toggleImageCandidate(candidate.url, event.target.checked)}
                                                        />
                                                        <span className="st-import-image-candidate-url">{candidate.url}</span>
                                                        <span className="st-import-image-candidate-source">
                                                            {t(`sillyTavernImport.imageCandidates.source.${candidate.source}`)}
                                                        </span>
                                                    </label>
                                                ))}
                                            </div>
                                        </>
                                    ) : null}
                                </section>
                            ) : null}
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
                            <div className="st-import-stream-progress" aria-live="polite">
                                <p className="status-text">{t("sillyTavernImport.review.extracting")}</p>
                                <p className="st-import-section-hint">
                                    {streamProgress?.connected
                                        ? t("sillyTavernImport.review.progress.connected")
                                        : t("sillyTavernImport.review.progress.connecting")}
                                </p>
                                <div className="st-import-stream-counters">
                                    {Object.entries(streamProgress?.sections ?? {})
                                        .filter(([, count]) => count.total > 0 || count.received > 0)
                                        .map(([name, count]) => (
                                            <div className="st-import-stream-counter" key={name}>
                                                <span>
                                                    {t(`sillyTavernImport.review.progress.sections.${name}`, {
                                                        defaultValue: name.replaceAll("_", " "),
                                                    })}
                                                </span>
                                                <strong>{count.received}/{count.total ?? "?"}</strong>
                                            </div>
                                        ))}
                                </div>
                                {streamProgress?.keepalives > 0 ? (
                                    <p className="st-import-section-hint">
                                        {t("sillyTavernImport.review.progress.keepalives", {
                                            count: streamProgress.keepalives,
                                        })}
                                    </p>
                                ) : null}
                            </div>
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

            {urlModalOpen ? (
                <div className="modal-backdrop" role="presentation" onMouseDown={() => setUrlModalOpen(false)}>
                    <div
                        className="modal-panel compact-modal-panel"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="st-url-modal-title"
                        onMouseDown={(event) => event.stopPropagation()}
                    >
                        <form className="connection-create-form" onSubmit={handleUrlSubmit}>
                            <div className="modal-header">
                                <h2 id="st-url-modal-title">{t("sillyTavernImport.urlModal.title")}</h2>
                            </div>
                            <div className="connection-create-form-content">
                                <label className="form-field inline-field modal-form-field" htmlFor="st-card-url">
                                    <span>{t("sillyTavernImport.urlModal.label")}</span>
                                    <input
                                        id="st-card-url"
                                        className="single-line-input"
                                        type="url"
                                        required
                                        autoFocus
                                        placeholder="https://example.com/card.png"
                                        value={cardUrl}
                                        onChange={(event) => setCardUrl(event.target.value)}
                                    />
                                </label>
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="secondary-button" onClick={() => setUrlModalOpen(false)}>
                                    {t("sillyTavernImport.urlModal.cancel")}
                                </button>
                                <button type="submit" className="primary-button" disabled={!cardUrl.trim()}>
                                    {t("sillyTavernImport.urlModal.submit")}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
