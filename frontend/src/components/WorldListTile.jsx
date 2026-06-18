import { useState } from "react";

import { getWorldCoverUrl } from "@/api/worlds";
import placeholderImage from "@/assets/placeholder.png";

export function WorldListTile({ world }) {
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
        </article>
    );
}
