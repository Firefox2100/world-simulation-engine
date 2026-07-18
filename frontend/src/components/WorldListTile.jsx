import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getWorldCoverUrl } from "@/api/worlds";
import placeholderImage from "@/assets/placeholder/world.svg";
import { WorldActionButton } from "@/components/WorldActionButton";

export function WorldListTile({ world, onEdit, onDelete, onCreateSimulation }) {
    const { t } = useTranslation();
    const [imageSrc, setImageSrc] = useState(getWorldCoverUrl(world.id));

    return (
        <article className="world-tile">
            <img
                src={imageSrc}
                alt={world.name}
                className="world-tile-image"
                onError={() => setImageSrc(placeholderImage)}
            />

            <div className="world-tile-content">
                <h2 className="world-tile-title">{world.name}</h2>
            </div>

            <div className="world-tile-actions">
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
        </article>
    );
}
