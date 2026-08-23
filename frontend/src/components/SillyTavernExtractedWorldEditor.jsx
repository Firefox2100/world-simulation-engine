import { useTranslation } from "react-i18next";

import { TurnContentEditor } from "@/components/TurnContentEditor";

const INTENT_TYPES = ["need", "obligation", "quest", "agenda", "aspiration", "relationship", "habit", "reaction"];
const INTENT_STATUSES = ["active", "paused", "completed", "failed", "abandoned"];
const INTENT_HORIZONS = ["immediate", "short", "day", "long", "open_ended"];
const MEMORY_SUPPORT_TYPES = ["direct", "inferred", "reported", "contradicts"];
const TURN_TYPES = ["user_input", "system_response", "system_continue"];
const CONTAINER_STATES = ["hidden", "locked", "unlocked", "open"];
const RELATIONSHIP_VISIBILITIES = ["objective", "public", "private"];
const SUBJECTIVE_CLAIM_CATEGORIES = [
    "appearance", "personality", "preference", "aversion", "capability", "habit", "value",
    "relationship_expectation", "identity", "state", "safety", "access", "contents", "purpose",
    "condition", "ownership", "risk", "history", "other",
];
const SUBJECTIVE_CLAIM_STANCES = ["believes", "suspects", "uncertain", "doubts", "denies"];

const INTENT_LIST_FIELDS = [
    "success_conditions", "failure_conditions", "maintenance_conditions", "constraints",
    "current_plan", "next_action_biases", "blockers", "open_threads",
];

function joinLines(values) {
    return (values ?? []).join("\n");
}

function splitLines(text) {
    return text.split("\n").map((line) => line.trim()).filter(Boolean);
}

function newId() {
    return typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `new-${Math.random().toString(36).slice(2)}`;
}

function personName(people, id) {
    return people.find((person) => person.id === id)?.name ?? "";
}

function coerceVariableValue(valueType, rawText) {
    switch (valueType) {
        case "integer": {
            const parsed = Number.parseInt(rawText, 10);
            return Number.isNaN(parsed) ? 0 : parsed;
        }
        case "float": {
            const parsed = Number.parseFloat(rawText);
            return Number.isNaN(parsed) ? 0 : parsed;
        }
        case "boolean":
            return rawText === "true";
        default:
            return rawText;
    }
}

function EntitySection({ title, hint, children, onAdd, addLabel }) {
    return (
        <section className="st-import-section">
            <h2>{title}</h2>
            {hint ? <p className="st-import-section-hint">{hint}</p> : null}
            <div className="st-import-entry-list">{children}</div>
            {onAdd ? (
                <button type="button" className="secondary-button st-import-add-button" onClick={onAdd}>
                    {addLabel}
                </button>
            ) : null}
        </section>
    );
}

function EntityCard({ title, onRemove, removeLabel, children }) {
    return (
        <div className="st-import-entry">
            <div className="st-import-entry-header st-import-entry-header-static">
                <span className="st-import-entry-title">{title}</span>
                {onRemove ? (
                    <button type="button" className="icon-button st-import-remove-button" onClick={onRemove} aria-label={removeLabel}>
                        ×
                    </button>
                ) : null}
            </div>
            <div className="st-import-entry-body">{children}</div>
        </div>
    );
}

function EntityMultiSelect({ entities, selectedIds, onToggle }) {
    return (
        <div className="st-import-chip-list">
            {entities.map((entity) => (
                <label key={entity.id} className="st-import-chip">
                    <input
                        type="checkbox"
                        checked={selectedIds.includes(entity.id)}
                        onChange={(event) => onToggle(entity.id, event.target.checked)}
                    />
                    {entity.name}
                </label>
            ))}
        </div>
    );
}

