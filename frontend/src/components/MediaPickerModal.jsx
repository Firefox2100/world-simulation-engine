import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchMedia, uploadMedia } from "@/api/media";
import { MediaImage } from "@/components/MediaImage";

const limit = 24;

export function MediaPickerModal({ worldId, selectedMediaId = null, onSelect, onClose }) {
    const { t } = useTranslation();
    const fileInputRef = useRef(null);
    const [media, setMedia] = useState([]);
    const [offset, setOffset] = useState(0);
    const [selectedId, setSelectedId] = useState(selectedMediaId);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState(null);

    const loadMedia = useCallback(async (nextOffset = 0, append = false) => {
        try {
            append ? setLoadingMore(true) : setLoading(true);
            setError(null);
            const data = await fetchMedia({
                worldId,
                type: "image/png",
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
    }, [worldId]);

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    useEffect(() => {
        startTransition(() => {
            loadMedia(0, false);
        });
    }, [loadMedia]);

    async function handleUpload(event) {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        try {
            setUploading(true);
            setError(null);
            const created = await uploadMedia(file, {
                type: "image/png",
                title: file.name,
                filename: file.name.replace(/\.[^.]+$/, ""),
            });
            setMedia((current) => [created, ...current]);
            setSelectedId(created.id);
        } catch (err) {
            setError(err.message);
        } finally {
            setUploading(false);
            event.target.value = "";
        }
    }

    const selected = media.find((item) => item.id === selectedId);

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal-panel media-picker-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="media-picker-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <div className="modal-header">
                    <div>
                        <h2 id="media-picker-title">{t("mediaPicker.title")}</h2>
                        <p className="media-picker-subtitle">{t("mediaPicker.subtitle")}</p>
                    </div>
                    <button
                        type="button"
                        className="icon-button"
                        aria-label={t("mediaPicker.close")}
                        onClick={onClose}
                    >
                        ×
                    </button>
                </div>

                <div className="media-picker-toolbar">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png"
                        className="visually-hidden"
                        onChange={handleUpload}
                    />
                    <button
                        type="button"
                        className="secondary-button"
                        disabled={uploading}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        {uploading ? t("mediaPicker.uploading") : t("mediaPicker.upload")}
                    </button>
                </div>

                <div className="media-picker-body">
                    {loading ? (
                        <p className="status-text">{t("mediaPicker.loading")}</p>
                    ) : error ? (
                        <p className="status-text error-text">{t("mediaPicker.error", { error })}</p>
                    ) : media.length === 0 ? (
                        <p className="status-text">{t("mediaPicker.empty")}</p>
                    ) : (
                        <div className="media-picker-grid">
                            {media.map((item) => (
                                <button
                                    key={item.id}
                                    type="button"
                                    className={`media-picker-card${selectedId === item.id ? " active" : ""}`}
                                    onClick={() => setSelectedId(item.id)}
                                >
                                    <MediaImage media={item} className="media-picker-card-image" />
                                    <span>{item.title || item.filename}</span>
                                </button>
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
                                {loadingMore ? t("mediaPicker.loadingMore") : t("mediaPicker.loadMore")}
                            </button>
                        </div>
                    ) : null}
                </div>

                <div className="modal-actions">
                    <button type="button" className="secondary-button" onClick={onClose}>
                        {t("mediaPicker.cancel")}
                    </button>
                    <button
                        type="button"
                        className="primary-button"
                        disabled={!selectedId}
                        onClick={() => onSelect(selected ?? { id: selectedId })}
                    >
                        {t("mediaPicker.select")}
                    </button>
                </div>
            </div>
        </div>
    );
}
