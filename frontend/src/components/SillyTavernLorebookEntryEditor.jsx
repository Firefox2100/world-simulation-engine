import { useTranslation } from "react-i18next";

export function SillyTavernLorebookEntryEditor({ entry, index, onChange }) {
    const { t } = useTranslation();

    function update(patch) {
        onChange(index, { ...entry, ...patch });
    }

    const title = entry.name?.trim() || entry.comment?.trim() || t("sillyTavernImport.lorebook.untitled", { index: index + 1 });

    return (
        <div className={`st-import-entry${entry.enabled ? "" : " st-import-entry-disabled"}`}>
            <label className="st-import-entry-header">
                <input
                    type="checkbox"
                    checked={entry.enabled}
                    onChange={(event) => update({ enabled: event.target.checked })}
                />
                <span className="st-import-entry-title">{title}</span>
            </label>

            <div className="st-import-entry-body">
                <div className="form-field">
                    <label>{t("sillyTavernImport.lorebook.name")}</label>
                    <input
                        className="single-line-input"
                        type="text"
                        value={entry.name ?? ""}
                        onChange={(event) => update({ name: event.target.value })}
                    />
                </div>

                <div className="form-field">
                    <label>{t("sillyTavernImport.lorebook.keys")}</label>
                    <input
                        className="single-line-input"
                        type="text"
                        value={(entry.keys ?? []).join(", ")}
                        onChange={(event) =>
                            update({
                                keys: event.target.value
                                    .split(",")
                                    .map((key) => key.trim())
                                    .filter(Boolean),
                            })
                        }
                    />
                </div>

                <div className="form-field">
                    <label>{t("sillyTavernImport.lorebook.content")}</label>
                    <textarea
                        className="multi-line-input"
                        value={entry.content ?? ""}
                        onChange={(event) => update({ content: event.target.value })}
                    />
                </div>
            </div>
        </div>
    );
}
