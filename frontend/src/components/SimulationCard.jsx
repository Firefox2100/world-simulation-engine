import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getSimulationCoverUrl } from "@/api/simulations";
import placeholderImage from "@/assets/placeholder.png";
import { WorldActionButton } from "@/components/WorldActionButton";

export function SimulationCard({ simulation, onOpenChat, onDelete }) {
    const { t } = useTranslation();
    const [imageSrc, setImageSrc] = useState(getSimulationCoverUrl(simulation.id));

    return (
        <article className="simulation-card">
            <div className="simulation-card-image-frame">
                <img
                    src={imageSrc}
                    alt={simulation.name}
                    className="simulation-card-image"
                    onError={() => setImageSrc(placeholderImage)}
                />
                <div className="simulation-card-description">
                    <p>{simulation.description}</p>
                </div>
            </div>

            <div className="simulation-card-body">
                <h2 className="simulation-card-title">{simulation.name}</h2>
                <div className="simulation-actions">
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
            </div>
        </article>
    );
}
