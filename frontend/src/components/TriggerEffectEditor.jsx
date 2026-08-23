import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
    CheckboxField,
    EntityRefField,
    FieldLabel,
    MultiSelectField,
    SelectField,
    TextArea,
    TextField,
} from "@/components/FormFields";
import { defaultEffect, defaultEntityRef, defaultOperation } from "@/utils/triggerDefaults";

const effectTypes = ["narrative_beat", "forced_action", "state_mutation", "perceived_cue"];
const operationTypes = ["state_change", "relationship_change", "create", "promote", "no_physical_change"];
const physicalEntityTypes = [
    "world", "character", "background_character", "item", "item_stack",
    "equipment", "container", "location", "landmark", "body", "unknown",
];
const relationshipTypes = [
    "located_at", "inside", "held_by", "owned_by", "equipped_by", "wearing", "attached_to",
    "near", "part_of", "derived_from", "interacting_with", "emotion_toward", "state_toward", "other",
];

// A JSON escape hatch for the two arbitrary-shaped dict[str, Any] fields on state_mutation
// operations (properties / target_properties) - keyed by the caller on the operation's `type` so
// switching operation type (which resets these fields) remounts this with fresh local text state
// instead of showing stale JSON from the previous type.
function PropertiesJsonField({ label, value, onChange }) {
    const { t } = useTranslation();
    const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2));
    const [parseError, setParseError] = useState(null);

    function handleChange(nextText) {
        setText(nextText);
        try {
            const parsed = nextText.trim() ? JSON.parse(nextText) : {};
            setParseError(null);
            onChange(parsed);
        } catch {
            setParseError(t("triggers.invalidJson"));
        }
    }

    return (
        <div className="form-field inline-field">
            <FieldLabel label={label} required={false} />
            <textarea
                className="multi-line-input trigger-json-input"
                value={text}
                onChange={(event) => handleChange(event.target.value)}
            />
            {parseError ? <p className="form-error">{parseError}</p> : null}
        </div>
    );
}

function coerceScalar(rawValue) {
    if (rawValue === "true") return true;
    if (rawValue === "false") return false;
    if (rawValue.trim() !== "" && Number.isFinite(Number(rawValue))) return Number(rawValue);
    return rawValue;
}

function FieldChangesEditor({ fieldChanges, onChange }) {
    const { t } = useTranslation();

    function updateAt(index, patch) {
        const next = [...fieldChanges];
        next[index] = { ...next[index], ...patch };
        onChange(next);
    }

    function removeAt(index) {
        onChange(fieldChanges.filter((_, entryIndex) => entryIndex !== index));
    }

    return (
        <div className="trigger-field-changes">
            <FieldLabel label={t("triggers.fields.fieldChanges")} required />
            {fieldChanges.map((change, index) => (
                <div className="trigger-field-change-row" key={index}>
                    <input
                        className="single-line-input"
                        placeholder={t("triggers.fields.fieldPath")}
                        value={change.field_path ?? ""}
                        onChange={(event) => updateAt(index, { field_path: event.target.value })}
                    />
                    <input
                        className="single-line-input"
                        placeholder={t("triggers.fields.newValue")}
                        value={change.new_value ?? ""}
                        onChange={(event) => updateAt(index, { new_value: coerceScalar(event.target.value) })}
                    />
                    <input
                        className="single-line-input"
                        placeholder={t("triggers.fields.reason")}
                        value={change.reason ?? ""}
                        onChange={(event) => updateAt(index, { reason: event.target.value })}
                    />
                    {fieldChanges.length > 1 ? (
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("triggers.removeFieldChange")}
                            onClick={() => removeAt(index)}
                        >
                            ×
                        </button>
                    ) : null}
                </div>
            ))}
            <button
                type="button"
                className="secondary-button"
                onClick={() => onChange([...fieldChanges, { field_path: "", old_value: null, new_value: "", reason: "" }])}
            >
                {t("triggers.addFieldChange")}
            </button>
        </div>
    );
}

function EntityRefEditor({ label, value, onChange, listId, onClear = null }) {
    const { t } = useTranslation();
    const ref = value ?? defaultEntityRef();

    return (
        <fieldset className="trigger-entity-ref">
            <legend>{label}</legend>
            <SelectField
                label={t("triggers.fields.entityType")}
                value={ref.type}
                onChange={(nextType) => onChange({ ...ref, type: nextType })}
                options={physicalEntityTypes.map((id) => ({ id, name: t(`triggers.entityTypes.${id}`) }))}
                required
            />
            <EntityRefField
                label={t("triggers.fields.entityId")}
                value={ref.id ?? ""}
                onChange={(value_) => onChange({ ...ref, id: value_ || null })}
                listId={listId}
            />
            <TextField
                label={t("triggers.fields.entityName")}
                value={ref.name ?? ""}
                onChange={(value_) => onChange({ ...ref, name: value_ || null })}
            />
            {onClear ? (
                <button type="button" className="secondary-button danger-button" onClick={onClear}>
                    {t("triggers.clearEntityRef")}
                </button>
            ) : null}
        </fieldset>
    );
}

