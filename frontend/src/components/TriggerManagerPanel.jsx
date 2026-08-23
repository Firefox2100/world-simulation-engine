import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchSimulationCharacters, fetchSimulationLandmarks, fetchSimulationLocations } from "@/api/simulations";
import { createTrigger, deleteTrigger, fetchTriggers, setTriggerStatus, updateTrigger } from "@/api/triggers";
import { fetchWorldCharacters, fetchWorldLandmarks, fetchWorldLocations } from "@/api/worldEntities";
import { CheckboxField, EntityRefDatalist, FieldLabel, SelectField, TextArea, TextField } from "@/components/FormFields";
import { TriggerConditionEditor } from "@/components/TriggerConditionEditor";
import { TriggerEffectEditor } from "@/components/TriggerEffectEditor";
import { labelFor } from "@/utils/entityLabel";
import { defaultCondition, defaultEffect } from "@/utils/triggerDefaults";

function emptyForm() {
    return {
        name: "",
        description: "",
        condition: defaultCondition("location"),
        effect_kind: "event",
        effects: [defaultEffect("narrative_beat")],
        gate_effect: null,
        chance: null,
        repeatable: false,
        cooldown_turns: null,
        reversible: true,
    };
}

function formFromTrigger(trigger) {
    return {
        name: trigger.name,
        description: trigger.description ?? "",
        condition: trigger.condition,
        effect_kind: trigger.effect_kind,
        effects: trigger.effects ?? [],
        gate_effect: trigger.gate_effect,
        chance: trigger.chance,
        repeatable: trigger.repeatable,
        cooldown_turns: trigger.cooldown_turns,
        reversible: trigger.reversible,
    };
}

function payloadFromForm(form) {
    return {
        name: form.name.trim(),
        description: form.description,
        condition: form.condition,
        effect_kind: form.effect_kind,
        effects: form.effect_kind === "event" ? form.effects : [],
        gate_effect: form.effect_kind === "gate" ? form.gate_effect : null,
        chance: form.effect_kind === "event" && form.chance !== null && form.chance !== "" ? Number(form.chance) : null,
        repeatable: form.effect_kind === "event" ? form.repeatable : false,
        cooldown_turns:
            form.effect_kind === "event" && form.repeatable && form.cooldown_turns !== null && form.cooldown_turns !== ""
                ? parseInt(form.cooldown_turns, 10)
                : null,
        reversible: form.effect_kind === "gate" ? form.reversible : true,
    };
}

