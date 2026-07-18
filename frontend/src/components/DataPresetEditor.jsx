import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CollapsibleFormSection } from "@/components/CollapsibleFormSection";
import { dataPresetListFields, makeModelAttribute, makeModelStat } from "@/shared/dataPresetModel";

export function DataPresetEditor({ enabled, onEnabledChange, value, onChange }) {
    const { t } = useTranslation();
    const [openSections, setOpenSections] = useState(
        dataPresetListFields.reduce(
            (state, field) => ({ ...state, [field.key]: false }),
            { entity_types: false },
        ),
    );

    function updateList(key, updater) {
        onChange({
            ...value,
            [key]: updater(value[key]),
        });
    }

    function addItem(field) {
        updateList(field.key, (items) => [
            ...items,
            field.type === "attribute" ? makeModelAttribute() : makeModelStat(),
        ]);
    }

    function updateItem(key, index, field, fieldValue) {
        updateList(key, (items) =>
            items.map((item, itemIndex) =>
                itemIndex === index ? { ...item, [field]: fieldValue } : item,
            ),
        );
    }

    function removeItem(key, index) {
        updateList(key, (items) => items.filter((_, itemIndex) => itemIndex !== index));
    }

    function addValue(key, itemIndex) {
        updateList(key, (items) =>
            items.map((item, index) =>
                index === itemIndex ? { ...item, values: [...item.values, ""] } : item,
            ),
        );
    }

    function updateValue(key, itemIndex, valueIndex, fieldValue) {
        updateList(key, (items) =>
            items.map((item, index) =>
                index === itemIndex
                    ? {
                          ...item,
                          values: item.values.map((valueItem, currentValueIndex) =>
                              currentValueIndex === valueIndex ? fieldValue : valueItem,
                          ),
                      }
                    : item,
            ),
        );
    }

    function removeValue(key, itemIndex, valueIndex) {
        updateList(key, (items) =>
            items.map((item, index) =>
                index === itemIndex
                    ? {
                          ...item,
                          values: item.values.filter((_, currentValueIndex) => currentValueIndex !== valueIndex),
                      }
                    : item,
            ),
        );
    }

    function addEntityType() {
        onChange({
            ...value,
            entity_types: [...value.entity_types, { name: "", description: "" }],
        });
    }

    function updateEntityType(index, field, fieldValue) {
        onChange({
            ...value,
            entity_types: value.entity_types.map((entityType, entityIndex) =>
                entityIndex === index ? { ...entityType, [field]: fieldValue } : entityType,
            ),
        });
    }

    function removeEntityType(index) {
        onChange({
            ...value,
            entity_types: value.entity_types.filter((_, entityIndex) => entityIndex !== index),
        });
    }

    function toggle(key) {
        setOpenSections((current) => ({ ...current, [key]: !current[key] }));
    }

    return (
        <div className="data-preset-editor">
            <label className="checkbox-field agent-preset-enable">
                <span>{t("worldCreate.dataPreset.include")}</span>
                <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(event) => onEnabledChange(event.target.checked)}
                />
            </label>

            {enabled ? (
                <div className="nested-form-stack">
                    {dataPresetListFields.map((field) => (
                        <div className="agent-role-section" key={field.key}>
                            <CollapsibleFormSection
                                title={t(`worldCreate.dataPreset.sections.${field.key}`)}
                                tooltipLabel={t("worldCreate.tooltipLabel", {
                                    field: t(`worldCreate.dataPreset.sections.${field.key}`),
                                })}
                                tooltip={t(`worldCreate.dataPreset.tooltips.${field.key}`)}
                                open={openSections[field.key]}
                                onToggle={() => toggle(field.key)}
                            >
                                <div className="data-preset-list">
                                    {value[field.key].map((item, index) => (
                                        <div className="data-preset-item" key={index}>
                                            <div className="prompt-message-header">
                                                <span className="data-preset-item-title">
                                                    {t("worldCreate.dataPreset.itemTitle", {
                                                        number: index + 1,
                                                    })}
                                                </span>
                                                <button
                                                    type="button"
                                                    className="secondary-button"
                                                    onClick={() => removeItem(field.key, index)}
                                                >
                                                    {t("worldCreate.remove")}
                                                </button>
                                            </div>

                                            <div className="form-field inline-field">
                                                <label htmlFor={`${field.key}-${index}-name`}>
                                                    {t("worldCreate.dataPreset.fields.name")}
                                                </label>
                                                <input
                                                    id={`${field.key}-${index}-name`}
                                                    className="single-line-input"
                                                    value={item.name}
                                                    onChange={(event) =>
                                                        updateItem(
                                                            field.key,
                                                            index,
                                                            "name",
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </div>

                                            {field.type === "attribute" ? (
                                                <div className="data-values-editor">
                                                    <div className="data-values-header">
                                                        <span>
                                                            {t(
                                                                "worldCreate.dataPreset.fields.values",
                                                            )}
                                                        </span>
                                                        <button
                                                            type="button"
                                                            className="secondary-button"
                                                            onClick={() => addValue(field.key, index)}
                                                        >
                                                            {t("worldCreate.add")}
                                                        </button>
                                                    </div>
                                                    {item.values.map((fieldValue, valueIndex) => (
                                                        <div
                                                            className="list-editor-row"
                                                            key={valueIndex}
                                                        >
                                                            <label
                                                                htmlFor={`${field.key}-${index}-value-${valueIndex}`}
                                                            >
                                                                {t(
                                                                    "worldCreate.dataPreset.fields.value",
                                                                )}
                                                            </label>
                                                            <input
                                                                id={`${field.key}-${index}-value-${valueIndex}`}
                                                                className="single-line-input"
                                                                value={fieldValue}
                                                                onChange={(event) =>
                                                                    updateValue(
                                                                        field.key,
                                                                        index,
                                                                        valueIndex,
                                                                        event.target.value,
                                                                    )
                                                                }
                                                            />
                                                            <button
                                                                type="button"
                                                                className="secondary-button"
                                                                onClick={() =>
                                                                    removeValue(
                                                                        field.key,
                                                                        index,
                                                                        valueIndex,
                                                                    )
                                                                }
                                                            >
                                                                {t("worldCreate.remove")}
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : null}

                                            <div className="form-field inline-field">
                                                <label htmlFor={`${field.key}-${index}-creation`}>
                                                    {t(
                                                        "worldCreate.dataPreset.fields.creation_instruction",
                                                    )}
                                                </label>
                                                <input
                                                    id={`${field.key}-${index}-creation`}
                                                    className="single-line-input"
                                                    value={item.creation_instruction}
                                                    onChange={(event) =>
                                                        updateItem(
                                                            field.key,
                                                            index,
                                                            "creation_instruction",
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </div>

                                            <div className="form-field inline-field">
                                                <label htmlFor={`${field.key}-${index}-update`}>
                                                    {t(
                                                        "worldCreate.dataPreset.fields.update_instruction",
                                                    )}
                                                </label>
                                                <input
                                                    id={`${field.key}-${index}-update`}
                                                    className="single-line-input"
                                                    value={item.update_instruction}
                                                    onChange={(event) =>
                                                        updateItem(
                                                            field.key,
                                                            index,
                                                            "update_instruction",
                                                            event.target.value,
                                                        )
                                                    }
                                                />
                                            </div>

                                            <label className="checkbox-field agent-preset-enable">
                                                <span>
                                                    {t("worldCreate.dataPreset.fields.universal")}
                                                </span>
                                                <input
                                                    type="checkbox"
                                                    checked={item.universal}
                                                    onChange={(event) =>
                                                        updateItem(
                                                            field.key,
                                                            index,
                                                            "universal",
                                                            event.target.checked,
                                                        )
                                                    }
                                                />
                                            </label>
                                        </div>
                                    ))}

                                    <div className="prompt-add-row">
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => addItem(field)}
                                        >
                                            {t("worldCreate.add")}
                                        </button>
                                    </div>
                                </div>
                            </CollapsibleFormSection>
                        </div>
                    ))}

                    <div className="agent-role-section">
                        <CollapsibleFormSection
                            title={t("worldCreate.dataPreset.sections.entity_types")}
                            tooltipLabel={t("worldCreate.tooltipLabel", {
                                field: t("worldCreate.dataPreset.sections.entity_types"),
                            })}
                            tooltip={t("worldCreate.dataPreset.tooltips.entity_types")}
                            open={openSections.entity_types}
                            onToggle={() => toggle("entity_types")}
                        >
                            <div className="data-preset-list">
                                {value.entity_types.map((entityType, index) => (
                                    <div className="data-preset-item" key={index}>
                                        <div className="prompt-message-header">
                                            <span className="data-preset-item-title">
                                                {t("worldCreate.dataPreset.entityTypeTitle", {
                                                    number: index + 1,
                                                })}
                                            </span>
                                            <button
                                                type="button"
                                                className="secondary-button"
                                                onClick={() => removeEntityType(index)}
                                            >
                                                {t("worldCreate.remove")}
                                            </button>
                                        </div>
                                        <div className="form-field inline-field">
                                            <label htmlFor={`entity-type-${index}-name`}>
                                                {t("worldCreate.dataPreset.fields.type")}
                                            </label>
                                            <input
                                                id={`entity-type-${index}-name`}
                                                className="single-line-input"
                                                value={entityType.name}
                                                onChange={(event) =>
                                                    updateEntityType(
                                                        index,
                                                        "name",
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </div>
                                        <div className="form-field inline-field">
                                            <label htmlFor={`entity-type-${index}-description`}>
                                                {t("worldCreate.dataPreset.fields.description")}
                                            </label>
                                            <input
                                                id={`entity-type-${index}-description`}
                                                className="single-line-input"
                                                value={entityType.description}
                                                onChange={(event) =>
                                                    updateEntityType(
                                                        index,
                                                        "description",
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </div>
                                    </div>
                                ))}

                                <div className="prompt-add-row">
                                    <button
                                        type="button"
                                        className="secondary-button"
                                        onClick={addEntityType}
                                    >
                                        {t("worldCreate.add")}
                                    </button>
                                </div>
                            </div>
                        </CollapsibleFormSection>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
