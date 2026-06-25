import { useEffect, useMemo, useRef, useState, startTransition } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
    fetchSimulationRecords,
    fetchSimulations,
    getSimulationCoverUrl,
    sendSimulationInput,
} from "@/api/simulations";
import placeholderImage from "@/assets/placeholder/world.svg";

const simulationLimit = 24;
const recordLimit = 50;

function sortRecords(records) {
    return [...records].sort((a, b) => a.turn_number - b.turn_number || a.id - b.id);
}

function isUserRecord(record) {
    return record.type === "user_input";
}

function SimulationAvatar({ simulation, className = "chat-avatar" }) {
    const [failedSimulationId, setFailedSimulationId] = useState(null);
    const imageSrc =
        simulation?.id && failedSimulationId !== simulation.id
            ? getSimulationCoverUrl(simulation.id)
            : placeholderImage;

    return (
        <img
            src={imageSrc}
            alt={simulation?.name ?? ""}
            className={className}
            onError={() => setFailedSimulationId(simulation?.id ?? null)}
        />
    );
}

function UserAvatar({ label }) {
    return (
        <div className="chat-avatar user-avatar" aria-hidden="true">
            {label.slice(0, 1)}
        </div>
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

function ChatRecord({ record, simulation }) {
    const { t } = useTranslation();
    const userRecord = isUserRecord(record);
    const authorName = userRecord ? t("simulationChat.userName") : simulation?.name;

    return (
        <article className={`chat-message${userRecord ? " user" : " simulation"}`}>
            {userRecord ? <UserAvatar label={authorName} /> : <SimulationAvatar simulation={simulation} />}
            <div className="chat-message-content">
                <div className="chat-message-author">{authorName}</div>
                <div className="chat-bubble">
                    <p>{record.narration}</p>
                </div>
            </div>
        </article>
    );
}

function TypingIndicator({ stageName }) {
    return (
        <span className="typing-state">
            {stageName ? (
                <span className="typing-stage">
                    {stageName} completed
                </span>
            ) : null}
            <span className="typing-indicator" aria-label="Typing">
                <span />
                <span />
                <span />
            </span>
        </span>
    );
}

function StreamingChatRecord({ message, error, active, stageName, simulation }) {
    const { t } = useTranslation();
    const hasMessage = message.length > 0;

    return (
        <article className="chat-message simulation">
            <SimulationAvatar simulation={simulation} />
            <div className="chat-message-content">
                <div className="chat-message-author">
                    {simulation?.name ?? t("simulationChat.selectedFallback")}
                </div>
                <div className="chat-bubble">
                    {hasMessage ? <p>{message}</p> : active ? <TypingIndicator stageName={stageName} /> : null}
                    {!active && error ? <p className="chat-stream-error">{error}</p> : null}
                </div>
            </div>
        </article>
    );
}

export function SimulationChatPage() {
    const { t } = useTranslation();
    const { simulationId } = useParams();
    const recordsEndRef = useRef(null);
    const eventSourceRef = useRef(null);
    const composerInputRef = useRef(null);
    const streamErrorRef = useRef(null);
    const [simulations, setSimulations] = useState([]);
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

    const selectedSimulation = useMemo(
        () => simulations.find((simulation) => String(simulation.id) === String(simulationId)),
        [simulationId, simulations],
    );

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
                                startFrom: null,
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
                    startFrom: null,
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
            });
        }

        return () => {
            ignore = true;
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
        };
    }, [simulationId]);

    useEffect(() => {
        recordsEndRef.current?.scrollIntoView({ block: "end" });
    }, [records, streamingRecord?.message, streamingRecord?.error, streamingRecord?.stageName, recordLoading]);

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

    function finishRunStream({ runId, error = null }) {
        closeRunStream();
        const finalError = error ?? streamErrorRef.current;

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
    }

    function connectRunEvents(runId) {
        closeRunStream();
        streamErrorRef.current = null;

        const eventSource = new EventSource(`/api/simulations/runs/${runId}/events`);
        eventSourceRef.current = eventSource;

        eventSource.addEventListener("token", (event) => {
            try {
                const payload = JSON.parse(event.data);
                const node = payload.metadata?.langgraph_node;

                if (typeof node === "string" && node.startsWith("narrate_")) {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId) {
                            return current;
                        }

                        return {
                            ...current,
                            message: `${current.message}${payload.message ?? ""}`,
                        };
                    });
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

        eventSource.addEventListener("stage_update", (event) => {
            try {
                const payload = JSON.parse(event.data);
                const stageName = Object.keys(payload).at(-1);

                if (stageName) {
                    setStreamingRecord((current) => {
                        if (!current || current.runId !== runId || current.message.length > 0) {
                            return current;
                        }

                        return {
                            ...current,
                            stageName,
                        };
                    });
                }
            } catch {
                // Stage updates are only progress hints; malformed progress data should not stop the run.
            }
        });

        eventSource.addEventListener("error", (event) => {
            if ("data" in event && event.data !== undefined) {
                streamErrorRef.current = event.data;
                finishRunStream({
                    runId,
                    error: event.data,
                });
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
        if (sending || streamingRecord?.active) {
            return;
        }

        const rawInput = input;
        const trimmedInput = rawInput.trim();
        const userInput = trimmedInput.length === 0 ? null : rawInput;
        const localRecordId = `local-user-${Date.now()}`;

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

    function handleComposerKeyDown(event) {
        if (event.key !== "Enter" || event.shiftKey) {
            return;
        }

        event.preventDefault();
        handleSend();
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
                    <SimulationAvatar simulation={selectedSimulation} className="chat-header-avatar" />
                    <div className="chat-header-text">
                        <h2>{selectedSimulation?.name ?? t("simulationChat.selectedFallback")}</h2>
                        <p>{selectedSimulation?.description ?? t("simulationChat.selectedDescriptionFallback")}</p>
                    </div>
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
                                />
                            ))
                        )}

                        {streamingRecord ? (
                            <StreamingChatRecord
                                message={streamingRecord.message}
                                error={streamingRecord.error}
                                active={streamingRecord.active}
                                stageName={streamingRecord.stageName}
                                simulation={selectedSimulation}
                            />
                        ) : null}
                        <div ref={recordsEndRef} />
                    </div>
                </div>

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
                            disabled={sending || streamingRecord?.active}
                            placeholder={t("simulationChat.inputPlaceholder")}
                            onChange={(event) => setInput(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                        />
                        {sendError ? (
                            <p className="chat-send-error">{t("simulationChat.sendError", { error: sendError })}</p>
                        ) : null}
                    </div>
                    <button
                        type="submit"
                        className="chat-send-button"
                        disabled={sending || streamingRecord?.active}
                        aria-label={t("simulationChat.send")}
                        title={t("simulationChat.send")}
                    >
                        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                            <path d="M3.4 20.4 21 12 3.4 3.6 3 10l10 2-10 2 .4 6.4Z" />
                        </svg>
                    </button>
                </form>
            </div>
        </section>
    );
}
