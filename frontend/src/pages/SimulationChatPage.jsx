import { useCallback, useEffect, useMemo, useRef, useState, startTransition } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
    fetchEmbeddingConfigs,
    fetchLlmConfigs,
    fetchSimulationEmbeddingConfigs,
    fetchSimulationLlmConfigs,
    setSimulationEmbeddingConfigs,
    setSimulationLlmConfigs,
    simulatorComponents,
} from "@/api/configurations";
import {
    fetchCharacterInventory,
    fetchCharacterEmotion,
    fetchSimulation,
    fetchSimulationBackgroundCharacters,
    fetchSimulationCharacters,
    fetchSimulationContainers,
    fetchSimulationEquipment,
    fetchSimulationEvents,
    fetchSimulationItems,
    fetchSimulationIntents,
    fetchSimulationLandmarks,
    fetchSimulationLocations,
    fetchSimulationMemories,
    fetchSimulationRecords,
    fetchSimulationStacks,
    fetchSimulations,
    getSimulationRunUrl,
    getSimulationBackgroundCharacterImageUrl,
    getSimulationCharacterImageUrl,
    getSimulationContainerImageUrl,
    getSimulationEquipmentImageUrl,
    getSimulationItemImageUrl,
    getSimulationLandmarkImageUrl,
    getSimulationLocationImageUrl,
    getSimulationStackImageUrl,
    getSimulationCoverUrl,
    sendSimulationInput,
} from "@/api/simulations";
import { PromptAssignmentEditor } from "@/components/PromptAssignmentEditor";
import placeholderImage from "@/assets/placeholder/world.svg";
import characterPlaceholderImage from "@/assets/placeholder/character.svg";
import locationPlaceholderImage from "@/assets/placeholder/location.svg";
import entityPlaceholderImage from "@/assets/placeholder/banner.svg";

const simulationLimit = 24;
const recordLimit = 50;
const emptyList = [];
const detailSections = [
    "basic",
    "configs",
    "prompts",
    "locations",
    "landmarks",
    "characters",
    "background",
    "items",
    "stacks",
    "equipment",
    "containers",
    "turns",
    "events",
    "memories",
    "intents",
];
const entityDetailSections = [
    "landmarks",
    "background",
    "items",
    "stacks",
    "equipment",
    "containers",
    "turns",
    "events",
    "memories",
    "intents",
];

function useOptionalImage(imageUrl, fallbackSrc) {
    const [loadedImage, setLoadedImage] = useState({ sourceUrl: null, objectUrl: null });

    useEffect(() => {
        if (!imageUrl) {
            return undefined;
        }

        const controller = new AbortController();
        let objectUrl = null;

        async function loadImage() {
            try {
                const response = await fetch(imageUrl, { signal: controller.signal });

                if (!response.ok) {
                    return;
                }

                const blob = await response.blob();
                objectUrl = URL.createObjectURL(blob);
                setLoadedImage({ sourceUrl: imageUrl, objectUrl });
            } catch (err) {
                if (err.name !== "AbortError") {
                    setLoadedImage((current) =>
                        current.sourceUrl === imageUrl ? { sourceUrl: null, objectUrl: null } : current,
                    );
                }
            }
        }

        loadImage();

        return () => {
            controller.abort();

            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
            }
        };
    }, [imageUrl]);

    return loadedImage.sourceUrl === imageUrl ? loadedImage.objectUrl : fallbackSrc;
}

function sortRecords(records) {
    return [...records].sort((a, b) => a.turn_number - b.turn_number || String(a.id).localeCompare(String(b.id)));
}

function isUserRecord(record) {
    return record.type === "user_input";
}

function narrationBlocksFromValue(value) {
    if (Array.isArray(value?.blocks)) {
        return value.blocks;
    }

    if (Array.isArray(value)) {
        return value;
    }

    return null;
}

function narrationTextFromBlocks(blocks) {
    return (blocks ?? [])
        .map((block) => {
            if (block.type === "speech") {
                const speaker = block.character_name || block.character_id || "";
                return speaker ? `${speaker}: "${block.text}"` : block.text;
            }

            return block.text;
        })
        .filter(Boolean)
        .join("\n\n");
}

function validateInputMarkup(value) {
    let mode = null;
    let emphasisOpen = false;
    let buffer = "";

    for (let index = 0; index < value.length; index += 1) {
        const char = value[index];
        const nextTwo = value.slice(index, index + 2);

        if (char === "\\") {
            if (mode) {
                buffer += char;
            }
            if (index + 1 < value.length) {
                if (mode) {
                    buffer += value[index + 1];
                }
                index += 1;
            }
            continue;
        }

        if (nextTwo === "**") {
            emphasisOpen = !emphasisOpen;
            if (mode) {
                buffer += nextTwo;
            }
            index += 1;
            continue;
        }

        if (char === '"') {
            if (mode === "internal") {
                return "Internal dialog cannot contain speech quotes.";
            }
            if (mode === "speech") {
                if (buffer.trim().length === 0) {
                    return "Speech quotes cannot be empty.";
                }
                mode = null;
                buffer = "";
            } else {
                mode = "speech";
                buffer = "";
            }
            continue;
        }

        if (char === "*") {
            if (mode === "speech") {
                return "Speech cannot contain internal-dialog markers.";
            }
            if (mode === "internal") {
                if (buffer.trim().length === 0) {
                    return "Internal dialog markers cannot be empty.";
                }
                mode = null;
                buffer = "";
            } else {
                mode = "internal";
                buffer = "";
            }
            continue;
        }

        if (mode) {
            buffer += char;
        }
    }

    if (mode === "speech") {
        return 'Speech quote is not closed with ".';
    }
    if (mode === "internal") {
        return "Internal dialog is not closed with *.";
    }
    if (emphasisOpen) {
        return "Emphasis is not closed with **.";
    }

    return null;
}

function formatUserText(text) {
    const parts = [];
    let mode = null;
    let buffer = "";

    function pushBuffer(kind) {
        if (!buffer) {
            return;
        }
        parts.push({ kind, text: buffer });
        buffer = "";
    }

    for (let index = 0; index < text.length; index += 1) {
        const char = text[index];
        const nextTwo = text.slice(index, index + 2);

        if (nextTwo === "**" && mode !== "speech" && mode !== "internal") {
            pushBuffer("text");
            mode = mode === "emphasis" ? null : "emphasis";
            index += 1;
            continue;
        }

        if (char === '"' && mode !== "internal") {
            pushBuffer(mode || "text");
            mode = mode === "speech" ? null : "speech";
            continue;
        }

        if (char === "*" && mode !== "speech" && text[index + 1] !== "*") {
            pushBuffer(mode || "text");
            mode = mode === "internal" ? null : "internal";
            continue;
        }

        buffer += char;
    }

    pushBuffer(mode || "text");
    return parts;
}

