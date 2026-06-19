import { useState } from "react";

export function InfoTooltip({ label, text }) {
    const [open, setOpen] = useState(false);

    return (
        <span className="info-tooltip">
            <button
                type="button"
                className="info-tooltip-button"
                aria-label={label}
                aria-expanded={open}
                onClick={() => setOpen((current) => !current)}
                onBlur={() => setOpen(false)}
            >
                ?
            </button>
            <span className={`info-tooltip-content${open ? " open" : ""}`} role="tooltip">
                {text}
            </span>
        </span>
    );
}
