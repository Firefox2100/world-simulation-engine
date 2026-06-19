import { ConnectionProfileTile } from "@/components/ConnectionProfileTile";

export function ConnectionProfileColumn({ title, emptyText, profiles, providerLabels, createLabel, onCreate }) {
    return (
        <section className="connection-column">
            <div className="connection-column-header">
                <h2>{title}</h2>
                <button type="button" className="secondary-button" onClick={onCreate}>
                    {createLabel}
                </button>
            </div>

            {profiles.length === 0 ? (
                <p className="connection-empty-text">{emptyText}</p>
            ) : (
                <div className="connection-list">
                    {profiles.map((profile) => (
                        <ConnectionProfileTile
                            key={profile.id}
                            profile={profile}
                            providerLabels={providerLabels}
                        />
                    ))}
                </div>
            )}
        </section>
    );
}