function FormattedUserText({ text }) {
    return (
        <p>
            {formatUserText(text).map((part, index) => {
                if (part.kind === "speech") {
                    return <q key={`${part.kind}-${index}`}>{part.text}</q>;
                }
                if (part.kind === "internal") {
                    return <em key={`${part.kind}-${index}`}>{part.text}</em>;
                }
                if (part.kind === "emphasis") {
                    return <strong key={`${part.kind}-${index}`}>{part.text}</strong>;
                }
                return <span key={`${part.kind}-${index}`}>{part.text}</span>;
            })}
        </p>
    );
}

function stageFromStateChunk(chunk) {
    if (chunk?.memory_summary_proposal) {
        return "memory_summarizer";
    }

    if (chunk?.committed_turn || chunk?.state_commit_proposal) {
        return "state_committer";
    }

    if (chunk?.narration) {
        return "narrator";
    }

    if (chunk?.character_action_coordination || chunk?.user_action_coordination) {
        return "scene_coordinator";
    }

    if ((chunk?.character_action_validations ?? []).length > 0 || chunk?.user_action_validation) {
        return "action_validator";
    }

    if ((chunk?.character_actions ?? []).length > 0) {
        return "character_simulator";
    }

    if (chunk?.input_interpretation) {
        return "input_interpreter";
    }

    return null;
}

function SimulationAvatar({ simulation, className = "chat-avatar" }) {
    const imageSrc = useOptionalImage(
        simulation?.id ? getSimulationCoverUrl(simulation.id) : null,
        placeholderImage,
    );

    return (
        <img
            src={imageSrc}
            alt={simulation?.name ?? ""}
            className={className}
        />
    );
}

function SimulationConversationItem({ simulation, preview }) {
    const { t } = useTranslation();

    return (
        <NavLink
            to={`/simulations/${simulation.id}`}
            className={({ isActive }) => `conversation-item${isActive ? " active" : ""}`}
        >
            <SimulationAvatar simulation={simulation} className="conversation-avatar" />
            <div className="conversation-summary">
                <span className="conversation-title">{simulation.name}</span>
                <span className="conversation-preview">
                    {preview || t("simulationChat.noPreview")}
                </span>
            </div>
        </NavLink>
    );
}

function CharacterAvatar({ simulationId, character, label }) {
    const imageSrc = useOptionalImage(
        simulationId && character?.id
            ? getSimulationCharacterImageUrl({ simulationId, characterId: character.id })
            : null,
        characterPlaceholderImage,
    );

    return (
        <img
            src={imageSrc}
            alt={label ?? ""}
            className="chat-avatar"
        />
    );
}

function NarrationBlocks({ blocks, simulationId, charactersById }) {
    return (
        <>
            {blocks.map((block, index) => {
                if (block.type === "speech") {
                    const character = charactersById[String(block.character_id)];
                    const authorName = block.character_name || character?.name || block.character_id;

                    return (
                        <article
                            key={`${block.type}-${block.character_id}-${index}`}
                            className="chat-message character"
                        >
                            <CharacterAvatar
                                simulationId={simulationId}
                                character={character}
                                label={authorName}
                            />
                            <div className="chat-message-content">
                                <div className="chat-message-author">{authorName}</div>
                                <div className="chat-bubble character-speech">
                                    <p>{block.text}</p>
                                </div>
                            </div>
                        </article>
                    );
                }

                return (
                    <article
                        key={`${block.type}-${index}`}
                        className="chat-message narration-block"
                    >
                        <div className="chat-narration-card">
                            <p>{block.text}</p>
                        </div>
                    </article>
                );
            })}
        </>
    );
}

function ChatRecord({ record, simulation, charactersById, userCharacter }) {
    const { t } = useTranslation();
    const userRecord = isUserRecord(record);
    const authorName = userRecord ? (userCharacter?.name ?? t("simulationChat.userCharacterFallback")) : simulation?.name;
    const blocks = !userRecord ? narrationBlocksFromValue(record.narration_blocks) : null;

    if (blocks?.length > 0) {
        return (
            <NarrationBlocks
                blocks={blocks}
                simulationId={simulation?.id}
                charactersById={charactersById}
            />
        );
    }

    return (
        <article className={`chat-message${userRecord ? " user" : " simulation"}`}>
            {userRecord ? (
                <CharacterAvatar
                    simulationId={simulation?.id}
                    character={userCharacter}
                    label={authorName}
                />
            ) : (
                <SimulationAvatar simulation={simulation} />
            )}
            <div className="chat-message-content">
                <div className="chat-message-author">{authorName}</div>
                <div className="chat-bubble">
                    {userRecord ? <FormattedUserText text={record.narration} /> : <p>{record.narration}</p>}
                </div>
            </div>
        </article>
    );
}

function TypingIndicator() {
    return (
        <span className="typing-state">
            <span className="typing-indicator" aria-label="Typing">
                <span />
                <span />
                <span />
            </span>
        </span>
    );
}

function StreamingChatRecord({ message, blocks = [], error, active, stageName, simulation, charactersById }) {
    const { t } = useTranslation();
    const hasBlocks = blocks.length > 0;
    const hasMessage = message.length > 0 || hasBlocks;
    const stageLabel = stageName
        ? t(`worldCreate.newEditor.components.${stageName}`, { defaultValue: stageName })
        : null;

    if (hasBlocks) {
        return (
            <>
                <NarrationBlocks
                    blocks={blocks}
                    simulationId={simulation?.id}
                    charactersById={charactersById}
                />
                {active && stageLabel ? (
                    <div className="chat-stage-line streaming-stage-line">{stageLabel}</div>
                ) : null}
                {!active && error ? <p className="chat-stream-error">{error}</p> : null}
            </>
        );
    }

    return (
        <article className="chat-message simulation">
            <SimulationAvatar simulation={simulation} />
            <div className="chat-message-content">
                <div className="chat-message-author">
                    {simulation?.name ?? t("simulationChat.selectedFallback")}
                </div>
                <div className="chat-bubble">
                    {hasMessage ? <p>{message}</p> : active ? <TypingIndicator /> : null}
                    {!active && error ? <p className="chat-stream-error">{error}</p> : null}
                </div>
                {active && stageLabel ? (
                    <div className="chat-stage-line">{stageLabel}</div>
                ) : null}
            </div>
        </article>
    );
}

function CharacterImage({ simulationId, character, className = "simulation-details-cover" }) {
    const imageSrc = useOptionalImage(
        simulationId && character?.id
            ? getSimulationCharacterImageUrl({ simulationId, characterId: character.id })
            : null,
        characterPlaceholderImage,
    );

    return (
        <img
            src={imageSrc}
            alt={character?.name ?? ""}
            className={className}
        />
    );
}

function LocationImage({ simulationId, location, className = "simulation-details-cover" }) {
    const imageSrc = useOptionalImage(
        simulationId && location?.id
            ? getSimulationLocationImageUrl({ simulationId, locationId: location.id })
            : null,
        locationPlaceholderImage,
    );

    return (
        <img
            src={imageSrc}
            alt={location ? formatLocation(location, "") : ""}
            className={className}
        />
    );
}

