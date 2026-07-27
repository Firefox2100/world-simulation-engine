import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { transcribeSpeech } from "@/api/speechRecognition";

const SLIDE_CANCEL_THRESHOLD = 60;

function formatElapsed(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

function extensionForMimeType(mimeType) {
    if (mimeType?.includes("webm")) {
        return "webm";
    }
    if (mimeType?.includes("ogg")) {
        return "ogg";
    }
    if (mimeType?.includes("mp4") || mimeType?.includes("m4a")) {
        return "mp4";
    }
    if (mimeType?.includes("wav")) {
        return "wav";
    }
    return "dat";
}

export function VoiceRecorderButton({ disabled, isDesktop, onBusyChange, onTranscribed }) {
    const { t } = useTranslation();
    const [status, setStatus] = useState("idle");
    const [armed, setArmed] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const [error, setError] = useState(null);

    const mediaRecorderRef = useRef(null);
    const streamRef = useRef(null);
    const chunksRef = useRef([]);
    const timerRef = useRef(null);
    const dragStartXRef = useRef(0);
    const cancelledRef = useRef(false);

    useEffect(() => {
        onBusyChange?.(status !== "idle");
    }, [status, onBusyChange]);

    useEffect(() => {
        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
            streamRef.current?.getTracks().forEach((track) => track.stop());
            if (mediaRecorderRef.current?.state === "recording") {
                cancelledRef.current = true;
                mediaRecorderRef.current.stop();
            }
        };
    }, []);

    function releaseStream() {
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
    }

    async function startRecording() {
        setError(null);
        cancelledRef.current = false;

        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            setError(t("simulationChat.voiceInput.unsupported"));
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;
            chunksRef.current = [];

            const recorder = new MediaRecorder(stream);
            mediaRecorderRef.current = recorder;

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    chunksRef.current.push(event.data);
                }
            };

            recorder.onstop = () => {
                releaseStream();
                if (timerRef.current) {
                    clearInterval(timerRef.current);
                    timerRef.current = null;
                }

                if (cancelledRef.current || chunksRef.current.length === 0) {
                    setStatus("idle");
                    setElapsed(0);
                    return;
                }

                const mimeType = recorder.mimeType || "audio/webm";
                const blob = new Blob(chunksRef.current, { type: mimeType });
                void transcribe(blob, mimeType);
            };

            recorder.start();
            setStatus("recording");
            setElapsed(0);
            setArmed(false);
            timerRef.current = setInterval(() => {
                setElapsed((current) => current + 1);
            }, 1000);
        } catch (err) {
            setError(
                err?.name === "NotAllowedError" || err?.name === "SecurityError"
                    ? t("simulationChat.voiceInput.permissionDenied")
                    : t("simulationChat.voiceInput.startError"),
            );
        }
    }

    function stopRecording({ cancel = false } = {}) {
        cancelledRef.current = cancel;
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state === "inactive") {
            releaseStream();
            setStatus("idle");
            return;
        }

        recorder.stop();
    }

    async function transcribe(blob, mimeType) {
        setStatus("transcribing");

        try {
            const result = await transcribeSpeech(blob, {
                filename: `recording.${extensionForMimeType(mimeType)}`,
            });
            onTranscribed?.(result.text);
        } catch (err) {
            setError(err.message);
        } finally {
            setElapsed(0);
            setStatus("idle");
        }
    }

    function handleDesktopButtonClick() {
        if (disabled) {
            return;
        }
        if (status === "idle") {
            startRecording();
        } else if (status === "recording") {
            stopRecording({ cancel: false });
        }
    }

    function handleDesktopCancelClick(event) {
        event.stopPropagation();
        stopRecording({ cancel: true });
    }

    function handlePointerDown(event) {
        if (disabled || status !== "idle") {
            return;
        }
        event.currentTarget.setPointerCapture?.(event.pointerId);
        dragStartXRef.current = event.clientX;
        startRecording();
    }

    function handlePointerMove(event) {
        if (status !== "recording") {
            return;
        }
        const delta = event.clientX - dragStartXRef.current;
        setArmed(delta < -SLIDE_CANCEL_THRESHOLD);
    }

    function handlePointerUp() {
        if (status !== "recording") {
            return;
        }
        stopRecording({ cancel: armed });
        setArmed(false);
    }

    const busy = status !== "idle";
    const statusMessage =
        status === "recording"
            ? isDesktop
                ? t("simulationChat.voiceInput.recording", { time: formatElapsed(elapsed) })
                : armed
                    ? t("simulationChat.voiceInput.releaseToCancel")
                    : t("simulationChat.voiceInput.slideToCancelWithTime", { time: formatElapsed(elapsed) })
            : status === "transcribing"
                ? t("simulationChat.voiceInput.transcribing")
                : null;

    return (
        <div className="voice-recorder">
            <div className="voice-recorder-buttons">
                {isDesktop && status === "recording" ? (
                    <button
                        type="button"
                        className="voice-cancel-button"
                        onClick={handleDesktopCancelClick}
                        aria-label={t("simulationChat.voiceInput.cancel")}
                        title={t("simulationChat.voiceInput.cancel")}
                    >
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <path
                                d="M6 6l12 12M18 6 6 18"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                            />
                        </svg>
                    </button>
                ) : null}

                <button
                    type="button"
                    className={`voice-record-button${busy ? " active" : ""}${armed ? " armed" : ""}`}
                    disabled={disabled && status === "idle"}
                    aria-label={
                        status === "recording"
                            ? t("simulationChat.voiceInput.stop")
                            : t("simulationChat.voiceInput.start")
                    }
                    title={
                        status === "recording"
                            ? t("simulationChat.voiceInput.stop")
                            : t("simulationChat.voiceInput.start")
                    }
                    onClick={isDesktop ? handleDesktopButtonClick : undefined}
                    onPointerDown={!isDesktop ? handlePointerDown : undefined}
                    onPointerMove={!isDesktop ? handlePointerMove : undefined}
                    onPointerUp={!isDesktop ? handlePointerUp : undefined}
                    onPointerCancel={!isDesktop ? handlePointerUp : undefined}
                >
                    {isDesktop && status === "recording" ? (
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <rect x="7" y="7" width="10" height="10" rx="2" />
                        </svg>
                    ) : (
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" />
                            <path
                                d="M5 11a7 7 0 0 0 14 0M12 18v3"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                            />
                        </svg>
                    )}
                </button>
            </div>

            {statusMessage ? (
                <p className={`voice-recorder-status${armed ? " armed" : ""}`}>{statusMessage}</p>
            ) : null}
            {error ? <p className="chat-send-error">{error}</p> : null}
        </div>
    );
}
