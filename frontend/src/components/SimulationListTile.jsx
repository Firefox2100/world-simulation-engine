import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getSimulationCoverUrl } from "@/api/simulations";
import placeholderImage from "@/assets/placeholder.png";
import { WorldActionButton } from "@/components/WorldActionButton";

export function SimulationListTile({ simulation, onOpenChat, onDelete }) {
    const { t } = useTranslation();
    const [imageSrc, setImageSrc] = useState(getSimulationCoverUrl(simulation.id));

    return (
        <article className="simulation-tile">
            <img
                src={imageSrc}
                alt={simulation.name}
                className="simulation-tile-image"
                onError={() => setImageSrc(placeholderImage)}
            />

            <div className="simulation-tile-content">
                <h2 className="simulation-tile-title">{simulation.name}</h2>
            </div>

            <div className="simulation-tile-actions">
                <WorldActionButton
                    type="createSimulation"
                    label={t("home.actions.openChat")}
                    onClick={onOpenChat}
                />
                <WorldActionButton
                    type="delete"
                    label={t("home.actions.delete")}
                    danger
                    onClick={onDelete}
                />
            </div>
        </article>
    );
}
