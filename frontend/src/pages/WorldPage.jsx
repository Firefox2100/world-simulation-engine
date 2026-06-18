import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";

import { fetchWorlds } from "@/api/worlds";
import { WorldCard } from "@/components/WorldCard";
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

    if (loading) {
        return <p className="status-text">{t("worlds.loading")}</p>;
    }

    if (error) {
        return <p className="status-text error-text">{t("worlds.error", { error })}</p>;
    }

    return (
        <section>
            <div className="page-heading">
                <h1>{t("worlds.title")}</h1>
                <p>{t("worlds.subtitle")}</p>
            </div>

            {worlds.length === 0 ? (
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

            <div className="load-more-row">
                <button
                    className="load-more-button"
                    disabled={loadingMore}
                    onClick={() => loadWorlds(offset, true)}
                >
                    {loadingMore ? t("worlds.loadingMore") : t("worlds.loadMore")}
                </button>
            </div>
        </section>
    );
}
