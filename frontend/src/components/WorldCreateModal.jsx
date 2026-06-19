import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchLlmConnectionProfiles } from "@/api/connections";
import { createWorld, updateWorld, uploadWorldCoverImage } from "@/api/worlds";
import { AgentPresetEditor } from "@/components/AgentPresetEditor";
import { CollapsibleFormSection } from "@/components/CollapsibleFormSection";
import { DataPresetEditor } from "@/components/DataPresetEditor";
import { EmbeddingProfileEditor } from "@/components/EmbeddingProfileEditor";
import { InfoTooltip } from "@/components/InfoTooltip";
import { InitialWorldStateEditor } from "@/components/InitialWorldStateEditor";
import {
    agentPresetFormFromWorld,
    buildAgentPresetPayload,
    makeAgentPresetState,
} from "@/shared/agentPresetModel";
import {
    buildDataPresetPayload,
    dataPresetFormFromWorld,
    makeDataPresetState,
} from "@/shared/dataPresetModel";
import {
    buildEmbeddingProfilePayload,
    embeddingProfileFormFromWorld,
    makeEmbeddingProfileState,
} from "@/shared/embeddingProfileModel";
import {
    buildCharactersPayload,
    buildFactionRelationshipsPayload,
    buildFactionsPayload,
    buildInventoryPayload,
    buildLocationsPayload,
    buildSimulationStatePayload,
    buildTasksPayload,
    buildTurnRecordsPayload,
    buildWorldEntriesPayload,
    initialWorldStateFormFromWorld,
    makeInitialWorldStateState,
} from "@/shared/initialWorldStateModel";

const objectSections = [];

const listSections = [];

const booleanFields = ["act_for_user", "enable_tts", "enable_image_generation"];

function makeOpenState(keys) {
    return keys.reduce((state, key) => ({ ...state, [key]: false }), {});
}

function makeObjectState(keys) {
    return keys.reduce((state, key) => ({ ...state, [key]: { placeholder: "" } }), {});
}

function cleanText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function placeholderObject(value) {
    const placeholder = cleanText(value.placeholder);
    return placeholder ? { placeholder } : null;
}

function placeholderList(items) {
    const values = items.map(placeholderObject).filter(Boolean);
    return values.length > 0 ? values : null;
}