function NullableEntityRefEditor({ label, value, onChange, listId }) {
    const { t } = useTranslation();

    if (!value) {
        return (
            <div className="trigger-entity-ref-empty">
                <FieldLabel label={label} required={false} />
                <button type="button" className="secondary-button" onClick={() => onChange(defaultEntityRef())}>
                    {t("triggers.setEntityRef")}
                </button>
            </div>
        );
    }

    return (
        <EntityRefEditor label={label} value={value} onChange={onChange} listId={listId} onClear={() => onChange(null)} />
    );
}

function OperationFields({ operation, onChange }) {
    const { t } = useTranslation();

    function update(field, value) {
        onChange({ ...operation, [field]: value });
    }

    if (operation.type === "state_change") {
        return (
            <>
                <EntityRefEditor
                    label={t("triggers.fields.entity")}
                    value={operation.entity}
                    onChange={(value) => update("entity", value)}
                    listId="trigger-entity-refs"
                />
                <FieldChangesEditor fieldChanges={operation.field_changes ?? []} onChange={(value) => update("field_changes", value)} />
                <TextField label={t("triggers.fields.reason")} value={operation.reason ?? ""} onChange={(value) => update("reason", value)} required />
            </>
        );
    }

    if (operation.type === "relationship_change") {
        return (
            <>
                <SelectField
                    label={t("triggers.fields.relationshipType")}
                    value={operation.relationship_type}
                    onChange={(value) => update("relationship_type", value)}
                    options={relationshipTypes.map((id) => ({ id, name: t(`triggers.relationshipTypes.${id}`, { defaultValue: id }) }))}
                    required
                />
                <EntityRefEditor
                    label={t("triggers.fields.subject")}
                    value={operation.subject}
                    onChange={(value) => update("subject", value)}
                    listId="trigger-entity-refs"
                />
                <NullableEntityRefEditor
                    label={t("triggers.fields.object")}
                    value={operation.object}
                    onChange={(value) => update("object", value)}
                    listId="trigger-entity-refs"
                />
                <NullableEntityRefEditor
                    label={t("triggers.fields.oldObject")}
                    value={operation.old_object}
                    onChange={(value) => update("old_object", value)}
                    listId="trigger-entity-refs"
                />
                <PropertiesJsonField
                    key={operation.type}
                    label={t("triggers.fields.properties")}
                    value={operation.properties}
                    onChange={(value) => update("properties", value)}
                />
                <CheckboxField label={t("triggers.fields.ended")} checked={operation.ended} onChange={(value) => update("ended", value)} />
                <TextField label={t("triggers.fields.reason")} value={operation.reason ?? ""} onChange={(value) => update("reason", value)} required />
            </>
        );
    }

    if (operation.type === "create") {
        return (
            <>
                <SelectField
                    label={t("triggers.fields.entityType")}
                    value={operation.entity_type}
                    onChange={(value) => update("entity_type", value)}
                    options={physicalEntityTypes.map((id) => ({ id, name: t(`triggers.entityTypes.${id}`) }))}
                    required
                />
                <TextField label={t("triggers.fields.proposedId")} value={operation.proposed_id ?? ""} onChange={(value) => update("proposed_id", value || null)} />
                <PropertiesJsonField
                    key={operation.type}
                    label={t("triggers.fields.properties")}
                    value={operation.properties}
                    onChange={(value) => update("properties", value)}
                />
                <TextField label={t("triggers.fields.reason")} value={operation.reason ?? ""} onChange={(value) => update("reason", value)} required />
            </>
        );
    }

    if (operation.type === "promote") {
        return (
            <>
                <EntityRefEditor
                    label={t("triggers.fields.sourceEntity")}
                    value={operation.source_entity}
                    onChange={(value) => update("source_entity", value)}
                    listId="trigger-entity-refs"
                />
                <SelectField
                    label={t("triggers.fields.targetEntityType")}
                    value={operation.target_entity_type}
                    onChange={(value) => update("target_entity_type", value)}
                    options={physicalEntityTypes.map((id) => ({ id, name: t(`triggers.entityTypes.${id}`) }))}
                    required
                />
                <PropertiesJsonField
                    key={operation.type}
                    label={t("triggers.fields.targetProperties")}
                    value={operation.target_properties}
                    onChange={(value) => update("target_properties", value)}
                />
                <CheckboxField
                    label={t("triggers.fields.preserveSourceAsState")}
                    checked={operation.preserve_source_as_state}
                    onChange={(value) => update("preserve_source_as_state", value)}
                />
                <TextField label={t("triggers.fields.reason")} value={operation.reason ?? ""} onChange={(value) => update("reason", value)} required />
            </>
        );
    }

    // no_physical_change
    return <TextField label={t("triggers.fields.reason")} value={operation.reason ?? ""} onChange={(value) => update("reason", value)} required />;
}