export function SillyTavernExtractedWorldEditor({ assembled, onChange }) {
    const { t } = useTranslation();
    const { world, sections, report } = assembled;

    const characters = sections.characters ?? [];
    const locations = sections.locations ?? [];
    const landmarks = sections.landmarks ?? [];
    const backgroundCharacters = sections.background_characters ?? [];
    const items = sections.items ?? [];
    const itemStacks = sections.item_stacks ?? [];
    const equipment = sections.equipment ?? [];
    const containers = sections.containers ?? [];
    const turns = sections.turns ?? [];
    const events = sections.events ?? [];
    const memories = sections.memories ?? [];
    const intents = sections.intents ?? [];
    const relationships = sections.entity_relationships ?? [];
    const subjectiveClaims = sections.subjective_entity_claims ?? [];
    const variableSets = sections.entity_variable_sets ?? [];
    const media = sections.media ?? [];

    const allPeople = [
        ...characters.map((character) => ({ id: character.id, name: character.name, type: "character" })),
        ...backgroundCharacters.map((character) => ({ id: character.id, name: character.name, type: "background_character" })),
    ];

    const allEntities = [
        ...allPeople,
        ...locations.map((location) => ({ id: location.id, name: location.name, type: "location" })),
        ...items.map((item) => ({ id: item.id, name: item.name, type: "item" })),
        ...equipment.map((item) => ({ id: item.id, name: item.name, type: "equipment" })),
    ];

    function updateWorld(field, value) {
        onChange({ ...assembled, world: { ...world, [field]: value } });
    }

    function updateWorldMetadata(field, value) {
        onChange({
            ...assembled,
            world: { ...world, metadata: { ...(world.metadata ?? {}), [field]: value } },
        });
    }

    function updateSection(section, rows) {
        onChange({ ...assembled, sections: { ...sections, [section]: rows } });
    }

    function updateSections(patch) {
        onChange({ ...assembled, sections: { ...sections, ...patch } });
    }

    function updateItem(section, index, patch) {
        const rows = sections[section].slice();
        rows[index] = { ...rows[index], ...patch };
        updateSection(section, rows);
    }

    function removeItem(section, index) {
        updateSection(section, sections[section].filter((_, itemIndex) => itemIndex !== index));
    }

    function addItem(section, item) {
        updateSection(section, [...(sections[section] ?? []), item]);
    }

    function stackForItem(itemId) {
        return itemStacks.find((stack) => stack.item_id === itemId);
    }

    function updateItemFields(itemId, patch) {
        updateSection("items", items.map((item) => (item.id === itemId ? { ...item, ...patch } : item)));
    }

    function updateStackFields(itemId, patch) {
        updateSection(
            "item_stacks",
            itemStacks.map((stack) => (stack.item_id === itemId ? { ...stack, ...patch } : stack)),
        );
    }

    function addItemWithStack() {
        const itemId = newId();
        updateSections({
            items: [...items, { id: itemId, name: "", description: "", unique: false }],
            item_stacks: [
                ...itemStacks,
                { id: newId(), item_id: itemId, quantity: 1, quality: null, holder_id: null, location_id: null },
            ],
        });
    }

    function removeItemWithStack(itemId) {
        updateSections({
            items: items.filter((item) => item.id !== itemId),
            item_stacks: itemStacks.filter((stack) => stack.item_id !== itemId),
        });
    }

    return (
        <div className="st-import-extracted">
            {report?.entries?.length ? (
                <section className="st-import-section st-import-report">
                    <h2>{t("sillyTavernImport.review.reportTitle")}</h2>
                    <ul className="st-import-report-list">
                        {report.entries.map((entry, index) => (
                            <li key={index} className={entry.low_confidence ? "st-import-report-flagged" : ""}>
                                {entry.message}
                            </li>
                        ))}
                    </ul>
                </section>
            ) : null}

            <section className="st-import-section">
                <h2>{t("sillyTavernImport.review.world.title")}</h2>
                <div className="form-field">
                    <label>{t("sillyTavernImport.review.world.name")}</label>
                    <input
                        className="single-line-input"
                        type="text"
                        value={world.name ?? ""}
                        onChange={(event) => updateWorld("name", event.target.value)}
                    />
                </div>
                <div className="form-field">
                    <label>{t("sillyTavernImport.review.world.description")}</label>
                    <textarea
                        className="multi-line-input"
                        value={world.description ?? ""}
                        onChange={(event) => updateWorld("description", event.target.value)}
                    />
                </div>
                <div className="form-field">
                    <label>{t("sillyTavernImport.review.world.startingTime")}</label>
                    <input
                        className="single-line-input"
                        type="datetime-local"
                        value={(world.starting_time ?? "").slice(0, 16)}
                        onChange={(event) => updateWorld("starting_time", `${event.target.value}:00Z`)}
                    />
                </div>
                <EntityCard title={t("sillyTavernImport.review.world.metadataSectionTitle")}>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataAuthor")}</label>
                        <input
                            className="single-line-input"
                            type="text"
                            value={world.metadata?.author ?? ""}
                            onChange={(event) => updateWorldMetadata("author", event.target.value)}
                        />
                    </div>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataAuthorUrl")}</label>
                        <input
                            className="single-line-input"
                            type="text"
                            value={world.metadata?.author_url ?? ""}
                            onChange={(event) => updateWorldMetadata("author_url", event.target.value)}
                        />
                    </div>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataResourceUrl")}</label>
                        <input
                            className="single-line-input"
                            type="text"
                            value={world.metadata?.resource_url ?? ""}
                            onChange={(event) => updateWorldMetadata("resource_url", event.target.value)}
                        />
                    </div>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataVersion")}</label>
                        <input
                            className="single-line-input"
                            type="text"
                            value={world.metadata?.version ?? ""}
                            onChange={(event) => updateWorldMetadata("version", event.target.value)}
                        />
                    </div>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataTags")}</label>
                        <input
                            className="single-line-input"
                            type="text"
                            value={(world.metadata?.tags ?? []).join(", ")}
                            onChange={(event) =>
                                updateWorldMetadata(
                                    "tags",
                                    event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean),
                                )
                            }
                        />
                    </div>
                    <div className="form-field">
                        <label>{t("sillyTavernImport.review.world.metadataComment")}</label>
                        <textarea
                            className="multi-line-input"
                            value={world.metadata?.comment ?? ""}
                            onChange={(event) => updateWorldMetadata("comment", event.target.value)}
                        />
                    </div>
                </EntityCard>
            </section>

            <EntitySection
                title={t("sillyTavernImport.review.characters.title")}
                onAdd={() =>
                    addItem("characters", {
                        id: newId(), user_controlled: false, name: "", age: 0, gender: "", appearance: "",
                        description: "", public_state: "", private_state: "",
                        current_activity: { name: "idle", started_at: null, expected_end: null, interruptible: true, constraints: [] },
                        speech_style: "",
                    })
                }
                addLabel={t("sillyTavernImport.review.characters.add")}
            >
                {characters.map((character, index) => (
                    <EntityCard
                        key={character.id}
                        title={character.name || t("sillyTavernImport.review.characters.untitled")}
                        onRemove={() => removeItem("characters", index)}
                        removeLabel={t("sillyTavernImport.review.characters.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={character.name ?? ""}
                                onChange={(event) => updateItem("characters", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.characters.age")}</label>
                                <input
                                    className="single-line-input"
                                    type="number"
                                    value={character.age ?? 0}
                                    onChange={(event) => updateItem("characters", index, { age: Number(event.target.value) })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.characters.gender")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={character.gender ?? ""}
                                    onChange={(event) => updateItem("characters", index, { gender: event.target.value })}
                                />
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.appearance")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.appearance ?? ""}
                                onChange={(event) => updateItem("characters", index, { appearance: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.description ?? ""}
                                onChange={(event) => updateItem("characters", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.publicState")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.public_state ?? ""}
                                onChange={(event) => updateItem("characters", index, { public_state: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.privateState")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.private_state ?? ""}
                                onChange={(event) => updateItem("characters", index, { private_state: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.currentActivity")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={character.current_activity?.name ?? ""}
                                onChange={(event) =>
                                    updateItem("characters", index, {
                                        current_activity: { ...character.current_activity, name: event.target.value },
                                    })
                                }
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.characters.speechStyle")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.speech_style ?? ""}
                                onChange={(event) => updateItem("characters", index, { speech_style: event.target.value })}
                            />
                        </div>
                        <label className="checkbox-field">
                            {t("sillyTavernImport.review.characters.userControlled")}
                            <input
                                type="checkbox"
                                checked={Boolean(character.user_controlled)}
                                onChange={(event) => updateItem("characters", index, { user_controlled: event.target.checked })}
                            />
                        </label>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.locations.title")}
                onAdd={() => addItem("locations", { id: newId(), name: "", description: "", parent_location_id: null })}
                addLabel={t("sillyTavernImport.review.locations.add")}
            >
                {locations.map((location, index) => (
                    <EntityCard
                        key={location.id}
                        title={location.name || t("sillyTavernImport.review.locations.untitled")}
                        onRemove={() => removeItem("locations", index)}
                        removeLabel={t("sillyTavernImport.review.locations.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.locations.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={location.name ?? ""}
                                onChange={(event) => updateItem("locations", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.locations.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={location.description ?? ""}
                                onChange={(event) => updateItem("locations", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.locations.parent")}</label>
                            <select
                                className="single-line-input"
                                value={location.parent_location_id ?? ""}
                                onChange={(event) =>
                                    updateItem("locations", index, { parent_location_id: event.target.value || null })
                                }
                            >
                                <option value="">{t("sillyTavernImport.review.locations.none")}</option>
                                {locations
                                    .filter((other) => other.id !== location.id)
                                    .map((other) => (
                                        <option key={other.id} value={other.id}>
                                            {other.name}
                                        </option>
                                    ))}
                            </select>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.landmarks.title")}
                onAdd={() => addItem("landmarks", { id: newId(), name: "", description: "", location_id: null })}
                addLabel={t("sillyTavernImport.review.landmarks.add")}
            >
                {landmarks.map((landmark, index) => (
                    <EntityCard
                        key={landmark.id}
                        title={landmark.name || t("sillyTavernImport.review.landmarks.untitled")}
                        onRemove={() => removeItem("landmarks", index)}
                        removeLabel={t("sillyTavernImport.review.landmarks.remove")}
                    >
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={landmark.name ?? ""}
                                onChange={(event) => updateItem("landmarks", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={landmark.description ?? ""}
                                onChange={(event) => updateItem("landmarks", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.location_id")}</label>
                            <select
                                className="single-line-input"
                                value={landmark.location_id ?? ""}
                                onChange={(event) =>
                                    updateItem("landmarks", index, { location_id: event.target.value || null })
                                }
                            >
                                <option value="">{t("sillyTavernImport.review.landmarks.none")}</option>
                                {locations.map((location) => (
                                    <option key={location.id} value={location.id}>
                                        {location.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.backgroundCharacters.title")}
                onAdd={() =>
                    addItem("background_characters", {
                        id: newId(), name: "", description: "", location_id: null, position: null, landmark_id: null,
                    })
                }
                addLabel={t("sillyTavernImport.review.backgroundCharacters.add")}
            >
                {backgroundCharacters.map((character, index) => (
                    <EntityCard
                        key={character.id}
                        title={character.name || t("sillyTavernImport.review.backgroundCharacters.untitled")}
                        onRemove={() => removeItem("background_characters", index)}
                        removeLabel={t("sillyTavernImport.review.backgroundCharacters.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.backgroundCharacters.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={character.name ?? ""}
                                onChange={(event) => updateItem("background_characters", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.backgroundCharacters.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={character.description ?? ""}
                                onChange={(event) => updateItem("background_characters", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.location_id")}</label>
                                <select
                                    className="single-line-input"
                                    value={character.location_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("background_characters", index, { location_id: event.target.value || null })
                                    }
                                >
                                    <option value="">{t("sillyTavernImport.review.backgroundCharacters.none")}</option>
                                    {locations.map((location) => (
                                        <option key={location.id} value={location.id}>
                                            {location.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.position")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={character.position ?? ""}
                                    onChange={(event) =>
                                        updateItem("background_characters", index, { position: event.target.value || null })
                                    }
                                />
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.backgroundCharacters.landmark")}</label>
                            <select
                                className="single-line-input"
                                value={character.landmark_id ?? ""}
                                onChange={(event) =>
                                    updateItem("background_characters", index, { landmark_id: event.target.value || null })
                                }
                            >
                                <option value="">{t("sillyTavernImport.review.backgroundCharacters.none")}</option>
                                {landmarks.map((landmark) => (
                                    <option key={landmark.id} value={landmark.id}>
                                        {landmark.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.items.title")}
                onAdd={addItemWithStack}
                addLabel={t("sillyTavernImport.review.items.add")}
            >
                {items.map((item) => {
                    const stack = stackForItem(item.id);
                    return (
                        <EntityCard
                            key={item.id}
                            title={item.name || t("sillyTavernImport.review.items.untitled")}
                            onRemove={() => removeItemWithStack(item.id)}
                            removeLabel={t("sillyTavernImport.review.items.remove")}
                        >
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.items.name")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={item.name ?? ""}
                                    onChange={(event) => updateItemFields(item.id, { name: event.target.value })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.items.description")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={item.description ?? ""}
                                    onChange={(event) => updateItemFields(item.id, { description: event.target.value })}
                                />
                            </div>
                            <label className="checkbox-field">
                                {t("sillyTavernImport.review.items.unique")}
                                <input
                                    type="checkbox"
                                    checked={Boolean(item.unique)}
                                    onChange={(event) => updateItemFields(item.id, { unique: event.target.checked })}
                                />
                            </label>
                            <div className="st-import-field-pair">
                                <div className="form-field">
                                    <label>{t("sillyTavernImport.review.items.quantity")}</label>
                                    <input
                                        className="single-line-input"
                                        type="number"
                                        min="1"
                                        value={stack?.quantity ?? 1}
                                        onChange={(event) =>
                                            updateStackFields(item.id, { quantity: Number(event.target.value) })
                                        }
                                    />
                                </div>
                                <div className="form-field">
                                    <label>{t("sillyTavernImport.review.items.quality")}</label>
                                    <input
                                        className="single-line-input"
                                        type="text"
                                        value={stack?.quality ?? ""}
                                        onChange={(event) =>
                                            updateStackFields(item.id, { quality: event.target.value || null })
                                        }
                                    />
                                </div>
                            </div>
                            <div className="st-import-field-pair">
                                <div className="form-field">
                                    <label>{t("sillyTavernImport.review.items.holder")}</label>
                                    <select
                                        className="single-line-input"
                                        value={stack?.holder_id ?? ""}
                                        onChange={(event) =>
                                            updateStackFields(item.id, {
                                                holder_id: event.target.value || null,
                                                location_id: event.target.value ? null : stack?.location_id ?? null,
                                            })
                                        }
                                    >
                                        <option value="">{t("sillyTavernImport.review.items.none")}</option>
                                        {allPeople.map((person) => (
                                            <option key={person.id} value={person.id}>
                                                {person.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div className="form-field">
                                    <label>{t("sillyTavernImport.review.items.location")}</label>
                                    <select
                                        className="single-line-input"
                                        value={stack?.location_id ?? ""}
                                        onChange={(event) =>
                                            updateStackFields(item.id, {
                                                location_id: event.target.value || null,
                                                holder_id: event.target.value ? null : stack?.holder_id ?? null,
                                            })
                                        }
                                    >
                                        <option value="">{t("sillyTavernImport.review.items.none")}</option>
                                        {locations.map((location) => (
                                            <option key={location.id} value={location.id}>
                                                {location.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </EntityCard>
                    );
                })}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.equipment.title")}
                onAdd={() =>
                    addItem("equipment", {
                        id: newId(), name: "", description: "", quality: null, holder_id: null,
                        equipped: true, equipped_position: null,
                    })
                }
                addLabel={t("sillyTavernImport.review.equipment.add")}
            >
                {equipment.map((item, index) => (
                    <EntityCard
                        key={item.id}
                        title={item.name || t("sillyTavernImport.review.equipment.untitled")}
                        onRemove={() => removeItem("equipment", index)}
                        removeLabel={t("sillyTavernImport.review.equipment.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.equipment.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={item.name ?? ""}
                                onChange={(event) => updateItem("equipment", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.equipment.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={item.description ?? ""}
                                onChange={(event) => updateItem("equipment", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.equipment.quality")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={item.quality ?? ""}
                                    onChange={(event) =>
                                        updateItem("equipment", index, { quality: event.target.value || null })
                                    }
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.equipment.slot")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={item.equipped_position ?? ""}
                                    onChange={(event) =>
                                        updateItem("equipment", index, { equipped_position: event.target.value || null })
                                    }
                                />
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.equipment.holder")}</label>
                            <select
                                className="single-line-input"
                                value={item.holder_id ?? ""}
                                onChange={(event) =>
                                    updateItem("equipment", index, { holder_id: event.target.value || null })
                                }
                            >
                                <option value="">{t("sillyTavernImport.review.equipment.none")}</option>
                                {allPeople.map((person) => (
                                    <option key={person.id} value={person.id}>
                                        {person.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.containers.title")}
                onAdd={() =>
                    addItem("containers", {
                        id: newId(), name: "", description: "", state: "unlocked", owner_id: null,
                        holder_id: null, location_id: null, position: null, unlocking_item_ids: [],
                    })
                }
                addLabel={t("sillyTavernImport.review.containers.add")}
            >
                {containers.map((container, index) => (
                    <EntityCard
                        key={container.id}
                        title={container.name || t("sillyTavernImport.review.containers.untitled")}
                        onRemove={() => removeItem("containers", index)}
                        removeLabel={t("sillyTavernImport.review.containers.remove")}
                    >
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={container.name ?? ""}
                                onChange={(event) => updateItem("containers", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={container.description ?? ""}
                                onChange={(event) => updateItem("containers", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.state")}</label>
                            <select
                                className="single-line-input"
                                value={container.state ?? "unlocked"}
                                onChange={(event) => updateItem("containers", index, { state: event.target.value })}
                            >
                                {CONTAINER_STATES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.containers.states.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.holder_id")}</label>
                                <select
                                    className="single-line-input"
                                    value={container.holder_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("containers", index, {
                                            holder_id: event.target.value || null,
                                            location_id: event.target.value ? null : container.location_id ?? null,
                                        })
                                    }
                                >
                                    <option value="">{t("sillyTavernImport.review.containers.none")}</option>
                                    {allPeople.map((person) => (
                                        <option key={person.id} value={person.id}>
                                            {person.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.location_id")}</label>
                                <select
                                    className="single-line-input"
                                    value={container.location_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("containers", index, {
                                            location_id: event.target.value || null,
                                            holder_id: event.target.value ? null : container.holder_id ?? null,
                                        })
                                    }
                                >
                                    <option value="">{t("sillyTavernImport.review.containers.none")}</option>
                                    {locations.map((location) => (
                                        <option key={location.id} value={location.id}>
                                            {location.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.owner_id")}</label>
                                <select
                                    className="single-line-input"
                                    value={container.owner_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("containers", index, { owner_id: event.target.value || null })
                                    }
                                >
                                    <option value="">{t("sillyTavernImport.review.containers.none")}</option>
                                    {allPeople.map((person) => (
                                        <option key={person.id} value={person.id}>
                                            {person.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("simulationDetails.genericFields.position")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={container.position ?? ""}
                                    onChange={(event) =>
                                        updateItem("containers", index, { position: event.target.value || null })
                                    }
                                />
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.containers.unlockingItems")}</label>
                            <EntityMultiSelect
                                entities={items}
                                selectedIds={container.unlocking_item_ids ?? []}
                                onToggle={(itemId, checked) => {
                                    const current = container.unlocking_item_ids ?? [];
                                    const next = checked
                                        ? [...current, itemId]
                                        : current.filter((id) => id !== itemId);
                                    updateItem("containers", index, { unlocking_item_ids: next });
                                }}
                            />
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection
                title={t("sillyTavernImport.review.turns.title")}
                onAdd={() =>
                    addItem("turns", {
                        id: newId(),
                        sequence: turns.length,
                        type: "system_response",
                        content: "",
                        start_time: new Date().toISOString(),
                    })
                }
                addLabel={t("sillyTavernImport.review.turns.add")}
            >
                {turns.map((turn, index) => (
                    <EntityCard
                        key={turn.id}
                        title={t("sillyTavernImport.review.turns.untitled", { index: index + 1 })}
                        onRemove={() => removeItem("turns", index)}
                        removeLabel={t("sillyTavernImport.review.turns.remove")}
                    >
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.type")}</label>
                            <select
                                className="single-line-input"
                                value={turn.type ?? "system_response"}
                                onChange={(event) => updateItem("turns", index, { type: event.target.value })}
                            >
                                {TURN_TYPES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.turns.types.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("simulationDetails.genericFields.content")}</label>
                            <TurnContentEditor
                                content={turn.content ?? ""}
                                characters={allPeople}
                                type={turn.type ?? "system_response"}
                                onChange={(value) => updateItem("turns", index, { content: value })}
                            />
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.events.title")}>
                {events.map((eventItem, index) => {
                    const involvedIds = (eventItem.involved_characters ?? []).map((entry) => entry.character_id);
                    return (
                        <EntityCard
                            key={eventItem.id}
                            title={eventItem.name || t("sillyTavernImport.review.events.untitled")}
                            onRemove={() => removeItem("events", index)}
                            removeLabel={t("sillyTavernImport.review.events.remove")}
                        >
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.events.name")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={eventItem.name ?? ""}
                                    onChange={(event) => updateItem("events", index, { name: event.target.value })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.events.summary")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={eventItem.summary ?? ""}
                                    onChange={(event) => updateItem("events", index, { summary: event.target.value })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.events.outcome")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={eventItem.outcome ?? ""}
                                    onChange={(event) => updateItem("events", index, { outcome: event.target.value || null })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.events.involved")}</label>
                                <EntityMultiSelect
                                    entities={allPeople}
                                    selectedIds={involvedIds}
                                    onToggle={(characterId, checked) => {
                                        const next = checked
                                            ? [...involvedIds, characterId]
                                            : involvedIds.filter((id) => id !== characterId);
                                        updateItem("events", index, {
                                            involved_characters: next.map((id) => ({ character_id: id, involvement: "participate" })),
                                        });
                                    }}
                                />
                            </div>
                        </EntityCard>
                    );
                })}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.memories.title")}>
                {memories.map((memory, index) => {
                    const linkedIds = (memory.character_links ?? []).map((link) => link.character_id);
                    return (
                        <EntityCard
                            key={memory.id}
                            title={t("sillyTavernImport.review.memories.untitled", { index: index + 1 })}
                            onRemove={() => removeItem("memories", index)}
                            removeLabel={t("sillyTavernImport.review.memories.remove")}
                        >
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.memories.summary")}</label>
                                <textarea
                                    className="multi-line-input"
                                    value={memory.summary ?? ""}
                                    onChange={(event) => updateItem("memories", index, { summary: event.target.value })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.memories.keywords")}</label>
                                <input
                                    className="single-line-input"
                                    type="text"
                                    value={(memory.keywords ?? []).join(", ")}
                                    onChange={(event) =>
                                        updateItem("memories", index, {
                                            keywords: event.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                                        })
                                    }
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.memories.supportType")}</label>
                                <select
                                    className="single-line-input"
                                    value={memory.support_type ?? "direct"}
                                    onChange={(event) => updateItem("memories", index, { support_type: event.target.value })}
                                >
                                    {MEMORY_SUPPORT_TYPES.map((option) => (
                                        <option key={option} value={option}>
                                            {t(`sillyTavernImport.review.memories.supportTypes.${option}`)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.memories.event")}</label>
                                <select
                                    className="single-line-input"
                                    value={memory.event_id ?? ""}
                                    onChange={(event) => updateItem("memories", index, { event_id: event.target.value })}
                                >
                                    {events.map((eventItem) => (
                                        <option key={eventItem.id} value={eventItem.id}>
                                            {eventItem.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.memories.characters")}</label>
                                <EntityMultiSelect
                                    entities={characters}
                                    selectedIds={linkedIds}
                                    onToggle={(characterId, checked) => {
                                        const next = checked
                                            ? [...linkedIds, characterId]
                                            : linkedIds.filter((id) => id !== characterId);
                                        updateItem("memories", index, {
                                            character_links: next.map((id) => ({
                                                character_id: id, confidence: 1.0, salience: "medium",
                                                stance: "remember", behavioural_relevance: null,
                                            })),
                                        });
                                    }}
                                />
                            </div>
                        </EntityCard>
                    );
                })}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.intents.title")}>
                {intents.map((intent, index) => (
                    <EntityCard
                        key={intent.id}
                        title={intent.name || t("sillyTavernImport.review.intents.untitled")}
                        onRemove={() => removeItem("intents", index)}
                        removeLabel={t("sillyTavernImport.review.intents.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.name")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={intent.name ?? ""}
                                onChange={(event) => updateItem("intents", index, { name: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={intent.description ?? ""}
                                onChange={(event) => updateItem("intents", index, { description: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.character")}</label>
                            <select
                                className="single-line-input"
                                value={intent.character_id ?? ""}
                                onChange={(event) => updateItem("intents", index, { character_id: event.target.value })}
                            >
                                {characters.map((character) => (
                                    <option key={character.id} value={character.id}>
                                        {character.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.type")}</label>
                            <select
                                className="single-line-input"
                                value={intent.type ?? ""}
                                onChange={(event) => updateItem("intents", index, { type: event.target.value })}
                            >
                                {INTENT_TYPES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.intents.types.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.intents.priority")}</label>
                                <input
                                    className="single-line-input"
                                    type="number"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={intent.priority ?? 0}
                                    onChange={(event) => updateItem("intents", index, { priority: Number(event.target.value) })}
                                />
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.intents.urgency")}</label>
                                <input
                                    className="single-line-input"
                                    type="number"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={intent.urgency ?? 0}
                                    onChange={(event) => updateItem("intents", index, { urgency: Number(event.target.value) })}
                                />
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.status")}</label>
                            <select
                                className="single-line-input"
                                value={intent.status ?? ""}
                                onChange={(event) => updateItem("intents", index, { status: event.target.value })}
                            >
                                {INTENT_STATUSES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.intents.statuses.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.horizon")}</label>
                            <select
                                className="single-line-input"
                                value={intent.horizon ?? ""}
                                onChange={(event) => updateItem("intents", index, { horizon: event.target.value })}
                            >
                                {INTENT_HORIZONS.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.intents.horizons.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.intents.desiredState")}</label>
                            <textarea
                                className="multi-line-input"
                                value={intent.desired_state ?? ""}
                                onChange={(event) => updateItem("intents", index, { desired_state: event.target.value })}
                            />
                        </div>
                        {INTENT_LIST_FIELDS.map((field) => (
                            <div className="form-field" key={field}>
                                <label>{t(`simulationDetails.genericFields.${field}`)}</label>
                                <textarea
                                    className="multi-line-input"
                                    placeholder={t("sillyTavernImport.review.intents.oneItemPerLine")}
                                    value={joinLines(intent[field])}
                                    onChange={(event) =>
                                        updateItem("intents", index, { [field]: splitLines(event.target.value) })
                                    }
                                />
                            </div>
                        ))}
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.relationships.title")}>
                {relationships.map((relationship, index) => (
                    <EntityCard
                        key={index}
                        title={relationship.label || t("sillyTavernImport.review.relationships.untitled")}
                        onRemove={() => removeItem("entity_relationships", index)}
                        removeLabel={t("sillyTavernImport.review.relationships.remove")}
                    >
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.relationships.label")}</label>
                            <input
                                className="single-line-input"
                                type="text"
                                value={relationship.label ?? ""}
                                onChange={(event) => updateItem("entity_relationships", index, { label: event.target.value })}
                            />
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.relationships.visibility")}</label>
                            <select
                                className="single-line-input"
                                value={relationship.visibility ?? "objective"}
                                onChange={(event) => {
                                    const visibility = event.target.value;
                                    const isPrivate = visibility === "private";
                                    const description = isPrivate
                                        ? relationship.public_description ?? relationship.private_description ?? ""
                                        : relationship.private_description ?? relationship.public_description ?? "";
                                    updateItem("entity_relationships", index, {
                                        visibility,
                                        public_description: isPrivate ? null : description,
                                        private_description: isPrivate ? description : null,
                                        perspective_character_id: isPrivate ? relationship.perspective_character_id : null,
                                    });
                                }}
                            >
                                {RELATIONSHIP_VISIBILITIES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.relationships.visibilities.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.relationships.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={
                                    relationship.visibility === "private"
                                        ? relationship.private_description ?? ""
                                        : relationship.public_description ?? ""
                                }
                                onChange={(event) =>
                                    updateItem(
                                        "entity_relationships",
                                        index,
                                        relationship.visibility === "private"
                                            ? { private_description: event.target.value }
                                            : { public_description: event.target.value },
                                    )
                                }
                            />
                        </div>
                        {relationship.visibility === "private" ? (
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.relationships.perspective")}</label>
                                <select
                                    className="single-line-input"
                                    value={relationship.perspective_character_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("entity_relationships", index, {
                                            perspective_character_id: event.target.value || null,
                                        })
                                    }
                                >
                                    <option value="">{t("sillyTavernImport.review.relationships.none")}</option>
                                    {characters.map((character) => (
                                        <option key={character.id} value={character.id}>
                                            {character.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        ) : null}
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.relationships.source")}</label>
                                <select
                                    className="single-line-input"
                                    value={relationship.source?.id ?? ""}
                                    onChange={(event) => {
                                        const person = allPeople.find((candidate) => candidate.id === event.target.value);
                                        updateItem("entity_relationships", index, {
                                            source: { id: person.id, type: person.type },
                                        });
                                    }}
                                >
                                    {allPeople.map((person) => (
                                        <option key={person.id} value={person.id}>
                                            {person.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.relationships.target")}</label>
                                <select
                                    className="single-line-input"
                                    value={relationship.target?.id ?? ""}
                                    onChange={(event) => {
                                        const person = allPeople.find((candidate) => candidate.id === event.target.value);
                                        updateItem("entity_relationships", index, {
                                            target: { id: person.id, type: person.type },
                                        });
                                    }}
                                >
                                    {allPeople.map((person) => (
                                        <option key={person.id} value={person.id}>
                                            {person.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.subjectiveClaims.title")}>
                {subjectiveClaims.map((claim, index) => (
                    <EntityCard
                        key={claim.id}
                        title={
                            personName(characters, claim.observer_character_id) ||
                            t("sillyTavernImport.review.subjectiveClaims.untitled")
                        }
                        onRemove={() => removeItem("subjective_entity_claims", index)}
                        removeLabel={t("sillyTavernImport.review.subjectiveClaims.remove")}
                    >
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.subjectiveClaims.observer")}</label>
                                <select
                                    className="single-line-input"
                                    value={claim.observer_character_id ?? ""}
                                    onChange={(event) =>
                                        updateItem("subjective_entity_claims", index, {
                                            observer_character_id: event.target.value,
                                        })
                                    }
                                >
                                    {characters.map((character) => (
                                        <option key={character.id} value={character.id}>
                                            {character.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.subjectiveClaims.subject")}</label>
                                <select
                                    className="single-line-input"
                                    value={claim.subject?.id ?? ""}
                                    onChange={(event) => {
                                        const entity = allEntities.find((candidate) => candidate.id === event.target.value);
                                        if (!entity) return;
                                        updateItem("subjective_entity_claims", index, {
                                            subject: { type: entity.type, id: entity.id, name: null },
                                        });
                                    }}
                                >
                                    {allEntities.map((entity) => (
                                        <option key={entity.id} value={entity.id}>
                                            {entity.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.subjectiveClaims.category")}</label>
                            <select
                                className="single-line-input"
                                value={claim.category ?? ""}
                                onChange={(event) => updateItem("subjective_entity_claims", index, { category: event.target.value })}
                            >
                                {SUBJECTIVE_CLAIM_CATEGORIES.map((option) => (
                                    <option key={option} value={option}>
                                        {t(`sillyTavernImport.review.subjectiveClaims.categories.${option}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-field">
                            <label>{t("sillyTavernImport.review.subjectiveClaims.statement")}</label>
                            <textarea
                                className="multi-line-input"
                                value={claim.statement ?? ""}
                                onChange={(event) =>
                                    updateItem("subjective_entity_claims", index, {
                                        statement: event.target.value,
                                        normalized_statement: event.target.value.toLowerCase().trim(),
                                    })
                                }
                            />
                        </div>
                        <div className="st-import-field-pair">
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.subjectiveClaims.stance")}</label>
                                <select
                                    className="single-line-input"
                                    value={claim.stance ?? ""}
                                    onChange={(event) => updateItem("subjective_entity_claims", index, { stance: event.target.value })}
                                >
                                    {SUBJECTIVE_CLAIM_STANCES.map((option) => (
                                        <option key={option} value={option}>
                                            {t(`sillyTavernImport.review.subjectiveClaims.stances.${option}`)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>{t("sillyTavernImport.review.subjectiveClaims.confidence")}</label>
                                <input
                                    className="single-line-input"
                                    type="number"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={claim.confidence ?? 0}
                                    onChange={(event) =>
                                        updateItem("subjective_entity_claims", index, { confidence: Number(event.target.value) })
                                    }
                                />
                            </div>
                        </div>
                    </EntityCard>
                ))}
            </EntitySection>

            <EntitySection title={t("sillyTavernImport.review.variableSets.title")}>
                {variableSets.map((variableSet, index) => (
                    <EntityCard
                        key={index}
                        title={
                            variableSet.owner_type === "character"
                                ? personName(allPeople, variableSet.owner_id)
                                : locations.find((location) => location.id === variableSet.owner_id)?.name ?? ""
                        }
                        onRemove={() => removeItem("entity_variable_sets", index)}
                        removeLabel={t("sillyTavernImport.review.variableSets.removeSet")}
                    >
                        {(variableSet.variables ?? []).map((variable, variableIndex) => (
                            <div key={variableIndex} className="st-import-variable-row">
                                <span className="st-import-variable-name">{variable.name}</span>
                                {variable.value_type === "boolean" ? (
                                    <input
                                        type="checkbox"
                                        checked={Boolean(variable.value)}
                                        onChange={(event) => {
                                            const variables = variableSet.variables.slice();
                                            variables[variableIndex] = { ...variable, value: event.target.checked };
                                            updateItem("entity_variable_sets", index, { variables });
                                        }}
                                    />
                                ) : (
                                    <input
                                        className="single-line-input"
                                        type={variable.value_type === "integer" || variable.value_type === "float" ? "number" : "text"}
                                        step={variable.value_type === "float" ? "any" : undefined}
                                        value={String(variable.value ?? "")}
                                        onChange={(event) => {
                                            const variables = variableSet.variables.slice();
                                            variables[variableIndex] = {
                                                ...variable,
                                                value: coerceVariableValue(variable.value_type, event.target.value),
                                            };
                                            updateItem("entity_variable_sets", index, { variables });
                                        }}
                                    />
                                )}
                                <button
                                    type="button"
                                    className="icon-button st-import-remove-button"
                                    aria-label={t("sillyTavernImport.review.variableSets.remove")}
                                    onClick={() => {
                                        const variables = variableSet.variables.filter((_, i) => i !== variableIndex);
                                        updateItem("entity_variable_sets", index, { variables });
                                    }}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </EntityCard>
                ))}
            </EntitySection>

            {media.length > 0 ? (
                <section className="st-import-section">
                    <h2>{t("sillyTavernImport.review.media.title")}</h2>
                    <p className="st-import-section-hint">{t("sillyTavernImport.review.media.hint")}</p>
                    <div className="media-picker-grid">
                        {media.map((mediaRow, index) => (
                            <div className="media-picker-card" key={mediaRow.id}>
                                <img
                                    className="media-picker-card-image"
                                    src={mediaRow.preview_data_uri}
                                    alt={mediaRow.title || mediaRow.filename}
                                    loading="lazy"
                                    decoding="async"
                                />
                                <button
                                    type="button"
                                    className="icon-button st-import-remove-button"
                                    aria-label={t("sillyTavernImport.review.media.remove")}
                                    onClick={() => removeItem("media", index)}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </div>
                </section>
            ) : null}
        </div>
    );
}

export { INTENT_TYPES, INTENT_STATUSES, INTENT_HORIZONS, MEMORY_SUPPORT_TYPES };
