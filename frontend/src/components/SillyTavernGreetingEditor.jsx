export function SillyTavernGreetingEditor({ greeting, selected, onSelect, onChange }) {
    return (
        <div className={`st-import-greeting${selected ? " st-import-greeting-selected" : ""}`}>
            <label className="st-import-greeting-header">
                <input
                    type="radio"
                    name="st-import-selected-greeting"
                    checked={selected}
                    onChange={onSelect}
                />
                <span className="st-import-greeting-label">{greeting.label}</span>
            </label>
            <textarea
                className="multi-line-input"
                value={greeting.text}
                onChange={(event) => onChange(event.target.value)}
            />
        </div>
    );
}
