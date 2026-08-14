import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export function SillyTavernDropzone({ onFileSelected, onUrlRequested, disabled }) {
    const { t } = useTranslation();
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef(null);

    function openPicker() {
        if (!disabled) {
            inputRef.current?.click();
        }
    }

    function handleDrop(event) {
        event.preventDefault();
        setDragging(false);
        if (disabled) {
            return;
        }

        const droppedFile = event.dataTransfer.files?.[0];
        if (droppedFile) {
            onFileSelected(droppedFile);
        }
    }

    return (
        <div
            className={`st-import-dropzone${dragging ? " st-import-dropzone-active" : ""}${disabled ? " st-import-dropzone-disabled" : ""}`}
            role="button"
            tabIndex={0}
            onClick={openPicker}
            onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openPicker();
                }
            }}
            onDragOver={(event) => {
                event.preventDefault();
                if (!disabled) {
                    setDragging(true);
                }
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
        >
            <p className="st-import-dropzone-prompt">{t("sillyTavernImport.dropzone.prompt")}</p>
            <p className="st-import-dropzone-hint">{t("sillyTavernImport.dropzone.hint")}</p>
            <button
                type="button"
                className="secondary-button st-import-url-button"
                disabled={disabled}
                onClick={(event) => {
                    event.stopPropagation();
                    onUrlRequested();
                }}
            >
                {t("sillyTavernImport.dropzone.fromUrl")}
            </button>
            <input
                ref={inputRef}
                type="file"
                accept=".png,image/png,.json,application/json"
                className="st-import-dropzone-input"
                disabled={disabled}
                onChange={(event) => {
                    const selected = event.target.files?.[0];
                    if (selected) {
                        onFileSelected(selected);
                    }
                    event.target.value = "";
                }}
            />
        </div>
    );
}
