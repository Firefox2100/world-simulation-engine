import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { createSimulationFromWorld, deleteWorld, fetchWorld, fetchWorlds } from "@/api/worlds";
import { WorldCard } from "@/components/WorldCard";
import { WorldCreateModal } from "@/components/WorldCreateModal";
import { WorldListTile } from "@/components/WorldListTile";
import { useMediaQuery } from "@/shared/useMediaQuery";

export function WorldPage() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const isDesktop = useMediaQuery("(min-width: 768px)");

    const [worlds, setWorlds] = useState([]);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState(null);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [editingWorld, setEditingWorld] = useState(null);
    const [actionError, setActionError] = useState(null);

    const limit = 24;

    async function loadWorlds(nextOffset = 0, append = false) {
        try {
            append ? setLoadingMore(true) : setLoading(true);
            setError(null);

            const data = await fetchWorlds({
                limit,
                offset: nextOffset,
            });

            setWorlds((current) => (append ? [...current, ...data] : data));
            setOffset(nextOffset + data.length);
            setHasMore(data.length === limit);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }

    useEffect(() => {
        startTransition(() => {
            loadWorlds(0, false);
        });
    }, []);

    async function handleWorldSaved() {
        setCreateModalOpen(false);
        setEditingWorld(null);
        await loadWorlds(0, false);
    }

    async function handleEditWorld(world) {
        try {
            setActionError(null);
            const data = await fetchWorld(world.id);
            setEditingWorld(data);
        } catch (err) {
            setActionError(err.message);
        }
    }

    async function handleDeleteWorld(world) {
        if (!window.confirm(t("worlds.confirmDelete", { name: world.name }))) {
            return;
        }

        try {
            setActionError(null);
            await deleteWorld(world.id);
            await loadWorlds(0, false);
        } catch (err) {
            setActionError(err.message);
        }
    }

    async function handleCreateSimulation(world) {
        try {
            setActionError(null);
            const simulation = await createSimulationFromWorld(world.id);
            navigate(`/simulations/${simulation.id}`);
        } catch (err) {
            setActionError(err.message);
        }
    }

    return (
        <section>
            <div className="page-heading page-heading-with-action">
                <div>
                    <h1>{t("worlds.title")}</h1>
                    <p>{t("worlds.subtitle")}</p>
                </div>
                <button
                    type="button"
                    className="primary-button"
                    onClick={() => setCreateModalOpen(true)}
                >
                    {t("worlds.create")}
                </button>
            </div>

            {actionError ? (
                <p className="status-text error-text">{t("worlds.actionError", { error: actionError })}</p>
            ) : null}

            {loading ? (
                <p className="status-text">{t("worlds.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("worlds.error", { error })}</p>
            ) : worlds.length === 0 ? (
                <p className="status-text">{t("worlds.empty")}</p>
            ) : isDesktop ? (
                <div className="world-grid">
                    {worlds.map((world) => (
                        <WorldCard
                            key={world.id}
                            world={world}
                            onEdit={handleEditWorld}
                            onDelete={handleDeleteWorld}
                            onCreateSimulation={handleCreateSimulation}
                        />
                    ))}
                </div>
            ) : (
                <div className="world-list">
                    {worlds.map((world) => (
                        <WorldListTile
                            key={world.id}
                            world={world}
                            onEdit={handleEditWorld}
                            onDelete={handleDeleteWorld}
                            onCreateSimulation={handleCreateSimulation}
                        />
                    ))}
                </div>
            )}

            {!loading && !error && hasMore ? (
                <div className="load-more-row">
                    <button
                        className="load-more-button"
                        disabled={loadingMore}
                        onClick={() => loadWorlds(offset, true)}
                    >
                        {loadingMore ? t("worlds.loadingMore") : t("worlds.loadMore")}
                    </button>
                </div>
            ) : null}

            {createModalOpen ? (
                <WorldCreateModal
                    onClose={() => setCreateModalOpen(false)}
                    onSaved={handleWorldSaved}
                />
            ) : null}

            {editingWorld ? (
                <WorldCreateModal
                    mode="edit"
                    initialWorld={editingWorld}
                    onClose={() => setEditingWorld(null)}
                    onSaved={handleWorldSaved}
                />
            ) : null}
        </section>
    );
}