// Full CRUD for Trigger, self-contained (fetches its own trigger list and entity lookups) so the
// same component can be mounted from both WorldCreateModal (sourceType="world") and
// SimulationChatPage's details modal (sourceType="simulation") - the backend's /triggers
// endpoints are source-agnostic, taking either a World or a Simulation id as source_id.
export function TriggerManagerPanel({ sourceType, sourceId }) {
    const { t } = useTranslation();
    const [triggers, setTriggers] = useState([]);
    const [lookups, setLookups] = useState({ characters: [], locations: [], landmarks: [] });
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(emptyForm());
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);

    async function reload() {
        if (!sourceId) {
            setTriggers([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            setTriggers(await fetchTriggers(sourceId));
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        let cancelled = false;

        async function loadLookups() {
            if (!sourceId) {
                return;
            }
            try {
                const [characters, locations, landmarks] = sourceType === "world"
                    ? await Promise.all([fetchWorldCharacters(sourceId), fetchWorldLocations(sourceId), fetchWorldLandmarks(sourceId)])
                    : await Promise.all([fetchSimulationCharacters(sourceId), fetchSimulationLocations(sourceId), fetchSimulationLandmarks(sourceId)]);
                if (!cancelled) {
                    setLookups({ characters, locations, landmarks });
                }
            } catch {
                // Lookups only power id autocomplete - a failure here must not block trigger CRUD.
            }
        }

        async function loadTriggers() {
            if (!sourceId) {
                setTriggers([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            setError(null);
            try {
                const data = await fetchTriggers(sourceId);
                if (!cancelled) {
                    setTriggers(data);
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

        loadLookups();
        loadTriggers();

        return () => {
            cancelled = true;
        };
    }, [sourceType, sourceId]);

    function beginCreate() {
        setEditing(null);
        setForm(emptyForm());
        setError(null);
    }

    function beginEdit(trigger) {
        setEditing(trigger);
        setForm(formFromTrigger(trigger));
        setError(null);
    }

    function updateForm(field, value) {
        setForm((current) => ({ ...current, [field]: value }));
    }

    function changeEffectKind(nextKind) {
        setForm((current) => ({
            ...current,
            effect_kind: nextKind,
            effects: nextKind === "event" && current.effects.length === 0 ? [defaultEffect("narrative_beat")] : current.effects,
            gate_effect: nextKind === "gate" ? (current.gate_effect ?? { description: "" }) : current.gate_effect,
        }));
    }

    async function save() {
        setError(null);
        try {
            setSaving(true);
            const payload = payloadFromForm(form);
            const saved = editing
                ? await updateTrigger(editing.id, payload)
                : await createTrigger({ ...payload, source_id: sourceId });
            await reload();
            setEditing(saved);
            setForm(formFromTrigger(saved));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    async function remove(trigger) {
        if (!window.confirm(t("triggers.confirmDelete", { name: labelFor(trigger, trigger.id) }))) {
            return;
        }
        setError(null);
        try {
            setSaving(true);
            await deleteTrigger(trigger.id);
            if (editing?.id === trigger.id) {
                beginCreate();
            }
            await reload();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    async function toggleStatus(trigger, nextStatus) {
        setError(null);
        try {
            setSaving(true);
            const updated = await setTriggerStatus(trigger.id, nextStatus);
            await reload();
            if (editing?.id === trigger.id) {
                setEditing(updated);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    const formValid = form.name.trim().length > 0
        && (form.effect_kind === "gate" ? Boolean(form.gate_effect?.description?.trim()) : form.effects.length > 0);
    const entityRefOptions = [...lookups.characters, ...lookups.locations, ...lookups.landmarks];

    if (!sourceId) {
        return <p className="status-text">{t("triggers.saveSourceFirst")}</p>;
    }

    return (
        <section className="world-editor-form trigger-manager-panel">
            <EntityRefDatalist listId="trigger-characters" options={lookups.characters} />
            <EntityRefDatalist listId="trigger-locations" options={lookups.locations} />
            <EntityRefDatalist listId="trigger-landmarks" options={lookups.landmarks} />
            <EntityRefDatalist listId="trigger-entity-refs" options={entityRefOptions} />

            {error ? <p className="form-error">{error}</p> : null}
            {loading ? <p className="status-text">{t("worldCreate.newEditor.loading")}</p> : null}

            <div className="simulation-detail-subtabs world-editor-entity-list" role="tablist">
                <button
                    type="button"
                    className={`simulation-detail-subtab world-editor-create-tab${editing ? "" : " active"}`}
                    onClick={beginCreate}
                >
                    {t("worldCreate.newEditor.createNew")}
                </button>
                {triggers.length === 0 && !loading ? (
                    <p className="simulation-details-empty-line">{t("triggers.empty")}</p>
                ) : (
                    triggers.map((trigger) => (
                        <button
                            key={trigger.id}
                            type="button"
                            className={`simulation-detail-subtab${editing?.id === trigger.id ? " active" : ""}`}
                            onClick={() => beginEdit(trigger)}
                        >
                            {labelFor(trigger, trigger.id)}
                            <span className={`trigger-status-badge trigger-status-${trigger.status}`}>
                                {t(`triggers.statuses.${trigger.status}`)}
                            </span>
                        </button>
                    ))
                )}
            </div>

            <div className="world-editor-form">
                <h3>
                    {editing
                        ? t("worldCreate.newEditor.editing", { name: labelFor(editing, editing.id) })
                        : t("triggers.createNew")}
                </h3>

                <TextField label={t("triggers.fields.name")} value={form.name} onChange={(value) => updateForm("name", value)} required />
                <TextArea label={t("triggers.fields.description")} value={form.description} onChange={(value) => updateForm("description", value)} />

                <h4>{t("triggers.conditionSectionTitle")}</h4>
                <TriggerConditionEditor
                    condition={form.condition}
                    onChange={(value) => updateForm("condition", value)}
                    lookups={lookups}
                />

                <h4>{t("triggers.effectSectionTitle")}</h4>
                <SelectField
                    label={t("triggers.fields.effectKind")}
                    value={form.effect_kind}
                    onChange={changeEffectKind}
                    options={["event", "gate"].map((id) => ({ id, name: t(`triggers.effectKinds.${id}`) }))}
                    required
                />
                <TriggerEffectEditor
                    effectKind={form.effect_kind}
                    effects={form.effects}
                    gateEffect={form.gate_effect}
                    onEffectsChange={(value) => updateForm("effects", value)}
                    onGateEffectChange={(value) => updateForm("gate_effect", value)}
                    lookups={lookups}
                />

                {form.effect_kind === "event" ? (
                    <>
                        <TextField
                            label={t("triggers.fields.chance")}
                            type="number"
                            value={form.chance ?? ""}
                            onChange={(value) => updateForm("chance", value === "" ? null : value)}
                        />
                        <CheckboxField label={t("triggers.fields.repeatable")} checked={form.repeatable} onChange={(value) => updateForm("repeatable", value)} />
                        {form.repeatable ? (
                            <TextField
                                label={t("triggers.fields.cooldownTurns")}
                                type="number"
                                value={form.cooldown_turns ?? ""}
                                onChange={(value) => updateForm("cooldown_turns", value === "" ? null : value)}
                            />
                        ) : null}
                    </>
                ) : (
                    <CheckboxField label={t("triggers.fields.reversible")} checked={form.reversible} onChange={(value) => updateForm("reversible", value)} />
                )}

                {editing ? (
                    <div className="trigger-status-controls">
                        <FieldLabel label={t("triggers.fields.status")} required={false} />
                        <span className={`trigger-status-badge trigger-status-${editing.status}`}>
                            {t(`triggers.statuses.${editing.status}`)}
                        </span>
                        {editing.status === "disabled" ? (
                            <button type="button" className="secondary-button" disabled={saving} onClick={() => toggleStatus(editing, "dormant")}>
                                {t("triggers.enable")}
                            </button>
                        ) : (
                            <button type="button" className="secondary-button" disabled={saving} onClick={() => toggleStatus(editing, "disabled")}>
                                {t("triggers.disable")}
                            </button>
                        )}
                    </div>
                ) : null}

                <div className="modal-actions inline-actions">
                    <button type="button" className="primary-button" disabled={saving || !formValid} onClick={save}>
                        {editing ? t("worldCreate.newEditor.updateEntity") : t("worldCreate.newEditor.saveEntity")}
                    </button>
                    {editing ? (
                        <>
                            <button type="button" className="secondary-button" onClick={beginCreate}>
                                {t("worldCreate.cancel")}
                            </button>
                            <button type="button" className="secondary-button danger-button" disabled={saving} onClick={() => remove(editing)}>
                                {t("worldCreate.newEditor.deleteEntity")}
                            </button>
                        </>
                    ) : null}
                </div>
            </div>
        </section>
    );
}
