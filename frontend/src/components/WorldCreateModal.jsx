import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAuthors } from "@/api/authors";
import {
    fetchEmbeddingConfigs,
    fetchLlmConfigs,
    fetchWorldEmbeddingConfigs,
    fetchWorldLlmConfigs,
    setWorldEmbeddingConfigs,
    setWorldLlmConfigs,
    simulatorComponents,
} from "@/api/configurations";
import { deleteCoverImage, getCoverImageUrl, setCoverImage } from "@/api/media";
import { createWorld, updateWorld } from "@/api/worlds";
import {
    createWorldBackgroundCharacter,
    createWorldCharacter,
    createWorldContainer,
    createWorldEquipment,
    createWorldItem,
    createWorldItemStack,
    createWorldLocation,
    deleteBackgroundCharacter,
    deleteCharacter,
    deleteContainer,
    deleteEquipment,
    deleteItem,
    deleteLocation,
    fetchWorldAuthor,
    fetchWorldBackgroundCharacters,
    fetchWorldCharacters,
    fetchWorldContainers,
    fetchWorldEquipment,
    fetchWorldItems,
    fetchWorldLocations,
    updateBackgroundCharacter,
    updateCharacter,
    updateContainer,
    updateEquipment,
    updateItem,
    updateLocation,
    updateWorldAuthor,
} from "@/api/worldEntities";
import { MediaPickerModal } from "@/components/MediaPickerModal";
import { PromptAssignmentEditor } from "@/components/PromptAssignmentEditor";

const sections = ["world", "configs", "prompts", "locations", "characters", "background", "items", "equipment", "containers", "stacks"];
const entitySections = ["locations", "characters", "background", "items", "equipment", "containers", "stacks"];

const entityDependencies = {
    characters: ["locations"],
    background: ["locations"],
    equipment: ["locations", "characters", "containers"],
    containers: ["locations", "characters", "items", "equipment", "containers"],
    stacks: ["locations", "characters", "items", "containers"],
};

const requiredFields = {
    locations: ["name", "description"],
    characters: [
        "name",
        "age",
        "gender",
        "appearance",
        "description",
        "public_state",
        "private_state",
        "activity_name",
    ],
    background: ["name", "description"],
    items: ["name", "description"],
    equipment: ["name", "description"],
    containers: ["name", "description", "state"],
    stacks: ["item_id"],
};

const emptyForms = {
    locations: { name: "", description: "", parent_location_id: "" },
    characters: {
        user_controlled: false,
        name: "",
        age: "0",
        gender: "",
        appearance: "",
        description: "",
        public_state: "",
        private_state: "",
        activity_name: "Idle",
        activity_interruptible: true,
        activity_constraints: "",
        location_id: "",
        position: "",
    },
    background: { name: "", description: "", location_id: "", position: "", landmark_id: "" },
    items: { name: "", description: "", unique: false },
    equipment: {
        name: "",
        description: "",
        quality: "",
        location_id: "",
        position: "",
        owner_id: "",
        holder_id: "",
        equipped: false,
        equipped_position: "",
    },
    containers: {
        name: "",
        description: "",
        state: "unlocked",
        location_id: "",
        position: "",
        owner_id: "",
        holder_id: "",
        held_stack_ids: "",
        held_equipment_ids: "",
        held_container_ids: "",
        unlocking_item_ids: "",
    },
    stacks: { item_id: "", quantity: "1", quality: "", location_id: "", position: "", holder_id: "", owner_id: "" },
};

