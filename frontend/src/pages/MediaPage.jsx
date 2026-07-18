import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { deleteMedia, fetchMedia, mediaTypes, uploadMedia } from "@/api/media";
import { MediaImage } from "@/components/MediaImage";

const limit = 24;

export function MediaPage() {
    const { t } = useTranslation();
    const fileInputRef = useRef(null);
    const [activeType, setActiveType] = useState("image/png");
    const [media, setMedia] = useState([]);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);

    const loadMedia = useCallback(async (nextOffset = 0, append = false, type = activeType) => {
        try {
            append ? setLoadingMore(true) : setLoading(true);
            setError(null);

            const data = await fetchMedia({
                type,
                limit,
                offset: nextOffset,
            });

            setMedia((current) => (append ? [...current, ...data] : data));
            setOffset(nextOffset + data.length);
            setHasMore(data.length === limit);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, [activeType]);

    useEffect(() => {
        startTransition(() => {
            loadMedia(0, false, activeType);
        });
    }, [activeType, loadMedia]);

    async function handleUpload(event) {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        try {
            setActionError(null);
            setUploading(true);
            await uploadMedia(file, {
                type: activeType,
                title: file.name,
                filename: file.name.replace(/\.[^.]+$/, ""),
            });
            await loadMedia(0, false);
        } catch (err) {
            setActionError(err.message);
        } finally {
            setUploading(false);
            event.target.value = "";
        }
    }

    async function handleDelete(item) {
        if (!window.confirm(t("media.confirmDelete", { name: item.title || item.filename }))) {
            return;
        }

        try {
            setActionError(null);
            await deleteMedia(item.id);
            setMedia((current) => current.filter((entry) => entry.id !== item.id));
            setOffset((current) => Math.max(0, current - 1));
        } catch (err) {
            setActionError(err.message);
        }
    }

    return (
        <section>
            <div className="page-heading page-heading-with-action">
                <div>
                    <h1>{t("media.title")}</h1>
                    <p>{t("media.subtitle")}</p>
                </div>
                <div className="media-upload-actions">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png"
                        className="visually-hidden"
                        onChange={handleUpload}
                    />
                    <button
                        type="button"
                        className="primary-button"
                        disabled={uploading}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        {uploading ? t("media.uploading") : t("media.upload")}
                    </button>
                </div>
            </div>

            <div className="configuration-tabs" role="tablist" aria-label={t("media.tabsLabel")}>
                {mediaTypes.map((type) => (
                    <button
                        key={type}
                        type="button"
                        role="tab"
                        aria-selected={activeType === type}
                        className={`configuration-tab${activeType === type ? " active" : ""}`}
                        onClick={() => setActiveType(type)}
                    >
                        {t(`media.types.${type}`)}
                    </button>
                ))}
            </div>

            {actionError ? <p className="status-text error-text">{t("media.actionError", { error: actionError })}</p> : null}

            {loading ? (
                <p className="status-text">{t("media.loading")}</p>
            ) : error ? (
                <p className="status-text error-text">{t("media.error", { error })}</p>
            ) : media.length === 0 ? (
                <p className="status-text">{t("media.empty")}</p>
            ) : (
                <div className="media-grid">
                    {media.map((item) => (
                        <article key={item.id} className="media-card">
                            <MediaImage media={item} />
                            <div className="media-card-body">
                                <h2>{item.title || item.filename}</h2>
                                <p>{item.filename}</p>
                                <button
                                    type="button"
                                    className="connection-action-button danger"
                                    onClick={() => handleDelete(item)}
                                >
                                    {t("media.delete")}
                                </button>
                            </div>
                        </article>
                    ))}
                </div>
            )}

            {!loading && !error && hasMore ? (
                <div className="load-more-row">
                    <button
                        className="load-more-button"
                        disabled={loadingMore}
                        onClick={() => loadMedia(offset, true)}
                    >
                        {loadingMore ? t("media.loadingMore") : t("media.loadMore")}
                    </button>
                </div>
            ) : null}
        </section>
    );
}