function StateMutationOperationsEditor({ operations, onChange }) {
    const { t } = useTranslation();

    function updateAt(index, value) {
        const next = [...operations];
        next[index] = value;
        onChange(next);
    }

    function removeAt(index) {
        onChange(operations.filter((_, entryIndex) => entryIndex !== index));
    }

    return (
        <div className="trigger-operation-list">
            <h4>{t("triggers.fields.operations")}</h4>
            {operations.map((operation, index) => (
                <div className="trigger-operation-item" key={index}>
                    <SelectField
                        label={t("triggers.fields.operationType")}
                        value={operation.type}
                        onChange={(nextType) => updateAt(index, defaultOperation(nextType))}
                        options={operationTypes.map((id) => ({ id, name: t(`triggers.operationTypes.${id}`) }))}
                        required
                    />
                    <OperationFields operation={operation} onChange={(value) => updateAt(index, value)} />
                    {operations.length > 1 ? (
                        <button type="button" className="secondary-button danger-button" onClick={() => removeAt(index)}>
                            {t("triggers.removeOperation")}
                        </button>
                    ) : null}
                </div>
            ))}
            {operations.length < 6 ? (
                <button
                    type="button"
                    className="secondary-button"
                    onClick={() => onChange([...operations, defaultOperation("state_change")])}
                >
                    {t("triggers.addOperation")}
                </button>
            ) : null}
        </div>
    );
}

function EffectFields({ effect, onChange, lookups }) {
    const { t } = useTranslation();

    function update(field, value) {
        onChange({ ...effect, [field]: value });
    }

    if (effect.type === "forced_action") {
        return (
            <>
                <EntityRefField
                    label={t("triggers.fields.characterId")}
                    value={effect.character_id}
                    onChange={(value) => update("character_id", value)}
                    listId="trigger-characters"
                    required
                />
                <TextArea label={t("triggers.fields.directive")} value={effect.directive ?? ""} onChange={(value) => update("directive", value)} required />
            </>
        );
    }

    if (effect.type === "state_mutation") {
        return (
            <>
                <StateMutationOperationsEditor operations={effect.operations ?? []} onChange={(value) => update("operations", value)} />
                <TextField label={t("triggers.fields.note")} value={effect.note ?? ""} onChange={(value) => update("note", value)} />
            </>
        );
    }

    if (effect.type === "perceived_cue") {
        return (
            <>
                <MultiSelectField
                    label={t("triggers.fields.characterIds")}
                    value={effect.character_ids ?? []}
                    onChange={(value) => update("character_ids", value)}
                    options={lookups.characters}
                    required
                />
                <TextArea
                    label={t("triggers.fields.cueDescription")}
                    value={effect.description ?? ""}
                    onChange={(value) => update("description", value)}
                    required
                />
                <TextField
                    label={t("triggers.fields.expiresAfterTurns")}
                    type="number"
                    value={effect.expires_after_turns ?? 20}
                    onChange={(value) => update("expires_after_turns", value === "" ? 20 : Number(value))}
                />
            </>
        );
    }

    // narrative_beat
    return (
        <>
            <TextArea label={t("triggers.fields.directive")} value={effect.directive ?? ""} onChange={(value) => update("directive", value)} required />
            <MultiSelectField
                label={t("triggers.fields.relevantCharacterIds")}
                value={effect.relevant_character_ids ?? []}
                onChange={(value) => update("relevant_character_ids", value)}
                options={lookups.characters}
            />
        </>
    );
}

// Editor for the effect_kind-dependent half of a Trigger: `effects` (EVENT, max 3, each a
// narrative_beat/forced_action/state_mutation) or `gate_effect` (GATE, a single description) -
// mirroring the backend's _validate_effect_shape branching, which rejects the other shape.
export function TriggerEffectEditor({ effectKind, effects, gateEffect, onEffectsChange, onGateEffectChange, lookups }) {
    const { t } = useTranslation();

    if (effectKind === "gate") {
        return (
            <TextArea
                label={t("triggers.fields.gateDescription")}
                value={gateEffect?.description ?? ""}
                onChange={(value) => onGateEffectChange({ description: value })}
                required
            />
        );
    }

    function updateAt(index, value) {
        const next = [...effects];
        next[index] = value;
        onEffectsChange(next);
    }

    function removeAt(index) {
        onEffectsChange(effects.filter((_, entryIndex) => entryIndex !== index));
    }

    return (
        <div className="trigger-effect-list">
            {effects.map((effect, index) => (
                <div className="trigger-effect-item" key={index}>
                    <SelectField
                        label={t("triggers.fields.effectType")}
                        value={effect.type}
                        onChange={(nextType) => updateAt(index, defaultEffect(nextType))}
                        options={effectTypes.map((id) => ({ id, name: t(`triggers.effectTypes.${id}`) }))}
                        required
                    />
                    <EffectFields effect={effect} onChange={(value) => updateAt(index, value)} lookups={lookups} />
                    <button type="button" className="secondary-button danger-button" onClick={() => removeAt(index)}>
                        {t("triggers.removeEffect")}
                    </button>
                </div>
            ))}
            {effects.length < 3 ? (
                <button type="button" className="secondary-button" onClick={() => onEffectsChange([...effects, defaultEffect("narrative_beat")])}>
                    {t("triggers.addEffect")}
                </button>
            ) : null}
        </div>
    );
}
