import { useTranslation } from "react-i18next";

import { useImageGenerationAction } from "@/shared/useImageGenerationAction";

export function GenerateCoverImageButton({ label, onGenerate, disabled = false }) {
    const { t } = useTranslation();
    const { state, error, trigger } = useImageGenerationAction(onGenerate);

    return (
        <>
            <button
                type="button"
                className="secondary-button"
                onClick={trigger}
                disabled={disabled || state === "generating"}
            >
                {state === "generating" ? t("simulationDetails.generatingCoverImage") : label}
            </button>
            {state === "success" ? (
                <span className="status-text">{t("simulationDetails.coverImageGenerated")}</span>
            ) : null}
            {state === "error" ? (
                <span className="status-text error-text">
                    {t("simulationDetails.coverImageError", { error })}
                </span>
            ) : null}
        </>
    );
}
