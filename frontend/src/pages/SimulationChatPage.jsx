import { useCallback, useEffect, useMemo, useRef, useState, startTransition } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
    fetchAllTalkStatus,
    fetchEmbeddingConfigs,
    fetchImageConfigs,
    fetchLlmConfigs,
    fetchSimulationEmbeddingConfigs,
    fetchSimulationImageConfigs,
    fetchSimulationImageGenerationConfig,
    fetchSimulationLlmConfigs,
    fetchSimulationTtsGenerationConfig,
    fetchSttConfigs,
    fetchTtsConfigs,
    imageChatComponents,
    imageComponents,
    setSimulationEmbeddingConfigs,
    setSimulationImageConfigs,
    setSimulationImageGenerationConfig,
    setSimulationLlmConfigs,
    setSimulationTtsConfig,
    setSimulationTtsGenerationConfig,
    simulatorComponents,
} from "@/api/configurations";
import {
    fetchBlockGeneratedImages,
    fetchCharacterInventory,
    fetchCharacterEmotion,
    fetchCharacterLocation,
    fetchCharacterTtsConfig,
    fetchSimulation,
    fetchSimulationBackgroundCharacters,
    fetchSimulationCharacters,
    fetchSimulationContainers,
    fetchSimulationEquipment,
    fetchSimulationEvents,
    fetchSimulationItems,
    fetchSimulationIntents,
    fetchSimulationLandmarks,
    fetchSimulationLocations,
    fetchSimulationMemories,
    fetchSimulationRecords,
    fetchSimulationAuditEvents,
    fetchSimulationStacks,
    fetchSimulations,
    fetchSimulationTtsBackendConfig,
    fetchTurnGeneratedImages,
    fetchTurnPresentation,
    generateBlockVoice,
    generateCharacterCoverImage,
    generateCharacterPortraitImage,
    generateItemCoverImage,
    generateLocationCoverImage,
    generateSceneImage,
    getSimulationRunUrl,
    getSimulationBackgroundCharacterImageUrl,
    getSimulationCharacterImageUrl,
    getSimulationContainerImageUrl,
    getSimulationEquipmentImageUrl,
    getSimulationItemImageUrl,
    getSimulationLandmarkImageUrl,
    getSimulationLocationImageUrl,
    getSimulationCoverUrl,
    sendSimulationInput,
    setCharacterTtsConfig,
} from "@/api/simulations";
import { deleteCoverImage, getMediaUrl, setCoverImage } from "@/api/media";
import { ensureAudioUnlockListeners, playAudioUrlSequence } from "@/utils/audioPlayback";
import { waitForBlocksVoiced } from "@/utils/turnVoicePolling";
import { MediaPickerModal } from "@/components/MediaPickerModal";
import { PromptAssignmentEditor } from "@/components/PromptAssignmentEditor";
import { VoiceRecorderButton } from "@/components/VoiceRecorderButton";
import { useMediaQuery } from "@/shared/useMediaQuery";
import placeholderImage from "@/assets/placeholder/world.svg";
import characterPlaceholderImage from "@/assets/placeholder/character.svg";
import locationPlaceholderImage from "@/assets/placeholder/location.svg";
import entityPlaceholderImage from "@/assets/placeholder/banner.svg";

const simulationLimit = 24;
const recordLimit = 50;
const emptyList = [];
const emptyObject = {};
const detailSections = [
    "basic",
    "configs",
    "imageGeneration",
    "ttsGeneration",
    "prompts",
    "locations",
    "landmarks",
    "characters",
    "background",
    "items",
    "stacks",
    "equipment",
    "containers",
    "events",
    "memories",
    "intents",
    "observability",
];
const entityDetailSections = [
    "landmarks",
    "background",
    "items",
    "stacks",
    "equipment",
    "containers",
    "events",
    "memories",
    "intents",
];

function useOptionalImage(imageUrl, fallbackSrc) {
    const [loadedImage, setLoadedImage] = useState({ sourceUrl: null, objectUrl: null });

    useEffect(() => {
        if (!imageUrl) {
            return undefined;
        }

        const controller = new AbortController();
        let objectUrl = null;

        async function loadImage() {
            try {
                const response = await fetch(imageUrl, { signal: controller.signal });

                if (!response.ok) {
                    return;
                }

                const blob = await response.blob();
                objectUrl = URL.createObjectURL(blob);
                setLoadedImage({ sourceUrl: imageUrl, objectUrl });
            } catch (err) {
                if (err.name !== "AbortError") {
                    setLoadedImage((current) =>
                        current.sourceUrl === imageUrl ? { sourceUrl: null, objectUrl: null } : current,
                    );
                }
            }
        }

        loadImage();

        return () => {
            controller.abort();

            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
            }
        };
    }, [imageUrl]);

    const isLoaded = loadedImage.sourceUrl === imageUrl && Boolean(loadedImage.objectUrl);
    return { src: isLoaded ? loadedImage.objectUrl : fallbackSrc, isLoaded };
}

function ImageLightbox({ imageUrl, alt = "", onClose }) {
    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    return (
        <div className="image-lightbox-backdrop" role="presentation" onMouseDown={onClose}>
            <img
                src={imageUrl}
                alt={alt}
                className="image-lightbox-image"
                onMouseDown={(event) => event.stopPropagation()}
            />
        </div>
    );
}

function EnlargeableImage({ src, isLoaded, alt = "", className }) {
    const [lightboxOpen, setLightboxOpen] = useState(false);

    return (
        <>
            <img
                src={src}
                alt={alt}
                className={`${className}${isLoaded ? " enlargeable-image" : ""}`}
                onClick={isLoaded ? () => setLightboxOpen(true) : undefined}
            />
            {lightboxOpen ? (
                <ImageLightbox imageUrl={src} alt={alt} onClose={() => setLightboxOpen(false)} />
            ) : null}
        </>
    );
}

function fetchImagesForSource(sourceType, sourceId) {
    return sourceType === "turn"
        ? fetchTurnGeneratedImages(sourceId)
        : fetchBlockGeneratedImages(sourceId);
}

