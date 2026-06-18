import { useState } from "react";
import { getSimulationCoverUrl } from "@/api/simulations";
import placeholderImage from "@/assets/placeholder.png";

export function SimulationListTile({ simulation }) {
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
        </article>
    );
}
