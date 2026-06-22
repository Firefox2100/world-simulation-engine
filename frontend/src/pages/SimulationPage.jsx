import { useEffect, useState, startTransition } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { deleteSimulation, fetchSimulations } from "@/api/simulations";
import { useMediaQuery } from "@/shared/useMediaQuery";
import { SimulationCard } from "@/components/SimulationCard";
import { SimulationListTile } from "@/components/SimulationListTile";

export function SimulationPage() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const isDesktop = useMediaQuery("(min-width: 768px)");

    const [simulations, setSimulations] = useState([]);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);

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

    async function handleDelete(simulation) {
        if (!window.confirm(t("home.confirmDelete", { name: simulation.name }))) {
            return;
        }

        try {
            setActionError(null);
            await deleteSimulation(simulation.id);
            setSimulations((current) => current.filter((item) => item.id !== simulation.id));
            setOffset((current) => Math.max(0, current - 1));
        } catch (err) {
            setActionError(err.message);
        }
    }

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

            {actionError ? (
                <p className="status-text error-text">{t("home.actionError", { error: actionError })}</p>
            ) : null}

            {simulations.length === 0 ? (
                <p className="status-text">{t("home.empty")}</p>
            ) : isDesktop ? (
                <div className="simulation-grid">
                    {simulations.map((simulation) => (
                        <SimulationCard
                            key={simulation.id}
                            simulation={simulation}
                            onOpenChat={() => navigate(`/simulations/${simulation.id}`)}
                            onDelete={() => handleDelete(simulation)}
                        />
                    ))}
                </div>
            ) : (
                <div className="simulation-list">
                    {simulations.map((simulation) => (
                        <SimulationListTile
                            key={simulation.id}
                            simulation={simulation}
                            onOpenChat={() => navigate(`/simulations/${simulation.id}`)}
                            onDelete={() => handleDelete(simulation)}
                        />
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
