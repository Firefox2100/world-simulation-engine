import { useState } from "react";
import { getSimulationCoverUrl } from "@/api/simulations";
import placeholderImage from "@/assets/placeholder.png";

export function SimulationCard({ simulation }) {
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
            </div>

            <div className="simulation-card-body">
                <h2 className="simulation-card-title">{simulation.name}</h2>
            </div>

            <div className="simulation-card-description">
                <p>{simulation.description}</p>
            </div>
        </article>
    );
}
