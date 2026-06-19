import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CollapsibleFormSection } from "@/components/CollapsibleFormSection";
import { WorldExtraStateEditor } from "@/components/WorldExtraStateEditor";
import { makeCharacter, makeEntity, makeLocation } from "@/shared/initialWorldStateModel";

function optionNames(items) {
    return items.map((item) => item.name.trim()).filter(Boolean);
}

function locationLabel(location) {
    return [location.primary_location, location.detailed_location, location.scene]
        .map((part) => part.trim())
        .filter(Boolean)
        .join(" / ");
}

export function InitialWorldStateEditor({ stateEnabled, onStateEnabledChange, value, onChange, dataPreset }) {
    const { t } = useTranslation();
    const [openSections, setOpenSections] = useState({
        state: false,
        locations: false,
        characters: false,
    });

    const characterAttributeOptions = optionNames(dataPreset.character_attributes);
    const characterStatOptions = optionNames(dataPreset.character_stats);
    const locationAttributeOptions = [];
    const locationStatOptions = [];
    const entityTypeOptions = optionNames(dataPreset.entity_types);

    function toggle(key) {
        setOpenSections((current) => ({ ...current, [key]: !current[key] }));
    }

    function updateState(field, fieldValue) {
        onChange({
            ...value,
            state: { ...value.state, [field]: fieldValue },
        });
    }

    function addLocation() {
        const id = value.nextIds.location;
        onChange({
            ...value,
            locations: [...value.locations, makeLocation(id)],
            nextIds: { ...value.nextIds, location: id + 1 },
        });
    }

    function updateLocation(index, field, fieldValue) {
        onChange({
            ...value,
            locations: value.locations.map((location, locationIndex) =>
                locationIndex === index ? { ...location, [field]: fieldValue } : location,
            ),
        });
    }

    function removeLocation(index) {
        const removedId = value.locations[index].id;
        onChange({
            ...value,
            locations: value.locations.filter((_, locationIndex) => locationIndex !== index),
            characters: value.characters.map((character) =>
                character.location === String(removedId) ? { ...character, location: "" } : character,
            ),
            state:
                value.state.scene === String(removedId)
                    ? { ...value.state, scene: "" }
                    : value.state,
        });
    }

    function addCharacter() {
        const id = value.nextIds.character;
        onChange({
            ...value,
            characters: [...value.characters, makeCharacter(id)],
            nextIds: { ...value.nextIds, character: id + 1 },
        });
    }

    function updateCharacter(index, field, fieldValue) {
        onChange({
            ...value,
            characters: value.characters.map((character, characterIndex) =>
                characterIndex === index ? { ...character, [field]: fieldValue } : character,
            ),
        });
    }

    function removeCharacter(index) {
        onChange({
            ...value,
            characters: value.characters.filter((_, characterIndex) => characterIndex !== index),
        });
    }

    function updateCollection(collection, index, updater) {
        onChange({
            ...value,
            [collection]: value[collection].map((item, itemIndex) =>
                itemIndex === index ? updater(item) : item,
            ),
        });
    }

    function addAttribute(collection, index, options) {
        if (options.length === 0) {
            return;
        }

        updateCollection(collection, index, (item) => ({
            ...item,
            attributes: [...item.attributes, { name: options[0], values: [] }],
        }));
    }

    function updateAttribute(collection, itemIndex, attributeIndex, field, fieldValue) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            attributes: item.attributes.map((attribute, index) =>
                index === attributeIndex ? { ...attribute, [field]: fieldValue } : attribute,
            ),
        }));
    }

    function removeAttribute(collection, itemIndex, attributeIndex) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            attributes: item.attributes.filter((_, index) => index !== attributeIndex),
        }));
    }

    function addAttributeValue(collection, itemIndex, attributeIndex) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            attributes: item.attributes.map((attribute, index) =>
                index === attributeIndex
                    ? { ...attribute, values: [...attribute.values, ""] }
                    : attribute,
            ),
        }));
    }

    function updateAttributeValue(collection, itemIndex, attributeIndex, valueIndex, fieldValue) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            attributes: item.attributes.map((attribute, index) =>
                index === attributeIndex
                    ? {
                          ...attribute,
                          values: attribute.values.map((attributeValue, currentIndex) =>
                              currentIndex === valueIndex ? fieldValue : attributeValue,
                          ),
                      }
                    : attribute,
            ),
        }));
    }

    function removeAttributeValue(collection, itemIndex, attributeIndex, valueIndex) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            attributes: item.attributes.map((attribute, index) =>
                index === attributeIndex
                    ? {
                          ...attribute,
                          values: attribute.values.filter((_, currentIndex) => currentIndex !== valueIndex),
                      }
                    : attribute,
            ),
        }));
    }

    function addStat(collection, index, options) {
        if (options.length === 0) {
            return;
        }

        updateCollection(collection, index, (item) => ({
            ...item,
            stats: [...item.stats, { name: options[0], value: "" }],
        }));
    }

    function updateStat(collection, itemIndex, statIndex, field, fieldValue) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            stats: item.stats.map((stat, index) =>
                index === statIndex ? { ...stat, [field]: fieldValue } : stat,
            ),
        }));
    }

    function removeStat(collection, itemIndex, statIndex) {
        updateCollection(collection, itemIndex, (item) => ({
            ...item,
            stats: item.stats.filter((_, index) => index !== statIndex),
        }));
    }

    function addEntity(locationIndex) {
        const id = value.nextIds.entity;
        onChange({
            ...value,
            locations: value.locations.map((location, index) =>
                index === locationIndex
                    ? { ...location, entities: [...location.entities, makeEntity(id)] }
                    : location,
            ),
            nextIds: { ...value.nextIds, entity: id + 1 },
        });
    }

    function updateEntity(locationIndex, entityIndex, field, fieldValue) {
        onChange({
            ...value,
            locations: value.locations.map((location, index) =>
                index === locationIndex
                    ? {
                          ...location,
                          entities: location.entities.map((entity, currentEntityIndex) =>
                              currentEntityIndex === entityIndex
                                  ? { ...entity, [field]: fieldValue }
                                  : entity,
                          ),
                      }
                    : location,
            ),
        });
    }

    function removeEntity(locationIndex, entityIndex) {
        onChange({
            ...value,
            locations: value.locations.map((location, index) =>
                index === locationIndex
                    ? {
                          ...location,
                          entities: location.entities.filter(
                              (_, currentEntityIndex) => currentEntityIndex !== entityIndex,
                          ),
                      }
                    : location,
            ),
        });
    }

    function addInteraction(locationIndex, entityIndex) {
        updateEntity(
            locationIndex,
            entityIndex,
            "interactions",
            [...value.locations[locationIndex].entities[entityIndex].interactions, ""],
        );
    }

    function updateInteraction(locationIndex, entityIndex, interactionIndex, fieldValue) {
        const entity = value.locations[locationIndex].entities[entityIndex];
        updateEntity(
            locationIndex,
            entityIndex,
            "interactions",
            entity.interactions.map((interaction, index) =>
                index === interactionIndex ? fieldValue : interaction,
            ),
        );
    }

    function removeInteraction(locationIndex, entityIndex, interactionIndex) {
        const entity = value.locations[locationIndex].entities[entityIndex];
        updateEntity(
            locationIndex,
            entityIndex,
            "interactions",
            entity.interactions.filter((_, index) => index !== interactionIndex),
        );
    }

    function renderAttributeEditor(collection, item, itemIndex, options) {
        return (
            <div className="data-values-editor">
                <div className="data-values-header">
                    <span>{t("worldCreate.initialState.attributes")}</span>
                    <button
                        type="button"
                        className="secondary-button"
                        disabled={options.length === 0}
                        onClick={() => addAttribute(collection, itemIndex, options)}
                    >
                        {t("worldCreate.add")}
                    </button>
                </div>

                {item.attributes.map((attribute, attributeIndex) => (
                    <div className="initial-map-editor" key={attributeIndex}>
                        <div className="list-editor-row">
                            <label>{t("worldCreate.initialState.fields.attribute")}</label>
                            <select
                                className="single-line-input"
                                value={attribute.name}
                                onChange={(event) =>
                                    updateAttribute(
                                        collection,
                                        itemIndex,
                                        attributeIndex,
                                        "name",
                                        event.target.value,
                                    )
                                }
                            >
                                {options.map((option) => (
                                    <option key={option} value={option}>
                                        {option}
                                    </option>
                                ))}
                            </select>
                            <button
                                type="button"
                                className="secondary-button"
                                onClick={() =>
                                    removeAttribute(collection, itemIndex, attributeIndex)
                                }
                            >
                                {t("worldCreate.remove")}
                            </button>
                        </div>

                        {attribute.values.map((attributeValue, valueIndex) => (
                            <div className="list-editor-row" key={valueIndex}>
                                <label>{t("worldCreate.initialState.fields.value")}</label>
                                <input
                                    className="single-line-input"
                                    value={attributeValue}
                                    onChange={(event) =>
                                        updateAttributeValue(
                                            collection,
                                            itemIndex,
                                            attributeIndex,
                                            valueIndex,
                                            event.target.value,
                                        )
                                    }
                                />
                                <button
                                    type="button"
                                    className="secondary-button"
                                    onClick={() =>
                                        removeAttributeValue(
                                            collection,
                                            itemIndex,
                                            attributeIndex,
                                            valueIndex,
                                        )
                                    }
                                >
                                    {t("worldCreate.remove")}
                                </button>
                            </div>
                        ))}

                        <div className="prompt-add-row">
                            <button
                                type="button"
                                className="secondary-button"
                                onClick={() =>
                                    addAttributeValue(collection, itemIndex, attributeIndex)
                                }
                            >
                                {t("worldCreate.initialState.addValue")}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    function renderStatEditor(collection, item, itemIndex, options) {
        return (
            <div className="data-values-editor">
                <div className="data-values-header">
                    <span>{t("worldCreate.initialState.stats")}</span>
                    <button
                        type="button"
                        className="secondary-button"
                        disabled={options.length === 0}
                        onClick={() => addStat(collection, itemIndex, options)}
                    >
                        {t("worldCreate.add")}
                    </button>
                </div>

                {item.stats.map((stat, statIndex) => (
                    <div className="list-editor-row" key={statIndex}>
                        <label>{t("worldCreate.initialState.fields.stat")}</label>
                        <select
                            className="single-line-input"
                            value={stat.name}
                            onChange={(event) =>
                                updateStat(
                                    collection,
                                    itemIndex,
                                    statIndex,
                                    "name",
                                    event.target.value,
                                )
                            }
                        >
                            {options.map((option) => (
                                <option key={option} value={option}>
                                    {option}
                                </option>
                            ))}
                        </select>
                        <input
                            className="single-line-input"
                            type="number"
                            value={stat.value}
                            onChange={(event) =>
                                updateStat(
                                    collection,
                                    itemIndex,
                                    statIndex,
                                    "value",
                                    event.target.value,
                                )
                            }
                        />
                        <button
                            type="button"
                            className="secondary-button"
                            onClick={() => removeStat(collection, itemIndex, statIndex)}
                        >
                            {t("worldCreate.remove")}
                        </button>
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div className="initial-world-state-editor">
            <div className="nested-form-stack">
                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.initialState.state")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.initialState.state"),
                        })}
                        tooltip={t("worldCreate.initialState.stateTooltip")}
                        open={openSections.state}
                        onToggle={() => toggle("state")}
                    >
                        <div className="agent-profile-editor">
                            <label className="checkbox-field agent-preset-enable">
                                <span>{t("worldCreate.initialState.includeState")}</span>
                                <input
                                    type="checkbox"
                                    checked={stateEnabled}
                                    onChange={(event) =>
                                        onStateEnabledChange(event.target.checked)
                                    }
                                />
                            </label>

                            {stateEnabled ? (
                                <>
                                    <div className="form-field inline-field">
                                        <label>{t("worldCreate.initialState.fields.scene")}</label>
                                        <select
                                            className="single-line-input"
                                            value={value.state.scene}
                                            onChange={(event) =>
                                                updateState("scene", event.target.value)
                                            }
                                        >
                                            <option value="">
                                                {t("worldCreate.initialState.noLocation")}
                                            </option>
                                            {value.locations.map((location) => (
                                                <option key={location.id} value={location.id}>
                                                    {locationLabel(location) ||
                                                        t("worldCreate.initialState.locationTitle", {
                                                            number: location.id,
                                                        })}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    <div className="agent-number-grid">
                                        <div className="compact-form-field">
                                            <label>
                                                {t("worldCreate.initialState.fields.turn_number")}
                                            </label>
                                            <input
                                                className="single-line-input"
                                                type="number"
                                                value={value.state.turn_number}
                                                onChange={(event) =>
                                                    updateState("turn_number", event.target.value)
                                                }
                                            />
                                        </div>
                                        <div className="compact-form-field">
                                            <label>
                                                {t("worldCreate.initialState.fields.time_label")}
                                            </label>
                                            <input
                                                className="single-line-input"
                                                value={value.state.time_label}
                                                onChange={(event) =>
                                                    updateState("time_label", event.target.value)
                                                }
                                            />
                                        </div>
                                    </div>
                                    {[
                                        "state",
                                        "recent_history_summary",
                                        "long_term_history_summary",
                                    ].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>
                                                {t(`worldCreate.initialState.fields.${field}`)}
                                            </label>
                                            <input
                                                className="single-line-input"
                                                value={value.state[field]}
                                                onChange={(event) =>
                                                    updateState(field, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))}
                                </>
                            ) : null}
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.initialState.locations")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.initialState.locations"),
                        })}
                        tooltip={t("worldCreate.initialState.locationsTooltip")}
                        open={openSections.locations}
                        onToggle={() => toggle("locations")}
                    >
                        <div className="data-preset-list">
                            {value.locations.map((location, index) => (
                                <div className="data-preset-item" key={location.id}>
                                    <div className="prompt-message-header">
                                        <span className="data-preset-item-title">
                                            {t("worldCreate.initialState.locationTitle", {
                                                number: index + 1,
                                            })}
                                        </span>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => removeLocation(index)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    {[
                                        "primary_location",
                                        "detailed_location",
                                        "scene",
                                        "description",
                                    ].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>
                                                {t(`worldCreate.initialState.fields.${field}`)}
                                            </label>
                                            <input
                                                className="single-line-input"
                                                value={location[field]}
                                                onChange={(event) =>
                                                    updateLocation(
                                                        index,
                                                        field,
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </div>
                                    ))}
                                    {renderAttributeEditor(
                                        "locations",
                                        location,
                                        index,
                                        locationAttributeOptions,
                                    )}
                                    {renderStatEditor("locations", location, index, locationStatOptions)}
                                    <div className="data-values-editor">
                                        <div className="data-values-header">
                                            <span>{t("worldCreate.initialState.entities")}</span>
                                            <button
                                                type="button"
                                                className="secondary-button"
                                                onClick={() => addEntity(index)}
                                            >
                                                {t("worldCreate.add")}
                                            </button>
                                        </div>
                                        {location.entities.map((entity, entityIndex) => (
                                            <div className="data-preset-item" key={entity.id}>
                                                <div className="prompt-message-header">
                                                    <span className="data-preset-item-title">
                                                        {t(
                                                            "worldCreate.initialState.entityTitle",
                                                            { number: entityIndex + 1 },
                                                        )}
                                                    </span>
                                                    <button
                                                        type="button"
                                                        className="secondary-button"
                                                        onClick={() =>
                                                            removeEntity(index, entityIndex)
                                                        }
                                                    >
                                                        {t("worldCreate.remove")}
                                                    </button>
                                                </div>
                                                <div className="form-field inline-field">
                                                    <label>
                                                        {t("worldCreate.initialState.fields.name")}
                                                    </label>
                                                    <input
                                                        className="single-line-input"
                                                        value={entity.name}
                                                        onChange={(event) =>
                                                            updateEntity(
                                                                index,
                                                                entityIndex,
                                                                "name",
                                                                event.target.value,
                                                            )
                                                        }
                                                    />
                                                </div>
                                                <div className="form-field inline-field">
                                                    <label>
                                                        {t("worldCreate.initialState.fields.type")}
                                                    </label>
                                                    <select
                                                        className="single-line-input"
                                                        value={entity.type}
                                                        onChange={(event) =>
                                                            updateEntity(
                                                                index,
                                                                entityIndex,
                                                                "type",
                                                                event.target.value,
                                                            )
                                                        }
                                                    >
                                                        <option value="">
                                                            {t(
                                                                "worldCreate.initialState.noEntityType",
                                                            )}
                                                        </option>
                                                        {entityTypeOptions.map((option) => (
                                                            <option key={option} value={option}>
                                                                {option}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </div>
                                                {["description", "status"].map((field) => (
                                                    <div className="form-field inline-field" key={field}>
                                                        <label>
                                                            {t(
                                                                `worldCreate.initialState.fields.${field}`,
                                                            )}
                                                        </label>
                                                        <input
                                                            className="single-line-input"
                                                            value={entity[field]}
                                                            onChange={(event) =>
                                                                updateEntity(
                                                                    index,
                                                                    entityIndex,
                                                                    field,
                                                                    event.target.value,
                                                                )
                                                            }
                                                        />
                                                    </div>
                                                ))}
                                                <div className="data-values-editor">
                                                    <div className="data-values-header">
                                                        <span>
                                                            {t(
                                                                "worldCreate.initialState.fields.interactions",
                                                            )}
                                                        </span>
                                                        <button
                                                            type="button"
                                                            className="secondary-button"
                                                            onClick={() =>
                                                                addInteraction(index, entityIndex)
                                                            }
                                                        >
                                                            {t("worldCreate.add")}
                                                        </button>
                                                    </div>
                                                    {entity.interactions.map(
                                                        (interaction, interactionIndex) => (
                                                            <div
                                                                className="list-editor-row"
                                                                key={interactionIndex}
                                                            >
                                                                <label>
                                                                    {t(
                                                                        "worldCreate.initialState.fields.interaction",
                                                                    )}
                                                                </label>
                                                                <input
                                                                    className="single-line-input"
                                                                    value={interaction}
                                                                    onChange={(event) =>
                                                                        updateInteraction(
                                                                            index,
                                                                            entityIndex,
                                                                            interactionIndex,
                                                                            event.target.value,
                                                                        )
                                                                    }
                                                                />
                                                                <button
                                                                    type="button"
                                                                    className="secondary-button"
                                                                    onClick={() =>
                                                                        removeInteraction(
                                                                            index,
                                                                            entityIndex,
                                                                            interactionIndex,
                                                                        )
                                                                    }
                                                                >
                                                                    {t("worldCreate.remove")}
                                                                </button>
                                                            </div>
                                                        ),
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addLocation}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.initialState.characters")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.initialState.characters"),
                        })}
                        tooltip={t("worldCreate.initialState.charactersTooltip")}
                        open={openSections.characters}
                        onToggle={() => toggle("characters")}
                    >
                        <div className="data-preset-list">
                            {value.characters.map((character, index) => (
                                <div className="data-preset-item" key={character.id}>
                                    <div className="prompt-message-header">
                                        <span className="data-preset-item-title">
                                            {t("worldCreate.initialState.characterTitle", {
                                                number: index + 1,
                                            })}
                                        </span>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => removeCharacter(index)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    {["name", "gender", "age"].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.initialState.fields.${field}`)}</label>
                                            <input
                                                className="single-line-input"
                                                type={field === "age" ? "number" : "text"}
                                                value={character[field]}
                                                onChange={(event) =>
                                                    updateCharacter(index, field, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))}
                                    {[
                                        "description",
                                        "appearance",
                                        "public_state",
                                        "private_state",
                                    ].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.initialState.fields.${field}`)}</label>
                                            <input
                                                className="single-line-input"
                                                value={character[field]}
                                                onChange={(event) =>
                                                    updateCharacter(index, field, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))}
                                    <div className="form-field inline-field">
                                        <label>{t("worldCreate.initialState.fields.location")}</label>
                                        <select
                                            className="single-line-input"
                                            value={character.location}
                                            onChange={(event) =>
                                                updateCharacter(index, "location", event.target.value)
                                            }
                                        >
                                            <option value="">
                                                {t("worldCreate.initialState.noLocation")}
                                            </option>
                                            {value.locations.map((location) => (
                                                <option key={location.id} value={location.id}>
                                                    {locationLabel(location) ||
                                                        t("worldCreate.initialState.locationTitle", {
                                                            number: location.id,
                                                        })}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    <label className="checkbox-field agent-preset-enable">
                                        <span>
                                            {t("worldCreate.initialState.fields.user_controlled")}
                                        </span>
                                        <input
                                            type="checkbox"
                                            checked={character.user_controlled}
                                            onChange={(event) =>
                                                updateCharacter(
                                                    index,
                                                    "user_controlled",
                                                    event.target.checked,
                                                )
                                            }
                                        />
                                    </label>
                                    {renderAttributeEditor(
                                        "characters",
                                        character,
                                        index,
                                        characterAttributeOptions,
                                    )}
                                    {renderStatEditor(
                                        "characters",
                                        character,
                                        index,
                                        characterStatOptions,
                                    )}
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addCharacter}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <WorldExtraStateEditor value={value} onChange={onChange} embedded />
            </div>
        </div>
    );
}