function cleanText(value) {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function labelFor(entity, fallback) {
    return entity?.name || entity?.model || entity?.id || fallback;
}

function makeEntityForm(kind, entity) {
    if (!entity) {
        return { ...emptyForms[kind] };
    }

    if (kind === "characters") {
        return {
            ...emptyForms.characters,
            ...entity,
            age: entity.age == null ? "0" : String(entity.age),
            activity_name: entity.current_activity?.name ?? "Idle",
            activity_interruptible: entity.current_activity?.interruptible ?? true,
            activity_constraints: (entity.current_activity?.constraints ?? []).join(", "),
        };
    }

    return Object.fromEntries(
        Object.entries({ ...emptyForms[kind], ...entity }).map(([key, value]) => [
            key,
            Array.isArray(value) ? value.join(", ") : value == null ? "" : value,
        ]),
    );
}

function worldFormFromWorld(world) {
    return {
        name: world?.name ?? "",
        description: world?.description ?? "",
        language: world?.language ?? "en",
        starting_time: world?.starting_time ? world.starting_time.slice(0, 16) : "2000-01-01T00:00",
        version: world?.version == null ? "1" : String(world.version),
        url: world?.url ?? "",
        author_id: world?.author_id ?? "",
    };
}

function worldPayload(form) {
    return {
        name: form.name.trim(),
        description: cleanText(form.description),
        language: form.language,
        starting_time: new Date(form.starting_time).toISOString(),
        version: Number.parseInt(form.version, 10) || 1,
        url: cleanText(form.url),
        author_id: form.author_id,
    };
}

function emptyComponentConfigMap() {
    return Object.fromEntries(simulatorComponents.map((component) => [component, ""]));
}

function componentConfigMapFromAssignments(assignments) {
    return assignments.reduce((result, assignment) => {
        result[assignment.component] = assignment.config?.id ?? "";
        return result;
    }, emptyComponentConfigMap());
}

function componentAssignmentsFromMap(configsByComponent) {
    return simulatorComponents.map((component) => ({
        component,
        config_id: configsByComponent[component] || null,
    }));
}

function hasValue(value) {
    if (typeof value === "boolean") {
        return true;
    }

    if (Array.isArray(value)) {
        return value.length > 0;
    }

    return value !== null && value !== undefined && String(value).trim().length > 0;
}

function isWorldFormValid(form) {
    return ["name", "language", "starting_time", "author_id"].every((field) => hasValue(form[field]));
}

function isEntityFormValid(kind, form) {
    return (requiredFields[kind] ?? []).every((field) => hasValue(form[field]));
}

export function WorldCreateModal({ mode = "create", initialWorld = null, onClose, onSaved }) {
    const { t } = useTranslation();
    const isEdit = mode === "edit";
    const [activeSection, setActiveSection] = useState("world");
    const [world, setWorld] = useState(initialWorld);
    const [worldForm, setWorldForm] = useState(() => worldFormFromWorld(initialWorld));
    const [authors, setAuthors] = useState([]);
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [embeddingConfigs, setEmbeddingConfigs] = useState([]);
    const [llmConfigsByComponent, setLlmConfigsByComponent] = useState(() => emptyComponentConfigMap());
    const [embeddingConfigsByComponent, setEmbeddingConfigsByComponent] = useState(() => emptyComponentConfigMap());
    const [locations, setLocations] = useState([]);
    const [characters, setCharacters] = useState([]);
    const [backgroundCharacters, setBackgroundCharacters] = useState([]);
    const [items, setItems] = useState([]);
    const [equipment, setEquipment] = useState([]);
    const [containers, setContainers] = useState([]);
    const [forms, setForms] = useState(() =>
        Object.fromEntries(Object.keys(emptyForms).map((key) => [key, { ...emptyForms[key] }])),
    );
    const [editing, setEditing] = useState({});
    const [loadingSections, setLoadingSections] = useState({});
    const [loadedSections, setLoadedSections] = useState({});
    const [configConnectionsLoaded, setConfigConnectionsLoaded] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [configNotice, setConfigNotice] = useState(null);
    const [mediaPickerTarget, setMediaPickerTarget] = useState(null);
    const [coverRefreshKey, setCoverRefreshKey] = useState(0);

    const worldId = world?.id ?? initialWorld?.id ?? null;
    const worldFormValid = isWorldFormValid(worldForm);
    const loading = Boolean(loadingSections[activeSection]);

    const lookups = useMemo(
        () => ({
            locations,
            characters,
            items,
            equipment,
            containers,
        }),
        [characters, containers, equipment, items, locations],
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
        async function loadGlobalOptions() {
            const [authorData, llmData, embeddingData] = await Promise.all([
                fetchAuthors(),
                fetchLlmConfigs(),
                fetchEmbeddingConfigs(),
            ]);
            setAuthors(authorData);
            setLlmConfigs(llmData);
            setEmbeddingConfigs(embeddingData);
        }

        loadGlobalOptions().catch((err) => setError(err.message));
    }, []);

    const setSectionData = useCallback((kind, data) => {
        if (kind === "locations") {
            setLocations(data);
        } else if (kind === "characters") {
            setCharacters(data);
        } else if (kind === "background") {
            setBackgroundCharacters(data);
        } else if (kind === "items") {
            setItems(data);
        } else if (kind === "equipment") {
            setEquipment(data);
        } else if (kind === "containers") {
            setContainers(data);
        }
    }, []);

    const fetchSectionData = useCallback(async (kind, id) => {
        if (kind === "locations") {
            return fetchWorldLocations(id);
        }

        if (kind === "characters") {
            return fetchWorldCharacters(id);
        }

        if (kind === "background") {
            return fetchWorldBackgroundCharacters(id);
        }

        if (kind === "items") {
            return fetchWorldItems(id);
        }

        if (kind === "equipment") {
            return fetchWorldEquipment(id);
        }

        if (kind === "containers") {
            return fetchWorldContainers(id);
        }

        return [];
    }, []);

    const loadEntitySection = useCallback(
        async (kind, id = worldId, { force = false, includeDependencies = true } = {}) => {
            if (!id || !entitySections.includes(kind)) {
                return;
            }

            const dependencies = includeDependencies ? (entityDependencies[kind] ?? []) : [];
            const sectionsToLoad = [...new Set([kind, ...dependencies])]
                .filter((section) => section !== "stacks")
                .filter((section) => force || !loadedSections[section]);

            if (sectionsToLoad.length === 0) {
                return;
            }

            setLoadingSections((current) => ({
                ...current,
                ...Object.fromEntries(sectionsToLoad.map((section) => [section, true])),
            }));

            try {
                const results = await Promise.all(
                    sectionsToLoad.map(async (section) => [section, await fetchSectionData(section, id)]),
                );

                results.forEach(([section, data]) => setSectionData(section, data));
                setLoadedSections((current) => ({
                    ...current,
                    ...Object.fromEntries(sectionsToLoad.map((section) => [section, true])),
                }));
            } catch (err) {
                setError(err.message);
            } finally {
                setLoadingSections((current) => ({
                    ...current,
                    ...Object.fromEntries(sectionsToLoad.map((section) => [section, false])),
                }));
            }
        },
        [fetchSectionData, loadedSections, setSectionData, worldId],
    );

    useEffect(() => {
        if (!worldId) {
            return;
        }

        fetchWorldAuthor(worldId)
            .then((author) => setWorldForm((current) => ({ ...current, author_id: current.author_id || author?.id || "" })))
            .catch(() => {});
    }, [worldId]);

    useEffect(() => {
        if (!entitySections.includes(activeSection)) {
            return;
        }

        const loadTimer = window.setTimeout(() => {
            loadEntitySection(activeSection);
        }, 0);

        return () => window.clearTimeout(loadTimer);
    }, [activeSection, loadEntitySection]);

    useEffect(() => {
        if (activeSection !== "configs" || !worldId || configConnectionsLoaded) {
            return;
        }

        let cancelled = false;

        async function loadWorldConfigConnections() {
            setLoadingSections((current) => ({ ...current, configs: true }));
            try {
                const [llmAssignments, embeddingAssignments] = await Promise.all([
                    fetchWorldLlmConfigs(worldId),
                    fetchWorldEmbeddingConfigs(worldId),
                ]);

                if (!cancelled) {
                    setLlmConfigsByComponent(componentConfigMapFromAssignments(llmAssignments));
                    setEmbeddingConfigsByComponent(componentConfigMapFromAssignments(embeddingAssignments));
                    setConfigConnectionsLoaded(true);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoadingSections((current) => ({ ...current, configs: false }));
                }
            }
        }

        loadWorldConfigConnections();

        return () => {
            cancelled = true;
        };
    }, [activeSection, configConnectionsLoaded, worldId]);

    function updateWorldField(field, value) {
        setWorldForm((current) => ({ ...current, [field]: value }));
    }

    function updateForm(kind, field, value) {
        setForms((current) => ({
            ...current,
            [kind]: {
                ...current[kind],
                [field]: value,
            },
        }));
    }

    function updateComponentConfig(kind, component, configId) {
        const setter = kind === "llm" ? setLlmConfigsByComponent : setEmbeddingConfigsByComponent;

        setter((current) => ({
            ...current,
            [component]: configId,
        }));
    }

    async function ensureWorldSaved() {
        if (worldId) {
            return worldId;
        }

        if (!isWorldFormValid(worldForm)) {
            throw new Error(t("worldCreate.newEditor.validation.worldRequired"));
        }

        const saved = await createWorld(worldPayload(worldForm));
        setWorld(saved);
        if (worldForm.author_id) {
            await updateWorldAuthor(saved.id, worldForm.author_id);
        }
        return saved.id;
    }

    async function saveWorldOnly(event) {
        event?.preventDefault();
        setError(null);

        if (!worldFormValid) {
            setError(t("worldCreate.validation.nameRequired"));
            return;
        }

        try {
            setSaving(true);
            const payload = worldPayload(worldForm);
            const saved = worldId ? await updateWorld(worldId, payload) : await createWorld(payload);
            setWorld(saved);
            if (worldForm.author_id) {
                await updateWorldAuthor(saved.id, worldForm.author_id);
            }
            setSaving(false);
            if (!isEdit) {
                setActiveSection("configs");
            }
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function saveConfigurations() {
        setError(null);
        setConfigNotice(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            await Promise.all(
                [
                    setWorldLlmConfigs(id, componentAssignmentsFromMap(llmConfigsByComponent)),
                    setWorldEmbeddingConfigs(id, componentAssignmentsFromMap(embeddingConfigsByComponent)),
                ],
            );
            setConfigConnectionsLoaded(true);
            setConfigNotice(t("worldCreate.newEditor.configSaved"));
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function saveEntity(kind) {
        setError(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            const form = forms[kind];
            const editingEntity = editing[kind];
            let savedEntity = null;

            if (kind === "locations") {
                savedEntity = editingEntity
                    ? await updateLocation(editingEntity.id, form)
                    : await createWorldLocation(id, form);
            } else if (kind === "characters") {
                savedEntity = editingEntity
                    ? await updateCharacter(editingEntity.id, form)
                    : await createWorldCharacter(id, form);
            } else if (kind === "background") {
                savedEntity = editingEntity
                    ? await updateBackgroundCharacter(editingEntity.id, form)
                    : await createWorldBackgroundCharacter(id, form);
            } else if (kind === "items") {
                savedEntity = editingEntity ? await updateItem(editingEntity.id, form) : await createWorldItem(id, form);
            } else if (kind === "equipment") {
                savedEntity = editingEntity
                    ? await updateEquipment(editingEntity.id, form)
                    : await createWorldEquipment(id, form);
            } else if (kind === "containers") {
                savedEntity = editingEntity
                    ? await updateContainer(editingEntity.id, form)
                    : await createWorldContainer(id, form);
            } else if (kind === "stacks") {
                if (!form.item_id) {
                    throw new Error(t("worldCreate.newEditor.validation.itemRequired"));
                }
                savedEntity = await createWorldItemStack(id, form.item_id, form);
            }

            await loadEntitySection(kind, id, { force: true, includeDependencies: false });
            if (savedEntity && kind !== "stacks") {
                setEditing((current) => ({ ...current, [kind]: savedEntity }));
                setForms((current) => ({ ...current, [kind]: makeEntityForm(kind, savedEntity) }));
            } else {
                setForms((current) => ({ ...current, [kind]: { ...emptyForms[kind] } }));
                setEditing((current) => ({ ...current, [kind]: null }));
            }
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function deleteEntity(kind, entity) {
        if (!window.confirm(t("worldCreate.newEditor.confirmDelete", { name: labelFor(entity, entity.id) }))) {
            return;
        }

        try {
            setSaving(true);
            if (kind === "locations") {
                await deleteLocation(entity.id);
            } else if (kind === "characters") {
                await deleteCharacter(entity.id);
            } else if (kind === "background") {
                await deleteBackgroundCharacter(entity.id);
            } else if (kind === "items") {
                await deleteItem(entity.id);
            } else if (kind === "equipment") {
                await deleteEquipment(entity.id);
            } else if (kind === "containers") {
                await deleteContainer(entity.id);
            }
            await loadEntitySection(kind, worldId, { force: true, includeDependencies: false });
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    function beginEdit(kind, entity) {
        setEditing((current) => ({ ...current, [kind]: entity }));
        setForms((current) => ({ ...current, [kind]: makeEntityForm(kind, entity) }));
    }

    function beginCreate(kind) {
        setEditing((current) => ({ ...current, [kind]: null }));
        setForms((current) => ({ ...current, [kind]: { ...emptyForms[kind] } }));
    }

    async function handleSelectCover(media) {
        if (!mediaPickerTarget) {
            return;
        }

        try {
            setSaving(true);
            setError(null);
            await setCoverImage(mediaPickerTarget.kind, mediaPickerTarget.id, media.id);
            setCoverRefreshKey((current) => current + 1);
            setMediaPickerTarget(null);
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function handleRemoveCover(kind, id) {
        try {
            setSaving(true);
            setError(null);
            await deleteCoverImage(kind, id);
            setCoverRefreshKey((current) => current + 1);
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    function finish() {
        onSaved();
    }

    const entityData = {
        locations,
        characters,
        background: backgroundCharacters,
        items,
        equipment,
        containers,
        stacks: [],
    };

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="simulation-details-modal world-editor-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="create-world-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <aside className="simulation-details-nav" aria-label={t("worldCreate.newEditor.navLabel")}>
                    <div className="simulation-details-nav-title">
                        {isEdit ? t("worldCreate.editTitle") : t("worldCreate.title")}
                    </div>
                    {sections.map((section) => (
                        <button
                            key={section}
                            type="button"
                            className={`simulation-details-nav-item${activeSection === section ? " active" : ""}`}
                            onClick={() => setActiveSection(section)}
                        >
                            {t(`worldCreate.newEditor.tabs.${section}`)}
                        </button>
                    ))}
                </aside>

                <section className="simulation-details-content">
                    <header className="simulation-details-header">
                        <div>
                            <p className="simulation-details-eyebrow">
                                {worldId
                                    ? t("worldCreate.newEditor.savedWorld", { id: worldId })
                                    : t("worldCreate.newEditor.unsavedWorld")}
                            </p>
                            <h2 id="create-world-title">
                                {t(`worldCreate.newEditor.tabs.${activeSection}`)}
                            </h2>
                        </div>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("worldCreate.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </header>

                    <div className="simulation-details-body">
                        {loading ? <p className="status-text">{t("worldCreate.newEditor.loading")}</p> : null}
                        {error ? <p className="form-error">{error}</p> : null}

                        {activeSection === "world" ? (
                            <form className="world-editor-form" onSubmit={saveWorldOnly}>
                                <TextField label={t("worldCreate.fields.name.label")} value={worldForm.name} onChange={(value) => updateWorldField("name", value)} required />
                                <TextArea label={t("worldCreate.fields.description.label")} value={worldForm.description} onChange={(value) => updateWorldField("description", value)} />
                                <SelectField label={t("worldCreate.fields.language.label")} value={worldForm.language} onChange={(value) => updateWorldField("language", value)} options={[{ id: "en", name: "English" }, { id: "zh", name: "中文" }]} required />
                                <SelectField label={t("worldCreate.newEditor.fields.author")} value={worldForm.author_id} onChange={(value) => updateWorldField("author_id", value)} options={authors} emptyLabel={t("worldCreate.newEditor.emptySelect")} required />
                                <TextField label={t("worldCreate.newEditor.fields.startingTime")} value={worldForm.starting_time} onChange={(value) => updateWorldField("starting_time", value)} type="datetime-local" required />
                                <TextField label={t("worldCreate.newEditor.fields.version")} value={worldForm.version} onChange={(value) => updateWorldField("version", value)} type="number" />
                                <TextField label={t("worldCreate.newEditor.fields.url")} value={worldForm.url} onChange={(value) => updateWorldField("url", value)} />
                                <CoverImageField
                                    kind="world"
                                    sourceId={worldId}
                                    refreshKey={coverRefreshKey}
                                    disabled={!worldId || saving}
                                    onChoose={() => setMediaPickerTarget({ kind: "world", id: worldId })}
                                    onRemove={() => handleRemoveCover("world", worldId)}
                                />
                                <div className="modal-actions inline-actions">
                                    <button type="submit" className="primary-button" disabled={saving || !worldFormValid}>
                                        {saving ? t("worldCreate.saving") : t("worldCreate.newEditor.saveWorld")}
                                    </button>
                                    <button type="button" className="secondary-button" onClick={finish}>
                                        {t("worldCreate.newEditor.done")}
                                    </button>
                                </div>
                            </form>
                        ) : null}

                        {activeSection === "configs" ? (
                            <section className="world-editor-form">
                                <ComponentConfigMatrix
                                    llmConfigs={llmConfigs}
                                    embeddingConfigs={embeddingConfigs}
                                    llmConfigsByComponent={llmConfigsByComponent}
                                    embeddingConfigsByComponent={embeddingConfigsByComponent}
                                    onChange={updateComponentConfig}
                                />
                                {configNotice ? (
                                    <p className="simulation-details-empty-line">{configNotice}</p>
                                ) : null}
                                <div className="modal-actions inline-actions">
                                    <button type="button" className="primary-button" disabled={saving || !worldFormValid} onClick={saveConfigurations}>
                                        {saving ? t("worldCreate.saving") : t("worldCreate.newEditor.saveConfigurations")}
                                    </button>
                                    <button type="button" className="secondary-button" onClick={finish}>
                                        {t("worldCreate.newEditor.done")}
                                    </button>
                                </div>
                            </section>
                        ) : null}

                        {activeSection === "prompts" ? (
                            <PromptAssignmentEditor
                                sourceType="world"
                                sourceId={worldId}
                                language={worldForm.language}
                            />
                        ) : null}

                        {["locations", "characters", "background", "items", "equipment", "containers", "stacks"].includes(activeSection) ? (
                            <EntitySection
                                kind={activeSection}
                                data={entityData[activeSection]}
                                form={forms[activeSection]}
                                editing={editing[activeSection]}
                                lookups={lookups}
                                saving={saving}
                                worldReady={Boolean(worldId) || worldFormValid}
                                onChange={(field, value) => updateForm(activeSection, field, value)}
                                onSave={() => saveEntity(activeSection)}
                                onEdit={(entity) => beginEdit(activeSection, entity)}
                                onCreate={() => beginCreate(activeSection)}
                                onChooseCover={(entity) => setMediaPickerTarget({ kind: activeSection, id: entity.id })}
                                onRemoveCover={(entity) => handleRemoveCover(activeSection, entity.id)}
                                onCancelEdit={() => {
                                    setEditing((current) => ({ ...current, [activeSection]: null }));
                                    setForms((current) => ({ ...current, [activeSection]: { ...emptyForms[activeSection] } }));
                                }}
                                onDelete={(entity) => deleteEntity(activeSection, entity)}
                                coverRefreshKey={coverRefreshKey}
                            />
                        ) : null}
                    </div>
                </section>
            </div>

            {mediaPickerTarget ? (
                <MediaPickerModal
                    worldId={worldId}
                    onSelect={handleSelectCover}
                    onClose={() => setMediaPickerTarget(null)}
                />
            ) : null}
        </div>
    );
}

function EntitySection({ kind, data, form, editing, lookups, saving, worldReady, onChange, onSave, onEdit, onCreate, onChooseCover, onRemoveCover, onCancelEdit, onDelete, coverRefreshKey }) {
    const { t } = useTranslation();
    const formValid = isEntityFormValid(kind, form);

    return (
        <section>
            <div className="simulation-detail-subtabs world-editor-entity-list">
                <button
                    type="button"
                    className={`simulation-detail-subtab world-editor-create-tab${editing ? "" : " active"}`}
                    onClick={onCreate}
                >
                    {t("worldCreate.newEditor.createNew")}
                </button>
                {data.length === 0 ? (
                    <p className="simulation-details-empty-line">{t(`worldCreate.newEditor.empty.${kind}`)}</p>
                ) : (
                    data.map((entity) => (
                        <button
                            key={entity.id}
                            type="button"
                            className={`simulation-detail-subtab${editing?.id === entity.id ? " active" : ""}`}
                            onClick={() => onEdit(entity)}
                        >
                            {labelFor(entity, entity.id)}
                        </button>
                    ))
                )}
            </div>

            <div className="world-editor-form">
                <h3>{editing ? t("worldCreate.newEditor.editing", { name: labelFor(editing, editing.id) }) : t(`worldCreate.newEditor.create.${kind}`)}</h3>
                <CoverImageField
                    kind={kind}
                    sourceId={editing?.id}
                    refreshKey={coverRefreshKey}
                    disabled={!editing?.id || saving}
                    onChoose={() => onChooseCover(editing)}
                    onRemove={() => onRemoveCover(editing)}
                />
                <EntityFields kind={kind} form={form} lookups={lookups} onChange={onChange} />
                <div className="modal-actions inline-actions">
                    <button type="button" className="primary-button" disabled={saving || !worldReady || !formValid} onClick={onSave}>
                        {editing ? t("worldCreate.newEditor.updateEntity") : t("worldCreate.newEditor.saveEntity")}
                    </button>
                    {editing ? (
                        <>
                            <button type="button" className="secondary-button" onClick={onCancelEdit}>
                                {t("worldCreate.cancel")}
                            </button>
                            <button type="button" className="secondary-button danger-button" onClick={() => onDelete(editing)}>
                                {t("worldCreate.newEditor.deleteEntity")}
                            </button>
                        </>
                    ) : null}
                </div>
            </div>
        </section>
    );
}

function CoverImageField({ kind, sourceId, refreshKey, disabled, onChoose, onRemove }) {
    const { t } = useTranslation();
    const [failedImageUrl, setFailedImageUrl] = useState(null);
    const imageUrl = sourceId ? `${getCoverImageUrl(kind, sourceId)}?v=${refreshKey}` : null;
    const failed = Boolean(imageUrl && failedImageUrl === imageUrl);

    return (
        <div className="world-editor-cover-field">
            <FieldLabel label={t("worldCreate.newEditor.fields.coverImage")} required={false} />
            <div className="world-editor-cover-row">
                <div className="world-editor-cover-preview">
                    {imageUrl && !failed ? (
                        <img
                            src={imageUrl}
                            alt={t("worldCreate.newEditor.fields.coverImage")}
                            onError={() => setFailedImageUrl(imageUrl)}
                        />
                    ) : (
                        <span>
                            {sourceId
                                ? t("worldCreate.newEditor.noCoverImage")
                                : t("worldCreate.newEditor.saveBeforeCover")}
                        </span>
                    )}
                </div>
                <div className="world-editor-cover-actions">
                    <button type="button" className="secondary-button" disabled={disabled} onClick={onChoose}>
                        {t("worldCreate.newEditor.chooseCoverImage")}
                    </button>
                    <button type="button" className="secondary-button" disabled={disabled} onClick={onRemove}>
                        {t("worldCreate.newEditor.removeCoverImage")}
                    </button>
                </div>
            </div>
        </div>
    );
}

function EntityFields({ kind, form, lookups, onChange }) {
    const { t } = useTranslation();
    const isRequired = (name) => requiredFields[kind]?.includes(name) ?? false;
    const field = (name, options = {}) => (
        <TextField
            key={name}
            label={t(`worldCreate.newEditor.fields.${name}`)}
            value={form[name] ?? ""}
            onChange={(value) => onChange(name, value)}
            required={isRequired(name)}
            {...options}
        />
    );
    const area = (name) => (
        <TextArea key={name} label={t(`worldCreate.newEditor.fields.${name}`)} value={form[name] ?? ""} required={isRequired(name)} onChange={(value) => onChange(name, value)} />
    );

    if (kind === "locations") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                <SelectField label={t("worldCreate.newEditor.fields.parent_location_id")} value={form.parent_location_id} onChange={(value) => onChange("parent_location_id", value)} options={lookups.locations} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
            </>
        );
    }

    if (kind === "characters") {
        return (
            <>
                <CheckboxField label={t("worldCreate.newEditor.fields.user_controlled")} checked={form.user_controlled} onChange={(value) => onChange("user_controlled", value)} />
                {field("name", { required: true })}
                {field("age", { type: "number" })}
                {field("gender", { required: true })}
                {area("appearance")}
                {area("description")}
                {area("public_state")}
                {area("private_state")}
                {field("activity_name", { required: true })}
                <CheckboxField label={t("worldCreate.newEditor.fields.activity_interruptible")} checked={form.activity_interruptible} onChange={(value) => onChange("activity_interruptible", value)} />
                {field("activity_constraints")}
                <SelectField label={t("worldCreate.newEditor.fields.location_id")} value={form.location_id} onChange={(value) => onChange("location_id", value)} options={lookups.locations} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
                {field("position")}
            </>
        );
    }

    if (kind === "background") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                <SelectField label={t("worldCreate.newEditor.fields.location_id")} value={form.location_id} onChange={(value) => onChange("location_id", value)} options={lookups.locations} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
                {field("position")}
            </>
        );
    }

    if (kind === "items") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                <CheckboxField label={t("worldCreate.newEditor.fields.unique")} checked={form.unique} onChange={(value) => onChange("unique", value)} />
            </>
        );
    }

    if (kind === "equipment") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                {field("quality")}
                <RelationshipFields form={form} lookups={lookups} onChange={onChange} />
                <CheckboxField label={t("worldCreate.newEditor.fields.equipped")} checked={form.equipped} onChange={(value) => onChange("equipped", value)} />
                {field("equipped_position")}
            </>
        );
    }

    if (kind === "containers") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                <SelectField label={t("worldCreate.newEditor.fields.state")} value={form.state} onChange={(value) => onChange("state", value)} options={["hidden", "locked", "unlocked", "open"].map((id) => ({ id, name: id }))} />
                <RelationshipFields form={form} lookups={lookups} onChange={onChange} />
                {field("held_stack_ids")}
                <MultiSelectField label={t("worldCreate.newEditor.fields.held_equipment_ids")} value={form.held_equipment_ids} onChange={(value) => onChange("held_equipment_ids", value)} options={lookups.equipment} />
                <MultiSelectField label={t("worldCreate.newEditor.fields.held_container_ids")} value={form.held_container_ids} onChange={(value) => onChange("held_container_ids", value)} options={lookups.containers} />
                <MultiSelectField label={t("worldCreate.newEditor.fields.unlocking_item_ids")} value={form.unlocking_item_ids} onChange={(value) => onChange("unlocking_item_ids", value)} options={lookups.items} />
            </>
        );
    }

    return (
        <>
            <SelectField label={t("worldCreate.newEditor.fields.item_id")} value={form.item_id} onChange={(value) => onChange("item_id", value)} options={lookups.items} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
            {field("quantity", { type: "number" })}
            {field("quality")}
            <RelationshipFields form={form} lookups={lookups} onChange={onChange} />
        </>
    );
}

function RelationshipFields({ form, lookups, onChange }) {
    const { t } = useTranslation();

    return (
        <>
            <SelectField label={t("worldCreate.newEditor.fields.location_id")} value={form.location_id} onChange={(value) => onChange("location_id", value)} options={lookups.locations} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
            <TextField label={t("worldCreate.newEditor.fields.position")} value={form.position ?? ""} onChange={(value) => onChange("position", value)} />
            <SelectField label={t("worldCreate.newEditor.fields.owner_id")} value={form.owner_id} onChange={(value) => onChange("owner_id", value)} options={lookups.characters} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
            <SelectField label={t("worldCreate.newEditor.fields.holder_id")} value={form.holder_id} onChange={(value) => onChange("holder_id", value)} options={[...lookups.characters, ...lookups.containers]} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
        </>
    );
}

function FieldLabel({ label, required }) {
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

function TextField({ label, value, onChange, type = "text", required = false }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <input className="single-line-input" value={value} type={type} required={required} onChange={(event) => onChange(event.target.value)} />
        </label>
    );
}

function TextArea({ label, value, onChange, required = false }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <textarea className="multi-line-input" value={value} required={required} onChange={(event) => onChange(event.target.value)} />
        </label>
    );
}

function SelectField({ label, value, onChange, options, emptyLabel = null, required = false }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <select className="single-line-input" value={value ?? ""} required={required} onChange={(event) => onChange(event.target.value)}>
                {emptyLabel ? <option value="">{emptyLabel}</option> : null}
                {options.map((option) => (
                    <option key={option.id} value={option.id}>
                        {labelFor(option, option.id)}
                    </option>
                ))}
            </select>
        </label>
    );
}