// Loads the images already generated for one turn/block, and lets a sibling generate action
// append a freshly generated one immediately, without waiting on a refetch.
function useBubbleImages(sourceType, sourceId) {
    const [images, setImages] = useState([]);
    const [activeIndex, setActiveIndex] = useState(0);

    useEffect(() => {
        if (!sourceId) {
            return undefined;
        }

        let cancelled = false;

        fetchImagesForSource(sourceType, sourceId)
            .then((fetched) => {
                if (!cancelled) {
                    setImages(fetched);
                    setActiveIndex(Math.max(fetched.length - 1, 0));
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setImages([]);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [sourceType, sourceId]);

    function addImage(media) {
        setImages((current) => {
            const next = [...current, media];
            setActiveIndex(next.length - 1);
            return next;
        });
    }

    return { images, activeIndex, setActiveIndex, addImage };
}

function BubbleImageGallery({ images, activeIndex, onIndexChange }) {
    const { t } = useTranslation();
    const [lightboxOpen, setLightboxOpen] = useState(false);
    const activeImage = images[activeIndex];

    if (!activeImage) {
        return null;
    }

    const imageUrl = getMediaUrl(activeImage.id);

    function showRelative(offset) {
        onIndexChange((activeIndex + offset + images.length) % images.length);
    }

    return (
        <div className="bubble-image">
            <img
                src={imageUrl}
                alt=""
                className="bubble-image-media"
                onClick={() => setLightboxOpen(true)}
            />
            {images.length > 1 ? (
                <>
                    <button
                        type="button"
                        className="bubble-image-nav bubble-image-nav-prev"
                        onClick={(event) => {
                            event.stopPropagation();
                            showRelative(-1);
                        }}
                        aria-label={t("simulationChat.previousImage")}
                    >
                        ‹
                    </button>
                    <button
                        type="button"
                        className="bubble-image-nav bubble-image-nav-next"
                        onClick={(event) => {
                            event.stopPropagation();
                            showRelative(1);
                        }}
                        aria-label={t("simulationChat.nextImage")}
                    >
                        ›
                    </button>
                    <span className="bubble-image-counter">{activeIndex + 1}/{images.length}</span>
                </>
            ) : null}
            {lightboxOpen ? (
                <ImageLightbox imageUrl={imageUrl} onClose={() => setLightboxOpen(false)} />
            ) : null}
        </div>
    );
}

function sortRecords(records) {
    return [...records].sort((a, b) => a.turn_number - b.turn_number || String(a.id).localeCompare(String(b.id)));
}

function isUserRecord(record) {
    return record.type === "user_input";
}

function narrationBlocksFromValue(value) {
    if (Array.isArray(value?.blocks)) {
        return value.blocks;
    }

    if (Array.isArray(value)) {
        return value;
    }

    return null;
}

function narrationTextFromBlocks(blocks) {
    return (blocks ?? [])
        .map((block) => {
            if (block.type === "speech") {
                const speaker = block.character_name || block.character_id || "";
                return speaker ? `${speaker}: "${block.text}"` : block.text;
            }

            return block.text;
        })
        .filter(Boolean)
        .join("\n\n");
}

function validateInputMarkup(value) {
    let mode = null;
    let emphasisOpen = false;
    let buffer = "";

    for (let index = 0; index < value.length; index += 1) {
        const char = value[index];
        const nextTwo = value.slice(index, index + 2);

        if (char === "\\") {
            if (mode) {
                buffer += char;
            }
            if (index + 1 < value.length) {
                if (mode) {
                    buffer += value[index + 1];
                }
                index += 1;
            }
            continue;
        }

        if (nextTwo === "**") {
            emphasisOpen = !emphasisOpen;
            if (mode) {
                buffer += nextTwo;
            }
            index += 1;
            continue;
        }

        if (char === '"') {
            if (mode === "internal") {
                return "Internal dialog cannot contain speech quotes.";
            }
            if (mode === "speech") {
                if (buffer.trim().length === 0) {
                    return "Speech quotes cannot be empty.";
                }
                mode = null;
                buffer = "";
            } else {
                mode = "speech";
                buffer = "";
            }
            continue;
        }

        if (char === "*") {
            if (mode === "speech") {
                return "Speech cannot contain internal-dialog markers.";
            }
            if (mode === "internal") {
                if (buffer.trim().length === 0) {
                    return "Internal dialog markers cannot be empty.";
                }
                mode = null;
                buffer = "";
            } else {
                mode = "internal";
                buffer = "";
            }
            continue;
        }

        if (mode) {
            buffer += char;
        }
    }

    if (mode === "speech") {
        return 'Speech quote is not closed with ".';
    }
    if (mode === "internal") {
        return "Internal dialog is not closed with *.";
    }
    if (emphasisOpen) {
        return "Emphasis is not closed with **.";
    }

    return null;
}

function formatUserText(text) {
    const parts = [];
    let mode = null;
    let buffer = "";

    function pushBuffer(kind) {
        if (!buffer) {
            return;
        }
        parts.push({ kind, text: buffer });
        buffer = "";
    }

    for (let index = 0; index < text.length; index += 1) {
        const char = text[index];
        const nextTwo = text.slice(index, index + 2);

        if (nextTwo === "**" && mode !== "speech" && mode !== "internal") {
            pushBuffer("text");
            mode = mode === "emphasis" ? null : "emphasis";
            index += 1;
            continue;
        }

        if (char === '"' && mode !== "internal") {
            pushBuffer(mode || "text");
            mode = mode === "speech" ? null : "speech";
            continue;
        }

        if (char === "*" && mode !== "speech" && text[index + 1] !== "*") {
            pushBuffer(mode || "text");
            mode = mode === "internal" ? null : "internal";
            continue;
        }

        buffer += char;
    }

    pushBuffer(mode || "text");
    return parts;
}

function FormattedUserText({ text }) {
    return (
        <p>
            {formatUserText(text).map((part, index) => {
                if (part.kind === "speech") {
                    return <q key={`${part.kind}-${index}`}>{part.text}</q>;
                }
                if (part.kind === "internal") {
                    return <em key={`${part.kind}-${index}`}>{part.text}</em>;
                }
                if (part.kind === "emphasis") {
                    return <strong key={`${part.kind}-${index}`}>{part.text}</strong>;
                }
                return <span key={`${part.kind}-${index}`}>{part.text}</span>;
            })}
        </p>
    );
}

function stageFromStateChunk(chunk) {
    if (chunk?.memory_summary_proposal) {
        return "memory_summarizer";
    }

    if (chunk?.committed_turn || chunk?.state_commit_proposal) {
        return "state_committer";
    }

    if (chunk?.narration) {
        return "narrator";
    }

    if (chunk?.character_action_coordination || chunk?.user_action_coordination) {
        return "scene_coordinator";
    }

    if ((chunk?.character_action_validations ?? []).length > 0 || chunk?.user_action_validation) {
        return "action_validator";
    }

    if ((chunk?.character_actions ?? []).length > 0) {
        return "character_simulator";
    }

    if (chunk?.input_interpretation) {
        return "input_interpreter";
    }

    return null;
}

function SimulationAvatar({ simulation, className = "chat-avatar", refreshKey = 0 }) {
    const { src, isLoaded } = useOptionalImage(
        simulation?.id
            ? `${getSimulationCoverUrl(simulation.id)}${refreshKey ? `?v=${refreshKey}` : ""}`
            : null,
        placeholderImage,
    );

    return (
        <EnlargeableImage
            src={src}
            isLoaded={isLoaded}
            alt={simulation?.name ?? ""}
            className={className}
        />
    );
}

function SimulationConversationItem({ simulation, preview }) {
    const { t } = useTranslation();

    return (
        <NavLink
            to={`/simulations/${simulation.id}`}
            className={({ isActive }) => `conversation-item${isActive ? " active" : ""}`}
        >
            <SimulationAvatar simulation={simulation} className="conversation-avatar" />
            <div className="conversation-summary">
                <span className="conversation-title">{simulation.name}</span>
                <span className="conversation-preview">
                    {preview || t("simulationChat.noPreview")}
                </span>
            </div>
        </NavLink>
    );
}

function CharacterAvatar({ simulationId, character, label }) {
    const { src, isLoaded } = useOptionalImage(
        simulationId && character?.id
            ? getSimulationCharacterImageUrl({ simulationId, characterId: character.id })
            : null,
        characterPlaceholderImage,
    );

    return (
        <EnlargeableImage
            src={src}
            isLoaded={isLoaded}
            alt={label ?? ""}
            className="chat-avatar"
        />
    );
}

function SegmentVoiceButton({ block, onVoiceGenerated }) {
    const { t } = useTranslation();
    const audioRef = useRef(null);
    const justGeneratedRef = useRef(false);
    const [voiceMediaId, setVoiceMediaId] = useState(block.voice_media_id ?? null);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState(null);

    async function handleClick() {
        if (voiceMediaId) {
            setError(null);
            audioRef.current?.play();
            return;
        }

        try {
            setGenerating(true);
            setError(null);
            const media = await generateBlockVoice(block.id);
            justGeneratedRef.current = true;
            setVoiceMediaId(media.id);
            onVoiceGenerated?.(block.id, media.id);
        } catch (err) {
            setError(err.message);
        } finally {
            setGenerating(false);
        }
    }

    useEffect(() => {
        // Only auto-play right after this component generated the clip itself, never on mount
        // (which would otherwise autoplay every already-generated segment when history loads).
        if (justGeneratedRef.current && audioRef.current) {
            justGeneratedRef.current = false;
            audioRef.current.play().catch(() => {});
        }
    }, [voiceMediaId]);

    const label = error
        ? error
        : voiceMediaId
          ? t("simulationChat.playVoice")
          : t("simulationChat.generateVoice");

    return (
        <>
            <button
                type="button"
                className={`segment-voice-button${voiceMediaId ? " generated" : ""}${error ? " error" : ""}`}
                onClick={handleClick}
                disabled={generating}
                title={label}
                aria-label={label}
            >
                {generating ? "…" : voiceMediaId ? "▶" : "🔊"}
            </button>
            {voiceMediaId ? (
                <audio ref={audioRef} src={getMediaUrl(voiceMediaId)} preload="none" />
            ) : null}
        </>
    );
}

function useImageGenerationAction(onGenerate) {
    const [state, setState] = useState("idle");
    const [error, setError] = useState(null);
    const resetTimerRef = useRef(null);

    useEffect(() => () => {
        if (resetTimerRef.current) {
            clearTimeout(resetTimerRef.current);
        }
    }, []);

    async function trigger() {
        if (state === "generating") {
            return;
        }

        setState("generating");
        setError(null);

        try {
            await onGenerate();
            setState("success");
        } catch (err) {
            setError(err.message);
            setState("error");
        } finally {
            resetTimerRef.current = setTimeout(() => setState("idle"), 3000);
        }
    }

    return { state, error, trigger };
}

function SegmentImageButton({ label, onGenerate }) {
    const { state, error, trigger } = useImageGenerationAction(onGenerate);
    const title = state === "error" ? error : label;

    return (
        <button
            type="button"
            className={`segment-image-button${state === "success" ? " generated" : ""}${state === "error" ? " error" : ""}`}
            onClick={trigger}
            disabled={state === "generating"}
            title={title}
            aria-label={title}
        >
            {state === "generating" ? "…" : state === "success" ? "✓" : state === "error" ? "!" : "🖼"}
        </button>
    );
}

function GenerateCoverImageButton({ label, onGenerate }) {
    const { t } = useTranslation();
    const { state, error, trigger } = useImageGenerationAction(onGenerate);

    return (
        <div className="cover-image-generate-control">
            <button
                type="button"
                className="secondary-button"
                onClick={trigger}
                disabled={state === "generating"}
            >
                {state === "generating" ? t("simulationDetails.generatingCoverImage") : label}
            </button>
            {state === "success" ? (
                <span className="status-text">{t("simulationDetails.coverImageGenerated")}</span>
            ) : null}
            {state === "error" ? (
                <span className="status-text error-text">
                    {t("simulationDetails.coverImageError", { error })}
                </span>
            ) : null}
        </div>
    );
}

function CoverImageActions({ error, onChoose, onRemove }) {
    const { t } = useTranslation();

    return (
        <div className="cover-image-generate-control">
            <button type="button" className="secondary-button" onClick={onChoose}>
                {t("simulationDetails.chooseCoverImage")}
            </button>
            <button type="button" className="secondary-button" onClick={onRemove}>
                {t("simulationDetails.removeCoverImage")}
            </button>
            {error ? (
                <span className="status-text error-text">
                    {t("simulationDetails.coverImageActionError", { error })}
                </span>
            ) : null}
        </div>
    );
}

// Mirrors the backend InputInterpreter's OOC marker syntax: a user action's raw text can carry
// an embedded `[/OOC: ...]` command, which is a player instruction to the simulator, not an
// in-character action - it must never be treated as something to depict in a generated image.
const OOC_MARKER_PATTERN = /\[\/OOC:[\s\S]*?\]/g;

function hasInWorldActionText(text) {
    return Boolean(text && text.replace(OOC_MARKER_PATTERN, "").trim().length > 0);
}

async function generateSceneImageForCharacter({ simulationId, userCharacterId, turnId, blockId = null, t }) {
    const location = await fetchCharacterLocation(userCharacterId);
    if (!location?.id) {
        throw new Error(t("simulationChat.noCurrentLocation"));
    }

    return generateSceneImage({ simulationId, locationId: location.id, turnId, blockId });
}

function SpeechBlockMessage({ block, simulationId, charactersById, allowVoice, turnId, canGeneratePortrait }) {
    const { t } = useTranslation();
    const speakerId = block.speaker_id ?? block.character_id;
    const character = charactersById[String(speakerId)];
    const authorName = block.speaker_name || block.character_name || character?.name || speakerId;
    const { images, activeIndex, setActiveIndex, addImage } = useBubbleImages("block", block.id ?? null);

    const voiceButton = allowVoice && block.id ? <SegmentVoiceButton block={block} /> : null;
    const imageButton = canGeneratePortrait && turnId && speakerId
        ? (
            <SegmentImageButton
                label={t("simulationChat.generatePortraitImage")}
                onGenerate={async () => {
                    const media = await generateCharacterPortraitImage({
                        simulationId,
                        characterId: speakerId,
                        turnId,
                        blockId: block.id ?? null,
                    });
                    addImage(media);
                    return media;
                }}
            />
        )
        : null;
    const actions = voiceButton || imageButton
        ? <span className="chat-message-actions">{voiceButton}{imageButton}</span>
        : null;

    return (
        <article className="chat-message character">
            <CharacterAvatar
                simulationId={simulationId}
                character={character}
                label={authorName}
            />
            <div className="chat-message-content">
                <div className="chat-message-author">{authorName}</div>
                <div className="chat-bubble character-speech">
                    <p>{block.text}</p>
                    {images.length > 0 ? (
                        <BubbleImageGallery images={images} activeIndex={activeIndex} onIndexChange={setActiveIndex} />
                    ) : null}
                </div>
            </div>
            {actions}
        </article>
    );
}

function UserActionBlockMessage({ block, simulationId, userCharacter, turnId, userCharacterId, canGenerateScene }) {
    const { t } = useTranslation();
    const authorName = userCharacter?.name ?? block.speaker_name ?? block.speaker_id ?? "";
    const { images, activeIndex, setActiveIndex, addImage } = useBubbleImages("block", block.id ?? null);

    const imageButton = canGenerateScene && turnId && userCharacterId
        && hasInWorldActionText(block.text)
        ? (
            <SegmentImageButton
                label={t("simulationChat.generateSceneImage")}
                onGenerate={async () => {
                    const media = await generateSceneImageForCharacter({
                        simulationId,
                        userCharacterId,
                        turnId,
                        blockId: block.id ?? null,
                        t,
                    });
                    addImage(media);
                    return media;
                }}
            />
        )
        : null;

    return (
        <article className="chat-message user presentation-action">
            <CharacterAvatar
                simulationId={simulationId}
                character={userCharacter}
                label={authorName}
            />
            <div className="chat-message-content">
                <div className="chat-message-author">{authorName}</div>
                <div className="chat-bubble">
                    <FormattedUserText text={block.text ?? ""} />
                    {images.length > 0 ? (
                        <BubbleImageGallery images={images} activeIndex={activeIndex} onIndexChange={setActiveIndex} />
                    ) : null}
                </div>
            </div>
            {imageButton ? <span className="chat-message-actions">{imageButton}</span> : null}
        </article>
    );
}

function NarrationCardBlockMessage({ block, allowVoice, turnId, userCharacterId, canGenerateScene, simulationId }) {
    const { t } = useTranslation();
    const isNarration = block.type === "narration";
    const { images, activeIndex, setActiveIndex, addImage } = useBubbleImages(
        "block",
        isNarration ? (block.id ?? null) : null,
    );

    const blockClass = block.type === "thought"
        ? "thought-block"
        : block.type === "system_notice"
          ? "system-notice-block"
          : block.type === "media"
            ? "media-block"
            : block.type === "action"
              ? "action-block"
              : "narration-block";
    const voiceButton = allowVoice && isNarration && block.id ? <SegmentVoiceButton block={block} /> : null;
    const imageButton = canGenerateScene && turnId && userCharacterId && isNarration
        ? (
            <SegmentImageButton
                label={t("simulationChat.generateSceneImage")}
                onGenerate={async () => {
                    const media = await generateSceneImageForCharacter({
                        simulationId,
                        userCharacterId,
                        turnId,
                        blockId: block.id ?? null,
                        t,
                    });
                    addImage(media);
                    return media;
                }}
            />
        )
        : null;
    const actions = voiceButton || imageButton
        ? <span className="chat-message-actions">{voiceButton}{imageButton}</span>
        : null;

    return (
        <article className={`chat-message ${blockClass} presentation-${block.completion ?? "complete"}`}>
            <div className="chat-narration-card">
                {block.type === "media" ? (
                    <p>Media: {block.media_id}</p>
                ) : block.type === "thought" ? (
                    <p><em>{block.text}</em></p>
                ) : (
                    <p>{block.text}</p>
                )}
                {images.length > 0 ? (
                    <BubbleImageGallery images={images} activeIndex={activeIndex} onIndexChange={setActiveIndex} />
                ) : null}
            </div>
            {actions}
        </article>
    );
}

function NarrationBlocks({
    blocks,
    simulationId,
    charactersById,
    userCharacter = null,
    userRecord = false,
    allowVoice = false,
    turnId = null,
    userCharacterId = null,
    canGenerateScene = false,
    canGeneratePortrait = false,
}) {
    return (
        <>
            {blocks.map((block, index) => {
                if (block.type === "speech") {
                    const speakerId = block.speaker_id ?? block.character_id;
                    return (
                        <SpeechBlockMessage
                            key={block.id ?? `${block.type}-${speakerId}-${index}`}
                            block={block}
                            simulationId={simulationId}
                            charactersById={charactersById}
                            allowVoice={allowVoice}
                            turnId={turnId}
                            canGeneratePortrait={canGeneratePortrait}
                        />
                    );
                }

                if (block.type === "action" && userRecord) {
                    return (
                        <UserActionBlockMessage
                            key={block.id ?? `${block.type}-${index}`}
                            block={block}
                            simulationId={simulationId}
                            userCharacter={userCharacter}
                            turnId={turnId}
                            userCharacterId={userCharacterId}
                            canGenerateScene={canGenerateScene}
                        />
                    );
                }

                return (
                    <NarrationCardBlockMessage
                        key={block.id ?? `${block.type}-${index}`}
                        block={block}
                        allowVoice={allowVoice}
                        turnId={turnId}
                        userCharacterId={userCharacterId}
                        canGenerateScene={canGenerateScene}
                        simulationId={simulationId}
                    />
                );
            })}
        </>
    );
}

function ChatRecord({
    record,
    simulation,
    charactersById,
    userCharacter,
    canGenerateScene = false,
    canGeneratePortrait = false,
}) {
    const { t } = useTranslation();
    const userRecord = isUserRecord(record);
    const authorName = userRecord ? (userCharacter?.name ?? t("simulationChat.userCharacterFallback")) : simulation?.name;
    const blocks = narrationBlocksFromValue(record.narration_blocks);
    const hasBlocks = blocks?.length > 0;
    const { images, activeIndex, setActiveIndex, addImage } = useBubbleImages("turn", hasBlocks ? null : record.id);

    if (hasBlocks) {
        return (
            <NarrationBlocks
                blocks={blocks}
                simulationId={simulation?.id}
                charactersById={charactersById}
                userCharacter={userCharacter}
                userRecord={userRecord}
                allowVoice
                turnId={record.id}
                userCharacterId={userCharacter?.id ?? null}
                canGenerateScene={canGenerateScene}
                canGeneratePortrait={canGeneratePortrait}
            />
        );
    }

    const imageButton = canGenerateScene && userCharacter?.id && record.id
        && (!userRecord || hasInWorldActionText(record.narration))
        ? (
            <SegmentImageButton
                label={t("simulationChat.generateSceneImage")}
                onGenerate={async () => {
                    const media = await generateSceneImageForCharacter({
                        simulationId: simulation?.id,
                        userCharacterId: userCharacter.id,
                        turnId: record.id,
                        t,
                    });
                    addImage(media);
                    return media;
                }}
            />
        )
        : null;

    return (
        <article className={`chat-message${userRecord ? " user" : " simulation"}`}>
            {userRecord ? (
                <CharacterAvatar
                    simulationId={simulation?.id}
                    character={userCharacter}
                    label={authorName}
                />
            ) : (
                <SimulationAvatar simulation={simulation} />
            )}
            <div className="chat-message-content">
                <div className="chat-message-author">{authorName}</div>
                <div className="chat-bubble">
                    {userRecord ? <FormattedUserText text={record.narration} /> : <p>{record.narration}</p>}
                    {images.length > 0 ? (
                        <BubbleImageGallery images={images} activeIndex={activeIndex} onIndexChange={setActiveIndex} />
                    ) : null}
                </div>
            </div>
            {imageButton ? <span className="chat-message-actions">{imageButton}</span> : null}
        </article>
    );
}

function TypingIndicator() {
    return (
        <span className="typing-state">
            <span className="typing-indicator" aria-label="Typing">
                <span />
                <span />
                <span />
            </span>
        </span>
    );
}

function StreamingChatRecord({ message, blocks = [], error, active, stageName, simulation, charactersById }) {
    const { t } = useTranslation();
    const hasBlocks = blocks.length > 0;
    const hasMessage = message.length > 0 || hasBlocks;
    const stageLabel = stageName
        ? t(`worldCreate.newEditor.components.${stageName}`, { defaultValue: stageName })
        : null;

    if (hasBlocks) {
        return (
            <>
                <NarrationBlocks
                    blocks={blocks}
                    simulationId={simulation?.id}
                    charactersById={charactersById}
                />
                {active && stageLabel ? (
                    <div className="chat-stage-line streaming-stage-line">{stageLabel}</div>
                ) : null}
                {!active && error ? <p className="chat-stream-error">{error}</p> : null}
            </>
        );
    }

    return (
        <article className="chat-message simulation">
            <SimulationAvatar simulation={simulation} />
            <div className="chat-message-content">
                <div className="chat-message-author">
                    {simulation?.name ?? t("simulationChat.selectedFallback")}
                </div>
                <div className="chat-bubble">
                    {hasMessage ? <p>{message}</p> : active ? <TypingIndicator /> : null}
                    {!active && error ? <p className="chat-stream-error">{error}</p> : null}
                </div>
                {active && stageLabel ? (
                    <div className="chat-stage-line">{stageLabel}</div>
                ) : null}
            </div>
        </article>
    );
}

function ActionSuggestions({ suggestions, open, onToggle, onSelect, disabled }) {
    const { t } = useTranslation();

    if (!suggestions.length) {
        return null;
    }

    return (
        <div className="chat-suggestions">
            <button
                type="button"
                className="chat-suggestions-toggle"
                onClick={onToggle}
                aria-expanded={open}
            >
                <span>{t("simulationChat.suggestions.title")}</span>
                <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    focusable="false"
                    className={`chat-suggestions-chevron${open ? " open" : ""}`}
                >
                    <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </button>
            {open ? (
                <ul className="chat-suggestions-list">
                    {suggestions.map((suggestion, index) => (
                        <li key={`${index}-${suggestion}`}>
                            <button
                                type="button"
                                className="chat-suggestion-chip"
                                onClick={() => onSelect(suggestion)}
                                disabled={disabled}
                                title={t("simulationChat.suggestions.useSuggestion")}
                            >
                                {suggestion}
                            </button>
                        </li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function CharacterImage({ simulationId, character, className = "simulation-details-cover", refreshKey = 0 }) {
    const { src, isLoaded } = useOptionalImage(
        simulationId && character?.id
            ? `${getSimulationCharacterImageUrl({ simulationId, characterId: character.id })}${refreshKey ? `?v=${refreshKey}` : ""}`
            : null,
        characterPlaceholderImage,
    );

    return (
        <EnlargeableImage
            src={src}
            isLoaded={isLoaded}
            alt={character?.name ?? ""}
            className={className}
        />
    );
}

function LocationImage({ simulationId, location, className = "simulation-details-cover", refreshKey = 0 }) {
    const { src, isLoaded } = useOptionalImage(
        simulationId && location?.id
            ? `${getSimulationLocationImageUrl({ simulationId, locationId: location.id })}${refreshKey ? `?v=${refreshKey}` : ""}`
            : null,
        locationPlaceholderImage,
    );

    return (
        <EnlargeableImage
            src={src}
            isLoaded={isLoaded}
            alt={location ? formatLocation(location, "") : ""}
            className={className}
        />
    );
}

function EntityImage({ imageUrl, fallbackSrc = entityPlaceholderImage, alt = "", className = "simulation-details-cover" }) {
    const { src, isLoaded } = useOptionalImage(
        imageUrl,
        fallbackSrc,
    );

    return (
        <EnlargeableImage
            src={src}
            isLoaded={isLoaded}
            alt={alt}
            className={className}
        />
    );
}

function formatBoolean(value, t) {
    return value ? t("simulationDetails.boolean.yes") : t("simulationDetails.boolean.no");
}

function formatLocation(location, emptyValue) {
    if (!location) {
        return emptyValue;
    }

    return location.name || emptyValue;
}

function configLabel(config, fallback) {
    return config?.name || config?.model || config?.id || fallback;
}

function emptyComponentConfigMap(components) {
    return Object.fromEntries(components.map((component) => [component, ""]));
}

function componentConfigMapFromAssignments(components, assignments) {
    return assignments.reduce((result, assignment) => {
        result[assignment.component] = assignment.config?.id ?? "";
        return result;
    }, emptyComponentConfigMap(components));
}

function componentAssignmentsFromMap(components, configsByComponent) {
    return components.map((component) => ({
        component,
        config_id: configsByComponent[component] || null,
    }));
}

function DetailLink({ children, onClick }) {
    return (
        <button type="button" className="simulation-details-link" onClick={onClick}>
            {children}
        </button>
    );
}

function formatObjectListValue(value, emptyValue) {
    if (Array.isArray(value)) {
        return value.length > 0 ? value.join(", ") : emptyValue;
    }

    if (value && typeof value === "object") {
        const nestedEntries = Object.entries(value);
        return nestedEntries.length > 0
            ? nestedEntries.map(([nestedKey, nestedValue]) => `${nestedKey}: ${nestedValue}`).join(", ")
            : emptyValue;
    }

    return value ?? emptyValue;
}

function ObjectList({ title, values, emptyValue }) {
    const entries = Object.entries(values ?? {});

    if (entries.length === 0) {
        return null;
    }

    return (
        <section className="simulation-details-object-list">
            <h4>{title}</h4>
            <div className="simulation-details-chip-list">
                {entries.map(([key, value]) => (
                    <div key={key} className="simulation-details-chip">
                        <span>{key}</span>
                        <strong>{formatObjectListValue(value, emptyValue)}</strong>
                    </div>
                ))}
            </div>
        </section>
    );
}

function truncateText(text, maxLength = 60) {
    if (!text) {
        return text;
    }

    return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}…` : text;
}

// Entities like Turn and Memory have no short "name" field, only long free text
// (narration/content/summary). Falling back to that raw text as a title would blow up the
// heading and overflow the subtab pill, so it's truncated into a short preview instead.
function entityTitle(entity) {
    return (
        entity?.name ||
        entity?.item?.name ||
        truncateText(entity?.narration) ||
        truncateText(entity?.summary) ||
        truncateText(entity?.content) ||
        entity?.id ||
        ""
    );
}

// Whichever field describeEntity draws its text from - entityRows excludes it so the
// same text isn't shown twice (once as the description, once as a generic field row).
// Turn records are normalized with a `narration` field (the properly assembled, per-viewer
// text) alongside the raw `content` they were built from; narration wins here so `content`
// stays available for the permanent exclusion below instead of leaking through as a row.
function describeEntityField(entity) {
    if (entity?.description) {
        return "description";
    }
    if (entity?.item?.description) {
        return "item";
    }
    if (entity?.narration) {
        return "narration";
    }
    if (entity?.summary) {
        return "summary";
    }
    if (entity?.content) {
        return "content";
    }
    return null;
}

function describeEntity(entity) {
    const field = describeEntityField(entity);
    return (field ? entity[field]?.description ?? entity[field] : "") || "";
}

// content/turn_number/rendering_id are Turn-specific synthetic fields (see normalizeTurn in
// api/simulations.js) that always duplicate narration/sequence once those are shown, so they're
// dropped from the generic grid outright rather than case-by-case per entity.
const alwaysHiddenEntityFields = [
    "id",
    "attributes",
    "stats",
    "embedding",
    "content",
    "turn_number",
    "rendering_id",
];

function entityRows(entity, t) {
    const descriptionField = describeEntityField(entity);

    return Object.entries(entity ?? {})
        .filter(([key, value]) => {
            if (alwaysHiddenEntityFields.includes(key) || key === descriptionField) {
                return false;
            }
            if (value === null || value === undefined) {
                return false;
            }
            if (Array.isArray(value)) {
                return value.length > 0 && value.every((entry) => entry !== null && typeof entry !== "object");
            }
            return typeof value !== "object";
        })
        .map(([key, value]) => ({
            key,
            label: t(`simulationDetails.genericFields.${key}`, { defaultValue: key.replaceAll("_", " ") }),
            value: Array.isArray(value) ? value.join(", ") : String(value),
            refId: key.endsWith("_id") && !Array.isArray(value) ? String(value) : null,
        }));
}

// Sections whose entities are addressable from a generic reference field (owner_id, holder_id,
// location_id, ...). Characters and locations are checked first since they're the most common
// targets; order among the rest doesn't matter since ids are unique across the simulation.
const referenceLookupSections = ["background", "items", "stacks", "equipment", "containers", "landmarks"];

function resolveEntityReference(id, { characters, locations, entities }) {
    if (!id) {
        return null;
    }

    const character = characters?.find((candidate) => candidate.id === id);
    if (character) {
        return { section: "characters", label: character.name };
    }

    const location = locations?.find((candidate) => candidate.id === id);
    if (location) {
        return { section: "locations", label: formatLocation(location, id) };
    }

    for (const section of referenceLookupSections) {
        const match = (entities?.[section] ?? []).find((candidate) => candidate.id === id);
        if (match) {
            return { section, label: entityTitle(match) };
        }
    }

    return null;
}

function GenericEntityPanel({
    section,
    entity,
    emptyText,
    imageUrl,
    fallbackImage,
    coverImageAction = null,
    characters = emptyList,
    locations = emptyList,
    entities = emptyObject,
    onNavigate,
}) {
    const { t } = useTranslation();

    if (!entity) {
        return <p className="status-text">{emptyText}</p>;
    }

    return (
        <>
            <div className={`simulation-details-hero${imageUrl ? "" : " simulation-details-hero-no-image"}`}>
                {imageUrl ? (
                    <EntityImage
                        imageUrl={imageUrl}
                        fallbackSrc={fallbackImage}
                        alt={entityTitle(entity)}
                    />
                ) : null}
                <div className="simulation-details-summary">
                    <h3>{entityTitle(entity)}</h3>
                    <p>{describeEntity(entity) || t("simulationDetails.noDescription")}</p>
                    {coverImageAction}
                </div>
            </div>

            <div className="simulation-details-separator" />

            <dl className="simulation-details-grid">
                {entityRows(entity, t).map((row) => {
                    const reference = row.refId
                        ? resolveEntityReference(row.refId, { characters, locations, entities })
                        : null;

                    return (
                        <div key={`${section}-${row.label}`} className="simulation-details-row">
                            <dt>{row.label}</dt>
                            <dd>
                                {reference ? (
                                    <DetailLink onClick={() => onNavigate?.(reference.section, row.refId)}>
                                        {reference.label}
                                    </DetailLink>
                                ) : (
                                    row.value || t("simulationDetails.emptyValue")
                                )}
                            </dd>
                        </div>
                    );
                })}
            </dl>

            <ObjectList
                title={t("simulationDetails.genericFields.attributes")}
                values={entity.attributes}
                emptyValue={t("simulationDetails.emptyValue")}
            />
            <ObjectList
                title={t("simulationDetails.genericFields.stats")}
                values={entity.stats}
                emptyValue={t("simulationDetails.emptyValue")}
            />
        </>
    );
}

function EntitySubtabs({ entities, selectedEntity, emptyText, onSelect }) {
    if (entities.length === 0) {
        return <p className="simulation-details-empty-line">{emptyText}</p>;
    }

    return (
        <div className="simulation-detail-subtabs" role="tablist">
            {entities.map((entity) => (
                <button
                    key={entity.id}
                    type="button"
                    className={`simulation-detail-subtab${selectedEntity?.id === entity.id ? " active" : ""}`}
                    onClick={() => onSelect(entity.id)}
                >
                    {entityTitle(entity)}
                </button>
            ))}
        </div>
    );
}

function InventoryList({ title, entries, emptyText, renderMeta }) {
    return (
        <section className="simulation-details-inventory-section">
            <h4>{title}</h4>
            {entries.length === 0 ? (
                <p className="simulation-details-empty-line">{emptyText}</p>
            ) : (
                <div className="simulation-details-inventory-list">
                    {entries.map((entry) => (
                        <article
                            key={entry.id ?? entry.stack_id ?? entry.item_id}
                            className="simulation-details-inventory-card"
                        >
                            <div className="simulation-details-inventory-card-header">
                                <h5>{entry.name}</h5>
                                <span>{renderMeta(entry)}</span>
                            </div>
                            <p>{entry.description}</p>
                            {entry.quality ? (
                                <div className="simulation-details-inventory-quality">
                                    {entry.quality}
                                </div>
                            ) : null}
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}

function CharacterInventory({ inventory }) {
    const { t } = useTranslation();
    const safeInventory = inventory ?? { stacks: [], equipment: [], containers: [] };

    return (
        <section className="simulation-details-inventory">
            <h4>{t("simulationDetails.characterFields.inventory")}</h4>
            <InventoryList
                title={t("simulationDetails.inventory.stacks")}
                entries={safeInventory.stacks ?? []}
                emptyText={t("simulationDetails.inventory.emptyStacks")}
                renderMeta={(stack) =>
                    stack.unique
                        ? t("simulationDetails.inventory.unique")
                        : t("simulationDetails.inventory.quantity", { quantity: stack.quantity })
                }
            />
            <InventoryList
                title={t("simulationDetails.inventory.equipment")}
                entries={safeInventory.equipment ?? []}
                emptyText={t("simulationDetails.inventory.emptyEquipment")}
                renderMeta={(equipment) =>
                    equipment.equipped
                        ? t("simulationDetails.inventory.equipped", {
                              position: equipment.equipped_position ?? "",
                          })
                        : t("simulationDetails.inventory.held")
                }
            />
            <InventoryList
                title={t("simulationDetails.inventory.containers")}
                entries={safeInventory.containers ?? []}
                emptyText={t("simulationDetails.inventory.emptyContainers")}
                renderMeta={(container) =>
                    t(`worldCreate.enums.containerState.${container.state}`, {
                        defaultValue: container.state,
                    })
                }
            />
        </section>
    );
}

function LocationEntities({ entities }) {
    const { t } = useTranslation();

    return (
        <section className="simulation-details-inventory">
            <h4>{t("simulationDetails.locationFields.entities")}</h4>
            {(entities ?? []).length === 0 ? (
                <p className="simulation-details-empty-line">
                    {t("simulationDetails.locationFields.noEntities")}
                </p>
            ) : (
                <div className="simulation-details-inventory-list">
                    {entities.map((entity) => (
                        <article key={entity.id} className="simulation-details-inventory-card">
                            <div className="simulation-details-inventory-card-header">
                                <h5>{entity.name}</h5>
                                <span>{entity.type}</span>
                            </div>
                            <p>{entity.description}</p>
                            <div className="simulation-details-inventory-quality">
                                {entity.status}
                            </div>
                            {entity.interactions?.length > 0 ? (
                                <div className="simulation-details-entity-interactions">
                                    {entity.interactions.map((interaction) => (
                                        <span key={interaction}>{interaction}</span>
                                    ))}
                                </div>
                            ) : null}
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}

function SimulationConfigEditor({ simulationId }) {
    const { t } = useTranslation();
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [embeddingConfigs, setEmbeddingConfigs] = useState([]);
    const [llmConfigsByComponent, setLlmConfigsByComponent] = useState(
        () => emptyComponentConfigMap(simulatorComponents),
    );
    const [embeddingConfigsByComponent, setEmbeddingConfigsByComponent] = useState(
        () => emptyComponentConfigMap(simulatorComponents),
    );
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfigurations() {
            try {
                setLoading(true);
                setError(null);

                const [llms, embeddings, llmAssignments, embeddingAssignments] = await Promise.all([
                    fetchLlmConfigs(),
                    fetchEmbeddingConfigs(),
                    fetchSimulationLlmConfigs(simulationId),
                    fetchSimulationEmbeddingConfigs(simulationId),
                ]);

                if (!cancelled) {
                    setLlmConfigs(llms);
                    setEmbeddingConfigs(embeddings);
                    setLlmConfigsByComponent(
                        componentConfigMapFromAssignments(simulatorComponents, llmAssignments),
                    );
                    setEmbeddingConfigsByComponent(
                        componentConfigMapFromAssignments(simulatorComponents, embeddingAssignments),
                    );
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadConfigurations();

        return () => {
            cancelled = true;
        };
    }, [simulationId]);

    function updateComponentConfig(kind, component, configId) {
        const setter = kind === "llm" ? setLlmConfigsByComponent : setEmbeddingConfigsByComponent;

        setter((current) => ({
            ...current,
            [component]: configId,
        }));
    }

    async function saveConfigurations() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            await Promise.all([
                setSimulationLlmConfigs(
                    simulationId,
                    componentAssignmentsFromMap(simulatorComponents, llmConfigsByComponent),
                ),
                setSimulationEmbeddingConfigs(
                    simulationId,
                    componentAssignmentsFromMap(simulatorComponents, embeddingConfigsByComponent),
                ),
            ]);
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("simulationDetails.configLoading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
            <div className="world-editor-config-matrix">
                <div className="world-editor-config-matrix-header">
                    <span>{t("worldCreate.newEditor.fields.component")}</span>
                    <span>{t("worldCreate.newEditor.fields.llmConfig")}</span>
                    <span>{t("worldCreate.newEditor.fields.embeddingConfig")}</span>
                </div>
                {simulatorComponents.map((component) => (
                    <div className="world-editor-config-row" key={component}>
                        <div className="world-editor-component-name">
                            {t(`worldCreate.newEditor.components.${component}`, { defaultValue: component })}
                        </div>
                        <select
                            className="single-line-input"
                            value={llmConfigsByComponent[component] ?? ""}
                            onChange={(event) => updateComponentConfig("llm", component, event.target.value)}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {llmConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {configLabel(config, config.id)}
                                </option>
                            ))}
                        </select>
                        <select
                            className="single-line-input"
                            value={embeddingConfigsByComponent[component] ?? ""}
                            onChange={(event) =>
                                updateComponentConfig("embedding", component, event.target.value)
                            }
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {embeddingConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {configLabel(config, config.id)}
                                </option>
                            ))}
                        </select>
                    </div>
                ))}
            </div>
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveConfigurations}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

const imageGenerationModes = ["manual", "auto", "always"];

function ImageGenerationConfigEditor({ simulationId }) {
    const { t } = useTranslation();
    const [mode, setMode] = useState("manual");
    const [fallbackTurns, setFallbackTurns] = useState(10);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfig() {
            try {
                setLoading(true);
                setError(null);

                const config = await fetchSimulationImageGenerationConfig(simulationId);

                if (!cancelled) {
                    setMode(config.mode ?? "manual");
                    setFallbackTurns(config.fallback_turns ?? 10);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadConfig();

        return () => {
            cancelled = true;
        };
    }, [simulationId]);

    async function saveConfig() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            const saved = await setSimulationImageGenerationConfig(simulationId, {
                mode,
                fallback_turns: Number(fallbackTurns) || 1,
            });
            setMode(saved.mode ?? mode);
            setFallbackTurns(saved.fallback_turns ?? fallbackTurns);
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("simulationDetails.configLoading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
            <label className="form-field inline-field">
                <span className="world-editor-field-label">
                    <span>{t("simulationDetails.imageGeneration.mode")}</span>
                </span>
                <select
                    className="single-line-input"
                    value={mode}
                    onChange={(event) => setMode(event.target.value)}
                >
                    {imageGenerationModes.map((option) => (
                        <option key={option} value={option}>
                            {t(`simulationDetails.imageGeneration.modes.${option}`)}
                        </option>
                    ))}
                </select>
            </label>
            <p className="simulation-details-empty-line">
                {t(`simulationDetails.imageGeneration.modeHints.${mode}`)}
            </p>
            {mode === "auto" ? (
                <div className="compact-form-field">
                    <label htmlFor="image-generation-fallback-turns">
                        {t("simulationDetails.imageGeneration.fallbackTurns")}
                    </label>
                    <input
                        id="image-generation-fallback-turns"
                        className="single-line-input"
                        type="number"
                        min="1"
                        step="1"
                        value={fallbackTurns}
                        onChange={(event) => setFallbackTurns(event.target.value)}
                    />
                </div>
            ) : null}
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveConfig}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

function ImageModelConfigEditor({ simulationId }) {
    const { t } = useTranslation();
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [imageConfigs, setImageConfigs] = useState([]);
    const [llmConfigsByComponent, setLlmConfigsByComponent] = useState(
        () => emptyComponentConfigMap(imageChatComponents),
    );
    const [imageConfigsByComponent, setImageConfigsByComponent] = useState(
        () => emptyComponentConfigMap(imageComponents),
    );
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfigurations() {
            try {
                setLoading(true);
                setError(null);

                const [llms, images, llmAssignments, imageAssignments] = await Promise.all([
                    fetchLlmConfigs(),
                    fetchImageConfigs(),
                    fetchSimulationLlmConfigs(simulationId),
                    fetchSimulationImageConfigs(simulationId),
                ]);

                if (!cancelled) {
                    setLlmConfigs(llms);
                    setImageConfigs(images);
                    setLlmConfigsByComponent(
                        componentConfigMapFromAssignments(imageChatComponents, llmAssignments),
                    );
                    setImageConfigsByComponent(
                        componentConfigMapFromAssignments(imageComponents, imageAssignments),
                    );
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadConfigurations();

        return () => {
            cancelled = true;
        };
    }, [simulationId]);

    function updateComponentConfig(kind, component, configId) {
        const setter = kind === "llm" ? setLlmConfigsByComponent : setImageConfigsByComponent;

        setter((current) => ({
            ...current,
            [component]: configId,
        }));
    }

    async function saveConfigurations() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            await Promise.all([
                setSimulationLlmConfigs(
                    simulationId,
                    componentAssignmentsFromMap(imageChatComponents, llmConfigsByComponent),
                ),
                setSimulationImageConfigs(
                    simulationId,
                    componentAssignmentsFromMap(imageComponents, imageConfigsByComponent),
                ),
            ]);
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("simulationDetails.configLoading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
            <div className="world-editor-config-matrix">
                <div className="world-editor-config-matrix-header">
                    <span>{t("worldCreate.newEditor.fields.component")}</span>
                    <span>{t("worldCreate.newEditor.fields.llmConfig")}</span>
                    <span>{t("worldCreate.newEditor.fields.imageConfig")}</span>
                </div>
                {imageChatComponents.map((component) => (
                    <div className="world-editor-config-row" key={component}>
                        <div className="world-editor-component-name">
                            {t(`worldCreate.newEditor.components.${component}`, { defaultValue: component })}
                        </div>
                        <select
                            className="single-line-input"
                            value={llmConfigsByComponent[component] ?? ""}
                            onChange={(event) => updateComponentConfig("llm", component, event.target.value)}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {llmConfigs.map((config) => (
                                <option key={config.id} value={config.id}>
                                    {configLabel(config, config.id)}
                                </option>
                            ))}
                        </select>
                        {imageComponents.includes(component) ? (
                            <select
                                className="single-line-input"
                                value={imageConfigsByComponent[component] ?? ""}
                                onChange={(event) => updateComponentConfig("image", component, event.target.value)}
                            >
                                <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                                {imageConfigs.map((config) => (
                                    <option key={config.id} value={config.id}>
                                        {configLabel(config, config.id)}
                                    </option>
                                ))}
                            </select>
                        ) : (
                            <span className="simulation-details-empty-line">
                                {t("simulationDetails.imageGeneration.noImageModelNeeded")}
                            </span>
                        )}
                    </div>
                ))}
            </div>
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveConfigurations}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

const ttsGenerationModes = ["manual", "auto"];

function TtsGenerationConfigEditor({ simulationId }) {
    const { t } = useTranslation();
    const [mode, setMode] = useState("manual");
    const [autoplayInBrowser, setAutoplayInBrowser] = useState(false);
    const [availableBackends, setAvailableBackends] = useState([]);
    const [backendConfigId, setBackendConfigId] = useState(null);
    const [narratorVoice, setNarratorVoice] = useState("");
    const [rvcNarratorVoice, setRvcNarratorVoice] = useState("");
    const [rvcNarratorPitch, setRvcNarratorPitch] = useState("");
    const [voiceOptions, setVoiceOptions] = useState([]);
    const [rvcVoiceOptions, setRvcVoiceOptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfig() {
            try {
                setLoading(true);
                setError(null);

                const [genConfig, backend, backends] = await Promise.all([
                    fetchSimulationTtsGenerationConfig(simulationId),
                    fetchSimulationTtsBackendConfig(simulationId).catch(() => null),
                    fetchTtsConfigs().catch(() => []),
                ]);

                if (!cancelled) {
                    setMode(genConfig.mode ?? "manual");
                    setAutoplayInBrowser(Boolean(genConfig.autoplay_in_browser));
                    setAvailableBackends(backends);
                    setBackendConfigId(backend?.id ?? null);
                    setNarratorVoice(genConfig.narrator_voice ?? "");
                    setRvcNarratorVoice(genConfig.rvc_narrator_voice ?? "");
                    setRvcNarratorPitch(genConfig.rvc_narrator_pitch == null ? "" : String(genConfig.rvc_narrator_pitch));
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadConfig();

        return () => {
            cancelled = true;
        };
    }, [simulationId]);

    // The narrator's voice and RVC voice can only be ones AllTalk actually has loaded, so they're
    // fetched live from the selected backend's connection rather than typed in freehand.
    useEffect(() => {
        const connectionId = availableBackends.find((backend) => backend.id === backendConfigId)?.connection?.id;
        if (!connectionId) {
            return undefined;
        }

        let cancelled = false;

        async function loadVoices() {
            try {
                const status = await fetchAllTalkStatus(connectionId);
                if (!cancelled) {
                    setVoiceOptions(status.voices ?? []);
                    setRvcVoiceOptions(status.rvc_voices ?? []);
                }
            } catch {
                if (!cancelled) {
                    setVoiceOptions([]);
                    setRvcVoiceOptions([]);
                }
            }
        }

        loadVoices();

        return () => {
            cancelled = true;
        };
    }, [backendConfigId, availableBackends]);

    function handleBackendChange(nextBackendConfigId) {
        setBackendConfigId(nextBackendConfigId || null);
    }

    async function saveConfig() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            const saved = await setSimulationTtsGenerationConfig(simulationId, {
                mode,
                autoplay_in_browser: autoplayInBrowser,
                narrator_voice: narratorVoice || null,
                rvc_narrator_voice: rvcNarratorVoice || null,
                rvc_narrator_pitch: rvcNarratorPitch === "" ? null : Number.parseInt(rvcNarratorPitch, 10),
            });
            setMode(saved.mode ?? mode);
            setAutoplayInBrowser(Boolean(saved.autoplay_in_browser));
            setNarratorVoice(saved.narrator_voice ?? "");
            setRvcNarratorVoice(saved.rvc_narrator_voice ?? "");
            setRvcNarratorPitch(saved.rvc_narrator_pitch == null ? "" : String(saved.rvc_narrator_pitch));
            if (backendConfigId) {
                await setSimulationTtsConfig(simulationId, backendConfigId);
            }
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return <p className="status-text">{t("simulationDetails.configLoading")}</p>;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
            <label className="form-field inline-field">
                <span className="world-editor-field-label">
                    <span>{t("simulationDetails.ttsGeneration.mode")}</span>
                </span>
                <select
                    className="single-line-input"
                    value={mode}
                    onChange={(event) => setMode(event.target.value)}
                >
                    {ttsGenerationModes.map((option) => (
                        <option key={option} value={option}>
                            {t(`simulationDetails.ttsGeneration.modes.${option}`)}
                        </option>
                    ))}
                </select>
            </label>
            <p className="simulation-details-empty-line">
                {t(`simulationDetails.ttsGeneration.modeHints.${mode}`)}
            </p>
            <label className="form-field inline-field">
                <span className="world-editor-field-label">
                    <span>{t("simulationDetails.ttsGeneration.autoplayInBrowser")}</span>
                </span>
                <input
                    type="checkbox"
                    checked={autoplayInBrowser}
                    onChange={(event) => setAutoplayInBrowser(event.target.checked)}
                />
            </label>
            <p className="simulation-details-empty-line">
                {t("simulationDetails.ttsGeneration.autoplayInBrowserHint")}
            </p>
            <label className="form-field inline-field">
                <span className="world-editor-field-label">
                    <span>{t("simulationDetails.ttsGeneration.backend")}</span>
                </span>
                <select
                    className="single-line-input"
                    value={backendConfigId ?? ""}
                    onChange={(event) => handleBackendChange(event.target.value)}
                >
                    <option value="">{t("simulationDetails.ttsGeneration.noBackend")}</option>
                    {availableBackends.map((backend) => (
                        <option key={backend.id} value={backend.id}>
                            {backend.name || backend.model || backend.engine} ({backend.engine})
                        </option>
                    ))}
                </select>
            </label>
            <div className="compact-form-field">
                <label htmlFor="tts-generation-narrator-voice">
                    {t("simulationDetails.ttsGeneration.narratorVoice")}
                </label>
                <select
                    id="tts-generation-narrator-voice"
                    className="single-line-input"
                    value={narratorVoice}
                    disabled={!backendConfigId}
                    onChange={(event) => setNarratorVoice(event.target.value)}
                >
                    <option value="">{t("simulationDetails.ttsGeneration.noVoice")}</option>
                    {Array.from(new Set([...voiceOptions, ...(narratorVoice ? [narratorVoice] : [])])).map(
                        (voice) => (
                            <option key={voice} value={voice}>
                                {voice}
                            </option>
                        ),
                    )}
                </select>
            </div>
            <div className="compact-form-field">
                <label htmlFor="tts-generation-rvc-narrator-voice">
                    {t("simulationDetails.ttsGeneration.rvcNarratorVoice")}
                </label>
                <select
                    id="tts-generation-rvc-narrator-voice"
                    className="single-line-input"
                    value={rvcNarratorVoice}
                    disabled={!backendConfigId}
                    onChange={(event) => setRvcNarratorVoice(event.target.value)}
                >
                    <option value="">{t("simulationDetails.ttsGeneration.noVoice")}</option>
                    {Array.from(new Set([...rvcVoiceOptions, ...(rvcNarratorVoice ? [rvcNarratorVoice] : [])])).map(
                        (voice) => (
                            <option key={voice} value={voice}>
                                {voice}
                            </option>
                        ),
                    )}
                </select>
            </div>
            <div className="compact-form-field">
                <label htmlFor="tts-generation-rvc-narrator-pitch">
                    {t("simulationDetails.ttsGeneration.rvcNarratorPitch")}
                </label>
                <input
                    id="tts-generation-rvc-narrator-pitch"
                    className="single-line-input"
                    type="number"
                    value={rvcNarratorPitch}
                    disabled={!backendConfigId}
                    onChange={(event) => setRvcNarratorPitch(event.target.value)}
                />
            </div>
            {!backendConfigId ? (
                <p className="simulation-details-empty-line">
                    {t("simulationDetails.ttsGeneration.narratorVoiceHint")}
                </p>
            ) : null}
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveConfig}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

function CharacterVoiceEditor({ simulationId, characterId }) {
    const { t } = useTranslation();
    const [voice, setVoice] = useState("");
    const [backendConfigId, setBackendConfigId] = useState(null);
    const [backendConnectionId, setBackendConnectionId] = useState(null);
    const [voiceOptions, setVoiceOptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function loadConfig() {
            try {
                setLoading(true);
                setError(null);

                const [ttsConfig, backend] = await Promise.all([
                    fetchCharacterTtsConfig(characterId).catch(() => null),
                    fetchSimulationTtsBackendConfig(simulationId).catch(() => null),
                ]);

                if (!cancelled) {
                    setVoice(ttsConfig?.character_voice ?? "");
                    setBackendConfigId(backend?.id ?? null);
                    setBackendConnectionId(backend?.connection?.id ?? null);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadConfig();

        return () => {
            cancelled = true;
        };
    }, [simulationId, characterId]);

    // Same reasoning as TtsGenerationConfigEditor's narrator voice - a character can only speak
    // with a voice AllTalk actually has loaded, fetched live from the simulation's TTS backend.
    useEffect(() => {
        if (!backendConnectionId) {
            return undefined;
        }

        let cancelled = false;

        async function loadVoices() {
            try {
                const status = await fetchAllTalkStatus(backendConnectionId);
                if (!cancelled) {
                    setVoiceOptions(status.voices ?? []);
                }
            } catch {
                if (!cancelled) {
                    setVoiceOptions([]);
                }
            }
        }

        loadVoices();

        return () => {
            cancelled = true;
        };
    }, [backendConnectionId]);

    async function saveVoice() {
        try {
            setSaving(true);
            setNotice(null);
            setError(null);
            const payload = { character_voice: voice || null };
            if (backendConfigId) {
                payload.backend_config_id = backendConfigId;
            }
            const saved = await setCharacterTtsConfig(characterId, payload);
            setVoice(saved.character_voice ?? "");
            setNotice(t("simulationDetails.configSaved"));
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return null;
    }

    return (
        <section className="world-editor-form">
            {error ? (
                <p className="status-text error-text">
                    {t("simulationDetails.configError", { error })}
                </p>
            ) : null}
            <div className="compact-form-field">
                <label htmlFor="character-voice-input">{t("simulationDetails.characterFields.voice")}</label>
                <select
                    id="character-voice-input"
                    className="single-line-input"
                    value={voice}
                    disabled={!backendConnectionId}
                    onChange={(event) => setVoice(event.target.value)}
                >
                    <option value="">{t("simulationDetails.ttsGeneration.noVoice")}</option>
                    {Array.from(new Set([...voiceOptions, ...(voice ? [voice] : [])])).map((option) => (
                        <option key={option} value={option}>
                            {option}
                        </option>
                    ))}
                </select>
            </div>
            {!backendConnectionId ? (
                <p className="simulation-details-empty-line">
                    {t("simulationDetails.ttsGeneration.narratorVoiceHint")}
                </p>
            ) : null}
            {notice ? <p className="simulation-details-empty-line">{notice}</p> : null}
            <div className="modal-actions inline-actions">
                <button type="button" className="primary-button" disabled={saving} onClick={saveVoice}>
                    {saving ? t("simulationDetails.configSaving") : t("simulationDetails.saveConfigurations")}
                </button>
            </div>
        </section>
    );
}

function SimulationDetailsModal({
    simulation,
    characters,
    locations,
    entities,
    inventory,
    emotion,
    characterLocation,
    auditEvents,
    imageCapabilities = emptyObject,
    activeSection,
    selectedCharacterId,
    selectedLocationId,
    selectedEntityIds,
    onActiveSectionChange,
    onSelectedCharacterIdChange,
    onSelectedLocationIdChange,
    onSelectedEntityIdChange,
    onClose,
}) {
    const { t } = useTranslation();
    const canGenerateCharacterCover = Boolean(imageCapabilities.character_image_generator);
    const canGenerateLocationCover = Boolean(imageCapabilities.location_image_generator);
    const canGenerateItemCover = Boolean(imageCapabilities.item_image_generator);
    const [coverPickerTarget, setCoverPickerTarget] = useState(null);
    const [coverRefreshKey, setCoverRefreshKey] = useState(0);
    const [coverActionError, setCoverActionError] = useState(null);
    const selectedCharacter =
        characters.find((character) => character.id === selectedCharacterId) ?? characters[0] ?? null;
    const selectedLocation = selectedCharacter ? characterLocation ?? null : null;
    const selectedLocationDetail =
        locations.find((location) => location.id === selectedLocationId) ?? locations[0] ?? null;
    const selectedEntity = entityDetailSections.includes(activeSection)
        ? (entities[activeSection] ?? []).find((entity) => entity.id === selectedEntityIds[activeSection]) ??
          (entities[activeSection] ?? [])[0] ??
          null
        : null;

    useEffect(() => {
        function onKeyDown(event) {
            if (event.key === "Escape") {
                onClose();
            }
        }

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [onClose]);

    if (!simulation) {
        return null;
    }

    function selectLocation(locationId) {
        onSelectedLocationIdChange(locationId);
        onActiveSectionChange("locations");
    }

    async function handleSelectCover(media) {
        if (!coverPickerTarget) {
            return;
        }

        try {
            setCoverActionError(null);
            await setCoverImage(coverPickerTarget.kind, coverPickerTarget.id, media.id);
            setCoverRefreshKey((current) => current + 1);
            setCoverPickerTarget(null);
        } catch (err) {
            setCoverActionError(err.message);
        }
    }

    async function handleRemoveCover(kind, id) {
        try {
            setCoverActionError(null);
            await deleteCoverImage(kind, id);
            setCoverRefreshKey((current) => current + 1);
        } catch (err) {
            setCoverActionError(err.message);
        }
    }

    // Stacks display and inherit the cover image of the item they're an instance of, rather
    // than getting their own - so the cover target for a selected stack is its item.
    function coverTargetForEntitySection(section, entity) {
        if (!entity) {
            return null;
        }
        if (section === "stacks") {
            return entity.item?.id ? { kind: "items", id: entity.item.id } : null;
        }
        return { kind: section, id: entity.id };
    }

    function navigateToEntity(section, entityId) {
        if (section === "locations") {
            selectLocation(entityId);
            return;
        }
        if (section === "characters") {
            onSelectedCharacterIdChange(entityId);
            onActiveSectionChange("characters");
            return;
        }
        onSelectedEntityIdChange(section, entityId);
        onActiveSectionChange(section);
    }

    const detailsTitle =
        activeSection === "characters" && selectedCharacter
            ? selectedCharacter.name
            : activeSection === "locations" && selectedLocationDetail
              ? formatLocation(selectedLocationDetail, t("simulationDetails.tabs.locations"))
              : selectedEntity
                ? entityTitle(selectedEntity)
                : activeSection === "configs"
                    ? t("simulationDetails.tabs.configs")
                    : activeSection === "imageGeneration"
                      ? t("simulationDetails.tabs.imageGeneration")
                    : activeSection === "ttsGeneration"
                      ? t("simulationDetails.tabs.ttsGeneration")
                    : activeSection === "prompts"
                      ? t("simulationDetails.tabs.prompts")
                    : activeSection === "observability"
                      ? t("simulationDetails.tabs.observability")
                  : simulation.name;

    const basicRows = [
        { label: t("simulationDetails.fields.name"), value: simulation.name },
        { label: t("simulationDetails.fields.language"), value: simulation.language },
        { label: t("simulationDetails.fields.actForUser"), value: formatBoolean(simulation.act_for_user, t) },
        {
            label: t("simulationDetails.fields.enableImageGeneration"),
            value: formatBoolean(simulation.enable_image_generation, t),
        },
        {
            label: t("simulationDetails.fields.emotionEnabled"),
            value: formatBoolean(simulation.emotion_enabled, t),
        },
    ];
    const characterRows = selectedCharacter
        ? [
              { label: t("simulationDetails.characterFields.gender"), value: selectedCharacter.gender },
              { label: t("simulationDetails.characterFields.age"), value: selectedCharacter.age },
              {
                  label: t("simulationDetails.characterFields.location"),
                  value: selectedLocation ? (
                      <DetailLink onClick={() => selectLocation(selectedLocation.id)}>
                          {formatLocation(selectedLocation, t("simulationDetails.emptyValue"))}
                      </DetailLink>
                  ) : (
                      t("simulationDetails.emptyValue")
                  ),
              },
              {
                  label: t("simulationDetails.characterFields.userControlled"),
                  value: formatBoolean(selectedCharacter.user_controlled, t),
              },
          ]
        : [];
    const locationRows = selectedLocationDetail
        ? [
              { label: t("simulationDetails.locationFields.name"), value: selectedLocationDetail.name },
              {
                  label: t("simulationDetails.locationFields.description"),
                  value: selectedLocationDetail.description,
              },
          ]
        : [];
    const selectedEntityImageUrl = (() => {
        if (!selectedEntity?.id) {
            return null;
        }

        const suffix = coverRefreshKey ? `?v=${coverRefreshKey}` : "";

        if (activeSection === "landmarks") {
            return `${getSimulationLandmarkImageUrl(selectedEntity.id)}${suffix}`;
        }
        if (activeSection === "background") {
            return `${getSimulationBackgroundCharacterImageUrl(selectedEntity.id)}${suffix}`;
        }
        if (activeSection === "items") {
            return `${getSimulationItemImageUrl(selectedEntity.id)}${suffix}`;
        }
        if (activeSection === "stacks") {
            // Stacks are physical instances of an Item and don't get their own generated
            // image - show the item's cover image instead.
            return selectedEntity.item?.id
                ? `${getSimulationItemImageUrl(selectedEntity.item.id)}${suffix}`
                : null;
        }
        if (activeSection === "equipment") {
            return `${getSimulationEquipmentImageUrl(selectedEntity.id)}${suffix}`;
        }
        if (activeSection === "containers") {
            return `${getSimulationContainerImageUrl(selectedEntity.id)}${suffix}`;
        }
        return null;
    })();

    const selectedEntityFallback =
        activeSection === "background"
            ? characterPlaceholderImage
            : activeSection === "landmarks"
              ? locationPlaceholderImage
              : entityPlaceholderImage;

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="simulation-details-modal world-editor-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="simulation-details-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <aside className="simulation-details-nav" aria-label={t("simulationDetails.navLabel")}>
                    <div className="simulation-details-nav-title">
                        {t("simulationDetails.title")}
                    </div>
                    {detailSections.map((section) => (
                        <button
                            key={section}
                            type="button"
                            className={`simulation-details-nav-item${activeSection === section ? " active" : ""}`}
                            onClick={() => onActiveSectionChange(section)}
                        >
                            {t(`simulationDetails.tabs.${section}`, {
                                defaultValue: t(`worldCreate.newEditor.tabs.${section}`, { defaultValue: section }),
                            })}
                        </button>
                    ))}
                </aside>

                <section className="simulation-details-content">
                    <header className="simulation-details-header">
                        <div>
                            <p className="simulation-details-eyebrow">
                                {t(`simulationDetails.tabs.${activeSection}`)}
                            </p>
                            <h2 id="simulation-details-title">{detailsTitle}</h2>
                        </div>
                        <button
                            type="button"
                            className="icon-button"
                            aria-label={t("simulationDetails.close")}
                            onClick={onClose}
                        >
                            ×
                        </button>
                    </header>

                    <div className="simulation-details-body">
                        {activeSection === "characters" ? (
                            <div className="simulation-detail-subtabs" role="tablist">
                                {characters.map((character) => (
                                    <button
                                        key={character.id}
                                        type="button"
                                        className={`simulation-detail-subtab${
                                            selectedCharacter?.id === character.id ? " active" : ""
                                        }`}
                                        onClick={() => onSelectedCharacterIdChange(character.id)}
                                    >
                                        {character.name}
                                    </button>
                                ))}
                            </div>
                        ) : null}
                        {activeSection === "locations" ? (
                            <div className="simulation-detail-subtabs" role="tablist">
                                {locations.map((location) => (
                                    <button
                                        key={location.id}
                                        type="button"
                                        className={`simulation-detail-subtab${
                                            selectedLocationDetail?.id === location.id ? " active" : ""
                                        }`}
                                        onClick={() => onSelectedLocationIdChange(location.id)}
                                    >
                                        {formatLocation(location, t("simulationDetails.locationFields.location"))}
                                    </button>
                                ))}
                            </div>
                        ) : null}
                        {entityDetailSections.includes(activeSection) ? (
                            <EntitySubtabs
                                entities={entities[activeSection] ?? []}
                                selectedEntity={selectedEntity}
                                emptyText={t(`simulationDetails.empty.${activeSection}`, {
                                    defaultValue: t("simulationDetails.emptySection"),
                                })}
                                onSelect={(entityId) => onSelectedEntityIdChange(activeSection, entityId)}
                            />
                        ) : null}

                        {activeSection === "configs" ? (
                            <SimulationConfigEditor simulationId={simulation.id} />
                        ) : activeSection === "imageGeneration" ? (
                            <>
                                <ImageModelConfigEditor simulationId={simulation.id} />
                                <div className="simulation-details-separator" />
                                <ImageGenerationConfigEditor simulationId={simulation.id} />
                            </>
                        ) : activeSection === "ttsGeneration" ? (
                            <TtsGenerationConfigEditor simulationId={simulation.id} />
                        ) : activeSection === "prompts" ? (
                            <PromptAssignmentEditor sourceType="simulation" sourceId={simulation.id} />
                        ) : activeSection === "observability" ? (
                            <AuditEventTimeline events={auditEvents} />
                        ) : entityDetailSections.includes(activeSection) ? (
                            <GenericEntityPanel
                                section={activeSection}
                                entity={selectedEntity}
                                emptyText={t(`simulationDetails.empty.${activeSection}`, {
                                    defaultValue: t("simulationDetails.emptySection"),
                                })}
                                imageUrl={selectedEntityImageUrl}
                                fallbackImage={selectedEntityFallback}
                                characters={characters}
                                locations={locations}
                                entities={entities}
                                onNavigate={navigateToEntity}
                                coverImageAction={
                                    selectedEntity ? (
                                        <>
                                            {activeSection === "items" && canGenerateItemCover ? (
                                                <GenerateCoverImageButton
                                                    label={t("simulationDetails.generateCoverImage")}
                                                    onGenerate={() => generateItemCoverImage({
                                                        sourceId: simulation.id,
                                                        itemId: selectedEntity.id,
                                                    })}
                                                />
                                            ) : null}
                                            <CoverImageActions
                                                error={coverActionError}
                                                onChoose={() =>
                                                    setCoverPickerTarget(
                                                        coverTargetForEntitySection(activeSection, selectedEntity),
                                                    )
                                                }
                                                onRemove={() => {
                                                    const target = coverTargetForEntitySection(
                                                        activeSection,
                                                        selectedEntity,
                                                    );
                                                    if (target) {
                                                        handleRemoveCover(target.kind, target.id);
                                                    }
                                                }}
                                            />
                                        </>
                                    ) : null
                                }
                            />
                        ) : activeSection === "locations" ? (
                            selectedLocationDetail ? (
                                <>
                                    <div className="simulation-details-hero">
                                        <LocationImage
                                            simulationId={simulation.id}
                                            location={selectedLocationDetail}
                                            refreshKey={coverRefreshKey}
                                        />
                                        <div className="simulation-details-summary">
                                            <h3>
                                                {formatLocation(
                                                    selectedLocationDetail,
                                                    t("simulationDetails.locationFields.location"),
                                                )}
                                            </h3>
                                            <p>
                                                {selectedLocationDetail.description ||
                                                    t("simulationDetails.noDescription")}
                                            </p>
                                            {canGenerateLocationCover ? (
                                                <GenerateCoverImageButton
                                                    label={t("simulationDetails.generateCoverImage")}
                                                    onGenerate={() => generateLocationCoverImage({
                                                        sourceId: simulation.id,
                                                        locationId: selectedLocationDetail.id,
                                                    })}
                                                />
                                            ) : null}
                                            <CoverImageActions
                                                error={coverActionError}
                                                onChoose={() =>
                                                    setCoverPickerTarget({
                                                        kind: "locations",
                                                        id: selectedLocationDetail.id,
                                                    })
                                                }
                                                onRemove={() =>
                                                    handleRemoveCover("locations", selectedLocationDetail.id)
                                                }
                                            />
                                        </div>
                                    </div>

                                    <div className="simulation-details-separator" />

                                    <dl className="simulation-details-grid">
                                        {locationRows.map((row) => (
                                            <div key={row.label} className="simulation-details-row">
                                                <dt>{row.label}</dt>
                                                <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                            </div>
                                        ))}
                                    </dl>

                                    <ObjectList
                                        title={t("simulationDetails.locationFields.attributes")}
                                        values={selectedLocationDetail.attributes}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <ObjectList
                                        title={t("simulationDetails.locationFields.stats")}
                                        values={selectedLocationDetail.stats}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <LocationEntities entities={selectedLocationDetail.entities} />
                                </>
                            ) : (
                                <p className="status-text">{t("simulationDetails.noLocations")}</p>
                            )
                        ) : activeSection === "characters" ? (
                            selectedCharacter ? (
                                <>
                                    <div className="simulation-details-hero">
                                        <CharacterImage
                                            simulationId={simulation.id}
                                            character={selectedCharacter}
                                            refreshKey={coverRefreshKey}
                                        />
                                        <div className="simulation-details-summary">
                                            <h3>{selectedCharacter.name}</h3>
                                            <p>
                                                {selectedCharacter.description ||
                                                    t("simulationDetails.noDescription")}
                                            </p>
                                            {canGenerateCharacterCover ? (
                                                <GenerateCoverImageButton
                                                    label={t("simulationDetails.generateCoverImage")}
                                                    onGenerate={() => generateCharacterCoverImage({
                                                        sourceId: simulation.id,
                                                        characterId: selectedCharacter.id,
                                                    })}
                                                />
                                            ) : null}
                                            <CoverImageActions
                                                error={coverActionError}
                                                onChoose={() =>
                                                    setCoverPickerTarget({
                                                        kind: "characters",
                                                        id: selectedCharacter.id,
                                                    })
                                                }
                                                onRemove={() => handleRemoveCover("characters", selectedCharacter.id)}
                                            />
                                        </div>
                                    </div>

                                    <div className="simulation-details-separator" />

                                    <dl className="simulation-details-grid">
                                        {characterRows.map((row) => (
                                            <div key={row.label} className="simulation-details-row">
                                                <dt>{row.label}</dt>
                                                <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                            </div>
                                        ))}
                                    </dl>

                                    <div className="simulation-details-separator" />

                                    <div className="simulation-details-text-grid">
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.appearance")}</h4>
                                            <p>{selectedCharacter.appearance || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.publicState")}</h4>
                                            <p>{selectedCharacter.public_state || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                        <section>
                                            <h4>{t("simulationDetails.characterFields.privateState")}</h4>
                                            <p>{selectedCharacter.private_state || t("simulationDetails.emptyValue")}</p>
                                        </section>
                                    </div>

                                    <CharacterVoiceEditor
                                        simulationId={simulation.id}
                                        characterId={selectedCharacter.id}
                                    />

                                    <ObjectList
                                        title={t("simulationDetails.characterFields.attributes")}
                                        values={selectedCharacter.attributes}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <ObjectList
                                        title={t("simulationDetails.characterFields.stats")}
                                        values={selectedCharacter.stats}
                                        emptyValue={t("simulationDetails.emptyValue")}
                                    />
                                    <CharacterInventory inventory={inventory} />
                                    {emotion ? (
                                        <ObjectList
                                            title={t("simulationDetails.characterFields.emotion")}
                                            values={emotion.effective}
                                            emptyValue={t("simulationDetails.emptyValue")}
                                        />
                                    ) : null}
                                </>
                            ) : (
                                <p className="status-text">{t("simulationDetails.noCharacters")}</p>
                            )
                        ) : (
                            <>
                                <div className="simulation-details-hero">
                                    <SimulationAvatar
                                        simulation={simulation}
                                        className="simulation-details-cover"
                                        refreshKey={coverRefreshKey}
                                    />
                                    <div className="simulation-details-summary">
                                        <h3>{simulation.name}</h3>
                                        <p>
                                            {simulation.description || t("simulationDetails.noDescription")}
                                        </p>
                                        <CoverImageActions
                                            error={coverActionError}
                                            onChoose={() =>
                                                setCoverPickerTarget({ kind: "simulations", id: simulation.id })
                                            }
                                            onRemove={() => handleRemoveCover("simulations", simulation.id)}
                                        />
                                    </div>
                                </div>

                                <div className="simulation-details-separator" />

                                <dl className="simulation-details-grid">
                                    {basicRows.map((row) => (
                                        <div key={row.label} className="simulation-details-row">
                                            <dt>{row.label}</dt>
                                            <dd>{row.value ?? t("simulationDetails.emptyValue")}</dd>
                                        </div>
                                    ))}
                                </dl>
                            </>
                        )}

                        {coverPickerTarget ? (
                            <MediaPickerModal
                                simulationId={simulation.id}
                                onSelect={handleSelectCover}
                                onClose={() => setCoverPickerTarget(null)}
                            />
                        ) : null}
                    </div>
                </section>
            </div>
        </div>
    );
}

const allAuditRunsOption = "__all__";

function formatAuditTimestamp(value) {
    return value ? new Date(value).toLocaleString() : null;
}

// Groups events by run_id (every audit event carries one) so the timeline can default to
// showing just the most recent run/operation instead of every past attempt mixed together.
// A run's status is "failed" if any of its events failed, otherwise it takes the status of
// its most recent event - covers runs still missing a terminal "completed" event too.
function summarizeAuditRuns(events, t) {
    const runsById = new Map();

    for (const event of events) {
        if (!event.run_id) {
            continue;
        }
        const recordedAt = event.recorded_at ? new Date(event.recorded_at).getTime() : 0;
        const existing = runsById.get(event.run_id);
        if (!existing) {
            runsById.set(event.run_id, {
                runId: event.run_id,
                latestRecordedAt: recordedAt,
                latestStage: event.stage,
                category: event.category,
                failed: event.status === "failed",
            });
            continue;
        }
        if (event.status === "failed") {
            existing.failed = true;
        }
        if (recordedAt >= existing.latestRecordedAt) {
            existing.latestRecordedAt = recordedAt;
            existing.latestStage = event.stage;
            existing.category = event.category;
        }
    }

    return Array.from(runsById.values())
        .sort((a, b) => b.latestRecordedAt - a.latestRecordedAt)
        .map((run) => ({
            ...run,
            label: t("simulationDetails.observability.runLabel", {
                time: formatAuditTimestamp(run.latestRecordedAt) ?? t("simulationDetails.emptyValue"),
                category: run.category,
                status: run.failed
                    ? t("simulationDetails.observability.statusFailed")
                    : t("simulationDetails.observability.statusStage", { stage: run.latestStage }),
            }),
        }));
}

function AuditEventDetails({ details }) {
    const { t } = useTranslation();
    const { error_type: errorType, error_message: errorMessage, traceback, ...rest } = details ?? {};
    const hasError = Boolean(errorType || errorMessage || traceback);
    const hasRest = Object.keys(rest).length > 0;

    if (!hasError && !hasRest) {
        return null;
    }

    return (
        <>
            {hasError ? (
                <div className="audit-event-error">
                    <strong>{errorType || t("simulationDetails.observability.error")}</strong>
                    {errorMessage ? <p>{errorMessage}</p> : null}
                    {traceback ? (
                        <details>
                            <summary>{t("simulationDetails.observability.traceback")}</summary>
                            <pre className="audit-event-details">{traceback}</pre>
                        </details>
                    ) : null}
                </div>
            ) : null}
            {hasRest ? (
                <pre className="audit-event-details">{JSON.stringify(rest, null, 2)}</pre>
            ) : null}
        </>
    );
}

function AuditEventTimeline({ events }) {
    const { t } = useTranslation();
    const [selectedRunId, setSelectedRunId] = useState(null);

    const runs = useMemo(() => summarizeAuditRuns(events ?? [], t), [events, t]);
    const effectiveRunId =
        selectedRunId && (selectedRunId === allAuditRunsOption || runs.some((run) => run.runId === selectedRunId))
            ? selectedRunId
            : runs[0]?.runId ?? allAuditRunsOption;

    if (!events?.length) {
        return <p className="status-text">{t("simulationDetails.observability.empty")}</p>;
    }

    const visibleEvents = (
        effectiveRunId === allAuditRunsOption
            ? events
            : events.filter((event) => event.run_id === effectiveRunId)
    )
        .slice()
        .sort((a, b) => new Date(a.recorded_at ?? 0) - new Date(b.recorded_at ?? 0));

    return (
        <div className="audit-timeline">
            {runs.length > 1 ? (
                <label className="audit-run-picker">
                    {t("simulationDetails.observability.viewingRun")}
                    <select
                        value={effectiveRunId}
                        onChange={(event) => setSelectedRunId(event.target.value)}
                    >
                        {runs.map((run) => (
                            <option key={run.runId} value={run.runId}>
                                {run.label}
                            </option>
                        ))}
                        <option value={allAuditRunsOption}>
                            {t("simulationDetails.observability.allRuns")}
                        </option>
                    </select>
                </label>
            ) : null}
            {visibleEvents.map((event) => (
                <article
                    className={`audit-event${event.status === "failed" ? " audit-event-failed" : ""}`}
                    key={event.id}
                >
                    <header>
                        <strong>{event.stage}</strong>
                        <span>{event.category} · {event.origin} · {event.status}</span>
                    </header>
                    <small className="audit-event-timestamp">
                        {formatAuditTimestamp(event.recorded_at) ?? t("simulationDetails.emptyValue")}
                    </small>
                    <p>{event.summary}</p>
                    <small>
                        {event.simulation_time
                            ? t("simulationDetails.observability.simulationTime", {
                                  time: new Date(event.simulation_time).toLocaleString(),
                              })
                            : t("simulationDetails.observability.noSimulationTime")}
                    </small>
                    {event.actor_ids?.length ? (
                        <p className="simulation-details-empty-line">
                            {t("simulationDetails.observability.actors", {
                                actors: event.actor_ids.join(", "),
                            })}
                        </p>
                    ) : null}
                    <AuditEventDetails details={event.details} />
                </article>
            ))}
        </div>
    );
}

export function SimulationChatPage() {
    const { t } = useTranslation();
    const { simulationId } = useParams();
    const recordsEndRef = useRef(null);
    const eventSourceRef = useRef(null);
    const composerInputRef = useRef(null);
    const streamErrorRef = useRef(null);
    const streamReceivedNarrationRef = useRef(false);
    const lastRecordIdBeforeRunRef = useRef(null);
    const autoplayedTurnIdsRef = useRef(new Set());
    const autoplayControllerRef = useRef(null);
    const [simulations, setSimulations] = useState([]);
    const [simulationDetails, setSimulationDetails] = useState({});
    const [characterCache, setCharacterCache] = useState({});
    const [locationCache, setLocationCache] = useState({});
    const [entityCache, setEntityCache] = useState({});
    const [inventoryCache, setInventoryCache] = useState({});
    const [emotionCache, setEmotionCache] = useState({});
    const [characterLocationCache, setCharacterLocationCache] = useState({});
    const [auditCache, setAuditCache] = useState({});
    const [imageCapabilityCache, setImageCapabilityCache] = useState({});
    const [previews, setPreviews] = useState({});
    const [records, setRecords] = useState([]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [sendError, setSendError] = useState(null);
    const [streamingRecord, setStreamingRecord] = useState(null);
    const [loading, setLoading] = useState(true);
    const [recordLoading, setRecordLoading] = useState(true);
    const [error, setError] = useState(null);
    const [recordError, setRecordError] = useState(null);
    const [suggestionsOpen, setSuggestionsOpen] = useState(true);
    const [detailsOpen, setDetailsOpen] = useState(false);
    const [detailsSection, setDetailsSection] = useState("basic");
    const [selectedCharacterIds, setSelectedCharacterIds] = useState({});
    const [selectedLocationIds, setSelectedLocationIds] = useState({});
    const [selectedEntityIds, setSelectedEntityIds] = useState({});
    const [sttAvailable, setSttAvailable] = useState(false);
    const [voiceBusy, setVoiceBusy] = useState(false);
    const isDesktop = useMediaQuery("(min-width: 768px)");

    useEffect(() => {
        let cancelled = false;

        fetchSttConfigs()
            .then((configs) => {
                if (!cancelled) {
                    setSttAvailable(configs.length > 0);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setSttAvailable(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    const listedSimulation = useMemo(
        () => simulations.find((simulation) => String(simulation.id) === String(simulationId)),
        [simulationId, simulations],
    );
    const selectedSimulation = simulationDetails[simulationId] ?? listedSimulation;
    const selectedCharacters = characterCache[simulationId] ?? emptyList;
    const selectedCharactersById = useMemo(
        () => Object.fromEntries(selectedCharacters.map((character) => [String(character.id), character])),
        [selectedCharacters],
    );
    const selectedLocations = locationCache[simulationId] ?? [];
    const selectedEntities = entityCache[simulationId] ?? {};
    const userCharacter =
        selectedCharacters.find((character) => character.user_controlled) ?? selectedCharacters[0] ?? null;
    const selectedCharacterId = selectedCharacterIds[simulationId] ?? selectedCharacters[0]?.id ?? null;
    const selectedLocationId = selectedLocationIds[simulationId] ?? selectedLocations[0]?.id ?? null;
    const selectedEntityIdsForSimulation = selectedEntityIds[simulationId] ?? {};
    const selectedInventory = selectedCharacterId
        ? inventoryCache[`${simulationId}:${selectedCharacterId}`]
        : null;
    const selectedEmotion = selectedCharacterId
        ? emotionCache[`${simulationId}:${selectedCharacterId}`]
        : null;
    const selectedCharacterLocation = selectedCharacterId
        ? characterLocationCache[`${simulationId}:${selectedCharacterId}`]
        : null;
    const selectedAuditEvents = auditCache[simulationId] ?? [];
    const imageCapabilities = imageCapabilityCache[simulationId] ?? emptyObject;
    const canGenerateSceneImage = Boolean(imageCapabilities.scene_image_generator);
    const canGeneratePortraitImage = Boolean(imageCapabilities.character_portrait_image_generator);
    const suggestedActions = selectedSimulation?.suggested_actions ?? emptyList;
    const inputFormatError = useMemo(
        () => (input.trim().length > 0 ? validateInputMarkup(input) : null),
        [input],
    );
    const voiceInputDisabled = sending || Boolean(streamingRecord?.active);
    const sendDisabled = sending || streamingRecord?.active || Boolean(inputFormatError) || voiceBusy;

    async function refreshSimulationDetails(id) {
        try {
            const detail = await fetchSimulation(id);
            setSimulationDetails((current) => ({
                ...current,
                [id]: detail,
            }));
        } catch {
            // Keep cached/list data when the detail refresh fails.
        }
    }

    const refreshCharacters = useCallback(async (id) => {
        try {
            const characters = await fetchSimulationCharacters(id);
            setCharacterCache((current) => ({
                ...current,
                [id]: characters,
            }));
            setSelectedCharacterIds((current) => {
                if (current[id] || characters.length === 0) {
                    return current;
                }

                return {
                    ...current,
                    [id]: characters[0].id,
                };
            });
            return characters;
        } catch {
            // Keep cached characters available if background refresh fails.
            return emptyList;
        }
    }, []);

    async function refreshLocations(id) {
        try {
            const locations = await fetchSimulationLocations(id);
            setLocationCache((current) => ({
                ...current,
                [id]: locations,
            }));
            setSelectedLocationIds((current) => {
                if (current[id] || locations.length === 0) {
                    return current;
                }

                return {
                    ...current,
                    [id]: locations[0].id,
                };
            });
        } catch {
            // Keep cached locations available if background refresh fails.
        }
    }

    async function refreshEntities(id) {
        try {
            const [
                background,
                landmarks,
                items,
                stacks,
                equipment,
                containers,
                events,
                memories,
                intents,
            ] = await Promise.all([
                fetchSimulationBackgroundCharacters(id),
                fetchSimulationLandmarks(id),
                fetchSimulationItems(id),
                fetchSimulationStacks(id),
                fetchSimulationEquipment(id),
                fetchSimulationContainers(id),
                fetchSimulationEvents(id),
                fetchSimulationMemories(id),
                fetchSimulationIntents(id),
            ]);

            const nextEntities = {
                background,
                landmarks,
                items,
                stacks,
                equipment,
                containers,
                events,
                memories,
                intents,
            };

            setEntityCache((current) => ({
                ...current,
                [id]: nextEntities,
            }));
            setSelectedEntityIds((current) => {
                const currentSelection = current[id] ?? {};
                const nextSelection = { ...currentSelection };
                for (const section of entityDetailSections) {
                    if (nextSelection[section] || (nextEntities[section] ?? []).length === 0) {
                        continue;
                    }
                    nextSelection[section] = nextEntities[section][0].id;
                }

                if (Object.keys(nextSelection).length === Object.keys(currentSelection).length) {
                    return current;
                }

                return {
                    ...current,
                    [id]: nextSelection,
                };
            });
        } catch {
            // Keep cached entities available if background refresh fails.
        }
    }

    async function refreshAuditEvents(id) {
        try {
            const events = await fetchSimulationAuditEvents({ simulationId: id });
            setAuditCache((current) => ({ ...current, [id]: events }));
        } catch {
            setAuditCache((current) => ({ ...current, [id]: [] }));
        }
    }

    async function refreshImageCapabilities(id) {
        try {
            const assignments = await fetchSimulationImageConfigs(id);
            const capabilities = Object.fromEntries(
                assignments.map((assignment) => [assignment.component, Boolean(assignment.config)]),
            );
            setImageCapabilityCache((current) => ({ ...current, [id]: capabilities }));
        } catch {
            setImageCapabilityCache((current) => ({ ...current, [id]: {} }));
        }
    }

    async function refreshCharacterInventory(id, characterId) {
        if (!id || !characterId) {
            return;
        }

        try {
            const inventory = await fetchCharacterInventory(characterId);
            setInventoryCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: inventory,
            }));
        } catch {
            setInventoryCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: { stacks: [], equipment: [], containers: [] },
            }));
        }
    }

    async function refreshCharacterEmotion(id, characterId) {
        if (!id || !characterId) {
            return;
        }
        try {
            const emotion = await fetchCharacterEmotion({ simulationId: id, characterId });
            setEmotionCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: emotion,
            }));
        } catch {
            setEmotionCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: null,
            }));
        }
    }

    async function refreshCharacterLocation(id, characterId) {
        if (!id || !characterId) {
            return;
        }
        try {
            const location = await fetchCharacterLocation(characterId);
            setCharacterLocationCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: location,
            }));
        } catch {
            setCharacterLocationCache((current) => ({
                ...current,
                [`${id}:${characterId}`]: null,
            }));
        }
    }

    useEffect(() => {
        ensureAudioUnlockListeners();

        return () => {
            autoplayControllerRef.current?.cancel?.();
            autoplayControllerRef.current = null;
        };
    }, []);

    useEffect(() => {
        let ignore = false;

        async function loadSimulations() {
            try {
                setLoading(true);
                setError(null);

                const data = await fetchSimulations({ limit: simulationLimit, offset: 0 });

                if (ignore) {
                    return;
                }

                setSimulations(data);

                const previewEntries = await Promise.all(
                    data.map(async (simulation) => {
                        try {
                            const latestRecords = await fetchSimulationRecords({
                                simulationId: simulation.id,
                                limit: 1,
                            });
                            const latestRecord = sortRecords(latestRecords).at(-1);

                            return [simulation.id, latestRecord?.narration ?? ""];
                        } catch {
                            return [simulation.id, ""];
                        }
                    }),
                );

                if (!ignore) {
                    setPreviews(Object.fromEntries(previewEntries));
                }
            } catch (err) {
                if (!ignore) {
                    setError(err.message);
                }
            } finally {
                if (!ignore) {
                    setLoading(false);
                }
            }
        }

        startTransition(() => {
            loadSimulations();
        });

        return () => {
            ignore = true;
        };
    }, []);

    useEffect(() => {
        let ignore = false;

        async function loadInitialRecords() {
            try {
                setRecordLoading(true);
                setRecordError(null);

                const data = await fetchSimulationRecords({
                    simulationId,
                    limit: recordLimit,
                });

                if (!ignore) {
                    setRecords(sortRecords(data));
                }
            } catch (err) {
                if (!ignore) {
                    setRecordError(err.message);
                }
            } finally {
                if (!ignore) {
                    setRecordLoading(false);
                }
            }
        }

        if (simulationId) {
            startTransition(() => {
                loadInitialRecords();
                refreshSimulationDetails(simulationId);
                refreshCharacters(simulationId).then(() => refreshEntities(simulationId));
                refreshLocations(simulationId);
                refreshImageCapabilities(simulationId);
            });
        }

        return () => {
            ignore = true;
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
        };
    }, [refreshCharacters, simulationId]);

    useEffect(() => {
        if (!detailsOpen || !simulationId) {
            return;
        }

        refreshSimulationDetails(simulationId);
        refreshCharacters(simulationId).then(() => refreshEntities(simulationId));
        refreshLocations(simulationId);
        refreshAuditEvents(simulationId);
        refreshImageCapabilities(simulationId);
    }, [detailsOpen, refreshCharacters, simulationId]);

    useEffect(() => {
        if (!detailsOpen || detailsSection !== "characters") {
            return;
        }

        refreshCharacterInventory(simulationId, selectedCharacterId);
        refreshCharacterEmotion(simulationId, selectedCharacterId);
        refreshCharacterLocation(simulationId, selectedCharacterId);
    }, [detailsOpen, detailsSection, simulationId, selectedCharacterId]);

    useEffect(() => {
        recordsEndRef.current?.scrollIntoView({ block: "end" });
    }, [
        records,
        streamingRecord?.message,
        streamingRecord?.blocks,
        streamingRecord?.error,
        streamingRecord?.stageName,
        recordLoading,
    ]);

    useEffect(() => {
        const inputElement = composerInputRef.current;

        if (!inputElement) {
            return;
        }

        inputElement.style.height = "auto";
        inputElement.style.height = `${Math.min(inputElement.scrollHeight, 160)}px`;
        inputElement.style.overflowY = inputElement.scrollHeight > 160 ? "auto" : "hidden";
    }, [input]);

    function closeRunStream() {
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
    }

    async function refreshSimulationTurns(id = simulationId) {
        if (!id) {
            return;
        }

        const data = await fetchSimulationRecords({
            simulationId: id,
            limit: recordLimit,
        });
        const sortedTurns = sortRecords(data);

        setRecords(sortedTurns);
        setPreviews((current) => ({
            ...current,
            [id]: sortedTurns.at(-1)?.narration ?? "",
        }));

        return sortedTurns;
    }

    async function autoplayTurnIfEnabled(id, turn) {
        if (!turn?.id || autoplayedTurnIdsRef.current.has(turn.id)) {
            return;
        }

        let genConfig;
        try {
            genConfig = await fetchSimulationTtsGenerationConfig(id);
        } catch {
            return;
        }

        if (genConfig.mode !== "auto" || !genConfig.autoplay_in_browser) {
            return;
        }

        const voiceBlocks = (narrationBlocksFromValue(turn.narration_blocks) ?? []).filter(
            (block) => (block.type === "narration" || block.type === "speech") && block.id,
        );

        if (voiceBlocks.length === 0) {
            return;
        }

        autoplayedTurnIdsRef.current.add(turn.id);
        autoplayControllerRef.current?.cancel?.();

        const poll = waitForBlocksVoiced({
            turnId: turn.id,
            blockIds: voiceBlocks.map((block) => block.id),
            fetchTurnPresentation,
        });
        autoplayControllerRef.current = poll;

        const voiced = await poll.done;

        // A newer turn's autoplay (or unmount cleanup) may have superseded this one while polling.
        if (autoplayControllerRef.current !== poll) {
            return;
        }

        const voicedById = new Map(voiced.map((block) => [block.id, block]));
        const orderedUrls = voiceBlocks
            .map((block) => voicedById.get(block.id))
            .filter(Boolean)
            .map((block) => getMediaUrl(block.voice_media_id));

        if (orderedUrls.length === 0) {
            autoplayControllerRef.current = null;
            return;
        }

        const playback = playAudioUrlSequence(orderedUrls);
        autoplayControllerRef.current = playback;
        await playback.done;

        if (autoplayControllerRef.current === playback) {
            autoplayControllerRef.current = null;
        }
    }

    function finishRunStream({ runId, error = null }) {
        closeRunStream();
        const finalError = error ?? streamErrorRef.current;
        const previousLastId = lastRecordIdBeforeRunRef.current;

        setStreamingRecord((current) => {
            if (!current || current.runId !== runId) {
                return current;
            }

            return {
                ...current,
                active: false,
                error: finalError,
            };
        });

        refreshSimulationTurns()
            .then((sortedTurns) => {
                if (!finalError) {
                    setStreamingRecord((current) => (current?.runId === runId ? null : current));
                }

                const newestTurn = sortedTurns?.at(-1);
                if (!finalError && newestTurn && newestTurn.id !== previousLastId) {
                    autoplayTurnIfEnabled(simulationId, newestTurn).catch(() => {});
                }
            })
            .catch((err) => {
                setRecordError(err.message);
            });

        if (!finalError) {
            // Suggestions are refreshed alongside the turn commit on the backend; re-fetch the
            // simulation so the composer picks up the latest suggested_actions once the run settles.
            refreshSimulationDetails(simulationId);
        }
    }

    function connectRunEvents(runId) {
        closeRunStream();
        streamErrorRef.current = null;
        streamReceivedNarrationRef.current = false;

        const eventSource = new EventSource(getSimulationRunUrl({ simulationId, threadId: runId }));
        eventSourceRef.current = eventSource;

        eventSource.addEventListener("chunk", (event) => {
            try {
                const chunk = JSON.parse(event.data);
                const stageName = stageFromStateChunk(chunk);
                const blocks = narrationBlocksFromValue(chunk.narration_blocks ?? chunk.narration);

                if (stageName) {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId) {
                            return current;
                        }

                        return {
                            ...current,
                            stageName,
                            blocks: blocks ?? current.blocks,
                            message: blocks ? narrationTextFromBlocks(blocks) : chunk.narration ?? current.message,
                        };
                    });
                }

                if (chunk?.narration || chunk?.narration_blocks) {
                    streamReceivedNarrationRef.current = true;
                }
            } catch (err) {
                streamErrorRef.current = err.message;
                setStreamingRecord((current) => {
                    if (!current || current.runId !== runId) {
                        return current;
                    }

                    return {
                        ...current,
                        pendingError: err.message,
                    };
                });
            }
        });

        eventSource.addEventListener("status", (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.code === "still_generating") {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId) {
                            return current;
                        }

                        return {
                            ...current,
                            stageName: current.stageName || "narrator",
                            pendingError: payload.message,
                        };
                    });
                    return;
                }

                streamErrorRef.current = payload.message;
                finishRunStream({
                    runId,
                    error: payload.message,
                });
            } catch (err) {
                streamErrorRef.current = err.message;
                finishRunStream({
                    runId,
                    error: err.message,
                });
            }
        });

        eventSource.addEventListener("error", (event) => {
            if ("data" in event && event.data !== undefined) {
                let errorMessage = event.data;
                try {
                    const payload = JSON.parse(event.data);
                    errorMessage = payload.message ?? event.data;
                } catch {
                    // Keep the raw stream error text.
                }
                streamErrorRef.current = errorMessage;
                finishRunStream({
                    runId,
                    error: errorMessage,
                });
                return;
            }

            if (streamReceivedNarrationRef.current) {
                finishRunStream({ runId });
                return;
            }

            if (eventSource.readyState === EventSource.CLOSED || streamErrorRef.current) {
                finishRunStream({
                    runId,
                    error: streamErrorRef.current,
                });
            }
        });

        eventSource.addEventListener("done", () => {
            finishRunStream({ runId });
        });

        eventSource.addEventListener("cancelled", (event) => {
            finishRunStream({
                runId,
                error: event.data || t("simulationChat.cancelled"),
            });
        });
    }

    async function handleSend() {
        if (sendDisabled) {
            if (inputFormatError) {
                setSendError(inputFormatError);
            }
            return;
        }

        const rawInput = input;
        const trimmedInput = rawInput.trim();
        const userInput = trimmedInput.length === 0 ? null : rawInput;
        const localRecordId = `local-user-${Date.now()}`;
        lastRecordIdBeforeRunRef.current = records.at(-1)?.id ?? null;

        try {
            setSending(true);
            setSendError(null);
            setInput("");

            if (userInput !== null) {
                setRecords((current) => [
                    ...current,
                    {
                        id: localRecordId,
                        turn_number: Number.MAX_SAFE_INTEGER,
                        type: "user_input",
                        narration: userInput,
                    },
                ]);
            }

            const data = await sendSimulationInput({
                simulationId,
                userInput,
            });

            setStreamingRecord({
                runId: data.run_id,
                message: "",
                blocks: [],
                stageName: "",
                pendingError: null,
                error: null,
                active: true,
            });
            connectRunEvents(data.run_id);
        } catch (err) {
            if (userInput !== null) {
                setRecords((current) => current.filter((record) => record.id !== localRecordId));
            }
            setSendError(err.message);
        } finally {
            setSending(false);
        }
    }

    function handleSuggestionClick(suggestion) {
        if (sendDisabled) {
            return;
        }

        setInput(suggestion);
        composerInputRef.current?.focus();
    }

    function handleComposerKeyDown(event) {
        if (event.key !== "Enter" || event.shiftKey) {
            return;
        }

        if (sendDisabled) {
            return;
        }

        event.preventDefault();
        handleSend();
    }

    function handleVoiceTranscribed(text) {
        if (!text) {
            return;
        }

        setInput((current) => (current.trim().length === 0 ? text : `${current.trimEnd()} ${text}`));
        composerInputRef.current?.focus();
    }

    if (loading) {
        return <p className="status-text">{t("simulationChat.loading")}</p>;
    }

    if (error) {
        return <p className="status-text error-text">{t("simulationChat.error", { error })}</p>;
    }

    return (
        <section className="simulation-chat-layout">
            <aside className="conversation-sidebar" aria-label={t("simulationChat.conversationListLabel")}>
                <div className="conversation-sidebar-header">
                    <h1>{t("simulationChat.title")}</h1>
                    <Link to="/" className="secondary-button">
                        {t("simulationChat.back")}
                    </Link>
                </div>

                <div className="conversation-list">
                    {simulations.map((simulation) => (
                        <SimulationConversationItem
                            key={simulation.id}
                            simulation={simulation}
                            preview={previews[simulation.id]}
                        />
                    ))}
                </div>
            </aside>

            <div className="chat-panel">
                <header className="chat-header">
                    <button
                        type="button"
                        className="chat-header-profile"
                        onClick={() => setDetailsOpen(true)}
                        disabled={!selectedSimulation}
                    >
                        <SimulationAvatar simulation={selectedSimulation} className="chat-header-avatar" />
                        <span className="chat-header-text">
                            <span className="chat-header-title">
                                {selectedSimulation?.name ?? t("simulationChat.selectedFallback")}
                            </span>
                            <span className="chat-header-description">
                                {selectedSimulation?.description ?? t("simulationChat.selectedDescriptionFallback")}
                            </span>
                        </span>
                    </button>
                </header>

                <div className="chat-records-wrapper">
                    <div className="chat-records" aria-live="polite">
                        {recordLoading ? (
                            <p className="status-text">{t("simulationChat.recordsLoading")}</p>
                        ) : recordError ? (
                            <p className="status-text error-text">
                                {t("simulationChat.recordsError", { error: recordError })}
                            </p>
                        ) : records.length === 0 && !streamingRecord ? (
                            <p className="status-text">{t("simulationChat.emptyRecords")}</p>
                        ) : (
                            records.map((record) => (
                                <ChatRecord
                                    key={record.id}
                                    record={record}
                                    simulation={selectedSimulation}
                                    charactersById={selectedCharactersById}
                                    userCharacter={userCharacter}
                                    canGenerateScene={canGenerateSceneImage}
                                    canGeneratePortrait={canGeneratePortraitImage}
                                />
                            ))
                        )}

                        {streamingRecord ? (
                            <StreamingChatRecord
                                message={streamingRecord.message}
                                blocks={streamingRecord.blocks}
                                error={streamingRecord.error}
                                active={streamingRecord.active}
                                stageName={streamingRecord.stageName}
                                simulation={selectedSimulation}
                                charactersById={selectedCharactersById}
                            />
                        ) : null}
                        <div ref={recordsEndRef} />
                    </div>
                </div>

                <ActionSuggestions
                    suggestions={suggestedActions}
                    open={suggestionsOpen}
                    onToggle={() => setSuggestionsOpen((current) => !current)}
                    onSelect={handleSuggestionClick}
                    disabled={sendDisabled}
                />

                <form
                    className="chat-composer"
                    onSubmit={(event) => {
                        event.preventDefault();
                        handleSend();
                    }}
                >
                    <div className="chat-composer-input-wrap">
                        <textarea
                            ref={composerInputRef}
                            className="chat-composer-input"
                            value={input}
                            rows={2}
                            disabled={voiceBusy}
                            placeholder={t("simulationChat.inputPlaceholder")}
                            onChange={(event) => setInput(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                        />
                        {inputFormatError ? (
                            <p className="chat-send-error">{inputFormatError}</p>
                        ) : sendError ? (
                            <p className="chat-send-error">{t("simulationChat.sendError", { error: sendError })}</p>
                        ) : null}
                    </div>
                    {sttAvailable ? (
                        <VoiceRecorderButton
                            disabled={voiceInputDisabled}
                            isDesktop={isDesktop}
                            onBusyChange={setVoiceBusy}
                            onTranscribed={handleVoiceTranscribed}
                        />
                    ) : null}
                    <button
                        type="submit"
                        className="chat-send-button"
                        disabled={sendDisabled}
                        aria-label={t("simulationChat.send")}
                        title={t("simulationChat.send")}
                    >
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <path d="M3.4 20.4 21 12 3.4 3.6 3 10l10 2-10 2 .4 6.4Z" />
                        </svg>
                    </button>
                </form>
            </div>

            {detailsOpen ? (
                <SimulationDetailsModal
                    simulation={selectedSimulation}
                    characters={selectedCharacters}
                    locations={selectedLocations}
                    entities={selectedEntities}
                    inventory={selectedInventory}
                    emotion={selectedEmotion}
                    characterLocation={selectedCharacterLocation}
                    auditEvents={selectedAuditEvents}
                    imageCapabilities={imageCapabilities}
                    activeSection={detailsSection}
                    selectedCharacterId={selectedCharacterId}
                    selectedLocationId={selectedLocationId}
                    selectedEntityIds={selectedEntityIdsForSimulation}
                    onActiveSectionChange={setDetailsSection}
                    onSelectedCharacterIdChange={(characterId) =>
                        setSelectedCharacterIds((current) => ({
                            ...current,
                            [simulationId]: characterId,
                        }))
                    }
                    onSelectedLocationIdChange={(locationId) =>
                        setSelectedLocationIds((current) => ({
                            ...current,
                            [simulationId]: locationId,
                        }))
                    }
                    onSelectedEntityIdChange={(section, entityId) =>
                        setSelectedEntityIds((current) => ({
                            ...current,
                            [simulationId]: {
                                ...(current[simulationId] ?? {}),
                                [section]: entityId,
                            },
                        }))
                    }
                    onClose={() => setDetailsOpen(false)}
                />
            ) : null}
        </section>
    );
}
