import { useTranslation } from "react-i18next";

const INTENT_TYPES = ["need", "obligation", "quest", "agenda", "aspiration", "relationship", "habit", "reaction"];
const INTENT_STATUSES = ["active", "paused", "completed", "failed", "abandoned"];
const INTENT_HORIZONS = ["immediate", "short", "day", "long", "open_ended"];
const MEMORY_SUPPORT_TYPES = ["direct", "inferred", "reported", "contradicts"];

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

function CharacterMultiSelect({ characters, selectedIds, onToggle }) {
    return (
        <div className="st-import-chip-list">
            {characters.map((character) => (
                <label key={character.id} className="st-import-chip">
                    <input
                        type="checkbox"
                        checked={selectedIds.includes(character.id)}
                        onChange={(event) => onToggle(character.id, event.target.checked)}
                    />
                    {character.name}
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
    const backgroundCharacters = sections.background_characters ?? [];
    const events = sections.events ?? [];
    const memories = sections.memories ?? [];
    const intents = sections.intents ?? [];
    const relationships = sections.entity_relationships ?? [];
    const variableSets = sections.entity_variable_sets ?? [];

    const allPeople = [
        ...characters.map((character) => ({ id: character.id, name: character.name, type: "character" })),
        ...backgroundCharacters.map((character) => ({ id: character.id, name: character.name, type: "background_character" })),
    ];

    function updateWorld(field, value) {
        onChange({ ...assembled, world: { ...world, [field]: value } });
    }

    function updateSection(section, items) {
        onChange({ ...assembled, sections: { ...sections, [section]: items } });
    }

    function updateItem(section, index, patch) {
        const items = sections[section].slice();
        items[index] = { ...items[index], ...patch };
        updateSection(section, items);
    }

    function removeItem(section, index) {
        updateSection(section, sections[section].filter((_, itemIndex) => itemIndex !== index));
    }

    function addItem(section, item) {
        updateSection(section, [...(sections[section] ?? []), item]);
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
                title={t("sillyTavernImport.review.backgroundCharacters.title")}
                onAdd={() => addItem("background_characters", { id: newId(), name: "", description: "" })}
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
                                <label>{t("sillyTavernImport.review.events.involved")}</label>
                                <CharacterMultiSelect
                                    characters={characters}
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
                                <CharacterMultiSelect
                                    characters={characters}
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
                            <label>{t("sillyTavernImport.review.relationships.description")}</label>
                            <textarea
                                className="multi-line-input"
                                value={relationship.public_description ?? ""}
                                onChange={(event) =>
                                    updateItem("entity_relationships", index, { public_description: event.target.value })
                                }
                            />
                        </div>
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
        </div>
    );
}

export { INTENT_TYPES, INTENT_STATUSES, INTENT_HORIZONS, MEMORY_SUPPORT_TYPES };
