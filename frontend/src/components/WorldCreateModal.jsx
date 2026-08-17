import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchAuthors } from "@/api/authors";
import {
    fetchAllTalkStatus,
    fetchEmbeddingConfigs,
    fetchImageConfigs,
    fetchLlmConfigs,
    fetchTtsConfigs,
    fetchWorldEmbeddingConfigs,
    fetchWorldImageConfigs,
    fetchWorldLlmConfigs,
    fetchWorldTtsConfig,
    imageChatComponents,
    imageComponents,
    setWorldEmbeddingConfigs,
    setWorldImageConfigs,
    setWorldLlmConfigs,
    setWorldTtsConfig,
    simulatorComponents,
} from "@/api/configurations";
import { deleteCoverImage, getCoverImageUrl, setCoverImage } from "@/api/media";
import { fetchCharacterTtsConfig, setCharacterTtsConfig } from "@/api/simulations";
import { createWorld, updateWorld } from "@/api/worlds";
import {
    createEvent,
    createLandmark,
    createMemory,
    createWorldBackgroundCharacter,
    createWorldCharacter,
    createWorldContainer,
    createWorldEquipment,
    createWorldItem,
    createWorldItemStack,
    createWorldLocation,
    createWorldTurn,
    deleteBackgroundCharacter,
    deleteCharacter,
    deleteContainer,
    deleteEquipment,
    deleteEvent,
    deleteItem,
    deleteLandmark,
    deleteLocation,
    deleteMemory,
    deleteWorldTurn,
    fetchWorldAuthor,
    fetchWorldBackgroundCharacters,
    fetchWorldCharacters,
    fetchWorldContainers,
    fetchWorldEquipment,
    fetchWorldEvents,
    fetchWorldItems,
    fetchWorldLandmarks,
    fetchWorldLocations,
    fetchWorldMemories,
    fetchWorldTurns,
    updateBackgroundCharacter,
    updateCharacter,
    updateContainer,
    updateEquipment,
    updateItem,
    updateLandmark,
    updateLocation,
    updateWorldAuthor,
    updateWorldTurn,
} from "@/api/worldEntities";
import { MediaPickerModal } from "@/components/MediaPickerModal";
import { PromptAssignmentEditor } from "@/components/PromptAssignmentEditor";
import { TurnContentEditor } from "@/components/TurnContentEditor";

const sections = [
    "world",
    "configs",
    "imageGeneration",
    "ttsGeneration",
    "prompts",
    "locations",
    "landmarks",
    "characters",
    "background",
    "items",
    "equipment",
    "containers",
    "stacks",
    "turns",
    "events",
    "memories",
];
const entitySections = ["locations", "landmarks", "characters", "background", "items", "equipment", "containers", "stacks"];
const narrativeSections = ["turns", "events", "memories"];

const TURN_TYPES = ["user_input", "system_response", "system_continue"];
const EVENT_INVOLVEMENTS = ["witness", "participate", "hear", "infer", "believe", "suspect"];
const MEMORY_SUPPORT_TYPES = ["direct", "inferred", "reported", "contradicts"];
const MEMORY_STANCES = ["remember", "infer", "believe", "doubt", "deny", "mistake"];
const MEMORY_SALIENCE = ["low", "medium", "high", "critical"];

const emptyTurnForm = { type: "system_response", content: "", start_time: "2000-01-01T00:00" };
const emptyEventForm = { name: "", summary: "", turn_ids: [], involved_characters: [] };
const emptyMemoryForm = {
    summary: "",
    keywords: "",
    event_id: "",
    support_type: "direct",
    character_links: [],
};
const emptyInvolvedCharacter = { character_id: "", involvement: "witness" };
const emptyCharacterLink = {
    character_id: "",
    confidence: "1",
    salience: "medium",
    behavioural_relevance: "",
    stance: "remember",
};

const entityDependencies = {
    landmarks: ["locations"],
    characters: ["locations"],
    background: ["locations", "landmarks"],
    equipment: ["locations", "characters", "containers"],
    containers: ["locations", "characters", "items", "equipment", "containers"],
    stacks: ["locations", "characters", "items", "containers"],
};

const requiredFields = {
    locations: ["name", "description"],
    landmarks: ["name", "description", "location_id"],
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
    landmarks: { name: "", description: "", location_id: "" },
    characters: {
        user_controlled: false,
        name: "",
        age: "0",
        gender: "",
        appearance: "",
        description: "",
        public_state: "",
        private_state: "",
        speech_style: "",
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
        metadata_author: world?.metadata?.author ?? "",
        metadata_author_url: world?.metadata?.author_url ?? "",
        metadata_resource_url: world?.metadata?.resource_url ?? "",
        metadata_comment: world?.metadata?.comment ?? "",
        metadata_version: world?.metadata?.version ?? "",
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
        metadata: {
            author: cleanText(form.metadata_author),
            author_url: cleanText(form.metadata_author_url),
            resource_url: cleanText(form.metadata_resource_url),
            comment: cleanText(form.metadata_comment),
            version: cleanText(form.metadata_version),
        },
    };
}

function emptyComponentConfigMap(components) {
    return Object.fromEntries(components.map((component) => [component, ""]));
}