function ComponentConfigMatrix({
    llmConfigs,
    embeddingConfigs,
    llmConfigsByComponent,
    embeddingConfigsByComponent,
    onChange,
}) {
    const { t } = useTranslation();

    return (
        <div className="world-editor-config-matrix">
            <div className="world-editor-config-matrix-header">
                <span>{t("worldCreate.newEditor.fields.component")}</span>
                <span>{t("worldCreate.newEditor.fields.llmConfig")}</span>
                <span>{t("worldCreate.newEditor.fields.embeddingConfig")}</span>
            </div>
            {simulatorComponents.map((component) => (
                <div className="world-editor-config-row" key={component}>
                    <div className="world-editor-component-name">
                        {t(`worldCreate.newEditor.components.${component}`, { defaultValue: component })}
                    </div>
                    <select
                        className="single-line-input"
                        value={llmConfigsByComponent[component] ?? ""}
                        onChange={(event) => onChange("llm", component, event.target.value)}
                    >
                        <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                        {llmConfigs.map((config) => (
                            <option key={config.id} value={config.id}>
                                {labelFor(config, config.id)}
                            </option>
                        ))}
                    </select>
                    <select
                        className="single-line-input"
                        value={embeddingConfigsByComponent[component] ?? ""}
                        onChange={(event) => onChange("embedding", component, event.target.value)}
                    >
                        <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                        {embeddingConfigs.map((config) => (
                            <option key={config.id} value={config.id}>
                                {labelFor(config, config.id)}
                            </option>
                        ))}
                    </select>
                </div>
            ))}
        </div>
    );
}

function MultiSelectField({ label, value, onChange, options, required = false }) {
    const selectedValues = Array.isArray(value)
        ? value
        : typeof value === "string"
          ? value.split(",").map((entry) => entry.trim()).filter(Boolean)
          : [];

    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <select
                className="single-line-input"
                multiple
                value={selectedValues}
                required={required}
                onChange={(event) =>
                    onChange(Array.from(event.target.selectedOptions).map((option) => option.value))
                }
            >
                {options.map((option) => (
                    <option key={option.id} value={option.id}>
                        {labelFor(option, option.id)}
                    </option>
                ))}
            </select>
        </label>
    );
}

function CheckboxField({ label, checked, onChange }) {
    return (
        <label className="checkbox-field world-editor-checkbox">
            <FieldLabel label={label} required={false} />
            <input type="checkbox" checked={Boolean(checked)} onChange={(event) => onChange(event.target.checked)} />
        </label>
    );
}
