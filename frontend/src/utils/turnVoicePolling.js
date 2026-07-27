// Polls a turn's presentation until the requested narration/speech blocks have voice audio
// attached, so auto-play can wait for background TTS generation to catch up with a freshly
// generated turn rather than racing it. No existing poll-with-timeout pattern exists elsewhere in
// this codebase (turns arrive over SSE, not polling), so this is purpose-built.

function findVoicedBlocks(record, blockIds) {
    const byId = new Map((record?.narration_blocks ?? []).map((block) => [block.id, block]));

    return blockIds
        .map((id) => byId.get(id))
        .filter((block) => block && block.voice_media_id);
}

/**
 * Polls `fetchTurnPresentation(turnId)` until every id in `blockIds` has a `voice_media_id`, or
 * `timeoutMs` elapses. Never rejects: on timeout it resolves with whatever subset of blocks ended
 * up voiced (possibly empty), and a failed fetch is treated as "not ready yet" and retried.
 *
 * Returns `{ cancel, done }` - `cancel()` stops polling immediately; `done` resolves to the array
 * of voiced blocks found (in `blockIds` order).
 */
export function waitForBlocksVoiced({
    turnId,
    blockIds,
    fetchTurnPresentation,
    intervalMs = 1500,
    timeoutMs = 30000,
}) {
    let cancelled = false;
    let timeoutHandle = null;
    let settle = null;

    const done = new Promise((resolve) => {
        settle = resolve;
        const startedAt = Date.now();

        async function poll() {
            if (cancelled) {
                return;
            }

            let record = null;
            try {
                record = await fetchTurnPresentation(turnId);
            } catch {
                // Treat a failed poll tick as "not ready yet" and retry on the next interval.
            }

            if (cancelled) {
                return;
            }

            const voiced = record ? findVoicedBlocks(record, blockIds) : [];
            if (voiced.length >= blockIds.length || Date.now() - startedAt >= timeoutMs) {
                resolve(voiced);
                return;
            }

            timeoutHandle = setTimeout(poll, intervalMs);
        }

        poll();
    });

    return {
        cancel() {
            if (cancelled) {
                return;
            }

            cancelled = true;
            if (timeoutHandle) {
                clearTimeout(timeoutHandle);
            }

            settle([]);
        },
        done,
    };
}
