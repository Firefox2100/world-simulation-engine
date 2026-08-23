import { useTranslation } from "react-i18next";

import { EntityRefField, SelectField, TextArea, TextField } from "@/components/FormFields";
import { defaultCondition } from "@/utils/triggerDefaults";

const comparisonOperators = ["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"];
const deterministicTypes = ["time", "location", "variable", "all_of", "any_of", "not"];

// VariableCondition.value is str | int | float | bool | list[str] on the backend. Authors pick
// an explicit type here instead of us guessing one from free text, since "70" could mean the
// number 70 or the string "70" and only the author knows which the tracked variable actually is.
function valueKindOf(value) {
    if (Array.isArray(value)) {
        return "list";
    }
    if (typeof value === "boolean") {
        return "boolean";
    }
    if (typeof value === "number") {
        return "number";
    }
    return "string";
}

function coerceValueForKind(kind, rawValue) {
    if (kind === "list") {
        return Array.isArray(rawValue)
            ? rawValue
            : String(rawValue ?? "").split(",").map((entry) => entry.trim()).filter(Boolean);
    }
    if (kind === "boolean") {
        return Boolean(rawValue);
    }
    if (kind === "number") {
        const parsed = Number(rawValue);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return String(rawValue ?? "");
}

function VariableConditionFields({ condition, onChange }) {
    const { t } = useTranslation();
    const valueKind = valueKindOf(condition.value);

    function changeValueKind(nextKind) {
        onChange("value", coerceValueForKind(nextKind, condition.value));
    }

    return (
        <>
            <EntityRefField
                label={t("triggers.fields.ownerId")}
                value={condition.owner_id}
                onChange={(value) => onChange("owner_id", value)}
                listId="trigger-entity-refs"
                required
            />
            <TextField
                label={t("triggers.fields.variableName")}
                value={condition.variable_name ?? ""}
                onChange={(value) => onChange("variable_name", value)}
                required
            />
            <SelectField
                label={t("triggers.fields.operator")}
                value={condition.operator}
                onChange={(value) => onChange("operator", value)}
                options={comparisonOperators.map((id) => ({ id, name: t(`triggers.operators.${id}`) }))}
                required
            />
            <SelectField
                label={t("triggers.fields.valueType")}
                value={valueKind}
                onChange={changeValueKind}
                options={["string", "number", "boolean", "list"].map((id) => ({ id, name: t(`triggers.valueTypes.${id}`) }))}
                required
            />
            {valueKind === "boolean" ? (
                <SelectField
                    label={t("triggers.fields.value")}
                    value={condition.value ? "true" : "false"}
                    onChange={(value) => onChange("value", value === "true")}
                    options={[{ id: "true", name: "true" }, { id: "false", name: "false" }]}
                    required
                />
            ) : valueKind === "list" ? (
                <TextField
                    label={t("triggers.fields.valueList")}
                    value={(condition.value ?? []).join(", ")}
                    onChange={(value) => onChange("value", coerceValueForKind("list", value))}
                    required
                />
            ) : (
                <TextField
                    label={t("triggers.fields.value")}
                    value={String(condition.value ?? "")}
                    type={valueKind === "number" ? "number" : "text"}
                    onChange={(value) => onChange("value", valueKind === "number" ? Number(value) : value)}
                    required
                />
            )}
        </>
    );
}

function ConditionListEditor({ conditions, onChange, lookups, depth }) {
    const { t } = useTranslation();

    function updateAt(index, value) {
        const next = [...conditions];
        next[index] = value;
        onChange(next);
    }

    function removeAt(index) {
        onChange(conditions.filter((_, entryIndex) => entryIndex !== index));
    }

    return (
        <div className="trigger-condition-list">
            {conditions.map((sub, index) => (
                <div className="trigger-condition-list-item" key={index}>
                    <TriggerConditionEditor
                        condition={sub}
                        onChange={(value) => updateAt(index, value)}
                        lookups={lookups}
                        allowSemantic={false}
                        depth={depth}
                    />
                    {conditions.length > 1 ? (
                        <button
                            type="button"
                            className="secondary-button danger-button"
                            onClick={() => removeAt(index)}
                        >
                            {t("triggers.removeCondition")}
                        </button>
                    ) : null}
                </div>
            ))}
            <button
                type="button"
                className="secondary-button"
                onClick={() => onChange([...conditions, defaultCondition("location")])}
            >
                {t("triggers.addCondition")}
            </button>
        </div>
    );
}

// Recursive editor for Trigger.condition: a type picker at each node, with type-specific fields
// below it, recursing into itself for all_of/any_of (a list of child conditions) and not (a
// single child condition). `allowSemantic` is false for every nested call - the backend only
// ever accepts a SemanticCondition as the trigger's sole top-level condition, never nested inside
// an all_of/any_of/not, so the type picker hides it once inside a composite.
export function TriggerConditionEditor({ condition, onChange, lookups, allowSemantic = true, depth = 0 }) {
    const { t } = useTranslation();
    const type = condition?.type ?? "location";
    const typeIds = allowSemantic ? [...deterministicTypes, "semantic"] : deterministicTypes;
    const typeOptions = typeIds.map((id) => ({ id, name: t(`triggers.conditionTypes.${id}`) }));

    function updateField(field, value) {
        onChange({ ...condition, [field]: value });
    }

    return (
        <div className={`trigger-condition-node${depth > 0 ? " trigger-condition-nested" : ""}`}>
            <SelectField
                label={t("triggers.fields.conditionType")}
                value={type}
                onChange={(nextType) => onChange(defaultCondition(nextType))}
                options={typeOptions}
                required
            />

            {type === "time" ? (
                <>
                    <SelectField
                        label={t("triggers.fields.operator")}
                        value={condition.operator}
                        onChange={(value) => updateField("operator", value)}
                        options={comparisonOperators.map((id) => ({ id, name: t(`triggers.operators.${id}`) }))}
                        required
                    />
                    <TextField
                        label={t("triggers.fields.timeValue")}
                        type="datetime-local"
                        value={condition.value ?? ""}
                        onChange={(value) => updateField("value", value)}
                        required
                    />
                </>
            ) : null}

            {type === "location" ? (
                <>
                    <EntityRefField
                        label={t("triggers.fields.characterId")}
                        value={condition.character_id}
                        onChange={(value) => updateField("character_id", value)}
                        listId="trigger-characters"
                        required
                    />
                    <EntityRefField
                        label={t("triggers.fields.locationId")}
                        value={condition.location_id}
                        onChange={(value) => updateField("location_id", value)}
                        listId="trigger-locations"
                        required
                    />
                    <EntityRefField
                        label={t("triggers.fields.landmarkIdOptional")}
                        value={condition.landmark_id ?? ""}
                        onChange={(value) => updateField("landmark_id", value || null)}
                        listId="trigger-landmarks"
                    />
                </>
            ) : null}

            {type === "variable" ? (
                <VariableConditionFields condition={condition} onChange={updateField} />
            ) : null}

            {type === "semantic" ? (
                <>
                    <SelectField
                        label={t("triggers.fields.semanticMode")}
                        value={condition.mode ?? "fact"}
                        onChange={(value) => updateField("mode", value)}
                        options={["fact", "pacing"].map((id) => ({ id, name: t(`triggers.semanticModes.${id}`) }))}
                        required
                    />
                    <TextArea
                        label={t("triggers.fields.statement")}
                        value={condition.statement ?? ""}
                        onChange={(value) => updateField("statement", value)}
                        required
                    />
                    <TextField
                        label={t("triggers.fields.relevantCharacterIds")}
                        value={(condition.relevant_character_ids ?? []).join(", ")}
                        onChange={(value) =>
                            updateField(
                                "relevant_character_ids",
                                value.split(",").map((entry) => entry.trim()).filter(Boolean),
                            )
                        }
                        listId="trigger-characters"
                    />
                </>
            ) : null}

            {type === "all_of" || type === "any_of" ? (
                <ConditionListEditor
                    conditions={condition.conditions ?? []}
                    onChange={(list) => updateField("conditions", list)}
                    lookups={lookups}
                    depth={depth + 1}
                />
            ) : null}

            {type === "not" ? (
                <div className="trigger-condition-list-item">
                    <TriggerConditionEditor
                        condition={condition.condition}
                        onChange={(value) => updateField("condition", value)}
                        lookups={lookups}
                        allowSemantic={false}
                        depth={depth + 1}
                    />
                </div>
            ) : null}
        </div>
    );
}
