import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMediaUrl } from "@/api/media";

export function MediaImage({ media, className = "media-card-image" }) {
    const { t } = useTranslation();
    const [src, setSrc] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;
        let objectUrl = null;

        async function loadImage() {
            try {
                setError(null);
                setSrc(null);
                const response = await fetch(getMediaUrl(media.id));

                if (!response.ok) {
                    throw new Error(`Request failed: ${response.status}`);
                }

                const blob = await response.blob();
                objectUrl = URL.createObjectURL(blob);
                if (!cancelled) {
                    setSrc(objectUrl);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            }
        }

        loadImage();

        return () => {
            cancelled = true;
            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
            }
        };
    }, [media.id]);

    if (error) {
        return <div className={`${className} media-card-image-state`}>{t("media.imageError")}</div>;
    }

    if (!src) {
        return <div className={`${className} media-card-image-state`}>{t("media.imageLoading")}</div>;
    }

    return <img src={src} alt={media.title || media.filename} className={className} />;
}