function componentConfigMapFromAssignments(components, assignments) {
    return assignments.reduce((result, assignment) => {
        result[assignment.component] = assignment.config?.id ?? "";
        return result;
    }, emptyComponentConfigMap(components));
}

function componentAssignmentsFromMap(components, configsByComponent) {
    return components.map((component) => ({
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
    const [imageConfigs, setImageConfigs] = useState([]);
    const [ttsConfigs, setTtsConfigs] = useState([]);
    const [llmConfigsByComponent, setLlmConfigsByComponent] = useState(() => emptyComponentConfigMap(simulatorComponents));
    const [embeddingConfigsByComponent, setEmbeddingConfigsByComponent] = useState(() => emptyComponentConfigMap(simulatorComponents));
    const [imageLlmConfigsByComponent, setImageLlmConfigsByComponent] = useState(() => emptyComponentConfigMap(imageChatComponents));
    const [imageConfigsByComponent, setImageConfigsByComponent] = useState(() => emptyComponentConfigMap(imageComponents));
    const [ttsConfigId, setTtsConfigId] = useState("");
    const [locations, setLocations] = useState([]);
    const [landmarks, setLandmarks] = useState([]);
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
    const [imageConnectionsLoaded, setImageConnectionsLoaded] = useState(false);
    const [ttsConnectionLoaded, setTtsConnectionLoaded] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [configNotice, setConfigNotice] = useState(null);
    const [mediaPickerTarget, setMediaPickerTarget] = useState(null);
    const [coverRefreshKey, setCoverRefreshKey] = useState(0);
    const [worldTurns, setWorldTurns] = useState([]);
    const [worldEvents, setWorldEvents] = useState([]);
    const [worldMemories, setWorldMemories] = useState([]);
    const [turnForm, setTurnForm] = useState(() => ({ ...emptyTurnForm }));
    const [editingTurn, setEditingTurn] = useState(null);
    const [eventForm, setEventForm] = useState(() => ({ ...emptyEventForm }));
    const [memoryForm, setMemoryForm] = useState(() => ({ ...emptyMemoryForm }));

    const worldId = world?.id ?? initialWorld?.id ?? null;
    const worldFormValid = isWorldFormValid(worldForm);
    const loading = Boolean(loadingSections[activeSection]);

    const lookups = useMemo(
        () => ({
            locations,
            landmarks,
            characters,
            items,
            equipment,
            containers,
        }),
        [characters, containers, equipment, items, landmarks, locations],
    );

    const nextTurnSequence = worldTurns.length
        ? Math.max(...worldTurns.map((turn) => turn.sequence)) + 1
        : 1;

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
        } else if (kind === "landmarks") {
            setLandmarks(data);
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

        if (kind === "landmarks") {
            return fetchWorldLandmarks(id);
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

    const loadNarrativeSection = useCallback(
        async (kind, id = worldId, { force = false } = {}) => {
            if (!id || !narrativeSections.includes(kind)) {
                return;
            }

            if (loadedSections[kind] && !force) {
                return;
            }

            setLoadingSections((current) => ({ ...current, [kind]: true }));

            try {
                if (kind === "turns") {
                    setWorldTurns(await fetchWorldTurns(id));
                } else if (kind === "events") {
                    setWorldEvents(await fetchWorldEvents(id));
                } else {
                    setWorldMemories(await fetchWorldMemories(id));
                }
                setLoadedSections((current) => ({ ...current, [kind]: true }));
            } catch (err) {
                setError(err.message);
            } finally {
                setLoadingSections((current) => ({ ...current, [kind]: false }));
            }
        },
        [loadedSections, worldId],
    );

    useEffect(() => {
        if (!narrativeSections.includes(activeSection)) {
            return;
        }

        const loadTimer = window.setTimeout(() => {
            loadNarrativeSection(activeSection);
            if (activeSection === "events" || activeSection === "memories" || activeSection === "turns") {
                loadEntitySection("characters", worldId, { includeDependencies: false });
            }
            if (activeSection === "events") {
                loadNarrativeSection("turns");
            }
            if (activeSection === "memories") {
                loadNarrativeSection("events");
            }
        }, 0);

        return () => window.clearTimeout(loadTimer);
    }, [activeSection, loadEntitySection, loadNarrativeSection, worldId]);

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
                    setLlmConfigsByComponent(componentConfigMapFromAssignments(simulatorComponents, llmAssignments));
                    setEmbeddingConfigsByComponent(
                        componentConfigMapFromAssignments(simulatorComponents, embeddingAssignments),
                    );
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

    useEffect(() => {
        if (activeSection !== "imageGeneration" || !worldId || imageConnectionsLoaded) {
            return;
        }

        let cancelled = false;

        async function loadWorldImageConnections() {
            setLoadingSections((current) => ({ ...current, imageGeneration: true }));
            try {
                const [llms, images, llmAssignments, imageAssignments] = await Promise.all([
                    fetchLlmConfigs(),
                    fetchImageConfigs(),
                    fetchWorldLlmConfigs(worldId),
                    fetchWorldImageConfigs(worldId),
                ]);

                if (!cancelled) {
                    setLlmConfigs(llms);
                    setImageConfigs(images);
                    setImageLlmConfigsByComponent(
                        componentConfigMapFromAssignments(imageChatComponents, llmAssignments),
                    );
                    setImageConfigsByComponent(
                        componentConfigMapFromAssignments(imageComponents, imageAssignments),
                    );
                    setImageConnectionsLoaded(true);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoadingSections((current) => ({ ...current, imageGeneration: false }));
                }
            }
        }

        loadWorldImageConnections();

        return () => {
            cancelled = true;
        };
    }, [activeSection, imageConnectionsLoaded, worldId]);

    useEffect(() => {
        if (activeSection !== "ttsGeneration" || !worldId || ttsConnectionLoaded) {
            return;
        }

        let cancelled = false;

        async function loadWorldTtsConnection() {
            setLoadingSections((current) => ({ ...current, ttsGeneration: true }));
            try {
                const [ttsBackends, ttsConfig] = await Promise.all([
                    fetchTtsConfigs(),
                    fetchWorldTtsConfig(worldId).catch(() => null),
                ]);

                if (!cancelled) {
                    setTtsConfigs(ttsBackends);
                    setTtsConfigId(ttsConfig?.id ?? "");
                    setTtsConnectionLoaded(true);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoadingSections((current) => ({ ...current, ttsGeneration: false }));
                }
            }
        }

        loadWorldTtsConnection();

        return () => {
            cancelled = true;
        };
    }, [activeSection, ttsConnectionLoaded, worldId]);

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

    function updateImageComponentConfig(kind, component, configId) {
        const setter = kind === "llm" ? setImageLlmConfigsByComponent : setImageConfigsByComponent;

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
                    setWorldLlmConfigs(id, componentAssignmentsFromMap(simulatorComponents, llmConfigsByComponent)),
                    setWorldEmbeddingConfigs(
                        id,
                        componentAssignmentsFromMap(simulatorComponents, embeddingConfigsByComponent),
                    ),
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

    async function saveImageConfigurations() {
        setError(null);
        setConfigNotice(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            await Promise.all(
                [
                    setWorldLlmConfigs(id, componentAssignmentsFromMap(imageChatComponents, imageLlmConfigsByComponent)),
                    setWorldImageConfigs(id, componentAssignmentsFromMap(imageComponents, imageConfigsByComponent)),
                ],
            );
            setImageConnectionsLoaded(true);
            setConfigNotice(t("worldCreate.newEditor.configSaved"));
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function saveTtsConfiguration() {
        setError(null);
        setConfigNotice(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            if (ttsConfigId) {
                await setWorldTtsConfig(id, ttsConfigId);
            }
            setTtsConnectionLoaded(true);
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
            } else if (kind === "landmarks") {
                savedEntity = editingEntity
                    ? await updateLandmark(editingEntity.id, form)
                    : await createLandmark(form.location_id, form);
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
            } else if (kind === "landmarks") {
                await deleteLandmark(entity.id);
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

    function updateTurnForm(field, value) {
        setTurnForm((current) => {
            // content's shape depends on which side of the user/system boundary type is on
            // (plain text vs NarrationProposal blocks JSON - see TurnContentEditor) - crossing
            // that boundary mid-edit must reset content, or the wrong editor would render the
            // other shape's raw value.
            if (field === "type" && (current.type === "user_input") !== (value === "user_input")) {
                return { ...current, type: value, content: "" };
            }
            return { ...current, [field]: value };
        });
    }

    function startEditTurn(turn) {
        setEditingTurn(turn);
        setTurnForm({
            type: turn.type,
            content: turn.content,
            start_time: (turn.start_time ?? "").slice(0, 16),
        });
    }

    function cancelEditTurn() {
        setEditingTurn(null);
        setTurnForm({ ...emptyTurnForm });
    }

    async function saveTurn() {
        setError(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            if (editingTurn) {
                await updateWorldTurn(id, editingTurn.id, turnForm);
            } else {
                await createWorldTurn(id, { ...turnForm, sequence: nextTurnSequence });
            }
            await loadNarrativeSection("turns", id, { force: true });
            setTurnForm({ ...emptyTurnForm });
            setEditingTurn(null);
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function deleteTurn(turn) {
        if (!window.confirm(t("worldCreate.newEditor.confirmDelete", { name: t("worldCreate.newEditor.turnTitle", { number: turn.sequence }) }))) {
            return;
        }

        try {
            setSaving(true);
            await deleteWorldTurn(worldId, turn.id);
            await loadNarrativeSection("turns", worldId, { force: true });
            if (editingTurn?.id === turn.id) {
                cancelEditTurn();
            }
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    function updateEventForm(field, value) {
        setEventForm((current) => ({ ...current, [field]: value }));
    }

    function addInvolvedCharacter() {
        setEventForm((current) => ({
            ...current,
            involved_characters: [...current.involved_characters, { ...emptyInvolvedCharacter }],
        }));
    }

    function updateInvolvedCharacter(index, field, value) {
        setEventForm((current) => ({
            ...current,
            involved_characters: current.involved_characters.map((row, rowIndex) =>
                rowIndex === index ? { ...row, [field]: value } : row,
            ),
        }));
    }

    function removeInvolvedCharacter(index) {
        setEventForm((current) => ({
            ...current,
            involved_characters: current.involved_characters.filter((_, rowIndex) => rowIndex !== index),
        }));
    }

    async function saveEvent() {
        setError(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            await createEvent({
                name: eventForm.name,
                summary: eventForm.summary,
                turn_ids: eventForm.turn_ids,
                involved_characters: eventForm.involved_characters.filter((row) => row.character_id),
            });
            await loadNarrativeSection("events", id, { force: true });
            setEventForm({ ...emptyEventForm });
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function removeEvent(event) {
        if (!window.confirm(t("worldCreate.newEditor.confirmDelete", { name: event.name || event.id }))) {
            return;
        }

        try {
            setSaving(true);
            await deleteEvent(event.id);
            await loadNarrativeSection("events", worldId, { force: true });
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    function updateMemoryForm(field, value) {
        setMemoryForm((current) => ({ ...current, [field]: value }));
    }

    function addCharacterLink() {
        setMemoryForm((current) => ({
            ...current,
            character_links: [...current.character_links, { ...emptyCharacterLink }],
        }));
    }

    function updateCharacterLink(index, field, value) {
        setMemoryForm((current) => ({
            ...current,
            character_links: current.character_links.map((row, rowIndex) =>
                rowIndex === index ? { ...row, [field]: value } : row,
            ),
        }));
    }

    function removeCharacterLink(index) {
        setMemoryForm((current) => ({
            ...current,
            character_links: current.character_links.filter((_, rowIndex) => rowIndex !== index),
        }));
    }

    async function saveMemory() {
        setError(null);

        try {
            setSaving(true);
            const id = await ensureWorldSaved();
            await createMemory({
                summary: memoryForm.summary,
                keywords: memoryForm.keywords,
                event_id: memoryForm.event_id,
                support_type: memoryForm.support_type,
                character_links: memoryForm.character_links
                    .filter((row) => row.character_id)
                    .map((row) => ({
                        character_id: row.character_id,
                        confidence: Number.parseFloat(row.confidence) || 0,
                        salience: row.salience,
                        behavioural_relevance: cleanText(row.behavioural_relevance),
                        stance: row.stance,
                    })),
            });
            await loadNarrativeSection("memories", id, { force: true });
            setMemoryForm({ ...emptyMemoryForm });
            setSaving(false);
        } catch (err) {
            setError(err.message);
            setSaving(false);
        }
    }

    async function removeMemory(memory) {
        if (!window.confirm(t("worldCreate.newEditor.confirmDelete", { name: memory.summary || memory.id }))) {
            return;
        }

        try {
            setSaving(true);
            await deleteMemory(memory.id);
            await loadNarrativeSection("memories", worldId, { force: true });
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
        landmarks,
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

                                <h3>{t("worldCreate.newEditor.metadataSectionTitle")}</h3>
                                <TextField label={t("worldCreate.newEditor.fields.metadataAuthor")} value={worldForm.metadata_author} onChange={(value) => updateWorldField("metadata_author", value)} />
                                <TextField label={t("worldCreate.newEditor.fields.metadataAuthorUrl")} value={worldForm.metadata_author_url} onChange={(value) => updateWorldField("metadata_author_url", value)} />
                                <TextField label={t("worldCreate.newEditor.fields.metadataResourceUrl")} value={worldForm.metadata_resource_url} onChange={(value) => updateWorldField("metadata_resource_url", value)} />
                                <TextField label={t("worldCreate.newEditor.fields.metadataVersion")} value={worldForm.metadata_version} onChange={(value) => updateWorldField("metadata_version", value)} />
                                <TextArea label={t("worldCreate.newEditor.fields.metadataComment")} value={worldForm.metadata_comment} onChange={(value) => updateWorldField("metadata_comment", value)} />
                                {(world?.creation_time ?? initialWorld?.creation_time) ? (
                                    <ReadOnlyField
                                        label={t("worldCreate.newEditor.fields.creationTime")}
                                        value={new Date(world?.creation_time ?? initialWorld?.creation_time).toLocaleString()}
                                    />
                                ) : null}

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

                        {activeSection === "imageGeneration" ? (
                            <section className="world-editor-form">
                                <ComponentConfigMatrix
                                    llmConfigs={llmConfigs}
                                    embeddingConfigs={imageConfigs}
                                    llmConfigsByComponent={imageLlmConfigsByComponent}
                                    embeddingConfigsByComponent={imageConfigsByComponent}
                                    embeddingLabel="imageConfig"
                                    components={imageChatComponents}
                                    embeddingComponents={imageComponents}
                                    onChange={updateImageComponentConfig}
                                />
                                {configNotice ? (
                                    <p className="simulation-details-empty-line">{configNotice}</p>
                                ) : null}
                                <div className="modal-actions inline-actions">
                                    <button type="button" className="primary-button" disabled={saving || !worldFormValid} onClick={saveImageConfigurations}>
                                        {saving ? t("worldCreate.saving") : t("worldCreate.newEditor.saveConfigurations")}
                                    </button>
                                    <button type="button" className="secondary-button" onClick={finish}>
                                        {t("worldCreate.newEditor.done")}
                                    </button>
                                </div>
                            </section>
                        ) : null}

                        {activeSection === "ttsGeneration" ? (
                            <section className="world-editor-form">
                                <SelectField
                                    label={t("worldCreate.newEditor.fields.ttsConfig")}
                                    value={ttsConfigId}
                                    onChange={setTtsConfigId}
                                    options={ttsConfigs}
                                    emptyLabel={t("worldCreate.newEditor.emptySelect")}
                                />
                                {configNotice ? (
                                    <p className="simulation-details-empty-line">{configNotice}</p>
                                ) : null}
                                <div className="modal-actions inline-actions">
                                    <button type="button" className="primary-button" disabled={saving || !worldFormValid} onClick={saveTtsConfiguration}>
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

                        {["locations", "landmarks", "characters", "background", "items", "equipment", "containers", "stacks"].includes(activeSection) ? (
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

                        {activeSection === "characters" && editing.characters ? (
                            <WorldCharacterVoiceEditor worldId={worldId} characterId={editing.characters.id} />
                        ) : null}

                        {activeSection === "turns" ? (
                            <TurnSection
                                turns={worldTurns}
                                characters={characters}
                                form={turnForm}
                                editing={editingTurn}
                                nextSequence={nextTurnSequence}
                                saving={saving}
                                worldReady={Boolean(worldId) || worldFormValid}
                                onChange={updateTurnForm}
                                onSave={saveTurn}
                                onEdit={startEditTurn}
                                onCreate={cancelEditTurn}
                                onCancelEdit={cancelEditTurn}
                                onDelete={deleteTurn}
                            />
                        ) : null}

                        {activeSection === "events" ? (
                            <EventSection
                                events={worldEvents}
                                turns={worldTurns}
                                characters={characters}
                                form={eventForm}
                                saving={saving}
                                worldReady={Boolean(worldId) || worldFormValid}
                                onChange={updateEventForm}
                                onAddInvolvement={addInvolvedCharacter}
                                onUpdateInvolvement={updateInvolvedCharacter}
                                onRemoveInvolvement={removeInvolvedCharacter}
                                onSave={saveEvent}
                                onDelete={removeEvent}
                            />
                        ) : null}

                        {activeSection === "memories" ? (
                            <MemorySection
                                memories={worldMemories}
                                events={worldEvents}
                                characters={characters}
                                form={memoryForm}
                                saving={saving}
                                worldReady={Boolean(worldId) || worldFormValid}
                                onChange={updateMemoryForm}
                                onAddCharacterLink={addCharacterLink}
                                onUpdateCharacterLink={updateCharacterLink}
                                onRemoveCharacterLink={removeCharacterLink}
                                onSave={saveMemory}
                                onDelete={removeMemory}
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

function enumOptions(t, prefix, values) {
    return values.map((value) => ({ id: value, name: t(`${prefix}.${value}`) }));
}

function turnContentHasText(type, content) {
    if (type === "user_input") {
        return content.trim().length > 0;
    }
    try {
        const parsed = JSON.parse(content);
        return Array.isArray(parsed?.blocks) && parsed.blocks.some((block) => (block.text ?? "").trim().length > 0);
    } catch {
        return content.trim().length > 0;
    }
}

function turnContentPreview(type, content) {
    if (type === "user_input") {
        return content;
    }
    try {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed?.blocks)) {
            return parsed.blocks
                .map((block) => (block.type === "speech" ? `${block.character_name ?? "?"}: "${block.text}"` : block.text))
                .join(" ");
        }
    } catch {
        // Legacy plain-text content - show as-is below.
    }
    return content;
}

function TurnSection({ turns, characters, form, editing, nextSequence, saving, worldReady, onChange, onSave, onEdit, onCreate, onCancelEdit, onDelete }) {
    const { t } = useTranslation();
    const formValid = Boolean(form.type) && turnContentHasText(form.type, form.content) && Boolean(form.start_time);
    const orderedTurns = [...turns].sort((a, b) => a.sequence - b.sequence);

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
            </div>
            <div className="data-preset-list">
                {orderedTurns.length === 0 ? (
                    <p className="simulation-details-empty-line">{t("worldCreate.newEditor.empty.turns")}</p>
                ) : (
                    orderedTurns.map((turn) => (
                        <button
                            key={turn.id}
                            type="button"
                            className={`data-preset-item data-preset-item-button${editing?.id === turn.id ? " active" : ""}`}
                            onClick={() => onEdit(turn)}
                        >
                            <div className="prompt-message-header">
                                <span className="data-preset-item-title">
                                    {t("worldCreate.newEditor.turnTitle", { number: turn.sequence })}
                                </span>
                                <span className="world-editor-required-badge">
                                    {t(`worldCreate.newEditor.turnTypes.${turn.type}`)}
                                </span>
                            </div>
                            <p>{turnContentPreview(turn.type, turn.content)}</p>
                        </button>
                    ))
                )}
            </div>

            <div className="world-editor-form">
                <h3>
                    {editing
                        ? t("worldCreate.newEditor.turnTitle", { number: editing.sequence })
                        : t("worldCreate.newEditor.create.turns")}
                </h3>
                <label className="form-field inline-field">
                    <FieldLabel label={t("worldCreate.newEditor.fields.sequence")} required />
                    <input
                        className="single-line-input"
                        value={editing ? editing.sequence : nextSequence}
                        disabled
                        readOnly
                    />
                </label>
                <SelectField
                    label={t("worldCreate.newEditor.fields.turn_type")}
                    value={form.type}
                    onChange={(value) => onChange("type", value)}
                    options={enumOptions(t, "worldCreate.newEditor.turnTypes", TURN_TYPES)}
                    required
                />
                <label className="form-field inline-field">
                    <FieldLabel label={t("worldCreate.newEditor.fields.content")} required />
                    <TurnContentEditor
                        content={form.content}
                        characters={characters}
                        type={form.type}
                        onChange={(value) => onChange("content", value)}
                    />
                </label>
                <TextField
                    label={t("worldCreate.newEditor.fields.start_time")}
                    type="datetime-local"
                    value={form.start_time}
                    onChange={(value) => onChange("start_time", value)}
                    required
                />
                <div className="modal-actions inline-actions">
                    <button
                        type="button"
                        className="primary-button"
                        disabled={saving || !worldReady || !formValid}
                        onClick={onSave}
                    >
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

function InvolvedCharactersEditor({ rows, characters, onAdd, onUpdate, onRemove }) {
    const { t } = useTranslation();

    return (
        <div className="data-values-editor">
            <div className="data-values-header">
                <span>{t("worldCreate.newEditor.fields.involved_characters")}</span>
                <button type="button" className="secondary-button" disabled={characters.length === 0} onClick={onAdd}>
                    {t("worldCreate.add")}
                </button>
            </div>
            {rows.map((row, index) => (
                <div className="list-editor-row" key={index}>
                    <label>{t("worldCreate.newEditor.fields.character")}</label>
                    <select
                        className="single-line-input"
                        value={row.character_id}
                        onChange={(event) => onUpdate(index, "character_id", event.target.value)}
                    >
                        <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                        {characters.map((character) => (
                            <option key={character.id} value={character.id}>
                                {character.name}
                            </option>
                        ))}
                    </select>
                    <label>{t("worldCreate.newEditor.fields.involvement")}</label>
                    <select
                        className="single-line-input"
                        value={row.involvement}
                        onChange={(event) => onUpdate(index, "involvement", event.target.value)}
                    >
                        {EVENT_INVOLVEMENTS.map((value) => (
                            <option key={value} value={value}>
                                {t(`worldCreate.newEditor.eventInvolvements.${value}`)}
                            </option>
                        ))}
                    </select>
                    <button type="button" className="secondary-button" onClick={() => onRemove(index)}>
                        {t("worldCreate.remove")}
                    </button>
                </div>
            ))}
        </div>
    );
}

function EventSection({
    events,
    turns,
    characters,
    form,
    saving,
    worldReady,
    onChange,
    onAddInvolvement,
    onUpdateInvolvement,
    onRemoveInvolvement,
    onSave,
    onDelete,
}) {
    const { t } = useTranslation();
    const formValid = form.name.trim().length > 0 && form.summary.trim().length > 0 && form.turn_ids.length > 0;
    const turnsById = new Map(turns.map((turn) => [turn.id, turn]));

    return (
        <section>
            <div className="data-preset-list">
                {events.length === 0 ? (
                    <p className="simulation-details-empty-line">{t("worldCreate.newEditor.empty.events")}</p>
                ) : (
                    events.map((event) => (
                        <div className="data-preset-item" key={event.id}>
                            <div className="prompt-message-header">
                                <span className="data-preset-item-title">{event.name}</span>
                                <button
                                    type="button"
                                    className="secondary-button danger-button"
                                    onClick={() => onDelete(event)}
                                >
                                    {t("worldCreate.newEditor.deleteEntity")}
                                </button>
                            </div>
                            <p>{event.summary}</p>
                        </div>
                    ))
                )}
            </div>

            <div className="world-editor-form">
                <h3>{t("worldCreate.newEditor.create.events")}</h3>
                <TextField
                    label={t("worldCreate.newEditor.fields.name")}
                    value={form.name}
                    onChange={(value) => onChange("name", value)}
                    required
                />
                <TextArea
                    label={t("worldCreate.newEditor.fields.summary")}
                    value={form.summary}
                    onChange={(value) => onChange("summary", value)}
                    required
                />
                <MultiSelectField
                    label={t("worldCreate.newEditor.fields.turn_ids")}
                    value={form.turn_ids}
                    onChange={(value) => onChange("turn_ids", value)}
                    options={[...turnsById.values()]
                        .sort((a, b) => a.sequence - b.sequence)
                        .map((turn) => ({
                            id: turn.id,
                            name: t("worldCreate.newEditor.turnTitle", { number: turn.sequence }),
                        }))}
                    required
                />
                <InvolvedCharactersEditor
                    rows={form.involved_characters}
                    characters={characters}
                    onAdd={onAddInvolvement}
                    onUpdate={onUpdateInvolvement}
                    onRemove={onRemoveInvolvement}
                />
                <div className="modal-actions inline-actions">
                    <button
                        type="button"
                        className="primary-button"
                        disabled={saving || !worldReady || !formValid}
                        onClick={onSave}
                    >
                        {t("worldCreate.newEditor.saveEntity")}
                    </button>
                </div>
            </div>
        </section>
    );
}

function CharacterLinksEditor({ rows, characters, onAdd, onUpdate, onRemove }) {
    const { t } = useTranslation();

    return (
        <div className="data-values-editor">
            <div className="data-values-header">
                <span>{t("worldCreate.newEditor.fields.character_links")}</span>
                <button type="button" className="secondary-button" disabled={characters.length === 0} onClick={onAdd}>
                    {t("worldCreate.add")}
                </button>
            </div>
            {rows.map((row, index) => (
                <div className="initial-map-editor" key={index}>
                    <div className="list-editor-row">
                        <label>{t("worldCreate.newEditor.fields.character")}</label>
                        <select
                            className="single-line-input"
                            value={row.character_id}
                            onChange={(event) => onUpdate(index, "character_id", event.target.value)}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {characters.map((character) => (
                                <option key={character.id} value={character.id}>
                                    {character.name}
                                </option>
                            ))}
                        </select>
                        <button type="button" className="secondary-button" onClick={() => onRemove(index)}>
                            {t("worldCreate.remove")}
                        </button>
                    </div>
                    <div className="list-editor-row">
                        <label>{t("worldCreate.newEditor.fields.confidence")}</label>
                        <input
                            className="single-line-input"
                            type="number"
                            min="0"
                            max="1"
                            step="0.05"
                            value={row.confidence}
                            onChange={(event) => onUpdate(index, "confidence", event.target.value)}
                        />
                        <label>{t("worldCreate.newEditor.fields.salience")}</label>
                        <select
                            className="single-line-input"
                            value={row.salience}
                            onChange={(event) => onUpdate(index, "salience", event.target.value)}
                        >
                            {MEMORY_SALIENCE.map((value) => (
                                <option key={value} value={value}>
                                    {t(`worldCreate.newEditor.memorySalience.${value}`)}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="list-editor-row">
                        <label>{t("worldCreate.newEditor.fields.stance")}</label>
                        <select
                            className="single-line-input"
                            value={row.stance}
                            onChange={(event) => onUpdate(index, "stance", event.target.value)}
                        >
                            {MEMORY_STANCES.map((value) => (
                                <option key={value} value={value}>
                                    {t(`worldCreate.newEditor.memoryStances.${value}`)}
                                </option>
                            ))}
                        </select>
                    </div>
                    <label className="form-field inline-field">
                        <span>{t("worldCreate.newEditor.fields.behavioural_relevance")}</span>
                        <input
                            className="single-line-input"
                            value={row.behavioural_relevance}
                            onChange={(event) => onUpdate(index, "behavioural_relevance", event.target.value)}
                        />
                    </label>
                </div>
            ))}
        </div>
    );
}

function MemorySection({
    memories,
    events,
    characters,
    form,
    saving,
    worldReady,
    onChange,
    onAddCharacterLink,
    onUpdateCharacterLink,
    onRemoveCharacterLink,
    onSave,
    onDelete,
}) {
    const { t } = useTranslation();
    const formValid =
        form.summary.trim().length > 0 &&
        Boolean(form.event_id) &&
        form.character_links.some((row) => row.character_id);

    return (
        <section>
            <div className="data-preset-list">
                {memories.length === 0 ? (
                    <p className="simulation-details-empty-line">{t("worldCreate.newEditor.empty.memories")}</p>
                ) : (
                    memories.map((memory) => (
                        <div className="data-preset-item" key={memory.id}>
                            <div className="prompt-message-header">
                                <span className="data-preset-item-title">{memory.summary}</span>
                                <button
                                    type="button"
                                    className="secondary-button danger-button"
                                    onClick={() => onDelete(memory)}
                                >
                                    {t("worldCreate.newEditor.deleteEntity")}
                                </button>
                            </div>
                            <p>{memory.keywords.join(", ")}</p>
                        </div>
                    ))
                )}
            </div>

            <div className="world-editor-form">
                <h3>{t("worldCreate.newEditor.create.memories")}</h3>
                <TextArea
                    label={t("worldCreate.newEditor.fields.summary")}
                    value={form.summary}
                    onChange={(value) => onChange("summary", value)}
                    required
                />
                <TextField
                    label={t("worldCreate.newEditor.fields.keywords")}
                    value={form.keywords}
                    onChange={(value) => onChange("keywords", value)}
                />
                <SelectField
                    label={t("worldCreate.newEditor.fields.event_id")}
                    value={form.event_id}
                    onChange={(value) => onChange("event_id", value)}
                    options={events.map((event) => ({ id: event.id, name: event.name }))}
                    emptyLabel={t("worldCreate.newEditor.emptySelect")}
                    required
                />
                <SelectField
                    label={t("worldCreate.newEditor.fields.support_type")}
                    value={form.support_type}
                    onChange={(value) => onChange("support_type", value)}
                    options={enumOptions(t, "worldCreate.newEditor.memorySupportTypes", MEMORY_SUPPORT_TYPES)}
                    required
                />
                <CharacterLinksEditor
                    rows={form.character_links}
                    characters={characters}
                    onAdd={onAddCharacterLink}
                    onUpdate={onUpdateCharacterLink}
                    onRemove={onRemoveCharacterLink}
                />
                <div className="modal-actions inline-actions">
                    <button
                        type="button"
                        className="primary-button"
                        disabled={saving || !worldReady || !formValid}
                        onClick={onSave}
                    >
                        {t("worldCreate.newEditor.saveEntity")}
                    </button>
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

    if (kind === "landmarks") {
        return (
            <>
                {field("name", { required: true })}
                {area("description")}
                <SelectField label={t("worldCreate.newEditor.fields.location_id")} value={form.location_id} onChange={(value) => onChange("location_id", value)} options={lookups.locations} emptyLabel={t("worldCreate.newEditor.emptySelect")} required />
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
                {area("speech_style")}
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
                <SelectField label={t("worldCreate.newEditor.fields.landmark_id")} value={form.landmark_id} onChange={(value) => onChange("landmark_id", value)} options={lookups.landmarks} emptyLabel={t("worldCreate.newEditor.emptySelect")} />
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

function ReadOnlyField({ label, value }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={false} />
            <input className="single-line-input" value={value} disabled readOnly />
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
    components = simulatorComponents,
    embeddingComponents = null,
    embeddingLabel = "embeddingConfig",
}) {
    const { t } = useTranslation();

    return (
        <div className="world-editor-config-matrix">
            <div className="world-editor-config-matrix-header">
                <span>{t("worldCreate.newEditor.fields.component")}</span>
                <span>{t("worldCreate.newEditor.fields.llmConfig")}</span>
                <span>{t(`worldCreate.newEditor.fields.${embeddingLabel}`)}</span>
            </div>
            {components.map((component) => (
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
                    {embeddingComponents === null || embeddingComponents.includes(component) ? (
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
                    ) : (
                        <span className="simulation-details-empty-line">
                            {t("simulationDetails.imageGeneration.noImageModelNeeded")}
                        </span>
                    )}
                </div>
            ))}
        </div>
    );
}

function WorldCharacterVoiceEditor({ worldId, characterId }) {
    const { t } = useTranslation();
    const [voice, setVoice] = useState("");
    const [backendConfigId, setBackendConfigId] = useState(null);
    const [backendConnectionId, setBackendConnectionId] = useState(null);
    const [voiceOptions, setVoiceOptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfig() {
            try {
                setLoading(true);
                setError(null);

                const [ttsConfig, backend] = await Promise.all([
                    fetchCharacterTtsConfig(characterId).catch(() => null),
                    fetchWorldTtsConfig(worldId).catch(() => null),
                ]);

                if (!cancelled) {
                    setVoice(ttsConfig?.character_voice ?? "");
                    setBackendConfigId(backend?.id ?? null);
                    setBackendConnectionId(backend?.connection?.id ?? null);
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

        loadConfig();

        return () => {
            cancelled = true;
        };
    }, [worldId, characterId]);

    // A character can only speak with a voice AllTalk actually has loaded, fetched live from
    // the world's configured TTS backend (see WorldTtsConfigEditor / the "Voice generation" tab).
    useEffect(() => {
        if (!backendConnectionId) {
            return undefined;
        }

        let cancelled = false;

        async function loadVoices() {
            try {
                const status = await fetchAllTalkStatus(backendConnectionId);
                if (!cancelled) {
                    setVoiceOptions(status.voices ?? []);
                }
            } catch {
                if (!cancelled) {
                    setVoiceOptions([]);
                }
            }
        }

        loadVoices();

        return () => {
            cancelled = true;
        };
    }, [backendConnectionId]);

    async function saveVoice() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            const payload = { character_voice: voice || null };
            if (backendConfigId) {
                payload.backend_config_id = backendConfigId;
            }
            const saved = await setCharacterTtsConfig(characterId, payload);
            setVoice(saved.character_voice ?? "");
            setNotice(t("worldCreate.newEditor.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return null;
    }

    return (
        <section className="world-editor-form">
            <h3>{t("worldCreate.newEditor.characterVoice")}</h3>
            {error ? <p className="form-error">{error}</p> : null}
            <div className="compact-form-field">
                <label htmlFor="world-character-voice-input">{t("worldCreate.newEditor.fields.voice")}</label>
                <select
                    id="world-character-voice-input"
                    className="single-line-input"
                    value={voice}
                    disabled={!backendConnectionId}
                    onChange={(event) => setVoice(event.target.value)}
                >
                    <option value="">{t("worldCreate.newEditor.noVoice")}</option>
                    {Array.from(new Set([...voiceOptions, ...(voice ? [voice] : [])])).map((option) => (
                        <option key={option} value={option}>
                            {option}
                        </option>
                    ))}
                </select>
            </div>
            {!backendConnectionId ? (
                <p className="simulation-details-empty-line">{t("worldCreate.newEditor.noVoiceHint")}</p>
            ) : null}
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveVoice}>
                    {saving ? t("worldCreate.saving") : t("worldCreate.newEditor.saveConfigurations")}
                </button>
            </div>
        </section>
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