export function WorldCreateModal({ mode = "create", initialWorld = null, onClose, onSaved }) {
    const { t } = useTranslation();
    const isEdit = mode === "edit";
    const [name, setName] = useState(initialWorld?.name ?? "");
    const [language, setLanguage] = useState(initialWorld?.language ?? "");
    const [coverImage, setCoverImage] = useState(null);
    const [description, setDescription] = useState(initialWorld?.description ?? "");
    const [booleans, setBooleans] = useState(
        booleanFields.reduce(
            (state, key) => ({ ...state, [key]: initialWorld?.[key] ?? false }),
            {},
        ),
    );
    const [agentPresetEnabled, setAgentPresetEnabled] = useState(Boolean(initialWorld?.agent_preset));
    const [agentPreset, setAgentPreset] = useState(() =>
        initialWorld?.agent_preset ? agentPresetFormFromWorld(initialWorld.agent_preset) : makeAgentPresetState(),
    );
    const [dataPresetEnabled, setDataPresetEnabled] = useState(Boolean(initialWorld?.data_preset));
    const [dataPreset, setDataPreset] = useState(() =>
        initialWorld?.data_preset ? dataPresetFormFromWorld(initialWorld.data_preset) : makeDataPresetState(),
    );
    const [embeddingProfileEnabled, setEmbeddingProfileEnabled] = useState(
        Boolean(initialWorld?.embedding_profile),
    );
    const [embeddingProfile, setEmbeddingProfile] = useState(() =>
        initialWorld?.embedding_profile
            ? embeddingProfileFormFromWorld(initialWorld.embedding_profile)
            : makeEmbeddingProfileState(),
    );
    const [simulationStateEnabled, setSimulationStateEnabled] = useState(Boolean(initialWorld?.state));
    const [initialWorldState, setInitialWorldState] = useState(() =>
        initialWorld ? initialWorldStateFormFromWorld(initialWorld) : makeInitialWorldStateState(),
    );
    const [llmConnections, setLlmConnections] = useState([]);
    const [objectValues, setObjectValues] = useState(makeObjectState(objectSections));
    const [listValues, setListValues] = useState(
        listSections.reduce((state, key) => ({ ...state, [key]: [] }), {}),
    );
    const [openSections, setOpenSections] = useState(
        makeOpenState([
            "description",
            "agent_preset",
            "data_preset",
            "embedding_profile",
            "initial_world_state",
            ...objectSections,
            ...listSections,
        ]),
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [connectionLoadError, setConnectionLoadError] = useState(null);
    const mountedRef = useRef(true);

    useEffect(() => {
        mountedRef.current = true;

        return () => {
            mountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    const refreshLlmConnections = useCallback(async () => {
        try {
            const data = await fetchLlmConnectionProfiles();
            if (!mountedRef.current) {
                return;
            }
            setLlmConnections(data);
            setConnectionLoadError(null);
        } catch (err) {
            if (!mountedRef.current) {
                return;
            }
            setLlmConnections([]);
            setConnectionLoadError(err.message);
        }
    }, []);

    useEffect(() => {
        const refreshTimer = window.setTimeout(() => {
            refreshLlmConnections();
        }, 0);

        return () => window.clearTimeout(refreshTimer);
    }, [refreshLlmConnections]);

    useEffect(() => {
        if (agentPresetEnabled || embeddingProfileEnabled) {
            const refreshTimer = window.setTimeout(() => {
                refreshLlmConnections();
            }, 0);

            return () => window.clearTimeout(refreshTimer);
        }

        return undefined;
    }, [agentPresetEnabled, embeddingProfileEnabled, refreshLlmConnections]);

    function toggleSection(key) {
        setOpenSections((current) => ({ ...current, [key]: !current[key] }));
    }

    function setObjectPlaceholder(key, value) {
        setObjectValues((current) => ({
            ...current,
            [key]: { placeholder: value },
        }));
    }

    function addListItem(key) {
        setListValues((current) => ({
            ...current,
            [key]: [...current[key], { placeholder: "" }],
        }));
    }

    function removeListItem(key, index) {
        setListValues((current) => ({
            ...current,
            [key]: current[key].filter((_, itemIndex) => itemIndex !== index),
        }));
    }

    function updateListItem(key, index, value) {
        setListValues((current) => ({
            ...current,
            [key]: current[key].map((item, itemIndex) =>
                itemIndex === index ? { placeholder: value } : item,
            ),
        }));
    }

    function buildPayload() {
        const payload = {
            name: name.trim(),
            act_for_user: booleans.act_for_user,
            enable_tts: booleans.enable_tts,
            enable_image_generation: booleans.enable_image_generation,
        };

        const cleanedDescription = cleanText(description);
        const cleanedLanguage = cleanText(language);

        if (cleanedDescription) {
            payload.description = cleanedDescription;
        }

        if (cleanedLanguage) {
            payload.language = cleanedLanguage;
        }

        if (agentPresetEnabled) {
            payload.agent_preset = buildAgentPresetPayload(agentPreset);
        }

        if (dataPresetEnabled) {
            payload.data_preset = buildDataPresetPayload(dataPreset);
        }

        if (embeddingProfileEnabled) {
            payload.embedding_profile = buildEmbeddingProfilePayload(embeddingProfile);
        }

        if (simulationStateEnabled) {
            payload.state = buildSimulationStatePayload(initialWorldState);
        }

        const locations = buildLocationsPayload(initialWorldState);
        if (locations.length > 0) {
            payload.locations = locations;
        }

        const characters = buildCharactersPayload(initialWorldState);
        if (characters.length > 0) {
            payload.characters = characters;
        }

        const factions = buildFactionsPayload(initialWorldState);
        if (factions.length > 0) {
            payload.factions = factions;
        }

        const factionRelationships = buildFactionRelationshipsPayload(initialWorldState);
        if (factionRelationships.length > 0) {
            payload.faction_relationships = factionRelationships;
        }

        const inventory = buildInventoryPayload(initialWorldState);
        if (Object.keys(inventory).length > 0) {
            payload.inventory = inventory;
        }

        const tasks = buildTasksPayload(initialWorldState);
        if (tasks.length > 0) {
            payload.tasks = tasks;
        }

        const worldEntries = buildWorldEntriesPayload(initialWorldState);
        if (worldEntries.length > 0) {
            payload.world_entries = worldEntries;
        }

        const turnRecords = buildTurnRecordsPayload(initialWorldState);
        if (turnRecords.length > 0) {
            payload.turn_records = turnRecords;
        }

        objectSections.forEach((key) => {
            const value = placeholderObject(objectValues[key]);
            if (value) {
                payload[key] = value;
            }
        });

        listSections.forEach((key) => {
            const value = placeholderList(listValues[key]);
            if (value) {
                payload[key] = value;
            }
        });

        return payload;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setError(null);

        if (name.trim().length === 0) {
            setError(t("worldCreate.validation.nameRequired"));
            return;
        }

        try {
            setSaving(true);
            const savedWorld = isEdit
                ? await updateWorld(initialWorld.id, buildPayload())
                : await createWorld(buildPayload());

            if (coverImage) {
                await uploadWorldCoverImage(savedWorld.id ?? initialWorld?.id, coverImage);
            }

            setSaving(false);
            onSaved();
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby="create-world-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <form className="world-create-form" onSubmit={handleSubmit}>
                    <div className="modal-header">
                        <h2 id="create-world-title">
                            {isEdit ? t("worldCreate.editTitle") : t("worldCreate.title")}
                        </h2>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("worldCreate.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </div>

                    <div className="world-create-form-content">
                        <div className="form-field inline-field">
                            <label htmlFor="world-name">{t("worldCreate.fields.name.label")}</label>
                            <InfoTooltip
                                label={t("worldCreate.tooltipLabel", {
                                    field: t("worldCreate.fields.name.label"),
                                })}
                                text={t("worldCreate.fields.name.tooltip")}
                            />
                            <input
                                id="world-name"
                                className="single-line-input"
                                value={name}
                                onChange={(event) => setName(event.target.value)}
                                required
                            />
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="world-language">
                                {t("worldCreate.fields.language.label")}
                            </label>
                            <InfoTooltip
                                label={t("worldCreate.tooltipLabel", {
                                    field: t("worldCreate.fields.language.label"),
                                })}
                                text={t("worldCreate.fields.language.tooltip")}
                            />
                            <input
                                id="world-language"
                                className="single-line-input"
                                value={language}
                                onChange={(event) => setLanguage(event.target.value)}
                                placeholder={t("worldCreate.fields.language.placeholder")}
                            />
                        </div>

                        <div className="form-field inline-field">
                            <label htmlFor="world-cover-image">
                                {t("worldCreate.fields.coverImage.label")}
                            </label>
                            <InfoTooltip
                                label={t("worldCreate.tooltipLabel", {
                                    field: t("worldCreate.fields.coverImage.label"),
                                })}
                                text={t("worldCreate.fields.coverImage.tooltip")}
                            />
                            <input
                                id="world-cover-image"
                                className="file-input"
                                type="file"
                                accept="image/*"
                                onChange={(event) =>
                                    setCoverImage(event.target.files?.[0] ?? null)
                                }
                            />
                        </div>

                        <div className="checkbox-grid">
                            {booleanFields.map((field) => (
                                <label className="checkbox-field" key={field}>
                                    <span>{t(`worldCreate.fields.${field}.label`)}</span>
                                    <InfoTooltip
                                        label={t("worldCreate.tooltipLabel", {
                                            field: t(`worldCreate.fields.${field}.label`),
                                        })}
                                        text={t(`worldCreate.fields.${field}.tooltip`)}
                                    />
                                    <input
                                        type="checkbox"
                                        checked={booleans[field]}
                                        onChange={(event) =>
                                            setBooleans((current) => ({
                                                ...current,
                                                [field]: event.target.checked,
                                            }))
                                        }
                                    />
                                </label>
                            ))}
                        </div>

                        <CollapsibleFormSection
                            title={t("worldCreate.fields.description.label")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.fields.description.label"),
                            })}
                            tooltip={t("worldCreate.fields.description.tooltip")}
                            open={openSections.description}
                            onToggle={() => toggleSection("description")}
                        >
                            <textarea
                                className="multi-line-input"
                                value={description}
                                onChange={(event) => setDescription(event.target.value)}
                            />
                        </CollapsibleFormSection>

                        <CollapsibleFormSection
                            key="agent_preset"
                            title={t("worldCreate.fields.agent_preset.label")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.fields.agent_preset.label"),
                            })}
                            tooltip={t("worldCreate.fields.agent_preset.tooltip")}
                            open={openSections.agent_preset}
                            onToggle={() => toggleSection("agent_preset")}
                        >
                            {connectionLoadError ? (
                                <p className="form-error">
                                    {t("worldCreate.connectionLoadError", {
                                        error: connectionLoadError,
                                    })}
                                </p>
                            ) : null}
                            <AgentPresetEditor
                                enabled={agentPresetEnabled}
                                onEnabledChange={setAgentPresetEnabled}
                                value={agentPreset}
                                onChange={setAgentPreset}
                                llmConnections={llmConnections}
                                providerLabels={{
                                    openai: t("connections.providers.openai"),
                                    ollama: t("connections.providers.ollama"),
                                }}
                            />
                        </CollapsibleFormSection>

                        <CollapsibleFormSection
                            key="data_preset"
                            title={t("worldCreate.fields.data_preset.label")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.fields.data_preset.label"),
                            })}
                            tooltip={t("worldCreate.fields.data_preset.tooltip")}
                            open={openSections.data_preset}
                            onToggle={() => toggleSection("data_preset")}
                        >
                            <DataPresetEditor
                                enabled={dataPresetEnabled}
                                onEnabledChange={setDataPresetEnabled}
                                value={dataPreset}
                                onChange={setDataPreset}
                            />
                        </CollapsibleFormSection>

                        <CollapsibleFormSection
                            key="embedding_profile"
                            title={t("worldCreate.fields.embedding_profile.label")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.fields.embedding_profile.label"),
                            })}
                            tooltip={t("worldCreate.fields.embedding_profile.tooltip")}
                            open={openSections.embedding_profile}
                            onToggle={() => toggleSection("embedding_profile")}
                        >
                            {connectionLoadError ? (
                                <p className="form-error">
                                    {t("worldCreate.connectionLoadError", {
                                        error: connectionLoadError,
                                    })}
                                </p>
                            ) : null}
                            <EmbeddingProfileEditor
                                enabled={embeddingProfileEnabled}
                                onEnabledChange={setEmbeddingProfileEnabled}
                                value={embeddingProfile}
                                onChange={setEmbeddingProfile}
                                llmConnections={llmConnections}
                                providerLabels={{
                                    openai: t("connections.providers.openai"),
                                    ollama: t("connections.providers.ollama"),
                                }}
                            />
                        </CollapsibleFormSection>

                        <CollapsibleFormSection
                            key="initial_world_state"
                            title={t("worldCreate.initialState.title")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.initialState.title"),
                            })}
                            tooltip={t("worldCreate.initialState.tooltip")}
                            open={openSections.initial_world_state}
                            onToggle={() => toggleSection("initial_world_state")}
                        >
                            <InitialWorldStateEditor
                                stateEnabled={simulationStateEnabled}
                                onStateEnabledChange={setSimulationStateEnabled}
                                value={initialWorldState}
                                onChange={setInitialWorldState}
                                dataPreset={dataPreset}
                            />
                        </CollapsibleFormSection>

                        {objectSections.map((field) => (
                            <CollapsibleFormSection
                                key={field}
                                title={t(`worldCreate.fields.${field}.label`)}
                                tooltipLabel={t("worldCreate.tooltipLabel", {
                                    field: t(`worldCreate.fields.${field}.label`),
                                })}
                                tooltip={t(`worldCreate.fields.${field}.tooltip`)}
                                open={openSections[field]}
                                onToggle={() => toggleSection(field)}
                            >
                                <div className="form-field">
                                    <label htmlFor={`world-${field}-placeholder`}>
                                        {t("worldCreate.fields.placeholder.label")}
                                    </label>
                                    <input
                                        id={`world-${field}-placeholder`}
                                        className="single-line-input"
                                        value={objectValues[field].placeholder}
                                        onChange={(event) =>
                                            setObjectPlaceholder(field, event.target.value)
                                        }
                                    />
                                </div>
                            </CollapsibleFormSection>
                        ))}

                        {listSections.map((field) => (
                            <CollapsibleFormSection
                                key={field}
                                title={t(`worldCreate.fields.${field}.label`)}
                                tooltipLabel={t("worldCreate.tooltipLabel", {
                                    field: t(`worldCreate.fields.${field}.label`),
                                })}
                                tooltip={t(`worldCreate.fields.${field}.tooltip`)}
                                open={openSections[field]}
                                onToggle={() => toggleSection(field)}
                            >
                                <div className="list-editor">
                                    {listValues[field].map((item, index) => (
                                        <div className="list-editor-row" key={index}>
                                            <label htmlFor={`world-${field}-${index}`}>
                                                {t("worldCreate.fields.placeholder.itemLabel", {
                                                    number: index + 1,
                                                })}
                                            </label>
                                            <input
                                                id={`world-${field}-${index}`}
                                                className="single-line-input"
                                                value={item.placeholder}
                                                onChange={(event) =>
                                                    updateListItem(field, index, event.target.value)
                                                }
                                            />
                                            <button
                                                type="button"
                                                className="secondary-button"
                                                onClick={() => removeListItem(field, index)}
                                            >
                                                {t("worldCreate.remove")}
                                            </button>
                                        </div>
                                    ))}

                                    <button
                                        type="button"
                                        className="secondary-button"
                                        onClick={() => addListItem(field)}
                                    >
                                        {t("worldCreate.add")}
                                    </button>
                                </div>
                            </CollapsibleFormSection>
                        ))}

                        {error ? (
                            <p className="form-error">{t("worldCreate.error", { error })}</p>
                        ) : null}
                    </div>

                    <div className="modal-actions">
                        <button type="button" className="secondary-button" onClick={onClose}>
                            {t("worldCreate.cancel")}
                        </button>
                        <button type="submit" className="primary-button" disabled={saving}>
                            {saving
                                ? t("worldCreate.saving")
                                : isEdit
                                  ? t("worldCreate.update")
                                  : t("worldCreate.submit")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
