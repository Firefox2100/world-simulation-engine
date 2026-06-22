import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";

import {
    fetchImageConnectionProfiles,
    fetchLlmConnectionProfiles,
} from "@/api/connections";
import { ConnectionCreateModal } from "@/components/ConnectionCreateModal";
import { ConnectionProfileColumn } from "@/components/ConnectionProfileColumn";

export function ConnectionsPage() {
    const { t } = useTranslation();
    const [llmProfiles, setLlmProfiles] = useState([]);
    const [imageProfiles, setImageProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [createModalType, setCreateModalType] = useState(null);
    const [editingConnection, setEditingConnection] = useState(null);

    const providerLabels = {
        openai: t("connections.providers.openai"),
        ollama: t("connections.providers.ollama"),
        comfy_ui: t("connections.providers.comfy_ui"),
    };

    async function loadConnections() {
        try {
            setLoading(true);
            setError(null);

            const [llmData, imageData] = await Promise.all([
                fetchLlmConnectionProfiles(),
                fetchImageConnectionProfiles(),
            ]);

            setLlmProfiles(llmData);
            setImageProfiles(imageData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        startTransition(() => {
            loadConnections();
        });
    }, []);

    async function handleCreated() {
        setCreateModalType(null);
        setEditingConnection(null);
        await loadConnections();
    }

    function openEditModal(type, profile) {
        setEditingConnection({ type, profile });
    }

    return (
        <section>
            <div className="page-heading">
                <h1>{t("connections.title")}</h1>
                <p>{t("connections.subtitle")}</p>
            </div>

            {loading ? (
                <p className="status-text">{t("connections.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("connections.error", { error })}</p>
            ) : (
                <div className="connections-layout">
                    <ConnectionProfileColumn
                        title={t("connections.llmTitle")}
                        emptyText={t("connections.empty.llm")}
                        profiles={llmProfiles}
                        providerLabels={providerLabels}
                        createLabel={t("connections.actions.create")}
                        onCreate={() => setCreateModalType("llm")}
                        onEdit={(profile) => openEditModal("llm", profile)}
                    />
                    <ConnectionProfileColumn
                        title={t("connections.imageTitle")}
                        emptyText={t("connections.empty.image")}
                        profiles={imageProfiles}
                        providerLabels={providerLabels}
                        createLabel={t("connections.actions.create")}
                        onCreate={() => setCreateModalType("image")}
                        onEdit={(profile) => openEditModal("image", profile)}
                    />
                </div>
            )}

            {createModalType ? (
                <ConnectionCreateModal
                    type={createModalType}
                    providerLabels={providerLabels}
                    onClose={() => setCreateModalType(null)}
                    onCreated={handleCreated}
                />
            ) : null}

            {editingConnection ? (
                <ConnectionCreateModal
                    type={editingConnection.type}
                    profile={editingConnection.profile}
                    providerLabels={providerLabels}
                    onClose={() => setEditingConnection(null)}
                    onCreated={handleCreated}
                />
            ) : null}
        </section>
    );
}
