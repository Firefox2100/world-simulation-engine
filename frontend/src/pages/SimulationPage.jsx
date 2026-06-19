import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";

import { fetchSimulations } from "@/api/simulations";
import { useMediaQuery } from "@/shared/useMediaQuery";
import { SimulationCard } from "@/components/SimulationCard";
import { SimulationListTile } from "@/components/SimulationListTile";

export function SimulationPage() {
    const { t } = useTranslation();
    const isDesktop = useMediaQuery("(min-width: 768px)");

    const [simulations, setSimulations] = useState([]);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState(null);

    const limit = 24;

    async function loadSimulations(nextOffset = 0, append = false) {
        try {
            append ? setLoadingMore(true) : setLoading(true);
            setError(null);

            const data = await fetchSimulations({
                limit,
                offset: nextOffset,
            });

            setSimulations((current) => (append ? [...current, ...data] : data));
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
            loadSimulations(0, false);
        });
    }, []);

    if (loading) {
        return <p className="status-text">{t("home.loading")}</p>;
    }

    if (error) {
        return <p className="status-text error-text">{t("home.error", { error })}</p>;
    }

    return (
        <section>
            <div className="page-heading">
                <h1>{t("home.title")}</h1>
                <p>{t("home.subtitle")}</p>
            </div>

            {simulations.length === 0 ? (
                <p className="status-text">{t("home.empty")}</p>
            ) : isDesktop ? (
                <div className="simulation-grid">
                    {simulations.map((simulation) => (
                        <SimulationCard key={simulation.id} simulation={simulation} />
                    ))}
                </div>
            ) : (
                <div className="simulation-list">
                    {simulations.map((simulation) => (
                        <SimulationListTile key={simulation.id} simulation={simulation} />
                    ))}
                </div>
            )}

            {hasMore ? (
                <div className="load-more-row">
                    <button
                        className="load-more-button"
                        disabled={loadingMore}
                        onClick={() => loadSimulations(offset, true)}
                    >
                        {loadingMore ? t("home.loadingMore") : t("home.loadMore")}
                    </button>
                </div>
            ) : null}
        </section>
    );
}