function EntityImage({ imageUrl, fallbackSrc = entityPlaceholderImage, alt = "", className = "simulation-details-cover" }) {
    const imageSrc = useOptionalImage(
        imageUrl,
        fallbackSrc,
    );

    return (
        <img
            src={imageSrc}
            alt={alt}
            className={className}
        />
    );
}

function formatBoolean(value, t) {
    return value ? t("simulationDetails.boolean.yes") : t("simulationDetails.boolean.no");
}

function formatLocation(location, emptyValue) {
    if (!location) {
        return emptyValue;
    }

    return [location.primary_location, location.detailed_location, location.scene]
        .filter(Boolean)
        .join(": ") || emptyValue;
}

function configLabel(config, fallback) {
    return config?.name || config?.model || config?.id || fallback;
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

function DetailLink({ children, onClick }) {
    return (
        <button type="button" className="simulation-details-link" onClick={onClick}>
            {children}
        </button>
    );
}

function ObjectList({ title, values, emptyValue }) {
    const entries = Object.entries(values ?? {});

    if (entries.length === 0) {
        return null;
    }

    return (
        <section className="simulation-details-object-list">
            <h4>{title}</h4>
            <div className="simulation-details-chip-list">
                {entries.map(([key, value]) => (
                    <div key={key} className="simulation-details-chip">
                        <span>{key}</span>
                        <strong>
                            {Array.isArray(value) ? value.join(", ") : (value ?? emptyValue)}
                        </strong>
                    </div>
                ))}
            </div>
        </section>
    );
}

function entityTitle(entity) {
    return entity?.name || entity?.summary || entity?.content || entity?.id || "";
}

function describeEntity(entity) {
    return entity?.description || entity?.summary || entity?.content || "";
}

function entityRows(entity, t) {
    return Object.entries(entity ?? {})
        .filter(([key, value]) => {
            if (["attributes", "stats", "embedding"].includes(key)) {
                return false;
            }
            return value !== null && value !== undefined && typeof value !== "object";
        })
        .map(([key, value]) => ({
            label: t(`simulationDetails.genericFields.${key}`, { defaultValue: key.replaceAll("_", " ") }),
            value: String(value),
        }));
}

function GenericEntityPanel({ section, entity, emptyText, imageUrl, fallbackImage }) {
    const { t } = useTranslation();

    if (!entity) {
        return <p className="status-text">{emptyText}</p>;
    }

    return (
        <>
            <div className="simulation-details-hero">
                {imageUrl ? (
                    <EntityImage
                        imageUrl={imageUrl}
                        fallbackSrc={fallbackImage}
                        alt={entityTitle(entity)}
                    />
                ) : null}
                <div className="simulation-details-summary">
                    <h3>{entityTitle(entity)}</h3>
                    <p>{describeEntity(entity) || t("simulationDetails.noDescription")}</p>
                </div>
            </div>

            <div className="simulation-details-separator" />

            <dl className="simulation-details-grid">
                {entityRows(entity, t).map((row) => (
                    <div key={`${section}-${row.label}`} className="simulation-details-row">
                        <dt>{row.label}</dt>
                        <dd>{row.value || t("simulationDetails.emptyValue")}</dd>
                    </div>
                ))}
            </dl>

            <ObjectList
                title={t("simulationDetails.genericFields.attributes")}
                values={entity.attributes}
                emptyValue={t("simulationDetails.emptyValue")}
            />
            <ObjectList
                title={t("simulationDetails.genericFields.stats")}
                values={entity.stats}
                emptyValue={t("simulationDetails.emptyValue")}
            />
        </>
    );
}

function EntitySubtabs({ entities, selectedEntity, emptyText, onSelect }) {
    if (entities.length === 0) {
        return <p className="simulation-details-empty-line">{emptyText}</p>;
    }

    return (
        <div className="simulation-detail-subtabs" role="tablist">
            {entities.map((entity) => (
                <button
                    key={entity.id}
                    type="button"
                    className={`simulation-detail-subtab${selectedEntity?.id === entity.id ? " active" : ""}`}
                    onClick={() => onSelect(entity.id)}
                >
                    {entityTitle(entity)}
                </button>
            ))}
        </div>
    );
}

function InventoryList({ title, entries, emptyText, renderMeta }) {
    return (
        <section className="simulation-details-inventory-section">
            <h4>{title}</h4>
            {entries.length === 0 ? (
                <p className="simulation-details-empty-line">{emptyText}</p>
            ) : (
                <div className="simulation-details-inventory-list">
                    {entries.map((entry) => (
                        <article
                            key={entry.id ?? entry.stack_id ?? entry.item_id}
                            className="simulation-details-inventory-card"
                        >
                            <div className="simulation-details-inventory-card-header">
                                <h5>{entry.name}</h5>
                                <span>{renderMeta(entry)}</span>
                            </div>
                            <p>{entry.description}</p>
                            {entry.quality ? (
                                <div className="simulation-details-inventory-quality">
                                    {entry.quality}
                                </div>
                            ) : null}
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}

function CharacterInventory({ inventory }) {
    const { t } = useTranslation();
    const safeInventory = inventory ?? { stacks: [], equipment: [], containers: [] };

    return (
        <section className="simulation-details-inventory">
            <h4>{t("simulationDetails.characterFields.inventory")}</h4>
            <InventoryList
                title={t("simulationDetails.inventory.stacks")}
                entries={safeInventory.stacks ?? []}
                emptyText={t("simulationDetails.inventory.emptyStacks")}
                renderMeta={(stack) =>
                    stack.unique
                        ? t("simulationDetails.inventory.unique")
                        : t("simulationDetails.inventory.quantity", { quantity: stack.quantity })
                }
            />
            <InventoryList
                title={t("simulationDetails.inventory.equipment")}
                entries={safeInventory.equipment ?? []}
                emptyText={t("simulationDetails.inventory.emptyEquipment")}
                renderMeta={(equipment) =>
                    equipment.equipped
                        ? t("simulationDetails.inventory.equipped", {
                              position: equipment.equipped_position ?? "",
                          })
                        : t("simulationDetails.inventory.held")
                }
            />
            <InventoryList
                title={t("simulationDetails.inventory.containers")}
                entries={safeInventory.containers ?? []}
                emptyText={t("simulationDetails.inventory.emptyContainers")}
                renderMeta={(container) =>
                    t(`worldCreate.enums.containerState.${container.state}`, {
                        defaultValue: container.state,
                    })
                }
            />
        </section>
    );
}

function LocationEntities({ entities }) {
    const { t } = useTranslation();

    return (
        <section className="simulation-details-inventory">
            <h4>{t("simulationDetails.locationFields.entities")}</h4>
            {(entities ?? []).length === 0 ? (
                <p className="simulation-details-empty-line">
                    {t("simulationDetails.locationFields.noEntities")}
                </p>
            ) : (
                <div className="simulation-details-inventory-list">
                    {entities.map((entity) => (
                        <article key={entity.id} className="simulation-details-inventory-card">
                            <div className="simulation-details-inventory-card-header">
                                <h5>{entity.name}</h5>
                                <span>{entity.type}</span>
                            </div>
                            <p>{entity.description}</p>
                            <div className="simulation-details-inventory-quality">
                                {entity.status}
                            </div>
                            {entity.interactions?.length > 0 ? (
                                <div className="simulation-details-entity-interactions">
                                    {entity.interactions.map((interaction) => (
                                        <span key={interaction}>{interaction}</span>
                                    ))}
                                </div>
                            ) : null}
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}

function SimulationConfigEditor({ simulationId }) {
    const { t } = useTranslation();
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [embeddingConfigs, setEmbeddingConfigs] = useState([]);
    const [llmConfigsByComponent, setLlmConfigsByComponent] = useState(() => emptyComponentConfigMap());
    const [embeddingConfigsByComponent, setEmbeddingConfigsByComponent] = useState(() => emptyComponentConfigMap());
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfigurations() {
            try {
                setLoading(true);
                setError(null);

                const [llms, embeddings, llmAssignments, embeddingAssignments] = await Promise.all([
                    fetchLlmConfigs(),
                    fetchEmbeddingConfigs(),
                    fetchSimulationLlmConfigs(simulationId),
                    fetchSimulationEmbeddingConfigs(simulationId),
                ]);

                if (!cancelled) {
                    setLlmConfigs(llms);
                    setEmbeddingConfigs(embeddings);
                    setLlmConfigsByComponent(componentConfigMapFromAssignments(llmAssignments));
                    setEmbeddingConfigsByComponent(componentConfigMapFromAssignments(embeddingAssignments));
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

        loadConfigurations();

        return () => {
            cancelled = true;
        };
    }, [simulationId]);

    function updateComponentConfig(kind, component, configId) {
        const setter = kind === "llm" ? setLlmConfigsByComponent : setEmbeddingConfigsByComponent;

        setter((current) => ({
            ...current,
            [component]: configId,
        }));
    }

    async function saveConfigurations() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            await Promise.all([
                setSimulationLlmConfigs(simulationId, componentAssignmentsFromMap(llmConfigsByComponent)),
                setSimulationEmbeddingConfigs(
                    simulationId,
                    componentAssignmentsFromMap(embeddingConfigsByComponent),
                ),
            ]);
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("simulationDetails.configLoading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
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
                            onChange={(event) => updateComponentConfig("llm", component, event.target.value)}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {llmConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {configLabel(config, config.id)}
                                </option>
                            ))}
                        </select>
                        <select
                            className="single-line-input"
                            value={embeddingConfigsByComponent[component] ?? ""}
                            onChange={(event) =>
                                updateComponentConfig("embedding", component, event.target.value)
                            }
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {embeddingConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {configLabel(config, config.id)}
                                </option>
                            ))}
                        </select>
                    </div>
                ))}
            </div>
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveConfigurations}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

function SimulationDetailsModal({
    simulation,
    characters,
    locations,
    entities,
    inventory,
    emotion,
    activeSection,
    selectedCharacterId,
    selectedLocationId,
    selectedEntityIds,
    onActiveSectionChange,
    onSelectedCharacterIdChange,
    onSelectedLocationIdChange,
    onSelectedEntityIdChange,
    onClose,
}) {
    const { t } = useTranslation();
    const selectedCharacter =
        characters.find((character) => character.id === selectedCharacterId) ?? characters[0] ?? null;
    const selectedCharacterLocationId = selectedCharacter?.location_id ?? selectedCharacter?.location ?? null;
    const selectedLocation = selectedCharacter
        ? locations.find((location) => location.id === selectedCharacterLocationId)
        : null;
    const selectedLocationDetail =
        locations.find((location) => location.id === selectedLocationId) ?? locations[0] ?? null;
    const selectedEntity = entityDetailSections.includes(activeSection)
        ? (entities[activeSection] ?? []).find((entity) => entity.id === selectedEntityIds[activeSection]) ??
          (entities[activeSection] ?? [])[0] ??
          null
        : null;

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    if (!simulation) {
        return null;
    }

    function selectLocation(locationId) {
        onSelectedLocationIdChange(locationId);
        onActiveSectionChange("locations");
    }

    const detailsTitle =
        activeSection === "characters" && selectedCharacter
            ? selectedCharacter.name
            : activeSection === "locations" && selectedLocationDetail
              ? formatLocation(selectedLocationDetail, t("simulationDetails.tabs.locations"))
              : selectedEntity
                ? entityTitle(selectedEntity)
                : activeSection === "configs"
                    ? t("simulationDetails.tabs.configs")
                    : activeSection === "prompts"
                      ? t("simulationDetails.tabs.prompts")
                  : simulation.name;

    const basicRows = [
        { label: t("simulationDetails.fields.id"), value: simulation.id },
        { label: t("simulationDetails.fields.name"), value: simulation.name },
        { label: t("simulationDetails.fields.language"), value: simulation.language },
        { label: t("simulationDetails.fields.actForUser"), value: formatBoolean(simulation.act_for_user, t) },
        { label: t("simulationDetails.fields.enableTts"), value: formatBoolean(simulation.enable_tts, t) },
        {
            label: t("simulationDetails.fields.enableImageGeneration"),
            value: formatBoolean(simulation.enable_image_generation, t),
        },
        {
            label: t("simulationDetails.fields.emotionEnabled"),
            value: formatBoolean(simulation.emotion_enabled, t),
        },
    ];
    const characterRows = selectedCharacter
        ? [
              { label: t("simulationDetails.characterFields.id"), value: selectedCharacter.id },
              { label: t("simulationDetails.characterFields.gender"), value: selectedCharacter.gender },
              { label: t("simulationDetails.characterFields.age"), value: selectedCharacter.age },
              {
                  label: t("simulationDetails.characterFields.location"),
                  value: selectedLocation ? (
                      <DetailLink onClick={() => selectLocation(selectedLocation.id)}>
                          {formatLocation(selectedLocation, t("simulationDetails.emptyValue"))}
                      </DetailLink>
                  ) : (
                      t("simulationDetails.emptyValue")
                  ),
              },
              {
                  label: t("simulationDetails.characterFields.userControlled"),
                  value: formatBoolean(selectedCharacter.user_controlled, t),
              },
          ]
        : [];
    const locationRows = selectedLocationDetail
        ? [
              { label: t("simulationDetails.locationFields.id"), value: selectedLocationDetail.id },
              {
                  label: t("simulationDetails.locationFields.primaryLocation"),
                  value: selectedLocationDetail.primary_location,
              },
              {
                  label: t("simulationDetails.locationFields.detailedLocation"),
                  value: selectedLocationDetail.detailed_location,
              },
              { label: t("simulationDetails.locationFields.scene"), value: selectedLocationDetail.scene },
          ]
        : [];
    const selectedEntityImageUrl = (() => {
        if (!selectedEntity?.id) {
            return null;
        }

        if (activeSection === "landmarks") {
            return getSimulationLandmarkImageUrl(selectedEntity.id);
        }
        if (activeSection === "background") {
            return getSimulationBackgroundCharacterImageUrl(selectedEntity.id);
        }
        if (activeSection === "items") {
            return getSimulationItemImageUrl(selectedEntity.id);
        }
        if (activeSection === "stacks") {
            return getSimulationStackImageUrl(selectedEntity.id);
        }
        if (activeSection === "equipment") {
            return getSimulationEquipmentImageUrl(selectedEntity.id);
        }
        if (activeSection === "containers") {
            return getSimulationContainerImageUrl(selectedEntity.id);
        }
        return null;
    })();

    const selectedEntityFallback =
        activeSection === "background"
            ? characterPlaceholderImage
            : activeSection === "landmarks"
              ? locationPlaceholderImage
              : entityPlaceholderImage;

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="simulation-details-modal world-editor-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="simulation-details-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <aside className="simulation-details-nav" aria-label={t("simulationDetails.navLabel")}>
                    <div className="simulation-details-nav-title">
                        {t("simulationDetails.title")}
                    </div>
                    {detailSections.map((section) => (
                        <button
                            key={section}
                            type="button"
                            className={`simulation-details-nav-item${activeSection === section ? " active" : ""}`}
                            onClick={() => onActiveSectionChange(section)}
                        >
                            {t(`simulationDetails.tabs.${section}`, {
                                defaultValue: t(`worldCreate.newEditor.tabs.${section}`, { defaultValue: section }),
                            })}
                        </button>
                    ))}
                </aside>

                <section className="simulation-details-content">
                    <header className="simulation-details-header">
                        <div>
                            <p className="simulation-details-eyebrow">
                                {t(`simulationDetails.tabs.${activeSection}`)}
                            </p>
                            <h2 id="simulation-details-title">{detailsTitle}</h2>
                        </div>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("simulationDetails.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </header>

                    <div className="simulation-details-body">
                        {activeSection === "characters" ? (
                            <div className="simulation-detail-subtabs" role="tablist">
                                {characters.map((character) => (
                                    <button
                                        key={character.id}
                                        type="button"
                                        className={`simulation-detail-subtab${
                                            selectedCharacter?.id === character.id ? " active" : ""
                                        }`}
                                        onClick={() => onSelectedCharacterIdChange(character.id)}
                                    >
                                        {character.name}
                                    </button>
                                ))}
                            </div>
                        ) : null}
                        {activeSection === "locations" ? (
                            <div className="simulation-detail-subtabs" role="tablist">
                                {locations.map((location) => (
                                    <button
                                        key={location.id}
                                        type="button"
                                        className={`simulation-detail-subtab${
                                            selectedLocationDetail?.id === location.id ? " active" : ""
                                        }`}
                                        onClick={() => onSelectedLocationIdChange(location.id)}
                                    >
                                        {location.scene || t("simulationDetails.locationFields.location")}
                                    </button>
                                ))}
                            </div>
                        ) : null}
                        {entityDetailSections.includes(activeSection) ? (
                            <EntitySubtabs
                                entities={entities[activeSection] ?? []}
                                selectedEntity={selectedEntity}
                                emptyText={t(`simulationDetails.empty.${activeSection}`, {
                                    defaultValue: t("simulationDetails.emptySection"),
                                })}
                                onSelect={(entityId) => onSelectedEntityIdChange(activeSection, entityId)}
                            />
                        ) : null}

                        {activeSection === "configs" ? (
                            <SimulationConfigEditor simulationId={simulation.id} />
                        ) : activeSection === "prompts" ? (
                            <PromptAssignmentEditor sourceType="simulation" sourceId={simulation.id} />
                        ) : entityDetailSections.includes(activeSection) ? (
                            <GenericEntityPanel
                                section={activeSection}
                                entity={selectedEntity}
                                emptyText={t(`simulationDetails.empty.${activeSection}`, {
                                    defaultValue: t("simulationDetails.emptySection"),
                                })}
                                imageUrl={selectedEntityImageUrl}
                                fallbackImage={selectedEntityFallback}
                            />
                        ) : activeSection === "locations" ? (
                            selectedLocationDetail ? (
                                <>
                                    <div className="simulation-details-hero">
                                        <LocationImage
                                            simulationId={simulation.id}
                                            location={selectedLocationDetail}
                                        />
                                        <div className="simulation-details-summary">
                                            <h3>
                                                {formatLocation(
                                                    selectedLocationDetail,
                                                    t("simulationDetails.locationFields.location"),
                                                )}
                                            </h3>
                                            <p>
                                                {selectedLocationDetail.description ||
                                                    t("simulationDetails.noDescription")}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="simulation-details-separator" />

                                    <dl className="simulation-details-grid">
                                        {locationRows.map((row) => (
                                            <div key={row.label} className="simulation-details-row">
                                                <dt>{row.label}</dt>
                                                <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                            </div>
                                        ))}
                                    </dl>

                                    <ObjectList
                                        title={t("simulationDetails.locationFields.attributes")}
                                        values={selectedLocationDetail.attributes}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <ObjectList
                                        title={t("simulationDetails.locationFields.stats")}
                                        values={selectedLocationDetail.stats}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <LocationEntities entities={selectedLocationDetail.entities} />
                                </>
                            ) : (
                                <p className="status-text">{t("simulationDetails.noLocations")}</p>
                            )
                        ) : activeSection === "characters" ? (
                            selectedCharacter ? (
                                <>
                                    <div className="simulation-details-hero">
                                        <CharacterImage
                                            simulationId={simulation.id}
                                            character={selectedCharacter}
                                        />
                                        <div className="simulation-details-summary">
                                            <h3>{selectedCharacter.name}</h3>
                                            <p>
                                                {selectedCharacter.description ||
                                                    t("simulationDetails.noDescription")}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="simulation-details-separator" />

                                    <dl className="simulation-details-grid">
                                        {characterRows.map((row) => (
                                            <div key={row.label} className="simulation-details-row">
                                                <dt>{row.label}</dt>
                                                <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                            </div>
                                        ))}
                                    </dl>

                                    <div className="simulation-details-separator" />

                                    <div className="simulation-details-text-grid">
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.appearance")}</h4>
                                            <p>{selectedCharacter.appearance || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.publicState")}</h4>
                                            <p>{selectedCharacter.public_state || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.privateState")}</h4>
                                            <p>{selectedCharacter.private_state || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                    </div>

                                    <ObjectList
                                        title={t("simulationDetails.characterFields.attributes")}
                                        values={selectedCharacter.attributes}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <ObjectList
                                        title={t("simulationDetails.characterFields.stats")}
                                        values={selectedCharacter.stats}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <CharacterInventory inventory={inventory} />
                                    {emotion ? (
                                        <ObjectList
                                            title={t("simulationDetails.characterFields.emotion")}
                                            values={emotion.effective}
                                            emptyValue={t("simulationDetails.emptyValue")}
                                        />
                                    ) : null}
                                </>
                            ) : (
                                <p className="status-text">{t("simulationDetails.noCharacters")}</p>
                            )
                        ) : (
                            <>
                                <div className="simulation-details-hero">
                                    <SimulationAvatar
                                        simulation={simulation}
                                        className="simulation-details-cover"
                                    />
                                    <div className="simulation-details-summary">
                                        <h3>{simulation.name}</h3>
                                        <p>
                                            {simulation.description || t("simulationDetails.noDescription")}
                                        </p>
                                    </div>
                                </div>

                                <div className="simulation-details-separator" />

                                <dl className="simulation-details-grid">
                                    {basicRows.map((row) => (
                                        <div key={row.label} className="simulation-details-row">
                                            <dt>{row.label}</dt>
                                            <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                        </div>
                                    ))}
                                </dl>
                            </>
                        )}
                    </div>
                </section>
            </div>
        </div>
    );
}

export function SimulationChatPage() {
    const { t } = useTranslation();
    const { simulationId } = useParams();
    const recordsEndRef = useRef(null);
    const eventSourceRef = useRef(null);
    const composerInputRef = useRef(null);
    const streamErrorRef = useRef(null);
    const streamReceivedNarrationRef = useRef(false);
    const [simulations, setSimulations] = useState([]);
    const [simulationDetails, setSimulationDetails] = useState({});
    const [characterCache, setCharacterCache] = useState({});
    const [locationCache, setLocationCache] = useState({});
    const [entityCache, setEntityCache] = useState({});
    const [inventoryCache, setInventoryCache] = useState({});
    const [emotionCache, setEmotionCache] = useState({});
    const [previews, setPreviews] = useState({});
    const [records, setRecords] = useState([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState(null);
    const [streamingRecord, setStreamingRecord] = useState(null);
    const [loading, setLoading] = useState(true);
    const [recordLoading, setRecordLoading] = useState(true);
    const [error, setError] = useState(null);
    const [recordError, setRecordError] = useState(null);
    const [detailsOpen, setDetailsOpen] = useState(false);
    const [detailsSection, setDetailsSection] = useState("basic");
    const [selectedCharacterIds, setSelectedCharacterIds] = useState({});
    const [selectedLocationIds, setSelectedLocationIds] = useState({});
    const [selectedEntityIds, setSelectedEntityIds] = useState({});

    const listedSimulation = useMemo(
        () => simulations.find((simulation) => String(simulation.id) === String(simulationId)),
        [simulationId, simulations],
    );
    const selectedSimulation = simulationDetails[simulationId] ?? listedSimulation;
    const selectedCharacters = characterCache[simulationId] ?? emptyList;
    const selectedCharactersById = useMemo(
        () => Object.fromEntries(selectedCharacters.map((character) => [String(character.id), character])),
        [selectedCharacters],
    );
    const selectedLocations = locationCache[simulationId] ?? [];
    const selectedEntities = entityCache[simulationId] ?? {};
    const userCharacter =
        selectedCharacters.find((character) => character.user_controlled) ?? selectedCharacters[0] ?? null;
    const selectedCharacterId = selectedCharacterIds[simulationId] ?? selectedCharacters[0]?.id ?? null;
    const selectedLocationId = selectedLocationIds[simulationId] ?? selectedLocations[0]?.id ?? null;
    const selectedEntityIdsForSimulation = selectedEntityIds[simulationId] ?? {};
    const selectedInventory = selectedCharacterId
        ? inventoryCache[`${simulationId}:${selectedCharacterId}`]
        : null;
    const selectedEmotion = selectedCharacterId
        ? emotionCache[`${simulationId}:${selectedCharacterId}`]
        : null;
    const inputFormatError = useMemo(
        () => (input.trim().length > 0 ? validateInputMarkup(input) : null),
        [input],
    );
    const sendDisabled = sending || streamingRecord?.active || Boolean(inputFormatError);

    async function refreshSimulationDetails(id) {
        try {
            const detail = await fetchSimulation(id);
            setSimulationDetails((current) => ({
                ...current,
                [id]: detail,
            }));
        } catch {
            // Keep cached/list data when the detail refresh fails.
        }
    }

    const refreshCharacters = useCallback(async (id) => {
        try {
            const characters = await fetchSimulationCharacters(id);
            setCharacterCache((current) => ({
                ...current,
                [id]: characters,
            }));
            setSelectedCharacterIds((current) => {
                if (current[id] || characters.length === 0) {
                    return current;
                }

                return {
                    ...current,
                    [id]: characters[0].id,
                };
            });
            return characters;
        } catch {
            // Keep cached characters available if background refresh fails.
            return emptyList;
        }
    }, []);

    async function refreshLocations(id) {
        try {
            const locations = await fetchSimulationLocations(id);
            setLocationCache((current) => ({
                ...current,
                [id]: locations,
            }));
            setSelectedLocationIds((current) => {
                if (current[id] || locations.length === 0) {
                    return current;
                }

                return {
                    ...current,
                    [id]: locations[0].id,
                };
            });
        } catch {
            // Keep cached locations available if background refresh fails.
        }
    }

    async function refreshEntities(id) {
        try {
            const [
                background,
                landmarks,
                items,
                stacks,
                equipment,
                containers,
                turns,
                events,
                memories,
                intents,
            ] = await Promise.all([
                fetchSimulationBackgroundCharacters(id),
                fetchSimulationLandmarks(id),
                fetchSimulationItems(id),
                fetchSimulationStacks(id),
                fetchSimulationEquipment(id),
                fetchSimulationContainers(id),
                fetchSimulationRecords({ simulationId: id, limit: recordLimit }),
                fetchSimulationEvents(id),
                fetchSimulationMemories(id),
                fetchSimulationIntents(id),
            ]);

            const nextEntities = {
                background,
                landmarks,
                items,
                stacks,
                equipment,
                containers,
                turns,
                events,
                memories,
                intents,
            };

            setEntityCache((current) => ({
                ...current,
                [id]: nextEntities,
            }));
            setSelectedEntityIds((current) => {
                const currentSelection = current[id] ?? {};
                const nextSelection = { ...currentSelection };
                for (const section of entityDetailSections) {
                    if (nextSelection[section] || (nextEntities[section] ?? []).length === 0) {
                        continue;
                    }
                    nextSelection[section] = nextEntities[section][0].id;
                }

                if (Object.keys(nextSelection).length === Object.keys(currentSelection).length) {
                    return current;
                }

                return {
                    ...current,
                    [id]: nextSelection,
                };
            });
        } catch {
            // Keep cached entities available if background refresh fails.
        }
    }

    async function refreshCharacterInventory(id, characterId) {
        if (!id || !characterId) {
            return;
        }

        try {
            const inventory = await fetchCharacterInventory(characterId);
            setInventoryCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: inventory,
            }));
        } catch {
            setInventoryCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: { stacks: [], equipment: [], containers: [] },
            }));
        }
    }

    async function refreshCharacterEmotion(id, characterId) {
        if (!id || !characterId) {
            return;
        }
        try {
            const emotion = await fetchCharacterEmotion({ simulationId: id, characterId });
            setEmotionCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: emotion,
            }));
        } catch {
            setEmotionCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: null,
            }));
        }
    }

    useEffect(() => {
        let ignore = false;

        async function loadSimulations() {
            try {
                setLoading(true);
                setError(null);

                const data = await fetchSimulations({ limit: simulationLimit, offset: 0 });

                if (ignore) {
                    return;
                }

                setSimulations(data);

                const previewEntries = await Promise.all(
                    data.map(async (simulation) => {
                        try {
                            const latestRecords = await fetchSimulationRecords({
                                simulationId: simulation.id,
                                limit: 1,
                            });
                            const latestRecord = sortRecords(latestRecords).at(-1);

                            return [simulation.id, latestRecord?.narration ?? ""];
                        } catch {
                            return [simulation.id, ""];
                        }
                    }),
                );

                if (!ignore) {
                    setPreviews(Object.fromEntries(previewEntries));
                }
            } catch (err) {
                if (!ignore) {
                    setError(err.message);
                }
            } finally {
                if (!ignore) {
                    setLoading(false);
                }
            }
        }

        startTransition(() => {
            loadSimulations();
        });

        return () => {
            ignore = true;
        };
    }, []);

    useEffect(() => {
        let ignore = false;

        async function loadInitialRecords() {
            try {
                setRecordLoading(true);
                setRecordError(null);

                const data = await fetchSimulationRecords({
                    simulationId,
                    limit: recordLimit,
                });

                if (!ignore) {
                    setRecords(sortRecords(data));
                }
            } catch (err) {
                if (!ignore) {
                    setRecordError(err.message);
                }
            } finally {
                if (!ignore) {
                    setRecordLoading(false);
                }
            }
        }

        if (simulationId) {
            startTransition(() => {
                loadInitialRecords();
                refreshSimulationDetails(simulationId);
                refreshCharacters(simulationId).then(() => refreshEntities(simulationId));
                refreshLocations(simulationId);
            });
        }

        return () => {
            ignore = true;
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
        };
    }, [refreshCharacters, simulationId]);

    useEffect(() => {
        if (!detailsOpen || !simulationId) {
            return;
        }

        refreshSimulationDetails(simulationId);
        refreshCharacters(simulationId).then(() => refreshEntities(simulationId));
        refreshLocations(simulationId);
    }, [detailsOpen, refreshCharacters, simulationId]);

    useEffect(() => {
        if (!detailsOpen || detailsSection !== "characters") {
            return;
        }

        refreshCharacterInventory(simulationId, selectedCharacterId);
        refreshCharacterEmotion(simulationId, selectedCharacterId);
    }, [detailsOpen, detailsSection, simulationId, selectedCharacterId]);

    useEffect(() => {
        recordsEndRef.current?.scrollIntoView({ block: "end" });
    }, [
        records,
        streamingRecord?.message,
        streamingRecord?.blocks,
        streamingRecord?.error,
        streamingRecord?.stageName,
        recordLoading,
    ]);

    useEffect(() => {
        const inputElement = composerInputRef.current;

        if (!inputElement) {
            return;
        }

        inputElement.style.height = "auto";
        inputElement.style.height = `${Math.min(inputElement.scrollHeight, 160)}px`;
        inputElement.style.overflowY = inputElement.scrollHeight > 160 ? "auto" : "hidden";
    }, [input]);

    function closeRunStream() {
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
    }

    async function refreshSimulationTurns(id = simulationId) {
        if (!id) {
            return;
        }

        const data = await fetchSimulationRecords({
            simulationId: id,
            limit: recordLimit,
        });
        const sortedTurns = sortRecords(data);

        setRecords(sortedTurns);
        setPreviews((current) => ({
            ...current,
            [id]: sortedTurns.at(-1)?.narration ?? "",
        }));
    }

    function finishRunStream({ runId, error = null }) {
        closeRunStream();
        const finalError = error ?? streamErrorRef.current;

        setStreamingRecord((current) => {
            if (!current || current.runId !== runId) {
                return current;
            }

            return {
                ...current,
                active: false,
                error: finalError,
            };
        });

        refreshSimulationTurns()
            .then(() => {
                if (!finalError) {
                    setStreamingRecord((current) => (current?.runId === runId ? null : current));
                }
            })
            .catch((err) => {
                setRecordError(err.message);
            });
    }

    function connectRunEvents(runId) {
        closeRunStream();
        streamErrorRef.current = null;
        streamReceivedNarrationRef.current = false;

        const eventSource = new EventSource(getSimulationRunUrl({ simulationId, threadId: runId }));
        eventSourceRef.current = eventSource;

        eventSource.addEventListener("chunk", (event) => {
            try {
                const chunk = JSON.parse(event.data);
                const stageName = stageFromStateChunk(chunk);
                const blocks = narrationBlocksFromValue(chunk.narration_blocks ?? chunk.narration);

                if (stageName) {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId) {
                            return current;
                        }

                        return {
                            ...current,
                            stageName,
                            blocks: blocks ?? current.blocks,
                            message: blocks ? narrationTextFromBlocks(blocks) : chunk.narration ?? current.message,
                        };
                    });
                }

                if (chunk?.narration || chunk?.narration_blocks) {
                    streamReceivedNarrationRef.current = true;
                }
            } catch (err) {
                streamErrorRef.current = err.message;
                setStreamingRecord((current) => {
                    if (!current || current.runId !== runId) {
                        return current;
                    }

                    return {
                        ...current,
                        pendingError: err.message,
                    };
                });
            }
        });

        eventSource.addEventListener("status", (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.code === "still_generating") {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId) {
                            return current;
                        }

                        return {
                            ...current,
                            stageName: current.stageName || "narrator",
                            pendingError: payload.message,
                        };
                    });
                    return;
                }

                streamErrorRef.current = payload.message;
                finishRunStream({
                    runId,
                    error: payload.message,
                });
            } catch (err) {
                streamErrorRef.current = err.message;
                finishRunStream({
                    runId,
                    error: err.message,
                });
            }
        });

        eventSource.addEventListener("error", (event) => {
            if ("data" in event && event.data !== undefined) {
                let errorMessage = event.data;
                try {
                    const payload = JSON.parse(event.data);
                    errorMessage = payload.message ?? event.data;
                } catch {
                    // Keep the raw stream error text.
                }
                streamErrorRef.current = errorMessage;
                finishRunStream({
                    runId,
                    error: errorMessage,
                });
                return;
            }

            if (streamReceivedNarrationRef.current) {
                finishRunStream({ runId });
                return;
            }

            if (eventSource.readyState === EventSource.CLOSED || streamErrorRef.current) {
                finishRunStream({
                    runId,
                    error: streamErrorRef.current,
                });
            }
        });

        eventSource.addEventListener("done", () => {
            finishRunStream({ runId });
        });

        eventSource.addEventListener("cancelled", (event) => {
            finishRunStream({
                runId,
                error: event.data || t("simulationChat.cancelled"),
            });
        });
    }

    async function handleSend() {
        if (sendDisabled) {
            if (inputFormatError) {
                setSendError(inputFormatError);
            }
            return;
        }

        const rawInput = input;
        const trimmedInput = rawInput.trim();
        const userInput = trimmedInput.length === 0 ? null : rawInput;
        const localRecordId = `local-user-${Date.now()}`;

        try {
            setSending(true);
            setSendError(null);
            setInput("");

            if (userInput !== null) {
                setRecords((current) => [
                    ...current,
                    {
                        id: localRecordId,
                        turn_number: Number.MAX_SAFE_INTEGER,
                        type: "user_input",
                        narration: userInput,
                    },
                ]);
            }

            const data = await sendSimulationInput({
                simulationId,
                userInput,
            });

            setStreamingRecord({
                runId: data.run_id,
                message: "",
                blocks: [],
                stageName: "",
                pendingError: null,
                error: null,
                active: true,
            });
            connectRunEvents(data.run_id);
        } catch (err) {
            if (userInput !== null) {
                setRecords((current) => current.filter((record) => record.id !== localRecordId));
            }
            setSendError(err.message);
        } finally {
            setSending(false);
        }
    }

    function handleComposerKeyDown(event) {
        if (event.key !== "Enter" || event.shiftKey) {
            return;
        }

        if (sendDisabled) {
            return;
        }

        event.preventDefault();
        handleSend();
    }

    if (loading) {
        return <p className="status-text">{t("simulationChat.loading")}</p>;
    }

    if (error) {
        return <p className="status-text error-text">{t("simulationChat.error", { error })}</p>;
    }

    return (
        <section className="simulation-chat-layout">
            <aside className="conversation-sidebar" aria-label={t("simulationChat.conversationListLabel")}>
                <div className="conversation-sidebar-header">
                    <h1>{t("simulationChat.title")}</h1>
                    <Link to="/" className="secondary-button">
                        {t("simulationChat.back")}
                    </Link>
                </div>

                <div className="conversation-list">
                    {simulations.map((simulation) => (
                        <SimulationConversationItem
                            key={simulation.id}
                            simulation={simulation}
                            preview={previews[simulation.id]}
                        />
                    ))}
                </div>
            </aside>

            <div className="chat-panel">
                <header className="chat-header">
                    <button
                        type="button"
                        className="chat-header-profile"
                        onClick={() => setDetailsOpen(true)}
                        disabled={!selectedSimulation}
                    >
                        <SimulationAvatar simulation={selectedSimulation} className="chat-header-avatar" />
                        <span className="chat-header-text">
                            <span className="chat-header-title">
                                {selectedSimulation?.name ?? t("simulationChat.selectedFallback")}
                            </span>
                            <span className="chat-header-description">
                                {selectedSimulation?.description ?? t("simulationChat.selectedDescriptionFallback")}
                            </span>
                        </span>
                    </button>
                </header>

                <div className="chat-records-wrapper">
                    <div className="chat-records" aria-live="polite">
                        {recordLoading ? (
                            <p className="status-text">{t("simulationChat.recordsLoading")}</p>
                        ) : recordError ? (
                            <p className="status-text error-text">
                                {t("simulationChat.recordsError", { error: recordError })}
                            </p>
                        ) : records.length === 0 && !streamingRecord ? (
                            <p className="status-text">{t("simulationChat.emptyRecords")}</p>
                        ) : (
                            records.map((record) => (
                                <ChatRecord
                                    key={record.id}
                                    record={record}
                                    simulation={selectedSimulation}
                                    charactersById={selectedCharactersById}
                                    userCharacter={userCharacter}
                                />
                            ))
                        )}

                        {streamingRecord ? (
                            <StreamingChatRecord
                                message={streamingRecord.message}
                                blocks={streamingRecord.blocks}
                                error={streamingRecord.error}
                                active={streamingRecord.active}
                                stageName={streamingRecord.stageName}
                                simulation={selectedSimulation}
                                charactersById={selectedCharactersById}
                            />
                        ) : null}
                        <div ref={recordsEndRef} />
                    </div>
                </div>

                <form
                    className="chat-composer"
                    onSubmit={(event) => {
                        event.preventDefault();
                        handleSend();
                    }}
                >
                    <div className="chat-composer-input-wrap">
                        <textarea
                            ref={composerInputRef}
                            className="chat-composer-input"
                            value={input}
                            rows={2}
                            placeholder={t("simulationChat.inputPlaceholder")}
                            onChange={(event) => setInput(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                        />
                        {inputFormatError ? (
                            <p className="chat-send-error">{inputFormatError}</p>
                        ) : sendError ? (
                            <p className="chat-send-error">{t("simulationChat.sendError", { error: sendError })}</p>
                        ) : null}
                    </div>
                    <button
                        type="submit"
                        className="chat-send-button"
                        disabled={sendDisabled}
                        aria-label={t("simulationChat.send")}
                        title={t("simulationChat.send")}
                    >
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <path d="M3.4 20.4 21 12 3.4 3.6 3 10l10 2-10 2 .4 6.4Z" />
                        </svg>
                    </button>
                </form>
            </div>

            {detailsOpen ? (
                <SimulationDetailsModal
                    simulation={selectedSimulation}
                    characters={selectedCharacters}
                    locations={selectedLocations}
                    entities={selectedEntities}
                    inventory={selectedInventory}
                    emotion={selectedEmotion}
                    activeSection={detailsSection}
                    selectedCharacterId={selectedCharacterId}
                    selectedLocationId={selectedLocationId}
                    selectedEntityIds={selectedEntityIdsForSimulation}
                    onActiveSectionChange={setDetailsSection}
                    onSelectedCharacterIdChange={(characterId) =>
                        setSelectedCharacterIds((current) => ({
                            ...current,
                            [simulationId]: characterId,
                        }))
                    }
                    onSelectedLocationIdChange={(locationId) =>
                        setSelectedLocationIds((current) => ({
                            ...current,
                            [simulationId]: locationId,
                        }))
                    }
                    onSelectedEntityIdChange={(section, entityId) =>
                        setSelectedEntityIds((current) => ({
                            ...current,
                            [simulationId]: {
                                ...(current[simulationId] ?? {}),
                                [section]: entityId,
                            },
                        }))
                    }
                    onClose={() => setDetailsOpen(false)}
                />
            ) : null}
        </section>
    );
}
