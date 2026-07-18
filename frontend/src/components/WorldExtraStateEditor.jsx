import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CollapsibleFormSection } from "@/components/CollapsibleFormSection";
import {
    makeEquipment,
    makeFaction,
    makeFactionRelationship,
    makeInventory,
    makeItem,
    makeTask,
    makeTurnRecord,
    makeWorldEntry,
    makeWorldEntryKeyword,
} from "@/shared/initialWorldStateModel";

const relationshipTypes = ["faction", "item", "character"];
const equipmentStatuses = ["equipped", "idle"];
const taskPriorities = ["urgent", "important", "normal", "background"];
const taskStatuses = ["paused", "in_progress", "completed", "failed", "abandoned"];
const taskTypes = ["main_quest", "side_quest", "daily"];
const turnTypes = ["user_input", "ai_response", "ai_continue", "ai_wait"];
const entryVisibilities = ["known", "suspected", "perceived", "inferred"];
const narrationPermissions = ["visible", "may_hint", "invisible"];
const recallTypes = ["always", "keyword", "semantic", "chained"];

function labelForCharacter(character) {
    return character.name.trim() || `Character ${character.id}`;
}

function labelForFaction(faction) {
    return faction.name.trim() || `Faction ${faction.id}`;
}

function allItems(state) {
    return state.inventories.flatMap((inventory) => inventory.items);
}

