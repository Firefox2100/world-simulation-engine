import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getWorldCoverUrl } from "@/api/worlds";
import placeholderImage from "@/assets/placeholder.png";
import { WorldActionButton } from "@/components/WorldActionButton";

export function WorldCard({ world, onEdit, onDelete, onCreateSimulation }) {
    const { t } = useTranslation();
    const [imageSrc, setImageSrc] = useState(getWorldCoverUrl(world.id));

    return (
        <article className="world-card">
            <div className="world-card-image-frame">
                <img
                    src={imageSrc}
                    alt={world.name}
                    className="world-card-image"
                    onError={() => setImageSrc(placeholderImage)}
                />
                <div className="world-card-description">
                    <p>{world.description}</p>
                </div>
            </div>

            <div className="world-card-body">
                <h2 className="world-card-title">{world.name}</h2>
                <div className="world-actions">
                    <WorldActionButton
                        type="edit"
                        label={t("worlds.actions.edit")}
                        onClick={() => onEdit(world)}
                    />
                    <WorldActionButton
                        type="createSimulation"
                        label={t("worlds.actions.createSimulation")}
                        onClick={() => onCreateSimulation(world)}
                    />
                    <WorldActionButton
                        type="delete"
                        label={t("worlds.actions.delete")}
                        danger
                        onClick={() => onDelete(world)}
                    />
                </div>
            </div>
        </article>
    );
}
