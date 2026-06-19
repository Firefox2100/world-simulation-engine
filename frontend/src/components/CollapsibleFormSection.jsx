import { InfoTooltip } from "@/components/InfoTooltip";

export function CollapsibleFormSection({
    title,
    tooltipLabel,
    tooltip,
    open,
    onToggle,
    children,
}) {
    return (
        <section className="collapsible-form-section">
            <div className="collapsible-form-section-header">
                <button type="button" className="collapsible-form-section-title" onClick={onToggle}>
                    <span className={`collapse-indicator${open ? " open" : ""}`}>›</span>
                    {title}
                </button>
                <InfoTooltip label={tooltipLabel} text={tooltip} />
            </div>

            {open ? <div className="collapsible-form-section-body">{children}</div> : null}
        </section>
    );
}
