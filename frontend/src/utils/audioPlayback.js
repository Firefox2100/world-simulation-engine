// Browsers block audio playback that isn't the direct, synchronous result of a user gesture
// (click/tap/keypress). A gesture-triggered click on a segment's own play button is always safe -
// but auto-playing a turn's segments once TTS generation finishes in the background happens well
// after any gesture, so it would otherwise be silently blocked.
//
// The fix (the same pattern web audio libraries like Howler.js and Tone.js use to support
// autoplay-after-interaction): the first real gesture anywhere on the page "unlocks" audio for the
// rest of the session by (a) creating/resuming a shared AudioContext, and (b) doing a play-then-
// immediately-pause on a shared <audio> element. Later programmatic playback reuses that same
// already-unlocked context/element, which browsers treat as a continuation of a permitted media
// session rather than a fresh (blockable) autoplay attempt.

const UNLOCK_EVENTS = ["pointerdown", "keydown"];

let unlocked = false;
let audioContext = null;
let sharedAudio = null;

function getAudioContextClass() {
    if (typeof window === "undefined") {
        return null;
    }

    return window.AudioContext || window.webkitAudioContext || null;
}

function getSharedAudioElement() {
    if (!sharedAudio) {
        sharedAudio = new Audio();
        sharedAudio.preload = "auto";
    }

    return sharedAudio;
}

function primeAudioContext() {
    const AudioContextClass = getAudioContextClass();
    if (!AudioContextClass) {
        return;
    }

    if (!audioContext) {
        try {
            audioContext = new AudioContextClass();
        } catch {
            return;
        }
    }

    if (audioContext.state === "suspended" && typeof audioContext.resume === "function") {
        audioContext.resume().catch(() => {});
    }
}

function primeSharedAudioElement() {
    const audio = getSharedAudioElement();

    try {
        const playAttempt = audio.play();
        if (playAttempt && typeof playAttempt.then === "function") {
            playAttempt.then(() => audio.pause()).catch(() => {});
        } else {
            audio.pause();
        }
    } catch {
        // Best effort - some environments (or an empty src) may throw synchronously.
    }
}

function unlockAudio() {
    if (unlocked) {
        return;
    }

    unlocked = true;
    primeAudioContext();
    primeSharedAudioElement();
}

/** Call once (e.g. on app/page mount) to arm the first-gesture unlock. Idempotent. */
export function ensureAudioUnlockListeners() {
    if (typeof document === "undefined" || unlocked) {
        return;
    }

    function handleGesture() {
        unlockAudio();
        UNLOCK_EVENTS.forEach((event) => document.removeEventListener(event, handleGesture));
    }

    UNLOCK_EVENTS.forEach((event) => document.addEventListener(event, handleGesture, { passive: true }));
}

export function isAudioUnlocked() {
    return unlocked;
}

/**
 * Plays a list of URLs back-to-back on a single shared <audio> element, waiting for each one to
 * finish before starting the next. Also unlocks audio itself (covers the case where a manual
 * segment click - itself a real gesture - is the very first playback attempt of the session).
 * Never throws: if playback is blocked (no gesture has ever occurred), it stops silently after
 * the first failed play() rather than erroring.
 *
 * Returns `{ cancel, done }` - call `cancel()` to stop mid-sequence; `done` resolves once the
 * sequence finishes, is cancelled, or is blocked.
 */
export function playAudioUrlSequence(urls, { onTrackStart } = {}) {
    unlockAudio();
    const audio = getSharedAudioElement();
    let cancelled = false;

    async function run() {
        for (const url of urls) {
            if (cancelled) {
                return;
            }

            onTrackStart?.(url);
            audio.src = url;

            try {
                await audio.play();
            } catch {
                return;
            }

            if (cancelled) {
                return;
            }

            await new Promise((resolve) => {
                function onEnded() {
                    audio.removeEventListener("ended", onEnded);
                    resolve();
                }

                audio.addEventListener("ended", onEnded);
            });
        }
    }

    const done = run();

    return {
        cancel() {
            cancelled = true;
            audio.pause();
        },
        done,
    };
}
