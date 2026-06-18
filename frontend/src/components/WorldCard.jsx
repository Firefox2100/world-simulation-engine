import { useState } from "react";

import { getWorldCoverUrl } from "@/api/worlds";
import placeholderImage from "@/assets/placeholder.png";

export function WorldCard({ world }) {
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
            </div>

            <div className="world-card-body">
                <h2 className="world-card-title">{world.name}</h2>
            </div>

            <div className="world-card-description">
                <p>{world.description}</p>
            </div>
        </article>
    );
}
