import { useTranslation } from "react-i18next";

import { ConnectionProviderIcon } from "@/components/ConnectionProviderIcon";

export function ConnectionProfileTile({ profile, providerLabels }) {
    const { t } = useTranslation();
    const providerLabel = providerLabels[profile.provider] ?? profile.provider;
    const profileName = profile.name || t("connections.unnamedProfile", { provider: providerLabel });

    return (
        <article className="connection-tile">
            <div className="connection-tile-main">
                <div className="connection-icon-frame" aria-hidden="true">
                    <ConnectionProviderIcon provider={profile.provider} />
                </div>
                <div className="connection-name" title={profileName}>
                    {profileName}
                </div>
            </div>

            <div className="connection-actions">
                <button
                    type="button"
                    className="connection-action-button"
                    aria-label={t("connections.actions.editProfile", { name: profileName })}
                >
                    {t("connections.actions.edit")}
                </button>
                <button
                    type="button"
                    className="connection-action-button danger"
                    aria-label={t("connections.actions.deleteProfile", { name: profileName })}
                >
                    {t("connections.actions.delete")}
                </button>
            </div>
        </article>
    );
}