export function WorldExtraStateEditor({ value, onChange, embedded = false }) {
    const { t } = useTranslation();
    const [openSections, setOpenSections] = useState({
        factions: false,
        faction_relationships: false,
        inventory: false,
        tasks: false,
        world_entries: false,
        turn_records: false,
    });

    function toggle(section) {
        setOpenSections((current) => ({ ...current, [section]: !current[section] }));
    }

    function setField(collection, index, field, fieldValue) {
        onChange({
            ...value,
            [collection]: value[collection].map((item, itemIndex) =>
                itemIndex === index ? { ...item, [field]: fieldValue } : item,
            ),
        });
    }

    function remove(collection, index) {
        onChange({
            ...value,
            [collection]: value[collection].filter((_, itemIndex) => itemIndex !== index),
        });
    }

    function addFaction() {
        const id = value.nextIds.faction;
        onChange({
            ...value,
            factions: [...value.factions, makeFaction(id)],
            nextIds: { ...value.nextIds, faction: id + 1 },
        });
    }

    function addRelationship() {
        onChange({
            ...value,
            faction_relationships: [...value.faction_relationships, makeFactionRelationship()],
        });
    }

    function addInventory() {
        const firstCharacter = value.characters[0]?.id ?? "";
        onChange({
            ...value,
            inventories: [...value.inventories, makeInventory(firstCharacter)],
        });
    }

    function updateInventory(index, updater) {
        onChange({
            ...value,
            inventories: value.inventories.map((inventory, inventoryIndex) =>
                inventoryIndex === index ? updater(inventory) : inventory,
            ),
        });
    }

    function addInventoryItem(inventoryIndex) {
        const id = value.nextIds.item;
        onChange({
            ...value,
            inventories: value.inventories.map((inventory, index) =>
                index === inventoryIndex
                    ? { ...inventory, items: [...inventory.items, makeItem(id)] }
                    : inventory,
            ),
            nextIds: { ...value.nextIds, item: id + 1 },
        });
    }

    function addInventoryEquipment(inventoryIndex) {
        const id = value.nextIds.equipment;
        onChange({
            ...value,
            inventories: value.inventories.map((inventory, index) =>
                index === inventoryIndex
                    ? { ...inventory, equipments: [...inventory.equipments, makeEquipment(id)] }
                    : inventory,
            ),
            nextIds: { ...value.nextIds, equipment: id + 1 },
        });
    }

    function updateInventoryObject(inventoryIndex, key, objectIndex, field, fieldValue) {
        updateInventory(inventoryIndex, (inventory) => ({
            ...inventory,
            [key]: inventory[key].map((item, index) =>
                index === objectIndex ? { ...item, [field]: fieldValue } : item,
            ),
        }));
    }

    function removeInventoryObject(inventoryIndex, key, objectIndex) {
        updateInventory(inventoryIndex, (inventory) => ({
            ...inventory,
            [key]: inventory[key].filter((_, index) => index !== objectIndex),
        }));
    }

    function addTask() {
        const id = value.nextIds.task;
        onChange({
            ...value,
            tasks: [...value.tasks, makeTask(id)],
            nextIds: { ...value.nextIds, task: id + 1 },
        });
    }

    function toggleTaskCharacter(taskIndex, characterId) {
        const id = String(characterId);
        setField(
            "tasks",
            taskIndex,
            "character_ids",
            value.tasks[taskIndex].character_ids.includes(id)
                ? value.tasks[taskIndex].character_ids.filter((current) => current !== id)
                : [...value.tasks[taskIndex].character_ids, id],
        );
    }

    function addWorldEntry() {
        const id = value.nextIds.worldEntry;
        onChange({
            ...value,
            world_entries: [...value.world_entries, makeWorldEntry(id)],
            nextIds: { ...value.nextIds, worldEntry: id + 1 },
        });
    }

    function addTurnRecord() {
        const id = value.nextIds.turnRecord;
        onChange({
            ...value,
            turn_records: [...value.turn_records, makeTurnRecord(id)],
            nextIds: { ...value.nextIds, turnRecord: id + 1 },
        });
    }

    function toggleEntryScope(entryIndex, characterId) {
        const id = String(characterId);
        const entry = value.world_entries[entryIndex];
        setField(
            "world_entries",
            entryIndex,
            "scope",
            entry.scope.includes(id)
                ? entry.scope.filter((current) => current !== id)
                : [...entry.scope, id],
        );
    }

    function toggleChainedEntry(entryIndex, chainedId) {
        const id = String(chainedId);
        const entry = value.world_entries[entryIndex];
        setField(
            "world_entries",
            entryIndex,
            "chained_ids",
            entry.chained_ids.includes(id)
                ? entry.chained_ids.filter((current) => current !== id)
                : [...entry.chained_ids, id],
        );
    }

    function addKeyword(entryIndex) {
        setField("world_entries", entryIndex, "keywords", [
            ...value.world_entries[entryIndex].keywords,
            makeWorldEntryKeyword(),
        ]);
    }

    function updateKeyword(entryIndex, keywordIndex, field, fieldValue) {
        const entry = value.world_entries[entryIndex];
        setField(
            "world_entries",
            entryIndex,
            "keywords",
            entry.keywords.map((keyword, index) =>
                index === keywordIndex ? { ...keyword, [field]: fieldValue } : keyword,
            ),
        );
    }

    function removeKeyword(entryIndex, keywordIndex) {
        const entry = value.world_entries[entryIndex];
        setField(
            "world_entries",
            entryIndex,
            "keywords",
            entry.keywords.filter((_, index) => index !== keywordIndex),
        );
    }

    function entityOptions(type) {
        if (type === "character") {
            return value.characters.map((character) => ({
                id: character.id,
                label: labelForCharacter(character),
            }));
        }

        if (type === "faction") {
            return value.factions.map((faction) => ({
                id: faction.id,
                label: labelForFaction(faction),
            }));
        }

        return allItems(value).map((item) => ({
            id: item.id,
            label: item.name.trim() || `Item ${item.id}`,
        }));
    }

    const content = (
        <>
                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.factions")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.factions"),
                        })}
                        tooltip={t("worldCreate.extraState.factionsTooltip")}
                        open={openSections.factions}
                        onToggle={() => toggle("factions")}
                    >
                        <div className="data-preset-list">
                            {value.factions.map((faction, index) => (
                                <div className="data-preset-item" key={faction.id}>
                                    <div className="prompt-message-header">
                                        <strong>
                                            {t("worldCreate.extraState.factionTitle", {
                                                number: index + 1,
                                            })}
                                        </strong>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("factions", index)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    {["name", "description"].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                            <input
                                                className="single-line-input"
                                                value={faction[field]}
                                                onChange={(event) =>
                                                    setField(
                                                        "factions",
                                                        index,
                                                        field,
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </div>
                                    ))}
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addFaction}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.factionRelationships")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.factionRelationships"),
                        })}
                        tooltip={t("worldCreate.extraState.factionRelationshipsTooltip")}
                        open={openSections.faction_relationships}
                        onToggle={() => toggle("faction_relationships")}
                    >
                        <div className="data-preset-list">
                            {value.faction_relationships.map((relationship, index) => (
                                <div className="data-preset-item" key={index}>
                                    <div className="prompt-message-header">
                                        <strong>
                                            {t("worldCreate.extraState.relationshipTitle", {
                                                number: index + 1,
                                            })}
                                        </strong>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("faction_relationships", index)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    {["from", "to"].map((side) => (
                                        <div className="relationship-row" key={side}>
                                            <label>
                                                {t(`worldCreate.extraState.fields.${side}`)}
                                            </label>
                                            <select
                                                className="single-line-input"
                                                value={relationship[`${side}_type`]}
                                                onChange={(event) => {
                                                    setField(
                                                        "faction_relationships",
                                                        index,
                                                        `${side}_type`,
                                                        event.target.value,
                                                    );
                                                    setField("faction_relationships", index, `${side}_id`, "");
                                                }}
                                            >
                                                {relationshipTypes.map((type) => (
                                                    <option key={type} value={type}>
                                                        {t(`worldCreate.enums.relationshipEntity.${type}`)}
                                                    </option>
                                                ))}
                                            </select>
                                            <select
                                                className="single-line-input"
                                                value={relationship[`${side}_id`]}
                                                onChange={(event) =>
                                                    setField(
                                                        "faction_relationships",
                                                        index,
                                                        `${side}_id`,
                                                        event.target.value,
                                                    )
                                                }
                                            >
                                                <option value="">
                                                    {t("worldCreate.extraState.fields.selectEntity")}
                                                </option>
                                                {entityOptions(relationship[`${side}_type`]).map((option) => (
                                                    <option key={option.id} value={option.id}>
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    ))}
                                    <div className="form-field inline-field">
                                        <label>{t("worldCreate.extraState.fields.relationship")}</label>
                                        <input
                                            className="single-line-input"
                                            value={relationship.relationship}
                                            onChange={(event) =>
                                                setField(
                                                    "faction_relationships",
                                                    index,
                                                    "relationship",
                                                    event.target.value,
                                                )
                                            }
                                        />
                                    </div>
                                    <label className="checkbox-field agent-preset-enable">
                                        <span>{t("worldCreate.extraState.fields.private")}</span>
                                        <input
                                            type="checkbox"
                                            checked={relationship.private}
                                            onChange={(event) =>
                                                setField(
                                                    "faction_relationships",
                                                    index,
                                                    "private",
                                                    event.target.checked,
                                                )
                                            }
                                        />
                                    </label>
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addRelationship}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.inventory")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.inventory"),
                        })}
                        tooltip={t("worldCreate.extraState.inventoryTooltip")}
                        open={openSections.inventory}
                        onToggle={() => toggle("inventory")}
                    >
                        <div className="data-preset-list">
                            {value.inventories.map((inventory, inventoryIndex) => (
                                <div className="data-preset-item" key={inventoryIndex}>
                                    <div className="prompt-message-header">
                                        <select
                                            className="single-line-input"
                                            value={inventory.character_id}
                                            onChange={(event) =>
                                                updateInventory(inventoryIndex, (current) => ({
                                                    ...current,
                                                    character_id: event.target.value,
                                                }))
                                            }
                                        >
                                            <option value="">
                                                {t("worldCreate.extraState.fields.selectCharacter")}
                                            </option>
                                            {value.characters.map((character) => (
                                                <option key={character.id} value={character.id}>
                                                    {labelForCharacter(character)}
                                                </option>
                                            ))}
                                        </select>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("inventories", inventoryIndex)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>

                                    <div className="data-values-editor">
                                        <div className="data-values-header">
                                            <span>{t("worldCreate.extraState.items")}</span>
                                            <button
                                                type="button"
                                                className="secondary-button"
                                                onClick={() => addInventoryItem(inventoryIndex)}
                                            >
                                                {t("worldCreate.add")}
                                            </button>
                                        </div>
                                        {inventory.items.map((item, itemIndex) => (
                                            <div className="data-preset-item" key={item.id}>
                                                <div className="prompt-message-header">
                                                    <strong>
                                                        {t("worldCreate.extraState.itemTitle", {
                                                            number: itemIndex + 1,
                                                        })}
                                                    </strong>
                                                    <button
                                                        type="button"
                                                        className="secondary-button"
                                                        onClick={() =>
                                                            removeInventoryObject(
                                                                inventoryIndex,
                                                                "items",
                                                                itemIndex,
                                                            )
                                                        }
                                                    >
                                                        {t("worldCreate.remove")}
                                                    </button>
                                                </div>
                                                {["name", "description", "quality", "quantity"].map((field) => (
                                                    <div className="form-field inline-field" key={field}>
                                                        <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                                        <input
                                                            className="single-line-input"
                                                            type={field === "quantity" ? "number" : "text"}
                                                            value={item[field]}
                                                            onChange={(event) =>
                                                                updateInventoryObject(
                                                                    inventoryIndex,
                                                                    "items",
                                                                    itemIndex,
                                                                    field,
                                                                    event.target.value,
                                                                )
                                                            }
                                                        />
                                                    </div>
                                                ))}
                                                <label className="checkbox-field agent-preset-enable">
                                                    <span>{t("worldCreate.extraState.fields.unique")}</span>
                                                    <input
                                                        type="checkbox"
                                                        checked={item.unique}
                                                        onChange={(event) =>
                                                            updateInventoryObject(
                                                                inventoryIndex,
                                                                "items",
                                                                itemIndex,
                                                                "unique",
                                                                event.target.checked,
                                                            )
                                                        }
                                                    />
                                                </label>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="data-values-editor">
                                        <div className="data-values-header">
                                            <span>{t("worldCreate.extraState.equipment")}</span>
                                            <button
                                                type="button"
                                                className="secondary-button"
                                                onClick={() => addInventoryEquipment(inventoryIndex)}
                                            >
                                                {t("worldCreate.add")}
                                            </button>
                                        </div>
                                        {inventory.equipments.map((equipment, equipmentIndex) => (
                                            <div className="data-preset-item" key={equipment.id}>
                                                <div className="prompt-message-header">
                                                    <strong>
                                                        {t("worldCreate.extraState.equipmentTitle", {
                                                            number: equipmentIndex + 1,
                                                        })}
                                                    </strong>
                                                    <button
                                                        type="button"
                                                        className="secondary-button"
                                                        onClick={() =>
                                                            removeInventoryObject(
                                                                inventoryIndex,
                                                                "equipments",
                                                                equipmentIndex,
                                                            )
                                                        }
                                                    >
                                                        {t("worldCreate.remove")}
                                                    </button>
                                                </div>
                                                {["name", "description", "quality"].map((field) => (
                                                    <div className="form-field inline-field" key={field}>
                                                        <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                                        <input
                                                            className="single-line-input"
                                                            value={equipment[field]}
                                                            onChange={(event) =>
                                                                updateInventoryObject(
                                                                    inventoryIndex,
                                                                    "equipments",
                                                                    equipmentIndex,
                                                                    field,
                                                                    event.target.value,
                                                                )
                                                            }
                                                        />
                                                    </div>
                                                ))}
                                                <div className="form-field inline-field">
                                                    <label>{t("worldCreate.extraState.fields.status")}</label>
                                                    <select
                                                        className="single-line-input"
                                                        value={equipment.status}
                                                        onChange={(event) =>
                                                            updateInventoryObject(
                                                                inventoryIndex,
                                                                "equipments",
                                                                equipmentIndex,
                                                                "status",
                                                                event.target.value,
                                                            )
                                                        }
                                                    >
                                                        {equipmentStatuses.map((status) => (
                                                            <option key={status} value={status}>
                                                                {t(`worldCreate.enums.equipmentStatus.${status}`)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addInventory}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.tasks")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.tasks"),
                        })}
                        tooltip={t("worldCreate.extraState.tasksTooltip")}
                        open={openSections.tasks}
                        onToggle={() => toggle("tasks")}
                    >
                        <div className="data-preset-list">
                            {value.tasks.map((task, taskIndex) => (
                                <div className="data-preset-item" key={task.id}>
                                    <div className="prompt-message-header">
                                        <strong>
                                            {t("worldCreate.extraState.taskTitle", {
                                                number: taskIndex + 1,
                                            })}
                                        </strong>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("tasks", taskIndex)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    <div className="checkbox-grid agent-checkbox-grid">
                                        {value.characters.map((character) => (
                                            <label className="checkbox-field" key={character.id}>
                                                <span>{labelForCharacter(character)}</span>
                                                <input
                                                    type="checkbox"
                                                    checked={task.character_ids.includes(String(character.id))}
                                                    onChange={() => toggleTaskCharacter(taskIndex, character.id)}
                                                />
                                            </label>
                                        ))}
                                    </div>
                                    {[
                                        ["priority", taskPriorities],
                                        ["status", taskStatuses],
                                        ["type", taskTypes],
                                    ].map(([field, options]) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                            <select
                                                className="single-line-input"
                                                value={task[field]}
                                                onChange={(event) =>
                                                    setField("tasks", taskIndex, field, event.target.value)
                                                }
                                            >
                                                {options.map((option) => (
                                                    <option key={option} value={option}>
                                                        {t(`worldCreate.enums.${field}.${option}`)}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    ))}
                                    {["goal", "progress", "source", "reward"].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                            <input
                                                className="single-line-input"
                                                type={field === "progress" ? "number" : "text"}
                                                value={task[field]}
                                                onChange={(event) =>
                                                    setField("tasks", taskIndex, field, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))}
                                    <label className="checkbox-field agent-preset-enable">
                                        <span>{t("worldCreate.extraState.fields.private")}</span>
                                        <input
                                            type="checkbox"
                                            checked={task.private}
                                            onChange={(event) =>
                                                setField("tasks", taskIndex, "private", event.target.checked)
                                            }
                                        />
                                    </label>
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addTask}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.worldEntries")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.worldEntries"),
                        })}
                        tooltip={t("worldCreate.extraState.worldEntriesTooltip")}
                        open={openSections.world_entries}
                        onToggle={() => toggle("world_entries")}
                    >
                        <div className="data-preset-list">
                            {value.world_entries.map((entry, entryIndex) => (
                                <div className="data-preset-item" key={entry.id}>
                                    <div className="prompt-message-header">
                                        <strong>
                                            {t("worldCreate.extraState.worldEntryTitle", {
                                                number: entryIndex + 1,
                                            })}
                                        </strong>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("world_entries", entryIndex)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    <div className="form-field inline-field">
                                        <label>{t("worldCreate.extraState.fields.scope")}</label>
                                        <select
                                            className="single-line-input"
                                            value={entry.scopeMode}
                                            onChange={(event) =>
                                                setField("world_entries", entryIndex, "scopeMode", event.target.value)
                                            }
                                        >
                                            {["everyone", "no_one", "characters"].map((mode) => (
                                                <option key={mode} value={mode}>
                                                    {t(`worldCreate.extraState.scopeMode.${mode}`)}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    {entry.scopeMode === "characters" ? (
                                        <div className="checkbox-grid agent-checkbox-grid">
                                            {value.characters.map((character) => (
                                                <label className="checkbox-field" key={character.id}>
                                                    <span>{labelForCharacter(character)}</span>
                                                    <input
                                                        type="checkbox"
                                                        checked={entry.scope.includes(String(character.id))}
                                                        onChange={() => toggleEntryScope(entryIndex, character.id)}
                                                    />
                                                </label>
                                            ))}
                                        </div>
                                    ) : null}
                                    {["content", "confidence", "created_at", "semantic_instruction"].map((field) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                            <input
                                                className="single-line-input"
                                                type={field === "confidence" || field === "created_at" ? "number" : "text"}
                                                step={field === "confidence" ? "0.1" : undefined}
                                                value={entry[field]}
                                                onChange={(event) =>
                                                    setField("world_entries", entryIndex, field, event.target.value)
                                                }
                                            />
                                        </div>
                                    ))}
                                    {[
                                        ["visibility", entryVisibilities],
                                        ["narration_permission", narrationPermissions],
                                        ["recall_type", recallTypes],
                                    ].map(([field, options]) => (
                                        <div className="form-field inline-field" key={field}>
                                            <label>{t(`worldCreate.extraState.fields.${field}`)}</label>
                                            <select
                                                className="single-line-input"
                                                value={entry[field]}
                                                onChange={(event) =>
                                                    setField("world_entries", entryIndex, field, event.target.value)
                                                }
                                            >
                                                {options.map((option) => (
                                                    <option key={option} value={option}>
                                                        {t(`worldCreate.enums.${field}.${option}`)}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    ))}
                                    {entry.recall_type === "keyword" ? (
                                        <div className="data-values-editor">
                                            <div className="data-values-header">
                                                <span>{t("worldCreate.extraState.fields.keywords")}</span>
                                                <button
                                                    type="button"
                                                    className="secondary-button"
                                                    onClick={() => addKeyword(entryIndex)}
                                                >
                                                    {t("worldCreate.add")}
                                                </button>
                                            </div>
                                            {entry.keywords.map((keyword, keywordIndex) => (
                                                <div className="relationship-row" key={keywordIndex}>
                                                    <input
                                                        className="single-line-input"
                                                        value={keyword.keyword}
                                                        onChange={(event) =>
                                                            updateKeyword(
                                                                entryIndex,
                                                                keywordIndex,
                                                                "keyword",
                                                                event.target.value,
                                                            )
                                                        }
                                                    />
                                                    <input
                                                        className="single-line-input"
                                                        type="number"
                                                        step="0.1"
                                                        value={keyword.similarity}
                                                        onChange={(event) =>
                                                            updateKeyword(
                                                                entryIndex,
                                                                keywordIndex,
                                                                "similarity",
                                                                event.target.value,
                                                            )
                                                        }
                                                    />
                                                    <button
                                                        type="button"
                                                        className="secondary-button"
                                                        onClick={() => removeKeyword(entryIndex, keywordIndex)}
                                                    >
                                                        {t("worldCreate.remove")}
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    ) : null}
                                    {entry.recall_type === "chained" ? (
                                        <div className="checkbox-grid agent-checkbox-grid">
                                            {value.world_entries
                                                .filter((candidate) => candidate.id !== entry.id)
                                                .map((candidate) => (
                                                    <label className="checkbox-field" key={candidate.id}>
                                                        <span>
                                                            {candidate.content.trim() ||
                                                                t("worldCreate.extraState.worldEntryTitle", {
                                                                    number: candidate.id,
                                                                })}
                                                        </span>
                                                        <input
                                                            type="checkbox"
                                                            checked={entry.chained_ids.includes(String(candidate.id))}
                                                            onChange={() =>
                                                                toggleChainedEntry(entryIndex, candidate.id)
                                                            }
                                                        />
                                                    </label>
                                                ))}
                                        </div>
                                    ) : null}
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addWorldEntry}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>

                <div className="agent-role-section">
                    <CollapsibleFormSection
                        title={t("worldCreate.extraState.turnRecords")}
                        tooltipLabel={t("worldCreate.tooltipLabel", {
                            field: t("worldCreate.extraState.turnRecords"),
                        })}
                        tooltip={t("worldCreate.extraState.turnRecordsTooltip")}
                        open={openSections.turn_records}
                        onToggle={() => toggle("turn_records")}
                    >
                        <div className="data-preset-list">
                            {value.turn_records.map((record, recordIndex) => (
                                <div className="data-preset-item" key={record.id}>
                                    <div className="prompt-message-header">
                                        <strong>
                                            {t("worldCreate.extraState.turnRecordTitle", {
                                                number: recordIndex + 1,
                                            })}
                                        </strong>
                                        <button
                                            type="button"
                                            className="secondary-button"
                                            onClick={() => remove("turn_records", recordIndex)}
                                        >
                                            {t("worldCreate.remove")}
                                        </button>
                                    </div>
                                    <div className="agent-number-grid">
                                        <div className="compact-form-field">
                                            <label>
                                                {t("worldCreate.extraState.fields.turn_number")}
                                            </label>
                                            <input
                                                className="single-line-input"
                                                type="number"
                                                value={record.turn_number}
                                                onChange={(event) =>
                                                    setField(
                                                        "turn_records",
                                                        recordIndex,
                                                        "turn_number",
                                                        event.target.value,
                                                    )
                                                }
                                            />
                                        </div>
                                        <div className="compact-form-field">
                                            <label>{t("worldCreate.extraState.fields.type")}</label>
                                            <select
                                                className="single-line-input"
                                                value={record.type}
                                                onChange={(event) =>
                                                    setField(
                                                        "turn_records",
                                                        recordIndex,
                                                        "type",
                                                        event.target.value,
                                                    )
                                                }
                                            >
                                                {turnTypes.map((type) => (
                                                    <option key={type} value={type}>
                                                        {t(`worldCreate.enums.turnType.${type}`)}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="form-field">
                                        <label>{t("worldCreate.extraState.fields.narration")}</label>
                                        <textarea
                                            className="multi-line-input prompt-template-input"
                                            value={record.narration}
                                            onChange={(event) =>
                                                setField(
                                                    "turn_records",
                                                    recordIndex,
                                                    "narration",
                                                    event.target.value,
                                                )
                                            }
                                        />
                                    </div>
                                </div>
                            ))}
                            <div className="prompt-add-row">
                                <button type="button" className="secondary-button" onClick={addTurnRecord}>
                                    {t("worldCreate.add")}
                                </button>
                            </div>
                        </div>
                    </CollapsibleFormSection>
                </div>
        </>
    );

    if (embedded) {
        return content;
    }

    return (
        <div className="initial-world-state-editor">
            <div className="nested-form-stack">{content}</div>
        </div>
    );
}
