import { useTranslation } from "react-i18next";

import { labelFor } from "@/utils/entityLabel";

export function FieldLabel({ label, required }) {
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

export function TextField({ label, value, onChange, type = "text", required = false, listId = null }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <input
                className="single-line-input"
                value={value}
                type={type}
                required={required}
                list={listId ?? undefined}
                onChange={(event) => onChange(event.target.value)}
            />
        </label>
    );
}

export function ReadOnlyField({ label, value }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={false} />
            <input className="single-line-input" value={value} disabled readOnly />
        </label>
    );
}

export function TextArea({ label, value, onChange, required = false }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <textarea className="multi-line-input" value={value} required={required} onChange={(event) => onChange(event.target.value)} />
        </label>
    );
}

export function SelectField({ label, value, onChange, options, emptyLabel = null, required = false }) {
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

export function MultiSelectField({ label, value, onChange, options, required = false }) {
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

export function CheckboxField({ label, checked, onChange }) {
    return (
        <label className="checkbox-field world-editor-checkbox">
            <FieldLabel label={label} required={false} />
            <input type="checkbox" checked={Boolean(checked)} onChange={(event) => onChange(event.target.checked)} />
        </label>
    );
}

// A free-text id input with autocomplete suggestions drawn from a <datalist> rendered elsewhere
// (see EntityRefDatalist) - used instead of a hard <select> for id references that may point at
// entities the caller hasn't fetched (items, equipment, ids created by another tab), while still
// making the common case (picking a known character/location) a one-click affair. The matching
// <datalist id={listId}> must be rendered exactly once by an ancestor - this field only points at
// it via the `list` attribute - since duplicating a <datalist> per field (e.g. once per node in a
// recursive tree) would produce duplicate DOM ids.
export function EntityRefField({ label, value, onChange, required = false, listId }) {
    return (
        <label className="form-field inline-field">
            <FieldLabel label={label} required={required} />
            <input
                className="single-line-input"
                value={value ?? ""}
                required={required}
                list={listId}
                onChange={(event) => onChange(event.target.value)}
            />
        </label>
    );
}

// Renders the shared <datalist> a same-id EntityRefField's `list` attribute points at. Mount
// once per distinct listId, near the top of a form tree - see TriggerManagerPanel.
export function EntityRefDatalist({ listId, options }) {
    return (
        <datalist id={listId}>
            {options.map((option) => (
                <option key={option.id} value={option.id}>
                    {labelFor(option, option.id)}
                </option>
            ))}
        </datalist>
    );
}
