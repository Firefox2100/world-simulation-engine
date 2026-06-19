import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";

import { fetchWorlds } from "@/api/worlds";
import { WorldCard } from "@/components/WorldCard";
import { WorldCreateModal } from "@/components/WorldCreateModal";
import { WorldListTile } from "@/components/WorldListTile";
import { useMediaQuery } from "@/shared/useMediaQuery";

export function WorldPage() {
    const { t } = useTranslation();
    const isDesktop = useMediaQuery("(min-width: 768px)");

    const [worlds, setWorlds] = useState([]);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState(null);
    const [createModalOpen, setCreateModalOpen] = useState(false);

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

    async function handleWorldCreated() {
        setCreateModalOpen(false);
        await loadWorlds(0, false);
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

            {loading ? (
                <p className="status-text">{t("worlds.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("worlds.error", { error })}</p>
            ) : worlds.length === 0 ? (
                <p className="status-text">{t("worlds.empty")}</p>
            ) : isDesktop ? (
                <div className="world-grid">
                    {worlds.map((world) => (
                        <WorldCard key={world.id} world={world} />
                    ))}
                </div>
            ) : (
                <div className="world-list">
                    {worlds.map((world) => (
                        <WorldListTile key={world.id} world={world} />
                    ))}
                </div>
            )}

            {!loading && !error ? (
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
                    onCreated={handleWorldCreated}
                />
            ) : null}
        </section>
    );
}
